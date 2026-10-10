"""Functional tests for IFN636-43: login with credentials."""

from conftest import PASSWORD


def test_login_page_loads(client):
    response = client.get("/login")

    assert response.status_code == 200
    assert b"Log in" in response.data


def test_teacher_login_redirects_to_teacher_dashboard(client):
    response = client.post(
        "/login", data={"email": "teacher@portal.edu.au", "password": PASSWORD}
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/teacher/assessments"


def test_student_login_redirects_to_student_dashboard(client):
    response = client.post(
        "/login", data={"email": "student1@portal.edu.au", "password": PASSWORD}
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/student"


def test_login_with_wrong_password_shows_error(client):
    response = client.post(
        "/login", data={"email": "teacher@portal.edu.au", "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert b"Invalid email or password." in response.data


def test_login_with_unknown_email_shows_same_error(client):
    response = client.post(
        "/login", data={"email": "nobody@portal.edu.au", "password": PASSWORD}
    )

    assert response.status_code == 401
    assert b"Invalid email or password." in response.data


def test_login_with_empty_fields_is_rejected(client):
    response = client.post("/login", data={"email": "", "password": ""})

    assert response.status_code == 400
    assert b"This field is required." in response.data


def test_login_with_invalid_email_format_is_rejected(client):
    response = client.post(
        "/login", data={"email": "not-an-email", "password": PASSWORD}
    )

    assert response.status_code == 400
    assert b"Invalid email address." in response.data


def test_logged_in_user_opening_login_is_redirected(teacher_client):
    response = teacher_client.get("/login")

    assert response.status_code == 302
    assert response.headers["Location"] == "/teacher/assessments"


def test_anonymous_user_is_redirected_to_login(client):
    response = client.get("/teacher/assessments")

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login")


def test_student_cannot_open_teacher_pages(student_client):
    response = student_client.get("/teacher/assessments")

    assert response.status_code == 403


def test_teacher_cannot_open_student_pages(teacher_client):
    response = teacher_client.get("/student")

    assert response.status_code == 403
