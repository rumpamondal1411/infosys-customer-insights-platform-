from typing import Optional
from pathlib import Path
import subprocess
import sys
import time
import re
from datetime import datetime

from fastapi import APIRouter, Query, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates

from app.database import get_db
from app.schemas.admin import AdminLogin
from app.services import admin_service, demo_data_service

from app.models.vendor import Vendor
from app.models.product import Product
from app.models.customer import Customer
from app.models.transaction import Transaction


router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)

templates = Jinja2Templates(directory="app/templates")


# =========================================================
# ADMIN LOGIN
# =========================================================

@router.post("/login")
def admin_login(payload: AdminLogin):
    return admin_service.login(payload)


# =========================================================
# SEED CUSTOMERS
# =========================================================

@router.post("/seed-customers")
def seed_customers(
    count: int = Query(
        30,
        ge=1,
        le=200,
        description="How many customers to add"
    ),
    db: Session = Depends(get_db),
):
    return demo_data_service.add_demo_customers(db, count)


# =========================================================
# ADMIN SYSTEM HEALTH PAGE
# =========================================================

@router.get("/system-health")
def system_health(request: Request):
    return templates.TemplateResponse(
        "system_health.html",
        {
            "request": request
        }
    )


# =========================================================
# SYSTEM HEALTH DATA
# =========================================================

@router.get("/system-health-data")
def system_health_data(
    db: Session = Depends(get_db)
):

    # -----------------------------------------------------
    # APPLICATION HEALTH
    # -----------------------------------------------------

    application_start = time.perf_counter()

    try:
        probe_start = time.perf_counter()

        # FastAPI reached this endpoint successfully
        probe_latency = round(
            (time.perf_counter() - probe_start) * 1000,
            2
        )

        ping_start = time.perf_counter()

        # Simple application-level operation
        _ = 1 + 1

        ping_latency = round(
            (time.perf_counter() - ping_start) * 1000,
            2
        )

        application_status = "Healthy"

    except Exception:
        probe_latency = 0
        ping_latency = 0
        application_status = "Unhealthy"

    application_latency = round(
        (time.perf_counter() - application_start) * 1000,
        2
    )


    # -----------------------------------------------------
    # DATABASE HEALTH
    # -----------------------------------------------------

    db_start = time.perf_counter()

    try:
        db.execute(text("SELECT 1"))

        db_latency = round(
            (time.perf_counter() - db_start) * 1000,
            2
        )

        db_status = "Healthy"

    except Exception:
        db_latency = round(
            (time.perf_counter() - db_start) * 1000,
            2
        )

        db_status = "Unhealthy"


    # -----------------------------------------------------
    # PLATFORM STATISTICS
    # -----------------------------------------------------

    try:
        vendors_count = db.query(Vendor).count()
    except Exception:
        vendors_count = 0

    try:
        products_count = db.query(Product).count()
    except Exception:
        products_count = 0

    try:
        customers_count = db.query(Customer).count()
    except Exception:
        customers_count = 0

    try:
        transactions_count = db.query(Transaction).count()
    except Exception:
        transactions_count = 0


    # -----------------------------------------------------
    # ANALYTICS HEALTH
    # -----------------------------------------------------

    analytics_start = time.perf_counter()

    try:

        # Real database query used as analytics health check
        db.query(Product).count()

        analytics_latency = round(
            (time.perf_counter() - analytics_start) * 1000,
            2
        )

        analytics_status = "Healthy"

    except Exception:

        analytics_latency = round(
            (time.perf_counter() - analytics_start) * 1000,
            2
        )

        analytics_status = "Unhealthy"


    # -----------------------------------------------------
    # CUSTOMER & ORDERS HEALTH
    # -----------------------------------------------------

    customer_start = time.perf_counter()

    try:

        db.query(Customer).count()
        db.query(Transaction).count()

        customer_latency = round(
            (time.perf_counter() - customer_start) * 1000,
            2
        )

        customer_status = "Healthy"

    except Exception:

        customer_latency = round(
            (time.perf_counter() - customer_start) * 1000,
            2
        )

        customer_status = "Unhealthy"


    # -----------------------------------------------------
    # ML / FORECASTING HEALTH
    # -----------------------------------------------------

    ml_start = time.perf_counter()

    try:

        # Check that required ML environment is available.
        # No model training is performed here.
        import pandas
        import numpy

        ml_latency = round(
            (time.perf_counter() - ml_start) * 1000,
            2
        )

        ml_status = "Healthy"

    except Exception:

        ml_latency = round(
            (time.perf_counter() - ml_start) * 1000,
            2
        )

        ml_status = "Unhealthy"


    # -----------------------------------------------------
    # PYTEST
    # -----------------------------------------------------

    pytest_result = run_pytest()


    # -----------------------------------------------------
    # OVERALL SYSTEM STATUS
    # -----------------------------------------------------

    all_services = [
        application_status,
        db_status,
        analytics_status,
        customer_status,
        ml_status,
    ]

    overall_status = (
        "Healthy"
        if all(service_status == "Healthy"
               for service_status in all_services)
        else "Unhealthy"
    )


    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return {
        "timestamp": datetime.utcnow().isoformat(),

        "application": {
            "status": application_status,
            "uptime": "Running",
            "probe_latency_ms": probe_latency,
            "ping_latency_ms": ping_latency,
            "total_latency_ms": application_latency,
        },

        "database": {
            "status": db_status,
            "uptime": "Connected",
            "query_latency_ms": db_latency,
        },

        "analytics": {
            "status": analytics_status,
            "uptime": "Available",
            "processing_latency_ms": analytics_latency,
        },

        "customer_orders": {
            "status": customer_status,
            "uptime": "Available",
            "response_latency_ms": customer_latency,
        },

        "ml": {
            "status": ml_status,
            "uptime": "Available",
            "processing_latency_ms": ml_latency,
        },

        "statistics": {
            "vendors": vendors_count,
            "products": products_count,
            "customers": customers_count,
            "transactions": transactions_count,
        },

        "tests": pytest_result,

        "overall": {
            "status": overall_status
        }
    }


