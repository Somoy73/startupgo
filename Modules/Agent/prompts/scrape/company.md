Focus: one company: everything the documents state about it, for a first investment screen. Documents may be its website, a LinkedIn or Crunchbase page, a registry entry, news or a profile.

- One record `kind` startup (or company) for the company itself, `title` its name, `website` its own site (the site being read counts when it is the company's own). Fields: country, city, legal_name, business_id, founded, sector, what_it_does, product_stage (idea, prototype, pilot, commercial, as stated), business_model, customers_or_pilots, team_size, founders, key_people, funding_raised, investors, revenue, ocean_impact, certifications, patents, awards, latest_news.
- Separate records for each funding round (`kind` funding_round, fields amount, date, investors), each grant or EU project (`kind` project or funding_round), and each named customer, partner or pilot that has its own facts (`kind` other, field relationship).
- What the company says about itself on its own pages is a claim: write it as one ("says its sensor is deployed in 12 ports").
- `quote`: the line that states the record's main claim.
- Gaps: the screening facts that are missing (team, funding, customers, product stage, legal entity), and where to look next (registry, news, LinkedIn, patents).
