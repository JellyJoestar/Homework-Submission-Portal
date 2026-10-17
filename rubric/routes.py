"""Teacher rubric forms; domain and database functions enforce the save rules."""
from flask import Blueprint, abort, redirect, render_template, request, url_for

from db import (
    AssessmentNotFoundError,
    create_rubric_criterion,
    delete_rubric_criterion,
    get_assessment_by_id,
    get_rubric_by_assessment,
    update_rubric_criterion,
)
from decorators import teacher_required
from forms import RubricActionForm, RubricCriterionForm
from rubric.models import (
    RubricCriterionNotFoundError,
    RubricNotEditableError,
    RubricValidationError,
)
from views import render_teacher_assessment

rubric = Blueprint("rubric", __name__)


def _draft_assessment(assessment_id):
    assessment = get_assessment_by_id(assessment_id)
    if assessment is None:
        abort(404, description="Assessment not found!")
    if assessment["status"] != "Draft":
        abort(400, description="Rubric criteria can only be changed while the assessment is Draft.")
    return assessment


def _add_validation_errors(form, error):
    for name, message in error.errors.items():
        field = getattr(form, name, None)
        if field is not None:
            field.errors = list(field.errors) + [message]


@rubric.route("/teacher/assessments/<int:assessment_id>/rubric", methods=["POST"])
@teacher_required
def add_criterion(assessment_id):
    assessment = _draft_assessment(assessment_id)
    form = RubricCriterionForm()
    if form.validate_on_submit():
        try:
            create_rubric_criterion(
                assessment_id, form.title.data, form.description.data, form.weight.data
            )
        except RubricValidationError as error:
            _add_validation_errors(form, error)
        except RubricNotEditableError:
            return "Rubric criteria can only be changed while the assessment is Draft.", 400
        except AssessmentNotFoundError:
            return "Assessment not found!", 404
        else:
            return redirect(url_for("views.view_assessment_details", assessment_id=assessment_id))
    return render_teacher_assessment(assessment, form), 400


@rubric.route(
    "/teacher/assessments/<int:assessment_id>/rubric/<int:criterion_id>/edit",
    methods=["GET", "POST"],
)
@teacher_required
def edit_criterion(assessment_id, criterion_id):
    assessment = _draft_assessment(assessment_id)
    try:
        criterion = get_rubric_by_assessment(assessment_id).get_criterion(criterion_id)
    except RubricCriterionNotFoundError:
        return "Rubric criterion not found.", 404
    form = RubricCriterionForm(obj=criterion)
    if form.validate_on_submit():
        try:
            update_rubric_criterion(
                assessment_id, criterion_id,
                form.title.data, form.description.data, form.weight.data,
            )
        except RubricValidationError as error:
            _add_validation_errors(form, error)
        except RubricCriterionNotFoundError:
            return "Rubric criterion not found.", 404
        except RubricNotEditableError:
            return "Rubric criteria can only be changed while the assessment is Draft.", 400
        except AssessmentNotFoundError:
            return "Assessment not found!", 404
        else:
            return redirect(url_for("views.view_assessment_details", assessment_id=assessment_id))
    return render_template(
        "edit_rubric_criterion.html", assessment=assessment, criterion=criterion, form=form
    ), (400 if request.method == "POST" else 200)


@rubric.route(
    "/teacher/assessments/<int:assessment_id>/rubric/<int:criterion_id>/delete",
    methods=["POST"],
)
@teacher_required
def remove_criterion(assessment_id, criterion_id):
    _draft_assessment(assessment_id)
    if not RubricActionForm().validate_on_submit():
        return "Invalid rubric action. Please reload the assessment and try again.", 400
    try:
        delete_rubric_criterion(assessment_id, criterion_id)
    except AssessmentNotFoundError:
        return "Assessment not found!", 404
    except RubricCriterionNotFoundError:
        return "Rubric criterion not found.", 404
    except RubricNotEditableError:
        return "Rubric criteria can only be changed while the assessment is Draft.", 400
    return redirect(url_for("views.view_assessment_details", assessment_id=assessment_id))
