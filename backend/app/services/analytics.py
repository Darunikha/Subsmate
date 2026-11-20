"""Dashboard and report calculations. Everything is computed from database rows."""
from datetime import timedelta

from flask import current_app
from sqlalchemy import func

from ..extensions import db
from ..models import Customer, Payment, RenewalHistory, Subscription, SubscriptionPlan
from .dates import add_months, month_range, today
from .subscriptions import status_condition


def _round(value):
    return round(float(value or 0), 2)


def count_by_status():
    return {
        status: Subscription.query.filter(status_condition(status)).count()
        for status in ("active", "expiring_soon", "expired", "cancelled")
    }


def revenue_between(start, end):
    """Sum of successful (paid) payments with paid_on in [start, end]."""
    total = (
        db.session.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.status == "paid", Payment.paid_on >= start, Payment.paid_on <= end)
        .scalar()
    )
    return _round(total)


def monthly_revenue(start, end):
    rows = (
        db.session.query(
            func.strftime("%Y-%m", Payment.paid_on).label("month"),
            func.sum(Payment.amount),
            func.count(Payment.id),
        )
        .filter(Payment.status == "paid", Payment.paid_on >= start, Payment.paid_on <= end)
        .group_by("month")
        .all()
    )
    by_month = {month: (total, count) for month, total, count in rows}
    return [
        {
            "month": key,
            "revenue": _round(by_month.get(key, (0, 0))[0]),
            "payments": by_month.get(key, (0, 0))[1],
        }
        for key in month_range(start, end)
    ]


def upcoming_renewals(days=None, limit=None, customer_id=None):
    """Live subscriptions expiring within ``days`` plus overdue (expired) ones."""
    days = days if days is not None else current_app.config["RENEWAL_WINDOW_DAYS"]
    horizon = today() + timedelta(days=days)
    query = Subscription.query.filter(
        Subscription.status == "active", Subscription.expiry_date <= horizon
    ).order_by(Subscription.expiry_date.asc())
    if customer_id is not None:
        query = query.filter(Subscription.customer_id == customer_id)
    if limit:
        query = query.limit(limit)
    return query.all()


def recent_activity(limit=8):
    events = []
    for sub in Subscription.query.order_by(Subscription.created_at.desc()).limit(limit):
        events.append(
            {
                "type": "subscription_created",
                "title": f"New subscription · {sub.plan.name}",
                "description": sub.customer.full_name,
                "subscription_id": sub.id,
                "amount": _round(sub.amount),
                "timestamp": sub.created_at.isoformat(),
            }
        )
    for renewal in RenewalHistory.query.order_by(RenewalHistory.renewed_at.desc()).limit(limit):
        events.append(
            {
                "type": "renewal",
                "title": f"Renewed · {renewal.plan.name}",
                "description": renewal.subscription.customer.full_name,
                "subscription_id": renewal.subscription_id,
                "amount": _round(renewal.amount),
                "timestamp": renewal.renewed_at.isoformat(),
            }
        )
    for payment in (
        Payment.query.filter(Payment.status.in_(("paid", "failed")))
        .order_by(Payment.updated_at.desc())
        .limit(limit)
    ):
        events.append(
            {
                "type": "payment_" + payment.status,
                "title": "Payment received" if payment.status == "paid" else "Payment failed",
                "description": payment.subscription.customer.full_name,
                "subscription_id": payment.subscription_id,
                "amount": _round(payment.amount),
                "timestamp": payment.updated_at.isoformat(),
            }
        )
    for sub in (
        Subscription.query.filter(Subscription.cancelled_at.isnot(None))
        .order_by(Subscription.cancelled_at.desc())
        .limit(limit)
    ):
        events.append(
            {
                "type": "cancelled",
                "title": f"Cancelled · {sub.plan.name}",
                "description": sub.customer.full_name,
                "subscription_id": sub.id,
                "amount": None,
                "timestamp": sub.cancelled_at.isoformat(),
            }
        )
    events.sort(key=lambda e: e["timestamp"], reverse=True)
    return events[:limit]


