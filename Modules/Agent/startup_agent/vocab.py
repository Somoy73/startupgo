"""Shared vocabularies.

Anything that feeds a score or a match is an enum, and the same values are used
on the startup side and the opportunity side (investors, grants, partners), so
matching is a join rather than a guess.
"""

from __future__ import annotations

from typing import Literal

# --- Fact envelope ------------------------------------------------------------

SOURCE_TYPES = ("registry", "grant_db", "eu_projects", "website", "pitch_deck", "news", "patent", "manual")
SourceType = Literal["registry", "grant_db", "eu_projects", "website", "pitch_deck", "news", "patent", "manual"]

FACT_STATUSES = ("claimed", "verified", "inferred")
FactStatus = Literal["claimed", "verified", "inferred"]

# --- A. Identity and registry ---------------------------------------------------

LEGAL_FORMS = (
    "limited_company",
    "public_limited_company",
    "cooperative",
    "partnership",
    "sole_trader",
    "association_or_foundation",
    "other",
)
COMPANY_STATUSES = ("active", "liquidation", "bankrupt", "dissolved")
EMPLOYEE_RANGES = ("1-9", "10-49", "50-249", "250+")

# --- B. Blue-economy profile ----------------------------------------------------

# The 10 EU BlueInvest sectors (BlueInvest Investor Reports 2023/2024), plus "other".
BLUE_SECTORS = (
    "aquaculture",
    "blue_biotechnology",
    "blue_renewable_energy",
    "blue_tech_and_ocean_observation",
    "coastal_and_maritime_tourism",
    "environmental_protection_and_regeneration",
    "fisheries",
    "shipbuilding_and_refit",
    "shipping_and_ports",
    "water_management",
    "other",
)
CUSTOMER_TYPES = ("B2B", "B2G", "B2C")
# Shared with partner/client `segments`. Proposed list; extend as the opportunity side grows.
CUSTOMER_SEGMENTS = (
    "ports",
    "shipowners_and_operators",
    "shipyards",
    "fish_farms",
    "fisheries",
    "offshore_energy",
    "coastal_municipalities",
    "public_authorities",
    "research_institutes",
    "water_utilities",
    "marine_tourism",
    "food_and_feed_industry",
    "consumer_goods",
    "chemicals_and_materials",
    "logistics",
    "insurance_and_finance",
    "other",
)

# --- C. Technology ----------------------------------------------------------------

DEV_STAGES = (
    "concept",
    "lab_proof",
    "prototype_lab",
    "prototype_relevant_env",
    "demo_operational_env",
    "qualified_system",
    "commercial_operation",
)

# --- D. Business ------------------------------------------------------------------

BUSINESS_MODELS = ("product_sale", "saas", "service", "licensing", "hardware_plus_service", "other")
CUSTOMER_VALIDATION = (
    "none",
    "interviews",
    "letters_of_intent",
    "unpaid_pilot",
    "paid_pilot",
    "paying_customers",
    "recurring_revenue",
)
REVENUE_TRENDS = ("none", "first_revenue", "growing", "flat", "declining")

# --- G. Funding and deal ------------------------------------------------------------

STAGES = ("pre_seed", "seed", "series_a", "series_b_plus", "grant_only")
ROUND_STAGES = ("pre_seed", "seed", "series_a", "series_b_plus", "other")

# --- I. Marketing and distribution ------------------------------------------------

SALES_CHANNELS = ("direct", "distributors", "partners", "online", "public_procurement")

# --- J. Signals -------------------------------------------------------------------

NEWS_TYPES = ("funding", "pilot", "hire", "award", "partnership", "other")
