# Mamaearth Growth Analytics Capstone

An end-to-end analytics repository for the Mamaearth Growth Analytics scenario in the capstone brief. The repository deliberately keeps the SQL and pandas pipelines independent over the same raw CSVs, then passes the verified pandas findings into the GenAI narrator.

## Repository structure

```text
.
├── README.md
├── requirements.txt
├── sql/
│   ├── schema.sql
│   ├── seed_data.sql
│   └── reports.sql
├── data/
│   ├── customers.csv
│   ├── products.csv
│   └── orders.csv
├── analysis/
│   ├── clean_and_eda.py
│   └── visualize.py
├── visualizations/
│   ├── return_rate_by_payment.png
│   └── monthly_revenue_trend.png
└── narrator/
    ├── findings.json
    ├── sample_output.txt
    └── generate_narrative.py
```

## Pipeline flow

```text
Raw CSVs
  ├──> SQLite relational layer -> SQL reports
  └──> pandas cleaning + EDA -> verified findings.json
                                      │
                                      v
                              GenAI / offline narrator
                                      │
                                      v
                               SCR business narrative
```

No downstream layer invents or recomputes business figures it does not own: SQL reports compute the raw database figures; pandas computes the cleaned EDA figures; `findings.json` is written by the pandas pipeline; and the narrator receives those findings as its source of truth.

## 1. Run the SQL layer first

From the repository root, ensure SQLite is installed.

```bash
sqlite3 capstone.db < sql/schema.sql
sqlite3 capstone.db < sql/seed_data.sql
sqlite3 capstone.db < sql/reports.sql
```

`schema.sql` resets the three tables, so the first two commands are safely repeatable. `reports.sql` includes the required `ALTER TABLE` section for `loyalty_tier`; rerun that report file against a fresh schema if you want to execute the whole file again.

The raw-data sanity counts after seeding are 45 customers, 16 products, and 180 orders. The required Part 1 report outputs are preserved as comments directly above each query in `sql/reports.sql`.

## 2. Run the independent pandas analysis layer

Install the Python dependencies:

```bash
python -m pip install -r requirements.txt
```

Then run, in this exact order:

```bash
python analysis/clean_and_eda.py
python analysis/visualize.py
```

`clean_and_eda.py` reads the three CSVs directly, prints the acceptance checks, flags (but does not drop) quantity outliers, and writes `narrator/findings.json` from the computed results. `visualize.py` regenerates both PNGs from the same cleaned pipeline and uses the outlier-corrected monthly series for the revenue chart.

## 3. Run the GenAI narrator

The narrator supports both Gemini and a completely offline path.

### Gemini API path

Google AI Studio's Gemini free tier can be used for this project. Set the API key as an environment variable; do not hardcode it into the repository.

Linux/macOS:

```bash
export GEMINI_API_KEY="YOUR_KEY"
python narrator/generate_narrative.py
```

Windows PowerShell:

```powershell
$env:GEMINI_API_KEY="YOUR_KEY"
python narrator/generate_narrative.py
```

The optional `GEMINI_MODEL` environment variable can override the default model.

### Offline / keyless path

No API key is required:

```bash
python narrator/generate_narrative.py
```

When `GEMINI_API_KEY` is absent, the script uses `generate_scr_narrative_offline(findings)` and makes no network call. If a configured Gemini call fails, it also falls back to the same deterministic template.

The script saves the generated narrative to `narrator/sample_output.txt` and runs the five-figure numeric accuracy checker. The checked figures are the cleaned revenue, COD return rate, highest-risk COD + Tier-2 return rate, duplicate reconciliation delta, and March peak revenue.

## Reproducibility checks

The capstone brief's key acceptance values are reproduced by the pipeline, including:

- Raw SQL revenue: ₹99,860.20
- Cleaned pandas revenue: ₹97,358.30
- Duplicate reconciliation delta: ₹2,501.90
- COD return rate: 44.4%
- Highest-risk segment: COD + Tier-2 cities at 54.5%
- Outlier-corrected peak: March 2026 at ₹20,318.90

The source CSVs are intentionally not edited by hand; all cleaning is performed in Python, as required by the brief.
