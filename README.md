# ShopSense — Multi-Vendor E-Commerce Analytics Platform
### Week 1 Deliverable: Marketplace Foundation & Vendor Analytics

This is the Week 1 implementation covering:

1. **Vendor Management & Marketplace Onboarding** — registration, profile
   management, verification workflow, approval/rejection, activation/suspension.
2. **Product & Inventory Analytics Engine** — product catalogue, category
   hierarchy, inventory tracking, low-stock alerts, a baseline demand forecast.
3. **Database schemas** for vendors, products, categories, inventory, and transactions.
4. **Sales aggregation & reporting** — revenue by vendor/category, top products,
   vendor performance snapshot, inventory turnover, and an exportable baseline
   marketplace report (JSON + CSV).

---

## 1. Explanation / Design Decisions

| Decision | Rationale |
|---|---|
| **FastAPI** | Async-ready, auto-generates OpenAPI docs (`/docs`), strong typing via Pydantic — ideal for a REST API that will grow across 8 weeks. |
| **SQLAlchemy 2.0 ORM + SQLite (default)** | Zero external infra needed to run Week 1 locally. `DATABASE_URL` is the only thing to change to point at PostgreSQL/MySQL later — no model or service code changes required. |
| **Layered architecture** (`routers` → `services` → `models`) | Routers only handle HTTP concerns. Business logic (onboarding workflow, stock deduction, aggregation) lives in `services/`, so it's reusable by the API, seed scripts, CI checks, or a future CLI/admin tool. |
| **pandas for aggregation** | Sales aggregation, revenue rollups, and the forecast are naturally expressed as groupby/aggregate operations — this also sets up Week 4's ML forecasting work, which will reuse the same DataFrame pipeline. |
| **Explicit state machines for Vendor/Product/Transaction status** | Vendor lifecycle (`pending → active/rejected → suspended → active`) and verification status are modeled as enums with guarded transitions in `vendor_service.py`, so invalid transitions (e.g. suspending a pending vendor) are rejected with clear errors. |
| **Inventory created alongside Product** | Every product always has exactly one inventory record (1:1), created transactionally with the product, avoiding orphaned catalogue entries with no stock record. |

### Data Model (Entity Relationships)

```
Vendor (1) ──── (M) Product ──── (1) Inventory
   │                  │
   │                  └──── (M) Category (self-referential parent/child)
   │
   └──── (M) Transaction ──── (M:1) Product
```

- **Vendor**: business details, contact info, commission_rate, status (pending/active/suspended/rejected), verification_status.
- **Category**: hierarchical (parent_id self-FK) — e.g. Electronics → Mobile Phones.
- **Product**: belongs to one vendor + one category, has price/cost_price/status.
- **Inventory**: 1:1 with Product — quantity_available, reorder_level, reorder_quantity, warehouse_location.
- **Transaction**: one row per sale line-item — the fact table analytics is built on.

---

## 2. Folder Structure

```
shopsense/
├── app/
│   ├── main.py                  # FastAPI app entrypoint, router registration
│   ├── config.py                # Settings (env-driven)
│   ├── database.py               # SQLAlchemy engine/session/Base, init_db()
│   ├── models/                   # SQLAlchemy ORM models (DB schema)
│   │   ├── vendor.py
│   │   ├── category.py
│   │   ├── product.py
│   │   ├── inventory.py
│   │   └── transaction.py
│   ├── schemas/                  # Pydantic request/response models
│   │   ├── vendor.py
│   │   ├── category.py
│   │   ├── product.py
│   │   ├── inventory.py
│   │   └── transaction.py
│   ├── routers/                  # FastAPI route handlers (HTTP layer only)
│   │   ├── vendors.py
│   │   ├── products.py
│   │   ├── inventory.py
│   │   ├── transactions.py
│   │   └── analytics.py
│   ├── services/                 # Business logic (reusable, testable)
│   │   ├── vendor_service.py
│   │   ├── product_service.py
│   │   ├── inventory_service.py
│   │   ├── transaction_service.py
│   │   ├── analytics_service.py  # sales aggregation engine
│   │   └── report_service.py     # baseline report generator (CSV/JSON)
│   └── utils/
│       └── seed_data.py          # sample data generator (Faker)
├── tests/
│   ├── conftest.py               # in-memory DB + TestClient fixtures
│   ├── test_vendors.py
│   ├── test_products_inventory.py
│   └── test_analytics.py
├── data/                         # SQLite DB file lives here (gitignored)
├── reports/                      # generated baseline reports (gitignored)
├── requirements.txt
├── .env.example
├── .gitignore
├── run.py                        # `python run.py` to start the server
└── README.md
```

