"""Manual payment tracking."""
from ..extensions import db
from ..models import PAYMENT_METHODS, PAYMENT_STATUSES, Payment
from ..utils import APIError, clean_str, parse_amount, parse_choice, parse_date
from .dates import today


def sync_payment_status(subscription):
    """A subscription's payment status mirrors its most recent payment record."""
    latest = (
        Payment.query.filter_by(subscription_id=subscription.id)
        .order_by(Payment.id.desc())
        .first()
    )
    subscription.payment_status = latest.status if latest else "pending"


def record_payment(subscription, data, user=None):
    """Create a payment for ``subscription`` from a validated-on-entry dict."""
    status = parse_choice(data.get("status") or "pending", "status", PAYMENT_STATUSES)
    amount = parse_amount(
        data.get("amount") if data.get("amount") not in (None, "") else subscription.amount,
        "amount",
    )
    paid_on = parse_date(data.get("paid_on"), "paid_on", required=False)
    payment = Payment(
        subscription=subscription,
        amount=amount,
        status=status,
        method=parse_choice(data.get("method"), "method", PAYMENT_METHODS, required=False),
        due_date=parse_date(data.get("due_date"), "due_date", required=False) or today(),
        paid_on=(paid_on or today()) if status == "paid" else None,
        reference=clean_str(data.get("reference"), "reference", 120),
        notes=clean_str(data.get("notes"), "notes", 1000),
        recorded_by_id=user.id if user else None,
    )
    db.session.add(payment)
    db.session.flush()
    sync_payment_status(subscription)
    if status == "failed":
        from .notifications import notify_payment_failed

        notify_payment_failed(payment)
    return payment


def update_payment(payment, data, user=None):
    if "status" in data:
        payment.status = parse_choice(data["status"], "status", PAYMENT_STATUSES)
    if "amount" in data:
        payment.amount = parse_amount(data["amount"], "amount")
    if "method" in data:
        payment.method = parse_choice(data["method"], "method", PAYMENT_METHODS, required=False)
    if "reference" in data:
        payment.reference = clean_str(data["reference"], "reference", 120)
    if "notes" in data:
        payment.notes = clean_str(data["notes"], "notes", 1000)
    if "due_date" in data:
        payment.due_date = parse_date(data["due_date"], "due_date")
    if payment.status == "paid":
        paid_on = parse_date(data.get("paid_on"), "paid_on", required=False)
        payment.paid_on = paid_on or payment.paid_on or today()
        if payment.paid_on > today():
            raise APIError("Paid date cannot be in the future.", 422, {"paid_on": "Future date."})
    else:
        payment.paid_on = None
    if user:
        payment.recorded_by_id = user.id
    db.session.flush()
    sync_payment_status(payment.subscription)
    if payment.status == "failed":
        from .notifications import notify_payment_failed

        notify_payment_failed(payment)
    return payment
