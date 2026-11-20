from flask import Blueprint, jsonify, request

from ..auth import current_user, login_required, roles_required
from ..extensions import db
from ..models import ACTIVE_INACTIVE, BILLING_CYCLES, ROLE_ADMIN, ROLE_CUSTOMER, SubscriptionPlan
from ..utils import (
    APIError,
    clean_str,
    get_json,
    get_or_404,
    parse_amount,
    parse_choice,
    require_fields,
)

bp = Blueprint("plans", __name__, url_prefix="/api/plans")


def _parse_features(value):
    if value is None:
        return []
    if isinstance(value, str):
        value = value.splitlines()
    if not isinstance(value, list):
        raise APIError("Invalid features.", 422, {"features": "Provide a list of features."})
    features = [str(v).strip() for v in value if str(v).strip()]
    if len(features) > 30:
        raise APIError("Too many features.", 422, {"features": "At most 30 features."})
    return features


def _name_taken(name, exclude_id=None):
    query = SubscriptionPlan.query.filter(db.func.lower(SubscriptionPlan.name) == name.lower())
    if exclude_id:
        query = query.filter(SubscriptionPlan.id != exclude_id)
    return query.first() is not None


@bp.get("")
@login_required
def list_plans():
    query = SubscriptionPlan.query
    status = request.args.get("status")
    if current_user().role == ROLE_CUSTOMER:
        status = "active"
    if status:
        query = query.filter(SubscriptionPlan.status == parse_choice(status, "status", ACTIVE_INACTIVE))
    plans = query.order_by(SubscriptionPlan.status, SubscriptionPlan.price).all()
    with_stats = current_user().role != ROLE_CUSTOMER
    return jsonify({"items": [p.to_dict(with_stats=with_stats) for p in plans], "total": len(plans)})


@bp.post("")
@roles_required(ROLE_ADMIN)
def create_plan():
    data = get_json()
    require_fields(data, "name", "price", "billing_cycle")
    name = clean_str(data["name"], "name", 120, required=True)
    if _name_taken(name):
        raise APIError("A plan with this name already exists.", 409, {"name": "Already exists."})
    plan = SubscriptionPlan(
        name=name,
        description=clean_str(data.get("description"), "description", 1000),
        price=parse_amount(data["price"], "price", allow_zero=True),
        billing_cycle=parse_choice(data["billing_cycle"], "billing_cycle", tuple(BILLING_CYCLES)),
        status=parse_choice(data.get("status") or "active", "status", ACTIVE_INACTIVE),
    )
    plan.features = _parse_features(data.get("features"))
    db.session.add(plan)
    db.session.commit()
    return jsonify(plan.to_dict(with_stats=True)), 201


@bp.get("/<int:plan_id>")
@login_required
def get_plan(plan_id):
    plan = get_or_404(SubscriptionPlan, plan_id, "Plan")
    if current_user().role == ROLE_CUSTOMER and plan.status != "active":
        raise APIError("Plan not found.", 404)
    return jsonify(plan.to_dict(with_stats=current_user().role != ROLE_CUSTOMER))


@bp.put("/<int:plan_id>")
@roles_required(ROLE_ADMIN)
def update_plan(plan_id):
    plan = get_or_404(SubscriptionPlan, plan_id, "Plan")
    data = get_json()
    if "name" in data:
        name = clean_str(data["name"], "name", 120, required=True)
        if _name_taken(name, exclude_id=plan.id):
            raise APIError("A plan with this name already exists.", 409, {"name": "Already exists."})
        plan.name = name
    if "description" in data:
        plan.description = clean_str(data["description"], "description", 1000)
    if "price" in data:
        # Existing subscriptions keep their agreed amount; new ones use the new price.
        plan.price = parse_amount(data["price"], "price", allow_zero=True)
    if "billing_cycle" in data:
        cycle = parse_choice(data["billing_cycle"], "billing_cycle", tuple(BILLING_CYCLES))
        if cycle != plan.billing_cycle and plan.subscriptions:
            raise APIError(
                "The billing cycle cannot be changed once a plan has subscriptions. "
                "Create a new plan instead.",
                400,
            )
        plan.billing_cycle = cycle
    if "features" in data:
        plan.features = _parse_features(data["features"])
    if "status" in data:
        plan.status = parse_choice(data["status"], "status", ACTIVE_INACTIVE)
    db.session.commit()
    return jsonify(plan.to_dict(with_stats=True))


@bp.delete("/<int:plan_id>")
@roles_required(ROLE_ADMIN)
def delete_plan(plan_id):
    plan = get_or_404(SubscriptionPlan, plan_id, "Plan")
    if plan.subscriptions:
        raise APIError(
            "This plan has subscriptions and cannot be deleted. Mark it inactive instead.", 409
        )
    db.session.delete(plan)
    db.session.commit()
    return "", 204
