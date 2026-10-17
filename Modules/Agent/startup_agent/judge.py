"""Judge agent: reviews the research and evaluation agents' work and sends it back to be redone.

Research review (per entry):
  - sections whose extraction failed                  → redo those sections
  - many values rejected (quote not found / invalid)  → redo the section with the rejections as notes
  - values their quotes don't support (LLM check)     → drop them, redo the section with notes
  - required fields missing                           → targeted web searches + redo their sections

Evaluation review (per entry):
  - scores that don't reproduce from the facts, levels without evidence, unordered ranking
                                                      → redo the evaluation
  - assessment too weakly evidenced (low confidence, unknown TRL/BRL)
                                                      → back to research with targeted searches

A redo always carries concrete instructions, rounds are capped by the caller, and searches already
tried are not repeated, so the loop ends. What a redo can't fix is kept as a note on the entry.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .errors import AgentError
from .llm import LLMClient
from .record import StartupRecord, rank_key
from .scoring import CRITERIA_FIELDS
from .spec import FIELDS_BY_NAME

Stage = Literal["research", "evaluation"]
Verdict = Literal["accept", "accept_with_issues", "redo"]

# Web searches that tend to surface a missing field (run by the research agent's search provider).
GAP_QUERIES: dict[str, str] = {
    **dict.fromkeys(("dev_stage", "pilots"), '"{name}" pilot OR prototype OR demonstration'),
    **dict.fromkeys(("customer_validation", "paying_customers"), '"{name}" customers OR clients OR contract'),
    "value_proposition": '"{name}" product solution',
    **dict.fromkeys(("business_model", "pricing"), '"{name}" pricing OR subscription OR "business model"'),
    **dict.fromkeys(("revenue_trend", "revenue_last_fy"), '"{name}" revenue OR turnover OR growth'),
    **dict.fromkeys(("equity_rounds", "stage", "total_raised", "current_raise"), '"{name}" raises funding round investors'),
    **dict.fromkeys(("founders", "team_size"), '"{name}" founder CEO team'),
    **dict.fromkeys(("impact_claim", "impact_pathway"), '"{name}" environmental impact ocean'),
    "impact_measured": '"{name}" impact results measured',
    **dict.fromkeys(("market_size_claim", "competitors"), '"{name}" market competitors'),
    **dict.fromkeys(("sales_channels", "distribution_partners"), '"{name}" distributor OR reseller OR partner'),
    "patents": '"{name}" patent',
}
_UNCHECKED_SOURCES = {"registry", "manual"}  # structured or derived facts: nothing for the LLM to judge
MAX_FACTS_CHECKED = 80


@dataclass(frozen=True, slots=True)
class JudgeSettings:
    max_research_rounds: int = 2  # redo passes the judge may request from the research agent
    max_evaluation_rounds: int = 1  # redo passes the judge may request from the evaluation agent
    check_support: bool = True  # LLM checks that each quote supports its value
    max_rejected_per_section: int = 2  # more rejected values than this → redo the section
    min_confidence: float = 0.35  # below this the assessment needs more research
    required_fields: tuple[str, ...] = ("dev_stage", "customer_validation", "business_model", "impact_claim")


@dataclass(slots=True)
class Issue:
    code: str
    message: str
    action: Literal["redo", "note"]
    section: str | None = None


@dataclass(slots=True)
class ResearchFeedback:
    """Instructions for a research redo."""

    sections: list[str] = field(default_factory=list)  # sections to re-extract
    notes: dict[str, list[str]] = field(default_factory=dict)  # section → reviewer notes for the extractor
    queries: list[str] = field(default_factory=list)  # extra web searches
    # Sections to re-extract only if the extra searches find new pages (otherwise nothing would change).
    search_sections: list[str] = field(default_factory=list)
    drop: list[dict[str, Any]] = field(default_factory=list)  # facts to remove: {"field", "value"}

    def redo_section(self, section: str, note: str) -> None:
        if section not in self.sections:
            self.sections.append(section)
        self.notes.setdefault(section, []).append(note)

    def search(self, query: str, field_name: str) -> None:
        self.queries.append(query)
        spec = FIELDS_BY_NAME[field_name]
        if spec.section not in self.search_sections:
            self.search_sections.append(spec.section)
        self.notes.setdefault(spec.section, []).append(f"Look again for {field_name}: {spec.description}")

    def __bool__(self) -> bool:
        return bool(self.sections or self.queries or self.drop)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResearchFeedback:
        return cls(**{k: data.get(k, default) for k, default in asdict(cls()).items()})


@dataclass(slots=True)
class Review:
    stage: Stage
    entry_id: str
    round: int
    verdict: Verdict
    issues: list[Issue]
    feedback: ResearchFeedback | None = None  # research redo instructions
    redo_evaluation: bool = False

    def summary(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "entry": self.entry_id,
            "round": self.round,
            "verdict": self.verdict,
            "issues": [f"[{i.action}] {i.message}" for i in self.issues],
        }


class Judge:
    def __init__(
        self,
        settings: JudgeSettings | None = None,
        *,
        llm: LLMClient | None = None,
        system_prompt: str = "",
        can_search: bool | Callable[[], bool] = False,
        weights: dict[str, float] | None = None,
    ):
        self.settings = settings or JudgeSettings()
        self.llm = llm
        self.system_prompt = system_prompt
        self._can_search = can_search
        self.weights = weights

    @property
    def can_search(self) -> bool:
        """Whether asking for more searches can help (re-checked: a search quota can run out mid-run)."""
        return self._can_search() if callable(self._can_search) else self._can_search

    # --- research ------------------------------------------------------------------

    def review_research(self, entry: dict[str, Any], *, round: int, can_redo: bool) -> Review:
        issues: list[Issue] = []
        feedback = ResearchFeedback()

        for error in entry.get("errors", []):
            if error["stage"].startswith("section "):
                section = error["stage"].split()[1]
                issues.append(Issue("section_failed", f"section {section} extraction failed: {error['message'][:160]}", "redo", section))
                feedback.redo_section(section, "The previous extraction of this section failed. Extract it again.")

        rejected: dict[str, list[dict[str, Any]]] = {}
        for rejection in entry.get("rejected_extractions", []):
            if spec := FIELDS_BY_NAME.get(rejection["field"]):
                rejected.setdefault(spec.section, []).append(rejection)
        for section, rejections in sorted(rejected.items()):
            if len(rejections) > self.settings.max_rejected_per_section:
                issues.append(Issue("rejected_values", f"{len(rejections)} values in section {section} were rejected", "redo", section))
                details = "; ".join(f"{r['field']}: {r['reason']}" for r in rejections[:8])
                feedback.redo_section(section, f"These values were rejected: {details}. Copy quotes word for word from one document.")

        for issue, drop, note in self._unsupported_facts(entry):
            issues.append(issue)
            if drop:
                feedback.drop.append(drop)
                feedback.redo_section(issue.section or "", note)

        tried = _queries_tried(entry)
        for field_name in self.settings.required_fields:
            if _has_fact(entry, field_name):
                continue
            query = GAP_QUERIES.get(field_name, '"{name}"').format(name=entry["name"])
            if self.can_search and query not in tried and query not in feedback.queries:
                issues.append(Issue("missing_field", f"{field_name} not found; searching: {query}", "redo", FIELDS_BY_NAME[field_name].section))
                feedback.search(query, field_name)
            else:
                issues.append(Issue("missing_field", f"{field_name} not found in any source", "note", FIELDS_BY_NAME[field_name].section))

        if not any(s["source_type"] not in ("website", "registry", "manual") for s in entry.get("sources", [])):
            issues.append(Issue("no_independent_source", "every fact comes from the startup's own material (claimed)", "note"))

        return _finish("research", entry["id"], round, issues, feedback=feedback if can_redo else None)

    def _unsupported_facts(self, entry: dict[str, Any]) -> Iterator[tuple[Issue, dict[str, Any] | None, str]]:
        """LLM check that each quote supports its value. Yields (issue, fact to drop, note for the extractor)."""
        if not (self.settings.check_support and self.llm):
            return
        facts = [f for f in _facts(entry) if f["source_type"] not in _UNCHECKED_SOURCES][:MAX_FACTS_CHECKED]
        if not facts:
            return
        listing = "\n".join(
            f"[{i}] field: {f['field']} ({FIELDS_BY_NAME[f['field']].description[:160]})\n"
            f"    value: {json.dumps(f['value'], ensure_ascii=False)[:300]}\n    quote: {f['evidence']}"
            for i, f in enumerate(facts)
        )
        try:
            result = self.llm.complete_json(
                system=self.system_prompt,
                user=f"Startup: {entry['name']}\n\nReview these extracted facts:\n\n{listing}",
                schema=_SUPPORT_SCHEMA,
            )
        except AgentError as exc:
            yield Issue("support_check_failed", f"quote-support check skipped: {str(exc)[:160]}", "note"), None, ""
            return
        for verdict in result.get("verdicts", []):
            index = verdict.get("id")
            if verdict.get("supported", True) or not isinstance(index, int) or not 0 <= index < len(facts):
                continue
            fact = facts[index]
            reason = str(verdict.get("reason", ""))[:200]
            shown = json.dumps(fact["value"], ensure_ascii=False)[:120]
            yield (
                Issue("unsupported_fact", f"{fact['field']} = {shown} is not supported by its quote ({reason})", "redo",
                      FIELDS_BY_NAME[fact["field"]].section),
                {"field": fact["field"], "value": fact["value"]},
                f"{fact['field']}: the value {shown} was not supported by the quote you gave ({reason}). "
                "Only report what a quote actually states.",
            )

    # --- evaluation ----------------------------------------------------------------

    def review_evaluation(
        self,
        records: list[dict[str, Any]],
        evaluated: list[dict[str, Any]],
        *,
        round: int,
        can_redo: bool,
        research_allowed: bool,
    ) -> list[Review]:
        ranking_ok = evaluated == sorted(evaluated, key=rank_key)
        reviews = []
        for entry in evaluated:
            issues: list[Issue] = []
            scores = entry["scores"]
            if StartupRecord.from_dict(entry).to_dict(weights=self.weights)["scores"] != scores:
                issues.append(Issue("score_mismatch", "scores do not reproduce from the facts", "redo"))
            for key, label in (("trl", "TRL"), ("brl", "BRL"), ("ocean_impact_readiness", "OIR")):
                if scores[key]["level"] is not None and not scores[key]["evidence"]:
                    issues.append(Issue("missing_evidence", f"{label} {scores[key]['level']} has no supporting evidence", "redo"))
            if not ranking_ok:
                issues.append(Issue("ranking", "entries are not ordered by investment score", "redo"))
            redo_evaluation = bool(issues) and can_redo
            if not can_redo:
                for issue in issues:
                    issue.action = "note"

            feedback = ResearchFeedback()
            if self._weakly_evidenced(scores):
                tried = _queries_tried(entry)
                if research_allowed and self.can_search:
                    for field_name in _gap_fields(scores):
                        query = GAP_QUERIES[field_name].format(name=entry["name"])
                        if query not in tried and query not in feedback.queries:
                            feedback.search(query, field_name)
                message = (
                    f"weakly evidenced assessment (confidence {scores['overall_confidence']}, "
                    f"TRL {scores['trl']['level']}, BRL {scores['brl']['level']})"
                )
                if feedback:
                    issues.append(Issue("low_confidence", f"{message}; more research: {'; '.join(feedback.queries)}", "redo"))
                else:
                    issues.append(Issue("low_confidence", message, "note"))

            reviews.append(_finish("evaluation", entry["id"], round, issues, feedback=feedback, redo_evaluation=redo_evaluation))

        evaluated_ids = {e["id"] for e in evaluated}
        for record in records:
            if record.get("id") not in evaluated_ids:
                issue = Issue("invalid_entry", "entry could not be evaluated", "note")
                reviews.append(_finish("evaluation", str(record.get("id", record.get("name", "?"))), round, [issue]))
        return reviews

    def _weakly_evidenced(self, scores: dict[str, Any]) -> bool:
        return (
            scores["overall_confidence"] < self.settings.min_confidence
            or scores["trl"]["level"] is None
            or scores["brl"]["level"] is None
        )

    # --- entry annotation ----------------------------------------------------------

    @staticmethod
    def annotate(entry: dict[str, Any], review: Review) -> dict[str, Any]:
        """The entry's review record: status, open issues from both stages, searches tried, history.

        Research issues stay open until a later research review replaces them, so an evaluation
        that accepts the scores doesn't hide unresolved research problems.
        """
        previous = entry.get("review") or {}
        issues = [i.message for i in review.issues]
        research_issues = issues if review.stage == "research" else previous.get("research_issues", [])
        open_issues = research_issues + (issues if review.stage == "evaluation" else [])
        queries = list(previous.get("queries_tried", []))
        if review.feedback:
            queries += [q for q in review.feedback.queries if q not in queries]
        status = "redo_requested" if review.verdict == "redo" else "accepted_with_issues" if open_issues else "accepted"
        return {
            "status": status,
            "open_issues": open_issues,
            "research_issues": research_issues,
            "queries_tried": queries,
            "history": [*previous.get("history", []), review.summary()],
        }


def _finish(
    stage: Stage,
    entry_id: str,
    round: int,
    issues: list[Issue],
    *,
    feedback: ResearchFeedback | None = None,
    redo_evaluation: bool = False,
) -> Review:
    """Redo only with an actionable instruction (and rounds left); otherwise every issue is a note."""
    redo = bool(feedback) or redo_evaluation
    if not redo:
        for issue in issues:
            issue.action = "note"
    verdict: Verdict = "redo" if redo else "accept_with_issues" if issues else "accept"
    return Review(stage, entry_id, round, verdict, issues, feedback or None, redo_evaluation)


def _gap_fields(scores: dict[str, Any]) -> list[str]:
    """Fields behind an unknown TRL/BRL and unknown criteria, most important first."""
    fields: list[str] = []
    if scores["trl"]["level"] is None:
        fields += ["dev_stage", "pilots"]
    if scores["brl"]["level"] is None:
        fields += ["customer_validation", "business_model"]
    for criterion in scores["criteria"]:
        if criterion["score"] is None:
            fields += [f for f in CRITERIA_FIELDS[criterion["name"]] if f in GAP_QUERIES]
    return list(dict.fromkeys(fields))


def _facts(entry: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for section in entry["sections"].values():
        for value in section["facts"].values():
            out += value if isinstance(value, list) else [value] if value else []
    return out


def _has_fact(entry: dict[str, Any], field_name: str) -> bool:
    return bool(entry["sections"][FIELDS_BY_NAME[field_name].section]["facts"].get(field_name))


def _queries_tried(entry: dict[str, Any]) -> set[str]:
    return set((entry.get("review") or {}).get("queries_tried", []))


_SUPPORT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "supported": {"type": "boolean"}, "reason": {"type": "string"}},
                "required": ["id", "supported", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["verdicts"],
    "additionalProperties": False,
}
