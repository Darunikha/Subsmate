from app.models import Customer, User


def _create(client, headers, **overrides):
    payload = {"full_name": "Nina Patel", "email": "nina@patelco.com", "phone": "+44 20 5550 1000"}
    payload.update(overrides)
    return client.post("/api/customers", headers=headers, json=payload)


def test_register_customer(client, auth):
    response = _create(client, auth("staff"))
    assert response.status_code == 201
    body = response.get_json()
    assert body["full_name"] == "Nina Patel"
    assert body["code"].startswith("CUS-")
    assert body["status"] == "active"
    assert body["registration_date"]
    assert body["has_login"] is False


def test_register_customer_with_portal_login(client, auth):
    response = _create(client, auth("admin"), create_login=True, password="Welcome@123")
    assert response.status_code == 201
    login = client.post("/api/auth/login", json={"email": "nina@patelco.com", "password": "Welcome@123"})
    assert login.status_code == 200
    assert login.get_json()["user"]["role"] == "customer"


def test_register_customer_validation(client, auth):
    response = _create(client, auth("staff"), email="not-an-email", full_name="")
    assert response.status_code == 422
    assert "full_name" in response.get_json()["errors"]


def test_duplicate_customer_email_rejected(client, auth):
    assert _create(client, auth("staff")).status_code == 201
    duplicate = _create(client, auth("staff"), email="NINA@patelco.com")
    assert duplicate.status_code == 409


def test_customer_list_search_and_detail(client, auth):
    _create(client, auth("staff"))
    _create(client, auth("staff"), full_name="Leo Grant", email="leo@grant.io")
    found = client.get("/api/customers?q=grant", headers=auth("staff")).get_json()
    assert found["total"] == 1
    assert found["items"][0]["full_name"] == "Leo Grant"

    by_email = client.get("/api/customers?q=patelco", headers=auth("admin")).get_json()
    assert by_email["total"] == 1

    customer_id = found["items"][0]["id"]
    detail = client.get(f"/api/customers/{customer_id}", headers=auth("staff"))
    assert detail.status_code == 200
    assert detail.get_json()["subscriptions"] == []


def test_update_customer(client, auth):
    customer_id = _create(client, auth("staff")).get_json()["id"]
    response = client.put(
        f"/api/customers/{customer_id}",
        headers=auth("staff"),
        json={"full_name": "Nina P. Patel", "phone": "+44 20 5550 2000", "status": "inactive"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["full_name"] == "Nina P. Patel"
    assert body["status"] == "inactive"


def test_update_customer_email_conflict(client, auth, other_customer):
    customer_id = _create(client, auth("staff")).get_json()["id"]
    response = client.put(
        f"/api/customers/{customer_id}", headers=auth("staff"), json={"email": "otto@test.io"}
    )
    assert response.status_code == 409


def test_delete_customer_without_history(client, auth, app):
    customer_id = _create(client, auth("staff"), create_login=True, password="Welcome@123").get_json()["id"]
    assert client.delete(f"/api/customers/{customer_id}", headers=auth("admin")).status_code == 204
    from app.extensions import db

    assert db.session.get(Customer, customer_id) is None
    assert User.query.filter_by(email="nina@patelco.com").first() is None
    assert client.get(f"/api/customers/{customer_id}", headers=auth("admin")).status_code == 404


def test_delete_customer_with_subscriptions_is_blocked(client, auth, customer, plans):
    client.post(
        "/api/subscriptions",
        headers=auth("staff"),
        json={"customer_id": customer.id, "plan_id": plans["monthly"].id},
    )
    response = client.delete(f"/api/customers/{customer.id}", headers=auth("admin"))
    assert response.status_code == 409


def test_customer_subscription_history_in_detail(client, auth, customer, plans):
    client.post(
        "/api/subscriptions",
        headers=auth("staff"),
        json={"customer_id": customer.id, "plan_id": plans["monthly"].id, "start_date": "2025-01-01"},
    )
    detail = client.get(f"/api/customers/{customer.id}", headers=auth("admin")).get_json()
    assert len(detail["subscriptions"]) == 1
    assert detail["subscriptions"][0]["status"] == "expired"
    assert len(detail["payments"]) == 1
