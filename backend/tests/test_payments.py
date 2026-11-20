from datetime import date, timedelta


def _subscription(client, auth, customer, plan, **extra):
    response = client.post(
        "/api/subscriptions",
        headers=auth("sales"),
        json={"customer_id": customer.id, "plan_id": plan.id, **extra},
    )
    assert response.status_code == 201
    return response.get_json()


def test_record_payment(client, auth, customer, plans):
    sub = _subscription(client, auth, customer, plans["monthly"])
    response = client.post(
        "/api/payments",
        headers=auth("billing"),
        json={"subscription_id": sub["id"], "amount": 50, "status": "paid", "method": "upi", "reference": "UPI-77"},
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["status"] == "paid"
    assert body["paid_on"] == date.today().isoformat()
    assert body["subscription"]["id"] == sub["id"]
    detail = client.get(f"/api/subscriptions/{sub['id']}", headers=auth("admin")).get_json()
    assert detail["payment_status"] == "paid"
    assert len(detail["payments"]) == 2


def test_update_payment_status_syncs_subscription(client, auth, customer, plans):
    sub = _subscription(client, auth, customer, plans["monthly"])
    payment_id = sub["payments"][0]["id"]

    paid = client.put(f"/api/payments/{payment_id}", headers=auth("billing"), json={"status": "paid", "method": "cash"})
    assert paid.status_code == 200
    assert paid.get_json()["paid_on"] == date.today().isoformat()
    detail = client.get(f"/api/subscriptions/{sub['id']}", headers=auth("admin")).get_json()
    assert detail["payment_status"] == "paid"

    failed = client.put(f"/api/payments/{payment_id}", headers=auth("billing"), json={"status": "failed"})
    assert failed.get_json()["status"] == "failed"
    assert failed.get_json()["paid_on"] is None
    detail = client.get(f"/api/subscriptions/{sub['id']}", headers=auth("admin")).get_json()
    assert detail["payment_status"] == "failed"


def test_failed_payment_creates_notification(client, auth, customer, plans):
    sub = _subscription(client, auth, customer, plans["monthly"])
    client.put(f"/api/payments/{sub['payments'][0]['id']}", headers=auth("billing"), json={"status": "failed"})
    notes = client.get("/api/notifications", headers=auth("billing")).get_json()
    assert any(n["category"] == "payment" for n in notes["items"])


def test_payment_validation(client, auth, customer, plans):
    sub = _subscription(client, auth, customer, plans["monthly"])
    bad_status = client.post("/api/payments", headers=auth("billing"),
                             json={"subscription_id": sub["id"], "status": "refunded"})
    assert bad_status.status_code == 422
    bad_amount = client.post("/api/payments", headers=auth("billing"),
                             json={"subscription_id": sub["id"], "amount": -5})
    assert bad_amount.status_code == 422
    future = client.post("/api/payments", headers=auth("billing"),
                         json={"subscription_id": sub["id"], "status": "paid",
                               "paid_on": (date.today() + timedelta(days=3)).isoformat()})
    assert future.status_code == 422


def test_pending_payments_filter_and_summary(client, auth, customer, other_customer, plans):
    _subscription(client, auth, customer, plans["monthly"])
    _subscription(client, auth, other_customer, plans["quarterly"], payment={"status": "paid"})
    body = client.get("/api/payments?status=pending", headers=auth("billing")).get_json()
    assert body["total"] == 1
    assert body["items"][0]["amount"] == 50
    assert body["summary"]["pending"]["amount"] == 50
    assert body["summary"]["paid"]["amount"] == 140


def test_overdue_payments_filter(client, auth, customer, plans):
    _subscription(client, auth, customer, plans["monthly"],
                  start_date=(date.today() - timedelta(days=10)).isoformat())
    body = client.get("/api/payments?overdue=true", headers=auth("billing")).get_json()
    assert body["total"] == 1
    assert body["items"][0]["is_overdue"] is True


def test_revenue_uses_only_paid_payments(client, auth, customer, other_customer, plans):
    _subscription(client, auth, customer, plans["monthly"], payment={"status": "paid"})
    _subscription(client, auth, other_customer, plans["yearly"])  # pending
    dashboard = client.get("/api/dashboard", headers=auth("admin")).get_json()
    assert dashboard["stats"]["monthly_revenue"] == 50
    assert dashboard["stats"]["pending_amount"] == 1000
    report = client.get("/api/reports/summary", headers=auth("admin")).get_json()
    assert report["totals"]["revenue"] == 50
    assert report["totals"]["pending_count"] == 1
