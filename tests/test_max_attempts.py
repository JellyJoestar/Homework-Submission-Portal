"""Focused tests for IFN636-97: assessment maximum attempts."""
from datetime import datetime
import re

import pytest

import db
import views


UNIT = {"unit_id": 1, "unit_code": "IFN636", "unit_name": "Software Life Cycle Management"}


def assessment(status="Draft", max_attempts=1):
    return {
        "assessment_id": 7,
        "title": "Assessment 2",
        "description": "Description",
        "criteria": "Criteria",
        "due_date": datetime(2026, 10, 30, 23, 59),
        "unit_id": 1,
        "unit_code": UNIT["unit_code"],
        "unit_name": UNIT["unit_name"],
        "status": status,
        "max_attempts": max_attempts,
    }


def form_data(max_attempts="1"):
    data = {
        "title": "Assessment 2",
        "description": "Description",
        "criteria": "Criteria",
        "due_date": "2026-10-30T23:59",
        "unit_id": "1",
    }
    if max_attempts is not None:
        data["max_attempts"] = max_attempts
    return data


@pytest.mark.parametrize("raw_value, expected", [("0", 0), ("1", 1), ("2147483647", 2147483647)])
def test_create_accepts_nonnegative_mysql_int_values(
    teacher_client, monkeypatch, raw_value, expected
):
    saved = []
    monkeypatch.setattr(views, "get_all_units", lambda: [UNIT])
    monkeypatch.setattr(views, "create_assessment", lambda *args: saved.append(args))

    response = teacher_client.post(
        "/teacher/assessments", data=form_data(raw_value)
    )

    assert response.status_code == 302
    assert saved[0][-1] == expected


def test_create_defaults_missing_max_attempts_to_one(teacher_client, monkeypatch):
    saved = []
    monkeypatch.setattr(views, "get_all_units", lambda: [UNIT])
    monkeypatch.setattr(views, "create_assessment", lambda *args: saved.append(args))

    response = teacher_client.post(
        "/teacher/assessments", data=form_data(None)
    )

    assert response.status_code == 302
    assert saved[0][-1] == 1


@pytest.mark.parametrize(
    "raw_value",
    ["-1", "1.5", "one", "", "+1", "1e2", "2147483648"],
)
def test_create_rejects_invalid_max_attempts(
    teacher_client, monkeypatch, raw_value
):
    monkeypatch.setattr(views, "get_all_units", lambda: [UNIT])
    monkeypatch.setattr(
        views,
        "create_assessment",
        lambda *args: pytest.fail("invalid input must not be persisted"),
    )

    response = teacher_client.post(
        "/teacher/assessments", data=form_data(raw_value)
    )

    assert response.status_code == 400
    assert b"Maximum attempts must be a non-negative integer." in response.data


def test_edit_persists_max_attempts_for_a_draft(teacher_client, monkeypatch):
    saved = []
    monkeypatch.setattr(views, "get_assessment_by_id", lambda assessment_id: assessment())
    monkeypatch.setattr(views, "get_all_units", lambda: [UNIT])
    monkeypatch.setattr(views, "update_assessment", lambda *args: saved.append(args))

    response = teacher_client.post(
        "/teacher/assessments/7/edit", data=form_data("4")
    )

    assert response.status_code == 302
    assert saved[0][0] == 7
    assert saved[0][-1] == 4


def test_edit_preserves_existing_limit_when_max_attempts_is_missing(
    teacher_client, monkeypatch
):
    saved = []
    monkeypatch.setattr(
        views,
        "get_assessment_by_id",
        lambda assessment_id: assessment(max_attempts=3),
    )
    monkeypatch.setattr(views, "get_all_units", lambda: [UNIT])
    monkeypatch.setattr(views, "update_assessment", lambda *args: saved.append(args))

    response = teacher_client.post(
        "/teacher/assessments/7/edit", data=form_data(None)
    )

    assert response.status_code == 302
    assert saved[0][-1] == 3


