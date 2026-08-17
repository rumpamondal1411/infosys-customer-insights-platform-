# ShopSense — Architecture Reference

## 1. System Overview

ShopSense is a multi-vendor e-commerce analytics platform built as a
single FastAPI service with a layered architecture, backed by SQLite
(dev) or PostgreSQL (production), with MLflow for experiment tracking and
APScheduler for background jobs. There is no microservice split — at this
scale a modular monolith keeps deployment and demo complexity low while
still keeping concerns cleanly separated in code.

```
┌─────────────────────────────────────────────────────────────┐
│                      Presentation Layer                       │
│   Jinja2 server-rendered pages (admin/vendor/customer portals)│
│   + Chart.js dashboards, vanilla JS (no frontend framework)   │
└───────────────────────────┬────────────────────────────────┘
                             │
┌───────────────────────────▼────────────────────────────────┐
│                      Routers (FastAPI)                        │
│  HTTP concerns only: request/response schemas, status codes   │
│  vendors · products · inventory · transactions · customer     │
│  admin · analytics · revenue_intelligence · customer_analytics│
│  validation · promotions · analytics_api (M3) · executive_    │
│  reports (M4) · dashboard (page routes)                       │
└───────────────────────────┬────────────────────────────────┘
                             │
┌───────────────────────────▼────────────────────────────────┐
│                        Services                                │
│  Business logic, reusable by routers, seed scripts, CI, and   │
│  the scheduler. Pandas-based aggregation lives here.           │
│  order_service · vendor_service · analytics_service ·         │
│  revenue_intelligence_service · customer_analytics_service ·  │
│  report_service · executive_report_service (M4) · etl/pipeline│
│  · ml/segmentation_training                                    │
└───────────────────────────┬────────────────────────────────┘
                             │
┌───────────────────────────▼────────────────────────────────┐
│                    Models (SQLAlchemy ORM)                     │
│  vendor · product · category · inventory · transaction ·      │
│  customer · rating · wishlist · promotion · analytics_snapshot│
└───────────────────────────┬────────────────────────────────┘
                             │
                    SQLite (dev) / PostgreSQL (prod)
```

**Why this layering:** routers only handle HTTP concerns (status codes,
request validation via Pydantic). Business logic — the vendor onboarding
state machine, stock deduction, aggregation pipelines — lives in
`services/`, so it's callable from the API, seed scripts, CI smoke tests,
or the scheduler without going through HTTP at all.

---

## 2. Data Model (Entity Relationships)

```
Vendor (1) ──── (M) Product ──── (1) Inventory
   │                  │
   │                  ├──── (M) Category (self-referential parent/child)
   │                  ├──── (M) Rating
   │                  └──── (M) Wishlist item
   │
   └──── (M) Transaction ──── (M:1) Product, Customer

Customer (1) ──── (M) Transaction
Customer (1) ──── (M) Wishlist item
Customer (1) ──── (M) ProductView   (recommendation signal)

AnalyticsSnapshot family (Milestone 3):
  PipelineRun · VendorPerformanceSnapshot · CustomerSegmentSnapshot
```

- **Vendor**: business details, commission_rate, status
  (pending/active/suspended/rejected), verification_status.
- **Product**: belongs to one vendor + one category; 1:1 with Inventory.
- **Transaction**: one row per cart line-item at checkout — the fact
  table nearly all analytics in this system is built on. There is no
  separate `Order` table; a checkout produces N transaction rows sharing
  an `order_ref` (see `app/schemas/order.py` for the design note).
- **AnalyticsSnapshot models** (Milestone 3): persisted audit trail of
  ETL runs and point-in-time vendor/segment snapshots, so the executive
  dashboard and BI reports aren't always recomputing from scratch.

---

## 3. Data Flow — Executive Reporting (Milestone 4)

The executive dashboard does not introduce a new data path. It reuses the
Milestone 1–3 analytics services and simply composes their outputs:

```
Transaction table (source of truth)
        │
        ▼
analytics_service / revenue_intelligence_service / customer_analytics_service
  (pandas groupby/aggregate — Milestones 1–3)
        │
        ▼
executive_report_service.executive_summary()   ← Milestone 4
  (composes: sales_summary + gmv_and_growth + vendor_performance
   + top_products + segment_customers + churn_risk + consistency_check)
        │
        ├──► GET /api/v1/executive/summary      (JSON, dashboard KPI cards)
        ├──► GET /api/v1/executive/kpi-trend     (JSON, trend chart)
        └──► GET /api/v1/executive/export        (.xlsx, stakeholder handoff)
```

This keeps a single source of truth per metric — the executive layer never
recomputes revenue or churn risk with its own logic, only aggregates what
the existing services already compute and tests cover.

---

## 4. Scheduled / Automated Processes

`app/scheduler.py` uses APScheduler's `BackgroundScheduler` (no external
cron/Celery/Airflow needed) — off by default (`ENABLE_SCHEDULER=false`) so
tests and local dev stay deterministic, turned on via `.env` for a
persistent deployment.

| Job | Schedule | What it does |
|---|---|---|
| `nightly_etl` | daily, `ETL_CRON_HOUR:ETL_CRON_MINUTE` | `run_pipeline()` — extract → clean → aggregate → load |
| `nightly_report` | 15 min after ETL | `generate_scheduled_report()` — extended JSON report |
| `weekly_retrain` | weekly, `MODEL_RETRAIN_CRON_DAY_OF_WEEK` | Retrains the K-Means segmentation model, logs to MLflow |

The executive report is **not** on the scheduler — it's generated
on-demand via `GET /api/v1/executive/export`, since it's meant to be
pulled fresh right before a stakeholder/mentor conversation rather than
pre-baked nightly.

---

## 5. Machine Learning Component

See `docs/ANALYTICS_MODELS.md` for the full model documentation
(features, training process, MLflow tracking, evaluation). Summary:
K-Means clustering over RFM (Recency, Frequency, Monetary) + product-view
features for customer segmentation, tracked via MLflow with
`sqlite:///./mlflow.db` as the tracking store.

---

## 6. Key Design Decisions

| Decision | Rationale |
|---|---|
| FastAPI + SQLAlchemy 2.0 + SQLite/PostgreSQL | Async-ready, auto-generated OpenAPI docs, zero external infra for local dev; `DATABASE_URL` is the only thing that changes for production. |
| Layered architecture (routers → services → models) | Business logic is reusable outside the HTTP layer (seed scripts, CI checks, scheduler). |
| No separate Order table | A checkout produces one Transaction row per line-item tagged with a shared `order_ref`, avoiding a parallel Order/OrderLine schema for a project of this scope. |
| pandas for all aggregation | Every analytics function follows the same groupby/aggregate shape, which is what makes composing them in `executive_report_service` (M4) straightforward. |
| Executive reporting composes existing services | Avoids a second source of truth for any metric — M4 adds a presentation/aggregation layer, not new analytics primitives. |
| APScheduler over Celery/Airflow | Satisfies "scheduled data refresh" without extra infrastructure a course project doesn't need. |
