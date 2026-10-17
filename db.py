import os
from contextlib import contextmanager
import mysql.connector
from dotenv import load_dotenv
from models import User
from rubric.models import AssessmentRubric, RubricNotEditableError, RubricValidationError

load_dotenv()


class AssessmentNotFoundError(Exception):
    """Raised when an attempted submission targets a missing assessment."""


class AssessmentNotPublishedError(Exception):
    """Raised when an assessment stops accepting submissions."""


class AttemptLimitReachedError(Exception):
    """Raised when a successful submission would exceed max_attempts."""


class SubmissionAlreadyGradedError(Exception):
    """Raised when legacy grading has awarded a mark to the submission."""


class SubmissionCommitOutcomeUnknownError(Exception):
    """Raised when MySQL may have committed despite a connection failure."""

def get_db_connection():
    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        time_zone="+10:00",  # Brisbane, no daylight saving
    )

    return connection

def get_all_assessments():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            a.assessment_id,
            a.title,
            a.description,
            a.due_date,
            a.max_attempts,
            a.status,
            a.allow_late,
            a.unit_id,
            u.unit_code,
            u.unit_name
        FROM assessments a
        JOIN units u
            ON a.unit_id = u.unit_id
        """
    )
    assessments = cursor.fetchall()
    cursor.close()
    connection.close()
    return assessments

def get_assessment_by_id(assessment_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            a.assessment_id,
            a.title,
            a.description,
            a.criteria,
            a.due_date,
            a.max_attempts,
            a.status,
            a.allow_late,
            a.unit_id,
            u.unit_code,
            u.unit_name
        FROM assessments a
        JOIN units u
            ON a.unit_id = u.unit_id
        WHERE a.assessment_id = %s
        """,
        (assessment_id,)
    )
    assessment = cursor.fetchone()
    cursor.close()
    connection.close()
    return assessment

def get_published_assessments():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            a.assessment_id,
            a.title,
            a.description,
            a.criteria,
            a.due_date,
            a.max_attempts,
            a.status,
            a.allow_late,
            a.unit_id,
            u.unit_code,
            u.unit_name
        FROM assessments a
        JOIN units u
            ON a.unit_id = u.unit_id
        WHERE a.status = 'Published'
        ORDER BY a.assessment_id DESC
        """
    )
    assessments = cursor.fetchall()
    cursor.close()
    connection.close()
    return assessments

def get_all_units():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            u.unit_id,
            u.unit_code,
            u.unit_name
        FROM units u
        ORDER BY u.unit_code
        """
    )
    units = cursor.fetchall()
    cursor.close()
    connection.close()
    return units

def create_assessment(title, description, criteria, due_date, unit_id, max_attempts, allow_late=False):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO assessments (
            title, description, criteria, due_date, unit_id, max_attempts, allow_late)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (title, description, criteria, due_date, unit_id, max_attempts, allow_late)
    )
    connection.commit()
    cursor.close()
    connection.close()

def update_assessment(
    assessment_id, title, description, criteria, due_date, unit_id, max_attempts, allow_late=False):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE assessments
        SET title = %s,
            description = %s,
            criteria = %s,
            due_date = %s,
            unit_id = %s,
            max_attempts = %s, 
            allow_late = %s
        WHERE assessment_id = %s
        AND status = 'Draft'
        """,
        (
            title,
            description,
            criteria,
            due_date,
            unit_id,
            max_attempts,
            allow_late, 
            assessment_id
        )
    )
    connection.commit()
    cursor.close()
    connection.close()

def delete_draft_assessment(assessment_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        DELETE FROM assessments
        WHERE assessment_id = %s
        AND status = 'Draft'
        """,
        (assessment_id,)
    )
    connection.commit()
    cursor.close()
    connection.close()

def update_assessment_status(assessment_id, current_status, new_status):
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE assessments
        SET status = %s
        WHERE assessment_id = %s
        AND status = %s
        """,
        (new_status, assessment_id, current_status)
    )
    updated_rows = cursor.rowcount

    connection.commit()
    cursor.close()
    connection.close()

    return updated_rows

def get_resources_by_assessment(assessment_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            resource_id,
            assessment_id,
            original_filename,
            stored_filename,
            uploaded_at
        FROM assessment_resources
        WHERE assessment_id = %s
        ORDER BY uploaded_at
        """,
        (assessment_id,)
    )
    resources = cursor.fetchall()
    cursor.close()
    connection.close()
    return resources


