from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from ..auth import current_user, login_required, roles_required
from ..extensions import db
from ..models import (
    PAYMENT_STATUSES,
    ROLE_ADMIN,
    ROLE_BILLING,
    ROLE_CUSTOMER,
    Customer,
    Payment,
    Subscription,
)
from ..services.dates import today
from ..services.payments import record_payment, update_payment
from ..utils import APIError, get_json, get_or_404, paginate, parse_bool, parse_choice, parse_date, require_fields

bp = Blueprint("payments", __name__, url_prefix="/api/payments")


def _scoped():
    query = Payment.query.join(Subscription).join(Customer)
    user = current_user()
    if user.role == ROLE_CUSTOMER:
        query = query.filter(Subscription.customer_id == user.customer_id)
    elif user.role not in (ROLE_ADMIN, ROLE_BILLING):
        raise APIError("You do not have permission to view payments.", 403)
    return query


@bp.get("")
@login_required
def list_payments():
    query = _scoped()
    args = request.args
    if args.get("status"):
        query = query.filter(Payment.status == parse_choice(args["status"], "status", PAYMENT_STATUSES))
    if args.get("subscription_id"):
        query = query.filter(Payment.subscription_id == int(args["subscription_id"]))
    if parse_bool(args.get("overdue", False)):
        query = query.filter(Payment.status != "paid", Payment.due_date < today())
    date_from = parse_date(args.get("from"), "from", required=False)
    date_to = parse_date(args.get("to"), "to", required=False)
    date_col = Payment.paid_on if args.get("status") == "paid" else Payment.due_date
    if date_from:
        query = query.filter(date_col >= date_from)
    if date_to:
        query = query.filter(date_col <= date_to)
    term = args.get("q", "").strip()
    if term:
        like = f"%{term}%"
        query = query.filter(
            or_(Customer.full_name.ilike(like), Customer.email.ilike(like), Payment.reference.ilike(like))
        )
    query = query.order_by(Payment.id.desc())
    result = paginate(query, lambda p: p.to_dict())

    totals = (
        _scoped()
        .with_entities(Payment.status, db.func.count(Payment.id), db.func.coalesce(db.func.sum(Payment.amount), 0))
        .group_by(Payment.status)
        .all()
    )
    result["summary"] = {
        status: {"count": count, "amount": round(float(amount), 2)} for status, count, amount in totals
    }
    return jsonify(result)


@bp.post("")
@roles_required(ROLE_ADMIN, ROLE_BILLING)
def create_payment():
    data = get_json()
    require_fields(data, "subscription_id")
    sub = get_or_404(Subscription, int(data["subscription_id"]), "Subscription")
    paid_on = parse_date(data.get("paid_on"), "paid_on", required=False)
    if paid_on and paid_on > today():
        raise APIError("Paid date cannot be in the future.", 422, {"paid_on": "Future date."})
    payment = record_payment(sub, data, current_user())
    db.session.commit()
    return jsonify(payment.to_dict()), 201


@bp.get("/<int:payment_id>")
@login_required
def get_payment(payment_id):
    payment = _scoped().filter(Payment.id == payment_id).first()
    if payment is None:
        raise APIError("Payment not found.", 404)
    return jsonify(payment.to_dict())


@bp.put("/<int:payment_id>")
@roles_required(ROLE_ADMIN, ROLE_BILLING)
def edit_payment(payment_id):
    payment = get_or_404(Payment, payment_id, "Payment")
    update_payment(payment, get_json(), current_user())
    db.session.commit()
    return jsonify(payment.to_dict())
