"""Rubric persistence boundaries, including the status recheck under a lock."""
import pytest
from decimal import Decimal

import db
from rubric.models import RubricCriterionNotFoundError, RubricNotEditableError, RubricValidationError


class RecordingCursor:
    def __init__(self, assessment, criteria=()):
        self.assessment = assessment
        self.criteria = list(criteria)
        self.executions = []
        self.lastrowid = 41
        self.closed = False

    def execute(self, query, params=None):
        self.executions.append((" ".join(query.split()), params))

    def fetchone(self):
        return self.assessment

    def fetchall(self):
        return self.criteria

    def close(self):
        self.closed = True


class RecordingConnection:
    def __init__(self, assessment, criteria=()):
        self.cursor_instance = RecordingCursor(assessment, criteria)
        self.started = False
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, **kwargs):
        assert kwargs == {"dictionary": True}
        return self.cursor_instance

    def start_transaction(self):
        self.started = True

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


OPERATIONS = [
    lambda: db.create_rubric_criterion(7, "Analysis", "Description", "100"),
    lambda: db.update_rubric_criterion(7, 1, "Analysis", "Description", "100"),
    lambda: db.delete_rubric_criterion(7, 1),
    lambda: db.publish_assessment_with_rubric(7),
]


@pytest.mark.parametrize("status", ["Published", "Closed", "Archived"])
@pytest.mark.parametrize("operation", OPERATIONS, ids=["create", "update", "delete", "publish"])
def test_ac7_locked_database_status_rejects_writes_even_after_an_earlier_draft_read(
    monkeypatch, status, operation,
):
    connection = RecordingConnection({"assessment_id": 7, "status": status})
    monkeypatch.setattr(db, "get_db_connection", lambda: connection)

    with pytest.raises(RubricNotEditableError):
        operation()

    assert connection.started
    assert len(connection.cursor_instance.executions) == 1
    assert "FOR UPDATE" in connection.cursor_instance.executions[0][0]
    assert connection.rolled_back and not connection.committed
    assert connection.closed and connection.cursor_instance.closed


def criterion_row(criterion_id=1, weight="100"):
    return {
        "criterion_id": criterion_id, "assessment_id": 7,
        "title": "Analysis", "description": "Explain reasoning.", "weight": Decimal(weight),
    }


@pytest.mark.parametrize("operation", OPERATIONS, ids=["create", "update", "delete", "publish"])
def test_missing_assessment_rolls_back_and_releases_resources(monkeypatch, operation):
    connection = RecordingConnection(None)
    monkeypatch.setattr(db, "get_db_connection", lambda: connection)

    with pytest.raises(db.AssessmentNotFoundError):
        operation()

    assert len(connection.cursor_instance.executions) == 1
    assert connection.rolled_back and not connection.committed
    assert connection.closed and connection.cursor_instance.closed


def test_ac1_insert_is_scoped_to_the_assessment_and_commits(monkeypatch):
    connection = RecordingConnection({"assessment_id": 7, "status": "Draft"})
    monkeypatch.setattr(db, "get_db_connection", lambda: connection)

    criterion_id = db.create_rubric_criterion(7, "Analysis", "Explain reasoning.", "33.33")

    query, params = connection.cursor_instance.executions[-1]
    assert "INSERT INTO rubric_criteria" in query
    assert params == (7, "Analysis", "Explain reasoning.", Decimal("33.33"))
    assert criterion_id == 41
    assert connection.committed and not connection.rolled_back


@pytest.mark.parametrize("operation,expected_parameters", [
    (lambda: db.update_rubric_criterion(7, 1, "Updated", "New description", "40"),
     ("Updated", "New description", Decimal("40.00"), 1, 7)),
    (lambda: db.delete_rubric_criterion(7, 1), (1, 7)),
])
def test_ac2_ac3_update_and_delete_use_both_ids(monkeypatch, operation, expected_parameters):
    connection = RecordingConnection({"assessment_id": 7, "status": "Draft"}, [criterion_row()])
    monkeypatch.setattr(db, "get_db_connection", lambda: connection)

    operation()

    query, params = connection.cursor_instance.executions[-1]
    assert "WHERE criterion_id = %s AND assessment_id = %s" in query
    assert params == expected_parameters
    assert connection.committed and not connection.rolled_back


@pytest.mark.parametrize("operation", OPERATIONS[1:3], ids=["update", "delete"])
def test_foreign_or_missing_criterion_does_not_generate_a_write(monkeypatch, operation):
    connection = RecordingConnection({"assessment_id": 7, "status": "Draft"}, [criterion_row(2)])
    monkeypatch.setattr(db, "get_db_connection", lambda: connection)

    with pytest.raises(RubricCriterionNotFoundError):
        operation()

    assert len(connection.cursor_instance.executions) == 2
    assert connection.rolled_back and not connection.committed


def test_ac4_ac5_invalid_criterion_rolls_back_without_an_insert(monkeypatch):
    connection = RecordingConnection({"assessment_id": 7, "status": "Draft"})
    monkeypatch.setattr(db, "get_db_connection", lambda: connection)

    with pytest.raises(RubricValidationError):
        db.create_rubric_criterion(7, "", "", "101")

    assert len(connection.cursor_instance.executions) == 2
    assert connection.rolled_back and not connection.committed


@pytest.mark.parametrize("rows", [[], [criterion_row(weight="50")]])
def test_ac6_publication_validation_runs_inside_the_locked_transaction(monkeypatch, rows):
    connection = RecordingConnection({"assessment_id": 7, "status": "Draft"}, rows)
    monkeypatch.setattr(db, "get_db_connection", lambda: connection)

    with pytest.raises(RubricValidationError):
        db.publish_assessment_with_rubric(7)

    assert "FOR UPDATE" in connection.cursor_instance.executions[0][0]
    assert len(connection.cursor_instance.executions) == 2
    assert connection.rolled_back and not connection.committed


def test_ac6_valid_publication_updates_status_and_commits_once(monkeypatch):
    connection = RecordingConnection({"assessment_id": 7, "status": "Draft"}, [criterion_row()])
    monkeypatch.setattr(db, "get_db_connection", lambda: connection)

    db.publish_assessment_with_rubric(7)

    query, params = connection.cursor_instance.executions[-1]
    assert "SET status = 'Published'" in query and "status = 'Draft'" in query
    assert params == (7,)
    assert connection.committed and not connection.rolled_back


def test_database_write_error_rolls_back_and_closes_the_connection(monkeypatch):
    connection = RecordingConnection({"assessment_id": 7, "status": "Draft"})
    execute = connection.cursor_instance.execute

    def fail_insert(query, params=None):
        if "INSERT INTO rubric_criteria" in query:
            raise RuntimeError("database unavailable")
        execute(query, params)

    monkeypatch.setattr(connection.cursor_instance, "execute", fail_insert)
    monkeypatch.setattr(db, "get_db_connection", lambda: connection)

    with pytest.raises(RuntimeError, match="database unavailable"):
        db.create_rubric_criterion(7, "Analysis", "Description", "100")

    assert connection.rolled_back and not connection.committed
    assert connection.closed and connection.cursor_instance.closed
