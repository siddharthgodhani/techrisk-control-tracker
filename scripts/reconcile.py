"""
Tech Risk Control Exception Tracker -- Reconciliation Engine

Mirrors the JD's core repeatable routine:
  1. Extract data from approved sources
  2. Clean + reconcile across sources (catch mismatches / bad joins)
  3. Run quality checks BEFORE anything is used downstream
  4. Flag exceptions against defined SLAs/thresholds
  5. Log outcomes with full traceability back to source row

Run standalone: python3 reconcile.py
Outputs land in the project output/ folder.
"""
import pandas as pd
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUT_DIR = PROJECT_ROOT / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MASTER_SYSTEMS = [
    "CORE-BANK-01", "CORE-BANK-02", "PAYMENTS-GW", "SANCTIONS-SCR",
    "CRM-RETAIL", "DATA-LAKE-01", "AUTH-SVC", "API-GATEWAY",
    "MOBILE-BE", "REPORTING-DW"
]

run_ts = datetime.now()
qa_log = []  # every quality check result gets logged here, pass or fail


def log_qa(check_name, passed, detail):
    qa_log.append({
        "check": check_name,
        "result": "PASS" if passed else "FAIL",
        "detail": detail,
    })
    flag = "OK" if passed else "!!"
    print(f"  [{flag}] {check_name}: {detail}")


# =================================================================
# STEP 1: EXTRACT
# =================================================================
print("STEP 1: Extracting from approved sources...")
vuln = pd.read_csv(DATA_DIR / "vulnerability_scan.csv")
patch = pd.read_csv(DATA_DIR / "patch_compliance.csv")
access = pd.read_csv(DATA_DIR / "access_review.csv")
print(f"  Loaded vulnerability_scan.csv ({len(vuln)} rows)")
print(f"  Loaded patch_compliance.csv ({len(patch)} rows)")
print(f"  Loaded access_review.csv ({len(access)} rows)")

# =================================================================
# STEP 2: CLEAN + RECONCILE
# =================================================================
print("\nSTEP 2: Cleaning and reconciling across sources...")

# --- Reconciliation issue #1: inconsistent system_id casing across sources
access["system_id_raw"] = access["system_id"]
access["system_id"] = access["system_id"].str.upper().str.strip()
casing_fixed = (access["system_id_raw"] != access["system_id"]).sum()
log_qa(
    "system_id normalisation",
    True,
    f"{casing_fixed} row(s) had inconsistent system_id casing/whitespace -- normalised to master format"
)

# --- Reconciliation issue #2: duplicate rows
dupe_mask = access.duplicated(subset=["access_id"], keep="first")
n_dupes = dupe_mask.sum()
access_clean = access[~dupe_mask].copy()
log_qa(
    "duplicate row check (access_review)",
    n_dupes == 0,
    f"{n_dupes} duplicate access_id row(s) found and removed" if n_dupes else "no duplicates found"
)

# --- Reconciliation issue #3: orphaned references (system not in master list)
orphans = access_clean[~access_clean["system_id"].isin(MASTER_SYSTEMS)]
log_qa(
    "orphan system_id check (access_review vs master list)",
    len(orphans) == 0,
    f"{len(orphans)} row(s) reference a system_id not in the master system list: "
    f"{orphans['system_id'].unique().tolist()}" if len(orphans) else "all system_id values reconcile to master list"
)
# Orphans are excluded from downstream analysis but logged separately for follow-up -- never silently dropped
if len(orphans):
    orphans.to_csv(OUT_DIR / "_unreconciled_records.csv", index=False)
access_clean = access_clean[access_clean["system_id"].isin(MASTER_SYSTEMS)]

# --- Null / completeness checks across all three sources
for name, df, required_cols in [
    ("vulnerability_scan", vuln, ["finding_id", "system_id", "severity", "sla_due_date"]),
    ("patch_compliance", patch, ["system_id", "last_patched_date"]),
    ("access_review", access_clean, ["access_id", "system_id", "status"]),
]:
    n_nulls = df[required_cols].isnull().sum().sum()
    log_qa(
        f"completeness check ({name})",
        n_nulls == 0,
        f"{n_nulls} null value(s) found in required fields" if n_nulls else "no nulls in required fields"
    )

# =================================================================
# STEP 3: EXCEPTION FLAGGING (against defined thresholds/SLAs)
# =================================================================
print("\nSTEP 3: Flagging exceptions against defined SLAs...")

today = pd.Timestamp(run_ts.date())

# -- Vulnerability exceptions: open findings past their SLA due date
vuln["sla_due_date"] = pd.to_datetime(vuln["sla_due_date"])
vuln["found_date"] = pd.to_datetime(vuln["found_date"])
vuln_exceptions = vuln[(vuln["status"] == "Open") & (vuln["sla_due_date"] < today)].copy()
vuln_exceptions["exception_type"] = "Vulnerability SLA Breach"
vuln_exceptions["exception_detail"] = (
    "Open " + vuln_exceptions["severity"] + " finding overdue by "
    + (today - vuln_exceptions["sla_due_date"]).dt.days.astype(str) + " days"
)
vuln_exceptions["evidence_ref"] = vuln_exceptions["finding_id"]

