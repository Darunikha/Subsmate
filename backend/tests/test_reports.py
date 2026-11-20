def _subscribe(client, auth, customer, service, **extra):
    return client.post("/api/subscriptions", headers=auth("staff"),
                       json={"customer_id": customer.id, **service.payload(**extra)})


def test_report_summary_and_csv_export(client, auth, customer, services):
    _subscribe(client, auth, customer, services["monthly"], payment={"status": "paid"})
    summary = client.get("/api/reports/summary", headers=auth("admin")).get_json()
    assert summary["totals"]["active_subscriptions"] == 1
    assert summary["service_popularity"][0]["service"] == "Basic Monthly"
    assert len(summary["monthly_revenue"]) == 12

    for report in ("revenue", "payments", "pending-payments", "subscriptions", "services", "renewals", "customers"):
        response = client.get(f"/api/reports/export/{report}", headers=auth("admin"))
        assert response.status_code == 200, report
        assert response.mimetype == "text/csv"
        assert len(response.data.decode().splitlines()) >= 1

    rows = client.get("/api/reports/export/subscriptions", headers=auth("admin")).data.decode().splitlines()
    assert "Cara Customer" in rows[1]
    assert "Basic Monthly" in rows[1]
    assert client.get("/api/reports/export/unknown", headers=auth("admin")).status_code == 404


def test_service_popularity_groups_names_ignoring_case(client, auth, customer, other_customer, services):
    _subscribe(client, auth, customer, services["monthly"])
    _subscribe(client, auth, other_customer, services["monthly"], service_name="basic monthly")
    _subscribe(client, auth, other_customer, services["yearly"])
    rows = client.get("/api/reports/summary", headers=auth("admin")).get_json()["service_popularity"]
    by_name = {r["service"].lower(): r for r in rows}
    assert len(rows) == 2
    assert by_name["basic monthly"]["subscriptions"] == 2
    assert by_name["basic monthly"]["active"] == 2


def test_report_date_range_validation(client, auth):
    response = client.get("/api/reports/summary?from=2026-05-01&to=2026-01-01", headers=auth("admin"))
    assert response.status_code == 422


def test_health_and_metrics(client):
    assert client.get("/api/health").get_json() == {"status": "ok"}
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert b"subsmate_subscriptions" in metrics.data
