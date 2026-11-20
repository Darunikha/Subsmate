"""Token authentication and role-based authorization."""
from functools import wraps

from flask import current_app, g, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .extensions import db
from .models import User
from .utils import APIError

TOKEN_SALT = "subsmate-auth"


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=TOKEN_SALT)


def generate_token(user):
    # Embedding a password-hash fragment invalidates tokens after a password change.
    return _serializer().dumps({"uid": user.id, "pw": user.password_hash[-12:]})


def _user_from_request():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise APIError("Authentication required.", 401)
    token = header[7:].strip()
    try:
        payload = _serializer().loads(token, max_age=current_app.config["TOKEN_MAX_AGE"])
    except SignatureExpired:
        raise APIError("Your session has expired. Please sign in again.", 401) from None
    except BadSignature:
        raise APIError("Invalid authentication token.", 401) from None
    user = db.session.get(User, payload.get("uid"))
    if user is None or not user.is_active or user.password_hash[-12:] != payload.get("pw"):
        raise APIError("Invalid authentication token.", 401)
    return user


def current_user():
    return g.current_user


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        g.current_user = _user_from_request()
        return view(*args, **kwargs)

    return wrapper


def roles_required(*roles):
    """Allow only authenticated users whose role is in ``roles``."""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = _user_from_request()
            g.current_user = user
            if user.role not in roles:
                raise APIError("You do not have permission to perform this action.", 403)
            return view(*args, **kwargs)

        return wrapper

    return decorator
