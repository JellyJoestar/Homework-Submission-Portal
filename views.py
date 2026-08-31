import os
import uuid
from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for
)
from datetime import datetime
from werkzeug.utils import secure_filename
from db import (
    get_all_assessments,
    get_all_units,
    create_assessment,
    get_assessment_by_id,
    update_assessment,
    delete_draft_assessment,
    update_assessment_status,
    get_resources_by_assessment,
    get_resource_by_id,
    create_assessment_resource,
    delete_assessment_resource
)

views = Blueprint("views", __name__)
RESOURCE_UPLOAD_FOLDER = os.path.join(
    os.path.dirname(__file__),
    "uploads",
    "resources"
)

ALLOWED_RESOURCE_EXTENSIONS = {
    "pdf",
    "docx"
}

os.makedirs(
    RESOURCE_UPLOAD_FOLDER,
    exist_ok=True
)

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

def allowed_resource_file(filename):
    return ("." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_RESOURCE_EXTENSIONS)

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
    resources = get_resources_by_assessment(assessment_id)
    return render_template("assessment_details.html", assessment=assessment, resources=resources)


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
    resources = get_resources_by_assessment(assessment_id)
    for resource in resources:
        resource_path = os.path.join(RESOURCE_UPLOAD_FOLDER, resource["stored_filename"])
        if os.path.exists(resource_path):
            os.remove(resource_path)
    delete_draft_assessment(assessment_id)
    return redirect(url_for("views.teacher_assessments"))

@views.route("/teacher/assessments/<int:assessment_id>/publish",methods=["POST"])
def publish_assessment(assessment_id):
    if not teacher_required():
        return "Teacher access required.", 403
    assessment = get_assessment_by_id(assessment_id)
    if not assessment:
        return "Assessment not found!", 404
    if assessment["status"] != "Draft":
        return "Only Draft assessments can be published.", 400
    update_assessment_status(assessment_id, "Draft", "Published")
    return redirect(url_for("views.view_assessment_details", assessment_id=assessment_id))

@views.route("/teacher/assessments/<int:assessment_id>/close", methods=["POST"])
def close_assessment(assessment_id):
    if not teacher_required():
        return "Teacher access required.", 403
    assessment = get_assessment_by_id(assessment_id)
    if not assessment:
        return "Assessment not found!", 404
    if assessment["status"] != "Published":
        return "Only Published assessments can be closed.", 400
    update_assessment_status(assessment_id, "Published", "Closed")
    return redirect(url_for("views.view_assessment_details", assessment_id=assessment_id))


@views.route("/teacher/assessments/<int:assessment_id>/archive", methods=["POST"])
def archive_assessment(assessment_id):
    if not teacher_required():
        return "Teacher access required.", 403
    assessment = get_assessment_by_id(assessment_id)
    if not assessment:
        return "Assessment not found!", 404
    if assessment["status"] != "Closed":
        return "Only Closed assessments can be archived.", 400
    update_assessment_status(assessment_id, "Closed", "Archived")
    return redirect(url_for("views.view_assessment_details", assessment_id=assessment_id))

@views.route("/teacher/assessments/<int:assessment_id>/resources", methods=["POST"])
def upload_assessment_resource(assessment_id):
    if not teacher_required():
        return "Teacher access required.", 403
    assessment = get_assessment_by_id(assessment_id)
    if not assessment:
        return "Assessment not found!", 404
    if assessment["status"] != "Draft":
        return ("Supporting resources can only be changed "
                "while the assessment is Draft.", 400)
    resource_file = request.files.get("resource")
    if not resource_file or not resource_file.filename:
        return "Resource file is required.", 400
    original_filename = secure_filename(resource_file.filename)
    if not original_filename:
        return "Invalid filename.", 400
    if not allowed_resource_file(original_filename):
        return ("Only PDF and DOCX resources are supported.", 400)
    extension = os.path.splitext(original_filename)[1].lower()
    stored_filename = (f"{uuid.uuid4().hex}{extension}")
    resource_path = os.path.join(RESOURCE_UPLOAD_FOLDER, stored_filename)
    resource_file.save(resource_path)
    create_assessment_resource(assessment_id, original_filename, stored_filename)
    return redirect(url_for("views.view_assessment_details", assessment_id=assessment_id))

@views.route("/teacher/assessments/" "<int:assessment_id>/resources/" "<int:resource_id>/download")
def download_assessment_resource(assessment_id,resource_id):
    if not teacher_required():
        return "Teacher access required.", 403
    resource = get_resource_by_id(resource_id)
    if (not resource or resource["assessment_id"] != assessment_id):
        return "Resource not found!", 404
    return send_from_directory(RESOURCE_UPLOAD_FOLDER, resource["stored_filename"], as_attachment=True, download_name=resource["original_filename"])

@views.route("/teacher/assessments/" "<int:assessment_id>/resources/" "<int:resource_id>/delete", methods=["POST"])
def delete_resource(assessment_id,resource_id):
    if not teacher_required():
        return "Teacher access required.", 403
    assessment = get_assessment_by_id(assessment_id)
    if not assessment:
        return "Assessment not found!", 404
    if assessment["status"] != "Draft":
        return ("Supporting resources can only be changed "
                "while the assessment is Draft.", 400)
    resource = get_resource_by_id(resource_id)
    if (not resource or resource["assessment_id"] != assessment_id):
        return "Resource not found!", 404
    resource_path = os.path.join(RESOURCE_UPLOAD_FOLDER, resource["stored_filename"])
    if os.path.exists(resource_path):
        os.remove(resource_path)
    delete_assessment_resource(resource_id, assessment_id)
    return redirect(url_for("views.view_assessment_details",assessment_id=assessment_id))