"""Database models for Subsmate.

Tables: users, customers, subscription_plans, subscriptions, payments,
renewal_history, notifications.
"""
import json
from datetime import datetime, timezone

from flask import current_app
from sqlalchemy import CheckConstraint, UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .services.dates import today

ROLE_ADMIN = "admin"
ROLE_CUSTOMER = "customer"
ROLE_STAFF = "staff"
ROLES = (ROLE_ADMIN, ROLE_CUSTOMER, ROLE_STAFF)
STAFF_ROLES = (ROLE_ADMIN, ROLE_STAFF)

BILLING_CYCLES = {"monthly": 1, "quarterly": 3, "yearly": 12}
ACTIVE_INACTIVE = ("active", "inactive")
SUBSCRIPTION_STATES = ("active", "cancelled")  # stored; expiry is derived from dates
PAYMENT_STATUSES = ("paid", "pending", "failed")
PAYMENT_METHODS = ("cash", "bank_transfer", "card", "upi", "cheque", "other")


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _in(column, values):
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _iso(value):
    return value.isoformat() if value else None


def _money(value):
    return round(float(value or 0), 2)


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class User(TimestampMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint(_in("role", ROLES), name="ck_users_role"),)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime)
    customer_id = db.Column(
        db.Integer, db.ForeignKey("customers.id", ondelete="CASCADE"), unique=True
    )

    customer = db.relationship("Customer", back_populates="user", foreign_keys=[customer_id])

    def set_password(self, password):
        self.password_hash = generate_password_hash(
            password, method=current_app.config.get("PASSWORD_HASH_METHOD", "scrypt")
        )

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "customer_id": self.customer_id,
            "last_login_at": _iso(self.last_login_at),
            "created_at": _iso(self.created_at),
        }


class Customer(TimestampMixin, db.Model):
    __tablename__ = "customers"
    __table_args__ = (CheckConstraint(_in("status", ACTIVE_INACTIVE), name="ck_customers_status"),)

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    phone = db.Column(db.String(30))
    status = db.Column(db.String(20), nullable=False, default="active")
    registration_date = db.Column(db.Date, nullable=False, default=today)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))

    user = db.relationship(
        "User", back_populates="customer", uselist=False, foreign_keys=[User.customer_id]
    )
    subscriptions = db.relationship(
        "Subscription", back_populates="customer", order_by="Subscription.start_date.desc()"
    )

    @property
    def code(self):
        return f"CUS-{self.id:04d}"

    def to_dict(self, with_stats=False):
        data = {
            "id": self.id,
            "code": self.code,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "status": self.status,
            "registration_date": _iso(self.registration_date),
            "has_login": self.user is not None,
            "created_at": _iso(self.created_at),
        }
        if with_stats:
            statuses = [s.effective_status for s in self.subscriptions]
            data["subscription_count"] = len(statuses)
            data["active_subscription_count"] = sum(
                1 for s in statuses if s in ("active", "expiring_soon")
            )
        return data


class SubscriptionPlan(TimestampMixin, db.Model):
    __tablename__ = "subscription_plans"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_plans_price"),
        CheckConstraint(_in("billing_cycle", BILLING_CYCLES), name="ck_plans_cycle"),
        CheckConstraint(_in("status", ACTIVE_INACTIVE), name="ck_plans_status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2, asdecimal=False), nullable=False)
    billing_cycle = db.Column(db.String(20), nullable=False)
    features_json = db.Column("features", db.Text, nullable=False, default="[]")
    status = db.Column(db.String(20), nullable=False, default="active")

    subscriptions = db.relationship("Subscription", back_populates="plan")

    @property
    def features(self):
        try:
            return json.loads(self.features_json or "[]")
        except ValueError:
            return []

    @features.setter
    def features(self, values):
        self.features_json = json.dumps([str(v).strip() for v in values if str(v).strip()])

    def to_dict(self, with_stats=False):
        data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price": _money(self.price),
            "billing_cycle": self.billing_cycle,
            "features": self.features,
            "status": self.status,
            "created_at": _iso(self.created_at),
        }
        if with_stats:
            data["subscriber_count"] = sum(
                1 for s in self.subscriptions if s.effective_status in ("active", "expiring_soon")
            )
            data["total_subscriptions"] = len(self.subscriptions)
        return data

    def summary(self):
        return {"id": self.id, "name": self.name, "billing_cycle": self.billing_cycle}


