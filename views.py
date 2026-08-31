from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    session,
    url_for
)
from datetime import datetime
from db import (
    get_all_assessments,
    get_all_units,
    create_assessment,
    get_assessment_by_id,
    update_assessment,
    delete_draft_assessment
)

views = Blueprint("views", __name__)

@views.route("/")
def home():
    return render_template("index.html")


@views.route("/select-role/<role>")
def select_role(role):
    valid_roles = ["Teacher", "Student"]
    if role not in valid_roles:
        return "Invalid role!", 400
    session["role"] = role
    if role == "Teacher":
        return redirect(url_for("views.teacher_assessments"))
    return redirect(url_for("views.student_home"))

def teacher_required():
    return session.get("role") == "Teacher"

@views.route("/student")
def student_home():
    if session.get("role") != "Student":
        return "Student access required.", 403
    return """
        <h1>Student Home</h1>
        <p>Student role selected successfully.</p>
    """

@views.route("/teacher/assessments")
def teacher_assessments():
    if not teacher_required():
        return "Teacher access required.", 403
    assessments = get_all_assessments()
    return render_template("teacher_assessments.html", assessments=assessments)


@views.route("/teacher/assessments/<int:assessment_id>")
def view_assessment_details(assessment_id):
    if not teacher_required():
        return "Teacher access required.", 403
    assessment = get_assessment_by_id(assessment_id)
    if not assessment:
        return "Assessment not found!", 404
    return render_template("assessment_details.html", assessment=assessment)


@views.route("/teacher/assessments/new", methods=["GET"])
def new_assessment_page():
    if not teacher_required():
        return "Teacher access required.", 403
    units = get_all_units()
    return render_template("create_assessment.html", units=units)


@views.route("/teacher/assessments", methods=["POST"])
def create_new_assessment():
    if not teacher_required():
        return "Teacher access required.", 403
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    due_date_raw = request.form.get("due_date") or ""
    unit_id_raw = request.form.get("unit_id")
    if not title:
        return "Title can't be empty!", 400
    try:
        unit_id = int(unit_id_raw)
    except (TypeError, ValueError):
        return "Invalid unit_id!", 400

    valid_unit_ids = [unit["unit_id"] for unit in get_all_units()]

    if unit_id not in valid_unit_ids:
        return "Invalid unit_id!", 400
    if due_date_raw:
        try:
            due_date = datetime.fromisoformat(due_date_raw)
        except ValueError:
            return "Invalid due date!", 400
    else:
        due_date = None
    create_assessment(title, description, due_date, unit_id)
    return redirect(url_for("views.teacher_assessments"))

@views.route("/teacher/assessments/<int:assessment_id>/edit", methods=["GET", "POST"])
def edit_assessment(assessment_id):
    if not teacher_required():
        return "Teacher access required.", 403
    assessment = get_assessment_by_id(assessment_id)
    if not assessment:
        return "Assessment not found!", 404
    if assessment["status"] != "Draft":
        return "Only Draft assessments can be edited.", 400
    units = get_all_units()
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        due_date_raw = request.form.get("due_date") or ""
        unit_id_raw = request.form.get("unit_id")
        if not title:
            return "Title can't be empty!", 400
        try:
            unit_id = int(unit_id_raw)
        except (TypeError, ValueError):
            return "Invalid unit_id!", 400
        valid_unit_ids = [unit["unit_id"] for unit in units]
        if unit_id not in valid_unit_ids:
            return "Invalid unit_id!", 400
        if due_date_raw:
            try:
                due_date = datetime.fromisoformat(due_date_raw)
            except ValueError:
                return "Invalid due date!", 400
        else:
            due_date = None
        update_assessment(assessment_id, title, description, due_date, unit_id)
        return redirect(url_for("views.teacher_assessments"))
    return render_template("edit_assessment.html", assessment=assessment, units=units)

@views.route("/teacher/assessments/<int:assessment_id>/delete", methods=["POST"])
def delete_assessment(assessment_id):
    if not teacher_required():
        return "Teacher access required.", 403
    assessment = get_assessment_by_id(assessment_id)
    if not assessment:
        return "Assessment not found!", 404
    if assessment["status"] != "Draft":
        return "Only Draft assessments can be deleted.", 400
    delete_draft_assessment(assessment_id)
    return redirect(url_for("views.teacher_assessments"))