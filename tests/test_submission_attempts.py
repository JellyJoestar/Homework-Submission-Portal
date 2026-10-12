"""Functional and transaction-double tests for IFN636-104 and IFN636-106."""
import io

import pytest

import db
import views


ASSESSMENT_ID = 7
STUDENT_ID = 2


def assessment(status="Published", max_attempts=3):
    return {
        "assessment_id": ASSESSMENT_ID,
        "status": status,
        "max_attempts": max_attempts,
    }


def upload(filename="answer.pdf", content=b"valid submission"):
    return {"submission_file": (io.BytesIO(content), filename)}


def install_submission_double(monkeypatch, state, max_attempts):
    def save_submission_attempt(
        assessment_id, student_id, original_filename, stored_filename
    ):
        assert assessment_id == ASSESSMENT_ID
        assert student_id == STUDENT_ID
        if (
            state.get("attempt_count", 0) > 0
            and max_attempts != 0
            and state["attempt_count"] >= max_attempts
        ):
            raise db.AttemptLimitReachedError

        replaced_filename = state.get("stored_filename")
        state["submission_id"] = state.get("submission_id", 41)
        state["attempt_count"] = state.get("attempt_count", 0) + 1
        state["original_filename"] = original_filename
        state["stored_filename"] = stored_filename
        return {
            "submission_id": state["submission_id"],
            "attempt_count": state["attempt_count"],
            "replaced_stored_filename": replaced_filename,
        }

    monkeypatch.setattr(views, "save_submission_attempt", save_submission_attempt)


def configure_submission_route(monkeypatch, tmp_path, max_attempts=3):
    monkeypatch.setattr(views, "SUBMISSION_UPLOAD_FOLDER", str(tmp_path))
    monkeypatch.setattr(
        views,
        "get_assessment_by_id",
        lambda assessment_id: assessment(max_attempts=max_attempts),
    )


