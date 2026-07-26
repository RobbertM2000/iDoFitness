"""Tests for GET /api/workout-suggestion. Run with: py -m pytest"""
from unittest.mock import patch

import pytest

from app import create_app
from extensions import db
from models import Exercise
from seed import seed_equipment, seed_muscle_groups, seed_exercises

VALID_USER = {
    "username": "sanne_lifts",
    "email": "sanne@example.com",
    "password": "bench123",
    "password_confirm": "bench123",
}

VALID_ONBOARDING = {
    "display_name": "Sanne",
    "age": 29,
    "height_cm": 170,
    "bodyweight_kg": 68.5,
    "sex": "vrouw",
    "global_goal": "strength",
    "experience": "advanced",
    "days_per_week": 4,
    "session_minutes": 60,
    "training_location": "gym",
    "privacy_accepted": True,
}


@pytest.fixture
def app():
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True})
    with app.app_context():
        db.create_all()
        seed_equipment()
        seed_muscle_groups()
        seed_exercises()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post("/api/auth/register", json=VALID_USER)
    c.post("/api/onboarding", json=VALID_ONBOARDING)
    return c


def test_workout_suggestion_includes_wod_id_and_is_compound(client):
    resp = client.get("/api/workout-suggestion")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["wod_id"] == f"{body['date']}:{body['goal']}"
    assert len(body["exercises"]) > 0
    for exercise in body["exercises"]:
        assert "is_compound" in exercise


def test_workout_suggestion_requires_login():
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True})
    with app.app_context():
        db.create_all()
    resp = app.test_client().get("/api/workout-suggestion")
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "UNAUTHENTICATED"


def test_workout_suggestion_with_trained_compound_exercise(app, client):
    """Regression test for the real-world crash: Set.weight_kg/rpe are
    Numeric (Decimal) DB columns. Once a compound exercise has real
    history, its Decimal weight_kg reached _build_warmup's
    round_to_plate(), which does `weight_kg / 2.5` — Decimal/float raises
    TypeError, so any returning user with logged history on their
    first-ranked compound lift got a hard 500 (the actual root cause
    behind the "Er ging iets mis" reports, not just an edge case).

    Calls generate_wod directly with a single-candidate list built from
    real DB history, so this doesn't depend on the exercise-selection
    ranking happening to pick the trained exercise first.
    """
    from api.recommendations import _sessions_for_exercise
    from engine.predictor import UserProfile
    from engine.wod_generator import ExerciseInfo, generate_wod

    bench_id = Exercise.query.filter_by(name="Flat DB Press").first().id
    resp = client.post("/api/workouts", json={
        "performed_at": "2026-07-20T18:00:00Z",
        "duration_sec": 2000,
        "source": "manual",
        "exercises": [{
            "exercise_id": bench_id,
            "sets": [
                {"weight_kg": 22.5, "reps": 8, "rpe": 7.5},
                {"weight_kg": 22.5, "reps": 8, "rpe": 8},
            ],
        }],
    })
    assert resp.status_code == 201

    with app.app_context():
        candidates = [ExerciseInfo(
            exercise_id=bench_id, name="Flat DB Press", muscle_group="chest",
            is_compound=True, is_main_lift=False,
        )]
        histories = {bench_id: _sessions_for_exercise(1, bench_id)}
        wod = generate_wod(candidates, histories, UserProfile(global_goal="hypertrophy"), 60)

    trained = next(e for e in wod.exercises if e.exercise_id == bench_id)
    assert isinstance(trained.weight_kg, (int, float))
    for ramp in wod.warmup.ramp_sets:
        assert isinstance(ramp["weight_kg"], (int, float))


def test_workout_suggestion_engine_failure_returns_json_error(client):
    """An unexpected exception anywhere in the generation pipeline must
    still produce the app's normal JSON error envelope — never Flask's
    default HTML error page, which the frontend can't parse (and which is
    exactly what used to surface as an opaque "Er ging iets mis")."""
    with patch("api.suggestions.generate_wod", side_effect=RuntimeError("boom")):
        resp = client.get("/api/workout-suggestion")
    assert resp.status_code == 500
    body = resp.get_json()
    assert body is not None
    assert body["error"]["code"] == "SUGGESTION_FAILED"
    assert body["error"]["message"]
