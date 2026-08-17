// Milestone 4 — Executive Dashboard client logic.
// Vanilla JS + Chart.js, same pattern as dashboard.js / bi_dashboard's inline script.

let execTrendChart = null;
let execSegmentChart = null;

function setExecStatus(msg, isError = false) {
    const el = document.getElementById("execStatus");
    if (!el) return;
    el.textContent = msg;
    el.style.color = isError ? "#dc2626" : "#2563eb";
}

function kpiCard(label, value) {
    return `
        <div style="background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:16px; text-align:center;">
            <div style="font-size:13px; color:#6b7280; margin-bottom:6px;">${label}</div>
            <div style="font-size:22px; font-weight:700; color:#111827;">${value}</div>
        </div>
    `;
}

function formatCurrency(n) {
    if (n === null || n === undefined) return "—";
    return "$" + Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

async function loadExecutiveDashboard() {
    setExecStatus("Loading executive summary...");
    const periodDays = document.getElementById("periodSelect").value;

    try {
        const [summaryRes, trendRes] = await Promise.all([
            fetch(`/api/v1/executive/summary?period_days=${periodDays}`),
            fetch(`/api/v1/executive/kpi-trend?months=6`),
        ]);

        if (!summaryRes.ok) throw new Error(`summary request failed (${summaryRes.status})`);
        if (!trendRes.ok) throw new Error(`kpi-trend request failed (${trendRes.status})`);

        const summary = await summaryRes.json();
        const trend = await trendRes.json();

        // Each section renders independently — a failure in one (e.g. Chart.js
        // not loading from the CDN) must not prevent the others from showing.
        try { renderKpiCards(summary); } catch (e) { console.error("renderKpiCards failed", e); }
        try { renderTopVendors(summary.top_vendor_performance || []); } catch (e) { console.error("renderTopVendors failed", e); }
        try { renderTrendChart(trend); } catch (e) { console.error("renderTrendChart failed", e); }
        try { renderSegmentChart(summary.customer_segment_mix || []); } catch (e) { console.error("renderSegmentChart failed", e); }

        setExecStatus(`Updated: ${new Date(summary.generated_at).toLocaleString()}`);
    } catch (err) {
        console.error(err);
        setExecStatus(`Failed to load executive dashboard: ${err.message}`, true);
        const tbody = document.querySelector("#execTopVendorsTable tbody");
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="4" style="color:#dc2626;">Could not load vendor performance data. Check your connection and refresh.</td></tr>`;
        }
    }
}

function renderKpiCards(summary) {
    const grid = document.getElementById("kpiGrid");
    if (!grid) return;
    const k = summary.kpis || {};
    const growthLabel = `${k.revenue_growth_pct > 0 ? "▲" : "▼"} ${k.revenue_growth_pct}%`;

    grid.innerHTML = [
        kpiCard("Total Revenue", formatCurrency(k.total_revenue)),
        kpiCard("Total Orders", k.total_orders ?? "—"),
        kpiCard("GMV", formatCurrency(k.gmv)),
        kpiCard("Avg Order Value", formatCurrency(k.average_order_value)),
        kpiCard("Revenue Growth", growthLabel),
        kpiCard("Active Vendors", k.active_vendor_count ?? "—"),
        kpiCard(
            "High Churn-Risk Customers",
            k.high_churn_risk_customers === null || k.high_churn_risk_customers === undefined
                ? "N/A"
                : k.high_churn_risk_customers
        ),
        kpiCard(
            "Top Vendor",
            summary.top_vendor ? summary.top_vendor.business_name : "—"
        ),
    ].join("");
}

function renderTopVendors(vendors) {
    const tbody = document.querySelector("#execTopVendorsTable tbody");
    if (!tbody) return;
    if (!vendors.length) {
        tbody.innerHTML = `<tr><td colspan="4">No vendor sales data yet.</td></tr>`;
        return;
    }
    const medals = ["🥇", "🥈", "🥉"];
    tbody.innerHTML = vendors
        .map(
            (v, i) => `
        <tr>
            <td>${medals[i] || i + 1}</td>
            <td>${v.business_name ?? "—"}</td>
            <td>${formatCurrency(v.total_revenue)}</td>
            <td>${v.total_orders ?? v.order_count ?? "—"}</td>
        </tr>`
        )
        .join("");
}

function renderTrendChart(trend) {
    const ctx = document.getElementById("execTrendChart");
    if (!ctx) return;
    const labels = trend.map((r) => r.month);
    const revenue = trend.map((r) => r.revenue);

    if (execTrendChart) execTrendChart.destroy();
    execTrendChart = new Chart(ctx, {
        type: "line",
        data: {
            labels,
            datasets: [
                {
                    label: "Monthly Revenue",
                    data: revenue,
                    borderColor: "#2563eb",
                    backgroundColor: "rgba(37,99,235,0.1)",
                    tension: 0.3,
                    fill: true,
                },
            ],
        },
        options: { responsive: true, plugins: { legend: { display: false } } },
    });
}

function renderSegmentChart(segments) {
    const ctx = document.getElementById("execSegmentChart");
    if (!ctx) return;
    const labels = segments.map((s) => s.segment);
    const counts = segments.map((s) => s.customer_count);

    if (execSegmentChart) execSegmentChart.destroy();
    execSegmentChart = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels,
            datasets: [
                {
                    data: counts,
                    backgroundColor: ["#2563eb", "#16a34a", "#f59e0b", "#dc2626", "#7c3aed", "#0891b2"],
                },
            ],
        },
        options: { responsive: true },
    });
}

async function exportExecutiveReport() {
    setExecStatus("Generating executive workbook...");
    const periodDays = document.getElementById("periodSelect").value;
    try {
        const res = await fetch(`/api/v1/executive/export?period_days=${periodDays}`);
        if (!res.ok) throw new Error(`export failed (${res.status})`);
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "executive_report.xlsx";
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
        setExecStatus("Executive report downloaded.");
    } catch (err) {
        console.error(err);
        setExecStatus(`Export failed: ${err.message}`, true);
    }
}
