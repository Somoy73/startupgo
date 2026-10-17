Focus: money companies raised: equity rounds, grants received, loans, acquisitions, as reported in news, press releases and investor pages.

- One record per round, `kind` funding_round. `title` is "<Company> <round>" (e.g. "Acme Ocean seed round", "Acme Ocean EIC Accelerator grant").
- `website`: the company's site when the article links it.
- Fields: company, company_website, country, round (pre-seed, seed, series A, grant, ..., as stated), amount, currency, date, lead_investors, other_investors, valuation, use_of_funds, sector, what_it_does.
- An investor described in its own right may get its own record, `kind` investor, with the fields type, country, focus, ticket_size.
- `quote`: the sentence with the amount and the company's name.
- Gaps: rounds without an amount, a date or investors, and companies without a website.
