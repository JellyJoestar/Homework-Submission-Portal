"""
Shared pytest fixtures.

The tests do NOT need MySQL: database functions are replaced with fakes
using monkeypatch.

Fixtures you can use in any test:
    client          -> anonymous user (not logged in)
    teacher_client  -> logged in as the demo Teacher
    student_client  -> logged in as the demo Student
"""
import pytest
from werkzeug.security import generate_password_hash

import auth
from app import app as flask_app
from models import User

PASSWORD = "Password123!"
TEACHER_ID = 1
STUDENT_ID = 2


@pytest.fixture
def users():
    password_hash = generate_password_hash(PASSWORD)
    return {
        TEACHER_ID: User(TEACHER_ID, "teacher@portal.edu.au", password_hash, "Teacher", "Tess", "Teacher"),
        STUDENT_ID: User(STUDENT_ID, "student1@portal.edu.au", password_hash, "Student", "Sam", "Student"),
    }


@pytest.fixture
def app(monkeypatch, users):
    # Fake user lookups so login works without a database
    monkeypatch.setattr(auth, "get_user_by_id", lambda user_id: users.get(user_id))
    monkeypatch.setattr(
        auth,
        "get_user_by_email",
        lambda email: next((user for user in users.values() if user.email == email), None)
    )
    flask_app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret-key",
        WTF_CSRF_ENABLED=False
    )
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def login_as(client, user_id):
    # Flask-Login keeps the logged user id in the session cookie under "_user_id"
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


@pytest.fixture
def teacher_client(client):
    login_as(client, TEACHER_ID)
    return client


@pytest.fixture
def student_client(client):
    login_as(client, STUDENT_ID)
    return client
