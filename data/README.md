# Data Directory

This folder keeps data separate from notebooks and source code.

```text
data/
|-- app/        # local SQLite app database; runtime files are ignored by Git
|-- external/   # public-context reference tables
|-- raw/        # immutable source files
|-- processed/  # cleaned or transformed datasets, if needed later
`-- interim/    # temporary analysis extracts, if needed later
```

The current dataset is synthetic and lives at:

```text
data/raw/credit_risk_dataset.csv
```

The API prototype stores local runtime state at:

```text
data/app/microscore.sqlite3
```

SQLite files in `data/app/` are not committed.
