"""
api/suggestions.py
-------------------
GET /api/workout-suggestion — genereert een complete workout (WOD),
White Paper §5.5-5.6, §6.1.
"""

from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required, current_user

from engine.predictor import UserProfile
from engine.wod_generator import ExerciseInfo, generate_wod
from api.recommendations import _sessions_for_exercise
from helpers import error_response
from models import db, Exercise, MuscleGroup, WorkoutExercise, Workout, UserAvoidedExercise, UserEquipment

bp = Blueprint('suggestions', __name__, url_prefix='/api')


def _build_candidates(user_id: int) -> list[ExerciseInfo]:
    """
    Bouwt de kandidaatlijst: alle oefeningen die matchen op de
    apparatuur van de gebruiker, minus de vermijdlijst (§5.5 punt 3).
    """
    avoided_ids = {
        row.exercise_id for row in
        UserAvoidedExercise.query.filter_by(user_id=user_id).all()
    }

    user_equipment_ids = {
        row.equipment_id for row in
        UserEquipment.query.filter_by(user_id=user_id).all()
    }

    query = (
        db.session.query(Exercise, MuscleGroup.name)
        .join(MuscleGroup, Exercise.primary_muscle_id == MuscleGroup.id)
        .filter(Exercise.is_archived.is_(False))
    )

    candidates = []
    for exercise, muscle_group_name in query.all():
        if exercise.id in avoided_ids:
            continue
        # Sportschool = alles beschikbaar aangenomen (§4.2 scherm 7);
        # als je thuis-locatie opslaat, filter hier ook op equipment_id.
        if user_equipment_ids and exercise.equipment_id not in user_equipment_ids:
            continue
        candidates.append(ExerciseInfo(
            exercise_id=exercise.id,
            name=exercise.name,
            muscle_group=muscle_group_name,
            is_compound=exercise.is_compound,
            is_main_lift=exercise.is_main_lift,
        ))
    return candidates


@bp.route('/workout-suggestion', methods=['GET'])
@login_required
def get_workout_suggestion():
    """GET /api/workout-suggestion

    Wrapped in a catch-all: an uncaught exception here would otherwise
    fall through to Flask's default HTML error page, which the frontend
    can't parse as JSON — it'd surface as a generic, undebuggable
    "Er ging iets mis" with no indication anything actually broke
    server-side. Logging the real traceback here keeps this endpoint's
    failures diagnosable (backend log) while the client still gets the
    app's normal JSON error envelope.
    """
    user = current_user

    try:
        profile = UserProfile(
            global_goal=user.global_goal or 'hypertrophy',
            experience=user.experience or 'intermediate',
            sleep_score=user.sleep_score,
            stress_score=user.stress_score,
        )

        candidates = _build_candidates(user.id)
        histories = {
            ex.exercise_id: _sessions_for_exercise(user.id, ex.exercise_id)
            for ex in candidates
        }

        session_minutes = user.session_minutes or 60

        wod = generate_wod(candidates, histories, profile, session_minutes)
    except Exception:
        current_app.logger.exception(
            "Failed to generate workout suggestion for user_id=%s", user.id
        )
        body, status = error_response(
            "SUGGESTION_FAILED",
            "Kon geen workout genereren. Probeer het later opnieuw.",
            status=500,
        )
        return jsonify(body), status

    return jsonify({
        # Not a persisted row — WODs are generated on the fly — so this is a
        # date+goal composite the frontend can round-trip back as
        # Workout.suggested_from_wod_id when the user logs this WOD (§6.1).
        'wod_id': f"{wod.date.isoformat()}:{wod.goal}",
        'date': wod.date.isoformat(),
        'goal': wod.goal,
        'title': wod.title,
        'estimated_duration_min': wod.estimated_duration_min,
        'cold_start': wod.cold_start,
        'warmup': {
            'general': wod.warmup.general,
            'ramp_sets': wod.warmup.ramp_sets,
            'note': wod.warmup.note,
        },
        'exercises': [
            {
                'order': e.order,
                'exercise_id': e.exercise_id,
                'name': e.name,
                'is_compound': e.is_compound,
                'sets': e.sets,
                'reps_min': e.reps_min,
                'reps_max': e.reps_max,
                'rpe_target_min': e.rpe_target_min,
                'rpe_target_max': e.rpe_target_max,
                'rest_sec': e.rest_sec,
                'weight_kg': e.weight_kg,
                'reason': e.reason,
                'provisional': e.provisional,
                'cold_start': e.cold_start,
            }
            for e in wod.exercises
        ],
        'cooldown': wod.cooldown,
    })