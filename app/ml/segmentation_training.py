"""
Milestone 3 — versioned, tracked training job for the customer segmentation
model that Milestone 2 introduced (RFM + KMeans).

This does NOT replace `customer_analytics_service.segment_customers`, which
stays the fast, request-time path used by the live dashboard. This module
is the *tracked* training job: it fits the same kind of model but logs the
run to MLflow (params, metrics, the fitted estimator) and registers it in
the MLflow Model Registry, then stores a point-in-time snapshot of the
resulting segments in the database so results are auditable without
needing the MLflow server to be reachable.
"""
from datetime import datetime

import mlflow
import mlflow.sklearn
from sqlalchemy.orm import Session

from app.ml.mlflow_utils import configure_mlflow
from app.services.customer_analytics_service import _rfm_features, MIN_CUSTOMERS_FOR_CLUSTERING
from app.models.analytics_snapshot import CustomerSegmentSnapshot, MLModelRun

MODEL_NAME = "customer_segmentation_kmeans"


def train_and_register(db: Session, n_clusters: int = 4) -> dict:
    configure_mlflow()

    rfm = _rfm_features(db)
    if rfm.empty or rfm.shape[0] < MIN_CUSTOMERS_FOR_CLUSTERING:
        return {
            "trained": False,
            "reason": "Not enough customer purchase history for a meaningful clustering run "
                      f"(need >= {MIN_CUSTOMERS_FOR_CLUSTERING} customers with activity).",
        }

    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    feature_cols = ["recency_days", "frequency", "monetary", "views"]
    X = rfm[feature_cols].copy()
    X["recency_days"] = X["recency_days"].clip(upper=365)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    k = min(n_clusters, rfm.shape[0] - 1) if rfm.shape[0] > 1 else 1
    k = max(k, 2)

    with mlflow.start_run(run_name=f"segmentation-{datetime.utcnow():%Y%m%d-%H%M%S}") as run:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        cluster_ids = kmeans.fit_predict(X_scaled)
        rfm = rfm.copy()
        rfm["cluster_id"] = cluster_ids

        inertia = float(kmeans.inertia_)
        try:
            silhouette = float(silhouette_score(X_scaled, cluster_ids)) if k > 1 else 0.0
        except ValueError:
            silhouette = 0.0

        params = {"n_clusters": k, "n_customers": int(rfm.shape[0]), "features": ",".join(feature_cols)}
        metrics = {"inertia": inertia, "silhouette_score": silhouette}

        mlflow.log_params(params)
        mlflow.log_metrics(metrics)
        mlflow.sklearn.log_model(kmeans, artifact_path="model", registered_model_name=MODEL_NAME)

        run_id = run.info.run_id

    # Rank clusters by monetary value to reuse the same human labels as the
    # live dashboard, then persist a versioned snapshot.
    cluster_summary = rfm.groupby("cluster_id")[feature_cols].mean()
    ranked = cluster_summary.sort_values(by=["monetary", "frequency"], ascending=False).index.tolist()
    label_by_cluster = {}
    for rank, cid in enumerate(ranked):
        if rank == 0:
            label_by_cluster[cid] = "Champions"
        elif rank == len(ranked) - 1:
            label_by_cluster[cid] = "Low Engagement"
        else:
            label_by_cluster[cid] = "Loyal Customers"
    rfm["segment"] = rfm["cluster_id"].map(label_by_cluster)

    model_run = MLModelRun(
        model_name=MODEL_NAME,
        mlflow_run_id=run_id,
        version=None,  # set by the registry; fetched separately via get_latest_model_version
        params=params,
        metrics=metrics,
        trained_at=datetime.utcnow(),
        registered=True,
    )
    db.add(model_run)
    db.commit()
    db.refresh(model_run)

    for _, row in rfm.iterrows():
        db.add(CustomerSegmentSnapshot(
            pipeline_run_id=None,
            customer_id=int(row["customer_id"]),
            segment_label=row["segment"],
            recency_days=float(row["recency_days"]),
            frequency=float(row["frequency"]),
            monetary=float(row["monetary"]),
            snapshot_date=datetime.utcnow(),
        ))
    db.commit()

    return {
        "trained": True,
        "mlflow_run_id": run_id,
        "model_name": MODEL_NAME,
        "params": params,
        "metrics": metrics,
        "customers_segmented": int(rfm.shape[0]),
    }


def list_model_runs(db: Session, model_name: str = MODEL_NAME, limit: int = 20):
    return (
        db.query(MLModelRun)
        .filter(MLModelRun.model_name == model_name)
        .order_by(MLModelRun.trained_at.desc())
        .limit(limit)
        .all()
    )


def get_latest_registered_version(model_name: str = MODEL_NAME):
    """Queries the MLflow Model Registry for the most recent version."""
    configure_mlflow()
    client = mlflow.tracking.MlflowClient()
    try:
        versions = client.search_model_versions(f"name='{model_name}'")
    except Exception:
        return None
    if not versions:
        return None
    latest = sorted(versions, key=lambda v: int(v.version), reverse=True)[0]
    return {
        "name": model_name,
        "version": latest.version,
        "run_id": latest.run_id,
        "status": latest.status,
        "creation_timestamp": latest.creation_timestamp,
    }
