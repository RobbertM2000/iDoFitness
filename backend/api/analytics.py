"""
api/analytics.py
------------------
GET /api/analytics/dashboard   — goal-specific dashboard payload + warnings
GET /api/analytics/volume      — weekly tonnage + muscle group breakdown
GET /api/analytics/progression — e1RM series + trend + 2-week forecast
POST /api/warnings/<id>/dismiss

White Paper §12.2 (dashboard), §14 (warnings), BR-09 (max 3 warnings,
priority order, 7-day dismiss suppression).
"""
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required, current_user

from extensions import db
from helpers import error_response
from engine.predictor import SessionLog, regression_slope_over_days
from engine.warning_detector import detect_warnings
from api.recommendations import _sessions_for_exercise
from models import (
    Exercise, MuscleGroup, Workout, WorkoutExercise, Set,
    E1rmHistory, PersonalRecord, Warning,
)

bp = Blueprint('analytics', __name__, url_prefix='/api')

DISMISS_SUPPRESS_DAYS = 7          # BR-09
MAX_WARNINGS = 3                   # BR-09
REP_RANGE_WINDOW_DAYS = 28
MUSCLE_VOLUME_WINDOW_DAYS = 7
RPE_DISTRIBUTION_WINDOW_DAYS = 28
STREAK_LOOKBACK_DAYS = 60          # cap how far back we bother walking


def _today():
    return date.today()


# ---------------------------------------------------------------------------
# Shared data access — every helper here excludes soft-deleted workouts/sets
# and warmups (BR-08), matching the convention already used across
# api/workouts.py and api/recommendations.py.
# ---------------------------------------------------------------------------

def _trained_exercises(user_id: int, since: date | None = None) -> list[tuple[int, str]]:
    """Distinct (exercise_id, name) the user has real working-set history for."""
    query = (
        db.session.query(Exercise.id, Exercise.name)
        .join(WorkoutExercise, WorkoutExercise.exercise_id == Exercise.id)
        .join(Workout, Workout.id == WorkoutExercise.workout_id)
        .join(Set, Set.workout_exercise_id == WorkoutExercise.id)
        .filter(
            Workout.user_id == user_id,
            Workout.deleted_at.is_(None),
            Set.is_warmup.is_(False),
        )
    )
    if since is not None:
        query = query.filter(Workout.performed_at >= since)
    return query.distinct().all()


def _exercise_histories(user_id: int, since: date | None = None) -> dict[int, tuple[str, list[SessionLog]]]:
    """exercise_id -> (name, sessions) for every exercise with real history.
    Reuses _sessions_for_exercise (already float-casts Decimal columns —
    see the fix in api/recommendations.py) rather than re-querying."""
    histories = {}
    for exercise_id, name in _trained_exercises(user_id, since):
        sessions = _sessions_for_exercise(user_id, exercise_id)
        if since is not None:
            sessions = [s for s in sessions if s.performed_at >= since]
        if sessions:
            histories[exercise_id] = (name, sessions)
    return histories


def _muscle_group_set_counts(user_id: int, since: date) -> dict[str, int]:
    rows = (
        db.session.query(MuscleGroup.name, db.func.count(Set.id))
        .select_from(Set)
        .join(WorkoutExercise, Set.workout_exercise_id == WorkoutExercise.id)
        .join(Workout, WorkoutExercise.workout_id == Workout.id)
        .join(Exercise, WorkoutExercise.exercise_id == Exercise.id)
        .join(MuscleGroup, Exercise.primary_muscle_id == MuscleGroup.id)
        .filter(
            Workout.user_id == user_id,
            Workout.deleted_at.is_(None),
            Set.is_warmup.is_(False),
            Workout.performed_at >= since,
        )
        .group_by(MuscleGroup.name)
        .all()
    )
    return {name: count for name, count in rows}


def _muscle_group_volume_kg(user_id: int, since: date) -> dict[str, float]:
    rows = (
        db.session.query(MuscleGroup.name, Set.weight_kg, Set.reps)
        .select_from(Set)
        .join(WorkoutExercise, Set.workout_exercise_id == WorkoutExercise.id)
        .join(Workout, WorkoutExercise.workout_id == Workout.id)
        .join(Exercise, WorkoutExercise.exercise_id == Exercise.id)
        .join(MuscleGroup, Exercise.primary_muscle_id == MuscleGroup.id)
        .filter(
            Workout.user_id == user_id,
            Workout.deleted_at.is_(None),
            Set.is_warmup.is_(False),
            Workout.performed_at >= since,
        )
        .all()
    )
    volume: dict[str, float] = {}
    for name, weight_kg, reps in rows:
        volume[name] = volume.get(name, 0.0) + float(weight_kg) * reps
    return {k: round(v, 1) for k, v in volume.items()}


