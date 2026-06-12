# UCI Default of Credit Card Clients Benchmark

This folder is reserved for the public benchmark dataset used in MicroScore
Experiment B.

Official source:

- https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients

The raw benchmark file is not committed to Git. Download the official
`default of credit card clients.xls` file from UCI and place it here:

```text
data/external/benchmarks/uci-default-credit-card-clients/raw/default of credit card clients.xls
```

Then run:

```powershell
.venv\Scripts\python -m microscore --benchmark uci-default
```

Or pass a custom local CSV/XLS path:

```powershell
.venv\Scripts\python -m microscore --benchmark uci-default --benchmark-data "C:\path\to\default of credit card clients.xls"
```

The generated artifacts are written to:

```text
reports/benchmark-artifacts/uci-default-credit-card-clients/
```

Important limitation: this is a Taiwan credit-card default dataset. It is useful
for public benchmark validation of the modeling pipeline, but it is not local
Pavlodar MFI data and does not prove readiness for real lending deployment in
Kazakhstan.