def get_resource_by_id(resource_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            resource_id,
            assessment_id,
            original_filename,
            stored_filename,
            uploaded_at
        FROM assessment_resources
        WHERE resource_id = %s
        """,
        (resource_id,)
    )

    resource = cursor.fetchone()
    cursor.close()
    connection.close()
    return resource


def create_assessment_resource(assessment_id, original_filename, stored_filename):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO assessment_resources (
            assessment_id,
            original_filename,
            stored_filename
        )
        VALUES (%s, %s, %s)
        """,
        (assessment_id, original_filename, stored_filename)
    )

    connection.commit()
    cursor.close()
    connection.close()


def delete_assessment_resource(resource_id, assessment_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        DELETE FROM assessment_resources
        WHERE resource_id = %s
        AND assessment_id = %s
        """,
        (resource_id, assessment_id)
    )
    connection.commit()
    cursor.close()
    connection.close()

def save_submission_attempt(
    assessment_id, student_id, original_filename, stored_filename, is_late=False
):
    """Atomically create or replace the student's current submission.

    Locking the assessment row serializes first submissions and resubmissions for
    the same assessment across application instances. The unique submission key
    remains the final database safeguard for one current row per student.
    """
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    committed = False
    try:
        connection.start_transaction()
        cursor.execute(
            """
            SELECT assessment_id, status, max_attempts
            FROM assessments
            WHERE assessment_id = %s
            FOR UPDATE
            """,
            (assessment_id,)
        )
        assessment = cursor.fetchone()
        if not assessment:
            raise AssessmentNotFoundError
        if assessment["status"] != "Published":
            raise AssessmentNotPublishedError

        cursor.execute(
            """
            SELECT submission_id, stored_filename, attempt_count, mark, feedback
            FROM submissions
            WHERE assessment_id = %s
            AND student_id = %s
            FOR UPDATE
            """,
            (assessment_id, student_id)
        )
        submission = cursor.fetchone()

        if submission:
            if submission["mark"] is not None:
                raise SubmissionAlreadyGradedError

            if (
                assessment["max_attempts"] != 0
                and submission["attempt_count"] >= assessment["max_attempts"]
            ):
                raise AttemptLimitReachedError

            next_attempt_count = submission["attempt_count"] + 1
            cursor.execute(
                """
                UPDATE submissions
                SET original_filename = %s,
                    stored_filename = %s,
                    attempt_count = attempt_count + 1,
                    status = 'Submitted',
                    submitted_at = CURRENT_TIMESTAMP,
                    is_late = %s
                WHERE submission_id = %s
                """,
                (original_filename, stored_filename, is_late, submission["submission_id"])
            )
            submission_id = submission["submission_id"]
            replaced_stored_filename = submission["stored_filename"]
        else:
            next_attempt_count = 1
            cursor.execute(
                """
                INSERT INTO submissions (
                    assessment_id,
                    student_id,
                    original_filename,
                    stored_filename,
                    attempt_count,
                    is_late
                )
                VALUES (%s, %s, %s, %s, 1, %s)
                """,
                (assessment_id, student_id, original_filename, stored_filename, is_late)
            )
            submission_id = cursor.lastrowid
            replaced_stored_filename = None

        try:
            connection.commit()
        except Exception as error:
            raise SubmissionCommitOutcomeUnknownError from error
        committed = True
        return {
            "submission_id": submission_id,
            "attempt_count": next_attempt_count,
            "replaced_stored_filename": replaced_stored_filename,
        }
    except Exception:
        if not committed:
            try:
                connection.rollback()
            except Exception:
                pass
        raise
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            connection.close()
        except Exception:
            pass

def get_rubric_by_assessment(assessment_id):
    connection = get_db_connection()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT criterion_id, assessment_id, title, description, weight
            FROM rubric_criteria
            WHERE assessment_id = %s
            ORDER BY criterion_id
            """,
            (assessment_id,),
        )
        return AssessmentRubric(assessment_id, cursor.fetchall())
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