def _rep_counts(user_id: int, since: date) -> list[int]:
    rows = (
        db.session.query(Set.reps)
        .select_from(Set)
        .join(WorkoutExercise, Set.workout_exercise_id == WorkoutExercise.id)
        .join(Workout, WorkoutExercise.workout_id == Workout.id)
        .filter(
            Workout.user_id == user_id,
            Workout.deleted_at.is_(None),
            Set.is_warmup.is_(False),
            Workout.performed_at >= since,
        )
        .all()
    )
    return [r[0] for r in rows]


def _rpe_counts(user_id: int, since: date) -> dict[str, int]:
    """Bucketed to the nearest whole RPE 6-10 (half-point RPEs like 7.5
    fold into the nearer bucket) — matches the bar chart's 5 fixed bars."""
    rows = (
        db.session.query(Set.rpe)
        .select_from(Set)
        .join(WorkoutExercise, Set.workout_exercise_id == WorkoutExercise.id)
        .join(Workout, WorkoutExercise.workout_id == Workout.id)
        .filter(
            Workout.user_id == user_id,
            Workout.deleted_at.is_(None),
            Set.is_warmup.is_(False),
            Set.rpe.isnot(None),
            Workout.performed_at >= since,
        )
        .all()
    )
    buckets = {"6": 0, "7": 0, "8": 0, "9": 0, "10": 0}
    for (rpe,) in rows:
        bucket = min(10, max(6, round(float(rpe))))
        buckets[str(bucket)] += 1
    return buckets


def _weekly_tonnage(user_id: int, weeks: int) -> list[dict]:
    """Oldest -> newest, one entry per week, week 0 = the 7 days ending today."""
    today = _today()
    out = []
    for i in range(weeks - 1, -1, -1):
        week_end = today - timedelta(days=7 * i)
        week_start = week_end - timedelta(days=6)
        rows = (
            db.session.query(Set.weight_kg, Set.reps)
            .select_from(Set)
            .join(WorkoutExercise, Set.workout_exercise_id == WorkoutExercise.id)
            .join(Workout, WorkoutExercise.workout_id == Workout.id)
            .filter(
                Workout.user_id == user_id,
                Workout.deleted_at.is_(None),
                Set.is_warmup.is_(False),
                Workout.performed_at >= week_start,
                Workout.performed_at < week_end + timedelta(days=1),
            )
            .all()
        )
        tonnage = round(sum(float(w) * r for w, r in rows), 1)
        out.append({"week_start": week_start.isoformat(), "tonnage_kg": tonnage})
    return out


def _streak_days(user_id: int) -> int:
    since = _today() - timedelta(days=STREAK_LOOKBACK_DAYS)
    rows = (
        db.session.query(Workout.performed_at)
        .filter(
            Workout.user_id == user_id,
            Workout.deleted_at.is_(None),
            Workout.performed_at >= since,
        )
        .all()
    )
    trained_dates = {r[0].date() for r in rows}
    if not trained_dates:
        return 0
    today = _today()
    cursor = today if today in trained_dates else today - timedelta(days=1)
    if cursor not in trained_dates:
        return 0
    streak = 0
    while cursor in trained_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _last_workout_date(user_id: int) -> date | None:
    row = (
        Workout.query.filter_by(user_id=user_id)
        .filter(Workout.deleted_at.is_(None))
        .order_by(Workout.performed_at.desc())
        .first()
    )
    return row.performed_at.date() if row else None


def _recent_workouts(user_id: int, limit: int = 3) -> list[dict]:
    workouts = (
        Workout.query.filter_by(user_id=user_id)
        .filter(Workout.deleted_at.is_(None))
        .order_by(Workout.performed_at.desc())
        .limit(limit)
        .all()
    )
    out = []
    for w in workouts:
        set_ids = [s.id for we in w.exercises for s in we.sets if not s.is_warmup]
        tonnage = round(sum(float(s.weight_kg) * s.reps for we in w.exercises for s in we.sets if not s.is_warmup), 1)
        has_pr = bool(set_ids) and PersonalRecord.query.filter(
            PersonalRecord.user_id == user_id, PersonalRecord.set_id.in_(set_ids)
        ).first() is not None
        out.append({
            "id": w.id,
            "date": w.performed_at.date().isoformat(),
            "title": w.title,
            "tonnage_kg": tonnage,
            "exercise_count": len(w.exercises),
            "has_pr": has_pr,
        })
    return out


