"""NFR-RUB-01 HTTP access boundaries and their AC identifiers."""
import pytest
import db
import re
from copy import deepcopy
from conftest import login_as
from test_rubric_configuration import rubric_state


PROTECTED_REQUESTS = [
    ("GET", "/teacher/assessments/7"),
    ("POST", "/teacher/assessments/7/rubric"),
    ("GET", "/teacher/assessments/7/rubric/1/edit"),
    ("POST", "/teacher/assessments/7/rubric/1/edit"),
    ("POST", "/teacher/assessments/7/rubric/1/delete"),
    ("POST", "/teacher/assessments/7/publish"),
    ("GET", "/teacher/assessments/7/submissions"),
    ("GET", "/teacher/submissions/9"),
    ("POST", "/teacher/submissions/9/rubric-grading"),
    ("POST", "/teacher/submissions/9/mark-feedback"),
    ("GET", "/teacher/submissions/9/download"),
    ("GET", "/teacher/submissions/9/preview"),
    ("GET", "/student/assessments/7"),
    ("GET", "/student/assessments/7/resources/1/download"),
    ("POST", "/student/assessments/7/submit"),
    ("GET", "/student/submissions/9"),
    ("GET", "/student/submissions/9/preview"),
    ("GET", "/student/submissions"),
    ("GET", "/student/results"),
]


@pytest.mark.parametrize("method,path", PROTECTED_REQUESTS)
def test_ac1_anonymous_requests_stop_before_accessing_protected_data(client, monkeypatch, method, path):
    monkeypatch.setattr(db, "get_db_connection", lambda: pytest.fail("Anonymous request reached protected data"))
    response = client.open(path, method=method, json={"grades": [{"criterion_id": 1, "mark": "100"}]})
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login")
    assert b"student-result-heading" not in response.data
    assert b"data-grading-criterion-id" not in response.data


@pytest.mark.parametrize("user_id", ["not-a-number", "", "0", "-1", "1.0", None, True, [], "999"])
def test_ac1_invalid_or_expired_user_identity_is_treated_as_anonymous(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    response = client.get("/teacher/submissions/9")
    assert response.status_code == 302 and response.headers["Location"].startswith("/login")


def test_ac1_tampered_unsigned_session_does_not_authenticate(client):
    client.set_cookie("session", "not-a-valid-signed-session")
    response = client.get("/student/results")
    assert response.status_code == 302 and response.headers["Location"].startswith("/login")


RUBRIC_MANAGEMENT_REQUESTS = [
    ("POST", "/teacher/assessments/7/rubric"),
    ("GET", "/teacher/assessments/7/rubric/1/edit"),
    ("POST", "/teacher/assessments/7/rubric/1/edit"),
    ("POST", "/teacher/assessments/7/rubric/1/delete"),
    ("POST", "/teacher/assessments/7/publish"),
]


@pytest.mark.parametrize("method,path", RUBRIC_MANAGEMENT_REQUESTS)
def test_ac2_ac5_student_direct_rubric_requests_preserve_existing_records(student_client, rubric_state, method, path):
    rubric_state["create"](7, "Saved criterion", "Saved description", "100")
    before = deepcopy(rubric_state["rows"])
    response = student_client.open(path, method=method, data={
        "title": "Unauthorized change", "description": "Unauthorized change", "weight": "50",
    })
    assert response.status_code == 403
    assert rubric_state["rows"] == before
    assert b"Saved description" not in response.data


def authenticated_client_with_csrf(app, user_id):
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()
    page = client.get("/login")
    token = re.search(rb'name="csrf_token" type="hidden" value="([^"]+)"', page.data).group(1).decode()
    login_as(client, user_id)
    return client, token


def test_ac2_ac5_valid_student_csrf_and_forged_role_fields_do_not_grant_teacher_access(app, rubric_state):
    client, token = authenticated_client_with_csrf(app, 2)
    response = client.post("/teacher/assessments/7/rubric", data={
        "title": "Unauthorized", "description": "Unauthorized", "weight": "100",
        "csrf_token": token, "role": "Teacher", "user_id": "1", "teacher_id": "1",
    }, headers={"X-Role": "Teacher", "X-User-ID": "1"})
    assert response.status_code == 403 and rubric_state["rows"] == []


def test_ac2_teacher_can_still_create_edit_and_delete_with_valid_csrf(app, rubric_state):
    client, token = authenticated_client_with_csrf(app, 1)
    values = dict(title="Criterion", description="Required description", weight="100", csrf_token=token)
    assert client.post("/teacher/assessments/7/rubric", data=values).status_code == 302
    assert len(rubric_state["rows"]) == 1
    assert client.post("/teacher/assessments/7/rubric/1/edit", data={**values, "title": "Updated criterion"}).status_code == 302
    assert rubric_state["rows"][0]["title"] == "Updated criterion"
    assert client.post("/teacher/assessments/7/rubric/1/delete", data={"csrf_token": token}).status_code == 302
    assert rubric_state["rows"] == []


def test_ac2_existing_session_uses_current_database_role_after_demotion(teacher_client, users, rubric_state):
    rubric_state["create"](7, "Criterion", "Required description", "100")
    before = deepcopy(rubric_state["rows"])
    users[1].role = "Student"
    response = teacher_client.post("/teacher/assessments/7/rubric/1/delete")
    assert response.status_code == 403 and rubric_state["rows"] == before