@contextmanager
def _rubric_transaction(assessment_id):
    """Use the assessment row as the shared lock for rubric writes/publication."""
    connection = get_db_connection()
    cursor = None
    try:
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT assessment_id, status FROM assessments
            WHERE assessment_id = %s FOR UPDATE
            """,
            (assessment_id,),
        )
        assessment = cursor.fetchone()
        if assessment is None:
            raise AssessmentNotFoundError
        if assessment["status"] != "Draft":
            raise RubricNotEditableError
        cursor.execute(
            """
            SELECT criterion_id, assessment_id, title, description, weight
            FROM rubric_criteria
            WHERE assessment_id = %s
            ORDER BY criterion_id
            """,
            (assessment_id,),
        )
        rubric = AssessmentRubric(assessment_id, cursor.fetchall())
        yield cursor, assessment, rubric
        connection.commit()
    except Exception:
        try:
            connection.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            connection.close()


def create_rubric_criterion(assessment_id, title, description, weight):
    with _rubric_transaction(assessment_id) as (cursor, assessment, rubric):
        criterion = rubric.add_criterion(title, description, weight)
        cursor.execute(
            """
            INSERT INTO rubric_criteria (assessment_id, title, description, weight)
            VALUES (%s, %s, %s, %s)
            """,
            (assessment_id, criterion.title, criterion.description, criterion.weight),
        )
        return cursor.lastrowid


def update_rubric_criterion(assessment_id, criterion_id, title, description, weight):
    with _rubric_transaction(assessment_id) as (cursor, assessment, rubric):
        criterion = rubric.update_criterion(criterion_id, title, description, weight)
        cursor.execute(
            """
            UPDATE rubric_criteria SET title = %s, description = %s, weight = %s
            WHERE criterion_id = %s AND assessment_id = %s
            """,
            (
                criterion.title, criterion.description, criterion.weight,
                criterion_id, assessment_id,
            ),
        )


def delete_rubric_criterion(assessment_id, criterion_id):
    with _rubric_transaction(assessment_id) as (cursor, assessment, rubric):
        rubric.remove_criterion(criterion_id)
        cursor.execute(
            """
            DELETE FROM rubric_criteria
            WHERE criterion_id = %s AND assessment_id = %s
            """,
            (criterion_id, assessment_id),
        )


def publish_assessment_with_rubric(assessment_id):
    with _rubric_transaction(assessment_id) as (cursor, assessment, rubric):
        rubric.validate_for_publication()
        cursor.execute(
            """
            UPDATE assessments SET status = 'Published'
            WHERE assessment_id = %s AND status = 'Draft'
            """,
            (assessment_id,),
        )


class SubmissionNotFoundError(Exception):
    """The submission requested for grading no longer exists."""


def get_criterion_grades(submission_id):
    connection = get_db_connection()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT submission_id, criterion_id, mark, comment FROM criterion_grades "
            "WHERE submission_id = %s ORDER BY criterion_id",
            (submission_id,),
        )
        return cursor.fetchall()
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


@contextmanager
def grading_transaction(submission_id):
    """Match submission uploads' lock order: assessment, then submission.

    The initial lookup only discovers the parent; both rows are rechecked under
    locks before reading the rubric or writing marks. The shared parent lock also
    prevents rubric edits from racing with grading.
    """
    connection = get_db_connection()
    cursor = None
    try:
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT assessment_id FROM submissions WHERE submission_id = %s", (submission_id,))
        parent = cursor.fetchone()
        if parent is None:
            raise SubmissionNotFoundError
        assessment_id = parent["assessment_id"]
        cursor.execute("SELECT assessment_id, status FROM assessments WHERE assessment_id = %s FOR UPDATE", (assessment_id,))
        assessment = cursor.fetchone()
        if assessment is None:
            raise SubmissionNotFoundError
        if assessment["status"] == "Draft":
            raise RubricValidationError({"grading": "Grading is available after assessment publication."})
        cursor.execute(
            "SELECT submission_id, assessment_id, mark FROM submissions "
            "WHERE submission_id = %s AND assessment_id = %s FOR UPDATE",
            (submission_id, assessment_id),
        )
        submission = cursor.fetchone()
        if submission is None:
            raise SubmissionNotFoundError
        cursor.execute(
            "SELECT criterion_id, assessment_id, title, description, weight "
            "FROM rubric_criteria WHERE assessment_id = %s ORDER BY criterion_id",
            (assessment_id,),
        )
        rubric = AssessmentRubric(assessment_id, cursor.fetchall())
        yield cursor, submission, rubric
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            connection.close()


def store_criterion_grades(cursor, grading):
    """The caller's transaction owns commit/rollback for the complete save."""
    for grade in grading.grades:
        cursor.execute(
            "INSERT INTO criterion_grades (submission_id, criterion_id, mark, comment) "
            "VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE mark = %s, comment = %s",
            (grade.submission_id, grade.criterion_id, grade.mark, grade.comment, grade.mark, grade.comment),
        )


