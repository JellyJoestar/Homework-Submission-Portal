"""FR-RUB-03 published display, completed-result projection and latest values."""
from copy import deepcopy
from decimal import Decimal
import pytest
from flask import template_rendered
import db
import views
from conftest import login_as
from rubric.grading import grading_facade
from rubric.models import AssessmentRubric
from test_rubric_grading import grading_state, payload


@pytest.fixture
def student_state(grading_state, monkeypatch):
    state = grading_state
    state["snapshot_calls"] = []
    assessment = dict(assessment_id=7, title="Assessment", description="Requirements", criteria="Guidance",
                      due_date=None, max_attempts=3, allow_late=False, unit_code="IFN636", unit_name="Unit", status="Published")
    state["assessment"] = assessment
    def owned_submission(submission_id, student_id):
        if submission_id == 9 and student_id == 2 and not state["missing"]:
            return dict(deepcopy(state["submission"]), attempt_count=1)
        return None
    def snapshots(student_id, submission_id=None):
        state["snapshot_calls"].append((student_id, submission_id))
        if student_id != 2 or submission_id not in (None, 9) or state["missing"]:
            return {}
        return {9: {
            "submission_id": 9, "assessment_id": 7, "assessment_status": assessment["status"],
            "mark": state["submission"]["mark"], "feedback": state["submission"]["feedback"],
            "criteria": deepcopy(state["criteria"]), "grade_count": len(state["grades"]),
            "grades": [dict(criterion_id=criterion["criterion_id"],
                            mark=state["grades"].get(criterion["criterion_id"], {}).get("mark"),
                            comment=state["grades"].get(criterion["criterion_id"], {}).get("comment"))
                       for criterion in state["criteria"]],
        }}
    monkeypatch.setattr(db, "get_student_grading_snapshots", snapshots)
    monkeypatch.setattr(db, "get_published_rubric_by_assessment", lambda assessment_id:
                        AssessmentRubric(assessment_id, state["criteria"]) if assessment["status"] == "Published" else None)
    monkeypatch.setattr(views, "get_assessment_by_id", lambda assessment_id: assessment if assessment_id == 7 else None)
    monkeypatch.setattr(views, "get_resources_by_assessment", lambda assessment_id: [])
    monkeypatch.setattr(views, "get_submission_by_id", owned_submission)
    monkeypatch.setattr(views, "get_submission_by_assessment_and_student", lambda assessment_id, student_id:
                        owned_submission(9, student_id) if assessment_id == 7 else None)
    monkeypatch.setattr(views, "get_submissions_by_student", lambda student_id:
                        [owned_submission(9, student_id)] if owned_submission(9, student_id) else [])
    return state


@pytest.fixture
def captured_contexts(app):
    contexts = []
    def capture(sender, template, context, **extra):
        contexts.append(context)
    with template_rendered.connected_to(capture, app):
        yield contexts


@pytest.fixture
def grading_teacher(app):
    teacher = app.test_client()
    login_as(teacher, 1)
    return teacher


def test_ac1_ac2_published_assessment_displays_saved_definition(student_client, student_state):
    response = student_client.get("/student/assessments/7")
    assert response.status_code == 200
    for value in (b"Assessment Rubric", b"Analysis", b"Design", b"Evidence", b"40.00%", b"60.00%"):
        assert value in response.data
    assert b"<th scope=\"col\">Actions" not in response.data
    assert b"rubric-criterion-form" not in response.data
    assert b"percentage weights for this assessment" not in response.data


@pytest.mark.parametrize("status", ["Draft", "Closed", "Archived"])
def test_unpublished_assessment_does_not_retrieve_or_display_rubric(student_client, student_state, monkeypatch, status):
    student_state["assessment"]["status"] = status
    monkeypatch.setattr(db, "get_published_rubric_by_assessment", lambda assessment_id: pytest.fail("unavailable rubric read"))
    response = student_client.get("/student/assessments/7")
    assert response.status_code == 403 and b"Evidence" not in response.data


def test_published_historical_assessment_without_rubric_has_no_demo_content(student_client, student_state):
    student_state["criteria"] = []
    response = student_client.get("/student/assessments/7")
    assert response.status_code == 200
    assert b"student-rubric-heading" not in response.data


@pytest.mark.parametrize("path,context_key", [
    ("/student/submissions/9", "submission"), ("/student/results", "results"),
    ("/student/assessments/7", "submission"), ("/student/submissions", "submissions"),
])
def test_ac3_partial_grading_is_removed_before_rendering(student_client, student_state, captured_contexts, path, context_key):
    student_state["submission"].update(mark=Decimal("92.37"), feedback="PRIVATE_UNRELEASED_FEEDBACK")
    student_state["grades"] = {1: dict(submission_id=9, criterion_id=1, mark=Decimal("71.23"), comment="PRIVATE_CRITERION_COMMENT")}
    response = student_client.get(path)
    assert response.status_code == 200
    for secret in (b"92.37", b"71.23", b"PRIVATE_UNRELEASED_FEEDBACK", b"PRIVATE_CRITERION_COMMENT"):
        assert secret not in response.data
    value = captured_contexts[-1][context_key]
    record = value[0] if isinstance(value, list) else value
    assert all(key not in record for key in ("mark", "feedback", "rubric_result", "grades", "criterion_grades", "final_grade"))
    assert student_state["submission"]["mark"] == Decimal("92.37")