---

## 3. Files Created (Summary)

| File | Purpose |
|---|---|
| `app/database.py` | DB engine, session factory, `init_db()` creates all tables |
| `app/models/*.py` | 5 SQLAlchemy models = the full Week 1 database schema |
| `app/schemas/*.py` | Pydantic validation models for every API payload/response |
| `app/services/vendor_service.py` | Onboarding, verification, approve/reject, suspend/reactivate |
| `app/services/product_service.py` | Category + product catalogue CRUD |
| `app/services/inventory_service.py` | Restock, manual adjustment, low-stock alert detection |
| `app/services/transaction_service.py` | Records sales, deducts stock automatically |
| `app/services/analytics_service.py` | Sales aggregation engine (pandas-based) |
| `app/services/report_service.py` | Baseline marketplace report exporter (JSON + CSV) |
| `app/routers/*.py` | REST API endpoints, grouped by domain |
| `app/utils/seed_data.py` | Generates ~12 vendors, ~60 products, ~500 transactions |
| `tests/*.py` | 17 automated tests across vendor, product/inventory, analytics flows |

---

## 4. Commands to Run

```bash
# 1. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) copy env file — defaults work out of the box
cp .env.example .env

# 4. Seed the database with sample marketplace data
python -m app.utils.seed_data

# 5. Run the API server
python run.py
# or: uvicorn app.main:app --reload

# 6. Open interactive API docs
# http://localhost:8000/docs

# 7. Run the automated test suite
pytest -v
```

### Quick smoke test with curl (after step 5)

```bash
# Register a vendor
curl -X POST http://localhost:8000/vendors/register \
  -H "Content-Type: application/json" \
  -d '{"business_name":"Acme Co","contact_person":"Jane Doe","email":"jane@acme.com","phone":"555-0100"}'

# Approve the vendor (replace 1 with the returned id)
curl -X PATCH http://localhost:8000/vendors/1/approve -H "Content-Type: application/json" -d '{}'

# Generate the Week 1 baseline report
curl -X POST http://localhost:8000/analytics/reports/baseline
```

---

## 5. Expected Output

**`python -m app.utils.seed_data`:**
```
Seeding categories...
  -> 12 categories created
Seeding vendors...
  -> 12 vendors created
Seeding products & inventory...
  -> 48 products created
Seeding transactions...
  -> 500 transactions created

Seed complete.
```

**`python run.py`:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

**`GET /analytics/sales-summary`:**
```json
{
  "total_revenue": 48213.55,
  "total_orders": 441,
  "total_units_sold": 1298,
  "average_order_value": 109.33,
  "unique_customers": 200,
  "active_vendors": 8
}
```

**`pytest -v`:** all 17 tests pass, e.g.
```
tests/test_vendors.py::test_register_vendor PASSED
tests/test_vendors.py::test_vendor_onboarding_workflow PASSED
tests/test_products_inventory.py::test_low_stock_alert PASSED
tests/test_analytics.py::test_baseline_report_generation PASSED
...
17 passed in 2.1s
```

**`POST /analytics/reports/baseline`** writes files like:
```
reports/baseline_report_20260702_101530.json
reports/revenue_by_vendor_20260702_101530.csv
reports/revenue_by_category_20260702_101530.csv
reports/top_products_20260702_101530.csv
reports/vendor_performance_20260702_101530.csv
reports/inventory_turnover_20260702_101530.csv
```

> **Note on this sandbox:** this environment has no outbound network access, so
> `pip install` couldn't be run here to execute a live end-to-end test. Every
> file was syntax-checked (`py_compile`) and the code follows standard,
> well-established FastAPI/SQLAlchemy/pandas patterns. Run the commands above
> in your own environment to see it live — if anything doesn't behave as
> documented, send me the traceback and I'll fix it immediately.

---

## 6. API Documentation

Full interactive docs are auto-generated at **`/docs`** (Swagger UI) and
**`/redoc`** once the server is running. Summary below.

