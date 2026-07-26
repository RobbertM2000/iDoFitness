"""Tests for the exercises blueprint. Run with: py -m pytest"""
import pytest

from app import create_app
from extensions import db
from seed import seed_equipment, seed_muscle_groups, seed_exercises

VALID_USER = {
    "username": "daan_hyper",
    "email": "daan@example.com",
    "password": "chest123",
    "password_confirm": "chest123",
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


def test_seed_populates_expected_count():
    from exercise_data import EXERCISES
    assert len(EXERCISES) >= 50


def test_list_exercises_requires_login():
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True})
    with app.app_context():
        db.create_all()
    resp = app.test_client().get("/api/exercises")
    assert resp.status_code == 401


def test_list_exercises_returns_seeded_library(client):
    resp = client.get("/api/exercises")
    assert resp.status_code == 200
    names = [e["name"] for e in resp.get_json()["exercises"]]
    assert "Bench Press" in names


def test_filter_by_muscle(client):
    resp = client.get("/api/exercises?muscle=chest")
    assert resp.status_code == 200
    exercises = resp.get_json()["exercises"]
    assert len(exercises) > 0
    assert all(e["muscle"] == "chest" for e in exercises)


def test_search_by_query(client):
    resp = client.get("/api/exercises?q=squat")
    names = [e["name"].lower() for e in resp.get_json()["exercises"]]
    assert any("squat" in n for n in names)


def test_get_single_exercise_with_alternatives(client):
    bench = next(e for e in client.get("/api/exercises").get_json()["exercises"] if e["name"] == "Bench Press")
    resp = client.get(f"/api/exercises/{bench['id']}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["technique_tips"]
    assert body["common_mistakes"]
    assert len(body["alternatives"]) > 0


def test_get_nonexistent_exercise_404(client):
    resp = client.get("/api/exercises/999999")
    assert resp.status_code == 404


def test_create_custom_exercise(client):
    resp = client.post("/api/exercises", json={
        "name": "Landmine Press",
        "muscle": "shoulders",
        "equipment": "barbell",
        "is_compound": True,
    })
    assert resp.status_code == 201
    assert resp.get_json()["is_custom"] is True


def test_create_custom_exercise_duplicate_rejected(client):
    payload = {"name": "My Curl", "muscle": "biceps", "equipment": "dumbbell"}
    client.post("/api/exercises", json=payload)
    resp = client.post("/api/exercises", json=payload)
    assert resp.status_code == 409


def test_create_custom_exercise_invalid_muscle(client):
    resp = client.post("/api/exercises", json={
        "name": "Weird Move", "muscle": "not_a_muscle", "equipment": "barbell",
    })
    assert resp.status_code == 422
    assert "muscle" in resp.get_json()["error"]["fields"]


def test_avoid_and_unavoid_exercise(client):
    bench = next(e for e in client.get("/api/exercises").get_json()["exercises"] if e["name"] == "Bench Press")
    resp = client.post(f"/api/exercises/{bench['id']}/avoid", json={"reason": "shoulder injury"})
    assert resp.status_code == 200

    exercises = client.get("/api/exercises").get_json()["exercises"]
    updated = next(e for e in exercises if e["id"] == bench["id"])
    assert updated["is_avoided"] is True

    resp = client.delete(f"/api/exercises/{bench['id']}/avoid")
    assert resp.status_code == 204
    exercises = client.get("/api/exercises").get_json()["exercises"]
    updated = next(e for e in exercises if e["id"] == bench["id"])
    assert updated["is_avoided"] is False
