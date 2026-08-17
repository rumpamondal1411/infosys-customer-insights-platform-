"""
Centralized application configuration.
Values are loaded from environment variables / .env file, with sane defaults
so the app runs out of the box for local development.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ShopSense"
    app_env: str = "development"
    database_url: str = "sqlite:///./data/shopsense.db"
    default_commission_rate: float = 0.10
    low_stock_threshold_default: int = 10

    # --- Milestone 3 ---
    mlflow_tracking_uri: str = "sqlite:///./mlflow.db"
    mlflow_experiment_name: str = "shopsense-analytics"
    enable_scheduler: bool = False
    etl_cron_hour: int = 2          # nightly ETL run, default 2 AM
    etl_cron_minute: int = 0
    model_retrain_cron_day_of_week: str = "sun"  # weekly retrain
    reports_export_dir: str = "reports/exports"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
