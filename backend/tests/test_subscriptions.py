from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models import Payment, RenewalHistory, Subscription
from app.services.dates import add_months, calculate_expiry


# ----------------------------------------------------------------- expiry calculation
@pytest.mark.parametrize(
    "start, cycle, expected",
    [
        (date(2025, 1, 15), "monthly", date(2025, 2, 15)),
        (date(2025, 1, 31), "monthly", date(2025, 2, 28)),
        (date(2024, 1, 31), "monthly", date(2024, 2, 29)),
        (date(2025, 11, 30), "quarterly", date(2026, 2, 28)),
        (date(2025, 12, 1), "quarterly", date(2026, 3, 1)),
        (date(2024, 2, 29), "yearly", date(2025, 2, 28)),
        (date(2025, 6, 10), "yearly", date(2026, 6, 10)),
    ],
)
def test_calculate_expiry(start, cycle, expected):
    assert calculate_expiry(start, cycle) == expected


def test_calculate_expiry_rejects_unknown_cycle():
    with pytest.raises(ValueError):
        calculate_expiry(date(2025, 1, 1), "weekly")


def test_add_months_negative():
    assert add_months(date(2025, 3, 31), -1) == date(2025, 2, 28)


# ----------------------------------------------------------------- creation
def _subscribe(client, headers, customer_id, plan_id, **extra):
    payload = {"customer_id": customer_id, "plan_id": plan_id, **extra}
    return client.post("/api/subscriptions", headers=headers, json=payload)


def test_create_subscription_calculates_expiry(client, auth, customer, plans):
    response = _subscribe(client, auth("staff"), customer.id, plans["quarterly"].id, start_date="2026-01-31")
    assert response.status_code == 201
    body = response.get_json()
    assert body["start_date"] == "2026-01-31"
    assert body["expiry_date"] == "2026-04-30"
    assert body["amount"] == 140
    assert body["payment_status"] == "pending"
    assert len(body["payments"]) == 1
    assert body["payments"][0]["status"] == "pending"
    assert body["payments"][0]["due_date"] == "2026-01-31"


def test_create_subscription_with_paid_initial_payment(client, auth, customer, plans):
    response = _subscribe(
        client, auth("admin"), customer.id, plans["monthly"].id,
        payment={"status": "paid", "method": "card", "reference": "TX-1"},
    )
    body = response.get_json()
    assert response.status_code == 201
    assert body["payment_status"] == "paid"
    assert body["payments"][0]["paid_on"] == date.today().isoformat()


def test_create_subscription_custom_amount_and_default_start(client, auth, customer, plans):
    body = _subscribe(client, auth("staff"), customer.id, plans["yearly"].id, amount=900).get_json()
    assert body["amount"] == 900
    assert body["start_date"] == date.today().isoformat()
    assert body["expiry_date"] == calculate_expiry(date.today(), "yearly").isoformat()


def test_create_subscription_rejects_inactive_plan(client, auth, customer, plans):
    response = _subscribe(client, auth("staff"), customer.id, plans["inactive"].id)
    assert response.status_code == 400


def test_create_subscription_rejects_duplicate_current_plan(client, auth, customer, plans):
    assert _subscribe(client, auth("staff"), customer.id, plans["monthly"].id).status_code == 201
    assert _subscribe(client, auth("staff"), customer.id, plans["monthly"].id).status_code == 409


def test_create_subscription_requires_fields(client, auth):
    response = client.post("/api/subscriptions", headers=auth("staff"), json={})
    assert response.status_code == 422


def test_create_subscription_unknown_customer(client, auth, plans):
    assert _subscribe(client, auth("staff"), 9999, plans["monthly"].id).status_code == 404


# ----------------------------------------------------------------- status detection
def _make_sub(customer, plan, start, expiry, status="active"):
    sub = Subscription(customer=customer, plan=plan, start_date=start, expiry_date=expiry,
                       amount=plan.price, status=status, payment_status="paid")
    db.session.add(sub)
    db.session.commit()
    return sub


def test_status_is_derived_from_dates(app, customer, plans):
    today = date.today()
    plan = plans["monthly"]
    expired = _make_sub(customer, plan, today - timedelta(days=40), today - timedelta(days=1))
    soon = _make_sub(customer, plan, today - timedelta(days=25), today + timedelta(days=5))
    active = _make_sub(customer, plan, today, today + timedelta(days=60))
    cancelled = _make_sub(customer, plan, today, today + timedelta(days=60), status="cancelled")
    assert expired.effective_status == "expired"
    assert soon.effective_status == "expiring_soon"
    assert active.effective_status == "active"
    assert cancelled.effective_status == "cancelled"


def test_status_filter_matches_derived_status(client, auth, customer, plans):
    today = date.today()
    _make_sub(customer, plans["monthly"], today - timedelta(days=40), today - timedelta(days=3))
    _make_sub(customer, plans["quarterly"], today - timedelta(days=80), today + timedelta(days=3))
    _make_sub(customer, plans["yearly"], today, today + timedelta(days=300))
    for status, expected in (("expired", 1), ("expiring_soon", 1), ("active", 1), ("current", 2)):
        body = client.get(f"/api/subscriptions?status={status}", headers=auth("admin")).get_json()
        assert body["total"] == expected, status
        assert all(item["status"] == status for item in body["items"]) or status == "current"


