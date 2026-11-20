"""Realistic demo data, generated relative to today so the dashboard always looks live."""
import random
from datetime import datetime, time, timedelta

from .extensions import db
from .models import (
    Customer,
    Payment,
    RenewalHistory,
    Subscription,
    SubscriptionPlan,
    User,
)
from .services.dates import calculate_expiry, today

DEMO_USERS = [
    ("Ava Mitchell", "admin@subsmate.io", "Admin@123", "admin"),
    ("Daniel Reyes", "sales@subsmate.io", "Sales@123", "sales"),
    ("Grace Okafor", "billing@subsmate.io", "Billing@123", "billing"),
]
DEMO_CUSTOMER_LOGIN = ("priya.sharma@brightdental.com", "Customer@123")

PLANS = [
    ("Website Care Starter", "Monthly updates, uptime monitoring and security patches for small sites.",
     29, "monthly", ["Uptime monitoring", "Monthly plugin updates", "Email support"]),
    ("Website Care Business", "Priority maintenance for business websites with content edits included.",
     79, "monthly", ["Everything in Starter", "2 hours of content edits", "Priority support", "Daily backups"]),
    ("Cloud Backup Pro", "Encrypted off-site backups with 90-day retention.",
     49, "monthly", ["500 GB storage", "90-day retention", "Restore assistance"]),
    ("IT Support Quarterly", "Remote helpdesk and device management billed every quarter.",
     249, "quarterly", ["Up to 10 devices", "Remote helpdesk", "Quarterly health check"]),
    ("SEO Growth", "Ongoing search optimisation with quarterly strategy reviews.",
     399, "quarterly", ["Keyword tracking", "Monthly report", "Quarterly strategy call"]),
    ("Managed Hosting Annual", "Fully managed hosting with SSL, CDN and staging.",
     899, "yearly", ["Managed VPS", "Free SSL & CDN", "Staging environment", "24/7 monitoring"]),
    ("Legacy Basic", "Retired entry plan kept for historical subscriptions.",
     19, "monthly", ["Basic monitoring"]),
]

CUSTOMERS = [
    ("Priya Sharma", "priya.sharma@brightdental.com", "+1 415 555 0142"),
    ("Marcus Chen", "marcus@chenarchitects.com", "+1 212 555 0198"),
    ("Sofia Alvarez", "sofia@alvarezbakery.co", "+1 305 555 0117"),
    ("Liam O'Connor", "liam@oconnorlaw.ie", "+353 1 555 0133"),
    ("Hannah Becker", "hannah.becker@beckerphysio.de", "+49 30 5550 1203"),
    ("Kwame Mensah", "kwame@mensahlogistics.com", "+233 30 555 0166"),
    ("Emily Carter", "emily@carterstudio.design", "+1 646 555 0174"),
    ("Rahul Verma", "rahul.verma@vermatextiles.in", "+91 98 5550 2211"),
    ("Chloe Dubois", "chloe@duboisflorist.fr", "+33 1 55 50 12 34"),
    ("Noah Williams", "noah@williamsplumbing.com", "+1 512 555 0109"),
    ("Aisha Khan", "aisha@khanaccounting.co.uk", "+44 20 5550 1188"),
    ("Mateo Rossi", "mateo@rossitrattoria.it", "+39 06 5550 1290"),
    ("Yuki Tanaka", "yuki@tanakatranslations.jp", "+81 3 5550 1144"),
    ("Olivia Brown", "olivia@brownrealty.com", "+1 617 555 0186"),
    ("Ethan Davis", "ethan@davisfitness.com", "+1 720 555 0151"),
    ("Zara Ahmed", "zara@ahmedclinic.ae", "+971 4 555 0127"),
    ("Lucas Martin", "lucas@martinautoparts.ca", "+1 604 555 0163"),
    ("Isabella Garcia", "isabella@garciaevents.mx", "+52 55 5550 1178"),
    ("Jacob Wilson", "jacob@wilsoncarpentry.au", "+61 2 5550 1192"),
    ("Mia Johansson", "mia@johanssondesign.se", "+46 8 555 012 45"),
    ("Daniel Kim", "daniel@kimtutoring.kr", "+82 2 5550 1136"),
    ("Grace Thompson", "grace@thompsonvet.com", "+1 503 555 0128"),
    ("Arjun Nair", "arjun@nairconsulting.in", "+91 99 5550 3344"),
    ("Fatima Hassan", "fatima@hassanboutique.com", None),
]

METHODS = ["bank_transfer", "card", "card", "upi", "cash", "cheque"]


def _dt(day, hour=10):
    return datetime.combine(day, time(hour, 0))


