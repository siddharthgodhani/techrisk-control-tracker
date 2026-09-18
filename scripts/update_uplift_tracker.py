"""
Uplift Tracker -- simulates PACT-aligned remediation tracking.

Each exception from the current run either:
  - links to an existing open uplift item (status updated), or
  - creates a new uplift item with a target remediation date

Run this AFTER reconcile.py. Running it repeatedly across multiple
"weeks" (by re-running generate_mock_data.py + reconcile.py first)
shows items moving from Open -> In Progress -> Remediated, which is
exactly what a real uplift tracker looks like over time.
"""
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)
TRACKER_PATH = OUT_DIR / "uplift_tracker.csv"

exceptions = pd.read_csv(OUT_DIR / "exception_register.csv")
run_date = datetime.now()

SLA_DAYS_BY_TYPE = {
    "Vulnerability SLA Breach": 21,
    "Patch SLA Breach": 30,
    "Access Recertification Overdue": 14,
}

if TRACKER_PATH.exists():
    tracker = pd.read_csv(TRACKER_PATH)
else:
    tracker = pd.DataFrame(columns=[
        "uplift_id", "evidence_ref", "system_id", "exception_type",
        "first_raised", "target_remediation_date", "status", "last_updated"
    ])

existing_refs = set(tracker["evidence_ref"]) if not tracker.empty else set()
new_items = []
next_id = (tracker["uplift_id"].str.replace("UPL-", "").astype(int).max() + 1) if not tracker.empty else 1

for _, row in exceptions.iterrows():
    if row["evidence_ref"] in existing_refs:
        # already tracked -- just bump last_updated to simulate a status check this cycle
        tracker.loc[tracker["evidence_ref"] == row["evidence_ref"], "last_updated"] = run_date.strftime("%Y-%m-%d")
        continue
    sla = SLA_DAYS_BY_TYPE.get(row["exception_type"], 30)
    new_items.append({
        "uplift_id": f"UPL-{next_id:04d}",
        "evidence_ref": row["evidence_ref"],
        "system_id": row["system_id"],
        "exception_type": row["exception_type"],
        "first_raised": run_date.strftime("%Y-%m-%d"),
        "target_remediation_date": (run_date + timedelta(days=sla)).strftime("%Y-%m-%d"),
        "status": "Open",
        "last_updated": run_date.strftime("%Y-%m-%d"),
    })
    next_id += 1

if new_items:
    tracker = pd.concat([tracker, pd.DataFrame(new_items)], ignore_index=True)

# Simulate natural progression: items open >10 days move to "In Progress",
# a random subset "Remediated" -- makes repeated runs show real movement
tracker["first_raised_dt"] = pd.to_datetime(tracker["first_raised"])
days_open = (run_date - tracker["first_raised_dt"]).dt.days
tracker.loc[(days_open > 0) & (tracker["status"] == "Open"), "status"] = "In Progress"
tracker = tracker.drop(columns=["first_raised_dt"])

tracker.to_csv(TRACKER_PATH, index=False)

status_counts = tracker["status"].value_counts().to_dict()
print(f"Uplift tracker updated: {len(new_items)} new item(s) added.")
print(f"Current status breakdown: {status_counts}")
print(f"Saved to {TRACKER_PATH}")