def staff_dashboard():
    current_day = today()
    month_start = current_day.replace(day=1)
    prev_month_start = add_months(month_start, -1)
    prev_month_end = month_start - timedelta(days=1)
    statuses = count_by_status()
    window = current_app.config["RENEWAL_WINDOW_DAYS"]
    upcoming = upcoming_renewals()
    pending = db.session.query(
        func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0)
    ).filter(Payment.status == "pending").one()

    revenue_this_month = revenue_between(month_start, current_day)
    revenue_last_month = revenue_between(prev_month_start, prev_month_end)
    # Compare month-to-date against the same span of last month, not the whole month.
    same_span_end = min(prev_month_start + (current_day - month_start), prev_month_end)
    revenue_same_span = revenue_between(prev_month_start, same_span_end)
    change = None
    if revenue_same_span:
        change = round((revenue_this_month - revenue_same_span) / revenue_same_span * 100, 1)

    return {
        "stats": {
            "total_customers": Customer.query.count(),
            "active_customers": Customer.query.filter_by(status="active").count(),
            "active_subscriptions": statuses["active"] + statuses["expiring_soon"],
            "expired_subscriptions": statuses["expired"],
            "upcoming_renewals": sum(1 for s in upcoming if s.expiry_date >= current_day),
            "overdue_renewals": sum(1 for s in upcoming if s.expiry_date < current_day),
            "monthly_revenue": revenue_this_month,
            "last_month_revenue": revenue_last_month,
            "revenue_change_pct": change,
            "pending_payments": pending[0],
            "pending_amount": _round(pending[1]),
        },
        "status_overview": statuses,
        "revenue_chart": monthly_revenue(add_months(month_start, -5), current_day),
        "upcoming_renewals": [
            s.to_dict() for s in upcoming if s.expiry_date >= current_day
        ][:5],
        "recent_activity": recent_activity(),
        "renewal_window_days": window,
    }


def customer_dashboard(customer):
    current_day = today()
    subs = customer.subscriptions
    payments = (
        Payment.query.join(Subscription)
        .filter(Subscription.customer_id == customer.id)
        .order_by(Payment.id.desc())
        .all()
    )
    live = [s for s in subs if s.effective_status in ("active", "expiring_soon")]
    next_renewal = min(live, key=lambda s: s.expiry_date) if live else None
    return {
        "customer": customer.to_dict(),
        "stats": {
            "active_subscriptions": len(live),
            "expired_subscriptions": sum(1 for s in subs if s.effective_status == "expired"),
            "total_paid": _round(sum(p.amount for p in payments if p.status == "paid")),
            "pending_amount": _round(sum(p.amount for p in payments if p.status == "pending")),
            "next_renewal": next_renewal.to_dict() if next_renewal else None,
        },
        "subscriptions": [s.to_dict() for s in subs],
        "upcoming_renewals": [
            s.to_dict()
            for s in upcoming_renewals(customer_id=customer.id)
        ],
        "recent_payments": [p.to_dict() for p in payments[:5]],
        "today": current_day.isoformat(),
    }


