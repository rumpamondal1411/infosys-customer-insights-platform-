"""
Milestone 3 — scheduled data refresh & automated analytical pipeline
execution.

Uses APScheduler's BackgroundScheduler so no external cron/Celery/Airflow
infrastructure is required to satisfy "support scheduled data refresh
processes and automated analytical pipeline execution". Controlled by
ENABLE_SCHEDULER (off by default so tests/dev runs stay deterministic);
turn it on via .env for a "live" deployment.
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.database import SessionLocal

logger = logging.getLogger("shopsense.scheduler")

_scheduler: BackgroundScheduler | None = None


def _run_etl_job():
    from app.etl.pipeline import run_pipeline
    db = SessionLocal()
    try:
        result = run_pipeline(db, triggered_by="scheduler")
        logger.info("Scheduled ETL run complete: %s", result)
    except Exception:
        logger.exception("Scheduled ETL run failed")
    finally:
        db.close()


def _run_retrain_job():
    from app.ml.segmentation_training import train_and_register
    db = SessionLocal()
    try:
        result = train_and_register(db)
        logger.info("Scheduled model retrain complete: %s", result)
    except Exception:
        logger.exception("Scheduled model retrain failed")
    finally:
        db.close()


def _run_report_job():
    from app.services.report_service import generate_scheduled_report
    db = SessionLocal()
    try:
        generate_scheduled_report(db)
        logger.info("Scheduled report generation complete")
    except Exception:
        logger.exception("Scheduled report generation failed")
    finally:
        db.close()


def start_scheduler():
    """Called from the FastAPI startup event. No-op if disabled in config."""
    global _scheduler
    if not settings.enable_scheduler:
        logger.info("Scheduler disabled (ENABLE_SCHEDULER=false) — skipping job registration.")
        return None

    if _scheduler is not None:
        return _scheduler

    scheduler = BackgroundScheduler(timezone="UTC")

    scheduler.add_job(
        _run_etl_job,
        CronTrigger(hour=settings.etl_cron_hour, minute=settings.etl_cron_minute),
        id="nightly_etl",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_report_job,
        CronTrigger(hour=settings.etl_cron_hour, minute=settings.etl_cron_minute + 15),
        id="nightly_report",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_retrain_job,
        CronTrigger(day_of_week=settings.model_retrain_cron_day_of_week, hour=3, minute=0),
        id="weekly_retrain",
        replace_existing=True,
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info("Scheduler started: nightly ETL @ %02d:%02d UTC, weekly retrain on %s",
                settings.etl_cron_hour, settings.etl_cron_minute, settings.model_retrain_cron_day_of_week)
    return scheduler


def shutdown_scheduler():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
