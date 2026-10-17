"""Rubric persistence boundaries, including the status recheck under a lock."""
import pytest

import db
from rubric.models import RubricNotEditableError


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