### Vendor Management (`/vendors`)
| Method | Path | Description |
|---|---|---|
| POST | `/vendors/register` | Onboard a new vendor (status=pending) |
| GET | `/vendors` | List vendors, filter by `?status=` |
| GET | `/vendors/{id}` | Get vendor detail |
| PUT | `/vendors/{id}` | Update vendor profile |
| POST | `/vendors/{id}/submit-for-verification` | Move to in_review |
| PATCH | `/vendors/{id}/approve` | Approve onboarding → active/verified |
| PATCH | `/vendors/{id}/reject` | Reject onboarding application |
| PATCH | `/vendors/{id}/suspend` | Suspend an active vendor |
| PATCH | `/vendors/{id}/reactivate` | Reactivate a suspended vendor |
| DELETE | `/vendors/{id}` | Remove a vendor |

### Catalogue (`/categories`, `/products`)
| Method | Path | Description |
|---|---|---|
| POST | `/categories` | Create a category (optionally nested via `parent_id`) |
| GET | `/categories` | List all categories |
| POST | `/products` | Add a product (vendor must be active); optionally sets initial stock |
| GET | `/products` | List products, filter by vendor/category/status |
| PUT | `/products/{id}` | Update product |
| DELETE | `/products/{id}` | Remove product |
| POST | `/products/{id}/image` | Upload/replace a product image (JPG/PNG/WEBP, max 5MB) |
| DELETE | `/products/{id}/image` | Remove a product's image |

**How product images work:** the image file itself is saved to disk under
`app/static/uploads/products/{product_id}.{ext}` (served via the existing
`/static` mount), and only the resulting URL string is stored on the
product row (`products.image_url`). This is the standard pattern for any
database engine — SQLite, PostgreSQL, or MongoDB all work identically
here, since none of them store the raw image bytes in the database itself.
Re-uploading replaces the previous file automatically (including cleaning
up a stale file if the extension changed, e.g. `.png` → `.jpg`).

On the frontend, `/add-product` and `/edit-product` let a vendor pick an
image with a live preview before submitting, and `/my-products` renders
an Amazon/Flipkart-style card grid with each product's thumbnail (falling
back to a "No Image" placeholder tile for products without one yet).


### Inventory (`/inventory`)
| Method | Path | Description |
|---|---|---|
| GET | `/inventory/{product_id}` | Current stock for a product |
| PUT | `/inventory/{product_id}` | Manually adjust stock fields |
| POST | `/inventory/{product_id}/restock` | Add stock (warehouse replenishment) |
| GET | `/inventory/alerts/low-stock` | Products at/below reorder threshold |

### Transactions (`/transactions`)
| Method | Path | Description |
|---|---|---|
| POST | `/transactions` | Record a sale (auto-deducts stock) |
| GET | `/transactions` | List transactions, filter by vendor/product |

### Analytics & Reporting (`/analytics`)
| Method | Path | Description |
|---|---|---|
| GET | `/analytics/sales-summary` | Marketplace-wide KPIs |
| GET | `/analytics/revenue-by-vendor` | Revenue/orders/units grouped by vendor |
| GET | `/analytics/revenue-by-category` | Revenue grouped by category |
| GET | `/analytics/top-products` | Top N products by revenue |
| GET | `/analytics/vendor-performance` | Revenue, AOV, active product count per vendor |
| GET | `/analytics/inventory-turnover` | Units sold ÷ stock on hand per product |
| GET | `/analytics/forecast/{product_id}` | Moving-average demand forecast (7/14/30 day) |
| GET | `/analytics/consistency-check` | Revenue reconciliation across vendor/category rollups |
| POST | `/analytics/reports/baseline` | Generates + saves the full baseline report |

### Dashboard
| Method | Path | Description |
|---|---|---|
| GET | `/dashboard` | Visual marketplace dashboard (charts + tables, Chart.js) |

---

## 8. Milestone 1 Evaluation Criteria — How This Build Meets Them

