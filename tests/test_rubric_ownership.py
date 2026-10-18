"""NFR-RUB-01 AC4: student submission, preview and grading ownership."""
from copy import deepcopy
import pytest
import db
import views
from conftest import login_as
from models import User
from preview import routes as preview_routes
from rubric.grading import grading_facade
from test_rubric_grading import grading_state, payload
from test_student_rubric import student_state, captured_contexts


@pytest.fixture
def other_student(app, users):
    users[3] = User(3, "student2@portal.edu.au", users[2].password_hash, "Student", "Other", "Student")
    client = app.test_client()
    login_as(client, 3)
    return client


@pytest.fixture
def ownership_state(student_state, monkeypatch):
    student_state["preview_reads"] = []
    monkeypatch.setattr(preview_routes, "get_submission_by_id", views.get_submission_by_id)
    def preview(submission):
        student_state["preview_reads"].append(submission["submission_id"])
        return "Owned submission file", 200
    monkeypatch.setattr(preview_routes, "preview_submission_file", preview)
    grading_facade.save(9, payload(comment="PRIVATE_OWNER_COMMENT")["grades"])
    return student_state


@pytest.mark.parametrize("path", ["/student/submissions/9", "/student/submissions/9/preview"])
@pytest.mark.parametrize("query", ["", "?student_id=2&user_id=2&role=Teacher"])
def test_ac4_other_student_cannot_read_submission_or_preview(other_student, ownership_state, path, query):
    response = other_student.get(path + query, headers={"X-User-ID": "2", "X-Role": "Teacher"})
    assert response.status_code == 404
    assert b"PRIVATE_OWNER_COMMENT" not in response.data and b"report.pdf" not in response.data
    assert ownership_state["snapshot_calls"] == [] and ownership_state["preview_reads"] == []


@pytest.mark.parametrize("path", ["/student/submissions", "/student/results"])
def test_ac4_other_students_lists_do_not_include_owner_data(other_student, ownership_state, path):
    response = other_student.get(path + "?student_id=2")
    assert response.status_code == 200
    assert b"report.pdf" not in response.data and b"Rubric assessment" not in response.data
    assert b"PRIVATE_OWNER_COMMENT" not in response.data and b"86.00" not in response.data


def test_ac4_owner_can_still_view_own_submission_grading_and_preview(student_client, ownership_state):
    page = student_client.get("/student/submissions/9")
    assert page.status_code == 200 and b"PRIVATE_OWNER_COMMENT" in page.data
    assert b"86.00" in page.data
    assert student_client.get("/student/submissions/9/preview").status_code == 200
    assert ownership_state["preview_reads"] == [9]


@pytest.mark.parametrize("owner", [3, None])
def test_ac4_facade_rejects_unowned_or_unidentified_metadata_before_reading_grades(ownership_state, owner):
    record = dict(ownership_state["submission"], student_id=owner)
    with pytest.raises(db.SubmissionNotFoundError):
        grading_facade.student_submission(record, 2)
    assert ownership_state["snapshot_calls"] == []
    assert grading_facade.student_results([record], 2) == []
    assert ownership_state["snapshot_calls"] == []


@pytest.mark.parametrize("path", ["/student/submissions/9", "/student/submissions/9/preview", "/student/assessments/7"])
def test_ac4_route_rejects_foreign_metadata_even_if_lookup_returns_it(student_client, ownership_state, monkeypatch, path):
    foreign = dict(ownership_state["submission"], student_id=3, original_filename="PRIVATE_OTHER_FILE.pdf")
    monkeypatch.setattr(views, "get_submission_by_id", lambda *args: foreign)
    monkeypatch.setattr(views, "get_submission_by_assessment_and_student", lambda *args: foreign)
    monkeypatch.setattr(preview_routes, "get_submission_by_id", lambda *args: foreign)
    response = student_client.get(path)
    assert response.status_code == 404
    assert b"PRIVATE_OTHER_FILE.pdf" not in response.data and b"PRIVATE_OWNER_COMMENT" not in response.data
    assert ownership_state["snapshot_calls"] == [] and ownership_state["preview_reads"] == []


@pytest.mark.parametrize("path,context_key", [("/student/submissions", "submissions"), ("/student/results", "results")])
def test_ac4_mixed_repository_rows_are_filtered_before_rendering(student_client, ownership_state, captured_contexts, monkeypatch, path, context_key):
    own = deepcopy(ownership_state["submission"])
    foreign = dict(own, submission_id=99, student_id=3, assessment_title="PRIVATE_OTHER_ASSESSMENT", original_filename="PRIVATE_OTHER_FILE.pdf")
    unknown = dict(foreign, submission_id=100)
    unknown.pop("student_id")
    monkeypatch.setattr(views, "get_submissions_by_student", lambda student_id: [own, foreign, unknown])
    response = student_client.get(path)
    assert response.status_code == 200
    assert b"PRIVATE_OTHER_ASSESSMENT" not in response.data and b"PRIVATE_OTHER_FILE.pdf" not in response.data
    records = captured_contexts[-1][context_key]
    assert len(records) == 1 and records[0]["student_id"] == 2 and records[0]["submission_id"] == 9


def test_ac4_query_parameters_do_not_replace_authenticated_owner(student_client, ownership_state, monkeypatch):
    queried = []
    original = views.get_submission_by_id
    def lookup(submission_id, student_id):
        queried.append((submission_id, student_id))
        return original(submission_id, student_id)
    monkeypatch.setattr(views, "get_submission_by_id", lookup)
    response = student_client.get("/student/submissions/9?student_id=3&user_id=3")
    assert response.status_code == 200
    assert queried == [(9, 2)] and ownership_state["snapshot_calls"] == [(2, 9)]


@pytest.mark.parametrize("read,params,owner_predicate", [
    (lambda: db.get_submission_by_id(9, 2), (9, 2), "s.student_id = %s"),
    (lambda: db.get_submissions_by_student(2), (2,), "s.student_id = %s"),
    (lambda: db.get_submission_by_assessment_and_student(7, 2), (7, 2), "student_id = %s"),
    (lambda: db.get_student_grading_snapshots(2, 9), (2, 9), "s.student_id = %s"),
])
def test_ac4_repository_queries_bind_owner_id(read, params, owner_predicate, monkeypatch):
    class ReadConnection:
        def __init__(self):
            self.queries = []
        def cursor(self, **kwargs):
            return self
        def execute(self, sql, values):
            self.queries.append((" ".join(sql.split()), values))
        def fetchone(self):
            return None
        def fetchall(self):
            return []
        def close(self):
            pass
    connection = ReadConnection()
    monkeypatch.setattr(db, "get_db_connection", lambda: connection)
    read()
    sql, actual = connection.queries[0]
    assert owner_predicate in sql and actual == params
