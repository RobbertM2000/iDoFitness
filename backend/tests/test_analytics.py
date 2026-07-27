"""Tests for the analytics blueprint (dashboard/volume/progression/dismiss).
Run with: py -m pytest"""
import pytest

from app import create_app
from extensions import db
from seed import seed_equipment, seed_muscle_groups, seed_exercises
from models import Exercise, Warning

HYPERTROPHY_ONBOARDING = {
    "display_name": "Hyper",
    "age": 27, "height_cm": 175, "bodyweight_kg": 70, "sex": "vrouw",
    "global_goal": "hypertrophy", "experience": "intermediate",
    "days_per_week": 4, "session_minutes": 60, "training_location": "gym",
    "privacy_accepted": True,
}

STRENGTH_ONBOARDING = {**HYPERTROPHY_ONBOARDING, "global_goal": "strength", "display_name": "Str"}


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
def hyper_client(app):
    c = app.test_client()
    c.post("/api/auth/register", json={
        "username": "hyperuser", "email": "hyper@example.com",
        "password": "testpass123", "password_confirm": "testpass123",
    })
    c.post("/api/onboarding", json=HYPERTROPHY_ONBOARDING)
    return c


@pytest.fixture
def strength_client(app):
    c = app.test_client()
    c.post("/api/auth/register", json={
        "username": "strengthuser", "email": "strength@example.com",
        "password": "testpass123", "password_confirm": "testpass123",
    })
    c.post("/api/onboarding", json=STRENGTH_ONBOARDING)
    return c


@pytest.fixture
def bench_id(app):
    with app.app_context():
        return Exercise.query.filter_by(name="Bench Press").first().id


def log_workout(client, exercise_id, performed_at, weight=80, reps=5, rpe=7):
    return client.post("/api/workouts", json={
        "performed_at": performed_at,
        "duration_sec": 2400,
        "source": "manual",
        "exercises": [{"exercise_id": exercise_id, "sets": [
            {"weight_kg": weight, "reps": reps, "rpe": rpe},
        ]}],
    })


# ---------------------------------------------------------------------------
# GET /api/analytics/dashboard
# ---------------------------------------------------------------------------

def test_dashboard_requires_login():
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True})
    with app.app_context():
        db.create_all()
    resp = app.test_client().get("/api/analytics/dashboard")
    assert resp.status_code == 401


def test_dashboard_cold_start_hypertrophy_user_no_crash(hyper_client):
    resp = hyper_client.get("/api/analytics/dashboard")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["goal"] == "hypertrophy"
    assert body["week_volume_kg"] == 0
    assert len(body["volume_sparkline"]) == 8
    assert body["recent_workouts"] == []
    assert body["streak_days"] == 0
    assert body["rep_range_distribution"] is None  # no sets logged yet
    assert body["muscle_group_volume"] == {}
    # brand-new user with zero workouts ever -> inactivity warning
    assert any(w["type"] == "inactivity" for w in body["warnings"])


def test_dashboard_cold_start_strength_user_no_crash(strength_client):
    resp = strength_client.get("/api/analytics/dashboard")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["goal"] == "strength"
    assert "main_lift_e1rms" in body
    assert len(body["main_lift_e1rms"]) >= 1
    for lift in body["main_lift_e1rms"]:
        assert lift["current"] is None
        assert lift["series"] == []
    assert body["rpe_distribution"] == {"6": 0, "7": 0, "8": 0, "9": 0, "10": 0}


def test_dashboard_warnings_capped_at_three(hyper_client):
    resp = hyper_client.get("/api/analytics/dashboard")
    assert len(resp.get_json()["warnings"]) <= 3


def test_dashboard_with_logged_workout_updates_volume_and_streak(hyper_client, bench_id):
    resp = log_workout(hyper_client, bench_id, "2026-07-27T18:00:00Z", weight=80, reps=5)
    assert resp.status_code == 201

    resp = hyper_client.get("/api/analytics/dashboard")
    body = resp.get_json()
    assert body["week_volume_kg"] == 400.0  # 80 * 5
    assert body["streak_days"] == 1
    assert len(body["recent_workouts"]) == 1
    assert body["recent_workouts"][0]["tonnage_kg"] == 400.0


def test_dashboard_strength_user_shows_main_lift_after_logging(strength_client, bench_id):
    log_workout(strength_client, bench_id, "2026-07-27T18:00:00Z", weight=100, reps=5, rpe=8)
    resp = strength_client.get("/api/analytics/dashboard")
    body = resp.get_json()
    bench = next(l for l in body["main_lift_e1rms"] if l["exercise_id"] == bench_id)
    assert bench["current"] is not None
    assert isinstance(bench["current"], float)
    assert bench["last_trained"] == "2026-07-27"


# ---------------------------------------------------------------------------
# GET /api/analytics/volume
# ---------------------------------------------------------------------------

def test_volume_endpoint_shape(hyper_client):
    resp = hyper_client.get("/api/analytics/volume?weeks=4")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["weeks"] == 4
    assert len(body["weekly_tonnage"]) == 4
    assert body["muscle_group_volume"] == {}


def test_volume_endpoint_clamps_weeks(hyper_client):
    resp = hyper_client.get("/api/analytics/volume?weeks=999")
    assert resp.get_json()["weeks"] == 52


# ---------------------------------------------------------------------------
# GET /api/analytics/progression
# ---------------------------------------------------------------------------

