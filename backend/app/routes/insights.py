"""Dashboard, reports (with CSV export), notifications and global search."""
import csv
import io
from datetime import timedelta

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import or_

from ..auth import current_user, login_required, roles_required
from ..extensions import db
from ..models import (
    ROLE_ADMIN,
    ROLE_CUSTOMER,
    Customer,
    Notification,
    Payment,
    RenewalHistory,
    Subscription,
    SubscriptionPlan,
)
from ..services import analytics
from ..services.dates import add_months, today
from ..services.notifications import generate_renewal_reminders
from ..utils import APIError, parse_date

bp = Blueprint("insights", __name__, url_prefix="/api")


# --------------------------------------------------------------------------- dashboard
@bp.get("/dashboard")
@login_required
def dashboard():
    user = current_user()
    if user.role == ROLE_CUSTOMER:
        if user.customer is None:
            raise APIError("No customer profile is linked to this account.", 404)
        return jsonify({"role": "customer", **analytics.customer_dashboard(user.customer)})
    return jsonify({"role": user.role, **analytics.staff_dashboard()})


# --------------------------------------------------------------------------- reports
def _range():
    end = parse_date(request.args.get("to"), "to", required=False) or today()
    start = parse_date(request.args.get("from"), "from", required=False) or add_months(
        end.replace(day=1), -11
    )
    if start > end:
        raise APIError("The start date must be before the end date.", 422, {"from": "After 'to'."})
    if (end - start) > timedelta(days=366 * 5):
        raise APIError("Date range is limited to 5 years.", 422)
    return start, end


@bp.get("/reports/summary")
@roles_required(ROLE_ADMIN)
def report_summary():
    start, end = _range()
    return jsonify(analytics.report_summary(start, end))


