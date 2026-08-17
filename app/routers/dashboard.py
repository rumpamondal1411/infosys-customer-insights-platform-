"""
Marketplace Reporting Dashboard.

Serves server-rendered HTML pages for ShopSense.
The dashboard uses the existing analytics JSON endpoints
and Chart.js on the frontend.
"""

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates


router = APIRouter(tags=["Frontend"])

templates = Jinja2Templates(directory="app/templates")


# ============================================================
# MAIN PAGES
# ============================================================

@router.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        "home.html",
        {"request": request}
    )


@router.get("/login")
def login(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request}
    )


@router.get("/register-page")
def register_page(request: Request):
    return templates.TemplateResponse(
        "register.html",
        {"request": request}
    )


# ============================================================
# MARKETPLACE DASHBOARD
# ============================================================

@router.get("/dashboard")
def marketplace_dashboard(request: Request):
    """
    Main Marketplace Reporting Dashboard.

    This route is required by the Milestone 1 dashboard test.

    It visualizes:
    - Vendor revenue
    - Category revenue
    - Top products
    - Marketplace sales metrics
    """
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request}
    )


# ============================================================
# ADMIN PAGES
# ============================================================

@router.get("/admin-dashboard")
def admin_dashboard(request: Request):
    return templates.TemplateResponse(
        "admin_dashboard.html",
        {"request": request}
    )


@router.get("/admin-login")
def admin_login(request: Request):
    return templates.TemplateResponse(
        "admin_login.html",
        {"request": request}
    )


@router.get("/update-profile")
def update_profile(request: Request):
    return templates.TemplateResponse(
        "update_profile.html",
        {"request": request}
    )


@router.get("/vendors-page")
def vendors_page(request: Request):
    return templates.TemplateResponse(
        "vendors.html",
        {"request": request}
    )


# ============================================================
# VENDOR PAGES
# ============================================================

@router.get("/vendor-dashboard")
def vendor_dashboard(request: Request):
    return templates.TemplateResponse(
        "vendor_dashboard.html",
        {"request": request}
    )


@router.get("/add-product")
def add_product(request: Request):
    return templates.TemplateResponse(
        "add_product.html",
        {"request": request}
    )


@router.get("/change-password")
def change_password_page(request: Request):
    return templates.TemplateResponse(
        "change_password.html",
        {"request": request}
    )


@router.get("/vendor-settings")
def vendor_settings_page(request: Request):
    return templates.TemplateResponse(
        "vendor_settings.html",
        {"request": request}
    )


@router.get("/vendor-inventory-alerts")
def vendor_inventory_alerts_page(request: Request):
    return templates.TemplateResponse(
        "vendor_inventory_alerts.html",
        {"request": request}
    )


@router.get("/vendor-cancelled-orders")
def vendor_cancelled_orders_page(request: Request):
    return templates.TemplateResponse(
        "vendor_cancelled_orders.html",
        {"request": request}
    )


@router.get("/vendor-returned-orders")
def vendor_returned_orders_page(request: Request):
    return templates.TemplateResponse(
        "vendor_returned_orders.html",
        {"request": request}
    )


@router.get("/vendor-dev-tools")
def vendor_dev_tools_page(request: Request):
    return templates.TemplateResponse(
        "vendor_dev_tools.html",
        {"request": request}
    )


@router.get("/my-products")
def my_products(request: Request):
    return templates.TemplateResponse(
        "my_products.html",
        {"request": request}
    )


@router.get("/edit-product")
def edit_product(request: Request):
    return templates.TemplateResponse(
        "edit_product.html",
        {"request": request}
    )


@router.get("/vendor-benchmark-page")
def vendor_benchmark_page(request: Request):
    """Vendor performance compared with marketplace."""
    return templates.TemplateResponse(
        "vendor_benchmark.html",
        {"request": request}
    )


@router.get("/vendor-analytics-page")
def vendor_analytics_page(request: Request):
    """
    Vendor-facing Analytics page.

    Shows vendor revenue trend, top products,
    category mix and order-status mix.
    """
    return templates.TemplateResponse(
        "vendor_analytics.html",
        {"request": request}
    )