def test_first_successful_submission_starts_at_attempt_one(
    student_client, monkeypatch, tmp_path
):
    state = {}
    configure_submission_route(monkeypatch, tmp_path)
    install_submission_double(monkeypatch, state, max_attempts=3)

    response = student_client.post(
        f"/student/assessments/{ASSESSMENT_ID}/submit",
        data=upload(),
        content_type="multipart/form-data",
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/student/submissions/41")
    assert state["attempt_count"] == 1
    assert (tmp_path / state["stored_filename"]).read_bytes() == b"valid submission"


def test_repeated_successful_submissions_increment_once_and_replace_current_file(
    student_client, monkeypatch, tmp_path
):
    state = {}
    configure_submission_route(monkeypatch, tmp_path)
    install_submission_double(monkeypatch, state, max_attempts=3)

    first = student_client.post(
        f"/student/assessments/{ASSESSMENT_ID}/submit",
        data=upload("first.pdf", b"first"),
        content_type="multipart/form-data",
    )
    first_stored_filename = state["stored_filename"]
    second = student_client.post(
        f"/student/assessments/{ASSESSMENT_ID}/submit",
        data=upload("second.docx", b"second"),
        content_type="multipart/form-data",
    )

    assert first.status_code == 302
    assert second.status_code == 302
    assert state["attempt_count"] == 2
    assert state["original_filename"] == "second.docx"
    assert not (tmp_path / first_stored_filename).exists()
    assert (tmp_path / state["stored_filename"]).read_bytes() == b"second"


def test_limit_reached_returns_403_without_consuming_attempt_or_replacing_file(
    student_client, monkeypatch, tmp_path
):
    current_filename = "current.pdf"
    (tmp_path / current_filename).write_bytes(b"current valid file")
    state = {
        "submission_id": 41,
        "attempt_count": 2,
        "original_filename": "current.pdf",
        "stored_filename": current_filename,
    }
    configure_submission_route(monkeypatch, tmp_path, max_attempts=2)
    install_submission_double(monkeypatch, state, max_attempts=2)

    response = student_client.post(
        f"/student/assessments/{ASSESSMENT_ID}/submit",
        data=upload("rejected.pdf", b"must be discarded"),
        content_type="multipart/form-data",
    )

    assert response.status_code == 403
    assert b"Maximum submission limit reached" in response.data
    assert state["attempt_count"] == 2
    assert state["stored_filename"] == current_filename
    assert (tmp_path / current_filename).read_bytes() == b"current valid file"
    assert [path.name for path in tmp_path.iterdir()] == [current_filename]


def test_unlimited_assessment_counts_every_success_without_blocking(
    student_client, monkeypatch, tmp_path
):
    state = {}
    configure_submission_route(monkeypatch, tmp_path, max_attempts=0)
    install_submission_double(monkeypatch, state, max_attempts=0)

    responses = [
        student_client.post(
            f"/student/assessments/{ASSESSMENT_ID}/submit",
            data=upload(f"attempt-{number}.pdf", str(number).encode()),
            content_type="multipart/form-data",
        )
        for number in range(1, 5)
    ]

    assert [response.status_code for response in responses] == [302, 302, 302, 302]
    assert state["attempt_count"] == 4
    assert len(list(tmp_path.iterdir())) == 1
    assert (tmp_path / state["stored_filename"]).read_bytes() == b"4"


@pytest.mark.parametrize(
    "data, content_type, expected_message",
    [
        ({}, None, b"No submission file provided."),
        (upload(""), "multipart/form-data", b"No submission file selected."),
        (upload("notes.txt"), "multipart/form-data", b"Only PDF and DOCX"),
    ],
)
def test_invalid_uploads_do_not_call_database_or_create_files(
    student_client,
    monkeypatch,
    tmp_path,
    data,
    content_type,
    expected_message,
):
    configure_submission_route(monkeypatch, tmp_path)
    monkeypatch.setattr(
        views,
        "save_submission_attempt",
        lambda *args: pytest.fail("invalid uploads must not consume attempts"),
    )

    response = student_client.post(
        f"/student/assessments/{ASSESSMENT_ID}/submit",
        data=data,
        content_type=content_type,
    )

    assert response.status_code == 400
    assert expected_message in response.data
    assert list(tmp_path.iterdir()) == []


def test_database_failure_discards_new_file_without_replacing_current_file(
    student_client, monkeypatch, tmp_path
):
    current_filename = "current.pdf"
    (tmp_path / current_filename).write_bytes(b"still current")
    configure_submission_route(monkeypatch, tmp_path)
    monkeypatch.setattr(
        views,
        "save_submission_attempt",
        lambda *args: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        student_client.post(
            f"/student/assessments/{ASSESSMENT_ID}/submit",
            data=upload("new.pdf", b"new"),
            content_type="multipart/form-data",
        )

    assert (tmp_path / current_filename).read_bytes() == b"still current"
    assert [path.name for path in tmp_path.iterdir()] == [current_filename]


def test_unknown_commit_outcome_keeps_new_file_to_protect_possible_reference(
    student_client, monkeypatch, tmp_path
):
    current_filename = "current.pdf"
    (tmp_path / current_filename).write_bytes(b"current")
    configure_submission_route(monkeypatch, tmp_path)
    monkeypatch.setattr(
        views,
        "save_submission_attempt",
        lambda *args: (_ for _ in ()).throw(
            db.SubmissionCommitOutcomeUnknownError("connection lost during commit")
        ),
    )

    with pytest.raises(db.SubmissionCommitOutcomeUnknownError):
        student_client.post(
            f"/student/assessments/{ASSESSMENT_ID}/submit",
            data=upload("new.pdf", b"new"),
            content_type="multipart/form-data",
        )

    files = list(tmp_path.iterdir())
    assert (tmp_path / current_filename).read_bytes() == b"current"
    assert len(files) == 2
    assert any(path.name != current_filename and path.read_bytes() == b"new" for path in files)


def test_anonymous_user_is_redirected_to_login(client):
    path = f"/student/assessments/{ASSESSMENT_ID}/submit"

    anonymous_response = client.post(path, data=upload())

    assert anonymous_response.status_code == 302
    assert "/login" in anonymous_response.headers["Location"]


def test_teacher_user_cannot_submit(teacher_client):
    path = f"/student/assessments/{ASSESSMENT_ID}/submit"

    teacher_response = teacher_client.post(path, data=upload())

    assert teacher_response.status_code == 403


def test_non_published_assessment_remains_forbidden(
    student_client, monkeypatch, tmp_path
):
    monkeypatch.setattr(views, "SUBMISSION_UPLOAD_FOLDER", str(tmp_path))
    monkeypatch.setattr(
        views,
        "get_assessment_by_id",
        lambda assessment_id: assessment(status="Closed"),
    )
    monkeypatch.setattr(
        views,
        "save_submission_attempt",
        lambda *args: pytest.fail("closed assessments must not accept submissions"),
    )

    response = student_client.post(
        f"/student/assessments/{ASSESSMENT_ID}/submit", data=upload()
    )

    assert response.status_code == 403
    assert list(tmp_path.iterdir()) == []


class TransactionCursor:
    def __init__(self, rows, lastrowid=41):
        self.rows = list(rows)
        self.lastrowid = lastrowid
        self.executions = []
        self.closed = False

    def execute(self, query, params=None):
        self.executions.append((" ".join(query.split()), params))

    def fetchone(self):
        return self.rows.pop(0)

    def close(self):
        self.closed = True


class TransactionConnection:
    def __init__(self, rows, lastrowid=41, commit_error=None):
        self.cursor_instance = TransactionCursor(rows, lastrowid=lastrowid)
        self.commit_error = commit_error
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
        if self.commit_error:
            raise self.commit_error
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_database_first_attempt_locks_assessment_and_inserts_count_one(monkeypatch):
    connection = TransactionConnection(
        [{"assessment_id": 7, "status": "Published", "max_attempts": 3}, None]
    )
    monkeypatch.setattr(db, "get_db_connection", lambda: connection)

    result = db.save_submission_attempt(7, 2, "answer.pdf", "new.pdf")

    queries = [query for query, params in connection.cursor_instance.executions]
    assert connection.started
    assert "FROM assessments" in queries[0] and "FOR UPDATE" in queries[0]
    assert "FROM submissions" in queries[1] and "FOR UPDATE" in queries[1]
    assert "INSERT INTO submissions" in queries[2]
    assert "attempt_count" in queries[2]
    assert result == {
        "submission_id": 41,
        "attempt_count": 1,
        "replaced_stored_filename": None,
    }
    assert connection.committed and not connection.rolled_back


def test_database_resubmission_increments_under_lock_and_returns_old_filename(
    monkeypatch,
):
    connection = TransactionConnection(
        [
            {"assessment_id": 7, "status": "Published", "max_attempts": 3},
            {"submission_id": 41, "stored_filename": "old.pdf", "attempt_count": 1},
        ]
    )
    monkeypatch.setattr(db, "get_db_connection", lambda: connection)

    result = db.save_submission_attempt(7, 2, "answer.pdf", "new.pdf")

    update_query = connection.cursor_instance.executions[2][0]
    assert "attempt_count = attempt_count + 1" in update_query
    assert "mark" not in update_query and "feedback" not in update_query
    assert result == {
        "submission_id": 41,
        "attempt_count": 2,
        "replaced_stored_filename": "old.pdf",
    }
    assert connection.committed and not connection.rolled_back


def test_database_limit_rejection_rolls_back_without_update(monkeypatch):
    connection = TransactionConnection(
        [
            {"assessment_id": 7, "status": "Published", "max_attempts": 2},
            {"submission_id": 41, "stored_filename": "old.pdf", "attempt_count": 2},
        ]
    )
    monkeypatch.setattr(db, "get_db_connection", lambda: connection)

    with pytest.raises(db.AttemptLimitReachedError):
        db.save_submission_attempt(7, 2, "answer.pdf", "new.pdf")

    assert len(connection.cursor_instance.executions) == 2
    assert connection.rolled_back and not connection.committed


def test_database_unlimited_resubmission_still_increments(monkeypatch):
    connection = TransactionConnection(
        [
            {"assessment_id": 7, "status": "Published", "max_attempts": 0},
            {"submission_id": 41, "stored_filename": "old.pdf", "attempt_count": 99},
        ]
    )
    monkeypatch.setattr(db, "get_db_connection", lambda: connection)

    result = db.save_submission_attempt(7, 2, "answer.pdf", "new.pdf")

    assert result["attempt_count"] == 100
    assert connection.committed and not connection.rolled_back


def test_database_rechecks_published_status_inside_locked_transaction(monkeypatch):
    connection = TransactionConnection(
        [{"assessment_id": 7, "status": "Closed", "max_attempts": 3}]
    )
    monkeypatch.setattr(db, "get_db_connection", lambda: connection)

    with pytest.raises(db.AssessmentNotPublishedError):
        db.save_submission_attempt(7, 2, "answer.pdf", "new.pdf")

    assert len(connection.cursor_instance.executions) == 1
    assert connection.rolled_back and not connection.committed


def test_database_reports_unknown_commit_outcome(monkeypatch):
    connection = TransactionConnection(
        [{"assessment_id": 7, "status": "Published", "max_attempts": 3}, None],
        commit_error=OSError("connection lost"),
    )
    monkeypatch.setattr(db, "get_db_connection", lambda: connection)

    with pytest.raises(db.SubmissionCommitOutcomeUnknownError):
        db.save_submission_attempt(7, 2, "answer.pdf", "new.pdf")

    assert connection.rolled_back and not connection.committed
