"""Prometheus metrics: HTTP traffic plus business gauges computed at scrape time."""
import time

from flask import Response, g, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

REQUESTS = Counter(
    "subsmate_http_requests_total", "HTTP requests", ["method", "endpoint", "status"]
)
LATENCY = Histogram(
    "subsmate_http_request_duration_seconds", "HTTP request latency", ["method", "endpoint"]
)
SUBSCRIPTIONS = Gauge("subsmate_subscriptions", "Subscriptions by status", ["status"])
CUSTOMERS = Gauge("subsmate_customers_total", "Registered customers")
PENDING = Gauge("subsmate_pending_payments", "Payments awaiting settlement")
PENDING_AMOUNT = Gauge("subsmate_pending_payment_amount", "Amount awaiting settlement")
REVENUE_MONTH = Gauge("subsmate_revenue_current_month", "Paid revenue in the current month")


def init_metrics(app):
    @app.before_request
    def _start_timer():
        g._metrics_start = time.perf_counter()

    @app.after_request
    def _record(response):
        endpoint = request.endpoint or "unmatched"
        if endpoint != "metrics":
            start = getattr(g, "_metrics_start", None)
            if start is not None:
                LATENCY.labels(request.method, endpoint).observe(time.perf_counter() - start)
            REQUESTS.labels(request.method, endpoint, response.status_code).inc()
        return response

    @app.get("/metrics", endpoint="metrics")
    def metrics():
        from sqlalchemy import func

        from .extensions import db
        from .models import Customer, Payment
        from .services.analytics import count_by_status, revenue_between
        from .services.dates import today

        for status, count in count_by_status().items():
            SUBSCRIPTIONS.labels(status).set(count)
        CUSTOMERS.set(Customer.query.count())
        count, amount = db.session.query(
            func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0)
        ).filter(Payment.status == "pending").one()
        PENDING.set(count)
        PENDING_AMOUNT.set(float(amount))
        REVENUE_MONTH.set(revenue_between(today().replace(day=1), today()))
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
