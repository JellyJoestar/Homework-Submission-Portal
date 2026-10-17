"""Complete rubric grading writes for the existing submission review flow."""
from flask import Blueprint, jsonify, redirect, request, url_for
from db import SubmissionNotFoundError
from decorators import teacher_required
from forms import RubricActionForm
from rubric.grading import RubricGradingFacade
from rubric.models import RubricValidationError

grading = Blueprint("grading", __name__)
grading_facade = RubricGradingFacade()


def requested_grades():
    if request.is_json:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raise RubricValidationError({"grading": "Send an object containing the complete grades list."})
        return payload.get("grades")
    return [
        {"criterion_id": criterion_id, "mark": request.form.get(f"mark_{criterion_id}"),
         "comment": request.form.get(f"comment_{criterion_id}", "")}
        for criterion_id in request.form.getlist("criterion_id")
    ]


@grading.route("/teacher/submissions/<int:submission_id>/rubric-grading", methods=["POST"])
@teacher_required
def save_grading(submission_id):
    form = RubricActionForm(data={"csrf_token": request.headers.get("X-CSRFToken")}) if request.is_json else RubricActionForm()
    if not form.validate_on_submit():
        return jsonify(errors={"csrf_token": "Invalid grading action. Reload the page and try again."}), 400
    try:
        result = grading_facade.save(submission_id, requested_grades())
    except SubmissionNotFoundError:
        return "Submission not found.", 404
    except RubricValidationError as error:
        return jsonify(errors=error.errors), 400
    if request.is_json:
        return jsonify(submission_id=submission_id, final_grade=f"{result.final_grade:.2f}")
    return redirect(url_for("views.teacher_submission_details", submission_id=submission_id))
