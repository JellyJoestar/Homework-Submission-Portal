"""Student rubric/result read boundaries and single-statement snapshots."""
from decimal import Decimal
import pytest
import db


class ReadCursor:
    def __init__(self, rows, fail=False):
        self.rows, self.fail = rows, fail
        self.queries, self.closed = [], False

    def execute(self, sql, params):
        self.queries.append((" ".join(sql.split()), params))
        if self.fail:
            raise RuntimeError("Read failed")

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True


class ReadConnection:
    def __init__(self, rows, fail=False):
        self.reader, self.closed = ReadCursor(rows, fail), False

    def cursor(self, **kwargs):
        assert kwargs == {"dictionary": True}
        return self.reader

    def close(self):
        self.closed = True


def install(monkeypatch, rows, fail=False):
    connection = ReadConnection(rows, fail)
    monkeypatch.setattr(db, "get_db_connection", lambda: connection)
    return connection


def criterion(criterion_id=1):
    return dict(criterion_id=criterion_id, assessment_id=7, title="Criterion", description="Required description", weight=Decimal("50"))


def result_row(submission_id=9, criterion_id=1, mark="80", comment="Stored comment"):
    return dict(criterion(criterion_id), submission_id=submission_id, assessment_status="Published",
                final_grade=Decimal("85"), feedback="General feedback", grade_count=2,
                awarded_mark=Decimal(mark) if mark is not None else None, comment=comment)


def test_published_rubric_query_enforces_status_and_scopes_assessment(monkeypatch):
    connection = install(monkeypatch, [criterion(1), criterion(2)])
    rubric = db.get_published_rubric_by_assessment(7)
    sql, params = connection.reader.queries[0]
    assert "a.status = 'Published'" in sql and "a.assessment_id = %s" in sql
    assert params == (7,) and len(rubric.criteria) == 2
    assert connection.closed and connection.reader.closed


@pytest.mark.parametrize("rows,expected", [([], None), ([dict(criterion(), criterion_id=None)], 0)])
def test_missing_or_unpublished_rubric_is_distinct_from_legacy_empty_rubric(monkeypatch, rows, expected):
    install(monkeypatch, rows)
    result = db.get_published_rubric_by_assessment(7)
    if expected is None:
        assert result is None
    else:
        assert result.criteria == ()


@pytest.mark.parametrize("submission_id,params", [(None, (2,)), (9, (2, 9))])
def test_result_read_uses_one_statement_with_student_and_optional_submission_filter(monkeypatch, submission_id, params):
    connection = install(monkeypatch, [result_row(criterion_id=1), result_row(criterion_id=2, mark="90", comment=None)])
    snapshots = db.get_student_grading_snapshots(2, submission_id)
    assert len(connection.reader.queries) == 1
    sql, actual = connection.reader.queries[0]
    assert actual == params
    assert "WHERE s.student_id = %s" in sql
    assert ("AND s.submission_id = %s" in sql) == (submission_id is not None)
    assert "g.submission_id = s.submission_id AND g.criterion_id = c.criterion_id" in sql
    assert "s.mark AS final_grade" in sql and "g.mark AS awarded_mark" in sql
    snapshot = snapshots[9]
    assert snapshot["mark"] == Decimal("85") and snapshot["grade_count"] == 2
    assert len(snapshot["criteria"]) == 2 and len(snapshot["grades"]) == 2
    assert snapshot["grades"][1]["comment"] is None
    assert connection.closed and connection.reader.closed


def test_list_read_groups_each_submission_without_mixing_grades(monkeypatch):
    install(monkeypatch, [result_row(9, 1), result_row(10, 2, "90", "Other comment")])
    snapshots = db.get_student_grading_snapshots(2)
    assert set(snapshots) == {9, 10}
    assert snapshots[9]["grades"][0]["criterion_id"] == 1
    assert snapshots[10]["grades"][0]["criterion_id"] == 2
    assert snapshots[9]["grades"][0]["comment"] == "Stored comment"


def test_snapshot_retains_missing_marks_for_completeness_validation(monkeypatch):
    install(monkeypatch, [dict(result_row(mark=None, comment=None), grade_count=0)])
    snapshot = db.get_student_grading_snapshots(2, 9)[9]
    assert snapshot["grade_count"] == 0 and snapshot["grades"][0]["mark"] is None


def test_snapshot_identifies_historical_manual_grading_without_criteria(monkeypatch):
    install(monkeypatch, [dict(result_row(criterion_id=None), grade_count=0)])
    snapshot = db.get_student_grading_snapshots(2, 9)[9]
    assert snapshot["criteria"] == [] and snapshot["grades"] == []
    assert snapshot["mark"] == Decimal("85")


@pytest.mark.parametrize("read", [lambda: db.get_published_rubric_by_assessment(7), lambda: db.get_student_grading_snapshots(2, 9)])
def test_failed_reads_close_cursor_and_connection(monkeypatch, read):
    connection = install(monkeypatch, [], fail=True)
    with pytest.raises(RuntimeError):
        read()
    assert connection.closed and connection.reader.closed
