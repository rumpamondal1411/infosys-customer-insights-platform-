"""
Locust load test for ShopSense.

This is a dev-only tool, not part of the app itself — run it manually
against a live server to see how the API behaves under concurrent load.

Usage:
    locust -f locustfile.py --host=http://127.0.0.1:8000

Then open http://localhost:8089 in a browser to set the number of
users and spawn rate, and watch live response-time / RPS charts.
"""
from locust import HttpUser, task, between


class ShopSenseUser(HttpUser):

    wait_time = between(1, 3)

    @task(3)
    def view_products(self):
        self.client.get("/products")

    @task(2)
    def view_vendors(self):
        self.client.get("/vendors")

    @task(2)
    def executive_summary(self):
        self.client.get("/api/v1/executive/summary")

    @task(1)
    def api_docs(self):
        self.client.get("/docs")