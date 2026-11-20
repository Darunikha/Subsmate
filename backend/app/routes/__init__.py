from . import auth, customers, insights, payments, plans, renewals, subscriptions, users


def register_blueprints(app):
    for module in (auth, users, customers, plans, subscriptions, payments, renewals, insights):
        app.register_blueprint(module.bp)
