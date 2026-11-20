from . import auth, customers, insights, payments, renewals, subscriptions, users


def register_blueprints(app):
    for module in (auth, users, customers, subscriptions, payments, renewals, insights):
        app.register_blueprint(module.bp)