def test_ac4_ac5_ac6_complete_grading_updates_and_comments_are_current(student_client, grading_teacher, student_state):
    path = "/teacher/submissions/9/rubric-grading"
    assert b"student-result-heading" not in student_client.get("/student/submissions/9").data
    assert grading_teacher.post(path, json=payload()).status_code == 200
    page = student_client.get("/student/submissions/9")
    for value in (b"Rubric Results", b"80.00", b"90.00", b"86.00", b"Good reasoning", b"40.00%", b"60.00%"):
        assert value in page.data
    assert b"Legacy feedback" not in page.data
    assert grading_teacher.post(path, json=payload(first="50", comment="New criterion comment")).status_code == 200
    page = student_client.get("/student/submissions/9")
    assert b"74.00" in page.data and b"50.00" in page.data and b"New criterion comment" in page.data
    assert b"86.00" not in page.data and b"Good reasoning" not in page.data
    assert grading_teacher.post(path, json=payload(first="50", comment="Updated comment only")).status_code == 200
    page = student_client.get("/student/submissions/9")
    assert b"Updated comment only" in page.data and b"74.00" in page.data
    assert b"New criterion comment" not in page.data
    grading_teacher.post(path, json=payload(first="50", comment=""))
    assert b"Updated comment only" not in student_client.get("/student/submissions/9").data
    assert student_state["submission"]["mark"] == Decimal("74.00")


def test_results_summary_uses_same_gate_and_links_to_completed_breakdown(student_client, grading_teacher, student_state):
    pending = student_client.get("/student/results")
    assert b"Pending" in pending.data and b"View Rubric Results" not in pending.data
    grading_teacher.post("/teacher/submissions/9/rubric-grading", json=payload())
    complete = student_client.get("/student/results")
    assert b"86.00" in complete.data and b"View Rubric Results" in complete.data
    assert b'href="/student/submissions/9"' in complete.data
    assert student_state["snapshot_calls"][-1] == (2, None)


@pytest.mark.parametrize("status", ["Published", "Closed", "Archived"])
def test_complete_results_remain_visible_after_closing_assessment(student_client, grading_teacher, student_state, status):
    grading_teacher.post("/teacher/submissions/9/rubric-grading", json=payload())
    student_state["assessment"]["status"] = status
    assert b"86.00" in student_client.get("/student/submissions/9").data


@pytest.mark.parametrize("bad_state", ["no-final", "stale-final", "invalid-mark", "missing-mark", "extra-grade", "invalid-weights", "draft"])
def test_inconsistent_or_invalid_grading_never_releases_any_criterion(student_client, grading_teacher, student_state, bad_state):
    grading_teacher.post("/teacher/submissions/9/rubric-grading", json=payload(comment="DO_NOT_LEAK"))
    if bad_state == "no-final":
        student_state["submission"]["mark"] = None
    elif bad_state == "stale-final":
        student_state["submission"]["mark"] = Decimal("85.00")
    elif bad_state == "invalid-mark":
        student_state["grades"][1]["mark"] = Decimal("101")
    elif bad_state == "missing-mark":
        student_state["grades"][1]["mark"] = None
    elif bad_state == "extra-grade":
        student_state["grades"][999] = dict(submission_id=9, criterion_id=999, mark=Decimal("90"), comment="Foreign")
    elif bad_state == "invalid-weights":
        student_state["criteria"][0]["weight"] = Decimal("30")
    else:
        student_state["assessment"]["status"] = "Draft"
    page = student_client.get("/student/submissions/9")
    assert page.status_code == 200
    assert b"student-result-heading" not in page.data and b"DO_NOT_LEAK" not in page.data


def test_zero_final_grade_is_complete_and_visible(student_client, grading_teacher, student_state):
    grading_teacher.post("/teacher/submissions/9/rubric-grading", json=payload("0", "0", ""))
    assert b"Final grade:</strong> 0.00" in student_client.get("/student/submissions/9").data
    assert b"Marked" in student_client.get("/student/results").data


def test_projection_uses_current_snapshot_instead_of_stale_submission_mark(grading_teacher, student_state):
    grading_teacher.post("/teacher/submissions/9/rubric-grading", json=payload())
    stale_record = dict(student_state["submission"], mark=Decimal("0"), feedback="Stale feedback")
    current = grading_facade.student_submission(stale_record, 2)
    assert current["mark"] == Decimal("86.00")
    assert current["rubric_result"]["criteria"][0]["mark"] == Decimal("80.00")
    assert "feedback" not in current


def test_read_projection_is_read_only_and_uses_owned_snapshot(student_state):
    student_state["submission"].update(mark=Decimal("92.37"), feedback="Private")
    before = deepcopy(student_state["submission"])
    result = grading_facade.student_submission(student_state["submission"], 2)
    assert "mark" not in result and "feedback" not in result
    assert student_state["submission"] == before
    assert student_state["snapshot_calls"] == [(2, 9)]


def test_legacy_manual_result_is_preserved_and_pending_feedback_hidden(student_client, student_state):
    student_state["criteria"] = []
    pending = student_client.get("/student/results")
    assert b"Legacy feedback" not in pending.data
    student_state["submission"]["mark"] = Decimal("75.00")
    complete = student_client.get("/student/results")
    assert b"75.00" in complete.data and b"Legacy feedback" in complete.data


def test_saved_html_in_rubric_and_comments_is_escaped(student_client, grading_teacher, student_state):
    student_state["criteria"][0]["title"] = "<script>criterion()</script>"
    grading_teacher.post("/teacher/submissions/9/rubric-grading", json=payload(comment="<script>comment()</script>"))
    page = student_client.get("/student/submissions/9")
    assert b"&lt;script&gt;criterion()&lt;/script&gt;" in page.data
    assert b"&lt;script&gt;comment()&lt;/script&gt;" in page.data
    assert b"<script>" not in page.data
