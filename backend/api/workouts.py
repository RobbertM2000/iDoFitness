"""Workout logging routes — White Paper §7.2, §9, §10.2.

Save is one atomic transaction (BR: workout-save is één DB-transactie).
Idempotency via client_uuid (edge case #10: double-submit/retry never
creates a duplicate workout).
"""
import re
from datetime import datetime, timezone

from flask import Blueprint, current_app, request, jsonify
from flask_login import login_required, current_user

from extensions import db
from helpers import error_response
from models import Workout, WorkoutExercise, Set, Exercise, E1rmHistory, PersonalRecord
from engine.formulas import brzycki_e1rm, tonnage as tonnage_fn, tut_sec

workouts_bp = Blueprint("workouts", __name__, url_prefix="/api/workouts")

TEMPO_RE = re.compile(r"^\d{1,2}-\d{1,2}-\d{1,2}-\d{1,2}$")
PAGE_SIZE = 20


def validate_set(raw: dict, index: int) -> dict:
    """Returns field errors for one set, keyed like 'exercises[0].sets[2].reps'."""
    errors = {}
    weight = raw.get("weight_kg")
    if not isinstance(weight, (int, float)) or weight < 0:
        errors["weight_kg"] = "Gewicht moet 0 of hoger zijn"
    reps = raw.get("reps")
    if not isinstance(reps, int) or not (1 <= reps <= 100):
        errors["reps"] = "Reps moet tussen 1 en 100 liggen"
    rpe = raw.get("rpe")
    if rpe is not None and (not isinstance(rpe, (int, float)) or not (1 <= rpe <= 10)):
        errors["rpe"] = "RPE moet tussen 1 en 10 liggen"
    tempo = raw.get("tempo")
    if tempo and not TEMPO_RE.match(tempo):
        errors["tempo"] = "Tempo-formaat: E-P-C-P (bijv. 2-0-1-0)"
    return errors


def validate_workout_payload(data: dict) -> dict:
    fields = {}
    exercises = data.get("exercises")
    if not isinstance(exercises, list) or len(exercises) == 0:
        return {"exercises": "Voeg minstens één oefening toe"}

    total_sets = 0
    for i, ex in enumerate(exercises):
        if not isinstance(ex.get("exercise_id"), int):
            fields[f"exercises[{i}].exercise_id"] = "Ongeldige oefening"
        sets = ex.get("sets")
        if not isinstance(sets, list):
            fields[f"exercises[{i}].sets"] = "Ongeldige sets"
            continue
        total_sets += len(sets)
        for j, s in enumerate(sets):
            for field, msg in validate_set(s, j).items():
                fields[f"exercises[{i}].sets[{j}].{field}"] = msg

    if total_sets == 0:
        fields["sets"] = "Er zijn geen sets gelogd"

    return fields


def upsert_pr(user_id: int, exercise_id: int, record_type: str, value: float, set_id: int, achieved_at) -> bool:
    """Returns True if this is a new PR (created or improved)."""
    existing = PersonalRecord.query.filter_by(
        user_id=user_id, exercise_id=exercise_id, record_type=record_type
    ).first()
    if existing is None:
        db.session.add(PersonalRecord(
            user_id=user_id, exercise_id=exercise_id, record_type=record_type,
            value=value, set_id=set_id, achieved_at=achieved_at,
        ))
        return True
    if float(existing.value) < value:
        existing.value = value
        existing.set_id = set_id
        existing.achieved_at = achieved_at
        return True
    return False