# =========================================================
# PYTEST RUNNER
# =========================================================

def run_pytest():

    # Project root:
    # shopsense/
    project_root = Path(__file__).resolve().parents[2]

    start = time.perf_counter()

    try:

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "--tb=no",
                "-q"
            ],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=120
        )

        duration_ms = round(
            (time.perf_counter() - start) * 1000,
            2
        )

        output = (
            (result.stdout or "")
            + "\n"
            + (result.stderr or "")
        )

        # -------------------------------------------------
        # Parse pytest summary
        # -------------------------------------------------

        passed_match = re.search(
            r"(\d+)\s+passed",
            output
        )

        failed_match = re.search(
            r"(\d+)\s+failed",
            output
        )

        skipped_match = re.search(
            r"(\d+)\s+skipped",
            output
        )

        error_match = re.search(
            r"(\d+)\s+errors?",
            output
        )

        passed = (
            int(passed_match.group(1))
            if passed_match
            else 0
        )

        failed = (
            int(failed_match.group(1))
            if failed_match
            else 0
        )

        skipped = (
            int(skipped_match.group(1))
            if skipped_match
            else 0
        )

        errors = (
            int(error_match.group(1))
            if error_match
            else 0
        )

        total = (
            passed
            + failed
            + skipped
            + errors
        )


        # -------------------------------------------------
        # No tests found
        # -------------------------------------------------

        if total == 0:

            return {
                "status": "Not Run",
                "total": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "errors": 0,
                "pass_rate": 0,
                "duration_ms": duration_ms,
                "message": "No pytest tests found."
            }


        # -------------------------------------------------
        # Pass rate
        # -------------------------------------------------

        pass_rate = round(
            (passed / total) * 100,
            2
        )


        # -------------------------------------------------
        # Final pytest result
        # -------------------------------------------------

        return {
            "status": (
                "Passed"
                if failed == 0 and errors == 0
                else "Failed"
            ),

            "total": total,

            "passed": passed,

            "failed": failed,

            "skipped": skipped,

            "errors": errors,

            "pass_rate": pass_rate,

            "duration_ms": duration_ms,

            "message": "Actual pytest result"
        }


    # -----------------------------------------------------
    # TIMEOUT
    # -----------------------------------------------------

    except subprocess.TimeoutExpired:

        duration_ms = round(
            (time.perf_counter() - start) * 1000,
            2
        )

        return {
            "status": "Timeout",
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "pass_rate": 0,
            "duration_ms": duration_ms,
            "message": "Pytest execution timed out."
        }


    # -----------------------------------------------------
    # OTHER ERROR
    # -----------------------------------------------------

    except Exception as exc:

        duration_ms = round(
            (time.perf_counter() - start) * 1000,
            2
        )

        return {
            "status": "Error",
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "pass_rate": 0,
            "duration_ms": duration_ms,
            "message": str(exc)
        }