def seed_if_empty():
    if User.query.first() is not None:
        return False
    rng = random.Random(42)
    current_day = today()

    staff = []
    for name, email, password, role in DEMO_USERS:
        user = User(name=name, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        staff.append(user)
    admin, sales, billing = staff

    plans = []
    for name, description, price, cycle, features in PLANS:
        plan = SubscriptionPlan(
            name=name, description=description, price=price, billing_cycle=cycle,
            status="inactive" if name == "Legacy Basic" else "active",
            created_at=_dt(current_day - timedelta(days=500)),
        )
        plan.features = features
        db.session.add(plan)
        plans.append(plan)
    active_plans = [p for p in plans if p.status == "active"]
    legacy = plans[-1]

    customers = []
    for index, (full_name, email, phone) in enumerate(CUSTOMERS):
        registered = current_day - timedelta(days=rng.randint(20, 420))
        customer = Customer(
            full_name=full_name, email=email, phone=phone, registration_date=registered,
            status="inactive" if index == len(CUSTOMERS) - 2 else "active",
            created_at=_dt(registered),
        )
        db.session.add(customer)
        customers.append(customer)
    db.session.flush()
    for customer in customers:
        customer.created_by_id = sales.id

    login_email, login_password = DEMO_CUSTOMER_LOGIN
    portal_customer = next(c for c in customers if c.email == login_email)
    portal_user = User(name=portal_customer.full_name, email=login_email, role="customer",
                       customer=portal_customer)
    portal_user.set_password(login_password)
    db.session.add(portal_user)

    # The last customer is newly registered with no subscriptions yet.
    for index, customer in enumerate(customers[:-1]):
        count = 2 if index in (0, 1, 4, 7, 10, 13, 17) else 1
        chosen = rng.sample(active_plans, count)
        if index in (5, 15):
            chosen = [legacy]
        for plan in chosen:
            earliest = max((current_day - customer.registration_date).days, 1)
            offset = rng.randint(0, earliest)
            if index < 3:  # make sure the demo customer has a near-term renewal
                offset = rng.randint(20, earliest + 20)
            start = max(customer.registration_date, current_day - timedelta(days=offset))
            _build_history(rng, customer, plan, start, current_day, sales, billing, index)

    db.session.commit()
    return True


def _build_history(rng, customer, plan, start, current_day, sales, billing, index):
    sub = Subscription(
        customer=customer, plan=plan, start_date=start,
        expiry_date=calculate_expiry(start, plan.billing_cycle), amount=plan.price,
        status="active", payment_status="paid", created_by_id=sales.id,
        created_at=_dt(start, 9),
    )
    db.session.add(sub)

    def pay(period_start, status="paid"):
        paid_on = min(period_start + timedelta(days=rng.randint(0, 4)), current_day)
        payment = Payment(
            subscription=sub, amount=sub.amount, status=status, method=rng.choice(METHODS),
            due_date=period_start, paid_on=paid_on if status == "paid" else None,
            reference=f"TX-{rng.randint(100000, 999999)}" if status == "paid" else None,
            recorded_by_id=billing.id, created_at=_dt(period_start, 11),
            updated_at=_dt(paid_on if status == "paid" else period_start, 12),
        )
        db.session.add(payment)
        sub.payment_status = status
        return payment

    pay(start)
    # Walk forward through billing periods, renewing most of them.
    while sub.expiry_date <= current_day:
        will_renew = plan.status == "active" and rng.random() < 0.86
        if not will_renew:
            if rng.random() < 0.4:
                sub.status = "cancelled"
                sub.cancelled_at = _dt(sub.expiry_date - timedelta(days=rng.randint(1, 6)), 15)
                sub.cancellation_reason = rng.choice(
                    ["Switched provider", "Budget constraints", "Business closed", "No longer needed"]
                )
            break
        previous = sub.expiry_date
        renewed_on = previous - timedelta(days=rng.randint(0, 5))
        payment = pay(previous)
        new_expiry = calculate_expiry(previous, plan.billing_cycle)
        db.session.add(RenewalHistory(
            subscription=sub, plan=plan, payment=payment, previous_expiry_date=previous,
            period_start=previous, new_expiry_date=new_expiry, amount=sub.amount,
            renewed_by_id=billing.id, renewed_at=_dt(renewed_on, 14),
        ))
        sub.expiry_date = new_expiry
        sub.last_renewed_at = _dt(renewed_on, 14)

    # Current period: a mix of settled, pending and failed payments.
    if sub.status == "active" and sub.expiry_date > current_day:
        latest = sorted(sub.payments, key=lambda p: p.due_date)[-1]
        roll = rng.random()
        if roll < 0.12 or index in (2, 9):
            latest.status, latest.paid_on, latest.reference = "pending", None, None
            sub.payment_status = "pending"
        elif roll < 0.17:
            latest.status, latest.paid_on, latest.reference = "failed", None, None
            sub.payment_status = "failed"
    return sub
