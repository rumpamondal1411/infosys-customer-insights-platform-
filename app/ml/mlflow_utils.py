"""
Milestone 3 — MLflow experiment tracking & model registry helpers.

Tracking URI defaults to a local `./mlruns` folder (file store) so the
project still runs with zero external infrastructure, exactly like the
SQLite default for the database. Point MLFLOW_TRACKING_URI at a real
tracking server (e.g. the `mlflow` service in docker-compose.yml) in any
environment where one is available — no code changes required.
"""
import mlflow

from app.config import settings

_configured = False


def configure_mlflow():
    global _configured
    if _configured:
        return
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.mlflow_experiment_name)
    _configured = True
