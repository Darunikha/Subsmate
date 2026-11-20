"""Application configuration.

All values can be overridden with environment variables so the same image
runs locally, in Docker Compose and in Kubernetes.
"""
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _bool(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "instance", "subsmate.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Auth tokens are signed with SECRET_KEY and expire after this many seconds.
    TOKEN_MAX_AGE = int(os.environ.get("TOKEN_MAX_AGE", 60 * 60 * 12))

    # A subscription is "Expiring Soon" when it expires within this many days.
    EXPIRING_SOON_DAYS = int(os.environ.get("EXPIRING_SOON_DAYS", 7))
    # The renewals module lists subscriptions expiring within this many days.
    RENEWAL_WINDOW_DAYS = int(os.environ.get("RENEWAL_WINDOW_DAYS", 30))

    PASSWORD_HASH_METHOD = os.environ.get("PASSWORD_HASH_METHOD", "scrypt")

    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
    SEED_DEMO_DATA = _bool("SEED_DEMO_DATA", True)
    JSON_SORT_KEYS = False


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SEED_DEMO_DATA = False
    SECRET_KEY = "test-secret"
    PASSWORD_HASH_METHOD = "pbkdf2:sha256:1000"  # fast hashing for tests only
