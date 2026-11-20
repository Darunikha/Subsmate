"""Subscription lifecycle: creation, updates, cancellation and renewal."""
from datetime import timedelta

from flask import current_app
from sqlalchemy import and_

from ..extensions import db
from ..models import BILLING_CYCLES, RenewalHistory, Subscription, utcnow
from ..utils import APIError, clean_str, parse_amount, parse_choice, parse_date
from .dates import calculate_expiry, today
from .payments import record_payment

STATUS_FILTERS = ("active", "expiring_soon", "expired", "cancelled", "current")


def status_condition(status, on_date=None):
    """SQL condition matching Subscription.compute_status for list filtering."""
    on_date = on_date or today()
    soon = on_date + timedelta(days=current_app.config["EXPIRING_SOON_DAYS"])
    live = Subscription.status == "active"
    if status == "cancelled":
        return Subscription.status == "cancelled"
    if status == "expired":
        return and_(live, Subscription.expiry_date < on_date)
    if status == "expiring_soon":
        return and_(live, Subscription.expiry_date >= on_date, Subscription.expiry_date <= soon)
    if status == "active":
        return and_(live, Subscription.expiry_date > soon)
    if status == "current":  # anything not expired and not cancelled
        return and_(live, Subscription.expiry_date >= on_date)
    raise APIError(f"Unknown status filter. Use one of: {', '.join(STATUS_FILTERS)}.", 400)


def _service_name(value):
    return clean_str(value, "service_name", 120, required=True)


def _billing_cycle(value):
    return parse_choice(value, "billing_cycle", tuple(BILLING_CYCLES))


def _ensure_no_duplicate(customer_id, service_name, exclude_id=None):
    query = Subscription.query.filter(
        Subscription.customer_id == customer_id,
        db.func.lower(Subscription.service_name) == service_name.lower(),
        status_condition("current"),
    )
    if exclude_id:
        query = query.filter(Subscription.id != exclude_id)
    if query.first():
        raise APIError(
            "This customer already has a current subscription to this service. "
            "Renew the existing subscription instead.",
            409,
            {"service_name": "Already subscribed."},
        )


def create_subscription(customer, data, user=None):
    if customer.status != "active":
        raise APIError("Subscriptions can only be created for active customers.", 400)

    service_name = _service_name(data.get("service_name"))
    billing_cycle = _billing_cycle(data.get("billing_cycle"))
    amount = parse_amount(data.get("amount"), "amount", allow_zero=True)
    start_date = parse_date(data.get("start_date"), "start_date", required=False) or today()
    _ensure_no_duplicate(customer.id, service_name)

    subscription = Subscription(
        customer=customer,
        service_name=service_name,
        billing_cycle=billing_cycle,
        start_date=start_date,
        expiry_date=calculate_expiry(start_date, billing_cycle),
        amount=amount,
        status="active",
        payment_status="pending",
        notes=clean_str(data.get("notes"), "notes", 1000),
        created_by_id=user.id if user else None,
    )
    db.session.add(subscription)
    db.session.flush()

    if subscription.amount > 0:
        payment_data = dict(data.get("payment") or {})
        payment_data.setdefault("due_date", start_date.isoformat())
        record_payment(subscription, payment_data, user)
    else:
        subscription.payment_status = "paid"
    return subscription


def update_subscription(subscription, data):
    if subscription.status == "cancelled":
        raise APIError("Cancelled subscriptions cannot be edited.", 400)
    # Defer flushing until start and expiry dates are consistent again.
    with db.session.no_autoflush:
        return _apply_update(subscription, data)


def _apply_update(subscription, data):
    if "service_name" in data:
        name = _service_name(data["service_name"])
        if name.lower() != subscription.service_name.lower():
            _ensure_no_duplicate(subscription.customer_id, name, exclude_id=subscription.id)
        subscription.service_name = name

    recalculate = False
    if "billing_cycle" in data:
        cycle = _billing_cycle(data["billing_cycle"])
        if cycle != subscription.billing_cycle:
            subscription.billing_cycle = cycle
            recalculate = True
    if "start_date" in data:
        start_date = parse_date(data["start_date"], "start_date")
        if start_date != subscription.start_date:
            subscription.start_date = start_date
            recalculate = True

    if recalculate:
        if subscription.renewals:
            raise APIError(
                "Billing cycle and start date cannot be changed after a subscription has been "
                "renewed. Choose a new billing cycle when renewing instead.",
                400,
            )
        subscription.expiry_date = calculate_expiry(subscription.start_date, subscription.billing_cycle)

    if "amount" in data:
        subscription.amount = parse_amount(data["amount"], "amount", allow_zero=True)
    if "notes" in data:
        subscription.notes = clean_str(data["notes"], "notes", 1000)
    return subscription


def cancel_subscription(subscription, reason=None):
    if subscription.status == "cancelled":
        raise APIError("This subscription is already cancelled.", 400)
    subscription.status = "cancelled"
    subscription.cancelled_at = utcnow()
    subscription.cancellation_reason = clean_str(reason, "reason", 255)
    return subscription


def renew_subscription(subscription, data, user=None):
    """Extend a subscription by one billing period.

    Active subscriptions extend from their current expiry date so no paid time
    is lost; expired ones restart from today. A renewal history row and a new
    payment record are always created; earlier records are never modified.
    The billing cycle and amount can be changed at renewal time.
    """
    if subscription.status == "cancelled":
        raise APIError(
            "Cancelled subscriptions cannot be renewed. Create a new subscription instead.", 400
        )

    cycle = subscription.billing_cycle
    if data.get("billing_cycle") not in (None, ""):
        cycle = _billing_cycle(data["billing_cycle"])
    amount = parse_amount(data.get("amount"), "amount", allow_zero=True, required=False)
    if amount is None:
        amount = subscription.amount

    previous_expiry = subscription.expiry_date
    current_day = today()
    period_start = previous_expiry if previous_expiry >= current_day else current_day
    new_expiry = calculate_expiry(period_start, cycle)

    subscription.billing_cycle = cycle
    subscription.amount = amount
    subscription.expiry_date = new_expiry
    subscription.last_renewed_at = utcnow()

    payment = None
    if amount > 0:
        payment_data = dict(data.get("payment") or {})
        payment_data.setdefault("due_date", period_start.isoformat())
        payment_data["amount"] = amount
        payment = record_payment(subscription, payment_data, user)

    renewal = RenewalHistory(
        subscription=subscription,
        service_name=subscription.service_name,
        billing_cycle=cycle,
        payment=payment,
        previous_expiry_date=previous_expiry,
        period_start=period_start,
        new_expiry_date=new_expiry,
        amount=amount,
        notes=clean_str(data.get("notes"), "notes", 1000),
        renewed_by_id=user.id if user else None,
    )
    db.session.add(renewal)
    db.session.flush()
    return subscription, renewal
