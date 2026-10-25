"""Weekly Supply Chain Intelligence Report Service for RIOT RADAR.

Exposes:
1. get_weekly_report_preview: JSON summary preview for Control Tower display.
2. generate_weekly_pdf_report: Downloadable publication-grade PDF report (strict maximum 3 pages)
   using ReportLab and Matplotlib with DejaVuSans typography.
Uses Asia/Kolkata timezone and half-open intervals [week_start, next_week_start).
"""

import os
import io
import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from services.csv_store import DATA_DIR
from services.report_layout import (
    ReportDataAdapter,
    build_weekly_pdf_pages,
    verify_report_consistency,
)

REPORTS_DIR = DATA_DIR.parent / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def get_weekly_report_preview(week_label: str = "2026-W18") -> Dict[str, Any]:
    """Generate structured JSON summary preview for the weekly intelligence report.
    
    Composed directly via ReportDataAdapter ensuring identical metric values with the PDF.
    """
    adapter = ReportDataAdapter(week_label=week_label)
    data = adapter.get_consolidated_report_data()

    # Formulate executive summary using only strict case facts
    exec_summary = (
        f"Week 18 operations experienced a 4.1x demand surge in PR-DP across Quick Commerce channels, "
        f"compounded by a hill-region cooperative road outage disrupting single-source passionfruit pulp. "
        f"RIOT RADAR demand sensing flagged velocity spikes {data['kpis']['detection_lead_time']['this_fmt']} earlier than monthly spreadsheet consolidations. "
        f"{data['page1']['feasible_transfers_count']} inter-depot rebalancing transfers are proposed to mitigate allocation gaps."
    )

    return {
        "report_week": week_label,
        "reporting_period": data["header"]["reporting_period"],
        "generation_time": data["header"]["generated_time"],
        "timezone": "Asia/Kolkata",
        "overall_rag_status": data["header"]["overall_rag"],
        "rag_reason": data["header"]["rag_reason"],
        "key_metrics": {
            "depots_at_risk": data["kpis"]["depots_at_risk"]["this_fmt"],
            "projected_shortage_bottles": data["kpis"]["projected_shortage"]["this_val"],
            "riot_radar_wape_pct": data["kpis"]["forecast_wape"]["this_val"],
            "naive_benchmark_wape_pct": data["page3"]["wape_naive"],
            "forecast_bias_pct": data["page3"]["forecast_bias"],
            "transfer_proposals_count": data["kpis"]["feasible_transfers"]["this_val"],
            "detection_lead_time_days": data["kpis"]["detection_lead_time"]["this_val"],
            "pending_decisions_count": data["kpis"]["pending_decisions"]["this_val"],
        },
        "kpi_deltas": data["kpis"],
        "takeaways": data["takeaways"],
        "executive_summary": exec_summary,
        "data_honesty_note": (
            "Note: Lot-level shelf-life distribution and ground-truth series are synthetic demo constructs "
            "calibrated to Pulp Riot Juice Co. case constraints."
        ),
    }


def generate_weekly_pdf_report(week_label: str = "2026-W18") -> str:
    """Generate strict 3-page publication-grade PDF report using ReportLab and Matplotlib.
    
    Returns the absolute path to the generated PDF.
    """
    pdf_filename = f"weekly_intelligence_report_{week_label}.pdf"
    pdf_path = REPORTS_DIR / pdf_filename

    build_weekly_pdf_pages(week_label=week_label, output_path=pdf_path)
    return str(pdf_path)