@workouts_bp.route("", methods=["POST"])
@login_required
def create_workout():
    data = request.get_json(silent=True) or {}

    client_uuid = data.get("client_uuid")
    if client_uuid:
        existing = Workout.query.filter_by(client_uuid=client_uuid, user_id=current_user.id).first()
        if existing:
            return jsonify(_workout_response(existing)), 200

    field_errors = validate_workout_payload(data)
    if field_errors:
        body, status = error_response("VALIDATION_ERROR", "Controleer de invoer", field_errors)
        return jsonify(body), status

    performed_at_raw = data.get("performed_at")
    try:
        performed_at = (
            datetime.fromisoformat(performed_at_raw.replace("Z", "+00:00"))
            if performed_at_raw else datetime.now(timezone.utc)
        )
    except ValueError:
        body, status = error_response(
            "VALIDATION_ERROR", "Ongeldige datum", {"performed_at": "ISO-8601 verwacht"}
        )
        return jsonify(body), status

    # Wrapped in a catch-all: same rationale as get_workout_suggestion — an
    # uncaught exception mid-transaction would otherwise surface as Flask's
    # default HTML error page (unparseable JSON on the frontend) and leave
    # a half-flushed transaction. Roll back, log the real traceback, and
    # still hand the client the app's normal JSON error envelope.
    try:
        workout = Workout(
            user_id=current_user.id,
            performed_at=performed_at,
            duration_sec=data.get("duration_sec"),
            title=data.get("title"),
            notes=data.get("notes"),
            source=data.get("source", "manual"),
            client_uuid=client_uuid,
            suggested_from_wod_id=data.get("suggested_from_wod_id") or None,
        )
        db.session.add(workout)
        db.session.flush()  # assigns workout.id without committing yet

        new_prs = []
        achieved_date = performed_at.date()

        for position, ex_data in enumerate(data["exercises"], start=1):
            we = WorkoutExercise(
                workout_id=workout.id,
                exercise_id=ex_data["exercise_id"],
                position=position,
                notes=ex_data.get("notes"),
            )
            db.session.add(we)
            db.session.flush()

            working_sets = []  # (set_row, weight, reps) — excludes warmups, BR-08
            for set_number, s in enumerate(ex_data["sets"], start=1):
                tempo = s.get("tempo")
                reps = s["reps"]
                row = Set(
                    workout_exercise_id=we.id,
                    set_number=set_number,
                    weight_kg=s["weight_kg"],
                    reps=reps,
                    rpe=s.get("rpe"),
                    tempo=tempo,
                    tut_sec=tut_sec(reps, tempo),
                    is_warmup=bool(s.get("is_warmup", False)),
                )
                db.session.add(row)
                db.session.flush()
                if not row.is_warmup:
                    working_sets.append((row, float(row.weight_kg), reps))

            if not working_sets:
                continue

            exercise_id = ex_data["exercise_id"]
            exercise = db.session.get(Exercise, exercise_id)
            exercise_name = exercise.name if exercise else "Oefening"

            max_weight_row = max(working_sets, key=lambda t: t[1])
            max_reps_row = max(working_sets, key=lambda t: t[2])
            total_tonnage = sum(tonnage_fn(w, r) for _, w, r in working_sets)

            best_e1rm = None
            best_e1rm_row = None
            for row, w, r in working_sets:
                e1rm = brzycki_e1rm(w, r)
                if e1rm is not None and (best_e1rm is None or e1rm > best_e1rm):
                    best_e1rm, best_e1rm_row = e1rm, row

            if best_e1rm is not None:
                db.session.add(E1rmHistory(
                    user_id=current_user.id, exercise_id=exercise_id,
                    date=achieved_date, e1rm_kg=best_e1rm, source_set_id=best_e1rm_row.id,
                ))

            if upsert_pr(current_user.id, exercise_id, "weight", max_weight_row[1], max_weight_row[0].id, achieved_date):
                new_prs.append({"exercise": exercise_name, "type": "weight", "value": max_weight_row[1]})
            if upsert_pr(current_user.id, exercise_id, "reps", max_reps_row[2], max_reps_row[0].id, achieved_date):
                new_prs.append({"exercise": exercise_name, "type": "reps", "value": max_reps_row[2]})
            if upsert_pr(current_user.id, exercise_id, "tonnage", total_tonnage, working_sets[0][0].id, achieved_date):
                new_prs.append({"exercise": exercise_name, "type": "tonnage", "value": total_tonnage})
            if best_e1rm is not None and upsert_pr(
                current_user.id, exercise_id, "e1rm", best_e1rm, best_e1rm_row.id, achieved_date
            ):
                new_prs.append({"exercise": exercise_name, "type": "e1rm", "value": best_e1rm})

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to save workout for user_id=%s", current_user.id
        )
        body, status = error_response(
            "WORKOUT_SAVE_FAILED",
            "Workout opslaan mislukt. Probeer het opnieuw.",
            status=500,
        )
        return jsonify(body), status

    return jsonify(_workout_response(workout, new_prs=new_prs)), 201


