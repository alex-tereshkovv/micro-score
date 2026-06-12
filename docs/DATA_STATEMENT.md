# MicroScore Data Statement

This statement explains what data MicroScore currently uses, what is simulated,
what is evidence-based, and what must be validated before any real lending use.

## Current Data Status

MicroScore does not currently use real borrower-level data from a microfinance
organization. The borrower-level credit-risk dataset is synthetic and is used
for research pipeline development, leakage testing, audit design, and product
prototyping.

The Pavlodar regional layer is a public-context scaffold. It helps ask local
questions, but it is not a substitute for observed borrower repayment data or
measured financial-access data.

## Data Inventory

| Data source | Current use | Evidence status | Notes |
| --- | --- | --- | --- |
| Synthetic borrower-level credit-risk dataset | Train and test baseline ML models | Synthetic | Useful for engineering and audit design; not proof of real-world performance. |
| UCI Default of Credit Card Clients | Public benchmark validation | Evidence-based public benchmark | Real credit-card default data from Taiwan; useful for pipeline validation, not local Kazakhstan deployment evidence. |
| Pavlodar district/city names | Regional simulation and segment analysis | Evidence-based | Based on public administrative structure. |
| Pavlodar population and urban/rural context | Sampling weights and local motivation | Evidence-based | Should be refreshed from official statistics before publication. |
| District-level 2023 population estimates | Sampling weights | Secondary public source | Current CSV uses CityPopulation.de tables that cite Kazakhstan statistics; replace with direct official tables when available. |
| Distance to Pavlodar | Regional context feature | Assumption | Needs validation from geospatial calculations or official settlement coordinates. |
| Digital access index | Proxy for regional digital inclusion | Hypothesis | Should be replaced with measured ICT/mobile/internet access indicators. |
| MFI branch access index | Proxy for access to financial services | Hypothesis | Should be replaced with branch/agent/mobile-service availability data. |
| Seasonal income risk | Proxy for income volatility | Hypothesis | Should be validated with local employment, sector, agriculture, and household-income data. |
| Financial access gap | Derived feature | Hypothesis | Currently derived from assumed digital and branch access indices. |

## Evidence-Based / Assumption / Needs Validation

| Feature group | Evidence-based today | Assumption today | Needs validation |
| --- | --- | --- | --- |
| Geography | Pavlodar region, cities, districts, settlement categories | Exact mapping of borrower residence to financial behavior | Borrower-level district, settlement, and consented location context. |
| Population | Regional and district/city population context | Sampling weights from public estimates | Direct official district-level data source and update schedule. |
| Digital access | Official ICT statistics exist at national/regional level | District-level digital access index | Measured internet/mobile banking access by district or borrower consented data. |
| Financial access | Financial regulators publish institution context | District-level MFI branch access index | MFI/bank branch, agent, and digital-service availability by district. |
| Income stability | Regional labor/income statistics exist | Seasonal income risk by district | Borrower occupation, income volatility, sector, and repayment timing. |
| Credit behavior | Synthetic late-payment feature exists | Relationship between synthetic late payments and default | Real anonymized repayment histories and thin-file borrower outcomes. |

## Public Sources To Use Or Validate

- Bureau of National Statistics regional page for Pavlodar: population,
  urban/rural split, labor, income, GRP, and regional tables.
  https://stat.gov.kz/ru/region/pavlodar/
- Bureau of National Statistics demography page: population publications,
  electronic tables, and dynamic series.
  https://stat.gov.kz/industries/social-statistics/demography/
- Bureau of National Statistics ICT and communication statistics: household
  ICT use, mobile subscribers, internet-access indicators, and communication
  service tables.
  https://stat.gov.kz/industries/business-statistics/stat-it/
- Official government regional overview for Pavlodar: regional description,
  population, urban/rural share, and administrative structure.
  https://www.gov.kz/memleket/entities/qazalem/activities/27976?lang=en
- Agency for Regulation and Development of the Financial Market: official
  regulator for financial market supervision, financial consumer protection,
  and the microfinance sector.
  https://www.gov.kz/memleket/entities/ardfm?lang=en
- National Bank of Kazakhstan regional branches page: reference point for
  national financial infrastructure context.
  https://nationalbank.kz/en/page/territorialnye-filialy
- Kazakhstan open data portal: possible source for machine-readable public
  datasets.
  https://data.egov.kz/
- CityPopulation.de Pavlodar table: secondary convenience source that cites
  Kazakhstan statistical authorities for administrative population estimates.
  This should be treated as a bridge, not the final official source.
  https://www.citypopulation.de/en/kazakhstan/admin/12__pavlodar/
- UCI Default of Credit Card Clients: public benchmark dataset for credit-card
  default prediction.
  https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients

## Why Real Borrower Data Is Not Used Yet

Real credit data is sensitive. It may contain identity, repayment history,
income, contact, location, and household information. MicroScore should not use
real borrower data until there is:

- written permission or a data-use agreement with a partner organization;
- consent and privacy review;
- anonymization or pseudonymization;
- a clear data retention policy;
- a documented purpose limitation;
- security controls for storage and access;
- review of fairness, harm, and exclusion risks.

## Data Needed For A Pilot

Minimum anonymized pilot dataset:

- application date and loan product type;
- requested amount, approved amount, term, and repayment outcome;
- borrower district or settlement type;
- consented income stability indicators;
- mobile/digital banking usage indicators, aggregated where possible;
- repayment events over time;
- delinquency dates and recovery outcomes;
- model decision and human analyst decision where available.

Useful external context:

- district-level population and urban/rural split;
- measured internet/mobile access;
- branch, agent, or digital service availability;
- local labor and income volatility indicators;
- sector exposure such as agriculture, trade, services, and industry.

## Data That Should Not Be Collected For Scoring

MicroScore should not collect or use the following for scoring without a strong
legal, ethical, and safety justification:

- raw passwords or authentication secrets;
- contact lists, private messages, call logs, or social media content;
- religion, ethnicity, political views, or health information;
- precise GPS traces beyond what is necessary and consented;
- intrusive device telemetry;
- family-member data without consent;
- data purchased from opaque brokers;
- any variable that cannot be explained to a borrower or loan officer.

## Current Data Risk

The largest current data risk is that the synthetic dataset makes
`late_payment_count` unrealistically predictive. The model can therefore look
strong while relying on a proxy that is close to traditional repayment history.
The thin-file scenario that drops `late_payment_count` is a deliberate stress
test, and its weak performance is treated as a research finding rather than a
failure to hide.
