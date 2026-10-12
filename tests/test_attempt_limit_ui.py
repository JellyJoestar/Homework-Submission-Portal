"""Focused Flask/Jinja tests for IFN636-105 student attempt-limit UI."""
import re

import pytest

import views


ASSESSMENT_ID = 7
STUDENT_ID = 2


def assessment(max_attempts=3, status="Published"):
    return {
        "assessment_id": ASSESSMENT_ID,
        "title": "Assessment 2",
        "description": "Description",
        "criteria": "Criteria",
        "due_date": None,
        "unit_id": 1,
        "unit_code": "IFN636",
        "unit_name": "Software Life Cycle Management",
        "status": status,
        "max_attempts": max_attempts,
    }


def submission(attempt_count, student_id=STUDENT_ID, original_filename="latest-answer.pdf"):
    return {
        "submission_id": 41,
        "assessment_id": ASSESSMENT_ID,
        "student_id": student_id,
        "original_filename": original_filename,
        "attempt_count": attempt_count,
    }


def configure_details_route(
    monkeypatch,
    *,
    max_attempts=3,
    attempt_count=None,
    status="Published",
    resources=None,
):
    monkeypatch.setattr(
        views,
        "get_assessment_by_id",
        lambda assessment_id: assessment(max_attempts=max_attempts, status=status),
    )
    monkeypatch.setattr(
        views,
        "get_resources_by_assessment",
        lambda assessment_id: resources or [],
    )
    monkeypatch.setattr(
        views,
        "get_submission_by_assessment_and_student",
        lambda assessment_id, student_id: (
            None if attempt_count is None else submission(attempt_count, student_id)
        ),
    )


def assert_detail_value(response_data, label, value):
    pattern = rb"<strong>" + re.escape(label) + rb"</strong>\s*" + re.escape(value)
    assert re.search(pattern, response_data)


def test_no_submission_displays_zero_of_three_and_three_remaining(
    student_client, monkeypatch
):
    configure_details_route(monkeypatch, max_attempts=3, attempt_count=None)

    response = student_client.get(f"/student/assessments/{ASSESSMENT_ID}")

    assert response.status_code == 200
    assert_detail_value(response.data, b"Attempts:", b"0 of 3")
    assert_detail_value(response.data, b"Remaining attempts:", b"3")
    assert b'class="submission-upload-form"' in response.data


def test_two_of_three_displays_one_remaining_and_allows_upload(
    student_client, monkeypatch
):
    configure_details_route(monkeypatch, max_attempts=3, attempt_count=2)

    response = student_client.get(f"/student/assessments/{ASSESSMENT_ID}")

    assert response.status_code == 200
    assert_detail_value(response.data, b"Attempts:", b"2 of 3")
    assert_detail_value(response.data, b"Remaining attempts:", b"1")
    assert b'name="submission_file"' in response.data
    assert b'accept=".pdf,.docx"' in response.data


def test_existing_submission_displays_latest_filename_and_details_link(
    student_client, monkeypatch
):
    configure_details_route(monkeypatch, max_attempts=3, attempt_count=2)

    response = student_client.get(f"/student/assessments/{ASSESSMENT_ID}")

    assert response.status_code == 200
    assert b"Latest Submission" in response.data
    assert_detail_value(response.data, b"Latest filename:", b"latest-answer.pdf")
    assert b'href="/student/submissions/41"' in response.data
    assert re.search(rb">\s*View Submission\s*</a>", response.data)


def test_no_submission_hides_latest_filename_and_details_link(
    student_client, monkeypatch
):
    configure_details_route(monkeypatch, max_attempts=3, attempt_count=None)

    response = student_client.get(f"/student/assessments/{ASSESSMENT_ID}")

    assert response.status_code == 200
    assert b"Latest Submission" not in response.data
    assert b"Latest filename:" not in response.data
    assert b"View Submission" not in response.data


def test_three_of_three_has_no_functional_upload_and_accessible_warning_dialog(
    student_client, monkeypatch
):
    configure_details_route(monkeypatch, max_attempts=3, attempt_count=3)

    response = student_client.get(f"/student/assessments/{ASSESSMENT_ID}")

    assert response.status_code == 200
    assert_detail_value(response.data, b"Attempts:", b"3 of 3")
    assert_detail_value(response.data, b"Remaining attempts:", b"0")
    assert b"Maximum submission limit reached" in response.data
    assert b'role="alert"' in response.data
    assert b'<dialog' in response.data
    assert b'aria-haspopup="dialog"' in response.data
    assert b"dialog.showModal()" in response.data
    assert b'name="submission_file"' not in response.data
    assert b'class="submission-upload-form"' not in response.data


def test_attempt_count_above_limit_never_displays_negative_remaining(
    student_client, monkeypatch
):
    configure_details_route(monkeypatch, max_attempts=3, attempt_count=5)

    response = student_client.get(f"/student/assessments/{ASSESSMENT_ID}")

    assert response.status_code == 200
    assert_detail_value(response.data, b"Attempts:", b"5 of 3")
    assert_detail_value(response.data, b"Remaining attempts:", b"0")
    assert b'name="submission_file"' not in response.data


