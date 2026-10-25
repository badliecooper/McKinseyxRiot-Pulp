"""Weekly Report API endpoints for RIOT RADAR."""

import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from services.weekly_report import (
    get_weekly_report_preview,
    generate_weekly_pdf_report,
    REPORTS_DIR,
)

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/weekly/preview")
def get_report_preview(week: str = Query("2026-W18")):
    """Retrieve structured JSON summary preview of the weekly report."""
    return get_weekly_report_preview(week_label=week)


@router.post("/weekly/generate")
def post_generate_report(week: str = Query("2026-W18")):
    """Trigger Python Matplotlib + ReportLab generation of 3-page PDF report."""
    try:
        pdf_path = generate_weekly_pdf_report(week_label=week)
        filename = os.path.basename(pdf_path)
        return {
            "status": "SUCCESS",
            "filename": filename,
            "download_url": f"/api/reports/download/{filename}",
            "message": "Weekly intelligence report PDF generated successfully (3 pages max).",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report PDF: {str(e)}")


@router.get("/download/{filename}")
def download_report_pdf(filename: str):
    """Download the generated weekly intelligence PDF report."""
    file_path = REPORTS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Requested report PDF not found.")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/pdf",
    )
