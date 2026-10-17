"""Rate limiting, quota breakers, thinking, usage accounting, grouped extraction, fewer redo calls."""

from types import SimpleNamespace

import pytest
from google.genai import errors

from startup_agent.judge import Judge, JudgeSettings, ResearchFeedback
from startup_agent.llm import GeminiSession, QuotaExhausted, RateLimiter, UsageStats

from .conftest import RESPONSES, FakeSearch, build_test_agent
from .helpers import FakeLLM

GROUPS = [["A", "B", "H", "I"], ["C", "D", "E"], ["F", "G", "J"]]


def api_error(code: int, *, retry_delay: str | None = None, message: str = "error") -> errors.APIError:
    details = [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry_delay}] if retry_delay else []
    return errors.APIError(code, {"error": {"code": code, "message": message, "status": "X", "details": details}})


class FakeModels:
    """Plays back a script of exceptions/responses for generate_content."""

    def __init__(self, script):
        self.script = list(script)
        self.configs = []

    def generate_content(self, *, model, contents, config):
        self.configs.append(config)
        outcome = self.script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def ok(text="{}", prompt=100, output=20, thinking=0):
    usage = SimpleNamespace(prompt_token_count=prompt, candidates_token_count=output, thoughts_token_count=thinking)
    return SimpleNamespace(text=text, usage_metadata=usage)


def session_with(script, **kwargs):
    models = FakeModels(script)
    sleeps = []
    session = GeminiSession(lambda: SimpleNamespace(models=models), sleep=sleeps.append, **kwargs)
    return session, models, sleeps


class TestRateLimiter:
    def test_spaces_requests_evenly(self):
        now = [0.0]
        waits = []
        limiter = RateLimiter(30, clock=lambda: now[0], sleep=waits.append)  # one request per 2 s
        assert limiter.wait() == 0
        assert limiter.wait() == 2.0  # second request immediately after: waits its slot
        now[0] = 10.0
        assert limiter.wait() == 0  # idle long enough: no wait
        assert waits == [2.0]


class TestGeminiSession:
    def test_rate_limit_with_retry_info_is_retried_and_counted(self):
        session, models, sleeps = session_with([api_error(429, retry_delay="7s"), ok(prompt=500, output=50, thinking=10)])
        session.generate(model="m", contents="x", kind="llm")
        assert sleeps == [7.0]
        s = session.stats
        assert (s.llm_requests, s.retries, s.waited_seconds) == (2, 1, 7.0)
        assert (s.prompt_tokens, s.output_tokens, s.thinking_tokens) == (500, 50, 10)

    def test_exhausted_quota_is_not_called_again_but_other_kinds_still_work(self):
        session, models, _ = session_with([api_error(429), ok()])
        with pytest.raises(QuotaExhausted):
            session.generate(model="m", contents="x", kind="search")
        with pytest.raises(QuotaExhausted, match="skipped"):
            session.generate(model="m", contents="y", kind="search")
        assert not session.available("search") and session.available("llm")
        session.generate(model="m", contents="z", kind="llm")  # generation has its own quota
        assert session.stats.search_requests == 1 and session.stats.skipped == 1
        assert len(models.configs) == 2

    def test_thinking_level_is_sent_and_dropped_if_the_model_rejects_it(self):
        session, models, _ = session_with([api_error(400, message="thinking_level is not supported"), ok()], thinking="minimal")
        session.generate(model="m", contents="x", kind="llm")
        assert models.configs[0].thinking_config.thinking_level.value == "MINIMAL"
        assert models.configs[1].thinking_config is None
        assert session.thinking == ""

    def test_invalid_thinking_setting_is_rejected(self):
        with pytest.raises(Exception, match="thinking"):
            GeminiSession(lambda: None, thinking="maximum")

    def test_summary_mentions_skips(self):
        stats = UsageStats(llm_requests=3, llm_cached=7, skipped=2, waited_seconds=12.4)
        assert "3 request(s), 7 cached" in stats.summary() and "2 call(s) skipped" in stats.summary()


def test_grouped_sections_need_three_calls_instead_of_ten(tmp_path):
    llm = FakeLLM(RESPONSES)
    agent, _ = build_test_agent(tmp_path, llm=llm)
    agent.section_groups = GROUPS
    record = agent.profile(name="Acme Ocean", website="https://acme.fi")
    assert [c["section"] for c in llm.calls] == ["A, B, H, I", "C, D, E", "F, G, J"]
    assert record.facts["dev_stage"].value == "prototype_relevant_env"
    assert record.facts["business_id"].source_type == "registry"  # registry still runs after the group with A


def test_failed_group_reports_each_section(tmp_path):
    class FailCDE(FakeLLM):
        def complete_json(self, *, system, user, schema):
            if "Extract section C, D, E:" in user:
                from startup_agent.errors import AgentError

                raise AgentError("429 quota")
            return super().complete_json(system=system, user=user, schema=schema)

    agent, _ = build_test_agent(tmp_path, llm=FailCDE(RESPONSES))
    agent.section_groups = GROUPS
    record = agent.profile(name="Acme Ocean", website="https://acme.fi")
    assert [e["stage"] for e in record.errors if e["stage"].startswith("section")] == ["section C", "section D", "section E"]


def test_search_sections_are_not_re_extracted_when_search_finds_nothing_new(tmp_path):
    llm = FakeLLM(RESPONSES)
    agent, _ = build_test_agent(tmp_path, llm=llm, searcher=FakeSearch([]))
    record = agent.profile(name="Acme Ocean", website="https://acme.fi")
    feedback = ResearchFeedback()
    feedback.search('"Acme Ocean" customers', "customer_validation")
    calls = len(llm.calls)
    agent.improve(record, feedback)
    assert len(llm.calls) == calls  # nothing new found → no extraction call


def test_judge_stops_asking_for_searches_once_search_is_unavailable(tmp_path):
    agent, _ = build_test_agent(tmp_path)
    entry = agent.profile(name="Acme Ocean", website="https://acme.fi").to_dict()
    search_up = [True]
    judge = Judge(JudgeSettings(required_fields=("customer_validation",)), can_search=lambda: search_up[0])
    assert judge.review_research(entry, round=1, can_redo=True).verdict == "redo"
    search_up[0] = False
    assert judge.review_research(entry, round=1, can_redo=True).verdict == "accept_with_issues"
