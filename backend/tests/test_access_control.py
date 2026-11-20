"""Role-based access control and customer data isolation."""
import pytest


@pytest.fixture()
def two_subscriptions(client, auth, customer, other_customer, plans):
    own = client.post("/api/subscriptions", headers=auth("staff"),
                      json={"customer_id": customer.id, "plan_id": plans["monthly"].id}).get_json()
    other = client.post("/api/subscriptions", headers=auth("staff"),
                        json={"customer_id": other_customer.id, "plan_id": plans["monthly"].id}).get_json()
    return own, other


@pytest.mark.parametrize(
    "role, method, url, expected",
    [
        ("customer", "get", "/api/customers", 403),
        ("customer", "get", "/api/users", 403),
        ("customer", "get", "/api/reports/summary", 403),
        ("customer", "post", "/api/plans", 403),
        ("customer", "post", "/api/payments", 403),
        # Staff: day-to-day work (customers, subscriptions, payments) but no admin functions.
        ("staff", "get", "/api/users", 403),
        ("staff", "post", "/api/users", 403),
        ("staff", "post", "/api/plans", 403),
        ("staff", "put", "/api/plans/1", 403),
        ("staff", "delete", "/api/customers/1", 403),
        ("staff", "get", "/api/reports/summary", 403),
        ("staff", "get", "/api/reports/export/customers", 403),
        ("staff", "get", "/api/customers", 200),
        ("staff", "get", "/api/payments", 200),
        ("staff", "get", "/api/renewals/upcoming", 200),
        # Allowed for staff: these reach validation (422) instead of being refused (403).
        ("staff", "post", "/api/customers", 422),
        ("staff", "post", "/api/subscriptions", 422),
        ("staff", "post", "/api/payments", 422),
        ("admin", "get", "/api/users", 200),
        ("admin", "get", "/api/reports/summary", 200),
    ],
)
def test_role_permissions(client, auth, role, method, url, expected):
    response = getattr(client, method)(url, headers=auth(role), json={})
    assert response.status_code == expected


def test_customer_sees_only_own_subscriptions(client, auth, two_subscriptions):
    own, other = two_subscriptions
    body = client.get("/api/subscriptions", headers=auth("customer")).get_json()
    assert [s["id"] for s in body["items"]] == [own["id"]]
    assert client.get(f"/api/subscriptions/{own['id']}", headers=auth("customer")).status_code == 200
    assert client.get(f"/api/subscriptions/{other['id']}", headers=auth("customer")).status_code == 404


def test_customer_sees_only_own_payments_and_renewals(client, auth, two_subscriptions):
    own, other = two_subscriptions
    client.post(f"/api/subscriptions/{other['id']}/renew", headers=auth("staff"), json={})
    payments = client.get("/api/payments", headers=auth("customer")).get_json()
    assert {p["subscription_id"] for p in payments["items"]} == {own["id"]}
    other_payment = other["payments"][0]["id"]
    assert client.get(f"/api/payments/{other_payment}", headers=auth("customer")).status_code == 404
    history = client.get("/api/renewals/history", headers=auth("customer")).get_json()
    assert history["total"] == 0


def test_customer_cannot_modify_subscriptions(client, auth, two_subscriptions):
    own, _ = two_subscriptions
    assert client.post(f"/api/subscriptions/{own['id']}/renew", headers=auth("customer"), json={}).status_code == 403
    assert client.post(f"/api/subscriptions/{own['id']}/cancel", headers=auth("customer"), json={}).status_code == 403
    assert client.put(f"/api/subscriptions/{own['id']}", headers=auth("customer"), json={"amount": 1}).status_code == 403


def test_customer_dashboard_is_personal(client, auth, two_subscriptions):
    body = client.get("/api/dashboard", headers=auth("customer")).get_json()
    assert body["role"] == "customer"
    assert len(body["subscriptions"]) == 1
    assert "total_customers" not in body["stats"]


def test_customer_only_sees_active_plans(client, auth, plans):
    names = {p["name"] for p in client.get("/api/plans", headers=auth("customer")).get_json()["items"]}
    assert "Retired" not in names
    names = {p["name"] for p in client.get("/api/plans", headers=auth("admin")).get_json()["items"]}
    assert "Retired" in names


def test_admin_user_management(client, auth):
    created = client.post("/api/users", headers=auth("admin"), json={
        "name": "New Biller", "email": "biller2@test.io", "password": "Biller@1234", "role": "staff",
    })
    assert created.status_code == 201
    user_id = created.get_json()["id"]
    assert client.put(f"/api/users/{user_id}", headers=auth("admin"), json={"is_active": False}).status_code == 200
    login = client.post("/api/auth/login", json={"email": "biller2@test.io", "password": "Biller@1234"})
    assert login.status_code == 403
    assert client.delete(f"/api/users/{user_id}", headers=auth("admin")).status_code == 204


def test_admin_cannot_lock_themselves_out(client, auth, users):
    admin_id = users["admin"].id
    assert client.put(f"/api/users/{admin_id}", headers=auth("admin"), json={"is_active": False}).status_code == 400
    assert client.delete(f"/api/users/{admin_id}", headers=auth("admin")).status_code == 400
