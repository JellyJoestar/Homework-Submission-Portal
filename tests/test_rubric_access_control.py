"""NFR-RUB-01 HTTP access boundaries and their AC identifiers."""
import pytest
import db


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
