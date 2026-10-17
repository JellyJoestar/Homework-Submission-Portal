"""Real routes/facade/domain/repository with transactional in-memory SQL doubles."""
from copy import deepcopy
from decimal import Decimal
import re
import pytest
from werkzeug.datastructures import MultiDict
import db
import views
from rubric import grading_routes
from rubric.grading import grading_facade
from rubric.models import AssessmentRubric, RubricValidationError


@pytest.fixture
def grading_state(monkeypatch):
    state = {
        "submission": dict(submission_id=9, assessment_id=7, student_id=2, mark=None, feedback="Legacy feedback",
                           student_name="Sam Student", unit_code="IFN636", unit_name="Software Life Cycle Management",
                           assessment_title="Rubric assessment", original_filename="report.pdf", status="Submitted",
                           submitted_at="2026-10-17 12:00", assessment_status="Published"),
        "criteria": [dict(criterion_id=i, assessment_id=7, title=title, description="Evidence", weight=Decimal(weight))
                     for i, title, weight in [(1, "Analysis", "40"), (2, "Design", "60")]],
        "grades": {}, "connections": [], "missing": False, "fail_on": None,
    }

    class Connection:
        def __init__(self):
            self.snapshot = deepcopy((state["grades"], state["submission"]))
            self.queries, self.result = [], []
            self.committed = self.rolled_back = self.closed = self.cursor_closed = False
            self.rowcount = 1

        def start_transaction(self):
            pass

        def cursor(self, **kwargs):
            return self

        def execute(self, sql, params):
            sql = " ".join(sql.split())
            self.queries.append((sql, params))
            if state["fail_on"] and state["fail_on"] in sql:
                raise RuntimeError("Simulated database failure")
            if sql.startswith("SELECT assessment_id FROM submissions"):
                self.result = [] if state["missing"] or params[0] != 9 else [dict(assessment_id=7)]
            elif sql.startswith("SELECT assessment_id, status FROM assessments"):
                self.result = [dict(assessment_id=7, status=state["submission"]["assessment_status"])]
            elif sql.startswith("SELECT submission_id, assessment_id, mark FROM submissions"):
                self.result = [deepcopy(state["submission"])]
            elif "FROM rubric_criteria" in sql:
                self.result = deepcopy(state["criteria"])
            elif "FROM criterion_grades" in sql:
                self.result = list(deepcopy(state["grades"]).values())
            elif sql.startswith("INSERT INTO criterion_grades"):
                submission_id, criterion_id, mark, comment, *_ = params
                state["grades"][criterion_id] = dict(submission_id=submission_id, criterion_id=criterion_id, mark=mark, comment=comment)
            elif sql.startswith("UPDATE submissions SET mark"):
                state["submission"]["mark"] = params[0]
                if "feedback" in sql:
                    state["submission"]["feedback"] = params[1]
            else:
                raise AssertionError(f"Unexpected query: {sql}")

        def fetchone(self):
            return self.result.pop(0) if self.result else None

        def fetchall(self):
            return self.result

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True
            state["grades"], state["submission"] = deepcopy(self.snapshot)

        def close(self):
            if self.cursor_closed:
                self.closed = True
            else:
                self.cursor_closed = True

    def connect():
        connection = Connection()
        state["connections"].append(connection)
        return connection

    def get_submission(submission_id):
        return deepcopy(state["submission"]) if submission_id == 9 and not state["missing"] else None

    monkeypatch.setattr(db, "get_db_connection", connect)
    monkeypatch.setattr(db, "get_rubric_by_assessment", lambda assessment_id: AssessmentRubric(assessment_id, state["criteria"]))
    monkeypatch.setattr(views, "get_submission_for_teacher", get_submission)
    monkeypatch.setattr(grading_routes, "get_submission_for_teacher", get_submission)
    return state


def payload(first="80", second="90", comment="Good reasoning"):
    return {"grades": [dict(criterion_id=1, mark=first, comment=comment), dict(criterion_id=2, mark=second)]}


def form_values(first="80", second="90", comment="Good reasoning"):
    return MultiDict([("criterion_id", "1"), ("criterion_id", "2"), ("mark_1", first),
                      ("mark_2", second), ("comment_1", comment)])


def test_ac1_ac2_ac3_ac6_save_update_comment_and_reload(teacher_client, grading_state):
    path = "/teacher/submissions/9/rubric-grading"
    response = teacher_client.post(path, json=payload())
    assert response.status_code == 200 and response.json["final_grade"] == "86.00"
    assert grading_state["submission"]["mark"] == Decimal("86.00")
    assert set(grading_state["grades"]) == {1, 2}
    assert all(grade["submission_id"] == 9 for grade in grading_state["grades"].values())
    assert grading_state["submission"]["feedback"] == "Legacy feedback"
    assert teacher_client.post(path, json=payload(first="50")).json["final_grade"] == "74.00"
    assert teacher_client.post(path, json=payload(first="50", comment="Revised comment")).json["final_grade"] == "74.00"
    page = teacher_client.get("/teacher/submissions/9")
    assert b'Revised comment</textarea>' in page.data
    assert b'value="50.00"' in page.data and b"74.00" in page.data
    assert b"/mark-feedback" not in page.data
    assert len(grading_state["grades"]) == 2
    assert teacher_client.post(path, json=payload(first="50", comment="")).json["final_grade"] == "74.00"
    assert grading_state["grades"][1]["comment"] == ""


