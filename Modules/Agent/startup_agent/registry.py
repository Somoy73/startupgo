"""Finnish Trade Register (PRH / YTJ open data API v3) facts for section A.

Structured, independent and cheap: these facts are "verified" and filled before any LLM call.
Financial statements are not in the open API, so revenue/profit/equity stay with other sources.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

from .documents import host
from .facts import Fact, confidence_for

PRH_API = "https://avoindata.prh.fi/opendata-ytj-api/v3/companies"
BUSINESS_ID = re.compile(r"^\d{7}-\d$")
_ENGLISH = "3"
_FINNISH = "1"
_LEGAL_SUFFIXES = re.compile(r"\b(oyj|oy|ab|ltd|limited|inc|gmbh|as|aps|llc|plc|ky|ay)\b\.?", re.IGNORECASE)
_LEGAL_FORMS = (
    ("public limited", "public_limited_company"),
    ("limited company", "limited_company"),
    ("co-operative", "cooperative"),
    ("cooperative", "cooperative"),
    ("partnership", "partnership"),
    ("private trader", "sole_trader"),
    ("association", "association_or_foundation"),
    ("foundation", "association_or_foundation"),
)


def normalize_company_name(name: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", _LEGAL_SUFFIXES.sub(" ", name.casefold())).split())


def _description(entry: dict[str, Any], language: str = _ENGLISH) -> str:
    return next((d.get("description", "") for d in entry.get("descriptions", []) if d.get("languageCode") == language), "")


def _current(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((e for e in entries if not e.get("endDate")), entries[0] if entries else None)


class PRHRegistry:
    def __init__(self, fetch_json: Callable[[str], Any], *, today: str):
        self._fetch_json = fetch_json
        self.today = today

    def lookup(
        self,
        *,
        name: str,
        business_id: str | None = None,
        website_domain: str | None = None,
        allow_name_match: bool = True,
    ) -> dict[str, Fact]:
        """Facts for the company, or {} when no unambiguous match exists.

        A business ID or a registered website matching ``website_domain`` always identifies the
        company. A bare name match is only accepted with ``allow_name_match`` (e.g. a .fi site),
        so a same-named Finnish company is never merged into an unrelated startup.
        """
        company = self._find(name=name, business_id=business_id, website_domain=website_domain, allow_name_match=allow_name_match)
        return self.facts(company) if company else {}

    def _find(
        self, *, name: str, business_id: str | None, website_domain: str | None, allow_name_match: bool
    ) -> dict[str, Any] | None:
        if business_id and BUSINESS_ID.match(business_id):
            companies = self._query(businessId=business_id)
            return companies[0] if companies else None

        wanted = normalize_company_name(name)
        for company in self._query(name=name):
            names = [normalize_company_name(n.get("name", "")) for n in company.get("names", [])]
            website = (company.get("website") or {}).get("url") or ""
            registered_domain = host(website if "://" in website else f"https://{website}")
            if (website_domain and registered_domain == website_domain) or (allow_name_match and wanted in names):
                return company
        return None

    def _query(self, **params: str) -> list[dict[str, Any]]:
        data = self._fetch_json(f"{PRH_API}?{urlencode(params)}")
        companies = data.get("companies") if isinstance(data, dict) else None
        return companies if isinstance(companies, list) else []

    def facts(self, company: dict[str, Any]) -> dict[str, Fact]:
        business_id = (company.get("businessId") or {}).get("value")
        if not business_id:
            return {}
        source_url = f"{PRH_API}?{urlencode({'businessId': business_id})}"

        def fact(field: str, value: Any, evidence: str) -> Fact:
            return Fact(field, value, evidence, source_url, "registry", self.today, "verified", confidence_for("registry", classified=False))

        out: dict[str, Fact] = {"business_id": fact("business_id", business_id, f"businessId: {business_id}")}

        names = company.get("names", [])
        current_name = next((n["name"] for n in names if n.get("type") == "1" and not n.get("endDate")), None)
        if current_name:
            out["name"] = fact("name", current_name, f"name: {current_name}")
        aliases = sorted({n["name"] for n in names if n.get("name") and n["name"] != current_name})
        if aliases:
            out["aliases"] = fact("aliases", aliases, "names: " + "; ".join(aliases))

        founded = company.get("registrationDate") or (company.get("businessId") or {}).get("registrationDate")
        if founded:
            out["founded_date"] = fact("founded_date", founded, f"registrationDate: {founded}")

        if form := _current(company.get("companyForms", [])):
            label = _description(form)
            legal_form = next((code for needle, code in _LEGAL_FORMS if needle in label.casefold()), "other")
            out["legal_form"] = fact("legal_form", legal_form, f"companyForm: {label}")

        if status := self._status(company):
            out["status"] = fact("status", status[0], status[1])

        if line := company.get("mainBusinessLine"):
            code = line.get("type")
            if code:
                out["industry_code"] = fact("industry_code", code, f"mainBusinessLine: {code} {_description(line)}".strip())

        address = next((a for a in company.get("addresses", []) if a.get("type") == 1), None)
        city = next((p.get("city") for p in (address or {}).get("postOffices", []) if p.get("languageCode") == _FINNISH), None)
        if city:
            out["city"] = fact("city", city.title(), f"postOffice: {city}")
            out["country"] = fact("country", "Finland", "Finnish Trade Register (PRH) company record")
        return out

    @staticmethod
    def _status(company: dict[str, Any]) -> tuple[str, str] | None:
        for situation in company.get("companySituations", []):
            label = _description(situation).casefold()
            if "bankrupt" in label:
                return "bankrupt", f"companySituation: {_description(situation)}"
            if "liquidation" in label:
                return "liquidation", f"companySituation: {_description(situation)}"
        if company.get("tradeRegisterStatus") == "1":
            return "active", "tradeRegisterStatus: registered"
        if company.get("endDate"):
            return "dissolved", f"endDate: {company['endDate']}"
        return None
