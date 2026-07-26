"""Tests for GET /api/recommendation. Run with: py -m pytest"""
import pytest

from app import create_app
from extensions import db
from seed import seed_equipment, seed_muscle_groups, seed_exercises
from models import Exercise

VALID_USER = {
    "username": "sanne_lifts",
    "email": "sanne@example.com",
    "password": "bench123",
    "password_confirm": "bench123",
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
    return c


@pytest.fixture
def bench_id(app):
    with app.app_context():
        return Exercise.query.filter_by(name="Bench Press").first().id


def test_recommendation_requires_login(bench_id):
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True})
    with app.app_context():
        db.create_all()
    resp = app.test_client().get(f"/api/recommendation?exercise_id={bench_id}")
    assert resp.status_code == 401


def test_recommendation_requires_exercise_id(client):
    resp = client.get("/api/recommendation")
    assert resp.status_code == 400


def test_recommendation_unknown_exercise_404(client):
    resp = client.get("/api/recommendation?exercise_id=999999")
    assert resp.status_code == 404


def test_recommendation_cold_start(client, bench_id):
    resp = client.get(f"/api/recommendation?exercise_id={bench_id}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["cold_start"] is True
    assert body["weight_kg"] is None


def test_recommendation_with_history_returns_numeric_weight(client, bench_id):
    """Regression test: Set.weight_kg/rpe are Numeric (Decimal) DB columns.
    Before the float() cast in _sessions_for_exercise, this crashed
    round_to_plate() (Decimal/float TypeError) whenever the recommended
    exercise had real history, and separately serialized weight_kg as a
    JSON string ("100.0") instead of a number wherever it didn't crash."""
    client.post("/api/workouts", json={
        "performed_at": "2026-07-20T18:00:00Z",
        "duration_sec": 3000,
        "source": "manual",
        "exercises": [{
            "exercise_id": bench_id,
            "sets": [
                {"weight_kg": 100, "reps": 5, "rpe": 8},
                {"weight_kg": 100, "reps": 5, "rpe": 8.5},
            ],
        }],
    })

    resp = client.get(f"/api/recommendation?exercise_id={bench_id}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert isinstance(body["weight_kg"], (int, float))
    assert body["cold_start"] is False
