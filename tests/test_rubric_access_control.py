"""NFR-RUB-01 HTTP access boundaries and their AC identifiers."""
import pytest
import db
import re
from copy import deepcopy
from conftest import login_as
from test_rubric_configuration import rubric_state
from test_rubric_grading import grading_state, payload
from rubric.grading import grading_facade


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
    before = deepcopy((rubric_state["rows"], rubric_state["assessment"]))
    response = student_client.open(path, method=method, data={
        "title": "Unauthorized change", "description": "Unauthorized change", "weight": "50",
    })
    assert response.status_code == 403
    assert (rubric_state["rows"], rubric_state["assessment"]) == before
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


GRADING_REQUESTS = [
    ("GET", "/teacher/submissions/9"),
    ("GET", "/teacher/submissions/9/download"),
    ("GET", "/teacher/submissions/9/preview"),
    ("POST", "/teacher/submissions/9/rubric-grading"),
    ("POST", "/teacher/submissions/9/mark-feedback"),
]


@pytest.mark.parametrize("method,path", GRADING_REQUESTS)
def test_ac3_ac5_student_cannot_read_teacher_review_or_change_saved_grading(student_client, grading_state, method, path):
    grading_facade.save(9, payload(comment="PRIVATE_TEACHER_COMMENT")["grades"])
    before = deepcopy((grading_state["grades"], grading_state["submission"]))
    response = student_client.open(path, method=method, json=payload("100", "100", "Unauthorized"))
    assert response.status_code == 403
    assert b"PRIVATE_TEACHER_COMMENT" not in response.data
    assert (grading_state["grades"], grading_state["submission"]) == before


@pytest.mark.parametrize("encoding", ["form", "json", "legacy"])
def test_ac3_ac5_student_valid_csrf_cannot_override_marks_comments_or_result(app, grading_state, encoding):
    grading_facade.save(9, payload(comment="Protected comment")["grades"])
    before = deepcopy((grading_state["grades"], grading_state["submission"]))
    client, token = authenticated_client_with_csrf(app, 2)
    headers = {"X-Role": "Teacher", "X-User-ID": "1", "X-CSRFToken": token}
    if encoding == "json":
        response = client.post("/teacher/submissions/9/rubric-grading", json={
            **payload("100", "100", "Unauthorized"), "role": "Teacher", "final_grade": "100",
        }, headers=headers)
    elif encoding == "form":
        response = client.post("/teacher/submissions/9/rubric-grading", data={
            "criterion_id": ["1", "2"], "mark_1": "100", "mark_2": "100", "comment_1": "Unauthorized",
            "final_grade": "100", "role": "Teacher", "csrf_token": token,
        }, headers=headers)
    else:
        response = client.post("/teacher/submissions/9/mark-feedback", data={
            "mark": "100", "feedback": "Unauthorized", "csrf_token": token,
        }, headers=headers)
    assert response.status_code == 403
    assert (grading_state["grades"], grading_state["submission"]) == before


def test_ac3_unknown_submission_id_cannot_bypass_student_role_check(student_client, monkeypatch):
    monkeypatch.setattr(db, "get_db_connection", lambda: pytest.fail("Student reached grading persistence"))
    for submission_id in (9, 999):
        response = student_client.post(f"/teacher/submissions/{submission_id}/rubric-grading", json=payload())
        assert response.status_code == 403


def test_ac1_ac5_every_rubric_and_grading_route_is_in_the_access_matrix(app):
    covered = set(PROTECTED_REQUESTS)
    for rule in app.url_map.iter_rules():
        if rule.endpoint.startswith(("rubric.", "grading.")):
            path = str(rule).replace("<int:assessment_id>", "7").replace("<int:criterion_id>", "1").replace("<int:submission_id>", "9")
            for method in rule.methods & {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                assert (method, path) in covered, f"Missing authentication coverage for {method} {path}"


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_ac5_unsupported_http_methods_do_not_modify_grading(student_client, grading_state, method):
    before = deepcopy((grading_state["grades"], grading_state["submission"]))
    response = student_client.open("/teacher/submissions/9/rubric-grading", method=method, json=payload())
    assert response.status_code == 405
    assert (grading_state["grades"], grading_state["submission"]) == before


def test_ac5_method_override_headers_do_not_bypass_role_checks(student_client, rubric_state):
    rubric_state["create"](7, "Criterion", "Required description", "100")
    before = deepcopy(rubric_state["rows"])
    response = student_client.post("/teacher/assessments/7/rubric/1/delete", data={"_method": "DELETE", "role": "Teacher"},
                                   headers={"X-HTTP-Method-Override": "DELETE", "X-Role": "Teacher"})
    assert response.status_code == 403 and rubric_state["rows"] == before