def _csv_response(filename, header, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _d(value):
    return value.isoformat() if value else ""


@bp.get("/reports/export/<string:report>")
@roles_required(ROLE_ADMIN)
def export_report(report):
    start, end = _range()
    stamp = f"{start.isoformat()}_to_{end.isoformat()}"

    if report == "revenue":
        rows = [(r["month"], r["payments"], f'{r["revenue"]:.2f}') for r in analytics.monthly_revenue(start, end)]
        return _csv_response(f"revenue_{stamp}.csv", ["Month", "Paid payments", "Revenue"], rows)

    if report == "payments":
        payments = (
            Payment.query.filter(Payment.due_date >= start, Payment.due_date <= end)
            .order_by(Payment.due_date)
            .all()
        )
        rows = [
            (
                p.code, p.subscription.code, p.subscription.customer.full_name,
                p.subscription.plan.name, f"{p.amount:.2f}", p.status, p.method or "",
                _d(p.due_date), _d(p.paid_on), p.reference or "",
            )
            for p in payments
        ]
        header = ["Payment", "Subscription", "Customer", "Plan", "Amount", "Status", "Method",
                  "Due date", "Paid on", "Reference"]
        return _csv_response(f"payments_{stamp}.csv", header, rows)

    if report == "pending-payments":
        payments = Payment.query.filter(Payment.status == "pending").order_by(Payment.due_date).all()
        rows = [
            (
                p.code, p.subscription.customer.full_name, p.subscription.customer.email,
                p.subscription.plan.name, f"{p.amount:.2f}", _d(p.due_date),
                "yes" if p.is_overdue else "no",
            )
            for p in payments
        ]
        header = ["Payment", "Customer", "Email", "Plan", "Amount", "Due date", "Overdue"]
        return _csv_response(f"pending_payments_{today().isoformat()}.csv", header, rows)

    if report == "subscriptions":
        subs = (
            Subscription.query.filter(Subscription.start_date <= end, Subscription.expiry_date >= start)
            .order_by(Subscription.id)
            .all()
        )
        rows = [
            (
                s.code, s.customer.full_name, s.customer.email, s.plan.name, s.plan.billing_cycle,
                _d(s.start_date), _d(s.expiry_date), f"{s.amount:.2f}", s.payment_status,
                s.effective_status, len(s.renewals),
            )
            for s in subs
        ]
        header = ["Subscription", "Customer", "Email", "Plan", "Billing cycle", "Start date",
                  "Expiry date", "Amount", "Payment status", "Status", "Renewals"]
        return _csv_response(f"subscriptions_{stamp}.csv", header, rows)

    if report == "plans":
        summary = analytics.report_summary(start, end)
        rows = [
            (r["plan"], r["billing_cycle"], r["active"], r["subscriptions"], f'{r["revenue"]:.2f}')
            for r in summary["plan_popularity"]
        ]
        header = ["Plan", "Billing cycle", "Active subscriptions", "Total subscriptions", "Revenue in range"]
        return _csv_response(f"plan_popularity_{stamp}.csv", header, rows)

    if report == "renewals":
        renewals = (
            RenewalHistory.query.filter(
                db.func.date(RenewalHistory.renewed_at) >= start.isoformat(),
                db.func.date(RenewalHistory.renewed_at) <= end.isoformat(),
            )
            .order_by(RenewalHistory.renewed_at)
            .all()
        )
        rows = [
            (
                r.renewed_at.strftime("%Y-%m-%d %H:%M"), r.subscription.code,
                r.subscription.customer.full_name, r.plan.name, _d(r.previous_expiry_date),
                _d(r.new_expiry_date), f"{r.amount:.2f}", r.payment.status if r.payment else "",
                r.renewed_by.name if r.renewed_by else "",
            )
            for r in renewals
        ]
        header = ["Renewed at", "Subscription", "Customer", "Plan", "Previous expiry", "New expiry",
                  "Amount", "Payment status", "Renewed by"]
        return _csv_response(f"renewals_{stamp}.csv", header, rows)

    if report == "customers":
        customers = Customer.query.order_by(Customer.id).all()
        rows = [
            (
                c.code, c.full_name, c.email, c.phone or "", c.status, _d(c.registration_date),
                len(c.subscriptions),
                sum(1 for s in c.subscriptions if s.effective_status in ("active", "expiring_soon")),
            )
            for c in customers
        ]
        header = ["Customer", "Full name", "Email", "Phone", "Status", "Registered",
                  "Subscriptions", "Active subscriptions"]
        return _csv_response("customers.csv", header, rows)

    raise APIError("Unknown report.", 404)


# --------------------------------------------------------------------------- notifications
@bp.get("/notifications")
@login_required
def list_notifications():
    generate_renewal_reminders()
    user = current_user()
    query = Notification.query.filter_by(user_id=user.id)
    unread = query.filter_by(is_read=False).count()
    items = query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(30).all()
    return jsonify({"items": [n.to_dict() for n in items], "unread": unread})


@bp.post("/notifications/<int:notification_id>/read")
@login_required
def mark_read(notification_id):
    note = Notification.query.filter_by(id=notification_id, user_id=current_user().id).first()
    if note is None:
        raise APIError("Notification not found.", 404)
    note.is_read = True
    db.session.commit()
    return jsonify(note.to_dict())


@bp.post("/notifications/read-all")
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user().id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"message": "All notifications marked as read."})


# --------------------------------------------------------------------------- search
@bp.get("/search")
@login_required
def search():
    term = request.args.get("q", "").strip()
    if len(term) < 2:
        return jsonify({"customers": [], "subscriptions": [], "plans": []})
    like = f"%{term}%"
    user = current_user()

    subs = Subscription.query.join(Customer).join(SubscriptionPlan).filter(
        or_(Customer.full_name.ilike(like), Customer.email.ilike(like), SubscriptionPlan.name.ilike(like))
    )
    if user.role == ROLE_CUSTOMER:
        subs = subs.filter(Subscription.customer_id == user.customer_id)
    result = {"subscriptions": [s.summary() for s in subs.order_by(Subscription.id.desc()).limit(5)]}

    if user.role == ROLE_CUSTOMER:
        result["customers"] = []
        plans = SubscriptionPlan.query.filter(SubscriptionPlan.status == "active")
    else:
        customers = Customer.query.filter(
            or_(Customer.full_name.ilike(like), Customer.email.ilike(like), Customer.phone.ilike(like))
        ).limit(5)
        result["customers"] = [c.to_dict() for c in customers]
        plans = SubscriptionPlan.query
    result["plans"] = [p.to_dict() for p in plans.filter(SubscriptionPlan.name.ilike(like)).limit(5)]
    return jsonify(result)
