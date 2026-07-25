"""Tests for the auth blueprint. Run with: py -m pytest"""
import pytest

from app import create_app
from extensions import db


@pytest.fixture
def app():
    app = create_app({
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
    })
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


VALID_USER = {
    "username": "sanne_lifts",
    "email": "sanne@example.com",
    "password": "bench123",
    "password_confirm": "bench123",
}


def test_register_success(client):
    resp = client.post("/api/auth/register", json=VALID_USER)
    assert resp.status_code == 201
    assert resp.get_json()["user"]["username"] == "sanne_lifts"


def test_register_rejects_short_password(client):
    bad = {**VALID_USER, "password": "abc", "password_confirm": "abc"}
    resp = client.post("/api/auth/register", json=bad)
    assert resp.status_code == 422
    assert "password" in resp.get_json()["error"]["fields"]


def test_register_rejects_mismatched_confirmation(client):
    bad = {**VALID_USER, "password_confirm": "different1"}
    resp = client.post("/api/auth/register", json=bad)
    assert resp.status_code == 422
    assert "password_confirm" in resp.get_json()["error"]["fields"]


def test_register_duplicate_username_returns_409(client):
    client.post("/api/auth/register", json=VALID_USER)
    resp = client.post("/api/auth/register", json=VALID_USER)
    assert resp.status_code == 409


def test_check_username_availability(client):
    resp = client.get("/api/auth/check-username?u=sanne_lifts")
    assert resp.get_json() == {"available": True}
    client.post("/api/auth/register", json=VALID_USER)
    resp = client.get("/api/auth/check-username?u=sanne_lifts")
    assert resp.get_json() == {"available": False}


def test_login_success(client):
    client.post("/api/auth/register", json=VALID_USER)
    client.post("/api/auth/logout")
    resp = client.post(
        "/api/auth/login",
        json={"username": "sanne_lifts", "password": "bench123"},
    )
    assert resp.status_code == 200


def test_login_wrong_password_returns_generic_401(client):
    client.post("/api/auth/register", json=VALID_USER)
    resp = client.post(
        "/api/auth/login",
        json={"username": "sanne_lifts", "password": "wrongpass1"},
    )
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_me_requires_login(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user_after_login(client):
    client.post("/api/auth/register", json=VALID_USER)
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.get_json()["user"]["username"] == "sanne_lifts"


def test_logout_clears_session(client):
    client.post("/api/auth/register", json=VALID_USER)
    client.post("/api/auth/logout")
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
