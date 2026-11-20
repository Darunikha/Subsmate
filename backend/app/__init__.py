import logging
import os

from flask import Flask, jsonify
from flask_cors import CORS
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from .config import Config
from .extensions import db
from .utils import APIError


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object or Config)
    app.json.sort_keys = False

    _ensure_sqlite_dir(app.config["SQLALCHEMY_DATABASE_URI"])
    db.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    from . import models  # noqa: F401  (register models)
    from .metrics import init_metrics
    from .routes import register_blueprints

    register_blueprints(app)
    _register_error_handlers(app)
    init_metrics(app)

    @app.get("/api/health")
    def health():
        db.session.execute(db.text("SELECT 1"))
        return jsonify({"status": "ok"})

    with app.app_context():
        db.create_all()
        if app.config.get("SEED_DEMO_DATA"):
            from .seed import seed_if_empty

            seed_if_empty()

    @app.cli.command("seed")
    def seed_command():
        """Load demo data into an empty database."""
        from .seed import seed_if_empty

        print("Seeded demo data." if seed_if_empty() else "Database already has data; skipped.")

    return app


def _ensure_sqlite_dir(uri):
    prefix = "sqlite:///"
    if uri.startswith(prefix) and len(uri) > len(prefix):
        directory = os.path.dirname(os.path.abspath(uri[len(prefix):]))
        os.makedirs(directory, exist_ok=True)


def _register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(error):
        db.session.rollback()
        return error.to_response()

    @app.errorhandler(IntegrityError)
    def handle_integrity_error(_error):
        db.session.rollback()
        return jsonify({"error": "This change conflicts with existing records."}), 409

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        return jsonify({"error": error.description or error.name}), error.code

    @app.errorhandler(Exception)
    def handle_unexpected(error):
        db.session.rollback()
        logging.getLogger(__name__).exception("Unhandled error: %s", error)
        return jsonify({"error": "An unexpected error occurred."}), 500
