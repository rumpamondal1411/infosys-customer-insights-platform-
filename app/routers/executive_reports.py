"""
Milestone 4 — Executive Reporting & Advanced BI API.

Thin REST layer over executive_report_service. Lives under the same
/api/v1 prefix as Milestone 3's analytics_api.py, as a separate router so
it can be documented, tested, and versioned independently.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import executive_report_service

router = APIRouter(prefix="/api/v1/executive", tags=["Milestone 4 — Executive Reporting"])


@router.get("/summary")
def get_executive_summary(
    period_days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """One-call KPI roll-up for the executive dashboard."""
    try:
        return executive_report_service.executive_summary(db, period_days=period_days)
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Failed to build executive summary: {exc}")


@router.get("/kpi-trend")
def get_kpi_trend(
    months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
):
    """Monthly revenue/order trend for the executive line chart."""
    return executive_report_service.kpi_trend(db, months=months)


@router.get("/export")
def export_executive_report(
    period_days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Generates and downloads a multi-sheet executive .xlsx workbook."""
    try:
        path = executive_report_service.export_executive_workbook(db, period_days=period_days)
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Failed to export executive report: {exc}")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=path.split("/")[-1],
    )
