# Startup Go — Research Notes

Background research behind Startup Go's data model and scoring. Compiled 2026-10-16.

---

## 1. DeepTree: reference product notes

DeepTree (Milan, founded 2024 by Lorenzo Ferretti (CEO) and Claudio Arione (CTO)) is an
AI workspace for private markets. It raised a €2M seed in May 2026, led by CDP Venture Capital, and
says more than 100 banks, PE funds, M&A boutiques and asset managers use it.

### Features (from public coverage)

| # | Feature | What it does | Startup Go equivalent |
|---|---------|--------------|------------------------|
| 1 | Single integrated workspace | Financial data, corporate information and private-market analysis in one place, built into analysts' daily workflow | Deal-flow dashboard is the home screen |
| 2 | Natural-language screening | Find targets in plain language, with filters for region, ownership type, sector and revenue range | Search bar + filter row (sector, country, stage, min TRL/BRL, ocean impact area) |
| 3 | Company analysis pages | Filed financials, cap tables, trading comparables | Startup profile: readiness levels, ocean KPIs, funding rounds, sources |
| 4 | M&A deal intelligence | Searches thousands of transactions; maps deals, multiples and advisors | Later: funding-round explorer across all startups |
| 5 | Valuation & comparables | Compares valuations, sector models and comparable companies in seconds | Compare view (up to 3 startups side by side) |
| 6 | Portfolio monitoring | One view of portfolio performance, with automatic data collection, real-time KPIs and competitive benchmarking | Pipeline board (Sourced → Screening → Diligence → Term sheet → Portfolio) |
| 7 | Buyer discovery algorithm | Finds likely acquirers or buyers for a company | Later: investor ↔ startup matching (thesis fit) |
| 8 | Document generation | Investment memos, market maps, presentations | Later: one-click IC memo from a profile |
| 9 | Data collection & structuring | Proprietary pipeline; this is where DeepTree says its advantage lies; adding EU datasets | Backend ingestion (to build) |
| 10 | Enterprise / "Palantir-style" deployment | Full stack deployed against the client's private data, which stays in the client's cloud | Out of scope for MVP |
| 11 | Mobile app | Listed in one company profile | Responsive web first |

