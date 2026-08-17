"""
Vendor Management & Marketplace Onboarding API.

Covers: registration, profile management, verification workflow,
approval/rejection, activation/suspension, and listing/filtering.
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.vendor import VendorStatus
from app.schemas.vendor import (
    VendorCreate,
    VendorUpdate,
    VendorResponse,
    VendorStatusUpdate,
    VendorLogin,
)
from app.services import vendor_service
from app.services import vendor_analytics_service as va

router = APIRouter(prefix="/vendors", tags=["Vendor Management"])


@router.post("/register", response_model=VendorResponse, status_code=201)
def register_vendor(payload: VendorCreate, db: Session = Depends(get_db)):
    """Onboard a new vendor. Starts in PENDING / UNVERIFIED state."""
    return vendor_service.register_vendor(db, payload)

@router.post("/login")
def login_vendor(payload: VendorLogin, db: Session = Depends(get_db)):
    """
    Vendor Login
    """
    return vendor_service.login_vendor(db, payload)


@router.get("", response_model=List[VendorResponse])
def list_vendors(
    status_filter: Optional[VendorStatus] = Query(None, alias="status"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    return vendor_service.list_vendors(db, status_filter, skip, limit)


@router.get("/{vendor_id}", response_model=VendorResponse)
def get_vendor(vendor_id: int, db: Session = Depends(get_db)):
    return vendor_service.get_vendor(db, vendor_id)


@router.get("/{vendor_id}/analytics")
def vendor_analytics(vendor_id: int, months: int = Query(6, ge=1, le=24), db: Session = Depends(get_db)):
    """
    Single-call payload for the vendor-facing Analytics page: KPI summary,
    monthly revenue trend, top products, revenue-by-category, and
    order-status mix — all scoped to this vendor only.
    """
    return {
        "summary": va.vendor_kpis(db, vendor_id),
        "top_products": va.top_products(db, vendor_id, limit=5),
        "revenue_by_category": va.category_breakdown(db, vendor_id),
        "monthly_revenue_trend": va.monthly_revenue_trend(db, vendor_id, months=months),
        "order_status_breakdown": va.order_status_breakdown(db, vendor_id),
    }


@router.get("/{vendor_id}/analytics/export")
def export_vendor_analytics_report(vendor_id: int, months: int = Query(6, ge=1, le=24), db: Session = Depends(get_db)):
    """Downloads this vendor's analytics report as a CSV file."""
    try:
        path = va.export_vendor_report_csv(db, vendor_id, months=months)
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Failed to export vendor report: {exc}")
    return FileResponse(
        path,
        media_type="text/csv",
        filename=f"vendor_{vendor_id}_analytics_report.csv",
    )


@router.put("/{vendor_id}", response_model=VendorResponse)
def update_vendor(vendor_id: int, payload: VendorUpdate, db: Session = Depends(get_db)):
    """Update vendor profile details (business info, contact, commission)."""
    return vendor_service.update_vendor(db, vendor_id, payload)


@router.post("/{vendor_id}/submit-for-verification", response_model=VendorResponse)
def submit_for_verification(vendor_id: int, db: Session = Depends(get_db)):
    return vendor_service.submit_for_verification(db, vendor_id)


@router.patch("/{vendor_id}/approve", response_model=VendorResponse)
def approve_vendor(vendor_id: int, payload: VendorStatusUpdate, db: Session = Depends(get_db)):
    """Approve onboarding — moves vendor to VERIFIED / ACTIVE."""
    return vendor_service.approve_vendor(db, vendor_id, payload.reason)


@router.patch("/{vendor_id}/reject", response_model=VendorResponse)
def reject_vendor(vendor_id: int, payload: VendorStatusUpdate, db: Session = Depends(get_db)):
    """Reject onboarding application."""
    return vendor_service.reject_vendor(db, vendor_id, payload.reason)


@router.patch("/{vendor_id}/suspend", response_model=VendorResponse)
def suspend_vendor(vendor_id: int, payload: VendorStatusUpdate, db: Session = Depends(get_db)):
    """Suspend an active vendor (policy violation, poor performance, etc.)."""
    return vendor_service.suspend_vendor(db, vendor_id, payload.reason)


@router.patch("/{vendor_id}/reactivate", response_model=VendorResponse)
def reactivate_vendor(vendor_id: int, db: Session = Depends(get_db)):
    """Reactivate a previously suspended vendor."""
    return vendor_service.reactivate_vendor(db, vendor_id)


@router.delete("/{vendor_id}", status_code=204)
def delete_vendor(vendor_id: int, db: Session = Depends(get_db)):
    vendor_service.delete_vendor(db, vendor_id)