def _workout_response(workout: Workout, new_prs=None) -> dict:
    total_sets = 0
    total_tonnage = 0.0
    exercises_out = []
    for we in workout.exercises:
        sets_out = []
        for s in we.sets:
            sets_out.append({
                "id": s.id, "set_number": s.set_number,
                "weight_kg": float(s.weight_kg), "reps": s.reps,
                "rpe": float(s.rpe) if s.rpe is not None else None,
                "tempo": s.tempo, "is_warmup": s.is_warmup,
            })
            total_sets += 1
            if not s.is_warmup:
                total_tonnage += float(s.weight_kg) * s.reps
        exercises_out.append({
            "id": we.id, "exercise_id": we.exercise_id,
            "exercise_name": we.exercise.name if we.exercise else None,
            "position": we.position, "notes": we.notes, "sets": sets_out,
        })

    return {
        "workout": {
            "id": workout.id,
            "performed_at": workout.performed_at.isoformat(),
            "duration_sec": workout.duration_sec,
            "title": workout.title,
            "notes": workout.notes,
            "source": workout.source,
            "suggested_from_wod_id": workout.suggested_from_wod_id,
            "exercises": exercises_out,
        },
        "summary": {
            "total_sets": total_sets,
            "total_tonnage": round(total_tonnage, 2),
            "new_prs": new_prs or [],
        },
    }


@workouts_bp.route("", methods=["GET"])
@login_required
def list_workouts():
    exercise_id = request.args.get("exercise_id", type=int)
    page = max(1, request.args.get("page", 1, type=int))

    query = Workout.query.filter_by(user_id=current_user.id).filter(Workout.deleted_at.is_(None))
    if exercise_id:
        query = query.join(WorkoutExercise).filter(WorkoutExercise.exercise_id == exercise_id)

    query = query.order_by(Workout.performed_at.desc())
    total = query.count()
    workouts = query.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all()

    return jsonify({
        "workouts": [_workout_response(w)["workout"] for w in workouts],
        "page": page,
        "page_size": PAGE_SIZE,
        "total": total,
    }), 200


@workouts_bp.route("/<int:workout_id>", methods=["GET"])
@login_required
def get_workout(workout_id):
    workout = Workout.query.filter_by(id=workout_id, user_id=current_user.id).first()
    if not workout or workout.deleted_at is not None:
        return jsonify(error_response("NOT_FOUND", "Workout niet gevonden", status=404)[0]), 404
    return jsonify(_workout_response(workout)), 200


@workouts_bp.route("/<int:workout_id>", methods=["DELETE"])
@login_required
def delete_workout(workout_id):
    workout = Workout.query.filter_by(id=workout_id, user_id=current_user.id).first()
    if not workout or workout.deleted_at is not None:
        return jsonify(error_response("NOT_FOUND", "Workout niet gevonden", status=404)[0]), 404
    workout.deleted_at = datetime.now(timezone.utc)
    db.session.commit()
    return "", 204


@workouts_bp.route("/<int:workout_id>/restore", methods=["POST"])
@login_required
def restore_workout(workout_id):
    workout = Workout.query.filter_by(id=workout_id, user_id=current_user.id).first()
    if not workout or workout.deleted_at is None:
        return jsonify(error_response("NOT_FOUND", "Niets te herstellen", status=404)[0]), 404
    workout.deleted_at = None
    db.session.commit()
    return jsonify(_workout_response(workout)), 200