# -- Patch exceptions: systems past their patch SLA
patch["last_patched_date"] = pd.to_datetime(patch["last_patched_date"])
patch["days_since_patch"] = (today - patch["last_patched_date"]).dt.days
patch_exceptions = patch[patch["days_since_patch"] > patch["patch_sla_days"]].copy()
patch_exceptions["exception_type"] = "Patch SLA Breach"
patch_exceptions["exception_detail"] = (
    "Not patched for " + patch_exceptions["days_since_patch"].astype(str)
    + " days (SLA: " + patch_exceptions["patch_sla_days"].astype(str) + " days)"
)
patch_exceptions["evidence_ref"] = "PATCH-" + patch_exceptions["system_id"]

# -- Access exceptions: overdue recertifications
access_clean["last_recert_date"] = pd.to_datetime(access_clean["last_recert_date"])
access_clean["days_since_recert"] = (today - access_clean["last_recert_date"]).dt.days
access_exceptions = access_clean[
    (access_clean["status"] == "Overdue") |
    (access_clean["days_since_recert"] > access_clean["recert_sla_days"])
].copy()
access_exceptions["exception_type"] = "Access Recertification Overdue"
access_exceptions["exception_detail"] = (
    access_exceptions["user_role"] + " access not recertified for "
    + access_exceptions["days_since_recert"].astype(str) + " days"
)
access_exceptions["evidence_ref"] = access_exceptions["access_id"]

print(f"  Vulnerability SLA breaches : {len(vuln_exceptions)}")
print(f"  Patch SLA breaches         : {len(patch_exceptions)}")
print(f"  Access recert overdue      : {len(access_exceptions)}")

# =================================================================
# STEP 4: CONSOLIDATE MASTER EXCEPTION REGISTER (traceable to evidence)
# =================================================================
print("\nSTEP 4: Building consolidated exception register...")

master_exceptions = pd.concat([
    vuln_exceptions[["system_id", "exception_type", "severity", "exception_detail", "evidence_ref", "control_owner"]]
        .rename(columns={"severity": "severity_or_role"}),
    patch_exceptions[["system_id", "exception_type", "exception_detail", "evidence_ref", "control_owner"]]
        .assign(severity_or_role="N/A"),
    access_exceptions[["system_id", "exception_type", "exception_detail", "evidence_ref"]]
        .assign(severity_or_role=access_exceptions["user_role"], control_owner="IAM Team"),
], ignore_index=True)

master_exceptions.insert(0, "run_date", run_ts.strftime("%Y-%m-%d"))
master_exceptions.to_csv(OUT_DIR / "exception_register.csv", index=False)

# =================================================================
# STEP 5: QA LOG (evidence that checks ran before distribution)
# =================================================================
qa_df = pd.DataFrame(qa_log)
qa_df.insert(0, "run_date", run_ts.strftime("%Y-%m-%d"))
qa_df.insert(1, "run_time", run_ts.strftime("%H:%M:%S"))
qa_df.to_csv(OUT_DIR / "qa_check_log.csv", index=False)

any_fail = (qa_df["result"] == "FAIL").any()

# =================================================================
# STEP 6: SUMMARY STATS (feeds the dashboard + governance pack)
# =================================================================
summary = {
    "run_date": run_ts.strftime("%Y-%m-%d %H:%M"),
    "total_systems_reviewed": len(MASTER_SYSTEMS),
    "total_exceptions": len(master_exceptions),
    "vuln_sla_breaches": len(vuln_exceptions),
    "patch_sla_breaches": len(patch_exceptions),
    "access_recert_overdue": len(access_exceptions),
    "qa_checks_run": len(qa_df),
    "qa_checks_failed": int((qa_df["result"] == "FAIL").sum()),
    "unreconciled_records": len(orphans),
    "critical_vuln_open": int((vuln[(vuln.status == "Open")]["severity"] == "Critical").sum()),
}
pd.DataFrame([summary]).to_csv(OUT_DIR / "run_summary.csv", index=False)

print("\nSTEP 5-6: QA log and run summary written.")
print(f"\n{'='*60}")
print(f"PIPELINE COMPLETE -- {run_ts.strftime('%Y-%m-%d %H:%M')}")
print(f"{'='*60}")
print(f"Total exceptions logged : {summary['total_exceptions']}")
print(f"QA checks run / failed  : {summary['qa_checks_run']} / {summary['qa_checks_failed']}")
print(f"Unreconciled records    : {summary['unreconciled_records']} (see _unreconciled_records.csv)")
print(f"\nOutputs written to {OUT_DIR}/")
print("  - exception_register.csv   (traceable exception log)")
print("  - qa_check_log.csv         (evidence checks ran before use)")
print("  - run_summary.csv          (feeds dashboard + governance pack)")

if any_fail:
    print("\nNOTE: one or more QA checks failed on data quality (expected -- ")
    print("this demonstrates the pipeline catching bad data rather than silently passing it through).")
