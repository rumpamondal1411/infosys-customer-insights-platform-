# ShopSense — Analytics Model Documentation

This documents every non-trivial analytical model in the platform: what
it computes, the features/inputs it uses, and how to interpret its
output. Simple aggregations (revenue by vendor, top products) are
self-explanatory from their field names and are not repeated here — this
covers the models where the "how" matters.

---

## 1. Customer Segmentation — K-Means Clustering

**Where:** `app/services/customer_analytics_service.py::segment_customers`
(fast, request-time path used by the live dashboard) and
`app/ml/segmentation_training.py::train_and_register` (tracked training
job, logs to MLflow, used for auditable/versioned model runs).

**Features (RFM + engagement):**

| Feature | Definition |
|---|---|
| `recency_days` | Days since the customer's most recent purchase (clipped to 365 in the tracked training path, to stop very old one-time buyers from dominating scale) |
| `frequency` | Total number of completed purchases |
| `monetary` | Total amount spent |
| `views` | Total product views (engagement signal beyond just purchases) |

**Preprocessing:** features are standardized (`StandardScaler`) before
clustering, since K-Means is distance-based and `monetary` (dollars) and
`recency_days` (days) are on very different scales.

**Model:** `sklearn.cluster.KMeans`, `n_clusters=4` by default (tunable
via `n_clusters` param on both the live and tracked paths), `random_state=42`
for reproducibility, `n_init=10`.

**Cluster labeling:** clusters are ranked by mean `monetary` (tie-broken
by `frequency`) and mapped to human-readable segment names:
- Highest-value cluster → **Champions**
- Lowest-value cluster → **Low Engagement**
- Everything in between → **Loyal Customers**

**Evaluation metrics logged to MLflow:** `inertia` (within-cluster sum of
squares — lower is tighter clusters) and `silhouette_score` (−1 to 1,
higher is better-separated clusters). Both are visible per training run
via `GET /api/v1/ml/segmentation/runs`.

**Minimum data requirement:** clustering needs at least
`MIN_CUSTOMERS_FOR_CLUSTERING` customers with purchase activity;
below that, both the live and tracked paths return a "not enough data"
result rather than fitting a degenerate model. The Milestone 4 executive
summary handles this gracefully — `customer_segment_mix` returns `[]`
instead of erroring.

**Why two paths (live vs. tracked)?** The dashboard needs segments
instantly on every page load — refitting is fast enough for that. The
tracked path exists so a specific segmentation run can be versioned,
audited, and rolled back via the MLflow Model Registry without coupling
every dashboard request to MLflow being reachable.

---

## 2. Churn Risk Scoring

**Where:** `app/services/customer_analytics_service.py::churn_risk`

**Method:** heuristic, not ML — deliberately, since churn labels (did this
customer actually churn?) don't exist in this dataset to train against.
Instead it compares each customer's recency against their *own* historical
buying cadence:

```
avg_gap = mean(days between consecutive purchases)
risk_score = min(days_since_last_purchase / (avg_gap * 2.5), 1.0)
```

A customer who historically buys every 10 days and hasn't ordered in 40
scores much higher risk than a customer who has always bought roughly
quarterly and is 40 days out — the score is relative to their own
pattern, not a fixed threshold.

**Bands:** `risk_score >= 0.75` → High, `>= 0.4` → Medium, else Low.
Customers with zero purchase history get a flat `"New / No Purchases"`
label with `risk_score = 0.5` rather than an artificially high/low score.

**Consumed by:** the customer analytics dashboard, and the Milestone 4
executive summary's `high_churn_risk_customers` KPI (count of `"High"`
risk customers).

---

## 3. Product Recommendations

**Where:** `app/services/customer_analytics_service.py::recommend_for_customer`

**Method:** hybrid — combines two independently-computed lists:
- **Collaborative filtering** (`_collaborative_filtering`): finds
  customers with overlapping purchase history and recommends what similar
  customers bought that this customer hasn't.
- **Content-based filtering** (`_content_based`): recommends products
  similar (by category/attributes) to what the customer has purchased or
  viewed.

The two lists are merged, with popularity (`_popular_products`) as a
fallback for customers with too little history for either method to
produce results (cold-start handling).

---

## 4. Demand Forecast

**Where:** `app/services/analytics_service.py::simple_demand_forecast`

**Method:** a moving-average-style baseline over `days_history` (default
30) of a single product's sales, extended into a simple forward
projection. This is intentionally a baseline forecast, not a time-series
model (no ARIMA/Prophet) — the goal was a defensible, explainable number
for inventory reorder planning, not forecasting precision. The Milestone
3 `validation` module (`app/services/validation_service.py`) attaches a
confidence level and persists forecast history so forecast quality can be
tracked over time.

---

## 5. Revenue Intelligence — GMV & Growth

**Where:** `app/services/revenue_intelligence_service.py::gmv_and_growth`

**Method:** compares the trailing `period_days` window (default 30)
against the equal-length window immediately before it:

```
revenue_growth_pct = (current_period_revenue - previous_period_revenue)
                      / previous_period_revenue * 100
```

GMV (Gross Merchandise Value) is revenue plus discounts given — the total
value of merchandise transacted before marketplace commission/discounts
are netted out, distinct from net revenue.

This is the same function the Milestone 4 executive summary's
`revenue_growth_pct` KPI and `gmv` KPI call directly — no separate growth
calculation was introduced for the executive layer.

---

## 6. Milestone 4 — Executive Summary (composition, not a new model)

**Where:** `app/services/executive_report_service.py::executive_summary`

This is explicitly **not** a new analytical model — it's a composition
layer that calls the models/aggregations above (§1, §2, §5, plus
`analytics_service.sales_summary`, `vendor_performance`, `top_products`,
and `transactional_consistency_check`) and returns them as one payload.
Documented here for completeness since it's the main consumer-facing
surface for Milestone 4, and to make explicit that it introduces no new
statistical assumptions of its own — correctness of the underlying models
in §1–§5 is what determines correctness of the executive dashboard.

---

## 7. Model Governance (MLflow)

**Tracking URI:** `sqlite:///./mlflow.db` (configurable via
`MLFLOW_TRACKING_URI`). Every tracked segmentation run logs params
(`n_clusters`, `n_customers`, `features`), metrics (`inertia`,
`silhouette_score`), and the fitted estimator itself
(`mlflow.sklearn.log_model`), registered under the model name
`customer_segmentation_kmeans` in the MLflow Model Registry.

**Auditability:** in addition to MLflow, every tracked run also persists
an `MLModelRun` row and per-customer `CustomerSegmentSnapshot` rows in the
application database (`app/models/analytics_snapshot.py`), so segment
history is queryable via the API even if the MLflow server/store isn't
reachable — see `GET /api/v1/ml/segmentation/runs` and
`GET /api/v1/ml/segmentation/snapshots`.

**Retraining cadence:** weekly, via the APScheduler job described in
`ARCHITECTURE.md` §4 (`MODEL_RETRAIN_CRON_DAY_OF_WEEK`, off by default).
