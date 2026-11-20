"""In-app renewal reminders and alerts (no external messaging)."""
from datetime import timedelta

from flask import current_app

from ..extensions import db
from ..models import ROLE_ADMIN, ROLE_STAFF, Notification, Subscription, User
from .dates import today

REMINDER_ROLES = (ROLE_ADMIN, ROLE_STAFF)
EXPIRED_LOOKBACK_DAYS = 30


def _recipients(subscription, roles):
    users = User.query.filter(User.role.in_(roles), User.is_active.is_(True)).all()
    portal_user = subscription.customer.user
    if portal_user and portal_user.is_active:
        users.append(portal_user)
    return users


def _create(users, *, key, category, title, message, link, subscription_id):
    """Create one notification per user, skipping users who already have this key."""
    if not users:
        return 0
    existing = {
        row.user_id
        for row in Notification.query.filter(
            Notification.dedupe_key == key, Notification.user_id.in_([u.id for u in users])
        )
    }
    created = 0
    for user in users:
        if user.id in existing:
            continue
        is_customer = user.customer_id is not None
        db.session.add(
            Notification(
                user_id=user.id,
                category=category,
                title=title,
                message=message,
                link="/subscriptions" if is_customer else link,
                subscription_id=subscription_id,
                dedupe_key=key,
            )
        )
        created += 1
    return created


def generate_renewal_reminders():
    """Create reminders for subscriptions expiring soon or recently expired.

    Idempotent: a reminder is created once per user per subscription period.
    """
    current_day = today()
    soon = current_day + timedelta(days=current_app.config["EXPIRING_SOON_DAYS"])
    candidates = Subscription.query.filter(
        Subscription.status == "active",
        Subscription.expiry_date >= current_day - timedelta(days=EXPIRED_LOOKBACK_DAYS),
        Subscription.expiry_date <= soon,
    ).all()

    created = 0
    for sub in candidates:
        name = sub.customer.full_name
        users = _recipients(sub, REMINDER_ROLES)
        if sub.expiry_date < current_day:
            created += _create(
                users,
                key=f"expired:{sub.id}:{sub.expiry_date.isoformat()}",
                category="expired",
                title=f"{sub.code} has expired",
                message=f"{name}'s {sub.plan.name} subscription expired on "
                f"{sub.expiry_date.strftime('%b %d, %Y')}.",
                link=f"/subscriptions/{sub.id}",
                subscription_id=sub.id,
            )
        else:
            days = (sub.expiry_date - current_day).days
            when = "today" if days == 0 else f"in {days} day{'s' if days != 1 else ''}"
            created += _create(
                users,
                key=f"renewal:{sub.id}:{sub.expiry_date.isoformat()}",
                category="renewal",
                title=f"Renewal due {when}",
                message=f"{name}'s {sub.plan.name} subscription expires on "
                f"{sub.expiry_date.strftime('%b %d, %Y')}.",
                link=f"/subscriptions/{sub.id}",
                subscription_id=sub.id,
            )
    if created:
        db.session.commit()
    return created


def notify_payment_failed(payment):
    sub = payment.subscription
    users = User.query.filter(
        User.role.in_((ROLE_ADMIN, ROLE_STAFF)), User.is_active.is_(True)
    ).all()
    _create(
        users,
        key=f"payment-failed:{payment.id}",
        category="payment",
        title=f"Payment {payment.code} failed",
        message=f"Payment of {payment.amount:.2f} for {sub.customer.full_name} "
        f"({sub.plan.name}) was marked as failed.",
        link="/payments?status=failed",
        subscription_id=sub.id,
    )
