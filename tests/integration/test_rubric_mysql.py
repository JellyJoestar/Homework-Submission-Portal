"""Opt-in FR-RUB-01 tests against a disposable local/CI MySQL database.

RUBRIC_MYSQL_TESTS=1 enables these tests. Only assessments created by each test
are removed; existing application data is never used as test fixtures.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event
from uuid import uuid4
from pathlib import Path

import pytest

import db
from rubric.models import RubricNotEditableError, RubricValidationError
from rubric.grading import grading_facade
from rubric.grading_models import SubmissionGrading

pytestmark = pytest.mark.skipif(
    os.getenv("RUBRIC_MYSQL_TESTS") != "1",
    reason="requires an explicitly enabled disposable MySQL database",
)


@pytest.fixture
def mysql_assessment():
    created = []

    def create():
        connection = db.get_db_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT unit_id FROM units ORDER BY unit_id LIMIT 1")
            unit_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO assessments (title, description, unit_id) VALUES (%s, %s, %s)",
                (f"Rubric integration {uuid4().hex}", "Disposable test assessment", unit_id),
            )
            assessment_id = cursor.lastrowid
            created.append(assessment_id)
            connection.commit()
            return assessment_id
        finally:
            cursor.close()
            connection.close()

    yield create
    connection = db.get_db_connection()
    cursor = connection.cursor()
    try:
        for assessment_id in created:
            cursor.execute("DELETE FROM assessments WHERE assessment_id = %s", (assessment_id,))
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def test_mysql_ac1_to_ac3_crud_and_ac6_ac7_publication(teacher_client, mysql_assessment):
    assessment_id = mysql_assessment()
    base = f"/teacher/assessments/{assessment_id}"
    for title, weight in (("Analysis", "40"), ("Design", "60")):
        response = teacher_client.post(f"{base}/rubric", data={
            "title": title, "description": f"{title} evidence", "weight": weight,
        })
        assert response.status_code == 302
    initial = db.get_rubric_by_assessment(assessment_id).criteria
    first, other = initial
    response = teacher_client.post(f"{base}/rubric/{first.criterion_id}/edit", data={
        "title": "Revised analysis", "description": "Revised evidence", "weight": "50",
    })
    assert response.status_code == 302
    updated = db.get_rubric_by_assessment(assessment_id).criteria
    assert updated[0].criterion_id == first.criterion_id
    assert updated[0].assessment_id == assessment_id
    assert updated[0].title == "Revised analysis" and updated[0].weight == Decimal("50")
    assert updated[1] == other

    assert teacher_client.post(f"{base}/rubric/{first.criterion_id}/delete").status_code == 302
    assert db.get_rubric_by_assessment(assessment_id).criteria == (other,)
    db.create_rubric_criterion(assessment_id, "Analysis", "Final evidence", "40")
    assert teacher_client.post(f"{base}/publish").status_code == 302
    assert db.get_assessment_by_id(assessment_id)["status"] == "Published"
    before = db.get_rubric_by_assessment(assessment_id).criteria
    for path in (f"{base}/rubric", f"{base}/rubric/{other.criterion_id}/edit", f"{base}/rubric/{other.criterion_id}/delete"):
        assert teacher_client.post(path, data={"title": "Blocked", "description": "Blocked", "weight": "100"}).status_code == 400
    assert db.get_rubric_by_assessment(assessment_id).criteria == before


def test_mysql_ac4_ac5_and_ac6_rejected_changes_are_not_persisted(teacher_client, mysql_assessment):
    assessment_id = mysql_assessment()
    base = f"/teacher/assessments/{assessment_id}"
    assert teacher_client.post(f"{base}/publish").status_code == 400
    criterion_id = db.create_rubric_criterion(assessment_id, "Analysis", "Evidence", "50")
    before = db.get_rubric_by_assessment(assessment_id).criteria
    invalid = [
        {"title": "", "description": "Evidence", "weight": "50"},
        {"title": "Analysis", "description": "", "weight": "50"},
        {"title": "Analysis", "description": "Evidence", "weight": ""},
    ] + [{"title": "Analysis", "description": "Evidence", "weight": weight}
         for weight in ("0", "-1", "100.01", "1.001", "NaN")]
    for values in invalid:
        assert teacher_client.post(f"{base}/rubric/{criterion_id}/edit", data=values).status_code == 400
        assert db.get_rubric_by_assessment(assessment_id).criteria == before
    assert teacher_client.post(f"{base}/publish").status_code == 400
    assert db.get_assessment_by_id(assessment_id)["status"] == "Draft"
    assert db.get_rubric_by_assessment(assessment_id).criteria == before


def test_mysql_criterion_cannot_be_changed_through_another_assessment(teacher_client, mysql_assessment):
    owner_id, other_id = mysql_assessment(), mysql_assessment()
    criterion_id = db.create_rubric_criterion(owner_id, "Analysis", "Evidence", "100")
    before = db.get_rubric_by_assessment(owner_id).criteria
    base = f"/teacher/assessments/{other_id}/rubric/{criterion_id}"

    assert teacher_client.post(f"{base}/edit", data={"title": "Wrong", "description": "Wrong", "weight": "50"}).status_code == 404
    assert teacher_client.post(f"{base}/delete").status_code == 404
    assert db.get_rubric_by_assessment(owner_id).criteria == before


@pytest.mark.parametrize("first_action", ["publish", "change_weight"])
def test_mysql_concurrent_operations_recheck_the_locked_assessment(mysql_assessment, first_action):
    assessment_id = mysql_assessment()
    criterion_id = db.create_rubric_criterion(assessment_id, "Analysis", "Evidence", "100")
    connection = db.get_db_connection()
    cursor = connection.cursor()
    started = Event()

    def second_action():
        started.set()
        if first_action == "publish":
            return db.create_rubric_criterion(assessment_id, "Blocked", "Evidence", "50")
        return db.publish_assessment_with_rubric(assessment_id)

    try:
        connection.start_transaction()
        cursor.execute("SELECT assessment_id FROM assessments WHERE assessment_id = %s FOR UPDATE", (assessment_id,))
        cursor.fetchone()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(second_action)
            try:
                assert started.wait(timeout=5)
                if first_action == "publish":
                    cursor.execute("UPDATE assessments SET status = 'Published' WHERE assessment_id = %s", (assessment_id,))
                    expected_error = RubricNotEditableError
                else:
                    cursor.execute("UPDATE rubric_criteria SET weight = 50 WHERE criterion_id = %s", (criterion_id,))
                    expected_error = RubricValidationError
                connection.commit()
                with pytest.raises(expected_error):
                    future.result(timeout=10)
            finally:
                # Release our lock before waiting for the worker if an assertion fails.
                connection.rollback()
    finally:
        connection.rollback()
        cursor.close()
        connection.close()
    rubric = db.get_rubric_by_assessment(assessment_id)
    assert len(rubric.criteria) == 1
    if first_action == "publish":
        assert db.get_assessment_by_id(assessment_id)["status"] == "Published"
        assert rubric.total_weight == Decimal("100")
    else:
        assert db.get_assessment_by_id(assessment_id)["status"] == "Draft"
        assert rubric.total_weight == Decimal("50")


@pytest.fixture
def mysql_grading_submission(mysql_assessment):
    assessment_id = mysql_assessment()
    criteria = [db.create_rubric_criterion(assessment_id, title, "Evidence", weight)
                for title, weight in (("Analysis", "40"), ("Design", "60"))]
    db.publish_assessment_with_rubric(assessment_id)
    connection = db.get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT user_id FROM users WHERE role = 'Student' ORDER BY user_id LIMIT 1")
        student_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO submissions (assessment_id, student_id, original_filename, stored_filename) "
            "VALUES (%s, %s, %s, %s)", (assessment_id, student_id, "integration.pdf", "integration.pdf"),
        )
        submission_id = cursor.lastrowid
        connection.commit()
    finally:
        cursor.close()
        connection.close()
    return submission_id, assessment_id, student_id, criteria


def mysql_grade_rows(criteria, first="80", second="90", comment="Evidence reviewed"):
    return [dict(criterion_id=criteria[0], mark=first, comment=comment), dict(criterion_id=criteria[1], mark=second)]


def test_mysql_grading_ac1_ac2_ac3_ac6_complete_save_update_and_comment(teacher_client, mysql_grading_submission):
    submission_id, _, _, criteria = mysql_grading_submission
    path = f"/teacher/submissions/{submission_id}/rubric-grading"
    assert teacher_client.post(path, json={"grades": mysql_grade_rows(criteria)}).json["final_grade"] == "86.00"
    first = db.get_criterion_grades(submission_id)
    assert len(first) == 2 and first[0]["submission_id"] == submission_id
    assert teacher_client.post(path, json={"grades": mysql_grade_rows(criteria, first="50")}).json["final_grade"] == "74.00"
    assert teacher_client.post(path, json={"grades": mysql_grade_rows(criteria, first="50", comment="Latest comment")}).json["final_grade"] == "74.00"
    stored = db.get_criterion_grades(submission_id)
    assert len(stored) == 2 and stored[0]["criterion_id"] == criteria[0]
    assert stored[0]["mark"] == Decimal("50.00") and stored[0]["comment"] == "Latest comment"
    assert stored[1]["comment"] == ""
    assert db.get_submission_for_teacher(submission_id)["mark"] == Decimal("74.00")
    page = teacher_client.get(f"/teacher/submissions/{submission_id}")
    assert page.status_code == 200 and b"Latest comment</textarea>" in page.data


@pytest.mark.parametrize("invalid", ["out-of-range", "missing", "foreign", "duplicate"])
def test_mysql_grading_ac4_ac5_invalid_saves_preserve_complete_result(teacher_client, mysql_grading_submission, invalid):
    submission_id, _, _, criteria = mysql_grading_submission
    path = f"/teacher/submissions/{submission_id}/rubric-grading"
    grading_facade.save(submission_id, mysql_grade_rows(criteria))
    before = db.get_criterion_grades(submission_id)
    rows = mysql_grade_rows(criteria)
    if invalid == "out-of-range":
        rows[0]["mark"] = "100.01"
    elif invalid == "missing":
        rows.pop()
    elif invalid == "foreign":
        rows[0]["criterion_id"] = -1
    else:
        rows[1]["criterion_id"] = rows[0]["criterion_id"]
    assert teacher_client.post(path, json={"grades": rows}).status_code == 400
    assert db.get_criterion_grades(submission_id) == before
    assert db.get_submission_for_teacher(submission_id)["mark"] == Decimal("86.00")


@pytest.mark.parametrize("existing", [False, True], ids=["initial-save", "update"])
def test_mysql_grading_failure_rolls_back_marks_and_total(mysql_grading_submission, monkeypatch, existing):
    submission_id, _, _, criteria = mysql_grading_submission
    if existing:
        grading_facade.save(submission_id, mysql_grade_rows(criteria))
    before = db.get_criterion_grades(submission_id)
    previous_mark = db.get_submission_for_teacher(submission_id)["mark"]
    def fail_result(*args):
        raise RuntimeError("Simulated result write failure")
    monkeypatch.setattr(db, "store_rubric_result", fail_result)
    with pytest.raises(RuntimeError):
        grading_facade.save(submission_id, mysql_grade_rows(criteria, first="50"))
    assert db.get_criterion_grades(submission_id) == before
    assert db.get_submission_for_teacher(submission_id)["mark"] == previous_mark


def test_mysql_grading_rejects_an_existing_criterion_from_another_assessment(mysql_grading_submission, mysql_assessment):
    submission_id, _, _, criteria = mysql_grading_submission
    foreign_assessment = mysql_assessment()
    foreign_id = db.create_rubric_criterion(foreign_assessment, "Foreign", "Evidence", "100")
    rows = mysql_grade_rows(criteria)
    rows[0]["criterion_id"] = foreign_id
    with pytest.raises(RubricValidationError):
        grading_facade.save(submission_id, rows)
    assert db.get_criterion_grades(submission_id) == []
    assert db.get_submission_for_teacher(submission_id)["mark"] is None


def test_mysql_completed_zero_grading_blocks_concurrent_resubmission(mysql_grading_submission):
    submission_id, assessment_id, student_id, criteria = mysql_grading_submission
    started = Event()
    def resubmit():
        started.set()
        return db.save_submission_attempt(assessment_id, student_id, "new.pdf", "new.pdf")
    with ThreadPoolExecutor(max_workers=1) as executor:
        with db.grading_transaction(submission_id) as (cursor, submission, rubric):
            future = executor.submit(resubmit)
            assert started.wait(timeout=5)
            grading = SubmissionGrading(submission_id, rubric, mysql_grade_rows(criteria, "0", "0"))
            db.store_criterion_grades(cursor, grading)
            db.store_rubric_result(cursor, grading)
        with pytest.raises(db.SubmissionAlreadyGradedError):
            future.result(timeout=10)
    assert db.get_submission_for_teacher(submission_id)["mark"] == Decimal("0.00")
    assert db.get_submission_for_teacher(submission_id)["original_filename"] == "integration.pdf"
    with pytest.raises(RubricValidationError):
        db.update_submission_mark_feedback(submission_id, Decimal("100"), "Bypass")
    assert db.get_submission_for_teacher(submission_id)["mark"] == Decimal("0.00")


def test_mysql_student_published_rubric_and_latest_complete_result(student_client, mysql_grading_submission):
    submission_id, assessment_id, student_id, criteria = mysql_grading_submission
    rubric = db.get_published_rubric_by_assessment(assessment_id)
    assert {criterion.criterion_id for criterion in rubric.criteria} == set(criteria)
    published = student_client.get(f"/student/assessments/{assessment_id}")
    assert published.status_code == 200 and b"Assessment Rubric" in published.data
    assert b"40.00%" in published.data and b"60.00%" in published.data
    detail_path = f"/student/submissions/{submission_id}"
    assert b"student-result-heading" not in student_client.get(detail_path).data
    grading_facade.save(submission_id, mysql_grade_rows(criteria, comment="Complete criterion feedback"))
    complete = student_client.get(detail_path)
    assert complete.status_code == 200 and b"86.00" in complete.data
    assert b"Complete criterion feedback" in complete.data
    grading_facade.save(submission_id, mysql_grade_rows(criteria, first="50", comment="Updated criterion feedback"))
    revised = student_client.get(detail_path)
    assert b"74.00" in revised.data and b"Updated criterion feedback" in revised.data
    assert b"Complete criterion feedback" not in revised.data
    grading_facade.save(submission_id, mysql_grade_rows(criteria, first="50", comment="Comment-only revision"))
    assert b"Comment-only revision" in student_client.get(detail_path).data
    assert db.get_student_grading_snapshots(student_id, submission_id)[submission_id]["mark"] == Decimal("74.00")


def test_mysql_partial_grading_is_not_sent_to_students(student_client, mysql_grading_submission):
    submission_id, _, _, criteria = mysql_grading_submission
    grading_facade.save(submission_id, mysql_grade_rows(criteria, comment="UNRELEASED_CRITERION_COMMENT"))
    connection = db.get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM criterion_grades WHERE submission_id = %s AND criterion_id = %s", (submission_id, criteria[1]))
        connection.commit()
    finally:
        cursor.close()
        connection.close()
    page = student_client.get(f"/student/submissions/{submission_id}")
    assert page.status_code == 200 and b"student-result-heading" not in page.data
    assert b"UNRELEASED_CRITERION_COMMENT" not in page.data
    assert b"86.00" not in page.data
    summary = student_client.get("/student/results")
    assert b"UNRELEASED_CRITERION_COMMENT" not in summary.data and b"86.00" not in summary.data
    assert db.get_submission_for_teacher(submission_id)["mark"] == Decimal("86.00")


@pytest.mark.parametrize("status", ["Closed", "Archived"])
def test_mysql_non_published_definitions_are_not_returned(mysql_grading_submission, status):
    _, assessment_id, _, _ = mysql_grading_submission
    db.update_assessment_status(assessment_id, "Published", status)
    assert db.get_published_rubric_by_assessment(assessment_id) is None


@pytest.mark.parametrize("operation", ["create", "edit", "delete"])
def test_mysql_nfr_ac2_ac5_student_cannot_mutate_draft_rubric(student_client, mysql_assessment, operation):
    assessment_id = mysql_assessment()
    criterion_id = db.create_rubric_criterion(assessment_id, "Protected criterion", "Protected description", "100")
    before = db.get_rubric_by_assessment(assessment_id).criteria
    path = f"/teacher/assessments/{assessment_id}/rubric"
    if operation != "create":
        path += f"/{criterion_id}/{operation}"
    response = student_client.post(path, data={"title": "Unauthorized", "description": "Unauthorized", "weight": "50"})
    assert response.status_code == 403
    assert db.get_rubric_by_assessment(assessment_id).criteria == before


@pytest.mark.parametrize("encoding", ["json", "form", "legacy"])
def test_mysql_nfr_ac3_ac5_student_cannot_change_stored_grading(student_client, mysql_grading_submission, encoding):
    submission_id, _, _, criteria = mysql_grading_submission
    grading_facade.save(submission_id, mysql_grade_rows(criteria, comment="Protected comment"))
    before = db.get_criterion_grades(submission_id)
    path = f"/teacher/submissions/{submission_id}/rubric-grading"
    if encoding == "json":
        response = student_client.post(path, json={"grades": mysql_grade_rows(criteria, "100", "100", "Unauthorized")})
    elif encoding == "form":
        response = student_client.post(path, data={"criterion_id": list(map(str, criteria)),
            f"mark_{criteria[0]}": "100", f"mark_{criteria[1]}": "100", f"comment_{criteria[0]}": "Unauthorized"})
    else:
        response = student_client.post(f"/teacher/submissions/{submission_id}/mark-feedback", data={"mark": "100", "feedback": "Unauthorized"})
    assert response.status_code == 403
    assert db.get_criterion_grades(submission_id) == before
    assert db.get_submission_for_teacher(submission_id)["mark"] == Decimal("86.00")


def test_mysql_nfr_ac4_another_student_cannot_read_complete_result_or_file(app, users, student_client, mysql_grading_submission, monkeypatch, tmp_path):
    from conftest import login_as
    from preview import routes as preview_routes
    submission_id, _, owner_id, criteria = mysql_grading_submission
    grading_facade.save(submission_id, mysql_grade_rows(criteria, comment="PRIVATE_DATABASE_COMMENT"))
    connection = db.get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT user_id FROM users WHERE role = 'Student' AND user_id <> %s ORDER BY user_id LIMIT 1", (owner_id,))
        other_id = cursor.fetchone()[0]
    finally:
        cursor.close()
        connection.close()
    users[other_id] = db.get_user_by_id(other_id)
    other_client = app.test_client()
    login_as(other_client, other_id)
    monkeypatch.setattr(preview_routes, "SUBMISSION_UPLOAD_FOLDER", str(tmp_path))
    (tmp_path / "integration.pdf").write_bytes((Path(__file__).parents[1] / "files" / "report.pdf").read_bytes())
    detail = f"/student/submissions/{submission_id}"
    own = student_client.get(detail)
    assert own.status_code == 200 and b"PRIVATE_DATABASE_COMMENT" in own.data
    assert student_client.get(detail + "/preview").status_code == 200
    for path in (detail, detail + "/preview"):
        blocked = other_client.get(path + f"?student_id={owner_id}")
        assert blocked.status_code == 404
        assert b"PRIVATE_DATABASE_COMMENT" not in blocked.data and b"%PDF" not in blocked.data
    assert db.get_submission_by_id(submission_id, other_id) is None
    assert db.get_student_grading_snapshots(other_id, submission_id) == {}