def get_submissions_by_student(student_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            s.submission_id,
            s.assessment_id,
            s.student_id,
            s.original_filename,
            s.stored_filename,
            s.attempt_count,
            s.status,
            s.mark,
            s.feedback,
            s.submitted_at,
            s.is_late,
            a.title AS assessment_title,
            u.unit_code,
            u.unit_name
        FROM submissions s
        JOIN assessments a
            ON s.assessment_id = a.assessment_id
        JOIN units u
            ON a.unit_id = u.unit_id
        WHERE s.student_id = %s
        ORDER BY s.submitted_at DESC
        """,
        (student_id,)
    )

    submissions = cursor.fetchall()
    cursor.close()
    connection.close()
    return submissions

def get_submission_by_id(submission_id, student_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            s.submission_id,
            s.assessment_id,
            s.student_id,
            s.original_filename,
            s.stored_filename,
            s.attempt_count,
            s.status,
            s.mark,
            s.feedback,
            s.submitted_at,
            s.is_late,
            a.title AS assessment_title,
            u.unit_code,
            u.unit_name
        FROM submissions s
        JOIN assessments a
            ON s.assessment_id = a.assessment_id
        JOIN units u
            ON a.unit_id = u.unit_id
        WHERE s.submission_id = %s
        AND s.student_id = %s
        """,
        (submission_id, student_id)
    )

    submission = cursor.fetchone()
    cursor.close()
    connection.close()
    return submission

def get_submissions_by_assessment(assessment_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            s.submission_id,
            s.assessment_id,
            s.student_id,
            s.original_filename,
            s.stored_filename,
            s.attempt_count,
            s.status,
            s.submitted_at,
            s.is_late,
            CONCAT(st.first_name, ' ', st.last_name) AS student_name,
            a.title AS assessment_title,
            u.unit_code,
            u.unit_name
        FROM submissions s
        JOIN users st
            ON s.student_id = st.user_id
        JOIN assessments a
            ON s.assessment_id = a.assessment_id
        JOIN units u
            ON a.unit_id = u.unit_id
        WHERE s.assessment_id = %s
        ORDER BY s.submitted_at DESC
        """,
        (assessment_id,)
    )
    submissions = cursor.fetchall()
    cursor.close()
    connection.close()
    return submissions

def get_submission_for_teacher(submission_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            s.submission_id,
            s.assessment_id,
            s.student_id,
            s.original_filename,
            s.stored_filename,
            s.attempt_count,
            s.status,
            s.mark,
            s.feedback,
            s.submitted_at,
            s.is_late,
            CONCAT(st.first_name, ' ', st.last_name) AS student_name,
            a.title AS assessment_title,
            a.status AS assessment_status,
            u.unit_code,
            u.unit_name
        FROM submissions s
        JOIN users st
            ON s.student_id = st.user_id
        JOIN assessments a
            ON s.assessment_id = a.assessment_id
        JOIN units u
            ON a.unit_id = u.unit_id
        WHERE s.submission_id = %s
        """,
        (submission_id,)
    )
    submission = cursor.fetchone()
    cursor.close()
    connection.close()
    return submission

def update_submission_mark_feedback(submission_id, mark, feedback):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE submissions
        SET
            mark = %s,
            feedback = %s
        WHERE submission_id = %s
        """,
        (mark, feedback, submission_id)
    )
    connection.commit()
    updated_rows = cursor.rowcount
    cursor.close()
    connection.close()
    return updated_rows

def get_submission_by_assessment_and_student(assessment_id, student_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            submission_id,
            assessment_id,
            student_id,
            original_filename,
            stored_filename,
            attempt_count,
            mark,
            status,
            submitted_at
        FROM submissions
        WHERE assessment_id = %s
        AND student_id = %s
        """,
        (assessment_id, student_id)
    )

    submission = cursor.fetchone()
    cursor.close()
    connection.close()
    return submission

def get_user_by_id(user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            user_id,
            email,
            password_hash,
            role,
            first_name,
            last_name,
            created_at
        FROM users
        WHERE user_id = %s
        """,
        (user_id,)
    )
    user = User.from_row(cursor.fetchone())
    cursor.close()
    connection.close()
    return user

def get_user_by_email(email):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            user_id,
            email,
            password_hash,
            role,
            first_name,
            last_name,
            created_at
        FROM users
        WHERE email = %s
        """,
        (email,)
    )
    user = User.from_row(cursor.fetchone())
    cursor.close()
    connection.close()
    return user
