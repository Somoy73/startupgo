"""EU and national sources: CORDIS grants, BlueInvest pipeline, Google Patents pages, French and Norwegian registers.

Left out on purpose (limited coverage): the EU Blue Economy Observatory (data stops at 2023, EU-27 only,
established sectors only), EMFAF beneficiary lists (per-country formats), startup directories.
"""
from __future__ import annotations

from common import http, source

CORDIS = "https://cordis.europa.eu/search"
BLUEINVEST = "https://blueinvest-community.converve.io/pipeline_front.html"


@source(name="cordis_projects", section="3 Funding & grants", access="free", endpoint=CORDIS,
        use="EU research and innovation projects (FP7, H2020, Horizon Europe) with every participant's EU contribution, SME flag, role and VAT number",
        params={"q": "CORDIS query language, e.g. contenttype='project' AND 'Notpla'  (also: AND programme/code='HORIZON.3.1', AND status='SIGNED')",
                "num": "results per page (<=100)", "p": "page (1-based)", "srt": "Relevance:decreasing | /project/startDate:decreasing", "format": "json"},
        defaults={"query": "contenttype='project' AND 'seaweed'", "num": 5})
def cordis_projects(query="contenttype='project' AND 'seaweed'", num=50, p=1, srt="Relevance:decreasing"):
    return http(CORDIS, {"q": query, "num": num, "p": p, "srt": srt, "format": "json"})


@source(name="blueinvest_pipeline", section="1 Startup & investor", access="free", endpoint=BLUEINVEST,
        use="EU BlueInvest Project Pipeline: public showcase of ~700 blue-economy SMEs and projects with TRL and sector",
        params={"params[page]": "1..N (20 per page)", "params[q]": "free-text search", "params[event_id]": "1"},
        defaults={"page": 1}, notes="HTML; parsed in ingest_eu.py. Be polite: about 1 request per second.")
def blueinvest_pipeline(page=1, q=""):
    return http(BLUEINVEST, {"params[event_id]": 1, "params[show]": "comp", "params[q]": q, "params[page]": page}, raw=True)


@source(name="blueinvest_profile", section="1 Startup & investor", access="free", endpoint=f"{BLUEINVEST}?action=detail",
        use="One BlueInvest profile: company, country, sector, TRL, financial needs, funding allocation, website",
        params={"params[other_id]": "profile id from the pipeline list"}, defaults={"other_id": 1047})
def blueinvest_profile(other_id=1047):
    return http(BLUEINVEST, {"action": "detail", "params[event_id]": 1, "params[show]": "comp", "params[q]": "",
                             "params[other_id]": other_id}, raw=True)


@source(name="google_patents_page", section="5 Patents & research", access="free", endpoint="https://patents.google.com/patent/{number}/en",
        use="Patent page: all CPC classification codes, legal status, family countries",
        params={"number": "publication number, e.g. EP3601061B1"}, defaults={"number": "EP3601061B1"},
        notes="Unofficial; same blocking risk as google_patents_xhr")
def google_patents_page(number="EP3601061B1"):
    return http(f"https://patents.google.com/patent/{number}/en", headers={"User-Agent": "Mozilla/5.0"}, raw=True)


@source(name="fr_recherche_entreprises", section="2 Registries", access="free", endpoint="https://recherche-entreprises.api.gouv.fr/search",
        use="French companies: SIREN, founding date, legal form, NAF code, headcount band, directors, financials, status",
        params={"q": "name or SIREN", "per_page": "<=25", "page": "", "activite_principale": "NAF code filter", "code_postal": "",
                "departement": "", "etat_administratif": "A (active) | C (closed)", "tranche_effectif_salarie": "band code",
                "nom_personne": "director surname", "prenoms_personne": "director first names", "est_entrepreneur_individuel": "bool"},
        defaults={"q": "Algolesko", "per_page": 3})
def fr_recherche_entreprises(**p):
    return http("https://recherche-entreprises.api.gouv.fr/search", p)


@source(name="no_brreg", section="2 Registries", access="free", endpoint="https://data.brreg.no/enhetsregisteret/api/enheter",
        use="Norwegian companies: org number, founding date, legal form, employees, industry, bankruptcy and liquidation flags",
        params={"navn": "name", "organisasjonsnummer": "", "naeringskode": "NACE", "fraAntallAnsatte": "", "tilAntallAnsatte": "",
                "konkurs": "bool", "size": "<=100", "page": "0-based", "(roles)": "/enheter/{orgnr}/roller"},
        defaults={"navn": "Ocean Sun", "size": 3})
def no_brreg(orgnr=None, roles=False, **p):
    if orgnr:
        return http(f"https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}" + ("/roller" if roles else ""))
    return http("https://data.brreg.no/enhetsregisteret/api/enheter", p)