def _rep_range_distribution(rep_counts: list[int]) -> dict | None:
    if not rep_counts:
        return None
    buckets = {"6-10": 0, "10-15": 0, "15+": 0}
    for r in rep_counts:
        if r <= 10:
            buckets["6-10"] += 1
        elif r <= 15:
            buckets["10-15"] += 1
        else:
            buckets["15+"] += 1
    total = len(rep_counts)
    return {k: round(v / total * 100, 1) for k, v in buckets.items()}


def _main_lift_progressions(user_id: int) -> list[dict]:
    main_lifts = Exercise.query.filter_by(is_main_lift=True).all()
    today = _today()
    out = []
    for ex in main_lifts:
        history = (
            E1rmHistory.query.filter_by(user_id=user_id, exercise_id=ex.id)
            .order_by(E1rmHistory.date)
            .all()
        )
        if not history:
            out.append({
                "exercise_id": ex.id, "exercise": ex.name,
                "current": None, "trend_kg_per_week": None, "forecast_2weeks": None,
                "last_trained": None, "series": [],
            })
            continue
        series = [{"date": h.date.isoformat(), "e1rm_kg": float(h.e1rm_kg)} for h in history]
        dated = [((h.date - today).days, float(h.e1rm_kg)) for h in history]
        slope_per_day = regression_slope_over_days(dated)
        current = series[-1]["e1rm_kg"]
        trend = round(slope_per_day * 7, 2) if slope_per_day is not None else None
        forecast = round(current + slope_per_day * 14, 1) if slope_per_day is not None else None
        out.append({
            "exercise_id": ex.id, "exercise": ex.name,
            "current": current, "trend_kg_per_week": trend, "forecast_2weeks": forecast,
            "last_trained": history[-1].date.isoformat(), "series": series,
        })
    out.sort(key=lambda e: e["last_trained"] or "", reverse=True)
    return out


# ---------------------------------------------------------------------------
# Warnings — persistence + BR-09's 7-day dismiss suppression
# ---------------------------------------------------------------------------

def _get_active_warnings(user) -> list[dict]:
    since_muscle = _today() - timedelta(days=14)
    since_reps = _today() - timedelta(days=REP_RANGE_WINDOW_DAYS)

    candidates = detect_warnings(
        goal=user.global_goal or "hypertrophy",
        exercise_histories=_exercise_histories(user.id, since=_today() - timedelta(days=120)),
        muscle_group_sets=_muscle_group_set_counts(user.id, since_muscle),
        rep_counts=_rep_counts(user.id, since_reps),
        last_workout_date=_last_workout_date(user.id),
        days_per_week=user.days_per_week,
    )

    now = datetime.now(timezone.utc)
    suppress_after = now - timedelta(days=DISMISS_SUPPRESS_DAYS)
    result_rows = []
    for candidate in candidates:
        existing = (
            Warning.query.filter_by(user_id=user.id, warning_type=candidate.warning_type)
            .order_by(Warning.created_at.desc())
            .first()
        )
        # SQLite (tests) round-trips DateTime(timezone=True) as naive,
        # Postgres (prod) keeps it aware — normalize before comparing so
        # this doesn't crash under either backend.
        dismissed_at = existing.dismissed_at if existing else None
        if dismissed_at is not None and dismissed_at.tzinfo is None:
            dismissed_at = dismissed_at.replace(tzinfo=timezone.utc)
        if dismissed_at is not None and dismissed_at > suppress_after:
            continue  # still within the 7-day "don't nag me again" window
        if existing and existing.dismissed_at is None:
            existing.message = candidate.message
            existing.action_hint = candidate.action_hint
            existing.severity = candidate.severity
            row = existing
        else:
            row = Warning(
                user_id=user.id, warning_type=candidate.warning_type,
                message=candidate.message, action_hint=candidate.action_hint,
                severity=candidate.severity,
            )
            db.session.add(row)
        result_rows.append(row)

    db.session.commit()
    result_rows = result_rows[:MAX_WARNINGS]
    return [
        {
            "id": w.id, "type": w.warning_type, "message": w.message,
            "action_hint": w.action_hint, "severity": w.severity,
        }
        for w in result_rows
    ]