Sources: [StartupBusiness](https://www.startupbusiness.it/en/deeptree-secures-e2-million-for-its-ai-powered-fintech-solution/172223/),
[Teleborsa](https://www.teleborsa.it/AMP/News/2026/05/28/deeptree-round-da-2-milioni-di-euro-ferretti-modello-palantir-per-i-mercati-privati-1.html),
[Forbes Italia](https://forbes.it/2026/05/28/deep-tree-under-30-round-intelligence-ia),
[Raising.fi](https://raising.fi/news/deeptree-undisclosed-may-2026).
Caveat: these are press and aggregator descriptions, not hands-on use of the product.

**Takeaway for Startup Go.** DeepTree is horizontal: any private company, scored on its financials.
Startup Go is vertical. It covers deep-tech and ocean startups, which often have no meaningful
financials yet, so we score them on **readiness levels and verified impact evidence**.

---

## 2. Scoring frameworks

### 2.1 KTH Innovation Readiness Level™ (the readiness backbone)

KTH IRL is the most widely used multi-dimensional readiness model (KTH, DTU, McGill, FRQ Québec).
It scores six dimensions from 1 to 9. **BRL and TRL, which this project asked for, are two of its six dimensions.**

| Code | Dimension | L1 | L5 | L9 |
|------|-----------|----|----|----|
| CRL | Customer | Hunch that a need exists | Problem–solution fit confirmed by customers | Widespread, repeatable, scalable sales |
| TRL | Technology | Vague idea / research result | Components validated in a relevant environment | Proven in actual operations by several users |
| BRL | Business model | Vague business idea | Revenue and cost sides validated with external feedback; P&L indicates viability | Sustainable business model proven over time (profit + environmental/social impact) |
| IPRL | IP | Hypothesising about possible IP | Draft IP strategy; first formal application filed | IP strategy proven; key IP granted in several countries |
| TMRL | Team | Single individual missing key competencies | Founding team with main competencies and signed shareholder agreement | High-performing organisation, continuously developed |
| FRL | Funding | Little insight into costs or funding options | Pitch tested; 12-month budget; funding strategy decided | ≥6–12 months runway secured; full financial control |

Full level text for all 54 cells is in `DB/seed.sql` (`readiness_levels`).

Two rules from the KTH user guide that Startup Go applies:
- **Dimensions don't need to move together**, but a gap of more than 2–3 levels between them
  hinders development and raises failure risk. → the *imbalance flag* in scoring.
- KTH's BRL definition of "sustainable business model" already includes environmental and
  social impact. → this links BRL to the Ocean Impact score.

Sources: [KTH IRL compiled scale (PDF)](https://frq.gouv.qc.ca/app/uploads/2025/02/kth-innovation-readiness-level_compiled_va.pdf),
[KTH IRL user guide (PDF)](https://frq.gouv.qc.ca/app/uploads/2025/02/kth-irl-user-guide_va.pdf),
[DTU](https://www.inside.dtu.dk/en/research/commercialisation-and-patenting/patents-and-software/kth-innovation-readiness-level).

### 2.2 Ocean Impact Readiness (Ocean Impact Navigator)

I found no published scale called "Ocean Impact Readiness Level". The closest standard is the
**Ocean Impact Navigator** (1000 Ocean Startups + SYSTEMIQ, launched at the UN Ocean Conference 2022;
WEF edition 2023). It is an open-source library of **30 KPIs in 6 impact areas**:

| Area | Name | Example KPIs |
|------|------|--------------|
| A | Sustainably managed ocean resources | A1 biomass preserved/restored, A4 tonnes of seaweed & bivalves produced |
| B | A clean ocean | B1 micro-plastics diverted, B2 macro-plastic diverted, B3 N/P pollution mitigated |
| C | Thriving & restored marine habitats | C1 coral, C2 mangroves, C3 seagrass, C5 kelp forest area protected/restored |
| D | Towards 1.5 °C | D1 GHG reduced/avoided, D3 carbon sequestered, D4 NOx, D5 SOx mitigated |
| E | Climate-resilient coastal communities | E1 coastline protected, E2 ocean data used in adaptation decisions, E4 food security |
| F | Positive socio-economic outcomes | F1 jobs created, F2 people trained, F3 share of women employees |

The Navigator lets startups report each KPI **quantitatively or qualitatively**, with supporting
evidence, and expects early-stage companies to report qualitatively. Startup Go turns that into
a 0–4 **evidence level** per KPI, which gives a readiness-style score:

| Evidence | Meaning |
|----------|---------|
| 0 | Not addressed |
| 1 | Claimed (qualitative statement only) |
| 2 | Qualitative + supporting evidence (pilots, partner statements) |
| 3 | Quantitatively measured by the company |
| 4 | Third-party verified / certified |

Sources: [WEF – The Ocean Impact Navigator 2023 (PDF)](https://www3.weforum.org/docs/WEF_The_Ocean_Impact_Navigator_2023.pdf),
[1000 Ocean Startups – Navigator](https://www.1000oceanstartups.org/navigator),
[UN SDG launch event](https://sdgs.un.org/events/ocean-impact-navigator-harnessing-innovation-and-new-impact-measurement-framework-regenerate),
[Katapult Ocean 2024 Impact Report](https://katapult.vc/ocean/2024-impact-report-progress-challenges-and-the-path-to-a-thriving-blue-economy).

### 2.3 Investment Readiness / Potential

- **Investment Readiness Level** (Steve Blank, 2013–14): a TRL-style ladder for startups, tied
  to customer-development milestones.
  [Blog 1](https://steveblank.com/2013/11/25/its-time-to-play-moneyball-the-investment-readiness-level/),
  [Blog 2](https://steveblank.com/2014/07/01/how-investors-make-better-decisions-the-investment-readiness-level/)
- **Fellnhofer (2015)**, *Literature review: investment readiness level of SMEs*, Int. J. Managerial
  and Financial Accounting. [Link](https://inderscience.com/offer.php?id=74904)
- **Bradford (IAC 2024)** argues that TRL should drive the choice of financing instrument for space
  startups. [Link](https://iafastro.directory/iac/paper/id/85664/abstract-pdf/IAC-24,E6,1,11,x85664.brief.pdf)

### 2.4 Data-driven startup scoring (for the later ML phase)

| Paper | Data | Finding relevant to us |
|-------|------|------------------------|
| Potanin et al., *Startup success prediction and VC portfolio simulation using CrunchBase data* (2023) [arXiv:2309.15552](https://arxiv.org/abs/2309.15552) | Crunchbase, Series B/C | Funding metrics + founder traits + industry category; includes a backtested VC portfolio simulation |
| *A Fused Large Language Model for Predicting Startup Success* (2024) [arXiv:2409.03668](https://arxiv.org/abs/2409.03668) | 20,172 Crunchbase profiles | Founders' self-descriptions carry significant predictive signal; text plus structured fundamentals works best |
| Yin, Li & Wu, *Solving the Data Sparsity Problem in Predicting the Success of Startups* (2021) [arXiv:2112.07985](https://arxiv.org/abs/2112.07985) | Crunchbase | Early-stage data is sparse. Directly relevant: our startups are early stage |

Common finding: funding history and company age carry most of the signal, and accuracy is
modest (~0.74 ROC-AUC in one survival study). **So Startup Go v1 uses a transparent, rules-based
score rather than a black-box model.** An ML layer can be added once we have labelled outcomes.

---

## 3. Seed dataset

`DB/seed.sql` holds 8 real ocean-tech startups. Funding facts come from public announcements
(each round links its source). **Every readiness level and KPI evidence level is a seed estimate
I made from public information. None comes from the companies.** Each record is marked
`confidence = 'low'` and must be validated in diligence.

| Startup | HQ | What | Latest verified round |
|---------|----|------|----------------------|
| Notpla | London, UK | Seaweed-based packaging | £20M Series A+ (Sep 2024), lead UB Forest Industry Green Growth Fund |
| Sofar Ocean | San Francisco, US | Spotter buoys & marine weather data | $39M Series B (Nov 2021), USV + Foundry Group |
| Ocean Rainforest | Faroe Islands | Offshore seaweed cultivation | $6.2M Series A (Feb 2023), lead Grantham Foundation |
| Seabound | London, UK | Onboard carbon capture for ships | $4.4M seed (2022), lead Lowercarbon; £1.1M UK CMDC grant (2025) |
| Oceanium | Oban, UK | Seaweed biorefinery | ~$2.6M (2023), lead Builders Vision; earlier £2M Seed II |
| SeaForester | Lisbon, PT | Kelp / marine forest restoration | $1.9M seed (Oct 2025), co-led WWF + Schmidt Marine |
| Kelp Blue | NL / Lüderitz, NA | Giant kelp forest cultivation | ~$60M in-principle commitment (CFM + Eos), phased and pending approvals |
| Clearbot | Hong Kong | Autonomous waste-collecting boats | Seed (Sep 2022), lead Alibaba HK Entrepreneurs Fund, amount undisclosed |

Data-quality notes: aggregator sites (Seedtable, VCBacked, Caplight, CB Insights) often disagree
with company announcements. The seed data keeps the announced figure and stores its source URL.
