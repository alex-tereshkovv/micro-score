# External Reference Data

This folder contains small, hand-curated public-context tables used by the
research prototype.

## `pavlodar_district_profiles.csv`

Purpose: provide an evidence-based regional scaffold for simulated Pavlodar
context fields.

Evidence-based columns:

- `district`
- `settlement_type`
- `population_2023`
- `base_weight`

Model-assumption columns:

- `distance_to_pavlodar_km`
- `digital_access_index`
- `income_index`
- `mfi_branch_access_index`
- `seasonal_income_risk`

Sources:

- Kazakhstan Bureau of National Statistics regional page for 2026 population,
  urban/rural split, unemployment, and regional economic context:
  https://stat.gov.kz/ru/region/pavlodar/
- Official government regional overview for administrative structure and
  regional context:
  https://www.gov.kz/memleket/entities/qazalem/activities/27976?lang=en
- CityPopulation.de administrative table citing the Agency of Statistics of the
  Republic of Kazakhstan for 2023 estimates by district/city:
  https://www.citypopulation.de/en/kazakhstan/admin/12__pavlodar/

The table is not anonymized MFI data. It is a transparent research scaffold
until real local partner data becomes available.
