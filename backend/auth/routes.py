"""Auth routes — White Paper §4.2 (scherm 2: Account) and §10.2/§10.3.

Session-based auth via Flask-Login, HttpOnly cookies (configured in app.py).
Passwords hashed with werkzeug PBKDF2-SHA256 (see models.User.set_password).
"""
import re

from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import IntegrityError

from extensions import db, limiter
from helpers import error_response
from models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]+$")


def validate_registration(data: dict) -> dict:
    """Returns a dict of field -> error message. Empty dict = valid.

    Mirrors the client-side validation on onboarding scherm 2; server-side
    is authoritative per BR-10 (client-side is UX only).
    """
    fields = {}

    username = (data.get("username") or "").strip()
    if not (3 <= len(username) <= 30) or not USERNAME_RE.match(username):
        fields["username"] = "3-30 tekens, alleen letters, cijfers en underscore"

    email = (data.get("email") or "").strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        fields["email"] = "Ongeldig e-mailadres"

    password = data.get("password") or ""
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if len(password) < 8 or not has_letter or not has_digit:
        fields["password"] = "Minimaal 8 tekens met een letter en een cijfer"

    if data.get("password_confirm") != password:
        fields["password_confirm"] = "Wachtwoorden komen niet overeen"

    return fields


@auth_bp.route("/check-username", methods=["GET"])
def check_username():
    u = (request.args.get("u") or "").strip()
    if not u:
        return jsonify({"available": False}), 200
    exists = User.query.filter_by(username=u).first() is not None
    return jsonify({"available": not exists}), 200


@auth_bp.route("/register", methods=["POST"])
@limiter.limit("5/minute")  # White Paper §10.4: auth endpoints 5/min/IP
def register():
    data = request.get_json(silent=True) or {}

    field_errors = validate_registration(data)
    if field_errors:
        body, status = error_response(
            "VALIDATION_ERROR", "Controleer de invoer", field_errors
        )
        return jsonify(body), status

    user = User(
        username=data["username"].strip(),
        email=data["email"].strip().lower(),
        global_goal="hypertrophy",  # placeholder until onboarding (§4.2 scherm 4) runs
    )
    user.set_password(data["password"])

    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        body, status = error_response(
            "DUPLICATE",
            "Gebruikersnaam of e-mailadres is al in gebruik",
            status=409,
        )
        return jsonify(body), status

    login_user(user)
    return jsonify({"user": user.to_public_dict()}), 201


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5/minute")
def login():
    data = request.get_json(silent=True) or {}
    identifier = (data.get("username") or data.get("email") or "").strip()
    password = data.get("password") or ""

    user = User.query.filter(
        (User.username == identifier) | (User.email == identifier.lower())
    ).first()

    # Generic error message — never reveal whether the username exists (§17)
    if user is None or not user.check_password(password):
        body, status = error_response(
            "INVALID_CREDENTIALS", "Combinatie onbekend", status=401
        )
        return jsonify(body), status

    login_user(user)
    return jsonify({"user": user.to_public_dict()}), 200


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return "", 204


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    """Not in the original endpoint table but needed by the frontend AuthContext
    to check "am I already logged in?" on page load without a full profile call."""
    return jsonify({"user": current_user.to_public_dict()}), 200