def test_edit_rejects_invalid_max_attempts(teacher_client, monkeypatch):
    monkeypatch.setattr(views, "get_assessment_by_id", lambda assessment_id: assessment())
    monkeypatch.setattr(views, "get_all_units", lambda: [UNIT])
    monkeypatch.setattr(
        views,
        "update_assessment",
        lambda *args: pytest.fail("invalid input must not be persisted"),
    )

    response = teacher_client.post(
        "/teacher/assessments/7/edit", data=form_data("-1")
    )

    assert response.status_code == 400
    assert b"Maximum attempts must be a non-negative integer." in response.data


def test_published_assessment_limit_cannot_be_changed(teacher_client, monkeypatch):
    monkeypatch.setattr(
        views,
        "get_assessment_by_id",
        lambda assessment_id: assessment(status="Published"),
    )
    monkeypatch.setattr(
        views,
        "update_assessment",
        lambda *args: pytest.fail("a Published assessment must not be updated"),
    )

    response = teacher_client.post(
        "/teacher/assessments/7/edit", data=form_data("9")
    )

    assert response.status_code == 400
    assert b"Only Draft assessments can be edited." in response.data


def test_create_and_edit_forms_show_max_attempts(teacher_client, monkeypatch):
    monkeypatch.setattr(views, "get_all_units", lambda: [UNIT])
    monkeypatch.setattr(views, "get_assessment_by_id", lambda assessment_id: assessment(max_attempts=5))

    create_response = teacher_client.get("/teacher/assessments/new")
    edit_response = teacher_client.get("/teacher/assessments/7/edit")

    assert create_response.status_code == 200
    assert b"Maximum attempts" in create_response.data
    assert b'name="max_attempts"' in create_response.data
    assert b'value="1"' in create_response.data
    assert edit_response.status_code == 200
    assert b'value="5"' in edit_response.data


def test_teacher_details_display_unlimited(teacher_client, monkeypatch):
    monkeypatch.setattr(views, "get_assessment_by_id", lambda assessment_id: assessment(max_attempts=0))
    monkeypatch.setattr(views, "get_resources_by_assessment", lambda assessment_id: [])

    response = teacher_client.get("/teacher/assessments/7")

    assert response.status_code == 200
    assert b"Maximum attempts:" in response.data
    assert b"Unlimited" in response.data


def test_student_details_display_numeric_limit(student_client, monkeypatch):
    monkeypatch.setattr(
        views,
        "get_assessment_by_id",
        lambda assessment_id: assessment(status="Published", max_attempts=3),
    )
    monkeypatch.setattr(views, "get_resources_by_assessment", lambda assessment_id: [])

    response = student_client.get("/student/assessments/7")

    assert response.status_code == 200
    assert re.search(
        rb"<strong>Maximum attempts:</strong>\s*3\s*</div>", response.data
    )


class RecordingCursor:
    def __init__(self):
        self.query = None
        self.params = None

    def execute(self, query, params=None):
        self.query = query
        self.params = params

    def fetchone(self):
        return {"assessment_id": 7, "max_attempts": 6}

    def close(self):
        pass


class RecordingConnection:
    def __init__(self):
        self.cursor_instance = RecordingCursor()
        self.committed = False

    def cursor(self, **kwargs):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def close(self):
        pass


def test_database_create_persists_max_attempts(monkeypatch):
    connection = RecordingConnection()
    monkeypatch.setattr(db, "get_db_connection", lambda: connection)

    db.create_assessment("Title", "Description", "Criteria", None, 1, 8)

    assert "max_attempts" in connection.cursor_instance.query
    assert connection.cursor_instance.params[-1] == 8
    assert connection.committed


def test_database_read_and_draft_only_update_include_max_attempts(monkeypatch):
    read_connection = RecordingConnection()
    monkeypatch.setattr(db, "get_db_connection", lambda: read_connection)

    result = db.get_assessment_by_id(7)

    assert "a.max_attempts" in read_connection.cursor_instance.query
    assert result["max_attempts"] == 6

    update_connection = RecordingConnection()
    monkeypatch.setattr(db, "get_db_connection", lambda: update_connection)
    db.update_assessment(7, "Title", "Description", "Criteria", None, 1, 9)

    assert "max_attempts = %s" in update_connection.cursor_instance.query
    assert "AND status = 'Draft'" in update_connection.cursor_instance.query
    assert update_connection.cursor_instance.params[-2:] == (9, 7)
    assert update_connection.committed
