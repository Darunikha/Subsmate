from flask import Blueprint, current_app, jsonify, request

from ..auth import current_user, login_required
from ..models import ROLE_CUSTOMER, RenewalHistory, Subscription
from ..services.analytics import upcoming_renewals
from ..services.dates import today
from ..utils import APIError, paginate

bp = Blueprint("renewals", __name__, url_prefix="/api/renewals")


def _customer_scope():
    user = current_user()
    return user.customer_id if user.role == ROLE_CUSTOMER else None


@bp.get("/upcoming")
@login_required
def upcoming():
    try:
        days = int(request.args.get("days", current_app.config["RENEWAL_WINDOW_DAYS"]))
    except ValueError:
        raise APIError("days must be an integer.", 400) from None
    days = min(max(days, 1), 365)
    subs = upcoming_renewals(days=days, customer_id=_customer_scope())
    current_day = today()
    overdue = [s.to_dict() for s in subs if s.expiry_date < current_day]
    due = [s.to_dict() for s in subs if s.expiry_date >= current_day]
    return jsonify(
        {
            "days": days,
            "overdue": overdue,
            "upcoming": due,
            "counts": {
                "overdue": len(overdue),
                "expiring_soon": sum(1 for s in due if s["status"] == "expiring_soon"),
                "upcoming": len(due),
            },
        }
    )


@bp.get("/history")
@login_required
def history():
    query = RenewalHistory.query.join(Subscription)
    customer_id = _customer_scope()
    if customer_id is not None:
        query = query.filter(Subscription.customer_id == customer_id)
    if request.args.get("subscription_id"):
        query = query.filter(RenewalHistory.subscription_id == int(request.args["subscription_id"]))
    query = query.order_by(RenewalHistory.renewed_at.desc(), RenewalHistory.id.desc())
    return jsonify(paginate(query, lambda r: r.to_dict()))
