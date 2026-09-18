"""
Governance Pack Generator

Produces a 1-page PDF summary suitable for a governance/committee pack:
  - draft narrative (auto-generated from run stats, meant to be
    reviewed/edited by an analyst before submission -- not a final
    "AI-written" doc, exactly like the JD's "draft narrative development")
  - QA attestation (proves quality checks ran before this was produced)
  - table of top exceptions with evidence references for traceability

Must NOT run if QA checks failed catastrophically -- in real life this is
"ensuring all outputs are quality-checked and reviewed before use in
governance." Here we still generate the pack even with data-quality
findings, but we surface them prominently rather than hiding them --
that's the actual expectation: escalate, don't suppress.
"""
import pandas as pd
from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

summary = pd.read_csv(OUT_DIR / "run_summary.csv").iloc[0]
qa_log = pd.read_csv(OUT_DIR / "qa_check_log.csv")
exceptions = pd.read_csv(OUT_DIR / "exception_register.csv")

qa_failed = qa_log[qa_log["result"] == "FAIL"]

# --- Draft narrative (auto-generated, intended for analyst review before use) ---
narrative = (
    f"This week's technology risk intelligence cycle reviewed {summary['total_systems_reviewed']} "
    f"in-scope systems across vulnerability management, patch compliance, and access recertification "
    f"data sources. {summary['total_exceptions']} exceptions were identified against defined SLA "
    f"thresholds, comprising {summary['vuln_sla_breaches']} vulnerability SLA breaches, "
    f"{summary['patch_sla_breaches']} patch compliance breaches, and {summary['access_recert_overdue']} "
    f"overdue access recertifications. "
)
if summary["critical_vuln_open"] > 0:
    narrative += (
        f"Of note, {summary['critical_vuln_open']} open critical-severity vulnerability finding(s) "
        f"remain unremediated and are flagged for priority follow-up with control owners. "
    )
if summary["unreconciled_records"] > 0:
    narrative += (
        f"{summary['unreconciled_records']} record(s) could not be reconciled to the master system "
        f"list during data quality checks and have been excluded from this analysis pending "
        f"source-system clarification; see the unreconciled records log. "
    )
narrative += (
    f"All {summary['qa_checks_run']} data quality checks were completed prior to distribution"
    + (f", of which {summary['qa_checks_failed']} raised findings requiring follow-up "
       f"(detailed below)." if summary["qa_checks_failed"] > 0 else " with no findings.")
)

# --- Build PDF ---
styles = getSampleStyleSheet()
title_style = ParagraphStyle("TitleStyle", parent=styles["Title"], fontSize=16, spaceAfter=2)
meta_style = ParagraphStyle("MetaStyle", parent=styles["Normal"], fontSize=9, textColor=colors.grey)
h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=11, spaceBefore=10, spaceAfter=4)
body = ParagraphStyle("BodyText2", parent=styles["Normal"], fontSize=9.5, leading=13)
small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, textColor=colors.grey)
cell_text = ParagraphStyle("CellText", parent=styles["Normal"], fontSize=8, textColor=colors.black, leading=10)

doc = SimpleDocTemplate(
    str(OUT_DIR / "governance_pack.pdf"), pagesize=A4,
    topMargin=1.4*cm, bottomMargin=1.2*cm, leftMargin=1.6*cm, rightMargin=1.6*cm
)
story = []

story.append(Paragraph("Technology Risk Intelligence -- Weekly Exception Summary", title_style))
story.append(Paragraph(
    f"Run date: {summary['run_date']}  |  Status: DRAFT -- for analyst/manager review prior to governance submission",
    meta_style
))
story.append(Spacer(1, 6))
story.append(HRFlowable(width="100%", color=colors.HexColor("#333333")))

story.append(Paragraph("Summary Narrative (auto-drafted -- review before submission)", h2))
story.append(Paragraph(narrative, body))

story.append(Paragraph("Key Metrics", h2))
metrics_data = [
    ["Systems Reviewed", "Total Exceptions", "Vuln SLA Breaches", "Patch SLA Breaches", "Access Overdue"],
    [
        str(summary["total_systems_reviewed"]), str(summary["total_exceptions"]),
        str(summary["vuln_sla_breaches"]), str(summary["patch_sla_breaches"]),
        str(summary["access_recert_overdue"])
    ],
]
mt = Table(metrics_data, colWidths=[3.2*cm]*5)
mt.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ("TOPPADDING", (0, 0), (-1, -1), 5),
]))
story.append(mt)

story.append(Paragraph("Data Quality Attestation", h2))
qa_text = (
    f"{summary['qa_checks_run']} quality checks executed prior to distribution "
    f"({summary['qa_checks_run'] - summary['qa_checks_failed']} passed, "
    f"{summary['qa_checks_failed']} raised findings)."
)
story.append(Paragraph(qa_text, body))
if len(qa_failed):
    qa_table_data = [["Check", "Finding"]] + [
        [Paragraph(str(c), cell_text), Paragraph(str(d), cell_text)]
        for c, d in qa_failed[["check", "detail"]].values.tolist()
    ]
    qt = Table(qa_table_data, colWidths=[5*cm, 11.5*cm])
    qt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8a1f1f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(Spacer(1, 4))
    story.append(qt)

story.append(Paragraph("Top Exceptions (traceable to source evidence)", h2))
top = exceptions.sort_values("system_id").head(10)
exc_table_data = [["System", "Exception Type", "Detail", "Evidence Ref"]]
for _, r in top.iterrows():
    exc_table_data.append([
        r["system_id"], r["exception_type"],
        Paragraph(str(r["exception_detail"]), cell_text),
        r["evidence_ref"]
    ])
et = Table(exc_table_data, colWidths=[2.6*cm, 4*cm, 7*cm, 2.9*cm], repeatRows=1)
et.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTSIZE", (0, 0), (-1, -1), 8),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
]))
story.append(et)

story.append(Spacer(1, 8))
story.append(Paragraph(
    f"Full exception register ({len(exceptions)} rows) and QA log available in accompanying CSV files "
    f"for evidence traceability. Generated automatically by the exception tracking pipeline; "
    f"narrative and prioritisation to be reviewed and finalised by analyst prior to distribution.",
    small
))

doc.build(story)
print(f"Governance pack generated: {OUT_DIR}/governance_pack.pdf")
