"""Tests for the onboarding/profile blueprint. Run with: py -m pytest"""
import pytest

from app import create_app
from extensions import db
from models import Equipment

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
    app = create_app({
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "TESTING": True,
    })
    with app.app_context():
        db.create_all()
        for name in ["barbell", "dumbbell", "rack", "bench", "bodyweight"]:
            db.session.add(Equipment(name=name))
        db.session.commit()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post("/api/auth/register", json=VALID_USER)
    return c


def test_onboarding_requires_login():
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True})
    with app.app_context():
        db.create_all()
    c = app.test_client()
    resp = c.post("/api/onboarding", json=VALID_ONBOARDING)
    assert resp.status_code == 401


def test_onboarding_success_marks_completed(client):
    resp = client.post("/api/onboarding", json=VALID_ONBOARDING)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["user"]["onboarding_completed"] is True
    assert body["user"]["global_goal"] == "strength"
    assert body["user"]["display_name"] == "Sanne"


def test_onboarding_gym_grants_all_equipment(client):
    client.post("/api/onboarding", json=VALID_ONBOARDING)
    profile = client.get("/api/profile").get_json()["user"]
    assert profile["training_location"] == "gym"


def test_onboarding_home_requires_equipment_selection(client):
    payload = {**VALID_ONBOARDING, "training_location": "home", "equipment": []}
    resp = client.post("/api/onboarding", json=payload)
    assert resp.status_code == 422
    assert "equipment" in resp.get_json()["error"]["fields"]


def test_onboarding_home_with_equipment_succeeds(client):
    payload = {**VALID_ONBOARDING, "training_location": "home", "equipment": ["dumbbell", "bench"]}
    resp = client.post("/api/onboarding", json=payload)
    assert resp.status_code == 200


def test_onboarding_rejects_underage(client):
    payload = {**VALID_ONBOARDING, "age": 15}
    resp = client.post("/api/onboarding", json=payload)
    assert resp.status_code == 422
    assert "age" in resp.get_json()["error"]["fields"]


def test_onboarding_rejects_invalid_goal(client):
    payload = {**VALID_ONBOARDING, "global_goal": "cardio"}
    resp = client.post("/api/onboarding", json=payload)
    assert resp.status_code == 422
    assert "global_goal" in resp.get_json()["error"]["fields"]


def test_onboarding_rejects_missing_privacy_consent(client):
    payload = {**VALID_ONBOARDING, "privacy_accepted": False}
    resp = client.post("/api/onboarding", json=payload)
    assert resp.status_code == 422
    assert "privacy_accepted" in resp.get_json()["error"]["fields"]


def test_get_profile_returns_current_user(client):
    client.post("/api/onboarding", json=VALID_ONBOARDING)
    resp = client.get("/api/profile")
    assert resp.status_code == 200
    assert resp.get_json()["user"]["username"] == "sanne_lifts"


def test_patch_profile_changes_goal(client):
    client.post("/api/onboarding", json=VALID_ONBOARDING)
    resp = client.patch("/api/profile", json={"global_goal": "hypertrophy"})
    assert resp.status_code == 200
    assert resp.get_json()["user"]["global_goal"] == "hypertrophy"


def test_patch_profile_rejects_invalid_goal(client):
    resp = client.patch("/api/profile", json={"global_goal": "not_a_goal"})
    assert resp.status_code == 422


def test_list_equipment(client):
    resp = client.get("/api/equipment")
    assert resp.status_code == 200
    names = [e["name"] for e in resp.get_json()["equipment"]]
    assert "barbell" in names
