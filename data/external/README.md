# External Reference Data

This folder contains small, hand-curated public-context tables used by the
research prototype.

## `pavlodar_district_profiles.csv`

Purpose: provide an evidence-based regional scaffold for simulated Pavlodar
context fields.

## Evidence Status

Every assumption or hypothesis below should be treated as "Needs validation"
before any pilot or real lending use.

| Column | Status | Notes |
| --- | --- | --- |
| `district` | Evidence-based | Public administrative district/city names. |
| `settlement_type` | Evidence-based / simplified | Derived from public administrative context, simplified into urban, industrial city, peri-urban, and rural groups. |
| `population_2023` | Secondary public source | Current values come from CityPopulation.de tables citing Kazakhstan statistical authorities; replace with direct official tables when available. |
| `base_weight` | Derived | Computed from `population_2023`. |
| `distance_to_pavlodar_km` | Assumption | Approximate research feature; should be replaced with geospatial calculation. |
| `digital_access_index` | Hypothesis | Should be replaced with measured ICT/mobile/internet access indicators. |
| `income_index` | Hypothesis | Should be replaced with district-level income or labor-market data. |
| `mfi_branch_access_index` | Hypothesis | Should be replaced with observed MFI/bank branch, agent, or digital-service availability. |
| `seasonal_income_risk` | Hypothesis | Should be validated using local sector, employment, and income-volatility evidence. |
| `financial_access_gap` | Derived hypothesis | Derived from assumed digital and MFI branch access indices. |

## Source Map

| Research need | Current source | Evidence class | Validation action |
| --- | --- | --- | --- |
| Pavlodar regional population, urban/rural split, labor and income context | Kazakhstan Bureau of National Statistics regional page | Official | Use as primary region-level context. |
| Demographic publications and population tables | Kazakhstan Bureau of National Statistics demography page | Official | Use for refreshed population tables and methodology. |
| ICT/mobile/internet access context | Kazakhstan Bureau of National Statistics ICT and communication statistics | Official | Replace `digital_access_index` with measured indicators where possible. |
| Administrative and regional overview | Official government regional overview | Official | Use for regional narrative and administrative context. |
| Financial-market and microfinance regulator context | Agency for Regulation and Development of the Financial Market | Official | Use for MFI-sector governance and regulatory framing. |
| National financial infrastructure context | National Bank of Kazakhstan regional branches | Official | Use as context; not a direct MFI branch proxy. |
| Machine-readable open datasets | Kazakhstan open data portal | Official portal | Search for district-level and financial-access datasets. |
| District/city 2023 population values | CityPopulation.de citing Kazakhstan statistics | Secondary | Replace with direct official source before paper/PDF submission. |

## Sources

- Kazakhstan Bureau of National Statistics regional page for 2026 population,
  urban/rural split, unemployment, and regional economic context:
  https://stat.gov.kz/ru/region/pavlodar/
- Kazakhstan Bureau of National Statistics demography page:
  https://stat.gov.kz/industries/social-statistics/demography/
- Kazakhstan Bureau of National Statistics ICT and communication statistics:
  https://stat.gov.kz/industries/business-statistics/stat-it/
- Official government regional overview for administrative structure and
  regional context:
  https://www.gov.kz/memleket/entities/qazalem/activities/27976?lang=en
- Agency for Regulation and Development of the Financial Market:
  https://www.gov.kz/memleket/entities/ardfm?lang=en
- National Bank of Kazakhstan regional branches:
  https://nationalbank.kz/en/page/territorialnye-filialy
- Kazakhstan open data portal:
  https://data.egov.kz/
- CityPopulation.de administrative table citing the Agency of Statistics of the
  Republic of Kazakhstan for 2023 estimates by district/city:
  https://www.citypopulation.de/en/kazakhstan/admin/12__pavlodar/

The table is not anonymized MFI data. It is a transparent research scaffold
until real local partner data becomes available.
