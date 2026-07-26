"""Onboarding & profile routes — White Paper §4.2 (scherm 3-8) and §10.2.

Screens 1 (Welkom) and 2 (Account) are handled by the auth blueprint
(registration IS account creation). This blueprint covers scherm 3-8:
Basisgegevens, Trainingsdoel, Ervaring, Beschikbaarheid, Apparatuur &
locatie, and the final Samenvatting POST.
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from extensions import db
from helpers import error_response
from models import Equipment, UserEquipment

profile_bp = Blueprint("profile", __name__, url_prefix="/api")

VALID_GOALS = {"hypertrophy", "strength"}
VALID_EXPERIENCE = {"beginner", "intermediate", "advanced"}
VALID_SEX = {"man", "vrouw", "anders", "zeg_ik_liever_niet"}
VALID_LOCATION = {"gym", "home", "both"}
VALID_SESSION_MINUTES = {30, 45, 60, 75, 90}


def validate_onboarding(data: dict) -> dict:
    """Server-side validation mirroring onboarding scherm 3-7 (BR-10: server leads)."""
    fields = {}

    age = data.get("age")
    if not isinstance(age, int) or not (16 <= age <= 100):
        fields["age"] = "iDoFitness geeft trainingsadvies voor 16+ (max. 100)"

    height_cm = data.get("height_cm")
    if not isinstance(height_cm, int) or not (120 <= height_cm <= 230):
        fields["height_cm"] = "Lengte moet tussen 120 en 230 cm liggen"

    bodyweight_kg = data.get("bodyweight_kg")
    if not isinstance(bodyweight_kg, (int, float)) or not (30 <= bodyweight_kg <= 300):
        fields["bodyweight_kg"] = "Gewicht moet tussen 30 en 300 kg liggen"

    if data.get("sex") not in VALID_SEX:
        fields["sex"] = "Ongeldige selectie"

    if data.get("global_goal") not in VALID_GOALS:
        fields["global_goal"] = "Kies hypertrofie of kracht"

    if data.get("experience") not in VALID_EXPERIENCE:
        fields["experience"] = "Kies een ervaringsniveau"

    days = data.get("days_per_week")
    if not isinstance(days, int) or not (1 <= days <= 7):
        fields["days_per_week"] = "1-7 dagen"

    if data.get("session_minutes") not in VALID_SESSION_MINUTES:
        fields["session_minutes"] = "Ongeldige sessieduur"

    if data.get("training_location") not in VALID_LOCATION:
        fields["training_location"] = "Kies sportschool, thuis of beide"

    if data.get("training_location") in ("home", "both"):
        equipment = data.get("equipment")
        if not isinstance(equipment, list) or len(equipment) == 0:
            fields["equipment"] = "Kies minstens één apparatuur-optie"

    if not data.get("privacy_accepted"):
        fields["privacy_accepted"] = "Je moet akkoord gaan met het privacybeleid"

    return fields


@profile_bp.route("/onboarding", methods=["POST"])
@login_required
def submit_onboarding():
    data = request.get_json(silent=True) or {}

    field_errors = validate_onboarding(data)
    if field_errors:
        body, status = error_response("VALIDATION_ERROR", "Controleer de invoer", field_errors)
        return jsonify(body), status

    user = current_user
    user.display_name = (data.get("display_name") or "").strip() or None
    user.age = data["age"]
    user.height_cm = data["height_cm"]
    user.bodyweight_kg = data["bodyweight_kg"]
    user.sex = data["sex"]
    user.global_goal = data["global_goal"]
    user.experience = data["experience"]
    user.days_per_week = data["days_per_week"]
    user.session_minutes = data["session_minutes"]
    user.training_location = data["training_location"]
    user.onboarding_completed = True

    # Equipment (White Paper §4.2 scherm 7): gym = everything available;
    # home/both = exactly what the user selected.
    UserEquipment.query.filter_by(user_id=user.id).delete()
    if user.training_location == "gym":
        equipment_rows = Equipment.query.all()
    else:
        names = data.get("equipment", [])
        equipment_rows = Equipment.query.filter(Equipment.name.in_(names)).all()
    for eq in equipment_rows:
        db.session.add(UserEquipment(user_id=user.id, equipment_id=eq.id))

    db.session.commit()
    return jsonify({"user": user.to_public_dict()}), 200


@profile_bp.route("/profile", methods=["GET"])
@login_required
def get_profile():
    return jsonify({"user": current_user.to_public_dict()}), 200


@profile_bp.route("/profile", methods=["PATCH"])
@login_required
def patch_profile():
    """Partial update — e.g. changing global_goal later from Settings (§4.2 scherm 4 footnote)."""
    data = request.get_json(silent=True) or {}
    user = current_user

    if "global_goal" in data:
        if data["global_goal"] not in VALID_GOALS:
            body, status = error_response(
                "VALIDATION_ERROR", "Ongeldig doel", {"global_goal": "hypertrophy of strength"}
            )
            return jsonify(body), status
        user.global_goal = data["global_goal"]

    if "display_name" in data:
        user.display_name = (data["display_name"] or "").strip() or None

    if "unit_preference" in data and data["unit_preference"] in ("kg", "lbs"):
        user.unit_preference = data["unit_preference"]

    db.session.commit()
    return jsonify({"user": user.to_public_dict()}), 200


@profile_bp.route("/equipment", methods=["GET"])
@login_required
def list_equipment():
    """Backs onboarding scherm 7's equipment multi-select."""
    rows = Equipment.query.order_by(Equipment.name).all()
    return jsonify({"equipment": [{"id": e.id, "name": e.name} for e in rows]}), 200
