"""User management (administrators only)."""
from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from ..auth import current_user, roles_required
from ..extensions import db
from ..models import ROLE_ADMIN, ROLE_CUSTOMER, ROLES, Customer, User
from ..utils import (
    APIError,
    clean_str,
    get_json,
    get_or_404,
    paginate,
    parse_bool,
    parse_choice,
    parse_email,
    parse_password,
    require_fields,
)

bp = Blueprint("users", __name__, url_prefix="/api/users")


@bp.get("")
@roles_required(ROLE_ADMIN)
def list_users():
    query = User.query
    term = request.args.get("q", "").strip()
    if term:
        like = f"%{term}%"
        query = query.filter(or_(User.name.ilike(like), User.email.ilike(like)))
    if request.args.get("role"):
        query = query.filter(User.role == request.args["role"])
    return jsonify(paginate(query.order_by(User.role, User.name), lambda u: u.to_dict()))


@bp.post("")
@roles_required(ROLE_ADMIN)
def create_user():
    data = get_json()
    require_fields(data, "name", "email", "password", "role")
    email = parse_email(data["email"])
    if User.query.filter_by(email=email).first():
        raise APIError("A user with this email already exists.", 409, {"email": "Already in use."})
    role = parse_choice(data["role"], "role", ROLES)
    user = User(name=clean_str(data["name"], "name", 120, required=True), email=email, role=role)
    user.set_password(parse_password(data["password"]))
    if role == ROLE_CUSTOMER:
        customer = Customer.query.filter_by(email=email).first()
        if customer is None:
            raise APIError(
                "Customer logins must match an existing customer's email. "
                "Register the customer first.",
                422,
                {"email": "No customer with this email."},
            )
        if customer.user is not None:
            raise APIError("This customer already has a login.", 409)
        user.customer = customer
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@bp.put("/<int:user_id>")
@roles_required(ROLE_ADMIN)
def update_user(user_id):
    user = get_or_404(User, user_id, "User")
    data = get_json()
    me = current_user()
    if "name" in data:
        user.name = clean_str(data["name"], "name", 120, required=True)
    if "email" in data:
        email = parse_email(data["email"])
        clash = User.query.filter(User.email == email, User.id != user.id).first()
        if clash:
            raise APIError("A user with this email already exists.", 409, {"email": "Already in use."})
        user.email = email
    if "role" in data:
        role = parse_choice(data["role"], "role", ROLES)
        if user.id == me.id and role != user.role:
            raise APIError("You cannot change your own role.", 400)
        if (role == ROLE_CUSTOMER) != (user.role == ROLE_CUSTOMER):
            raise APIError("Customer logins cannot be converted to staff accounts or vice versa.", 400)
        user.role = role
    if "is_active" in data:
        active = parse_bool(data["is_active"])
        if user.id == me.id and not active:
            raise APIError("You cannot deactivate your own account.", 400)
        user.is_active = active
    if data.get("password"):
        user.set_password(parse_password(data["password"]))
    db.session.commit()
    return jsonify(user.to_dict())


@bp.delete("/<int:user_id>")
@roles_required(ROLE_ADMIN)
def delete_user(user_id):
    user = get_or_404(User, user_id, "User")
    if user.id == current_user().id:
        raise APIError("You cannot delete your own account.", 400)
    db.session.delete(user)
    db.session.commit()
    return "", 204
