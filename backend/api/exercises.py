"""Exercise library routes — White Paper §10.2, §13."""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from extensions import db
from helpers import error_response
from models import (
    Exercise, MuscleGroup, Equipment, UserAvoidedExercise, ExerciseAlternative,
    Workout, WorkoutExercise,
)

exercises_bp = Blueprint("exercises", __name__, url_prefix="/api/exercises")


def exercise_to_dict(ex: Exercise) -> dict:
    return {
        "id": ex.id,
        "name": ex.name,
        "muscle": ex.primary_muscle.name if ex.primary_muscle else None,
        "is_compound": ex.is_compound,
        "equipment_id": ex.equipment_id,
        "difficulty": ex.difficulty,
        "description": ex.description,
        "technique_tips": (ex.technique_tips or "").split("\n") if ex.technique_tips else [],
        "common_mistakes": (ex.common_mistakes or "").split("\n") if ex.common_mistakes else [],
        "video_url": ex.video_url,
        "is_main_lift": ex.is_main_lift,
        "is_custom": ex.created_by is not None,
    }


@exercises_bp.route("", methods=["GET"])
@login_required
def list_exercises():
    """Library (seed, created_by IS NULL) + the current user's own custom exercises,
    filterable by muscle group and free-text query (White Paper §13)."""
    muscle = request.args.get("muscle")
    q = request.args.get("q", "").strip()

    query = Exercise.query.filter(
        db.or_(Exercise.created_by.is_(None), Exercise.created_by == current_user.id)
    ).filter(Exercise.is_archived.is_(False))

    if muscle:
        mg = MuscleGroup.query.filter_by(name=muscle).first()
        if mg:
            query = query.filter(Exercise.primary_muscle_id == mg.id)
        else:
            return jsonify({"exercises": []}), 200

    if q:
        query = query.filter(Exercise.name.ilike(f"%{q}%"))

    exercises = query.order_by(Exercise.name).all()

    avoided_ids = {
        a.exercise_id for a in UserAvoidedExercise.query.filter_by(user_id=current_user.id).all()
    }

    return jsonify({
        "exercises": [
            {**exercise_to_dict(ex), "is_avoided": ex.id in avoided_ids} for ex in exercises
        ]
    }), 200


@exercises_bp.route("/search", methods=["GET"])
@login_required
def search_exercises():
    """Entry point for the Exercise Detail screen (White Paper §14): free-text
    search that surfaces exercises the user has actually logged before
    everything else, since "find my bench press history" is the common case
    — not "browse the whole library" (that's list_exercises above)."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"exercises": []}), 200

    candidates = (
        Exercise.query.filter(
            db.or_(Exercise.created_by.is_(None), Exercise.created_by == current_user.id)
        )
        .filter(Exercise.is_archived.is_(False))
        .filter(Exercise.name.ilike(f"%{q}%"))
        .order_by(Exercise.name)
        .limit(50)
        .all()
    )

    logged_ids = {
        row[0] for row in (
            db.session.query(WorkoutExercise.exercise_id)
            .join(Workout, Workout.id == WorkoutExercise.workout_id)
            .filter(Workout.user_id == current_user.id, Workout.deleted_at.is_(None))
            .distinct()
            .all()
        )
    }

    ordered = sorted(candidates, key=lambda ex: (ex.id not in logged_ids, ex.name))[:20]

    return jsonify({
        "exercises": [
            {**exercise_to_dict(ex), "logged": ex.id in logged_ids} for ex in ordered
        ]
    }), 200


@exercises_bp.route("/<int:exercise_id>", methods=["GET"])
@login_required
def get_exercise(exercise_id):
    ex = db.session.get(Exercise, exercise_id)
    if not ex or ex.is_archived:
        return jsonify(error_response("NOT_FOUND", "Oefening niet gevonden", status=404)[0]), 404

    alt_ids = [
        a.alternative_id for a in ExerciseAlternative.query.filter_by(exercise_id=ex.id).all()
    ]
    alternatives = Exercise.query.filter(Exercise.id.in_(alt_ids)).all() if alt_ids else []

    return jsonify({
        **exercise_to_dict(ex),
        "alternatives": [exercise_to_dict(a) for a in alternatives],
    }), 200


@exercises_bp.route("", methods=["POST"])
@login_required
def create_custom_exercise():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    muscle_name = data.get("muscle")
    equipment_name = data.get("equipment")

    fields = {}
    if not name:
        fields["name"] = "Naam is verplicht"
    mg = MuscleGroup.query.filter_by(name=muscle_name).first()
    if not mg:
        fields["muscle"] = "Onbekende spiergroep"
    eq = Equipment.query.filter_by(name=equipment_name).first()
    if not eq:
        fields["equipment"] = "Onbekende apparatuur"
    if fields:
        body, status = error_response("VALIDATION_ERROR", "Controleer de invoer", fields)
        return jsonify(body), status

    duplicate = Exercise.query.filter_by(name=name, created_by=current_user.id).first()
    if duplicate:
        body, status = error_response(
            "DUPLICATE", "Je hebt al een eigen oefening met deze naam", status=409
        )
        return jsonify(body), status

    ex = Exercise(
        name=name,
        primary_muscle_id=mg.id,
        is_compound=bool(data.get("is_compound", False)),
        equipment_id=eq.id,
        difficulty=data.get("difficulty"),
        description=data.get("description"),
        created_by=current_user.id,
    )
    db.session.add(ex)
    db.session.commit()
    return jsonify(exercise_to_dict(ex)), 201


@exercises_bp.route("/avoided", methods=["GET"])
@login_required
def list_avoided_exercises():
    """White Paper §4.3 — Settings' "Blessures & te vermijden oefeningen" list."""
    rows = (
        db.session.query(UserAvoidedExercise, Exercise)
        .join(Exercise, Exercise.id == UserAvoidedExercise.exercise_id)
        .filter(UserAvoidedExercise.user_id == current_user.id)
        .order_by(Exercise.name)
        .all()
    )
    return jsonify({
        "avoided_exercises": [
            {
                "exercise_id": ex.id,
                "name": ex.name,
                "muscle": ex.primary_muscle.name if ex.primary_muscle else None,
                "reason": avoided.reason,
            }
            for avoided, ex in rows
        ]
    }), 200


@exercises_bp.route("/<int:exercise_id>/avoid", methods=["POST"])
@login_required
def avoid_exercise(exercise_id):
    """White Paper §4.3 — blessure/vermijdlijst, used by the WOD generator later."""
    ex = db.session.get(Exercise, exercise_id)
    if not ex:
        return jsonify(error_response("NOT_FOUND", "Oefening niet gevonden", status=404)[0]), 404

    data = request.get_json(silent=True) or {}
    existing = UserAvoidedExercise.query.filter_by(
        user_id=current_user.id, exercise_id=exercise_id
    ).first()
    if not existing:
        db.session.add(UserAvoidedExercise(
            user_id=current_user.id, exercise_id=exercise_id,
            reason=(data.get("reason") or "")[:120],
        ))
        db.session.commit()
    return jsonify({"avoided": True}), 200


@exercises_bp.route("/<int:exercise_id>/avoid", methods=["DELETE"])
@login_required
def unavoid_exercise(exercise_id):
    UserAvoidedExercise.query.filter_by(
        user_id=current_user.id, exercise_id=exercise_id
    ).delete()
    db.session.commit()
    return "", 204