@bp.route('/warnings/<int:warning_id>/dismiss', methods=['POST'])
@login_required
def dismiss_warning(warning_id):
    w = Warning.query.filter_by(id=warning_id, user_id=current_user.id).first()
    if not w:
        body, status = error_response("NOT_FOUND", "Waarschuwing niet gevonden", status=404)
        return jsonify(body), status
    w.dismissed_at = datetime.now(timezone.utc)
    db.session.commit()
    return "", 204


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@bp.route('/analytics/dashboard', methods=['GET'])
@login_required
def get_dashboard():
    user = current_user
    try:
        goal = user.global_goal or "hypertrophy"
        today = _today()

        weekly = _weekly_tonnage(user.id, weeks=8)
        week_volume_kg = weekly[-1]["tonnage_kg"]
        prev_week_kg = weekly[-2]["tonnage_kg"] if len(weekly) > 1 else 0
        delta_pct = (
            round((week_volume_kg - prev_week_kg) / prev_week_kg * 100, 1)
            if prev_week_kg > 0 else None
        )

        payload = {
            "goal": goal,
            "warnings": _get_active_warnings(user),
            "week_volume_kg": week_volume_kg,
            "week_volume_delta_pct": delta_pct,
            "volume_sparkline": [w["tonnage_kg"] for w in weekly],
            "recent_workouts": _recent_workouts(user.id, limit=3),
            "streak_days": _streak_days(user.id),
        }

        if goal == "strength":
            main_lifts = _main_lift_progressions(user.id)
            payload["main_lift_e1rms"] = main_lifts
            payload["rpe_distribution"] = _rpe_counts(user.id, today - timedelta(days=RPE_DISTRIBUTION_WINDOW_DAYS))
        else:
            rep_counts = _rep_counts(user.id, today - timedelta(days=REP_RANGE_WINDOW_DAYS))
            payload["rep_range_distribution"] = _rep_range_distribution(rep_counts)
            payload["muscle_group_volume"] = _muscle_group_volume_kg(
                user.id, today - timedelta(days=MUSCLE_VOLUME_WINDOW_DAYS)
            )

        return jsonify(payload), 200
    except Exception:
        current_app.logger.exception("Failed to build dashboard for user_id=%s", user.id)
        body, status = error_response(
            "DASHBOARD_FAILED", "Dashboard kon niet geladen worden. Probeer het opnieuw.", status=500
        )
        return jsonify(body), status


@bp.route('/analytics/volume', methods=['GET'])
@login_required
def get_volume():
    weeks = request.args.get('weeks', 8, type=int)
    weeks = max(1, min(weeks, 52))
    since = _today() - timedelta(weeks=weeks)
    return jsonify({
        "weeks": weeks,
        "weekly_tonnage": _weekly_tonnage(current_user.id, weeks=weeks),
        "muscle_group_volume": _muscle_group_volume_kg(current_user.id, since),
    }), 200


@bp.route('/analytics/progression', methods=['GET'])
@login_required
def get_progression():
    exercise_id = request.args.get('exercise_id', type=int)
    if not exercise_id:
        body, status = error_response(
            "VALIDATION_ERROR", "exercise_id is verplicht", {"exercise_id": "Verplicht"}, status=400
        )
        return jsonify(body), status

    exercise = db.session.get(Exercise, exercise_id)
    if not exercise:
        body, status = error_response("NOT_FOUND", "Oefening niet gevonden", status=404)
        return jsonify(body), status

    history = (
        E1rmHistory.query.filter_by(user_id=current_user.id, exercise_id=exercise_id)
        .order_by(E1rmHistory.date)
        .all()
    )
    if not history:
        return jsonify({
            "exercise_id": exercise_id, "exercise_name": exercise.name,
            "series": [], "trend_kg_per_week": None, "forecast_2weeks_kg": None,
            "insufficient_data": True,
        }), 200

    today = _today()
    series = [{"date": h.date.isoformat(), "e1rm_kg": float(h.e1rm_kg)} for h in history]
    dated = [((h.date - today).days, float(h.e1rm_kg)) for h in history]
    slope_per_day = regression_slope_over_days(dated)
    current = series[-1]["e1rm_kg"]

    return jsonify({
        "exercise_id": exercise_id,
        "exercise_name": exercise.name,
        "series": series,
        "trend_kg_per_week": round(slope_per_day * 7, 2) if slope_per_day is not None else None,
        "forecast_2weeks_kg": round(current + slope_per_day * 14, 1) if slope_per_day is not None else None,
        "insufficient_data": slope_per_day is None,
    }), 200