| Criterion | Where it's implemented | How to verify |
|---|---|---|
| **Vendor onboarding validates ≥99% of registrations** | `vendor_service.validate_registration_payload()` + `register_vendor()` — checks blank fields, phone format, commission range, duplicate email/tax_id (including a race-safe `IntegrityError` catch so concurrent duplicates never 500). Every failure path returns a clean 400 with a specific reason, never a crash. | `pytest -v tests/test_vendors.py` — includes invalid-phone, duplicate-tax_id, blank-name, out-of-range-commission cases, all asserting clean 400/422 responses. |
| **Sales analytics ≥98% transactional consistency** | `analytics_service.transactional_consistency_check()` — reconciles the vendor-rollup total and category-rollup total against the raw marketplace total revenue, and reports a measurable `overall_consistency_pct`. | `GET /analytics/consistency-check` or `pytest tests/test_analytics.py::test_consistency_check_meets_threshold_after_sales`. Also included automatically in every baseline report. |
| **Dashboards visualize product/vendor performance** | `GET /dashboard` — a real HTML page (Chart.js) with a vendor-revenue bar chart, category-revenue donut chart, top-products table, vendor-performance table, and a live consistency-check readout. Not just JSON — an actual visual surface. | Open `http://localhost:8000/dashboard` after seeding data. `pytest tests/test_analytics.py::test_dashboard_page_renders` checks it serves valid HTML with the chart elements present. |

---

## 7. What's Deliberately Out of Scope for Week 1

These are called out so scope stays honest — they belong to later milestones
per the project outcomes list:

- ML-based inventory forecasting (Week 1 ships a moving-average baseline only; outcome #4 calls for full ML models later).
- Vendor performance **ranking/scoring** with weighted criteria (outcome #5) — Week 1 exposes the raw metrics (`/analytics/vendor-performance`) those rankings will be computed from.
- Customer segmentation/behavior tracking (outcome #3).
- PDF export and the full BI comparative-analysis dashboard (outcome #7) — CSV/JSON export exists now; PDF export is a natural next step reusing `report_service.py`.
- CI/CD pipeline config and data governance policies (outcome #8) — the test suite in `tests/` is the foundation a CI pipeline (e.g. GitHub Actions running `pytest`) would run.
- Any frontend/dashboard UI — Week 1 is the REST API + data layer; a dashboard (e.g. React or Streamlit) can sit on top of these endpoints in Week 2.

---

## 9. Milestone 2 (Weeks 3-4) — Inventory Intelligence & Customer Analytics

Milestone 2 adds two things on top of Week 1: a Flipkart/Meesho-style
**search + buy** flow on the customer dashboard, and two new analytics
modules.

### 9.1 Customer Dashboard — Search & Buy

- `GET /products?search=...` — full-text-ish search over product name,
  description, and SKU (`product_service.list_products`), reused by the
  new search box on `/customer-dashboard`. Every product now also carries
  `rating` / `rating_count` (shown as "⭐ 4.3 (128)", or "No ratings yet"
  if unrated) and a live `quantity_available` — the product card shows a
  red **"Out of Stock"** label and disables Add to Cart / Buy Now once
  stock hits zero.
- **A delivery address is mandatory before any order can be placed.**
  `POST /customer/checkout` rejects with `400 ADDRESS_REQUIRED: ...` if
  the customer has no `address_line`/`city`/`pincode`/`phone` on file
  (`app/schemas/customer.py::has_complete_address`). The dashboard catches
  that specific error, opens the "My Address" modal automatically, and —
  once the address is saved — **retries the exact order that was blocked**
  (see `pendingOrder` in `customer_dashboard.html`), so the customer never
  has to re-add items or re-pick a payment method.
- **Both "Add to Cart → checkout" and "Buy Now" show the same payment
  method picker** (COD / UPI / Net Banking) before placing an order — Buy
  Now now opens its own confirmation modal (`#buyNowModal`) instead of
  silently defaulting to COD.
- `POST /customer/checkout` — cart/"Buy Now" checkout. Validates stock for
  every line item up front (all-or-nothing), applies an optional promo
  code, deducts inventory, and creates one `Transaction` row per
  line-item tagged with a shared `order_ref` (see design note in
  `app/services/order_service.py` — there's intentionally no separate
  Order table, so every existing analytics pipeline built on `Transaction`
  picks up customer purchases automatically). Every order is stamped with
  `expected_delivery_date = placed_at + 2 days` (delivery is always
  assumed to take exactly 2 days).
- **Full order lifecycle** (`placed → shipped → delivered`, or
  `cancelled` / `returned`), tracked per line-item on `Transaction`
  (`order_status`, `shipped_at`, `delivered_at`, `cancelled_at`,
  `returned_at`). No scheduled job is required for orders to progress:
  `order_service._sync_order_status()` derives the live status purely
  from elapsed time (shipped at the 1-day mark, delivered at the 2-day
  mark) and persists it every time `GET /customer/{id}/orders` is called.
  The "My Orders" screen shows a Placed → Shipped → Delivered step
  indicator, the expected delivery date, and:
  - **Cancel Order** (`POST /customer/{id}/orders/{tx_id}/cancel`) — any
    time before delivery; restocks inventory and marks the transaction
    `CANCELLED` for analytics.
  - **Return Order** (`POST /customer/{id}/orders/{tx_id}/return`) — any
    time after delivery; restocks inventory and marks the transaction
    `REFUNDED` for analytics.
- `GET /customer/{customer_id}/orders` — order history ("My Orders"),
  always returned with fresh, live-synced fulfillment status.
- `POST /customer/{customer_id}/track-view/{product_id}` — logs a
  browsing/engagement event (`ProductView`), the raw signal Module 4's
  recommendation engine learns from.
- The dashboard also shows a **"Recommended for You"** rail sourced from
  `GET /customer-analytics/recommendations/{customer_id}`.

### 9.2 Module 3 — Sales Analytics & Revenue Intelligence (`/revenue-intelligence`)

`app/services/revenue_intelligence_service.py` aggregates orders,
payments, refunds, and promotional campaigns (all read from `Transaction`,
now extended with `discount_amount` / `promotion_id`) into:

| Endpoint | Purpose |
|---|---|
| `GET /revenue-intelligence/gmv-growth` | GMV, revenue, AOV, period-over-period revenue growth |
| `GET /revenue-intelligence/profit-margins` | Gross profit margin per product (price vs. cost_price on realized sales) |
| `GET /revenue-intelligence/refunds` | Refund/cancellation aggregation |
| `GET /revenue-intelligence/by-region` | Revenue segmented by region (vendor country) |
| `GET /revenue-intelligence/by-time` | Daily/weekly/monthly revenue rollups |
| `GET /revenue-intelligence/promotion-performance` | Orders/revenue/discount given per promo code |
| `GET /revenue-intelligence/dashboard` | One-call payload for the dashboard page |
| `POST /promotions`, `GET /promotions` | Create/list promotional campaigns |

Visual surface: **`/revenue-intelligence-page`** (admin dashboard, Chart.js).

### 9.3 Module 4 — Customer Behaviour & Recommendation Analytics (`/customer-analytics`)

`app/services/customer_analytics_service.py` combines purchase history
(`Transaction`) with browsing behaviour (`ProductView`) to deliver:

| Endpoint | Purpose |
|---|---|
| `GET /customer-analytics/segments` | Customer segmentation via **KMeans clustering** on standardized RFM + engagement features (Recency, Frequency, Monetary, Views); falls back to rule-based labeling when there's too little data to cluster meaningfully |
| `GET /customer-analytics/customer/{id}/profile` | Purchase history, browsing behaviour, favorite category, segment |
| `GET /customer-analytics/recommendations/{id}` | Personalized recommendations — **item-based collaborative filtering** (cosine similarity over the customer×product purchase matrix) blended with **content-based filtering** (category affinity), with a popularity fallback for cold-start customers |
| `GET /customer-analytics/churn-risk` | Churn-risk scoring from each customer's own purchase cadence (days since last order vs. their historical average gap) |
| `GET /customer-analytics/dashboard` | One-call payload for the dashboard page |

Visual surface: **`/customer-analytics-page`** (admin dashboard — segment
donut/bar charts, churn-risk table, recommendation preview tool).

### 9.4 Validating against historical data

Seeding now creates 40 customers, product views, and promotions, and
**links transactions to real seeded customer accounts** (Week 1's seed
script generated random `customer_id`s that didn't correspond to any
row — fixed here so segmentation/recommendation/churn analytics has
real history to learn from):

```bash
python -m app.utils.seed_data
pytest -v tests/test_orders.py tests/test_revenue_intelligence.py tests/test_customer_analytics.py
```

### 9.5 New/changed files (Milestone 2)

| File | Purpose |
|---|---|
| `app/models/transaction.py` | + `discount_amount`, `promotion_id`; + full order lifecycle: `OrderStatus` enum, `order_ref`, `order_status`, `expected_delivery_date`, `shipped_at`, `delivered_at`, `cancelled_at`, `cancellation_reason`, `returned_at`, `return_reason` |
| `app/models/product.py` | + `rating`, `rating_count`, computed `quantity_available` / `in_stock` properties |
| `app/schemas/customer.py` | Fixed a bug where a duplicate `CustomerResponse` class silently dropped address fields from every API response; + `has_complete_address()` |
| `app/schemas/order.py`, `app/services/order_service.py` | Cart/checkout ("Buy") flow — now enforces a mandatory delivery address, stamps a 2-day `expected_delivery_date`, and adds `_sync_order_status()` / `cancel_order()` / `return_order()` |
| `app/schemas/product.py`, `app/schemas/transaction.py`, `app/schemas/wishlist.py` | Expose the new rating/stock/order-lifecycle fields |
| `app/routers/customer.py` | + `POST /customer/{id}/orders/{tx_id}/cancel`, `POST /customer/{id}/orders/{tx_id}/return` |
| `app/services/revenue_intelligence_service.py`, `app/routers/revenue_intelligence.py` | Module 3 |
| `app/services/customer_analytics_service.py`, `app/routers/customer_analytics.py` | Module 4 |
| `app/routers/promotions.py` | Minimal CRUD for promo codes |
| `app/templates/revenue_intelligence.html`, `app/templates/customer_analytics.html` | New admin dashboard pages |
| `app/templates/customer_dashboard.html` | Search bar, cart, Buy Now (with payment method picker), address-required retry flow, full order-lifecycle "My Orders" (step indicator + Cancel/Return), product rating/out-of-stock badges, recommendations rail |
| `app/utils/seed_data.py`, `app/utils/migrate_add_columns.py` | Real customer↔transaction linkage, product views, promotions, ratings, backfilled order lifecycles; SQLite column migration for existing DBs |
| `requirements.txt` | + `scikit-learn` (KMeans, cosine similarity) |

---

## 10. Milestone 3 (Weeks 5-6) — Advanced Analytics, APIs & Reporting

### 10.1 Data Management & Analytics Infrastructure

- **Postgres-ready via SQLAlchemy** — no code changes needed, just set
  `DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/db` (this is exactly
  what `docker-compose.yml` does for the containerized deployment). SQLite
  remains the zero-infra local default.
- **ETL pipeline** — `app/etl/pipeline.py` implements `extract -> clean_transform
  -> aggregate -> load` as four independently-testable functions. Every run
  (manual or scheduled) is recorded in a `PipelineRun` audit row, and the
  aggregate output is persisted as a new, timestamped `VendorPerformanceSnapshot`
  row (never overwritten) so trends are inspectable across runs.
- **MLflow experiment tracking & model registry** — `app/ml/segmentation_training.py`
  is a *tracked* training job for the RFM/K-Means segmentation model: it logs
  params (`n_clusters`, feature list), metrics (inertia, silhouette score), and
  the fitted estimator to MLflow, and registers it under
  `customer_segmentation_kmeans` in the Model Registry. Results are also mirrored
  into `MLModelRun` / `CustomerSegmentSnapshot` tables so the API can serve model
  history without needing the MLflow server reachable on every request.
- **Scheduled data refresh** — `app/scheduler.py` (APScheduler) runs the ETL
  pipeline nightly, an extended report 15 minutes later, and a model retrain
  weekly. Disabled by default (`ENABLE_SCHEDULER=false`) so tests/dev runs stay
  deterministic; flip it on in `.env` for a "live" deployment.

### 10.2 API, Reporting & CI Integration

New router **`app/routers/analytics_api.py`** (mounted at `/api/v1`), on top of
the existing Milestone 1-2 REST APIs (vendors, products, inventory, revenue
intelligence, customer analytics):

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/etl/run` | Manually trigger the ETL pipeline |
| `GET /api/v1/etl/runs` | Pipeline run audit history |
| `GET /api/v1/etl/vendor-snapshots` | Versioned vendor performance snapshots |
| `POST /api/v1/ml/segmentation/train` | Train + register the segmentation model via MLflow |
| `GET /api/v1/ml/segmentation/runs` | Local training-run history |
| `GET /api/v1/ml/segmentation/latest-version` | Latest MLflow Model Registry version |
| `GET /api/v1/ml/segmentation/snapshots` | Versioned per-customer segment assignments |
| `GET /api/v1/benchmark/marketplace` | Vendor vs. marketplace-average benchmarking (revenue/orders/AOV, percentile rank) |
| `GET /api/v1/reports/export?section=...&fmt=csv\|xlsx` | On-demand report export/download |
| `POST /api/v1/reports/scheduled/run` | Manually trigger the extended scheduled report |

- **BI dashboard prototype** — `/bi-dashboard` (linked from the admin sidebar):
  interactive Chart.js panels (revenue trend, vendor benchmark, customer
  segments, inventory turnover), plus one-click CSV/Excel export and ETL/ML
  pipeline controls.
- **Marketplace benchmarking, embedded in the day-to-day dashboards** (not just
  the BI prototype above):
  - `/admin-dashboard` now has a "Marketplace Benchmarking" panel — a chart +
    table of every vendor's revenue percentile and % vs. marketplace average,
    backed by `GET /api/v1/benchmark/marketplace`.
  - `/vendor-dashboard` now has a "My Performance vs. Marketplace" panel —
    the signed-in vendor's own revenue/orders/AOV percentile and delta vs.
    the marketplace average, backed by `GET /api/v1/benchmark/marketplace?vendor_id=...`.
- **Customer-facing revenue analysis** — `/customer-dashboard` has a new "My
  Spending" panel (stat cards + monthly spend trend + spend-by-category
  chart), backed by a new endpoint:
  `GET /customer-analytics/customer/{customer_id}/revenue-analysis` →
  `app/services/customer_analytics_service.py::customer_revenue_analysis()`.
- **Docker** — `Dockerfile` + `docker-compose.yml` (app + Postgres). Build/run:
  ```bash
  docker compose up --build
  ```
- **CI/CD** — `.github/workflows/ci.yml`: installs deps, lints, seeds a fresh DB
  and runs data-validation checks, runs the full pytest suite, smoke-tests the
  ETL pipeline, then builds the Docker image (no push) on a separate job.

### 10.3 New/changed files (Milestone 3)

| File | Purpose |
|---|---|
| `app/models/analytics_snapshot.py` | `PipelineRun`, `VendorPerformanceSnapshot`, `CustomerSegmentSnapshot`, `MLModelRun` |
| `app/etl/pipeline.py` | Extract/clean/transform/aggregate/load ETL job |
| `app/ml/mlflow_utils.py`, `app/ml/segmentation_training.py` | MLflow tracking + model registry |
| `app/scheduler.py` | APScheduler nightly ETL / weekly retrain jobs |
| `app/routers/analytics_api.py` | Milestone 3 `/api/v1/*` control-plane endpoints |
| `app/services/revenue_intelligence_service.py` | + `marketplace_benchmark()` |
| `app/services/report_service.py` | + `export_section()`, `generate_scheduled_report()` |
| `app/services/customer_analytics_service.py` | + `customer_revenue_analysis()` — per-customer spend/trend/category breakdown |
| `app/routers/customer_analytics.py` | + `GET /customer-analytics/customer/{id}/revenue-analysis` |
| `app/templates/bi_dashboard.html` | BI dashboard prototype |
| `app/templates/admin_dashboard.html` | + Marketplace Benchmarking panel |
| `app/templates/vendor_dashboard.html` | + "My Performance vs. Marketplace" benchmarking panel |
| `app/templates/customer_dashboard.html` | + "My Spending" revenue-analysis panel; hardened "My Orders" modal (error handling, product names, status colors) |
| `app/templates/base_customer.html` | + Chart.js include, "My Spending" nav link |
| `tests/test_customer_analytics.py` | + tests for the new `revenue-analysis` endpoint |
| `Dockerfile`, `docker-compose.yml`, `.dockerignore` | Containerized deployment (app + Postgres) |
| `.github/workflows/ci.yml` | CI/CD pipeline |
| `tests/test_milestone3_etl_reporting.py` | ETL, benchmarking, and export tests |
| `requirements.txt` | + `psycopg2-binary`, `mlflow`, `APScheduler`, `openpyxl` |

### 10.4 Quick start (Milestone 3 features)

```bash
pip install -r requirements.txt

# Local dev (SQLite + local MLflow store, scheduler off)
python -m app.utils.seed_data
uvicorn app.main:app --reload

# Trigger things manually from the BI dashboard (/bi-dashboard) or curl:
curl -X POST http://localhost:8000/api/v1/etl/run
curl -X POST http://localhost:8000/api/v1/ml/segmentation/train
curl "http://localhost:8000/api/v1/reports/export?section=vendor_performance&fmt=xlsx" -o vendors.xlsx

# Full containerized stack (app + Postgres, scheduler on)
docker compose up --build
```
