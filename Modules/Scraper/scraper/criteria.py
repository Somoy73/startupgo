"""Deterministic startup selection criteria and hard filters."""

from __future__ import annotations

from dataclasses import dataclass

from .models import StartupProfile


@dataclass(slots=True)
class StartupCriteria:
    sectors: list[str] | None = None
    countries: list[str] | None = None
    minimum_trl: int | None = None
    minimum_brl: int | None = None
    minimum_funding_usd: float | None = None
    funding_stages: list[str] | None = None
    required_keywords: list[str] | None = None
    minimum_potential_score: float | None = None

    def __post_init__(self) -> None:
        self.sectors = [item.casefold() for item in (self.sectors or [])]
        self.countries = [item.casefold() for item in (self.countries or [])]
        self.funding_stages = [item.casefold() for item in (self.funding_stages or [])]
        self.required_keywords = [item.casefold() for item in (self.required_keywords or [])]


def disclosed_funding_usd(profile: StartupProfile) -> float:
    rates = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "NOK": 0.093, "DKK": 0.145}
    return sum(
        (round_item.amount or 0) * rates.get((round_item.currency or "").upper(), 0)
        for round_item in profile.funding
    )


def matches_criteria(profile: StartupProfile, criteria: StartupCriteria) -> bool:
    readiness = profile.readiness
    lead = profile.lead

    if criteria.sectors and profile.sector.casefold() not in criteria.sectors:
        return False
    if criteria.countries and lead.country.casefold() not in criteria.countries:
        return False
    if criteria.minimum_trl is not None and (
        readiness.trl is None or readiness.trl < criteria.minimum_trl
    ):
        return False
    if criteria.minimum_brl is not None and (
        readiness.brl is None or readiness.brl < criteria.minimum_brl
    ):
        return False
    if criteria.minimum_funding_usd is not None and disclosed_funding_usd(profile) < criteria.minimum_funding_usd:
        return False
    if criteria.funding_stages and not any(
        (item.round_type or "").casefold() in criteria.funding_stages for item in profile.funding
    ):
        return False
    if criteria.required_keywords:
        searchable = " ".join(
            (profile.lead.name, profile.description, profile.sector, profile.lead.tagline)
        ).casefold()
        if not all(keyword in searchable for keyword in criteria.required_keywords):
            return False
    return True
