"""
System Health Service

Provides health checks for the ShopSense admin dashboard.
Checks database, API, storage and ML/MLflow availability.
"""

from datetime import datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session


def check_database(db: Session) -> dict:
    """
    Check whether the database is reachable.
    """
    try:
        db.execute(text("SELECT 1"))

        return {
            "name": "Database",
            "status": "Healthy",
            "message": "Database connection is working normally.",
            "icon": "database",
        }

    except Exception as exc:
        return {
            "name": "Database",
            "status": "Down",
            "message": f"Database connection failed: {str(exc)}",
            "icon": "database",
        }


def check_storage() -> dict:
    """
    Check whether the application upload/static directory exists
    and is writable.
    """

    storage_path = Path("app/static/uploads")

    try:
        storage_path.mkdir(parents=True, exist_ok=True)

        test_file = storage_path / ".health_check"

        with open(test_file, "w", encoding="utf-8") as file:
            file.write("health-check")

        test_file.unlink(missing_ok=True)

        return {
            "name": "Storage",
            "status": "Healthy",
            "message": "File storage is available and writable.",
            "icon": "storage",
        }

    except Exception as exc:
        return {
            "name": "Storage",
            "status": "Warning",
            "message": f"Storage check failed: {str(exc)}",
            "icon": "storage",
        }


def check_ml_service() -> dict:
    """
    Check whether MLflow can be imported.

    This does not require an MLflow server to be running.
    It checks whether the ML environment is available to the application.
    """

    try:
        import mlflow

        version = getattr(mlflow, "__version__", "unknown")

        return {
            "name": "ML / MLflow",
            "status": "Healthy",
            "message": f"MLflow is available. Version: {version}",
            "icon": "ml",
        }

    except Exception as exc:
        return {
            "name": "ML / MLflow",
            "status": "Warning",
            "message": f"ML service is unavailable: {str(exc)}",
            "icon": "ml",
        }


def check_api() -> dict:
    """
    Basic application API health check.
    """

    return {
        "name": "API Service",
        "status": "Healthy",
        "message": "FastAPI application is running normally.",
        "icon": "api",
    }


def get_system_health(db: Session) -> dict:
    """
    Return complete system health information.
    """

    checks = [
        check_database(db),
        check_api(),
        check_storage(),
        check_ml_service(),
    ]

    healthy_count = sum(
        1 for item in checks
        if item["status"] == "Healthy"
    )

    warning_count = sum(
        1 for item in checks
        if item["status"] == "Warning"
    )

    down_count = sum(
        1 for item in checks
        if item["status"] == "Down"
    )

    if down_count > 0:
        overall_status = "Critical"
    elif warning_count > 0:
        overall_status = "Warning"
    else:
        overall_status = "Healthy"

    return {
        "overall_status": overall_status,
        "total_services": len(checks),
        "healthy_services": healthy_count,
        "warning_services": warning_count,
        "down_services": down_count,
        "checks": checks,
        "checked_at": datetime.now().strftime("%d %b %Y, %I:%M:%S %p"),
    }