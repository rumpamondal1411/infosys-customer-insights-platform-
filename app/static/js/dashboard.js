async function loadKPIs() {

    const res = await fetch("/analytics/sales-summary");

    const data = await res.json();

    document.getElementById("revenue").innerText =
        "$" + data.total_revenue;

    document.getElementById("orders").innerText =
        data.total_orders;

    document.getElementById("customers").innerText =
        data.unique_customers;

    document.getElementById("vendors").innerText =
        data.active_vendors;
}

loadKPIs();