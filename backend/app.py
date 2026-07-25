"""iDoFitness backend — Flask app factory (White Paper §10.1).

Run locally:
    py -m flask --app app run --debug --port 5000
Migrations (Alembic via Flask-Migrate):
    py -m flask --app app db migrate -m "message"
    py -m flask --app app db upgrade
"""
import os

from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS

from extensions import db, migrate, login_manager, limiter

load_dotenv()


def create_app(config_overrides: dict | None = None) -> Flask:
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "postgresql://localhost/idofitness_dev"
    )
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key-change-in-prod")
    # Session cookie hardening (White Paper §10.3 / §17)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("FLASK_ENV") == "production"

    if config_overrides:
        app.config.update(config_overrides)

    # Frontend (Vercel) and backend (Render) live on different origins in prod;
    # locally the Vite proxy handles /api, so CORS mostly matters for prod (§10.3).
    CORS(
        app,
        supports_credentials=True,
        origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    )

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    limiter.init_app(app)

    import models  # noqa: F401  (register models with SQLAlchemy metadata)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(models.User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        from helpers import error_response
        from flask import jsonify
        body, status = error_response("UNAUTHENTICATED", "Log in om door te gaan", status=401)
        return jsonify(body), status

    # Blueprints, registered as they are built (§10.5 build order):
    # auth -> workouts -> exercises -> recommendations -> suggestion -> analytics
    from auth.routes import auth_bp
    app.register_blueprint(auth_bp)

    @app.route("/api/health")
    def health():
        return {"status": "ok", "message": "iDoFitness backend ready"}

    @app.route("/healthz")  # Render healthcheck (§10.4)
    def healthz():
        return {"status": "ok"}

    return app


if __name__ == "__main__":
    create_app().run(debug=True, port=5000)
