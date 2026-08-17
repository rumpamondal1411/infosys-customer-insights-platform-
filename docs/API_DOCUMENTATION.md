# ShopSense — API Documentation

This is a reference index for the REST API. Every endpoint below is also
live in interactive form (try-it-out, request/response schemas) at:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **Raw OpenAPI schema:** `http://localhost:8000/openapi.json`

Those are auto-generated from the FastAPI route definitions and Pydantic
schemas, so they can never drift out of sync with the code — this document
is the map of *what exists and where*, not a duplicate of every request
body.

---

## 1. Module Index

| Module | Prefix | Purpose |
|---|---|---|
| Vendor Management | `/vendors` | Registration, verification, approval/rejection, suspend/reactivate |
| Products & Categories | `/products`, `/categories` | Catalogue CRUD, image upload, ratings |
| Inventory | `/inventory` | Stock levels, low-stock alerts, restocking |
| Transactions | `/transactions` | Raw transaction record access |
| Customer | `/customer` | Registration, login, address/profile, checkout, orders, wishlist, ratings |
| Auth | `/auth` | Vendor/admin authentication |
| Admin | `/admin` | Admin-only vendor/marketplace management |
| Sales & Marketplace Analytics | `/analytics` | Revenue, top products, vendor performance, inventory turnover, forecasting, baseline reports |
| Revenue Intelligence | `/revenue-intelligence` | GMV/growth, margins, refunds, regional/time-series breakdowns, promo performance, marketplace benchmarking |
| Customer Behaviour Analytics | `/customer-analytics` | RFM segmentation (K-Means), recommendations, churn risk |
| Validation | `/validation` | Data-quality and forecast-confidence checks |
| Promotions | `/promotions` | Discount codes |
| **Milestone 3 — Analytics Infrastructure** | `/api/v1` | ETL pipeline control, MLflow-tracked model training, marketplace benchmarking, report export/scheduling |
| **Milestone 4 — Executive Reporting** | `/api/v1/executive` | KPI roll-up, growth trend, executive Excel export |
| Frontend (server-rendered pages) | `/` | Dashboards, login/register, admin/vendor/customer portals |

---

## 2. Milestone 4 — Executive Reporting API (new)

Base path: `/api/v1/executive`

### `GET /api/v1/executive/summary`
One-call KPI roll-up for the executive dashboard.

**Query params:** `period_days` (int, 1–365, default 30) — growth-comparison window.

**Response shape:**
```json
{
  "generated_at": "2026-08-09T10:00:00",
  "period_days": 30,
  "kpis": {
    "total_revenue": 3096583.0,
    "total_orders": 121,
    "gmv": 3096583.0,
    "average_order_value": 25591.6,
    "revenue_growth_pct": 591.07,
    "active_vendor_count": 5,
    "high_churn_risk_customers": 14
  },
  "top_vendor": { "business_name": "...", "total_revenue": 0.0 },
  "top_products": [ /* top 5, same shape as /analytics/top-products */ ],
  "customer_segment_mix": [ /* cluster summary, same shape as /customer-analytics/segments */ ],
  "data_quality": { /* same shape as /analytics/consistency-check */ }
}
```

Degrades gracefully: if there isn't enough data yet for K-Means (e.g. a
near-empty database), `customer_segment_mix` returns `[]` and
`high_churn_risk_customers` returns `null` instead of the endpoint erroring.

### `GET /api/v1/executive/kpi-trend`
Monthly revenue/order trend for the executive line chart.

**Query params:** `months` (int, 1–24, default 6)

**Response:** list of `{ "month": "2026-07", "revenue": 12345.0, "orders": 42 }`.

### `GET /api/v1/executive/export`
Generates and downloads a multi-sheet `.xlsx` workbook (Summary KPIs, KPI
Trend, Vendor Performance, Top Products, Customer Segments) — the
single-file handoff for a stakeholder/mentor demo.

**Query params:** `period_days` (int, 1–365, default 30)

**Response:** `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` file download.

---

## 3. Authentication

Vendor and admin logins go through `/auth/*` and `/vendors/login`; the API
does not currently issue JWTs — session identity is passed as path/body
parameters (`vendor_id`, `customer_id`, `admin_id`) matching the layered
architecture described in `ARCHITECTURE.md`. If you add token-based auth
later, the executive-reporting endpoints have no auth of their own yet and
would need the same middleware applied to `/api/v1/executive/*`.

---

## 4. Error Conventions

All endpoints return standard FastAPI/Pydantic validation errors (`422`)
for malformed input, and raise `HTTPException` with a `400`/`404`/`500`
and a plain-text `detail` message for business-rule violations (e.g.
insufficient stock, missing delivery address, unknown report section).
There is no custom error envelope — `detail` is the message to surface to
a user or log.

---

## 5. Full Endpoint Reference

For the complete, always-current list of every route, request schema, and
response schema, use `/docs` (Swagger UI) while the app is running. This
document intentionally stays at the module level so it doesn't go stale
every time a field is added to a schema.
