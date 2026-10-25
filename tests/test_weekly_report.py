"""Unit and integration tests for Weekly Supply Chain Intelligence PDF Report."""

import re
from pathlib import Path
import pytest
from reportlab.pdfbase import pdfmetrics

from services.weekly_report import (
    generate_weekly_pdf_report,
    get_weekly_report_preview,
    REPORTS_DIR,
)
from services.report_layout import (
    ReportDataAdapter,
    verify_report_consistency,
)


def test_weekly_report_exact_three_pages():
    """Verify that the generated weekly PDF intelligence report has exactly 3 pages."""
    pdf_path_str = generate_weekly_pdf_report("2026-W18")
    pdf_path = Path(pdf_path_str)
    assert pdf_path.exists(), "PDF report file was not created"

    # Count pages via PDF trailer dictionary
    raw_data = pdf_path.read_bytes()
    page_matches = re.findall(rb"/Type\s*/Page\b", raw_data)
    assert len(page_matches) == 3, f"Expected exactly 3 pages, but found {len(page_matches)}"


def test_dejavu_fonts_registered():
    """Verify DejaVuSans is registered in ReportLab for native ₹ rendering."""
    registered = pdfmetrics.getRegisteredFontNames()
    assert "DejaVuSans" in registered
    assert "DejaVuSans-Bold" in registered


def test_internal_metric_consistency_passes():
    """Verify single source of truth across header, KPI strip, heatmap, and tables."""
    adapter = ReportDataAdapter("2026-W18")
    data = adapter.get_consolidated_report_data()
    # verify_report_consistency runs inside get_consolidated_report_data and must return True
    assert verify_report_consistency(data) is True

    # Validate specific cross-page matches
    assert data["header"]["depots_at_risk_count"] == data["kpis"]["depots_at_risk"]["this_val"]
    assert data["header"]["depots_at_risk_count"] == data["page2"]["heatmap_at_risk_depots_count"]
    assert data["kpis"]["projected_shortage"]["this_val"] == data["page2"]["total_shortage_bottles"]
    assert data["kpis"]["forecast_wape"]["this_val"] == data["page3"]["scorecard_wape_corrected"]
    assert data["kpis"]["feasible_transfers"]["this_val"] == data["page1"]["feasible_transfers_count"]


def test_internal_consistency_fails_loudly_on_mismatch():
    """Verify that verify_report_consistency raises ValueError if metrics diverge."""
    adapter = ReportDataAdapter("2026-W18")
    data = adapter.get_consolidated_report_data()

    # Tamper with header depots_at_risk_count
    corrupted_data = dict(data)
    corrupted_data["header"] = dict(data["header"])
    corrupted_data["header"]["depots_at_risk_count"] = 999

    with pytest.raises(ValueError, match="Internal Consistency Violation"):
        verify_report_consistency(corrupted_data)


def test_case_facts_vocabulary_compliance():
    """Verify that forbidden non-case regions (Northeast, Mumbai, Delhi) are strictly absent."""
    preview = get_weekly_report_preview("2026-W18")
    summary = preview["executive_summary"].lower()
    assert "northeast" not in summary
    assert "mumbai" not in summary
    assert "delhi" not in summary
    assert "hill-region cooperative" in summary


def test_proposed_actions_governance_labeling():
    """Verify all network actions are explicitly marked as proposed / pending approval."""
    adapter = ReportDataAdapter("2026-W18")
    data = adapter.get_consolidated_report_data()
    for action in data["top_actions"]:
        assert "PENDING APPROVAL" in action["status"]
