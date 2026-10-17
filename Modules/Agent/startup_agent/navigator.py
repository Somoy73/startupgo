"""Ocean Impact Navigator KPI evidence (DB/seed.sql ocean_kpis, levels 0-4) from the agent's impact facts.

The extraction schema's section E holds the impact claim, pathway, metrics and measurements as
free text. Each is matched to the Navigator's 30 KPIs by keyword, and its evidence level follows from
what kind of fact it is:

    impact_claim / impact_pathway / impact_metrics_defined   1 claimed (2 if an independent source says it)
    impact_measured                                          3 measured (4 if impact_verified_by names a verifier)

A KPI keeps its strongest fact; the fact's verbatim quote becomes the claim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .derive import Facts, items
from .facts import Fact

KPI_KEYWORDS: dict[str, tuple[str, ...]] = {
    "A1": ("biomass", "fish stock", "overfish", "bycatch", "by-catch"),
    "A2": ("seafood waste", "fish waste", "food waste", "side stream", "side-stream", "by-product", "byproduct"),
    "A3": ("fish welfare", "animal welfare", "sea lice", "mortality"),
    "A4": ("seaweed", "macroalgae", "mussel", "oyster", "bivalve", "scallop"),
    "B1": ("microplastic", "micro-plastic"),
    "B2": ("plastic", "marine litter", "ghost net", "ghost gear", "debris"),
    "B3": ("nitrogen", "phosphor", "nutrient", "eutrophication", "runoff"),
    "B4": ("wastewater", "waste water", "sewage", "effluent"),
    "B5": ("invasive",),
    "B6": ("heavy metal", "chemical", "underwater noise", "underwater sound", "oil spill", "antifouling", "anti-fouling", "biocide", "toxic"),
    "C1": ("coral",),
    "C2": ("mangrove",),
    "C3": ("seagrass", "sea grass", "eelgrass"),
    "C4": ("salt marsh", "saltmarsh"),
    "C5": ("kelp forest", "kelp restoration", "kelp reforest"),
    "C6": ("habitat", "reef", "seabed", "biodiversity", "ecosystem restor"),
    "D1": ("co2", "co₂", "ghg", "greenhouse", "carbon emission", "emissions", "decarboni", "fuel consumption", "fuel saving", "carbon footprint"),
    "D2": ("lifecycle emission", "life-cycle emission", "scope 1", "scope 2", "scope 3"),
    "D3": ("sequest", "carbon removal", "carbon capture", "blue carbon", "carbon sink"),
    "D4": ("nox", "nitrogen oxide"),
    "D5": ("sox", "sulphur", "sulfur"),
    "E1": ("coastline", "coastal erosion", "coastal protection", "shoreline", "flood protection"),
    "E2": ("climate adaptation", "early warning", "forecast", "ocean data", "ocean observation"),
    "E3": ("coastal communit", "climate resilien"),
    "E4": ("food security", "food supply"),
    "F1": ("jobs", "job creation", "employment", "livelihood"),
    "F2": ("training", "education"),
    "F3": ("women", "gender"),
    "F4": ("wage", "living income"),
    "F5": ("particulate", "pm2.5", "black carbon", "soot"),
}
# Plastic in general is macro-plastic; drop B2 when only micro-plastic is meant.
_MICRO_ONLY = re.compile(r"\bmicro-?plastics?\b")
_PATTERNS = {code: re.compile("|".join(rf"\b{re.escape(k)}" for k in words)) for code, words in KPI_KEYWORDS.items()}
IMPACT_FIELDS = ("impact_claim", "impact_pathway", "impact_metrics_defined", "impact_measured")
MAX_CLAIM = 300


@dataclass(frozen=True, slots=True)
class KpiEvidence:
    code: str
    level: int  # 1 claimed, 2 independently stated, 3 measured, 4 third-party verified
    claim: str
    source_url: str | None
    confidence: float


def ocean_kpis(facts: Facts) -> list[KpiEvidence]:
    """Evidence per Navigator KPI the impact facts mention, sorted by KPI code."""
    verified_by = items(facts, "impact_verified_by")
    best: dict[str, KpiEvidence] = {}
    for name in IMPACT_FIELDS:
        for fact in items(facts, name):
            evidence = KpiEvidence("", _level(name, fact, verified_by), _claim(fact), fact.source_url or None, fact.confidence)
            for code in kpi_codes(f"{_text(fact.value)} {fact.evidence}"):
                current = best.get(code)
                if current is None or (evidence.level, evidence.confidence) > (current.level, current.confidence):
                    best[code] = KpiEvidence(code, evidence.level, evidence.claim, evidence.source_url, evidence.confidence)
    return [best[code] for code in sorted(best)]


def kpi_codes(text: str) -> list[str]:
    text = text.casefold()
    codes = [code for code, pattern in _PATTERNS.items() if pattern.search(text)]
    if "B1" in codes and "B2" in codes and not _MICRO_ONLY.sub("", text).count("plastic"):
        codes.remove("B2")
    return codes


def _level(name: str, fact: Fact, verified_by: list[Fact]) -> int:
    if name == "impact_measured":
        return 4 if verified_by else 3
    return 2 if fact.status == "verified" else 1


def _claim(fact: Fact) -> str:
    text = (fact.evidence or _text(fact.value)).strip()
    return text if len(text) <= MAX_CLAIM else text[: MAX_CLAIM - 1].rstrip() + "…"


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_text(v) for v in value.values() if v is not None)
    if isinstance(value, list):
        return " ".join(_text(v) for v in value)
    return "" if value is None else str(value)
