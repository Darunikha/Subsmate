from app.extensions import db
from app.models import User


def test_login_success_returns_token_and_user(client, users):
    response = client.post("/api/auth/login", json={"email": "ADMIN@test.io ", "password": "Admin@1234"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["token"]
    assert body["user"]["role"] == "admin"
    assert "password_hash" not in body["user"]


def test_login_wrong_password(client, users):
    response = client.post("/api/auth/login", json={"email": "admin@test.io", "password": "nope"})
    assert response.status_code == 401


def test_login_missing_fields(client):
    response = client.post("/api/auth/login", json={"email": ""})
    assert response.status_code == 422
    assert "password" in response.get_json()["errors"]


def test_passwords_are_hashed(users):
    user = db.session.get(User, users["admin"].id)
    assert user.password_hash != "Admin@1234"
    assert user.check_password("Admin@1234")


def test_protected_route_requires_token(client):
    assert client.get("/api/dashboard").status_code == 401
    bad = client.get("/api/dashboard", headers={"Authorization": "Bearer forged.token"})
    assert bad.status_code == 401


def test_me_returns_current_user(client, auth):
    response = client.get("/api/auth/me", headers=auth("staff"))
    assert response.status_code == 200
    assert response.get_json()["email"] == "staff@test.io"


def test_deactivated_user_cannot_login_or_use_token(client, auth, users):
    headers = auth("staff")
    users["staff"].is_active = False
    db.session.commit()
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    response = client.post("/api/auth/login", json={"email": "staff@test.io", "password": "Staff@1234"})
    assert response.status_code == 403


def test_change_password_invalidates_old_token(client, auth):
    headers = auth("staff")
    response = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": "Staff@1234", "new_password": "NewPass@5678"},
    )
    assert response.status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    new_headers = {"Authorization": f"Bearer {response.get_json()['token']}"}
    assert client.get("/api/auth/me", headers=new_headers).status_code == 200


def test_change_password_rejects_wrong_current(client, auth):
    response = client.post(
        "/api/auth/change-password",
        headers=auth("staff"),
        json={"current_password": "wrong", "new_password": "NewPass@5678"},
    )
    assert response.status_code == 422