def test_unlimited_attempts_show_count_and_never_block_upload(
    student_client, monkeypatch
):
    configure_details_route(monkeypatch, max_attempts=0, attempt_count=5)

    response = student_client.get(f"/student/assessments/{ASSESSMENT_ID}")

    assert response.status_code == 200
    assert_detail_value(response.data, b"Attempts:", "5 — Unlimited".encode())
    assert_detail_value(response.data, b"Remaining attempts:", b"Unlimited")
    assert b'name="submission_file"' in response.data
    assert b"Maximum submission limit reached" not in response.data


def test_route_queries_only_the_logged_in_students_submission(
    student_client, monkeypatch
):
    captured = []
    monkeypatch.setattr(
        views,
        "get_assessment_by_id",
        lambda assessment_id: assessment(max_attempts=3),
    )
    monkeypatch.setattr(views, "get_resources_by_assessment", lambda assessment_id: [])

    def get_own_submission(assessment_id, student_id):
        captured.append((assessment_id, student_id))
        return submission(2, student_id)

    monkeypatch.setattr(
        views, "get_submission_by_assessment_and_student", get_own_submission
    )

    response = student_client.get(f"/student/assessments/{ASSESSMENT_ID}")

    assert response.status_code == 200
    assert captured == [(ASSESSMENT_ID, STUDENT_ID)]
    assert_detail_value(response.data, b"Attempts:", b"2 of 3")


def test_submission_details_link_target_scopes_lookup_to_logged_in_student(
    student_client, monkeypatch
):
    captured = []

    def get_owned_submission(submission_id, student_id):
        captured.append((submission_id, student_id))
        return {
            "submission_id": submission_id,
            "assessment_id": ASSESSMENT_ID,
            "student_id": student_id,
            "original_filename": "latest-answer.pdf",
            "stored_filename": "stored-latest-answer.pdf",
            "attempt_count": 2,
            "status": "Submitted",
            "mark": None,
            "feedback": None,
            "submitted_at": "2026-10-13 10:00:00",
            "assessment_title": "Assessment 2",
            "unit_code": "IFN636",
            "unit_name": "Software Life Cycle Management",
        }

    monkeypatch.setattr(views, "get_submission_by_id", get_owned_submission)

    response = student_client.get("/student/submissions/41")

    assert response.status_code == 200
    assert captured == [(41, STUDENT_ID)]
    assert b"latest-answer.pdf" in response.data


def test_submission_details_link_target_returns_404_for_unowned_submission(
    student_client, monkeypatch
):
    captured = []

    def reject_unowned_submission(submission_id, student_id):
        captured.append((submission_id, student_id))
        return None

    monkeypatch.setattr(views, "get_submission_by_id", reject_unowned_submission)

    response = student_client.get("/student/submissions/99")

    assert response.status_code == 404
    assert captured == [(99, STUDENT_ID)]


@pytest.mark.parametrize(
    "assessment_value, expected_status, expected_message",
    [
        (None, 404, b"Assessment not found!"),
        (assessment(status="Draft"), 403, b"Assessment is not available to students."),
        (assessment(status="Closed"), 403, b"Assessment is not available to students."),
    ],
)
def test_unavailable_assessments_do_not_query_submission_or_render_ui(
    student_client,
    monkeypatch,
    assessment_value,
    expected_status,
    expected_message,
):
    monkeypatch.setattr(
        views, "get_assessment_by_id", lambda assessment_id: assessment_value
    )
    monkeypatch.setattr(
        views,
        "get_resources_by_assessment",
        lambda assessment_id: pytest.fail("unavailable assessment read resources"),
    )
    monkeypatch.setattr(
        views,
        "get_submission_by_assessment_and_student",
        lambda *args: pytest.fail("unavailable assessment read submission"),
    )

    response = student_client.get(f"/student/assessments/{ASSESSMENT_ID}")

    assert response.status_code == expected_status
    assert expected_message in response.data


def test_resource_download_link_and_upload_form_are_preserved_when_available(
    student_client, monkeypatch
):
    resources = [
        {
            "resource_id": 9,
            "assessment_id": ASSESSMENT_ID,
            "original_filename": "brief.pdf",
        }
    ]
    configure_details_route(
        monkeypatch,
        max_attempts=3,
        attempt_count=1,
        resources=resources,
    )

    response = student_client.get(f"/student/assessments/{ASSESSMENT_ID}")

    assert response.status_code == 200
    assert b"brief.pdf" in response.data
    assert (
        b'/student/assessments/7/resources/9/download' in response.data
    )
    assert b'method="POST"' in response.data
    assert b'enctype="multipart/form-data"' in response.data
    assert b'name="submission_file"' in response.data