def test_upcoming_renewals_lists_30_day_window_and_overdue(client, auth, customer, plans):
    today = date.today()
    _make_sub(customer, plans["monthly"], today - timedelta(days=40), today - timedelta(days=2))
    _make_sub(customer, plans["quarterly"], today - timedelta(days=70), today + timedelta(days=20))
    _make_sub(customer, plans["yearly"], today, today + timedelta(days=200))
    body = client.get("/api/renewals/upcoming", headers=auth("staff")).get_json()
    assert body["counts"]["overdue"] == 1
    assert body["counts"]["upcoming"] == 1
    assert body["upcoming"][0]["plan"]["name"] == "Pro Quarterly"


# ----------------------------------------------------------------- renewal
def test_renew_active_subscription_extends_from_current_expiry(client, auth, customer, plans):
    today = date.today()
    sub = _make_sub(customer, plans["monthly"], today - timedelta(days=25), today + timedelta(days=5))
    original_expiry = sub.expiry_date
    response = client.post(
        f"/api/subscriptions/{sub.id}/renew",
        headers=auth("staff"),
        json={"payment": {"status": "paid", "method": "bank_transfer"}},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["subscription"]["expiry_date"] == calculate_expiry(original_expiry, "monthly").isoformat()
    assert body["renewal"]["previous_expiry_date"] == original_expiry.isoformat()
    assert body["renewal"]["period_start"] == original_expiry.isoformat()
    assert body["subscription"]["payment_status"] == "paid"


def test_renew_expired_subscription_restarts_from_today(client, auth, customer, plans):
    today = date.today()
    sub = _make_sub(customer, plans["quarterly"], today - timedelta(days=200), today - timedelta(days=100))
    body = client.post(f"/api/subscriptions/{sub.id}/renew", headers=auth("staff"), json={}).get_json()
    assert body["subscription"]["expiry_date"] == calculate_expiry(today, "quarterly").isoformat()
    assert body["subscription"]["status"] == "active"
    assert body["subscription"]["payment_status"] == "pending"


def test_renewal_keeps_previous_history_and_payments(client, auth, customer, plans):
    created = _subscribe(
        client, auth("staff"), customer.id, plans["monthly"].id, payment={"status": "paid"}
    ).get_json()
    sub_id = created["id"]
    first_payment_id = created["payments"][0]["id"]
    for _ in range(2):
        assert client.post(f"/api/subscriptions/{sub_id}/renew", headers=auth("staff"), json={}).status_code == 200

    assert RenewalHistory.query.filter_by(subscription_id=sub_id).count() == 2
    payments = Payment.query.filter_by(subscription_id=sub_id).all()
    assert len(payments) == 3
    first = db.session.get(Payment, first_payment_id)
    assert first.status == "paid"  # untouched by renewals

    history = client.get(f"/api/renewals/history?subscription_id={sub_id}", headers=auth("admin")).get_json()
    assert history["total"] == 2
    expiries = sorted(h["new_expiry_date"] for h in history["items"])
    assert expiries[1] > expiries[0]


def test_renew_with_plan_change(client, auth, customer, plans):
    sub = _subscribe(client, auth("staff"), customer.id, plans["monthly"].id).get_json()
    body = client.post(
        f"/api/subscriptions/{sub['id']}/renew", headers=auth("staff"), json={"plan_id": plans["yearly"].id}
    ).get_json()
    assert body["subscription"]["plan"]["id"] == plans["yearly"].id
    assert body["subscription"]["amount"] == 1000
    expected = calculate_expiry(date.fromisoformat(sub["expiry_date"]), "yearly")
    assert body["subscription"]["expiry_date"] == expected.isoformat()


def test_cannot_renew_cancelled_subscription(client, auth, customer, plans):
    sub = _subscribe(client, auth("staff"), customer.id, plans["monthly"].id).get_json()
    assert client.post(f"/api/subscriptions/{sub['id']}/cancel", headers=auth("staff"),
                       json={"reason": "Closed"}).status_code == 200
    response = client.post(f"/api/subscriptions/{sub['id']}/renew", headers=auth("staff"), json={})
    assert response.status_code == 400


# ----------------------------------------------------------------- update & cancel
def test_update_subscription_recalculates_expiry(client, auth, customer, plans):
    sub = _subscribe(client, auth("staff"), customer.id, plans["monthly"].id, start_date="2026-03-01").get_json()
    response = client.put(
        f"/api/subscriptions/{sub['id']}", headers=auth("staff"),
        json={"plan_id": plans["quarterly"].id, "start_date": "2026-04-15"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["expiry_date"] == "2026-07-15"
    assert body["amount"] == 140


def test_cancel_subscription(client, auth, customer, plans):
    sub = _subscribe(client, auth("staff"), customer.id, plans["monthly"].id).get_json()
    body = client.post(f"/api/subscriptions/{sub['id']}/cancel", headers=auth("admin"),
                       json={"reason": "Budget"}).get_json()
    assert body["status"] == "cancelled"
    assert body["cancellation_reason"] == "Budget"
    again = client.post(f"/api/subscriptions/{sub['id']}/cancel", headers=auth("admin"), json={})
    assert again.status_code == 400
    # A cancelled subscription frees the customer to subscribe to the plan again.
    assert _subscribe(client, auth("staff"), customer.id, plans["monthly"].id).status_code == 201
