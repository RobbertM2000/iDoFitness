"""
api/recommendations.py
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from engine.predictor import (
    SessionLog, SetLog, UserProfile, ExerciseProfile, get_recommendation,
)
from helpers import error_response
from models import db, Workout, WorkoutExercise, Set, Exercise

bp = Blueprint('recommendations', __name__, url_prefix='/api')


def _sessions_for_exercise(user_id: int, exercise_id: int) -> list[SessionLog]:
    """Query database voor alle sessions van een user + exercise."""
    rows = (
        db.session.query(Workout, WorkoutExercise, Set)
        .join(WorkoutExercise, Workout.id == WorkoutExercise.workout_id)
        .join(Set, Set.workout_exercise_id == WorkoutExercise.id)
        .filter(
            Workout.user_id == user_id,
            WorkoutExercise.exercise_id == exercise_id,
            Workout.deleted_at.is_(None),
        )
        .order_by(Workout.performed_at)
        .all()
    )

    workouts_dict = {}
    for workout, we, set_row in rows:
        date_key = workout.performed_at.date()
        if date_key not in workouts_dict:
            workouts_dict[date_key] = SessionLog(
                performed_at=date_key,
                sets=[]
            )
        workouts_dict[date_key].sets.append(
            SetLog(
                # Numeric DB columns come back as Decimal — SetLog is typed
                # `float`, and predictor.py's arithmetic (round_to_plate,
                # weight * pct, etc.) raises TypeError mixing Decimal with
                # the float literals it uses, so this cast is required, not
                # cosmetic (matches the same float() cast api/workouts.py
                # already does at its own DB boundary).
                weight_kg=float(set_row.weight_kg),
                reps=set_row.reps,
                rpe=float(set_row.rpe) if set_row.rpe is not None else None,
                is_warmup=set_row.is_warmup or False,
            )
        )

    return list(workouts_dict.values())


@bp.route('/recommendation', methods=['GET'])
@login_required
def get_exercise_recommendation():
    """GET /api/recommendation?exercise_id=1"""
    exercise_id = request.args.get('exercise_id', type=int)
    if not exercise_id:
        body, status = error_response(
            "VALIDATION_ERROR", "exercise_id is verplicht", {"exercise_id": "Verplicht"}, status=400
        )
        return jsonify(body), status

    user = current_user
    exercise = db.session.get(Exercise, exercise_id)
    if not exercise:
        body, status = error_response("NOT_FOUND", "Oefening niet gevonden", status=404)
        return jsonify(body), status

    profile = UserProfile(
        global_goal=getattr(user, 'global_goal', 'hypertrophy') or 'hypertrophy',
        experience=getattr(user, 'experience', 'intermediate') or 'intermediate',
        sleep_score=getattr(user, 'sleep_score', None),
        stress_score=getattr(user, 'stress_score', None),
    )

    exercise_profile = ExerciseProfile(
        is_compound=getattr(exercise, 'is_compound', True) or True,
        is_upper_body=getattr(exercise, 'is_upper_body', True) or True,
        is_barbell=True,
        linear_target_reps=5,
    )

    history = _sessions_for_exercise(user.id, exercise_id)
    advice = get_recommendation(history, profile, exercise_profile)

    return jsonify({
        'exercise_id': exercise_id,
        'exercise_name': exercise.name,
        'weight_kg': advice.weight_kg,
        'reps_min': advice.reps_min,
        'reps_max': advice.reps_max,
        'rpe_target': advice.rpe_target_display(),
        'reason': advice.reason,
        'provisional': advice.provisional,
        'cold_start': advice.cold_start,
        'deload': advice.deload,
    })