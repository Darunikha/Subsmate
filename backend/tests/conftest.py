import os
import sys
from dataclasses import dataclass

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app  # noqa: E402
from app.config import TestConfig  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Customer, User  # noqa: E402

PASSWORDS = {"admin": "Admin@1234", "staff": "Staff@1234", "customer": "Customer@1234"}


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        yield app
        db.session.remove()
        db.engine.dispose()  # in-memory database disappears with its connection


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def users(app):
    created = {}
    for role in ("admin", "staff"):
        user = User(name=f"{role.title()} User", email=f"{role}@test.io", role=role)
        user.set_password(PASSWORDS[role])
        db.session.add(user)
        created[role] = user
    customer = Customer(full_name="Cara Customer", email="customer@test.io", phone="+1 555 0100")
    db.session.add(customer)
    portal = User(name="Cara Customer", email="customer@test.io", role="customer", customer=customer)
    portal.set_password(PASSWORDS["customer"])
    db.session.add(portal)
    created["customer"] = portal
    db.session.commit()
    return created


def _login(client, email, password):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.get_json()
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


@pytest.fixture()
def auth(client, users):
    """auth('admin') -> headers for that role."""
    cache = {}

    def headers(role):
        if role not in cache:
            cache[role] = _login(client, users[role].email, PASSWORDS[role])
        return cache[role]

    return headers


@dataclass(frozen=True)
class Service:
    """A service a customer can subscribe to. Subscriptions carry these values themselves."""

    name: str
    price: float
    billing_cycle: str

    def payload(self, **extra):
        return {"service_name": self.name, "billing_cycle": self.billing_cycle, "amount": self.price, **extra}


@pytest.fixture()
def services():
    return {
        "monthly": Service("Basic Monthly", 50, "monthly"),
        "quarterly": Service("Pro Quarterly", 140, "quarterly"),
        "yearly": Service("Enterprise Yearly", 1000, "yearly"),
    }


@pytest.fixture()
def customer(users):
    return users["customer"].customer


@pytest.fixture()
def other_customer(app):
    other = Customer(full_name="Otto Other", email="otto@test.io")
    db.session.add(other)
    db.session.commit()
    return other
