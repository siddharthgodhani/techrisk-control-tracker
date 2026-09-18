"""
Generates mock 'source system' extracts to simulate the approved data sources
a Technology Risk Intelligence analyst would pull from each cycle:

  1. vulnerability_scan.csv   -> simulates a vuln management tool export
  2. patch_compliance.csv     -> simulates a patch management tool export
  3. access_review.csv        -> simulates an IAM/access recertification export

Re-running this script simulates a new week's data drop landing from the
approved sources -- this is what "extract data from approved sources" means
in the JD.
"""
import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)
np.random.seed(42)

SYSTEMS = [
    "CORE-BANK-01", "CORE-BANK-02", "PAYMENTS-GW", "SANCTIONS-SCR",
    "CRM-RETAIL", "DATA-LAKE-01", "AUTH-SVC", "API-GATEWAY",
    "MOBILE-BE", "REPORTING-DW"
]

OWNERS = ["A. Mehta", "R. Fernandes", "S. Iyer", "P. Rao", "K. Nair"]
SEVERITIES = ["Critical", "High", "Medium", "Low"]
SEV_WEIGHTS = [0.08, 0.22, 0.40, 0.30]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

today = datetime.today()

# ---------------------------------------------------------------
# 1. Vulnerability scan export
# ---------------------------------------------------------------
vuln_rows = []
vid = 1000
for system in SYSTEMS:
    n_findings = random.randint(1, 5)
    for _ in range(n_findings):
        found_date = today - timedelta(days=random.randint(5, 120))
        sev = np.random.choice(SEVERITIES, p=SEV_WEIGHTS)
        sla_days = {"Critical": 14, "High": 30, "Medium": 60, "Low": 90}[sev]
        due_date = found_date + timedelta(days=sla_days)
        vuln_rows.append({
            "finding_id": f"VULN-{vid}",
            "system_id": system,
            "severity": sev,
            "description": f"{sev}-severity finding on {system}",
            "found_date": found_date.strftime("%Y-%m-%d"),
            "sla_due_date": due_date.strftime("%Y-%m-%d"),
            "status": np.random.choice(["Open", "Remediated"], p=[0.55, 0.45]),
            "control_owner": random.choice(OWNERS),
        })
        vid += 1

pd.DataFrame(vuln_rows).to_csv(DATA_DIR / "vulnerability_scan.csv", index=False)

# ---------------------------------------------------------------
# 2. Patch compliance export
# ---------------------------------------------------------------
patch_rows = []
for system in SYSTEMS:
    last_patch = today - timedelta(days=random.randint(2, 100))
    patch_rows.append({
        "system_id": system,
        "os_patch_level": f"{random.randint(2024,2026)}.{random.randint(1,12):02d}",
        "last_patched_date": last_patch.strftime("%Y-%m-%d"),
        "days_since_patch": (today - last_patch).days,
        "patch_sla_days": 45,
        "control_owner": random.choice(OWNERS),
    })

pd.DataFrame(patch_rows).to_csv(DATA_DIR / "patch_compliance.csv", index=False)

# ---------------------------------------------------------------
# 3. Access review export (deliberately includes a few dirty/reconciliation issues)
# ---------------------------------------------------------------
access_rows = []
aid = 1
for system in SYSTEMS:
    n_users = random.randint(3, 6)
    for _ in range(n_users):
        review_date = today - timedelta(days=random.randint(10, 200))
        access_rows.append({
            "access_id": f"ACC-{aid:04d}",
            "system_id": system if random.random() > 0.05 else system.lower(),  # inject casing mismatch
            "user_role": random.choice(["Admin", "Standard User", "Service Account", "Read-Only"]),
            "last_recert_date": review_date.strftime("%Y-%m-%d"),
            "recert_sla_days": 180,
            "status": np.random.choice(["Certified", "Pending Recert", "Overdue"], p=[0.6, 0.25, 0.15]),
        })
        aid += 1

# inject a couple of rows referencing a system NOT in the master list (data quality issue to catch)
access_rows.append({
    "access_id": f"ACC-{aid:04d}", "system_id": "LEGACY-FTP-01",
    "user_role": "Admin", "last_recert_date": "2025-01-15",
    "recert_sla_days": 180, "status": "Overdue"
})
# inject a duplicate row (data quality issue to catch)
access_rows.append(access_rows[0].copy())

pd.DataFrame(access_rows).to_csv(DATA_DIR / "access_review.csv", index=False)

print("Mock source data generated:")
print(f"  vulnerability_scan.csv : {len(vuln_rows)} rows")
print(f"  patch_compliance.csv   : {len(patch_rows)} rows")
print(f"  access_review.csv      : {len(access_rows)} rows")
