from flask import Blueprint, jsonify

from ..auth import current_user, generate_token, login_required
from ..extensions import db
from ..models import User, utcnow
from ..utils import APIError, clean_str, get_json, parse_password, require_fields

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/login")
def login():
    data = get_json()
    require_fields(data, "email", "password")
    email = str(data["email"]).strip().lower()
    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(str(data["password"])):
        raise APIError("Invalid email or password.", 401)
    if not user.is_active:
        raise APIError("This account has been deactivated. Contact your administrator.", 403)
    user.last_login_at = utcnow()
    db.session.commit()
    return jsonify({"token": generate_token(user), "user": user.to_dict()})


@bp.get("/me")
@login_required
def me():
    return jsonify(current_user().to_dict())


@bp.put("/me")
@login_required
def update_me():
    data = get_json()
    user = current_user()
    if "name" in data:
        user.name = clean_str(data["name"], "name", 120, required=True)
    db.session.commit()
    return jsonify(user.to_dict())


@bp.post("/change-password")
@login_required
def change_password():
    data = get_json()
    require_fields(data, "current_password", "new_password")
    user = current_user()
    if not user.check_password(str(data["current_password"])):
        raise APIError(
            "Current password is incorrect.", 422, {"current_password": "Incorrect password."}
        )
    user.set_password(parse_password(data["new_password"], "new_password"))
    db.session.commit()
    # Old tokens are invalidated; hand back a fresh one.
    return jsonify({"message": "Password updated.", "token": generate_token(user)})
