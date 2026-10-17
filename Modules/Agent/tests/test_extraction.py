from startup_agent.documents import SourceDocument
from startup_agent.extraction import PromptTemplates, SectionExtractor, response_schema
from startup_agent.spec import SECTIONS, section_fields

from .helpers import FakeLLM, item, scalar

PROMPTS = PromptTemplates(
    system="system",
    section="{startup_name} {website} Extract section {section_id}: {section_title}. {section_note}\n{field_guide}\n{documents}",
)
SITE = SourceDocument("https://acme.fi/", "Acme", "Acme builds sensor buoys. In 2025 we completed a paid pilot with Port of Turku. Ports pay a monthly subscription.", "website", "2026-10-17", True)
NEWS = SourceDocument("https://yle.fi/acme", "News", "Port of Turku says the Acme buoy pilot cut sediment monitoring costs by half.", "news", "2026-10-16")


def extract(section: str, response: dict, docs=(SITE, NEWS)):
    llm = FakeLLM({section: response})
    return SectionExtractor(llm, PROMPTS).extract(SECTIONS[section], startup_name="Acme", website="https://acme.fi", documents=list(docs)), llm


def test_verified_quotes_become_facts_with_envelope():
    result, _ = extract("D", {
        "customer_validation": scalar("paid_pilot", "In 2025 we completed a paid pilot with Port of Turku."),
        "business_model": scalar("saas", "Ports pay a monthly subscription."),
    })
    cv = result.facts["customer_validation"]
    assert (cv.value, cv.source_url, cv.source_type, cv.status, cv.retrieved_at) == ("paid_pilot", "https://acme.fi/", "website", "claimed", "2026-10-17")
    assert result.facts["pricing"] is None  # not returned → unknown
    assert result.rejected == []


def test_independent_source_is_verified_and_wrong_url_is_corrected():
    result, _ = extract("C", {"pilots": [item({"partner": "Port of Turku", "environment": "harbour", "year": None, "outcome": "Costs halved"},
                                                "Acme buoy pilot cut sediment monitoring costs by half", url="https://acme.fi/")]})
    (pilot,) = result.facts["pilots"]
    assert pilot.source_url == "https://yle.fi/acme"
    assert pilot.status == "verified" and pilot.source_type == "news"


def test_unfound_quotes_invalid_enums_and_missing_evidence_are_rejected():
    result, _ = extract("D", {
        "customer_validation": scalar("paying_customers", "We have 40 paying customers."),
        "business_model": scalar("subscription", "Ports pay a monthly subscription."),
        "revenue_trend": scalar("growing", None),
    })
    assert result.facts["customer_validation"] is None
    assert result.facts["business_model"] is None
    assert result.facts["revenue_trend"] is None
    reasons = {r.field: r.reason for r in result.rejected}
    assert reasons["customer_validation"] == "evidence quote not found in any source document"
    assert reasons["business_model"].startswith("invalid value")
    assert reasons["revenue_trend"] == "no evidence quote"


def test_classified_fields_are_inferred():
    result, _ = extract("B", {"blue_sector": scalar("blue_tech_and_ocean_observation", "Acme builds sensor buoys.")})
    assert result.facts["blue_sector"].status == "inferred"
    assert result.facts["blue_sector"].confidence < 0.7


def test_prompt_contains_only_llm_fields_and_documents():
    _, llm = extract("A", {})
    user = llm.calls[0]["user"]
    assert "business_id" in user and "legal_form" not in user and "website_domain" not in user
    assert "source_url: https://acme.fi/" in user


def test_response_schema_is_strict():
    schema = response_schema(section_fields("C", origin="llm"))
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    dev = schema["properties"]["dev_stage"]["properties"]["value"]
    assert {"type": "null"} in dev["anyOf"]
    pilots = schema["properties"]["pilots"]["items"]
    assert pilots["required"] == ["item", "evidence", "source_url"]


def test_gemini_retry_policy():
    from types import SimpleNamespace

    from startup_agent.llm import _retry_delay

    def error(code, details=None):
        return SimpleNamespace(code=code, details={"error": {"details": details or []}})

    assert _retry_delay(error(503), 0) == 5  # transient server error: back off
    assert _retry_delay(error(429, [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "17s"}]), 0) == 17
    assert _retry_delay(error(429), 0) is None  # exhausted quota: fail fast
    assert _retry_delay(error(400), 0) is None
    assert _retry_delay(error(503), 3) is None  # out of attempts