def test_progression_requires_exercise_id(hyper_client):
    resp = hyper_client.get("/api/analytics/progression")
    assert resp.status_code == 400


def test_progression_unknown_exercise_404(hyper_client):
    resp = hyper_client.get("/api/analytics/progression?exercise_id=999999")
    assert resp.status_code == 404


def test_progression_zero_sessions(hyper_client, bench_id):
    resp = hyper_client.get(f"/api/analytics/progression?exercise_id={bench_id}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["provisional"] is True
    assert body["regression"] is None
    assert body["data_points"] == []
    assert body["personal_records"] == {}
    assert body["is_compound"] is True  # Bench Press


def test_progression_provisional_below_five_sessions(hyper_client, bench_id):
    for i, d in enumerate(["2026-06-01", "2026-06-08", "2026-06-15"]):
        log_workout(hyper_client, bench_id, f"{d}T18:00:00Z", weight=80 + i, reps=5, rpe=7)

    resp = hyper_client.get(f"/api/analytics/progression?exercise_id={bench_id}")
    body = resp.get_json()
    assert body["provisional"] is True  # < COLD_START_MIN_SESSIONS (5)
    assert body["regression"] is None  # < BR-06's 5-point floor too
    assert len(body["data_points"]) == 3


def test_progression_with_five_sessions_computes_regression(hyper_client, bench_id):
    dates = ["2026-06-01", "2026-06-08", "2026-06-15", "2026-06-22", "2026-06-29"]
    for i, d in enumerate(dates):
        log_workout(hyper_client, bench_id, f"{d}T18:00:00Z", weight=80 + i * 2.5, reps=5, rpe=7)

    resp = hyper_client.get(f"/api/analytics/progression?exercise_id={bench_id}")
    body = resp.get_json()
    assert body["provisional"] is False
    assert len(body["data_points"]) == 5
    assert body["regression"]["slope"] > 0  # weight increased every session
    assert body["regression"]["forecast_2weeks"] > body["data_points"][-1]["e1rm_kg"]
    for point in body["data_points"]:
        assert point["weight_kg"] is not None
        assert point["reps"] == 5
        assert point["e1rm_kg"] is not None  # reps<=10 -> BR-07 valid


def test_progression_marks_pr_points_and_returns_personal_records(hyper_client, bench_id):
    log_workout(hyper_client, bench_id, "2026-06-01T18:00:00Z", weight=80, reps=5, rpe=7)
    log_workout(hyper_client, bench_id, "2026-06-08T18:00:00Z", weight=90, reps=5, rpe=8)  # new weight PR

    resp = hyper_client.get(f"/api/analytics/progression?exercise_id={bench_id}")
    body = resp.get_json()
    assert body["data_points"][0]["is_pr"] is True  # first-ever set is a PR
    assert body["data_points"][1]["is_pr"] is True  # heavier -> new weight PR
    assert body["personal_records"]["weight"]["value"] == 90.0
    assert "e1rm" in body["personal_records"]
    assert "tonnage" in body["personal_records"]


def test_progression_session_with_only_high_reps_has_no_e1rm(hyper_client, bench_id):
    """BR-07: e1RM only valid for reps<=10 — an all-high-rep session still
    produces a weight data point (best tonnage set), just no e1rm_kg."""
    log_workout(hyper_client, bench_id, "2026-06-01T18:00:00Z", weight=40, reps=15, rpe=7)

    resp = hyper_client.get(f"/api/analytics/progression?exercise_id={bench_id}")
    body = resp.get_json()
    assert len(body["data_points"]) == 1
    assert body["data_points"][0]["weight_kg"] == 40.0
    assert body["data_points"][0]["reps"] == 15
    assert body["data_points"][0]["e1rm_kg"] is None


# ---------------------------------------------------------------------------
# POST /api/warnings/<id>/dismiss
# ---------------------------------------------------------------------------

def test_dismiss_warning_hides_it_for_seven_days(hyper_client):
    warnings = hyper_client.get("/api/analytics/dashboard").get_json()["warnings"]
    assert warnings  # brand-new user should have at least the inactivity warning
    warning_id = warnings[0]["id"]

    resp = hyper_client.post(f"/api/warnings/{warning_id}/dismiss")
    assert resp.status_code == 204

    warnings_after = hyper_client.get("/api/analytics/dashboard").get_json()["warnings"]
    assert all(w["id"] != warning_id for w in warnings_after)


def test_dismiss_nonexistent_warning_404(hyper_client):
    resp = hyper_client.post("/api/warnings/999999/dismiss")
    assert resp.status_code == 404


def test_dismiss_requires_login():
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True})
    with app.app_context():
        db.create_all()
    resp = app.test_client().post("/api/warnings/1/dismiss")
    assert resp.status_code == 401


def test_cannot_dismiss_another_users_warning(app, hyper_client, strength_client):
    # Each call gets its own nested app context: the `app` fixture holds one
    # context open for the whole test, and Flask-Login caches current_user
    # on flask.g, which is scoped to the app context — without a fresh
    # nested push per call, the second client's request would see the
    # first client's cached user instead of its own (a test-isolation
    # artifact; real requests each get a fresh context automatically).
    with app.app_context():
        warning_id = hyper_client.get("/api/analytics/dashboard").get_json()["warnings"][0]["id"]
    with app.app_context():
        resp = strength_client.post(f"/api/warnings/{warning_id}/dismiss")
    assert resp.status_code == 404
