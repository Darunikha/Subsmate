from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from ..auth import current_user, roles_required
from ..extensions import db
from ..models import (
    ACTIVE_INACTIVE,
    ROLE_ADMIN,
    ROLE_CUSTOMER,
    ROLE_STAFF,
    STAFF_ROLES,
    Customer,
    Payment,
    Subscription,
    User,
)
from ..services.dates import today
from ..utils import (
    APIError,
    clean_str,
    get_json,
    get_or_404,
    paginate,
    parse_bool,
    parse_choice,
    parse_date,
    parse_email,
    parse_password,
    parse_phone,
    require_fields,
)

bp = Blueprint("customers", __name__, url_prefix="/api/customers")


def _email_taken(email, exclude_customer=None):
    query = Customer.query.filter(Customer.email == email)
    if exclude_customer is not None:
        query = query.filter(Customer.id != exclude_customer.id)
    if query.first():
        return True
    user = User.query.filter_by(email=email).first()
    if user and (exclude_customer is None or user.customer_id != exclude_customer.id):
        return True
    return False


@bp.get("")
@roles_required(*STAFF_ROLES)
def list_customers():
    query = Customer.query
    term = request.args.get("q", "").strip()
    if term:
        like = f"%{term}%"
        query = query.filter(
            or_(Customer.full_name.ilike(like), Customer.email.ilike(like), Customer.phone.ilike(like))
        )
    if request.args.get("status"):
        query = query.filter(
            Customer.status == parse_choice(request.args["status"], "status", ACTIVE_INACTIVE)
        )
    query = query.order_by(Customer.created_at.desc(), Customer.id.desc())
    return jsonify(paginate(query, lambda c: c.to_dict(with_stats=True)))


@bp.post("")
@roles_required(ROLE_ADMIN, ROLE_STAFF)
def create_customer():
    data = get_json()
    require_fields(data, "full_name", "email")
    email = parse_email(data["email"])
    if _email_taken(email):
        raise APIError(
            "A customer or user with this email already exists.", 409, {"email": "Already registered."}
        )
    registration_date = parse_date(data.get("registration_date"), "registration_date", required=False)
    if registration_date and registration_date > today():
        raise APIError("Invalid date.", 422, {"registration_date": "Cannot be in the future."})
    customer = Customer(
        full_name=clean_str(data["full_name"], "full_name", 150, required=True),
        email=email,
        phone=parse_phone(data.get("phone")),
        status=parse_choice(data.get("status") or "active", "status", ACTIVE_INACTIVE),
        registration_date=registration_date or today(),
        created_by_id=current_user().id,
    )
    db.session.add(customer)
    if parse_bool(data.get("create_login", False)):
        login = User(name=customer.full_name, email=email, role=ROLE_CUSTOMER, customer=customer)
        login.set_password(parse_password(data.get("password")))
        db.session.add(login)
    db.session.commit()
    return jsonify(customer.to_dict(with_stats=True)), 201


@bp.get("/<int:customer_id>")
@roles_required(*STAFF_ROLES)
def get_customer(customer_id):
    customer = get_or_404(Customer, customer_id, "Customer")
    payments = (
        Payment.query.join(Subscription)
        .filter(Subscription.customer_id == customer.id)
        .order_by(Payment.id.desc())
        .all()
    )
    data = customer.to_dict(with_stats=True)
    data["subscriptions"] = [s.to_dict() for s in customer.subscriptions]
    data["payments"] = [p.to_dict() for p in payments]
    data["total_paid"] = round(sum(p.amount for p in payments if p.status == "paid"), 2)
    data["pending_amount"] = round(sum(p.amount for p in payments if p.status == "pending"), 2)
    return jsonify(data)


@bp.put("/<int:customer_id>")
@roles_required(ROLE_ADMIN, ROLE_STAFF)
def update_customer(customer_id):
    customer = get_or_404(Customer, customer_id, "Customer")
    data = get_json()
    if "full_name" in data:
        customer.full_name = clean_str(data["full_name"], "full_name", 150, required=True)
    if "email" in data:
        email = parse_email(data["email"])
        if email != customer.email:
            if _email_taken(email, exclude_customer=customer):
                raise APIError(
                    "A customer or user with this email already exists.",
                    409,
                    {"email": "Already registered."},
                )
            customer.email = email
            if customer.user:
                customer.user.email = email
    if "phone" in data:
        customer.phone = parse_phone(data["phone"])
    if "status" in data:
        customer.status = parse_choice(data["status"], "status", ACTIVE_INACTIVE)
        if customer.user:
            customer.user.is_active = customer.status == "active"
    if "registration_date" in data:
        customer.registration_date = parse_date(data["registration_date"], "registration_date")
    if parse_bool(data.get("create_login", False)) and customer.user is None:
        if User.query.filter_by(email=customer.email).first():
            raise APIError("A user with this email already exists.", 409)
        login = User(name=customer.full_name, email=customer.email, role=ROLE_CUSTOMER, customer=customer)
        login.set_password(parse_password(data.get("password")))
        db.session.add(login)
    db.session.commit()
    return jsonify(customer.to_dict(with_stats=True))


@bp.delete("/<int:customer_id>")
@roles_required(ROLE_ADMIN)
def delete_customer(customer_id):
    customer = get_or_404(Customer, customer_id, "Customer")
    if customer.subscriptions:
        raise APIError(
            "This customer has subscription and payment history, which must be kept. "
            "Mark the customer as inactive instead.",
            409,
        )
    if customer.user:
        db.session.delete(customer.user)
    db.session.delete(customer)
    db.session.commit()
    return "", 204
