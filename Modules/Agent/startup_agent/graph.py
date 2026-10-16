"""LangGraph workflow: research agent, evaluation agent, and a judge that reviews both.

research agent    Gathers data: discovers startups through the scraper (or takes a name + website),
                  crawls each website, searches the web, and extracts evidence-backed facts into
                  schema entries. On a redo it follows the judge's instructions for that entry.
evaluation agent  Assesses: recomputes scores from the facts (TRL, BRL, Ocean Impact Readiness,
                  10 investment criteria), ranks the startups and summarises each assessment.
judge             Reviews each agent's output. If the work isn't good enough it sends it back with
                  concrete instructions; rounds are capped, after which issues are kept as notes.

    START → research → judge_research ─┬─ redo ──────────→ research
                                       ├─ mode "both" ───→ evaluation → judge_evaluation ─┬─ redo evaluation → evaluation
                                       └─ mode "research" → END                           ├─ more research ─→ research
                                                                                          └─ accepted ──────→ END
    mode "evaluation" starts at evaluation (entries supplied in ``records``).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from .agent import StartupAgent
from .errors import AgentError
from .judge import Judge, ResearchFeedback
from .record import StartupRecord, rank_key

Mode = Literal["research", "evaluation", "both"]


class AgentState(TypedDict, total=False):
    # input
    mode: Mode
    name: str
    website: str
    business_id: str | None
    extra_urls: list[str]
    source: str  # discovery source: wellfound, generic, osm
    discover_url: str | None
    query: str | None
    location: str
    limit: int
    # research output / evaluation input: schema entries (each carries the judge's review)
    records: list[dict[str, Any]]
    skipped: Annotated[list[dict[str, str]], operator.add]
    # evaluation output, best first
    evaluated: list[dict[str, Any]]
    assessments: list[dict[str, Any]]
    # judge
    research_round: int
    evaluation_round: int
    feedback: dict[str, dict[str, Any]]  # entry id → research redo instructions
    redo_evaluation: bool
    reviews: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[str], operator.add]


def build_agent_graph(agent: StartupAgent, *, judge: Judge | None = None, weights: dict[str, float] | None = None):
    """Compile the research → judge → evaluation → judge graph."""
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise AgentError("the workflow requires the langgraph package") from exc

    judge = judge or Judge(can_search=agent.searcher is not None, weights=weights)
    limits = judge.settings

    # --- research agent -----------------------------------------------------------

    def research(state: AgentState) -> dict[str, Any]:
        round_ = state.get("research_round", 0) + 1
        if feedback := state.get("feedback"):
            return {**_redo_research(state["records"], feedback), "research_round": round_, "feedback": {}}
        try:
            if state.get("name") and state.get("website"):
                record = agent.profile(
                    name=state["name"],
                    website=state["website"],
                    business_id=state.get("business_id"),
                    extra_urls=state.get("extra_urls", []),
                )
                return {"records": [record.to_dict(weights=weights)], "research_round": round_}
            leads = agent.discover(
                source=state.get("source", "wellfound"),
                url=state.get("discover_url"),
                query=state.get("query"),
                location=state.get("location", ""),
                limit=state.get("limit", 10),
            )
        except AgentError as exc:
            return {"errors": [f"research: {exc}"], "research_round": round_}

        records, skipped = [], []
        for lead in leads:
            if not lead.website:
                skipped.append({"name": lead.name, "reason": "no website to research"})
                continue
            try:
                records.append(agent.profile_lead(lead).to_dict(weights=weights))
            except AgentError as exc:
                skipped.append({"name": lead.name, "reason": str(exc)})
        return {"records": records, "skipped": skipped, "research_round": round_}

    def _redo_research(records: list[dict[str, Any]], feedback: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Redo only the entries the judge sent back, following its instructions."""
        updated, errors = [], []
        for entry in records:
            if entry["id"] not in feedback:
                updated.append(entry)
                continue
            try:
                improved = agent.improve(StartupRecord.from_dict(entry), ResearchFeedback.from_dict(feedback[entry["id"]]))
                updated.append(improved.to_dict(weights=weights))
            except AgentError as exc:
                errors.append(f"research redo for {entry['name']}: {exc}")
                updated.append(entry)
        return {"records": updated, "errors": errors}

    # --- evaluation agent -------------------------------------------------------------

    def evaluation(state: AgentState) -> dict[str, Any]:
        evaluated, errors = [], []
        for entry in state.get("records", []):
            try:
                evaluated.append(StartupRecord.from_dict(entry).to_dict(weights=weights))
            except (KeyError, TypeError, ValueError) as exc:
                errors.append(f"evaluation: {entry.get('name', '?')} is not a valid entry ({exc!r})")
        evaluated.sort(key=rank_key)
        return {
            "evaluated": evaluated,
            "assessments": [assess(entry, rank) for rank, entry in enumerate(evaluated, 1)],
            "evaluation_round": state.get("evaluation_round", 0) + 1,
            "redo_evaluation": False,
            "errors": errors,
        }

    # --- judge ----------------------------------------------------------------------

    def judge_research(state: AgentState) -> dict[str, Any]:
        round_ = state.get("research_round", 1)
        can_redo = round_ <= limits.max_research_rounds
        records, feedback, reviews = [], {}, []
        for entry in state.get("records", []):
            review = judge.review_research(entry, round=round_, can_redo=can_redo)
            records.append({**entry, "review": judge.annotate(entry, review)})
            reviews.append(review.summary())
            if review.feedback:
                feedback[entry["id"]] = review.feedback.to_dict()
        return {"records": records, "feedback": feedback, "reviews": reviews}

    def judge_evaluation(state: AgentState) -> dict[str, Any]:
        evaluated = state.get("evaluated", [])
        reviews = judge.review_evaluation(
            state.get("records", []),
            evaluated,
            round=state.get("evaluation_round", 1),
            can_redo=state.get("evaluation_round", 1) <= limits.max_evaluation_rounds,
            research_allowed=state.get("mode", "both") == "both" and state.get("research_round", 0) <= limits.max_research_rounds,
        )
        by_id = {r.entry_id: r for r in reviews}
        annotated = [{**e, "review": judge.annotate(e, by_id[e["id"]])} if e["id"] in by_id else e for e in evaluated]
        return {
            "evaluated": annotated,
            "records": annotated,  # a research redo starts from the evaluated entries and their review history
            "assessments": [assess(entry, rank) for rank, entry in enumerate(annotated, 1)],
            "redo_evaluation": any(r.redo_evaluation for r in reviews),
            "feedback": {r.entry_id: r.feedback.to_dict() for r in reviews if r.feedback},
            "reviews": [r.summary() for r in reviews],
        }

    # --- routing --------------------------------------------------------------------

    def start(state: AgentState) -> str:
        return "evaluation" if state.get("mode", "both") == "evaluation" else "research"

    def after_judge_research(state: AgentState) -> str:
        if state.get("feedback"):
            return "research"
        return "evaluation" if state.get("mode", "both") == "both" else END

    def after_judge_evaluation(state: AgentState) -> str:
        if state.get("redo_evaluation"):
            return "evaluation"
        return "research" if state.get("feedback") else END

    graph = StateGraph(AgentState)
    graph.add_node("research", research)
    graph.add_node("judge_research", judge_research)
    graph.add_node("evaluation", evaluation)
    graph.add_node("judge_evaluation", judge_evaluation)
    graph.add_conditional_edges(START, start, ["research", "evaluation"])
    graph.add_edge("research", "judge_research")
    graph.add_conditional_edges("judge_research", after_judge_research, ["research", "evaluation", END])
    graph.add_edge("evaluation", "judge_evaluation")
    graph.add_conditional_edges("judge_evaluation", after_judge_evaluation, ["evaluation", "research", END])
    # Every pass is two steps (agent + judge); allow the worst case of the configured redo caps.
    passes = 2 * (limits.max_research_rounds + 1) + limits.max_evaluation_rounds + 1
    return graph.compile().with_config({"recursion_limit": max(25, 2 * passes + 5)})


def assess(entry: dict[str, Any], rank: int) -> dict[str, Any]:
    """Short summary of an evaluated entry."""
    scores = entry["scores"]
    known = sorted((c for c in scores["criteria"] if c["score"] is not None), key=lambda c: c["score"])
    review = entry.get("review") or {}
    return {
        "rank": rank,
        "id": entry["id"],
        "name": entry["name"],
        "website": entry["website"],
        "investment_score": scores["investment_score"],
        "investment_percent": scores["investment_percent"],
        "confidence": scores["overall_confidence"],
        "trl": scores["trl"]["level"],
        "brl": scores["brl"]["level"],
        "ocean_impact_readiness": scores["ocean_impact_readiness"]["level"],
        "strengths": [c["name"] for c in reversed(known) if c["score"] >= 4],
        "weaknesses": [c["name"] for c in known if c["score"] <= 2],
        "unknown": [c["name"] for c in scores["criteria"] if c["score"] is None],
        "next_steps": [step["type"] for step in entry["next_steps"][:3]],
        "data_gaps": len(entry["data_gaps"]),
        "review_status": review.get("status"),
        "open_issues": len(review.get("open_issues", [])),
    }
