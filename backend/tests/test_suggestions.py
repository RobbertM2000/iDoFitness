"""Tests for GET /api/workout-suggestion. Run with: py -m pytest"""
import pytest

from app import create_app
from extensions import db
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
