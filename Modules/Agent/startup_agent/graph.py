"""LangGraph orchestration for the research and evaluation agents."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal, TypedDict

from .agent import StartupAgent
from .errors import AgentError
from .record import StartupRecord


class AgentState(TypedDict, total=False):
    """State shared by the research and evaluation nodes."""

    mode: Literal["research", "evaluation", "both"]
    name: str
    website: str
    business_id: str | None
    source: str
    url: str | None
    query: str | None
    location: str
    limit: int
    extra_urls: list[str]
    leads: list[dict[str, Any]]
    records: list[dict[str, Any]]
    evaluated: list[dict[str, Any]]
    errors: list[str]


def build_agent_graph(agent: StartupAgent, *, weights: dict[str, float] | None = None):
    """Build a compiled graph with research and evaluation modes."""

    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise AgentError("LangGraph support requires the langgraph package") from exc

    def route(state: AgentState) -> str:
        return "evaluation" if state.get("mode", "both") == "evaluation" else "research"

    def after_research(state: AgentState) -> str:
        return "evaluation" if state.get("mode", "both") == "both" else "end"

    def research_node(state: AgentState) -> AgentState:
        try:
            if state.get("name") and state.get("website"):
                record = agent.profile(
                    name=state["name"],
                    website=state["website"],
                    business_id=state.get("business_id"),
                    extra_urls=state.get("extra_urls", []),
                )
                return {"records": [record.to_dict(weights=weights)]}

            leads = agent.discover(
                source=state.get("source", "wellfound"),
                url=state.get("url"),
                query=state.get("query"),
                location=state.get("location", ""),
                limit=state.get("limit", 10),
            )
            records: list[dict[str, Any]] = []
            failures: list[str] = []
            for lead in leads:
                if lead.website:
                    try:
                        records.append(agent.profile_lead(lead).to_dict(weights=weights))
                    except AgentError as exc:
                        failures.append(f"{lead.name}: {exc}")
                else:
                    records.append(
                        {
                            "name": lead.name,
                            "website": "",
                            "lead": asdict(lead),
                        }
                    )
            return {
                "leads": [asdict(lead) for lead in leads],
                "records": records,
                "errors": failures,
            }
        except AgentError as exc:
            return {"errors": [str(exc)]}

    def evaluation_node(state: AgentState) -> AgentState:
        evaluated: list[dict[str, Any]] = []
        for record in state.get("records", []):
            try:
                if "sections" in record:
                    evaluated.append(StartupRecord.from_dict(record).to_dict(weights=weights))
                else:
                    evaluated.append(
                        {
                            **record,
                            "evaluation": {
                                "status": "needs_research",
                                "reason": "No website was available for evidence-backed profiling",
                            },
                        }
                    )
            except (KeyError, TypeError, ValueError) as exc:
                evaluated.append(
                    {
                        **record,
                        "evaluation": {
                            "status": "invalid_record",
                            "reason": str(exc),
                        },
                    }
                )
        evaluated.sort(
            key=lambda item: (
                item.get("scores", {}).get("investment_score") is not None,
                item.get("scores", {}).get("investment_score") or -1,
            ),
            reverse=True,
        )
        return {"evaluated": evaluated}

    graph = StateGraph(AgentState)
    graph.add_node("research", research_node)
    graph.add_node("evaluation", evaluation_node)
    graph.add_conditional_edges(START, route, {"research": "research", "evaluation": "evaluation"})
    graph.add_conditional_edges("research", after_research, {"evaluation": "evaluation", "end": END})
    graph.add_edge("evaluation", END)
    return graph.compile()
