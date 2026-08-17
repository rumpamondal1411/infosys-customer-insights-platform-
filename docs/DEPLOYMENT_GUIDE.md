# ShopSense — Deployment Guide

## 1. Local Development (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # if execution policy blocks this, use .\.venv\Scripts\activate.bat instead
pip install -r requirements.txt
copy .env.example .env
python run.py                       # or: python -m uvicorn app.main:app --reload
```

App runs at `http://localhost:8000`. Interactive API docs at `/docs`.
Default `DATABASE_URL` is `sqlite:///./data/shopsense.db` — no external
DB needed for local dev.

To seed demo data:
```powershell
python -m app.utils.seed_data
```

---

## 2. Environment Variables

All settings are defined in `app/config.py` and loaded from `.env` (see
`.env.example` for the full template):

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/shopsense.db` | Point at PostgreSQL for production: `postgresql+psycopg2://user:pass@host:5432/db` |
| `APP_ENV` | `development` | Set to `production` in deployed environments |
| `MLFLOW_TRACKING_URI` | `sqlite:///./mlflow.db` | Where MLflow experiment runs are logged |
| `MLFLOW_EXPERIMENT_NAME` | `shopsense-analytics` | |
| `ENABLE_SCHEDULER` | `false` | Set `true` to enable nightly ETL/report/retrain jobs — leave `false` in CI/tests for determinism |
| `ETL_CRON_HOUR` / `ETL_CRON_MINUTE` | `2` / `0` | Nightly ETL run time (UTC) |
| `MODEL_RETRAIN_CRON_DAY_OF_WEEK` | `sun` | Weekly segmentation retrain day |
| `REPORTS_EXPORT_DIR` | `reports/exports` | Milestone 3 on-demand export destination |

Milestone 4's executive reports write to `reports/executive/` (created
automatically) — no new environment variable needed.

---

## 3. Docker

`Dockerfile` builds a `python:3.11-slim` image, installs
`libpq-dev`/`gcc` (needed by `psycopg2-binary` and pandas/scikit-learn
wheels), installs `requirements.txt`, and runs:

```
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Build and run standalone (SQLite, single container):
```bash
docker build -t shopsense .
docker run -p 8000:8000 -v $(pwd)/data:/app/data -v $(pwd)/reports:/app/reports shopsense
```

### 3.1 Docker Compose (app + PostgreSQL)

`docker-compose.yml` brings up a `postgres:16-alpine` service plus the app,
wired together via `DATABASE_URL`:

```bash
docker compose up --build
```

- `db` — Postgres 16, healthchecked before the app starts
- `app` — builds from the local `Dockerfile`, `ENABLE_SCHEDULER=true` (so
  nightly ETL/report/retrain actually run in a persistent deployment),
  mounts `./reports`, `./mlruns`, and `./app/static/uploads` as volumes so
  generated reports/models/images survive container restarts

This is the recommended way to demo a "production-like" deployment —
Postgres instead of SQLite, scheduler on, everything containerized.

---

## 4. CI/CD

`.github/workflows/ci.yml` runs on every push/PR to `main`:

1. **lint-and-test** — installs dependencies, runs `flake8` (non-blocking:
   `--exit-zero`), seeds demo data and runs the data-validation report as
   a smoke check, runs the full `pytest` suite (`--maxfail=1`), then
   smoke-tests the ETL pipeline end-to-end.
2. **docker-build** — (depends on `lint-and-test` passing) builds the
   Docker image with Buildx and GitHub Actions layer caching, without
   pushing anywhere.

Milestone 4's new test files (`test_integration_e2e.py`,
`test_performance.py`, `test_regression.py`, `test_executive_reports.py`)
run automatically as part of step 1's `pytest` — no CI config changes
were needed since they follow the existing `tests/` convention and use
the shared `conftest.py` fixtures.

To extend CI with a dedicated performance-test gate (optional, not
currently configured), add a separate step:
```yaml
      - name: Performance regression checks
        run: pytest -v tests/test_performance.py
```

---

## 5. Production Checklist

- [ ] Switch `DATABASE_URL` to PostgreSQL (see `docker-compose.yml` for
      the connection string format)
- [ ] Set `ENABLE_SCHEDULER=true` so nightly ETL/report/retrain jobs run
- [ ] Set `APP_ENV=production`
- [ ] Mount persistent volumes for `data/` (if still using SQLite
      anywhere), `reports/`, `mlruns/`, and `app/static/uploads/`
- [ ] Put a reverse proxy (nginx/Caddy) in front of uvicorn for TLS —
      not included in this repo, since it's environment-specific
- [ ] Review `CORSMiddleware` in `app/main.py` — `allow_origins=["*"]` is
      fine for a course demo, tighten it before any real deployment
- [ ] Confirm `reports/executive/` (Milestone 4 exports) is writable and,
      ideally, periodically cleaned up or excluded from version control

---

## 6. Manual Performance / Load Testing

The automated `tests/test_performance.py` suite catches regressions on
every CI run, but for a true load test against a running instance (e.g.
before a mentor demo with a large seeded dataset), a simple approach with
no new dependencies:

```powershell
# Windows PowerShell — 50 concurrent GETs against the executive summary
1..50 | ForEach-Object -Parallel {
    Invoke-WebRequest -Uri "http://localhost:8000/api/v1/executive/summary" -UseBasicParsing
} -ThrottleLimit 10
```

For a more thorough load test, `locust` or `k6` can be added as a dev-only
dependency, but neither is required for the automated regression checks
this milestone adds.
