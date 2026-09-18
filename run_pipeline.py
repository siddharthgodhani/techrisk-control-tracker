"""Cross-platform runner for the Tech Risk Control Exception Tracker.

Run from anywhere with:
    python run_pipeline.py
"""
from pathlib import Path
import json
import subprocess
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
SCRIPTS = ROOT / "scripts"
OUTPUT.mkdir(parents=True, exist_ok=True)


def run_step(label: str, script_name: str) -> None:
    print(f"\n=== {label} ===")
    subprocess.run([sys.executable, str(SCRIPTS / script_name)], cwd=ROOT, check=True)


def refresh_dashboard() -> Path:
    print("\n=== 5. Refreshing dashboard ===")
    exc = pd.read_csv(OUTPUT / "exception_register.csv")
    qa = pd.read_csv(OUTPUT / "qa_check_log.csv")
    summary = pd.read_csv(OUTPUT / "run_summary.csv").iloc[0].to_dict()
    uplift = pd.read_csv(OUTPUT / "uplift_tracker.csv")

    data = {
        "summary": summary,
        "by_system": exc.groupby("system_id").size().sort_values(ascending=False).to_dict(),
        "by_type": exc.groupby("exception_type").size().to_dict(),
        "exceptions": exc.to_dict("records"),
        "qa_log": qa.to_dict("records"),
        "uplift_status": uplift["status"].value_counts().to_dict(),
    }

    (OUTPUT / "dashboard_data.json").write_text(
        json.dumps(data, indent=2, default=str), encoding="utf-8"
    )

    template_path = OUTPUT / "dashboard.html"
    html = template_path.read_text(encoding="utf-8")
    placeholder = "__DATA_JSON__"
    if placeholder not in html:
        raise RuntimeError(
            "output/dashboard.html no longer contains the __DATA_JSON__ placeholder. "
            "Restore the original template from the project zip."
        )

    live_html = html.replace(placeholder, json.dumps(data, default=str))
    live_path = OUTPUT / "dashboard_live.html"
    live_path.write_text(live_html, encoding="utf-8")
    print(f"Dashboard generated: {live_path}")
    return live_path


def main() -> None:
    print(f"Project: {ROOT}")
    run_step("1. Generating latest mock source data", "generate_mock_data.py")
    run_step("2. Reconciling, QA-checking, and flagging exceptions", "reconcile.py")
    run_step("3. Updating uplift / remediation tracker", "update_uplift_tracker.py")
    run_step("4. Generating governance pack (PDF)", "generate_governance_pack.py")
    live_path = refresh_dashboard()

    print("\n=== Pipeline complete ===")
    print(f"Dashboard:       {live_path}")
    print(f"Governance pack: {OUTPUT / 'governance_pack.pdf'}")
    print(f"Exception log:   {OUTPUT / 'exception_register.csv'}")
    print("\nOn Windows, open output\\dashboard_live.html in your browser.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(f"\nPipeline stopped because a step failed (exit code {exc.returncode}).", file=sys.stderr)
        sys.exit(exc.returncode)
    except Exception as exc:
        print(f"\nPipeline failed: {exc}", file=sys.stderr)
        sys.exit(1)
