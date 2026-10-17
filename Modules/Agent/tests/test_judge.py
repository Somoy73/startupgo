"""The judge: reviewing research and evaluation work, and the redo loops it drives."""

import copy
import re

from startup_agent.errors import AgentError
from startup_agent.graph import build_agent_graph
from startup_agent.judge import Judge, JudgeSettings, ResearchFeedback
from startup_agent.record import StartupRecord

from .conftest import RESPONSES, SEARCH_HITS, FakeSearch, build_test_agent
from .helpers import FakeLLM, scalar

NO_REQUIRED = JudgeSettings(required_fields=())


def entry_for(tmp_path, **kwargs):
    agent, _ = build_test_agent(tmp_path, **kwargs)
    return agent, agent.profile(name="Acme Ocean", website="https://acme.fi").to_dict()


def judge_pointing_at(field_value: str, reason: str = "the quote does not say this"):
    """A judge LLM response marking the fact whose value contains ``field_value`` as unsupported."""

    def respond(user: str) -> dict:
        verdicts = []
        for match in re.finditer(r"\[(\d+)\] field: .*?\n    value: (.*?)\n", user):
            unsupported = field_value in match.group(2)
            verdicts.append({"id": int(match.group(1)), "supported": not unsupported, "reason": reason if unsupported else "ok"})
        return {"verdicts": verdicts}

    return respond


class TestResearchReview:
    def test_failed_section_is_sent_back(self, tmp_path):
        _, entry = entry_for(tmp_path)
        entry["errors"].append({"stage": "section D", "url": "", "message": "429 quota"})
        review = Judge(NO_REQUIRED).review_research(entry, round=1, can_redo=True)
        assert review.verdict == "redo"
        assert review.feedback.sections == ["D"]
        assert "failed" in review.feedback.notes["D"][0]

    def test_no_rounds_left_turns_issues_into_notes(self, tmp_path):
        _, entry = entry_for(tmp_path)
        entry["errors"].append({"stage": "section D", "url": "", "message": "429 quota"})
        review = Judge(NO_REQUIRED).review_research(entry, round=3, can_redo=False)
        assert review.verdict == "accept_with_issues" and review.feedback is None
        assert all(i.action == "note" for i in review.issues)

    def test_many_rejections_redo_the_section_with_reasons(self, tmp_path):
        _, entry = entry_for(tmp_path)
        entry["rejected_extractions"] = [
            {"field": f, "value": "x", "evidence": "y", "source_url": "", "reason": "evidence quote not found in any source document"}
            for f in ("dev_stage", "tech_description", "research_origin")
        ]
        review = Judge(NO_REQUIRED).review_research(entry, round=1, can_redo=True)
        assert review.feedback.sections == ["C"]
        assert "dev_stage: evidence quote not found" in review.feedback.notes["C"][0]

    def test_unsupported_fact_is_dropped_and_its_section_redone(self, tmp_path):
        _, entry = entry_for(tmp_path)
        llm = FakeLLM({"judge": judge_pointing_at("Maria Virtanen", "the quote names her but not as a founder")})
        review = Judge(NO_REQUIRED, llm=llm).review_research(entry, round=1, can_redo=True)
        (drop,) = review.feedback.drop
        assert drop["field"] == "founders" and drop["value"]["name"] == "Maria Virtanen"
        assert review.feedback.sections == ["F"]
        assert "not supported" in review.feedback.notes["F"][0]
        assert "registry" not in llm.calls[0]["user"]  # registry facts are not sent for checking

    def test_support_check_failure_is_only_a_note(self, tmp_path):
        _, entry = entry_for(tmp_path)

        class DownLLM:
            def complete_json(self, **_):
                raise AgentError("429 quota")

        review = Judge(NO_REQUIRED, llm=DownLLM()).review_research(entry, round=1, can_redo=True)
        assert review.verdict == "accept_with_issues"
        assert review.issues[0].code == "support_check_failed"

    def test_missing_required_field_triggers_one_targeted_search(self, tmp_path):
        _, entry = entry_for(tmp_path)
        judge = Judge(JudgeSettings(required_fields=("customer_validation",)), can_search=True)
        review = judge.review_research(entry, round=1, can_redo=True)
        assert review.feedback.queries == ['"Acme Ocean" customers OR clients OR contract']
        assert review.feedback.search_sections == ["D"] and review.feedback.sections == []  # only if the search finds pages

        entry["review"] = Judge.annotate(entry, review)
        again = judge.review_research(entry, round=2, can_redo=True)
        assert again.verdict == "accept_with_issues"  # same search is not repeated

    def test_missing_field_without_search_is_a_note(self, tmp_path):
        _, entry = entry_for(tmp_path)
        review = Judge(JudgeSettings(required_fields=("customer_validation",))).review_research(entry, round=1, can_redo=True)
        assert review.verdict == "accept_with_issues"


class TestEvaluationReview:
    def test_scores_that_do_not_match_the_facts_are_redone(self, tmp_path):
        _, entry = entry_for(tmp_path)
        tampered = copy.deepcopy(entry)
        tampered["scores"]["investment_score"] = 5.0
        (review,) = Judge().review_evaluation([tampered], [tampered], round=1, can_redo=True, research_allowed=False)
        assert review.redo_evaluation and review.verdict == "redo"
        (capped,) = Judge().review_evaluation([tampered], [tampered], round=2, can_redo=False, research_allowed=False)
        assert not capped.redo_evaluation and capped.verdict == "accept_with_issues"

    def test_weak_assessment_goes_back_to_research_when_allowed(self, tmp_path):
        _, entry = entry_for(tmp_path)
        judge = Judge(JudgeSettings(min_confidence=0.99), can_search=True)
        (review,) = judge.review_evaluation([entry], [entry], round=1, can_redo=True, research_allowed=True)
        assert review.feedback and review.feedback.queries
        (note,) = judge.review_evaluation([entry], [entry], round=1, can_redo=True, research_allowed=False)
        assert note.feedback is None and note.issues[-1].code == "low_confidence"

    def test_unordered_ranking_is_redone(self, tmp_path):
        _, good = entry_for(tmp_path)
        sparse = StartupRecord.from_dict(good)
        sparse.id, sparse.facts = "sparse", {k: v for k, v in sparse.facts.items() if k == "solution_summary"}
        worse = sparse.to_dict()
        reviews = Judge().review_evaluation([worse, good], [worse, good], round=1, can_redo=True, research_allowed=False)
        assert all(r.redo_evaluation for r in reviews)


