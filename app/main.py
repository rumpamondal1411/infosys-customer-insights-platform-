"""
ShopSense — Multi-Vendor E-Commerce Analytics Platform
Week 1: Marketplace Foundation & Vendor Analytics
active virtual environment: .\.venv\Scripts\Activate.ps1
FastAPI application entrypoint. Run with:
    python -m uvicorn app.main:app --reload
or:
    python run.py
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import (
    vendors, products, inventory, transactions, analytics, dashboard, auth, admin, customer,
    promotions, revenue_intelligence, customer_analytics, validation, analytics_api, executive_reports,
)
from app.scheduler import start_scheduler, shutdown_scheduler
from fastapi.staticfiles import StaticFiles




app = FastAPI(
    title="ShopSense API",
    description=(
        "Multi-Vendor E-Commerce Analytics Platform — Week 1: Vendor Management, "
        "Marketplace Onboarding, Product & Inventory Analytics Engine."
    ),
    version="0.1.0",
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vendors.router)
app.include_router(products.router)
app.include_router(inventory.router)
app.include_router(transactions.router)
app.include_router(analytics.router)
app.include_router(dashboard.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(customer.router)
app.include_router(promotions.router)
app.include_router(revenue_intelligence.router)
app.include_router(customer_analytics.router)
app.include_router(validation.router)
app.include_router(analytics_api.router)
app.include_router(executive_reports.router)

@app.on_event("startup")
def on_startup():
    init_db()
    start_scheduler()


@app.on_event("shutdown")
def on_shutdown():
    shutdown_scheduler()


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
