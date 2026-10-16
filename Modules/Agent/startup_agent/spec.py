"""The extraction schema as data: sections, fields, types and what each field feeds.

This table mirrors "Ocean Opportunity Radar — Extraction Schema". It drives the
per-section LLM JSON schemas, response validation, gap questions and the JSON
Schema export, so the schema lives in one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from . import vocab

Kind = Literal[
    "text",  # short verbatim-style value: a name, code, figure as written
    "sentence",  # one-sentence summary; may be paraphrased, evidence must still be verbatim
    "integer",
    "number",
    "date",  # YYYY, YYYY-MM or YYYY-MM-DD
    "boolean",
    "enum",
    "enum_list",
    "text_list",
    "object",
    "object_list",  # each item is its own fact with its own evidence
]
Origin = Literal[
    "llm",  # extracted from documents by the LLM (registry data may override)
    "registry",  # only from structured registries
    "derived",  # computed by code from other facts
    "input",  # given by the caller
]

SDG14_TARGETS = ("14.1", "14.2", "14.3", "14.4", "14.5", "14.6", "14.7", "14.a", "14.b", "14.c")


@dataclass(frozen=True, slots=True)
class Prop:
    """One property of an object-valued field."""

    kind: Kind
    description: str = ""
    enum: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FieldSpec:
    name: str
    section: str
    kind: Kind
    description: str
    feeds: tuple[str, ...] = ()
    enum: tuple[str, ...] = ()
    props: dict[str, Prop] = field(default_factory=dict)
    origin: Origin = "llm"
    # An LLM classification or mapping rather than a stated fact: status becomes "inferred".
    classified: bool = False
    # Asked on the fund's first call when the field is a gap.
    question: str = ""

    @property
    def is_list(self) -> bool:
        return self.kind == "object_list"


@dataclass(frozen=True, slots=True)
class SectionSpec:
    id: str
    title: str
    # URL path / page title fragments that route crawled pages to this section.
    keywords: tuple[str, ...]
    note: str = ""


SECTIONS: dict[str, SectionSpec] = {
    s.id: s
    for s in (
        SectionSpec("A", "Identity and registry", ("about", "company", "contact", "imprint", "impressum", "legal", "yhteystiedot")),
        SectionSpec("B", "Blue-economy profile", ("about", "solution", "product", "mission", "what-we-do", "industr", "sector", "customer", "application", "use-case")),
        SectionSpec("C", "Technology", ("technolog", "tech", "product", "solution", "how-it-works", "science", "research", "patent", "pilot", "case", "project")),
        SectionSpec("D", "Business", ("product", "pricing", "price", "solution", "customer", "case", "reference", "service", "offering", "business")),
        SectionSpec("E", "Ocean impact", ("impact", "sustainab", "environment", "esg", "mission", "ocean", "climate", "sdg", "report")),
        SectionSpec("F", "Team", ("team", "about", "people", "founder", "leadership", "board", "advisor", "career", "jobs"), note="Business facts only; no private personal data."),
        SectionSpec("G", "Funding and deal", ("investor", "funding", "news", "press", "about", "partner", "media")),
        SectionSpec("H", "Market and competition", ("market", "about", "why", "solution", "industr", "competit", "compare")),
        SectionSpec("I", "Marketing and distribution", ("partner", "distributor", "reseller", "dealer", "where-to-buy", "contact")),
        SectionSpec("J", "Signals for monitoring", ("news", "press", "media", "blog", "update", "event", "award", "article")),
    )
}


def _f(*args: Any, **kwargs: Any) -> FieldSpec:
    return FieldSpec(*args, **kwargs)


FIELDS: tuple[FieldSpec, ...] = (
    # A. Identity and registry
    _f("name", "A", "text", "Company name.", ("deduplication",), origin="input"),
    _f("aliases", "A", "text_list", "Other names the company uses or has used: former names, trading names.", ("deduplication",)),
    _f("website_domain", "A", "text", "Website domain, the deduplication key.", ("deduplication",), origin="derived"),
    _f("business_id", "A", "text", "Company registration number exactly as written, e.g. Finnish Y-tunnus 1234567-8.", ("deduplication",),
       question="What is your business ID (Y-tunnus)?"),
    _f("country", "A", "text", "Country of the headquarters, in English.", ("M:geography",)),
    _f("city", "A", "text", "City of the headquarters.", ("M:geography",)),
    _f("legal_form", "A", "enum", "Legal form from the trade register.", ("M:eligibility",), vocab.LEGAL_FORMS, origin="registry"),
    _f("founded_date", "A", "date", "Date or year the company was founded or incorporated.", ("BRL", "M:company_age"),
       question="When was the company founded?"),
    _f("status", "A", "enum", "Trade register status.", ("filter",), vocab.COMPANY_STATUSES, origin="registry"),
    _f("industry_code", "A", "text", "TOL 2008 industry code from the trade register.", ("D",), origin="registry"),
    _f("employee_range", "A", "enum", "Headcount range, only if a headcount or range is stated.", ("M:sme_status",), vocab.EMPLOYEE_RANGES,
       question="How many people work at the company?"),
    _f("revenue_last_fy", "A", "number", "Revenue in EUR for the last reported financial year, only if a figure is stated.", ("BRL", "IP:financials"),
       question="What was your revenue in the last financial year?"),
    _f("profit_last_fy", "A", "number", "Profit (loss negative) in EUR for the last reported financial year.", ("BRL", "IP:financials"),
       question="What was your profit or loss in the last financial year?"),
    _f("equity_last_fy", "A", "number", "Equity in EUR at the end of the last reported financial year.", ("BRL", "IP:financials")),
    # B. Blue-economy profile
    _f("blue_sector", "B", "enum", "BlueInvest sector that best fits the company's main activity.", ("M", "thesis_fit"), vocab.BLUE_SECTORS,
       classified=True, question="Which blue-economy sector do you mainly serve?"),
    _f("ocean_problem", "B", "sentence", "The ocean or water problem the company addresses, in one sentence.", ("OIR", "thesis_fit")),
    _f("solution_summary", "B", "sentence", "What the company offers, in one sentence.", ("display", "search")),
    _f("customer_type", "B", "enum_list", "Who pays: businesses (B2B), public bodies (B2G), consumers (B2C).", ("IP:business_model", "M:partners"),
       vocab.CUSTOMER_TYPES, question="Who are your paying customers: businesses, public bodies or consumers?"),
    _f("target_customers", "B", "enum_list", "Customer segments the company sells to or targets.", ("M:partners_and_clients",),
       vocab.CUSTOMER_SEGMENTS, classified=True, question="Which customer segments do you target first?"),
    # C. Technology
    _f("tech_description", "C", "sentence", "The core technology and how it works, in one or two sentences.", ("IP:tech",)),
    _f("dev_stage", "C", "enum",
       "Most advanced stage the sources state: concept (idea or papers), lab_proof (lab experiments show it works), "
       "prototype_lab (working prototype in the lab), prototype_relevant_env (prototype tested in a realistic or simulated environment), "
       "demo_operational_env (demonstrated in real operating conditions, e.g. at sea or at a customer site), "
       "qualified_system (complete system qualified or certified), commercial_operation (sold and used in daily operations).",
       ("TRL",), vocab.DEV_STAGES, question="What is the most demanding real environment your technology has worked in?"),
    _f("pilots", "C", "object_list", "Pilots, trials or demonstrations with a named partner or site.", ("TRL", "BRL", "M"),
       props={
           "partner": Prop("text", "Named partner or customer"),
           "environment": Prop("text", "Where it ran, e.g. harbour, open sea, fish farm, test basin, lab"),
           "year": Prop("integer"),
           "outcome": Prop("sentence", "Stated result"),
       },
       question="Which pilots have you run, with whom, and what were the results?"),
    _f("patents", "C", "object_list", "Patents or patent applications.", ("TRL", "IP:tech", "D"),
       props={"number": Prop("text"), "title": Prop("text"), "year": Prop("integer")},
       question="Do you hold patents or pending applications?"),
    _f("certifications", "C", "text_list", "Certifications or approvals, e.g. DNV class approval, CE marking.", ("TRL",)),
    _f("research_origin", "C", "sentence", "Research background, e.g. spin-out of a named university or institute.", ("M:research_partners",)),
    # D. Business
    _f("value_proposition", "D", "sentence", "The benefit customers get, in one sentence.", ("BRL", "IP:product")),
    _f("business_model", "D", "enum", "How the company makes money.", ("BRL", "IP:business_model"), vocab.BUSINESS_MODELS,
       question="How do you make money: product sales, subscriptions, services or licensing?"),
    _f("customer_validation", "D", "enum",
       "Strongest stated customer evidence: none, interviews, letters_of_intent, unpaid_pilot, paid_pilot, "
       "paying_customers (ongoing sales), recurring_revenue (renewing subscriptions or contracts).",
       ("BRL",), vocab.CUSTOMER_VALIDATION, question="What is your strongest customer commitment so far: LOIs, pilots or paying customers?"),
    _f("paying_customers", "D", "object", "Paying customers: a stated count and/or named customers.", ("BRL", "IP:market"),
       props={"count": Prop("integer", "Number of paying customers, if stated"), "names": Prop("text_list", "Named paying customers")},
       question="How many paying customers do you have, and who are they?"),
    _f("pricing", "D", "sentence", "Pricing or price level, as stated.", ("IP:business_model",), question="How is your offering priced?"),
    _f("revenue_trend", "D", "enum", "Revenue development as stated: none (pre-revenue), first_revenue, growing, flat, declining.",
       ("BRL", "IP:financials"), vocab.REVENUE_TRENDS, question="Is revenue growing, flat or declining?"),
    # E. Ocean impact
    _f("impact_claim", "E", "sentence", "The positive ocean or climate impact the company claims.", ("OIR",)),
    _f("impact_pathway", "E", "sentence", "How the solution creates the impact: problem → mechanism → outcome.", ("OIR",),
       question="How exactly does your solution produce its ocean impact?"),
    _f("impact_metrics_defined", "E", "text_list", "Impact metrics the company names, e.g. tonnes CO2 avoided, kg plastic removed.", ("OIR",),
       question="Which metrics do you use to track impact?"),
    _f("impact_measured", "E", "object_list", "Impact figures actually measured.", ("OIR",),
       props={"metric": Prop("text"), "value": Prop("text", "Figure as stated, with unit"), "period": Prop("text", "Period or pilot it covers")},
       question="Have you measured that impact? What were the figures?"),
    _f("impact_verified_by", "E", "text", "Independent third party that verified the impact figures.", ("OIR",),
       question="Has anyone independent verified your impact figures?"),
    _f("sdg14_targets", "E", "enum_list",
       "UN SDG 14 targets the impact maps to: 14.1 marine pollution; 14.2 protect and restore ecosystems; 14.3 acidification; "
       "14.4 sustainable fishing; 14.5 conserve coastal and marine areas; 14.6 fisheries subsidies; 14.7 benefits for small "
       "island and least developed states; 14.a marine research and technology; 14.b small-scale fishers; 14.c ocean law.",
       ("OIR", "M:impact_investors"), SDG14_TARGETS, classified=True),
    _f("negative_effects_addressed", "E", "object", "Whether the company addresses its own negative effects (lifecycle emissions, by-catch, noise).", ("OIR",),
       props={"addressed": Prop("boolean"), "note": Prop("sentence")}),
    # F. Team
    _f("founders", "F", "object_list", "Founders and their roles. Business facts only: no contact details or private information.", ("IP:team",),
       props={
           "name": Prop("text"),
           "role": Prop("text"),
           "domain_experience_years": Prop("integer", "Years of experience in the domain, if stated"),
           "technical": Prop("boolean", "Has a technical/engineering/science role or background"),
           "prior_startup": Prop("boolean", "Founded or worked at a startup before"),
       },
       question="Who are the founders and what are their roles?"),
    _f("team_size", "F", "integer", "Number of employees or team members as stated.", ("IP:team", "BRL"), question="How big is the team?"),
    _f("key_roles_missing", "F", "text_list", "Key roles not covered by the founding team.", ("IP:team", "next_steps"), origin="derived"),
    _f("advisors_board", "F", "object_list", "Board members and advisors.", ("IP:team",),
       props={"name": Prop("text"), "background": Prop("sentence")}),
    # G. Funding and deal
    _f("grants", "G", "object_list", "Public grants or subsidies received, e.g. Business Finland, EIC, Horizon Europe.", ("TRL", "M"),
       props={"funder": Prop("text"), "programme": Prop("text"), "amount": Prop("number"), "currency": Prop("text", "ISO 4217 code"), "year": Prop("integer")},
       question="Which grants or public funding have you received?"),
    _f("equity_rounds", "G", "object_list", "Equity investment rounds.", ("IP:deal_dynamics", "M"),
       props={
           "date": Prop("date"),
           "stage": Prop("enum", "Round stage", vocab.ROUND_STAGES),
           "amount": Prop("number"),
           "currency": Prop("text", "ISO 4217 code"),
           "investors": Prop("text_list"),
       },
       question="Which equity rounds have you raised, when, how much and from whom?"),
    _f("total_raised", "G", "number", "Total equity raised in EUR (approximate FX).", ("stage",), origin="derived"),
    _f("stage", "G", "enum", "Funding stage derived from rounds and grants.", ("M:primary_key",), vocab.STAGES, origin="derived"),
    _f("current_raise", "G", "object", "A round the company says it is currently raising.", ("IP:deal_dynamics", "M"),
       props={"amount": Prop("number"), "currency": Prop("text"), "stage": Prop("enum", "", vocab.ROUND_STAGES), "open": Prop("boolean")},
       question="Are you raising now? How much, at what stage?"),
    _f("accelerators", "G", "object_list", "Accelerator or incubator programmes.", ("D", "IP:team"),
       props={"programme": Prop("text"), "year": Prop("integer")}),
    # H. Market and competition
    _f("market_size_claim", "H", "object", "A market size figure the company cites.", ("IP:market",),
       props={
           "amount": Prop("number"),
           "currency": Prop("text"),
           "description": Prop("text", "What market the figure refers to"),
           "source_cited": Prop("text", "Source the company cites for the figure"),
       },
       question="How large is your target market, and what is the source?"),
    _f("target_geographies", "H", "text_list", "Countries or regions the company sells to or targets.", ("M",),
       question="Which countries or regions do you sell to?"),
    _f("competitors", "H", "text_list", "Named competitors or alternative solutions.", ("IP:competition",), question="Who are your main competitors?"),
    _f("differentiation", "H", "sentence", "How the company says it differs from competitors.", ("IP:competition",),
       question="What makes you different from those competitors?"),
    # I. Marketing and distribution
    _f("sales_channels", "I", "enum_list", "How the company sells.", ("IP:marketing_distribution",), vocab.SALES_CHANNELS,
       question="How do you sell: directly, via distributors, partners, online or public procurement?"),
    _f("distribution_partners", "I", "text_list", "Named distributors, resellers or channel partners.", ("M:partners",)),
    # J. Signals for monitoring
    _f("news", "J", "object_list", "Dated news, press releases or announcements about the company.", ("D", "monitoring"),
       props={"date": Prop("date"), "headline": Prop("text"), "url": Prop("text"), "type": Prop("enum", "", vocab.NEWS_TYPES)}),
    _f("last_changed", "J", "object", "Date each section last changed.", ("freshness",), origin="derived"),
)

FIELDS_BY_NAME: dict[str, FieldSpec] = {f.name: f for f in FIELDS}


def section_fields(section_id: str, *, origin: Origin | None = None) -> list[FieldSpec]:
    return [f for f in FIELDS if f.section == section_id and (origin is None or f.origin == origin)]


# --- JSON Schema helpers --------------------------------------------------------------

_SCALAR_SCHEMAS: dict[str, dict[str, Any]] = {
    "text": {"type": "string"},
    "sentence": {"type": "string"},
    "integer": {"type": "integer"},
    "number": {"type": "number"},
    "date": {"type": "string", "description": "YYYY, YYYY-MM or YYYY-MM-DD"},
    "boolean": {"type": "boolean"},
    "text_list": {"type": "array", "items": {"type": "string"}},
}


def nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


def value_schema(kind: Kind, enum: tuple[str, ...] = (), props: dict[str, Prop] | None = None) -> dict[str, Any]:
    """JSON Schema for a (non-null) field value."""
    if kind == "enum":
        return {"type": "string", "enum": list(enum)}
    if kind == "enum_list":
        return {"type": "array", "items": {"type": "string", "enum": list(enum)}}
    if kind in ("object", "object_list"):
        properties = {name: nullable(value_schema(p.kind, p.enum)) | _describe(p.description) for name, p in (props or {}).items()}
        obj = {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}
        return obj if kind == "object" else {"type": "array", "items": obj}
    return dict(_SCALAR_SCHEMAS[kind])


def _describe(description: str) -> dict[str, str]:
    return {"description": description} if description else {}
