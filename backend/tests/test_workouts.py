"""Tests for the workouts blueprint. Run with: py -m pytest"""
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


def workout_payload(bench_id, weight=100, reps=5, rpe=8):
    return {
        "performed_at": "2026-07-20T18:00:00Z",
        "duration_sec": 3000,
        "title": "Push Day",
        "source": "manual",
        "exercises": [
            {
                "exercise_id": bench_id,
                "sets": [
                    {"weight_kg": weight, "reps": reps, "rpe": rpe, "tempo": "2-0-1-0"},
                    {"weight_kg": weight, "reps": reps, "rpe": rpe},
                ],
            }
        ],
    }


def test_create_workout_requires_login(bench_id):
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True})
    with app.app_context():
        db.create_all()
    resp = app.test_client().post("/api/workouts", json=workout_payload(bench_id))
    assert resp.status_code == 401


def test_create_workout_success(client, bench_id):
    resp = client.post("/api/workouts", json=workout_payload(bench_id))
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["summary"]["total_sets"] == 2
    assert body["summary"]["total_tonnage"] == 1000.0  # 2 x (100*5)
    assert body["workout"]["title"] == "Push Day"


def test_create_workout_rejects_empty_exercises(client):
    resp = client.post("/api/workouts", json={"exercises": []})
    assert resp.status_code == 422


def test_create_workout_rejects_invalid_reps(client, bench_id):
    payload = workout_payload(bench_id)
    payload["exercises"][0]["sets"][0]["reps"] = 0
    resp = client.post("/api/workouts", json=payload)
    assert resp.status_code == 422


def test_create_workout_rejects_bad_tempo_format(client, bench_id):
    payload = workout_payload(bench_id)
    payload["exercises"][0]["sets"][0]["tempo"] = "fast"
    resp = client.post("/api/workouts", json=payload)
    assert resp.status_code == 422


def test_first_workout_sets_all_pr_types(client, bench_id):
    resp = client.post("/api/workouts", json=workout_payload(bench_id))
    prs = resp.get_json()["summary"]["new_prs"]
    types = {p["type"] for p in prs}
    assert types == {"weight", "reps", "tonnage", "e1rm"}


def test_second_lighter_workout_sets_no_new_prs(client, bench_id):
    client.post("/api/workouts", json=workout_payload(bench_id, weight=100, reps=5))
    resp = client.post("/api/workouts", json=workout_payload(bench_id, weight=90, reps=5))
    assert resp.get_json()["summary"]["new_prs"] == []


def test_heavier_second_workout_sets_weight_pr(client, bench_id):
    client.post("/api/workouts", json=workout_payload(bench_id, weight=100, reps=5))
    resp = client.post("/api/workouts", json=workout_payload(bench_id, weight=105, reps=5))
    prs = resp.get_json()["summary"]["new_prs"]
    assert any(p["type"] == "weight" and p["value"] == 105 for p in prs)


def test_idempotency_key_prevents_duplicate(client, bench_id):
    payload = workout_payload(bench_id)
    payload["client_uuid"] = "abc-123"
    first = client.post("/api/workouts", json=payload)
    second = client.post("/api/workouts", json=payload)
    assert first.status_code == 201
    assert second.status_code == 200  # returns existing, not a new one
    assert first.get_json()["workout"]["id"] == second.get_json()["workout"]["id"]

    history = client.get("/api/workouts").get_json()
    assert history["total"] == 1


def test_warmup_sets_excluded_from_tonnage_and_prs(client, bench_id):
    payload = {
        "performed_at": "2026-07-20T18:00:00Z",
        "exercises": [{
            "exercise_id": bench_id,
            "sets": [
                {"weight_kg": 150, "reps": 20, "rpe": 3, "is_warmup": True},
                {"weight_kg": 100, "reps": 5, "rpe": 8, "is_warmup": False},
            ],
        }],
    }
    resp = client.post("/api/workouts", json=payload)
    body = resp.get_json()
    assert body["summary"]["total_tonnage"] == 500.0  # only the working set
    prs = body["summary"]["new_prs"]
    weight_pr = next(p for p in prs if p["type"] == "weight")
    assert weight_pr["value"] == 100  # not the 150kg warmup


def test_list_workouts_pagination_and_ordering(client, bench_id):
    for i in range(3):
        payload = workout_payload(bench_id)
        payload["performed_at"] = f"2026-07-{20+i}T18:00:00Z"
        client.post("/api/workouts", json=payload)

    resp = client.get("/api/workouts")
    body = resp.get_json()
    assert body["total"] == 3
    dates = [w["performed_at"] for w in body["workouts"]]
    assert dates == sorted(dates, reverse=True)  # most recent first


def test_filter_history_by_exercise(client, bench_id, app):
    with app.app_context():
        squat_id = Exercise.query.filter_by(name="Back Squat").first().id
    client.post("/api/workouts", json=workout_payload(bench_id))
    client.post("/api/workouts", json=workout_payload(squat_id))

    resp = client.get(f"/api/workouts?exercise_id={bench_id}")
    assert resp.get_json()["total"] == 1


def test_soft_delete_and_restore(client, bench_id):
    created = client.post("/api/workouts", json=workout_payload(bench_id)).get_json()
    workout_id = created["workout"]["id"]

    delete_resp = client.delete(f"/api/workouts/{workout_id}")
    assert delete_resp.status_code == 204
    assert client.get("/api/workouts").get_json()["total"] == 0

    restore_resp = client.post(f"/api/workouts/{workout_id}/restore")
    assert restore_resp.status_code == 200
    assert client.get("/api/workouts").get_json()["total"] == 1


def test_delete_nonexistent_workout_404(client):
    resp = client.delete("/api/workouts/999999")
    assert resp.status_code == 404


def test_get_single_workout(client, bench_id):
    created = client.post("/api/workouts", json=workout_payload(bench_id)).get_json()
    workout_id = created["workout"]["id"]
    resp = client.get(f"/api/workouts/{workout_id}")
    assert resp.status_code == 200
    assert resp.get_json()["workout"]["exercises"][0]["exercise_name"] == "Bench Press"