def test_improve_follows_the_instructions(tmp_path):
    llm = FakeLLM({**RESPONSES, "F": [RESPONSES["F"], {"team_size": scalar(2, "Jussi Laine, CTO, marine engineer.", "https://acme.fi/team")}]})
    agent, _ = build_test_agent(tmp_path, llm=llm)
    record = agent.profile(name="Acme Ocean", website="https://acme.fi")
    record.review = {"queries_tried": ["q"]}
    maria = next(f.value for f in record.facts["founders"] if f.value["name"] == "Maria Virtanen")
    feedback = ResearchFeedback(sections=["F"], notes={"F": ["Find the team size."]}, drop=[{"field": "founders", "value": maria}])

    improved = agent.improve(record, feedback)
    assert [f.value["name"] for f in improved.facts["founders"]] == ["Jussi Laine"]  # dropped, not re-added
    assert improved.facts["team_size"].value == 2
    assert improved.facts["dev_stage"] == record.facts["dev_stage"]  # untouched sections keep their facts
    assert improved.facts["business_id"].source_type == "registry"
    assert improved.review == {"queries_tried": ["q"]}
    assert llm.count("F") == 2 and llm.count("C") == 1  # only the requested section was re-extracted
    assert "Reviewer feedback" in llm.calls[-1]["user"] and "Find the team size." in llm.calls[-1]["user"]


class TestLoops:
    def run(self, agent, judge, **state):
        return build_agent_graph(agent, judge=judge).invoke({"mode": "both", "name": "Acme Ocean", "website": "https://acme.fi", **state})

    def test_bad_research_is_redone_until_accepted(self, tmp_path):
        bad_c = {f: scalar("x", "not on the page") for f in ("tech_description", "research_origin")}
        bad_c["dev_stage"] = scalar("prototype_lab", "not on the page either")
        llm = FakeLLM({**RESPONSES, "C": [bad_c, RESPONSES["C"]]})
        agent, _ = build_test_agent(tmp_path, llm=llm)
        result = self.run(agent, Judge(NO_REQUIRED))

        assert result["research_round"] == 2
        assert llm.count("C") == 2
        verdicts = [(r["stage"], r["round"], r["verdict"]) for r in result["reviews"]]
        assert verdicts[0] == ("research", 1, "redo")
        assert verdicts[1][:2] == ("research", 2) and verdicts[1][2] != "redo"  # notes may remain (no news sources)
        (entry,) = result["evaluated"]
        assert entry["sections"]["C"]["facts"]["dev_stage"]["value"] == "prototype_relevant_env"
        assert entry["review"]["status"] in ("accepted", "accepted_with_issues")
        assert len(entry["review"]["history"]) == 3  # research ×2, evaluation ×1

    def test_hallucinated_fact_is_caught_and_dropped(self, tmp_path):
        responses = {**RESPONSES, "H": {"differentiation": scalar("Only real-time sediment sensor in Europe", "Acme Ocean builds sediment sensors for ports.")}}
        llm = FakeLLM({**responses, "H": [responses["H"], {}], "judge": [judge_pointing_at("Only real-time"), {"verdicts": []}]})
        agent, _ = build_test_agent(tmp_path, llm=llm)
        result = self.run(agent, Judge(NO_REQUIRED, llm=llm))
        (entry,) = result["evaluated"]
        assert entry["sections"]["H"]["facts"]["differentiation"] is None
        assert result["reviews"][0]["verdict"] == "redo"
        assert "differentiation" in result["reviews"][0]["issues"][0]

    def test_weak_evaluation_sends_research_back_with_searches(self, tmp_path):
        search = FakeSearch(SEARCH_HITS)
        agent, _ = build_test_agent(tmp_path, searcher=search)
        result = self.run(agent, Judge(JudgeSettings(required_fields=(), min_confidence=0.99), can_search=True))
        stages = [(r["stage"], r["verdict"]) for r in result["reviews"]]
        assert ("evaluation", "redo") in stages
        assert result["research_round"] >= 2
        assert any("customers OR clients" in q for q in search.queries)

    def test_rounds_are_capped(self, tmp_path):
        class AlwaysFailingD(FakeLLM):
            def complete_json(self, *, system, user, schema):
                if "Extract section D:" in user:
                    self.calls.append({"section": "D", "sections": ["D"], "user": user, "schema": schema})
                    raise AgentError("model unavailable")
                return super().complete_json(system=system, user=user, schema=schema)

        llm = AlwaysFailingD(RESPONSES)
        agent, _ = build_test_agent(tmp_path, llm=llm)
        result = self.run(agent, Judge(JudgeSettings(required_fields=(), max_research_rounds=2)))
        assert result["research_round"] == 3  # first pass + 2 redos
        assert llm.count("D") == 3
        (entry,) = result["evaluated"]
        assert entry["review"]["status"] == "accepted_with_issues"
        assert any("section D" in issue for issue in entry["review"]["open_issues"])