def report_summary(start, end):
    statuses = count_by_status()
    revenue = monthly_revenue(start, end)

    pending_rows = (
        Payment.query.filter(Payment.status.in_(("pending", "failed")))
        .order_by(Payment.due_date.asc())
        .all()
    )
    pending = [p for p in pending_rows if p.status == "pending"]

    plan_rows = (
        db.session.query(
            SubscriptionPlan,
            func.count(Subscription.id),
        )
        .outerjoin(
            Subscription,
            (Subscription.plan_id == SubscriptionPlan.id)
            & (Subscription.start_date <= end),
        )
        .group_by(SubscriptionPlan.id)
        .all()
    )
    plan_revenue = dict(
        db.session.query(Subscription.plan_id, func.sum(Payment.amount))
        .join(Payment, Payment.subscription_id == Subscription.id)
        .filter(Payment.status == "paid", Payment.paid_on >= start, Payment.paid_on <= end)
        .group_by(Subscription.plan_id)
        .all()
    )
    active_by_plan = dict(
        db.session.query(Subscription.plan_id, func.count(Subscription.id))
        .filter(status_condition("current"))
        .group_by(Subscription.plan_id)
        .all()
    )
    plan_popularity = sorted(
        (
            {
                "plan_id": plan.id,
                "plan": plan.name,
                "billing_cycle": plan.billing_cycle,
                "subscriptions": total,
                "active": active_by_plan.get(plan.id, 0),
                "revenue": _round(plan_revenue.get(plan.id)),
            }
            for plan, total in plan_rows
        ),
        key=lambda row: (row["active"], row["subscriptions"]),
        reverse=True,
    )

    # Customer distribution: how many current subscriptions each customer holds.
    current_counts = dict(
        db.session.query(Subscription.customer_id, func.count(Subscription.id))
        .filter(status_condition("current"))
        .group_by(Subscription.customer_id)
        .all()
    )
    buckets = {"No active subscription": 0, "1 subscription": 0, "2 subscriptions": 0, "3+ subscriptions": 0}
    for (customer_id,) in db.session.query(Customer.id):
        n = current_counts.get(customer_id, 0)
        label = (
            "No active subscription" if n == 0
            else "1 subscription" if n == 1
            else "2 subscriptions" if n == 2
            else "3+ subscriptions"
        )
        buckets[label] += 1

    renewal_rows = dict(
        db.session.query(
            func.strftime("%Y-%m", RenewalHistory.renewed_at), func.count(RenewalHistory.id)
        )
        .filter(
            func.date(RenewalHistory.renewed_at) >= start.isoformat(),
            func.date(RenewalHistory.renewed_at) <= end.isoformat(),
        )
        .group_by(func.strftime("%Y-%m", RenewalHistory.renewed_at))
        .all()
    )
    new_rows = dict(
        db.session.query(
            func.strftime("%Y-%m", Subscription.start_date), func.count(Subscription.id)
        )
        .filter(Subscription.start_date >= start, Subscription.start_date <= end)
        .group_by(func.strftime("%Y-%m", Subscription.start_date))
        .all()
    )
    cancel_rows = dict(
        db.session.query(
            func.strftime("%Y-%m", Subscription.cancelled_at), func.count(Subscription.id)
        )
        .filter(
            Subscription.cancelled_at.isnot(None),
            func.date(Subscription.cancelled_at) >= start.isoformat(),
            func.date(Subscription.cancelled_at) <= end.isoformat(),
        )
        .group_by(func.strftime("%Y-%m", Subscription.cancelled_at))
        .all()
    )
    trends = [
        {
            "month": key,
            "renewals": renewal_rows.get(key, 0),
            "new_subscriptions": new_rows.get(key, 0),
            "cancellations": cancel_rows.get(key, 0),
        }
        for key in month_range(start, end)
    ]

    return {
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "totals": {
            "active_subscriptions": statuses["active"] + statuses["expiring_soon"],
            "expiring_soon": statuses["expiring_soon"],
            "expired_subscriptions": statuses["expired"],
            "cancelled_subscriptions": statuses["cancelled"],
            "revenue": _round(sum(r["revenue"] for r in revenue)),
            "pending_count": len(pending),
            "pending_amount": _round(sum(p.amount for p in pending)),
            "overdue_count": sum(1 for p in pending if p.is_overdue),
            "renewals": sum(t["renewals"] for t in trends),
        },
        "monthly_revenue": revenue,
        "pending_payments": [p.to_dict() for p in pending_rows[:50]],
        "plan_popularity": plan_popularity,
        "customer_distribution": [{"label": k, "customers": v} for k, v in buckets.items()],
        "renewal_trends": trends,
    }
