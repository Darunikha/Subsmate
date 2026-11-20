def _plan(client, auth, **overrides):
    payload = {"name": "Growth", "price": 99.5, "billing_cycle": "monthly",
               "description": "For growing teams", "features": ["A", "B", " "]}
    payload.update(overrides)
    return client.post("/api/plans", headers=auth("admin"), json=payload)


def test_plan_crud(client, auth):
    created = _plan(client, auth)
    assert created.status_code == 201
    plan = created.get_json()
    assert plan["features"] == ["A", "B"]
    assert plan["price"] == 99.5

    updated = client.put(f"/api/plans/{plan['id']}", headers=auth("admin"),
                         json={"price": 120, "status": "inactive", "features": "X\nY"})
    assert updated.status_code == 200
    assert updated.get_json()["features"] == ["X", "Y"]
    assert updated.get_json()["status"] == "inactive"

    assert client.delete(f"/api/plans/{plan['id']}", headers=auth("admin")).status_code == 204


def test_plan_validation_and_duplicates(client, auth):
    assert _plan(client, auth, billing_cycle="weekly").status_code == 422
    assert _plan(client, auth, price="abc").status_code == 422
    assert _plan(client, auth).status_code == 201
    assert _plan(client, auth, name="growth").status_code == 409


def test_plan_with_subscriptions_cannot_be_deleted(client, auth, customer, plans):
    client.post("/api/subscriptions", headers=auth("sales"),
                json={"customer_id": customer.id, "plan_id": plans["monthly"].id})
    assert client.delete(f"/api/plans/{plans['monthly'].id}", headers=auth("admin")).status_code == 409
    response = client.put(f"/api/plans/{plans['monthly'].id}", headers=auth("admin"), json={"billing_cycle": "yearly"})
    assert response.status_code == 400


def test_report_summary_and_csv_export(client, auth, customer, plans):
    client.post("/api/subscriptions", headers=auth("sales"),
                json={"customer_id": customer.id, "plan_id": plans["monthly"].id, "payment": {"status": "paid"}})
    summary = client.get("/api/reports/summary", headers=auth("admin")).get_json()
    assert summary["totals"]["active_subscriptions"] == 1
    assert summary["plan_popularity"][0]["plan"] == "Basic Monthly"
    assert len(summary["monthly_revenue"]) == 12

    for report in ("revenue", "payments", "pending-payments", "subscriptions", "plans", "renewals", "customers"):
        response = client.get(f"/api/reports/export/{report}", headers=auth("admin"))
        assert response.status_code == 200, report
        assert response.mimetype == "text/csv"
        assert len(response.data.decode().splitlines()) >= 1

    rows = client.get("/api/reports/export/subscriptions", headers=auth("admin")).data.decode().splitlines()
    assert "Cara Customer" in rows[1]
    assert client.get("/api/reports/export/unknown", headers=auth("admin")).status_code == 404


def test_report_date_range_validation(client, auth):
    response = client.get("/api/reports/summary?from=2026-05-01&to=2026-01-01", headers=auth("admin"))
    assert response.status_code == 422


def test_health_and_metrics(client):
    assert client.get("/api/health").get_json() == {"status": "ok"}
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert b"subsmate_subscriptions" in metrics.data
