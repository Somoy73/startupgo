# Assessment parameters

Final list of parameters used to assess a startup, grouped by dimension. ★ = core parameter.
A plain field name is a feature in `startup_features`; a dotted name is a table column.

## 1. Team

| Parameter | Field |
|---|---|
| ★ Number of founders | `founder_count` |
| ★ Serial founders | `serial_founder_count` |
| ★ Founder retention | `founder_retention` |
| Earlier ventures of the founders | `prior_ventures_total` |
| Earlier ventures that failed | `prior_ventures_failed` |
| Other companies the founders run | `founder_other_ventures` |
| Board size | `board_size` |
| Officer churn | `officer_churn` |
| Headcount | `headcount` |
| Founder roles | `startup_people.role` |
| Founder education | `people.education` |

## 2. Technology and IP

| Parameter | Field |
|---|---|
| ★ Technology readiness (TRL) | `readiness_assessments.trl` |
| ★ First patent granted | `first_patent_granted` |
| Self-reported TRL | `blueinvest_trl` |
| Months from filing to grant | `first_patent_months_to_grant` |
| Patents held / granted | `patent_count`, `patents_granted` |
| Patents pending / abandoned | `patents_pending`, `patents_abandoned` |
| Ocean-technology patents | `ocean_patent_count`, `ocean_tech_groups` |
| IP readiness (IPRL) | `readiness_assessments.iprl` |

## 3. Customers and traction

| Parameter | Field |
|---|---|
| ★ Customer readiness (CRL) | `readiness_assessments.crl` |
| ★ Open roles | `open_roles` |
| Open technical / commercial roles | `technical_open_roles`, `commercial_open_roles` |
| News mentions, last 12 months | `news_mentions_12m` |

## 4. Market and competition

| Parameter | Field |
|---|---|
| ★ Competitor density | `blueinvest_peer_count` |
| ★ TRL compared with peers | `trl_vs_peers` |
| Peer median TRL | `peer_median_trl` |
| Closest peer | `top_peer` |
| Company age | `company_age_years` |
| Blue-economy sector | `blueinvest_sector`, `startups.sector` |

## 5. Business model and distribution

| Parameter | Field |
|---|---|
| ★ Business readiness (BRL) | `readiness_assessments.brl` |

## 6. Funding and deal

| Parameter | Field |
|---|---|
| ★ Total raised | `total_raised_usd` |
| ★ Number of rounds | `round_count` |
| ★ Months since last round | `months_since_last_round` |
| ★ Investor quality | `investor_quality_max` |
| Months between rounds | `median_months_between_rounds` |
| Last round date / stage | `last_round_date`, `last_round_type` |
| Investor mix | `investor_quality_mean`, `specialist_investor_share`, `follow_on_investors` |
| Number of investors / lead investors | `investor_count`, `lead_investors` |
| Valuation | `implied_post_money`, `latest_price_per_share`, `valuation_step_up` |
| EU grants | `eu_grants_total_eur`, `eic_or_sme_instrument`, `eu_coordinator_count` |
| Grant dependency | `grant_to_equity_ratio` |
| Funding sought | `blueinvest_funding_sought_eur` |
| Funding readiness (FRL) | `readiness_assessments.frl` |

## 7. Ocean impact

| Parameter | Field |
|---|---|
| ★ Impact evidence level (0–4) per KPI | `startup_ocean_kpis.evidence_level` |
| ★ Impact areas covered | `startup_ocean_kpis.kpi_code` |
| EU Ocean Mission project | `mission_ocean_grant` |

## Red flags

Any flag sends the startup to manual review; flags are not averaged into scores.

| Flag | Rule |
|---|---|
| Distress | `distress_flag = 1` |
| Registry status not active | `registry_status` ≠ active |
| Down round | `down_round_flag = 1` |
| No round in 2 years | `no_round_24m = 1` |
| Founder departures | `founder_retention < 0.5` |
| TRL self-report far from estimate | `abs(trl_gap) >= 2` |

## Evidence confidence

| Parameter | Field |
|---|---|
| Data completeness | `startup_parameter_status` |
| Funding sources disagree | `funding_total_spread` |
| Founding years disagree | `founded_year_conflicts` |
| TRL gap | `trl_gap` |
| Assessment confidence | `readiness_assessments.confidence` |
