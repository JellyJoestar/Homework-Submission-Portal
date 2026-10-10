"""Functional tests for IFN636-45: log out of the portal."""
import views


def test_logout_redirects_to_login(teacher_client):
    response = teacher_client.post("/logout")

    assert response.status_code == 302
    assert response.headers["Location"] == "/login"


def test_protected_pages_are_blocked_after_logout(teacher_client):
    teacher_client.post("/logout")

    response = teacher_client.get("/teacher/assessments")

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login")


def test_logout_requires_post(teacher_client):
    response = teacher_client.get("/logout")

    assert response.status_code == 405


def test_logout_button_hidden_for_anonymous_users(client):
    response = client.get("/login")

    assert b"Log out" not in response.data


def test_logout_button_shown_for_logged_users(student_client, monkeypatch):
    monkeypatch.setattr(views, "get_published_assessments", lambda: [])

    response = student_client.get("/student")

    assert response.status_code == 200
    assert b"Log out" in response.data


def test_protected_pages_are_not_cached_by_the_browser(student_client, monkeypatch):
    # "no-store" stops the back button from showing the page after logout
    monkeypatch.setattr(views, "get_published_assessments", lambda: [])

    response = student_client.get("/student")

    assert response.headers["Cache-Control"] == "no-store"
