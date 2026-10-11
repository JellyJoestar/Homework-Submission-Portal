"""
Routes that show a preview of a submitted file (FR-PREV-01, NFR-PREV-01).

The submission details pages load these routes inside an iframe.
"""
import os

from flask import Blueprint, make_response
from flask_login import current_user

from db import get_submission_by_id, get_submission_for_teacher
from decorators import student_required, teacher_required
from preview.factory import PreviewFactory
from views import SUBMISSION_UPLOAD_FOLDER

preview = Blueprint("preview", __name__)


def preview_submission_file(submission):
    file_path = os.path.join(SUBMISSION_UPLOAD_FOLDER, submission["stored_filename"])
    if not os.path.exists(file_path):
        return "The submitted file is not available.", 404
    file_preview = PreviewFactory.get_preview(file_path, submission["original_filename"])
    response = make_response(file_preview.render())
    # NFR-PREV-01: content from an uploaded file can never run scripts in the browser
    response.headers["Content-Security-Policy"] = "sandbox"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@preview.route("/student/submissions/<int:submission_id>/preview")
@student_required
def student_preview_submission(submission_id):
    # Only finds the submission if it belongs to the logged-in student
    submission = get_submission_by_id(submission_id, current_user.id)
    if not submission:
        return "Submission not found.", 404
    return preview_submission_file(submission)


@preview.route("/teacher/submissions/<int:submission_id>/preview")
@teacher_required
def teacher_preview_submission(submission_id):
    submission = get_submission_for_teacher(submission_id)
    if not submission:
        return "Submission not found.", 404
    return preview_submission_file(submission)
