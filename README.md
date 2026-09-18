# Tech Risk Control Exception Tracker & Governance Dashboard

A repeatable data reconciliation and exception-reporting pipeline, built to
mirror the day-to-day of a **Technology Risk Intelligence / Line 2 oversight**
analyst function: extract data from multiple sources, reconcile and
quality-check it, flag exceptions against defined SLAs, track remediation
over time, and produce a governance-ready summary.

This is a demonstration project using synthetic data — it is not connected
to any real system.

## Why this project

Built specifically against the requirements of an Analyst, Technology Risk
Intelligence role (Line 2, Group Technology Risk). Every JD requirement maps
to a concrete piece of this pipeline:

| JD requirement | Where it's implemented |
|---|---|
| Extract, clean, reconcile data from approved sources | `scripts/reconcile.py` — Step 1–2 |
| Quality checks before use / before distribution | `scripts/reconcile.py` — Step 2, logged to `qa_check_log.csv` |
| Escalate data quality issues / anomalies | Orphan & duplicate detection surfaced, not silently dropped (`_unreconciled_records.csv`) |
| Refresh dashboards and reporting packs | `output/dashboard.html` — one command regenerates it end-to-end |
| Basic trend / exceptions analysis | Exception register + by-system / by-type breakdowns in the dashboard |
| Evidence referencing / traceability | Every exception row carries an `evidence_ref` back to its source record |
| Uplift tracking (PACT-aligned) | `scripts/update_uplift_tracker.py` — tracks Open → In Progress → Remediated over repeated runs |
| Governance pack preparation / draft narrative | `scripts/generate_governance_pack.py` — auto-drafts a 1-page PDF summary for analyst review before submission |
| Basic automation (Python / scripting) | Whole pipeline runs end-to-end via `run_pipeline.sh` |

## Project structure

```
techrisk_project/
├── data/                       # mock "approved source" extracts
│   ├── vulnerability_scan.csv
│   ├── patch_compliance.csv
│   └── access_review.csv
├── scripts/
│   ├── generate_mock_data.py   # simulates a new week's data drop
│   ├── reconcile.py            # extract -> clean -> reconcile -> QA -> flag exceptions
│   ├── update_uplift_tracker.py# PACT-style remediation tracking over time
│   └── generate_governance_pack.py # 1-page PDF governance summary
├── output/
│   ├── exception_register.csv  # traceable exception log
│   ├── qa_check_log.csv        # evidence QA ran before distribution
│   ├── run_summary.csv         # feeds the dashboard + governance pack
│   ├── uplift_tracker.csv      # remediation tracking
│   ├── governance_pack.pdf     # generated governance summary
│   ├── dashboard_data.json     # data feeding the dashboard
│   └── dashboard.html          # interactive dashboard (open in any browser)
├── run_pipeline.py             # cross-platform runner (recommended)
├── run_pipeline.bat            # Windows double-click / Command Prompt wrapper
├── run_pipeline.sh             # macOS/Linux wrapper
└── README.md
```

## Running it

Windows (Command Prompt or PowerShell):

```text
python run_pipeline.py
```

Or double-click `run_pipeline.bat`.

macOS/Linux:

```bash
./run_pipeline.sh
```

This simulates one full weekly cycle:
1. Generates a fresh mock data drop (or use your own CSVs in `data/`)
2. Reconciles sources, runs quality checks, flags exceptions
3. Updates the uplift/remediation tracker
4. Regenerates the governance pack PDF
5. Refreshes the dashboard data

Open `output/dashboard_live.html` in a browser to view the refreshed dashboard. `output/dashboard.html` is kept as the reusable template.

## Notes on data quality by design

The mock data intentionally includes a duplicate row, a casing mismatch, and
a reference to a system outside the master system list. The pipeline is
built to **catch and surface these rather than silently dropping or
ignoring them** — that's the actual behaviour a Line 2 oversight function
requires: escalate anomalies, don't hide them.
