from startup_agent.registry import PRH_API, PRHRegistry, normalize_company_name

COMPANY = {
    "businessId": {"value": "2739393-2", "registrationDate": "2016-01-22"},
    "names": [
        {"name": "Acme Ocean Oy", "type": "1"},
        {"name": "Acme Wood Oy", "type": "1", "endDate": "2016-09-07"},
    ],
    "mainBusinessLine": {"type": "26511", "descriptions": [{"languageCode": "3", "description": "Manufacture of instruments"}]},
    "website": {"url": "www.acme.fi"},
    "companyForms": [{"type": "16", "descriptions": [{"languageCode": "3", "description": "Limited company"}]}],
    "companySituations": [],
    "addresses": [{"type": 1, "postOffices": [{"city": "TURKU", "languageCode": "1"}, {"city": "ÅBO", "languageCode": "2"}]}],
    "tradeRegisterStatus": "1",
    "registrationDate": "2016-02-01",
}


class FakeApi:
    def __init__(self, companies):
        self.companies = companies
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        return {"totalResults": len(self.companies), "companies": self.companies}


def test_facts_are_verified_registry_facts():
    facts = PRHRegistry(FakeApi([COMPANY]), today="2026-10-17").lookup(name="x", business_id="2739393-2")
    assert {k: f.value for k, f in facts.items()} == {
        "business_id": "2739393-2",
        "name": "Acme Ocean Oy",
        "aliases": ["Acme Wood Oy"],
        "founded_date": "2016-02-01",
        "legal_form": "limited_company",
        "status": "active",
        "industry_code": "26511",
        "city": "Turku",
        "country": "Finland",
    }
    first = facts["business_id"]
    assert (first.status, first.source_type, first.confidence) == ("verified", "registry", 0.95)
    assert first.source_url == f"{PRH_API}?businessId=2739393-2"


def test_bankruptcy_is_reported():
    bankrupt = {**COMPANY, "companySituations": [{"descriptions": [{"languageCode": "3", "description": "Bankrupt"}]}]}
    facts = PRHRegistry(FakeApi([bankrupt]), today="d").lookup(name="Acme Ocean", business_id="2739393-2")
    assert facts["status"].value == "bankrupt"


def test_name_match_requires_permission_but_domain_match_does_not():
    api = FakeApi([COMPANY])
    registry = PRHRegistry(api, today="d")
    assert registry.lookup(name="Acme Ocean Ltd", allow_name_match=False) == {}
    assert registry.lookup(name="Acme Ocean Ltd", allow_name_match=True)["business_id"].value == "2739393-2"
    assert registry.lookup(name="Totally different", website_domain="acme.fi", allow_name_match=False)
    assert api.urls[0] == f"{PRH_API}?name=Acme+Ocean+Ltd"


def test_normalize_company_name():
    assert normalize_company_name("Acme Ocean Oy") == normalize_company_name("ACME ocean Ltd.") == "acme ocean"
