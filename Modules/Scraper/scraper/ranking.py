"""Ranking helpers that keep hard decisions deterministic and explainable."""

from __future__ import annotations

from dataclasses import dataclass

from .criteria import disclosed_funding_usd, matches_criteria, StartupCriteria
from .models import StartupProfile


@dataclass(slots=True)
class RankedStartup:
    profile: StartupProfile
    score: float
    reasons: list[str]
    missing_data: list[str]


class StartupRanker:
    """Rank enriched profiles without allowing an LLM to invent a score."""

    def rank(
        self,
        profiles: list[StartupProfile],
        *,
        criteria: StartupCriteria,
        scores: dict[str, float] | None = None,
    ) -> list[RankedStartup]:
        ranked = []
        for profile in profiles:
            if not matches_criteria(profile, criteria):
                continue
            score = (scores or {}).get(profile.lead.key(), self._fallback_score(profile))
            ranked.append(
                RankedStartup(
                    profile=profile,
                    score=score,
                    reasons=self._reasons(profile),
                    missing_data=self._missing_data(profile),
                )
            )
        return sorted(ranked, key=lambda item: item.score, reverse=True)

    @staticmethod
    def _fallback_score(profile: StartupProfile) -> float:
        readiness = profile.readiness
        readiness_values = [value for value in (readiness.trl, readiness.brl) if value is not None]
        readiness_score = sum(readiness_values) / len(readiness_values) / 9 * 100 if readiness_values else 0
        funding_score = min(disclosed_funding_usd(profile) / 1_000_000 * 10, 100)
        return round(readiness_score * 0.7 + funding_score * 0.3, 1)

    @staticmethod
    def _reasons(profile: StartupProfile) -> list[str]:
        reasons = []
        if profile.readiness.trl is not None:
            reasons.append(f"TRL {profile.readiness.trl} is available")
        if profile.readiness.brl is not None:
            reasons.append(f"BRL {profile.readiness.brl} is available")
        funding = disclosed_funding_usd(profile)
        if funding:
            reasons.append(f"approximately USD {funding:,.0f} in disclosed funding")
        return reasons

    @staticmethod
    def _missing_data(profile: StartupProfile) -> list[str]:
        missing = []
        if not profile.description:
            missing.append("description")
        if not profile.website_url:
            missing.append("website")
        if profile.readiness.trl is None:
            missing.append("TRL")
        if profile.readiness.brl is None:
            missing.append("BRL")
        if not profile.funding:
            missing.append("funding")
        return missing
