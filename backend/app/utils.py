"""Request validation, error and pagination helpers."""
import re
from datetime import date

from flask import jsonify, request

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[0-9+()\-\s]{6,20}$")


class APIError(Exception):
    def __init__(self, message, status=400, errors=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.errors = errors or {}

    def to_response(self):
        body = {"error": self.message}
        if self.errors:
            body["errors"] = self.errors
        return jsonify(body), self.status


def get_json():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise APIError("Request body must be a JSON object.", 400)
    return data


def require_fields(data, *fields):
    errors = {}
    for field in fields:
        value = data.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors[field] = "This field is required."
    if errors:
        raise APIError("Please fill in all required fields.", 422, errors)


def clean_str(value, field, max_len=255, required=False):
    if value is None:
        if required:
            raise APIError(f"{field} is required.", 422, {field: "This field is required."})
        return None
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    if required and not value:
        raise APIError(f"{field} is required.", 422, {field: "This field is required."})
    if len(value) > max_len:
        raise APIError(
            f"{field} is too long.", 422, {field: f"Must be at most {max_len} characters."}
        )
    return value or None


def parse_email(value, field="email"):
    value = clean_str(value, field, required=True).lower()
    if not EMAIL_RE.match(value):
        raise APIError("Invalid email address.", 422, {field: "Enter a valid email address."})
    return value


def parse_phone(value, field="phone"):
    value = clean_str(value, field, max_len=30)
    if value and not PHONE_RE.match(value):
        raise APIError("Invalid phone number.", 422, {field: "Enter a valid phone number."})
    return value


def parse_date(value, field, required=True):
    if value in (None, ""):
        if required:
            raise APIError(f"{field} is required.", 422, {field: "This field is required."})
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise APIError("Invalid date.", 422, {field: "Use the format YYYY-MM-DD."}) from None


def parse_amount(value, field, allow_zero=False, required=True):
    if value in (None, ""):
        if required:
            raise APIError(f"{field} is required.", 422, {field: "This field is required."})
        return None
    try:
        amount = round(float(value), 2)
    except (TypeError, ValueError):
        raise APIError("Invalid amount.", 422, {field: "Enter a valid number."}) from None
    if amount < 0 or (amount == 0 and not allow_zero) or amount > 10_000_000:
        raise APIError("Invalid amount.", 422, {field: "Enter a positive amount."})
    return amount


def parse_choice(value, field, choices, required=True):
    if value in (None, ""):
        if required:
            raise APIError(f"{field} is required.", 422, {field: "This field is required."})
        return None
    value = str(value).strip().lower()
    if value not in choices:
        raise APIError(
            f"Invalid {field}.", 422, {field: f"Must be one of: {', '.join(choices)}."}
        )
    return value


def parse_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def parse_password(value, field="password"):
    if not isinstance(value, str) or len(value) < 8:
        raise APIError(
            "Password is too short.", 422, {field: "Use at least 8 characters."}
        )
    if len(value) > 128:
        raise APIError("Password is too long.", 422, {field: "Use at most 128 characters."})
    return value


def get_or_404(model, object_id, label=None):
    from .extensions import db

    obj = db.session.get(model, object_id)
    if obj is None:
        raise APIError(f"{label or model.__name__} not found.", 404)
    return obj


def paginate(query, serializer):
    try:
        page = max(int(request.args.get("page", 1)), 1)
        per_page = min(max(int(request.args.get("per_page", 20)), 1), 100)
    except ValueError:
        raise APIError("page and per_page must be integers.", 400) from None
    total = query.order_by(None).count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": [serializer(item) for item in items],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max((total + per_page - 1) // per_page, 1),
    }