# ============================================================
# PRODUCT / INVENTORY / TRANSACTION PAGES
# ============================================================

@router.get("/categories-page")
def categories_page(request: Request):
    return templates.TemplateResponse(
        "categories.html",
        {"request": request}
    )


@router.get("/inventory-page")
def inventory_page(request: Request):
    return templates.TemplateResponse(
        "inventory.html",
        {"request": request}
    )


@router.get("/update-stock")
def update_stock(request: Request):
    return templates.TemplateResponse(
        "update_stock.html",
        {"request": request}
    )


@router.get("/transactions-page")
def transactions_page(request: Request):
    return templates.TemplateResponse(
        "transactions.html",
        {"request": request}
    )


@router.get("/analytics-page")
def analytics_page(request: Request):
    return templates.TemplateResponse(
        "analytics.html",
        {"request": request}
    )


@router.get("/reports-page")
def reports_page(request: Request):
    return templates.TemplateResponse(
        "reports.html",
        {"request": request}
    )


# ============================================================
# CUSTOMER PAGES
# ============================================================

@router.get("/customer-login")
def customer_login_page(request: Request):
    return templates.TemplateResponse(
        "customer_login.html",
        {"request": request}
    )


@router.get("/customer-register")
def customer_register_page(request: Request):
    return templates.TemplateResponse(
        "customer_register.html",
        {"request": request}
    )


@router.get("/customer-dashboard")
def customer_dashboard_page(request: Request):
    return templates.TemplateResponse(
        "customer_dashboard.html",
        {"request": request}
    )


@router.get("/customer-profile-page")
def customer_profile_page(request: Request):
    return templates.TemplateResponse(
        "customer_profile.html",
        {"request": request}
    )


# ============================================================
# ANALYTICS / INTELLIGENCE PAGES
# ============================================================

@router.get("/revenue-intelligence-page")
def revenue_intelligence_page(request: Request):
    return templates.TemplateResponse(
        "revenue_intelligence.html",
        {"request": request}
    )


@router.get("/inventory-forecast-page")
def inventory_forecast_page(request: Request):
    return templates.TemplateResponse(
        "inventory_forecast.html",
        {"request": request}
    )


@router.get("/customer-analytics-page")
def customer_analytics_page(request: Request):
    return templates.TemplateResponse(
        "customer_analytics.html",
        {"request": request}
    )


@router.get("/validation-page")
def validation_page(request: Request):
    return templates.TemplateResponse(
        "validation.html",
        {"request": request}
    )


# ============================================================
# BUSINESS INTELLIGENCE
# ============================================================

@router.get("/bi-dashboard")
def bi_dashboard_page(request: Request):
    """Milestone 3 — Business Intelligence dashboard."""
    return templates.TemplateResponse(
        "bi_dashboard.html",
        {"request": request}
    )


@router.get("/executive-dashboard")
def executive_dashboard_page(request: Request):
    """Milestone 4 — Executive Dashboard."""
    return templates.TemplateResponse(
        "executive_dashboard.html",
        {"request": request}
    )


# ============================================================
# BENCHMARKING
# ============================================================

@router.get("/admin-benchmark-page")
def admin_benchmark_page(request: Request):
    """Marketplace benchmarking page for administrators."""
    return templates.TemplateResponse(
        "admin_benchmark.html",
        {"request": request}
    )


# ============================================================
# SYSTEM HEALTH
# ============================================================

@router.get("/system-health-page")
def system_health_page(request: Request):
    """System Health page for Admin."""
    return templates.TemplateResponse(
        "system_health.html",
        {"request": request}
    )
@router.get("/system-health")
def system_health_alias(request: Request):
    """
    Alias so /system-health resolves directly (the sidebar link and the
    canonical route both live under /admin/system-health — this exists
    because /system-health with no prefix 404s otherwise, which is the
    'Not Found' seen when hitting that URL directly).
    """
    return templates.TemplateResponse(
        "system_health.html",
        {"request": request}
    )