class Subscription(TimestampMixin, db.Model):
    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint("expiry_date > start_date", name="ck_subscriptions_dates"),
        CheckConstraint("amount >= 0", name="ck_subscriptions_amount"),
        CheckConstraint(_in("status", SUBSCRIPTION_STATES), name="ck_subscriptions_status"),
        CheckConstraint(_in("payment_status", PAYMENT_STATUSES), name="ck_subscriptions_pay"),
    )

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(
        db.Integer, db.ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    plan_id = db.Column(
        db.Integer,
        db.ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    start_date = db.Column(db.Date, nullable=False)
    expiry_date = db.Column(db.Date, nullable=False, index=True)
    amount = db.Column(db.Numeric(10, 2, asdecimal=False), nullable=False)
    payment_status = db.Column(db.String(20), nullable=False, default="pending")
    status = db.Column(db.String(20), nullable=False, default="active")
    notes = db.Column(db.Text)
    cancelled_at = db.Column(db.DateTime)
    cancellation_reason = db.Column(db.String(255))
    last_renewed_at = db.Column(db.DateTime)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))

    customer = db.relationship("Customer", back_populates="subscriptions")
    plan = db.relationship("SubscriptionPlan", back_populates="subscriptions")
    payments = db.relationship(
        "Payment", back_populates="subscription", order_by="Payment.id.desc()"
    )
    renewals = db.relationship(
        "RenewalHistory", back_populates="subscription", order_by="RenewalHistory.id.desc()"
    )

    @property
    def code(self):
        return f"SUB-{self.id:04d}"

    def compute_status(self, on_date=None, soon_days=None):
        """Derive the lifecycle status: active, expiring_soon, expired or cancelled."""
        if self.status == "cancelled":
            return "cancelled"
        on_date = on_date or today()
        if soon_days is None:
            soon_days = current_app.config["EXPIRING_SOON_DAYS"]
        if self.expiry_date < on_date:
            return "expired"
        if (self.expiry_date - on_date).days <= soon_days:
            return "expiring_soon"
        return "active"

    @property
    def effective_status(self):
        return self.compute_status()

    @property
    def days_until_expiry(self):
        return (self.expiry_date - today()).days

    def summary(self):
        return {
            "id": self.id,
            "code": self.code,
            "customer": {"id": self.customer.id, "full_name": self.customer.full_name},
            "plan": self.plan.summary(),
            "expiry_date": _iso(self.expiry_date),
            "status": self.effective_status,
        }

    def to_dict(self, detail=False):
        data = {
            "id": self.id,
            "code": self.code,
            "customer": {
                "id": self.customer.id,
                "full_name": self.customer.full_name,
                "email": self.customer.email,
            },
            "plan": self.plan.summary(),
            "start_date": _iso(self.start_date),
            "expiry_date": _iso(self.expiry_date),
            "amount": _money(self.amount),
            "payment_status": self.payment_status,
            "status": self.effective_status,
            "days_until_expiry": self.days_until_expiry,
            "notes": self.notes,
            "cancelled_at": _iso(self.cancelled_at),
            "cancellation_reason": self.cancellation_reason,
            "last_renewed_at": _iso(self.last_renewed_at),
            "renewal_count": len(self.renewals),
            "created_at": _iso(self.created_at),
        }
        if detail:
            data["payments"] = [p.to_dict(include_subscription=False) for p in self.payments]
            data["renewals"] = [r.to_dict(include_subscription=False) for r in self.renewals]
        return data


class Payment(TimestampMixin, db.Model):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payments_amount"),
        CheckConstraint(_in("status", PAYMENT_STATUSES), name="ck_payments_status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(
        db.Integer,
        db.ForeignKey("subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount = db.Column(db.Numeric(10, 2, asdecimal=False), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    method = db.Column(db.String(30))
    due_date = db.Column(db.Date, nullable=False)
    paid_on = db.Column(db.Date, index=True)
    reference = db.Column(db.String(120))
    notes = db.Column(db.Text)
    recorded_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))

    subscription = db.relationship("Subscription", back_populates="payments")
    recorded_by = db.relationship("User")

    @property
    def code(self):
        return f"PAY-{self.id:05d}"

    @property
    def is_overdue(self):
        return self.status != "paid" and self.due_date < today()

    def to_dict(self, include_subscription=True):
        data = {
            "id": self.id,
            "code": self.code,
            "subscription_id": self.subscription_id,
            "amount": _money(self.amount),
            "status": self.status,
            "method": self.method,
            "due_date": _iso(self.due_date),
            "paid_on": _iso(self.paid_on),
            "reference": self.reference,
            "notes": self.notes,
            "is_overdue": self.is_overdue,
            "recorded_by": self.recorded_by.name if self.recorded_by else None,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
        }
        if include_subscription:
            data["subscription"] = self.subscription.summary()
        return data


class RenewalHistory(db.Model):
    __tablename__ = "renewal_history"
    __table_args__ = (
        CheckConstraint("new_expiry_date > previous_expiry_date", name="ck_renewal_dates"),
    )

    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(
        db.Integer,
        db.ForeignKey("subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    plan_id = db.Column(
        db.Integer, db.ForeignKey("subscription_plans.id", ondelete="RESTRICT"), nullable=False
    )
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id", ondelete="SET NULL"))
    previous_expiry_date = db.Column(db.Date, nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    new_expiry_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(10, 2, asdecimal=False), nullable=False)
    notes = db.Column(db.Text)
    renewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    renewed_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    subscription = db.relationship("Subscription", back_populates="renewals")
    plan = db.relationship("SubscriptionPlan")
    payment = db.relationship("Payment")
    renewed_by = db.relationship("User")

    def to_dict(self, include_subscription=True):
        data = {
            "id": self.id,
            "subscription_id": self.subscription_id,
            "plan": self.plan.summary(),
            "previous_expiry_date": _iso(self.previous_expiry_date),
            "period_start": _iso(self.period_start),
            "new_expiry_date": _iso(self.new_expiry_date),
            "amount": _money(self.amount),
            "payment_id": self.payment_id,
            "payment_status": self.payment.status if self.payment else None,
            "notes": self.notes,
            "renewed_by": self.renewed_by.name if self.renewed_by else None,
            "renewed_at": _iso(self.renewed_at),
        }
        if include_subscription:
            data["subscription"] = self.subscription.summary()
        return data


class Notification(db.Model):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("user_id", "dedupe_key", name="uq_notifications_dedupe"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category = db.Column(db.String(30), nullable=False)  # renewal, expired, payment, system
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    link = db.Column(db.String(255))
    subscription_id = db.Column(
        db.Integer, db.ForeignKey("subscriptions.id", ondelete="CASCADE")
    )
    dedupe_key = db.Column(db.String(120))
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "message": self.message,
            "link": self.link,
            "subscription_id": self.subscription_id,
            "is_read": self.is_read,
            "created_at": _iso(self.created_at),
        }
