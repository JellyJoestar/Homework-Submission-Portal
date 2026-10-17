"""Real MySQL concurrency tests for IFN636-111."""

import os

import pytest

import db

from uuid import uuid4

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from concurrent.futures import TimeoutError as FutureTimeoutError
from threading import Event


pytestmark = pytest.mark.skipif(
    os.getenv("SUBMISSION_MYSQL_TESTS") != "1",
    reason="Requires explicit MySQL integration test opt-in",
)


@pytest.fixture(autouse=True)
def require_test_database():
    """Prevent tests from using the development database."""
    assert os.getenv("DB_HOST") in ("127.0.0.1", "localhost")
    assert os.getenv("DB_NAME") == "homework_portal_test"

    connection = db.get_db_connection()
    try:
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT DATABASE()")
            assert cursor.fetchone()[0] == "homework_portal_test"
        finally:
            cursor.close()
    finally:
        connection.close()


def test_mysql_connection():
    """Confirm the isolated test database is accessible."""
    connection = db.get_db_connection()
    try:
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM users")
            assert cursor.fetchone()[0] >= 1
        finally:
            cursor.close()
    finally:
        connection.close()


@pytest.fixture
def seeded_submission():
    """Create and clean up a disposable submission scenario."""
    connection = db.get_db_connection()
    cursor = connection.cursor(dictionary=True)
    assessment_id = None

    try:
        cursor.execute("SELECT DATABASE() AS db_name")
        assert cursor.fetchone()["db_name"] == "homework_portal_test"

        cursor.execute("SELECT unit_id FROM units LIMIT 1")
        unit = cursor.fetchone()

        cursor.execute(
            "SELECT user_id FROM users "
            "WHERE role = 'Student' LIMIT 1"
        )
        student = cursor.fetchone()

        assert unit is not None
        assert student is not None

        cursor.execute(
            """
            INSERT INTO assessments
                (title, description, unit_id, status, max_attempts)
            VALUES (%s, %s, %s, 'Published', 3)
            """,
            (
                f"IFN636-111 test {uuid4().hex}",
                "Disposable concurrency test",
                unit["unit_id"],
            ),
        )
        assessment_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO submissions
                (assessment_id, student_id, original_filename,
                 stored_filename, attempt_count)
            VALUES (%s, %s, %s, %s, 2)
            """,
            (
                assessment_id,
                student["user_id"],
                "original.pdf",
                f"ifn636-111-{uuid4().hex}.pdf",
            ),
        )
        connection.commit()

        yield assessment_id, student["user_id"]

    finally:
        try:
            connection.rollback()
            if assessment_id is not None:
                cursor.execute(
                    "DELETE FROM assessments WHERE assessment_id = %s",
                    (assessment_id,),
                )
                connection.commit()
        finally:
            cursor.close()
            connection.close()


def test_mysql_submission_fixture(seeded_submission):
    assessment_id, student_id = seeded_submission

    submission = db.get_submission_by_assessment_and_student(
        assessment_id, student_id
    )

    assert submission is not None
    assert submission["attempt_count"] == 2
    assert submission["mark"] is None


def test_mysql_concurrent_last_attempt_only_one_succeeds(seeded_submission):
    assessment_id, student_id = seeded_submission

    # Make both workers start their submission attempt together.
    barrier = Barrier(2)

    def submit(label):
        barrier.wait(timeout=5)

        try:
            result = db.save_submission_attempt(
                assessment_id,
                student_id,
                f"answer-{label}.pdf",
                f"stored-{assessment_id}-{label}.pdf",
            )
            return ("success", label, result)

        except db.AttemptLimitReachedError:
            return ("rejected", label, None)

    # Run two real database operations in separate threads.
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(submit, "A"),
            executor.submit(submit, "B"),
        ]
        results = [future.result(timeout=15) for future in futures]

    successes = [r for r in results if r[0] == "success"]
    rejections = [r for r in results if r[0] == "rejected"]

    assert len(successes) == 1
    assert len(rejections) == 1
    assert successes[0][2]["attempt_count"] == 3

    # Verify the final persisted database state.
    submission = db.get_submission_by_assessment_and_student(
        assessment_id, student_id
    )

    winning_label = successes[0][1]

    assert submission["attempt_count"] == 3
    assert submission["original_filename"] == f"answer-{winning_label}.pdf"
    assert submission["stored_filename"] == (
        f"stored-{assessment_id}-{winning_label}.pdf"
    )
    assert submission["mark"] is None


def test_mysql_submission_waits_for_locked_assessment(seeded_submission):
    assessment_id, student_id = seeded_submission

    locker = db.get_db_connection()
    cursor = locker.cursor()
    worker_started = Event()

    try:
        # Connection A: explicitly hold the assessment row lock.
        locker.start_transaction()
        cursor.execute(
            """
            SELECT assessment_id
            FROM assessments
            WHERE assessment_id = %s
            FOR UPDATE
            """,
            (assessment_id,),
        )
        assert cursor.fetchone() is not None

        def submit_while_locked():
            worker_started.set()
            return db.save_submission_attempt(
                assessment_id,
                student_id,
                "locked-test.pdf",
                f"stored-locked-{assessment_id}.pdf",
            )

        # Connection B: attempt submission while A holds the lock.
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(submit_while_locked)

            try:
                assert worker_started.wait(timeout=5)

                # Submission should not complete while A holds the lock.
                with pytest.raises(FutureTimeoutError):
                    future.result(timeout=0.3)

            finally:
                # Always release the lock, even if the assertion fails.
                locker.rollback()

            result = future.result(timeout=10)

        assert result["attempt_count"] == 3

        submission = db.get_submission_by_assessment_and_student(
            assessment_id, student_id
        )

        assert submission["attempt_count"] == 3
        assert submission["original_filename"] == "locked-test.pdf"
        assert submission["stored_filename"] == (
            f"stored-locked-{assessment_id}.pdf"
        )

    finally:
        locker.rollback()
        cursor.close()
        locker.close()