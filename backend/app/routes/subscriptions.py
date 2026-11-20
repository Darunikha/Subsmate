from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from ..auth import current_user, login_required, roles_required
from ..extensions import db
from ..models import (
    ROLE_ADMIN,
    ROLE_CUSTOMER,
    ROLE_STAFF,
    Customer,
    Subscription,
    SubscriptionPlan,
)
from ..services import subscriptions as service
from ..utils import APIError, get_json, get_or_404, paginate, require_fields

bp = Blueprint("subscriptions", __name__, url_prefix="/api/subscriptions")


def scoped_query():
    """Customers only ever see their own subscriptions."""
    query = Subscription.query
    user = current_user()
    if user.role == ROLE_CUSTOMER:
        query = query.filter(Subscription.customer_id == user.customer_id)
    return query


def get_accessible_subscription(subscription_id):
    sub = scoped_query().filter(Subscription.id == subscription_id).first()
    if sub is None:
        raise APIError("Subscription not found.", 404)
    return sub


@bp.get("")
@login_required
def list_subscriptions():
    query = scoped_query().join(Customer).join(SubscriptionPlan)
    args = request.args
    if args.get("status"):
        query = query.filter(service.status_condition(args["status"]))
    if args.get("customer_id"):
        query = query.filter(Subscription.customer_id == int(args["customer_id"]))
    if args.get("plan_id"):
        query = query.filter(Subscription.plan_id == int(args["plan_id"]))
    if args.get("payment_status"):
        query = query.filter(Subscription.payment_status == args["payment_status"])
    term = args.get("q", "").strip()
    if term:
        like = f"%{term}%"
        conditions = [
            Customer.full_name.ilike(like),
            Customer.email.ilike(like),
            SubscriptionPlan.name.ilike(like),
        ]
        digits = term.upper().removeprefix("SUB-").lstrip("0")
        if digits.isdigit():
            conditions.append(Subscription.id == int(digits))
        query = query.filter(or_(*conditions))
    sort = args.get("sort", "recent")
    order = {
        "expiry": Subscription.expiry_date.asc(),
        "amount": Subscription.amount.desc(),
    }.get(sort, Subscription.id.desc())
    return jsonify(paginate(query.order_by(order), lambda s: s.to_dict()))


@bp.post("")
@roles_required(ROLE_ADMIN, ROLE_STAFF)
def create_subscription():
    data = get_json()
    require_fields(data, "customer_id", "plan_id")
    customer = get_or_404(Customer, int(data["customer_id"]), "Customer")
    plan = get_or_404(SubscriptionPlan, int(data["plan_id"]), "Plan")
    sub = service.create_subscription(customer, plan, data, current_user())
    db.session.commit()
    return jsonify(sub.to_dict(detail=True)), 201


@bp.get("/<int:subscription_id>")
@login_required
def get_subscription(subscription_id):
    return jsonify(get_accessible_subscription(subscription_id).to_dict(detail=True))


@bp.put("/<int:subscription_id>")
@roles_required(ROLE_ADMIN, ROLE_STAFF)
def update_subscription(subscription_id):
    sub = get_or_404(Subscription, subscription_id, "Subscription")
    service.update_subscription(sub, get_json())
    db.session.commit()
    return jsonify(sub.to_dict(detail=True))


@bp.post("/<int:subscription_id>/cancel")
@roles_required(ROLE_ADMIN, ROLE_STAFF)
def cancel_subscription(subscription_id):
    sub = get_or_404(Subscription, subscription_id, "Subscription")
    data = request.get_json(silent=True) or {}
    service.cancel_subscription(sub, data.get("reason"))
    db.session.commit()
    return jsonify(sub.to_dict(detail=True))


@bp.post("/<int:subscription_id>/renew")
@roles_required(ROLE_ADMIN, ROLE_STAFF)
def renew_subscription(subscription_id):
    sub = get_or_404(Subscription, subscription_id, "Subscription")
    data = request.get_json(silent=True) or {}
    sub, renewal = service.renew_subscription(sub, data, current_user())
    db.session.commit()
    return jsonify({"subscription": sub.to_dict(detail=True), "renewal": renewal.to_dict()})
