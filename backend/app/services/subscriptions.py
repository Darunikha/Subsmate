"""Subscription lifecycle: creation, updates, cancellation and renewal."""
from datetime import timedelta

from flask import current_app
from sqlalchemy import and_

from ..extensions import db
from ..models import RenewalHistory, Subscription, utcnow
from ..utils import APIError, clean_str, parse_amount, parse_date
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


def _ensure_no_duplicate(customer_id, plan_id, exclude_id=None):
    query = Subscription.query.filter(
        Subscription.customer_id == customer_id,
        Subscription.plan_id == plan_id,
        status_condition("current"),
    )
    if exclude_id:
        query = query.filter(Subscription.id != exclude_id)
    if query.first():
        raise APIError(
            "This customer already has a current subscription to this plan. "
            "Renew the existing subscription instead.",
            409,
        )


def create_subscription(customer, plan, data, user=None):
    if customer.status != "active":
        raise APIError("Subscriptions can only be created for active customers.", 400)
    if plan.status != "active":
        raise APIError("The selected plan is inactive.", 400)

    start_date = parse_date(data.get("start_date"), "start_date", required=False) or today()
    amount = parse_amount(data.get("amount"), "amount", allow_zero=True, required=False)
    _ensure_no_duplicate(customer.id, plan.id)

    subscription = Subscription(
        customer=customer,
        plan=plan,
        start_date=start_date,
        expiry_date=calculate_expiry(start_date, plan.billing_cycle),
        amount=amount if amount is not None else plan.price,
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

    recalculate = False
    if "plan_id" in data and data["plan_id"] not in (None, "") and int(data["plan_id"]) != subscription.plan_id:
        from ..models import SubscriptionPlan
        from ..utils import get_or_404

        plan = get_or_404(SubscriptionPlan, int(data["plan_id"]), "Plan")
        if plan.status != "active":
            raise APIError("The selected plan is inactive.", 400)
        _ensure_no_duplicate(subscription.customer_id, plan.id, exclude_id=subscription.id)
        subscription.plan = plan
        recalculate = True
        if "amount" not in data:
            subscription.amount = plan.price

    if "start_date" in data:
        start_date = parse_date(data["start_date"], "start_date")
        if start_date != subscription.start_date:
            subscription.start_date = start_date
            recalculate = True

    if recalculate:
        if subscription.renewals:
            raise APIError(
                "Plan and start date cannot be changed after a subscription has been renewed. "
                "Choose a new plan when renewing instead.",
                400,
            )
        subscription.expiry_date = calculate_expiry(
            subscription.start_date, subscription.plan.billing_cycle
        )

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
    """
    from ..models import SubscriptionPlan
    from ..utils import get_or_404

    if subscription.status == "cancelled":
        raise APIError(
            "Cancelled subscriptions cannot be renewed. Create a new subscription instead.", 400
        )

    plan = subscription.plan
    if data.get("plan_id") not in (None, ""):
        plan = get_or_404(SubscriptionPlan, int(data["plan_id"]), "Plan")
    if plan.status != "active":
        raise APIError("The selected plan is inactive. Choose an active plan to renew.", 400)
    if plan.id != subscription.plan_id:
        _ensure_no_duplicate(subscription.customer_id, plan.id, exclude_id=subscription.id)

    amount = parse_amount(data.get("amount"), "amount", allow_zero=True, required=False)
    if amount is None:
        amount = subscription.amount if plan.id == subscription.plan_id else plan.price

    previous_expiry = subscription.expiry_date
    current_day = today()
    period_start = previous_expiry if previous_expiry >= current_day else current_day
    new_expiry = calculate_expiry(period_start, plan.billing_cycle)

    subscription.plan = plan
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
        plan=plan,
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