@pytest.mark.parametrize("bad_payload", [payload(first="100.01"), payload(first="-1"), payload(first="NaN"),
    payload(first="1.001"), payload(first=""), {"grades": payload()["grades"][:1]},
    {"grades": [payload()["grades"][0]] * 2}, {"grades": [dict(criterion_id=999, mark="80")]},
    {}, {"grades": "not a list"}, []])
def test_ac4_ac5_invalid_save_preserves_previous_complete_result(teacher_client, grading_state, bad_payload):
    path = "/teacher/submissions/9/rubric-grading"
    teacher_client.post(path, json=payload())
    before = deepcopy((grading_state["grades"], grading_state["submission"]))
    response = teacher_client.post(path, json=bad_payload)
    assert response.status_code == 400 and response.json["errors"]
    assert (grading_state["grades"], grading_state["submission"]) == before


def test_invalid_form_shows_feedback_and_retains_entered_comments(teacher_client, grading_state):
    response = teacher_client.post("/teacher/submissions/9/rubric-grading", data=form_values(first="101", comment="Keep this input"))
    assert response.status_code == 400
    assert b"Mark must be between 0 and 100." in response.data
    assert b"Keep this input</textarea>" in response.data
    assert grading_state["grades"] == {} and grading_state["submission"]["mark"] is None


def test_form_save_redirects_to_existing_review_and_zero_is_valid(teacher_client, grading_state):
    response = teacher_client.post("/teacher/submissions/9/rubric-grading", data=form_values("0", "0", ""), follow_redirects=True)
    assert response.status_code == 200
    assert b'value="0.00"' in response.data
    assert grading_state["submission"]["mark"] == Decimal("0.00")


def test_csrf_is_enforced_for_forms_and_json_header(teacher_client, grading_state, app):
    app.config["WTF_CSRF_ENABLED"] = True
    path = "/teacher/submissions/9/rubric-grading"
    assert teacher_client.post(path, data=form_values()).status_code == 400
    assert teacher_client.post(path, json=payload()).status_code == 400
    page = teacher_client.get("/teacher/submissions/9")
    token = re.search(rb'name="csrf_token" type="hidden" value="([^"]+)"', page.data).group(1).decode()
    assert teacher_client.post(path, json=payload(), headers={"X-CSRFToken": token}).status_code == 200
    values = form_values()
    values.add("csrf_token", token)
    assert teacher_client.post(path, data=values).status_code == 302


def test_comments_are_escaped_on_reload(teacher_client, grading_state):
    teacher_client.post("/teacher/submissions/9/rubric-grading", json=payload(comment="<script>alert(1)</script>"))
    page = teacher_client.get("/teacher/submissions/9")
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in page.data
    assert b"<script>alert(1)</script>" not in page.data


def test_database_failure_rolls_back_all_marks_and_result(grading_state):
    grading_facade.save(9, payload()["grades"])
    before = deepcopy((grading_state["grades"], grading_state["submission"]))
    grading_state["fail_on"] = "UPDATE submissions"
    with pytest.raises(RuntimeError):
        grading_facade.save(9, payload(first="50")["grades"])
    assert (grading_state["grades"], grading_state["submission"]) == before
    connection = grading_state["connections"][-1]
    assert connection.rolled_back and not connection.committed and connection.closed


def test_lock_order_matches_submission_upload_and_scopes_every_write(grading_state):
    grading_facade.save(9, payload()["grades"])
    connection = grading_state["connections"][-1]
    queries = connection.queries
    assert "FROM assessments" in queries[1][0] and "FOR UPDATE" in queries[1][0]
    assert "FROM submissions" in queries[2][0] and "FOR UPDATE" in queries[2][0]
    assert queries[2][1] == (9, 7)
    assert "FROM rubric_criteria" in queries[3][0] and "FOR UPDATE" in queries[3][0]
    assert all(params[:2] == (9, index) for index, (sql, params) in enumerate(queries[4:6], 1))
    assert queries[-1][1] == (Decimal("86.00"), 9, 7)
    assert connection.committed and connection.closed


def test_unknown_submission_returns_404_without_writes(teacher_client, grading_state):
    response = teacher_client.post("/teacher/submissions/999/rubric-grading", json=payload())
    assert response.status_code == 404 and grading_state["grades"] == {}


def test_draft_assessment_cannot_be_graded(teacher_client, grading_state):
    grading_state["submission"]["assessment_status"] = "Draft"
    response = teacher_client.post("/teacher/submissions/9/rubric-grading", json=payload())
    assert response.status_code == 400 and grading_state["grades"] == {}


def test_manual_endpoint_cannot_overwrite_calculated_result(teacher_client, grading_state):
    teacher_client.post("/teacher/submissions/9/rubric-grading", json=payload())
    response = teacher_client.post("/teacher/submissions/9/mark-feedback", data={"mark": "100", "feedback": "Bypass"})
    assert response.status_code == 400
    assert grading_state["submission"]["mark"] == Decimal("86.00")


def test_legacy_assessment_without_rubric_keeps_manual_review(teacher_client, grading_state):
    grading_state["criteria"] = []
    page = teacher_client.get("/teacher/submissions/9")
    assert b"Mark and Feedback" in page.data and b"Save Rubric Grading" not in page.data
    response = teacher_client.post("/teacher/submissions/9/mark-feedback", data={"mark": "75", "feedback": "Legacy update"})
    assert response.status_code == 302
    assert grading_state["submission"]["mark"] == Decimal("75")
    assert grading_state["submission"]["feedback"] == "Legacy update"
