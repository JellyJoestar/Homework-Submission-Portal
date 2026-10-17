"""FR-RUB-01 teacher forms and publication behavior."""
from dataclasses import asdict

import pytest

import views
from rubric import routes
from rubric.models import AssessmentRubric


@pytest.fixture
def rubric_state(monkeypatch):
    state = {
        "assessment": {
            "assessment_id": 7, "title": "Rubric assessment", "description": "Description",
            "criteria": "Additional guidance", "due_date": None, "max_attempts": 1,
            "unit_id": 1, "unit_code": "IFN636", "unit_name": "Software Life Cycle Management",
            "status": "Draft", "allow_late": False,
        },
        "rows": [],
    }

    def read_rubric(assessment_id):
        return AssessmentRubric(assessment_id, state["rows"])

    def create(assessment_id, title, description, weight):
        rubric = read_rubric(assessment_id)
        criterion = rubric.add_criterion(title, description, weight)
        row = asdict(criterion)
        row["criterion_id"] = max((item["criterion_id"] for item in state["rows"]), default=0) + 1
        state["rows"].append(row)
        return row["criterion_id"]

    def update(assessment_id, criterion_id, title, description, weight):
        rubric = read_rubric(assessment_id)
        rubric.update_criterion(criterion_id, title, description, weight)
        state["rows"] = [asdict(item) for item in rubric.criteria]

    def remove(assessment_id, criterion_id):
        rubric = read_rubric(assessment_id)
        rubric.remove_criterion(criterion_id)
        state["rows"] = [asdict(item) for item in rubric.criteria]

    def publish(assessment_id):
        read_rubric(assessment_id).validate_for_publication()
        state["assessment"]["status"] = "Published"

    for module in (views, routes):
        monkeypatch.setattr(module, "get_assessment_by_id", lambda assessment_id: state["assessment"])
        monkeypatch.setattr(module, "get_rubric_by_assessment", read_rubric)
    monkeypatch.setattr(views, "get_resources_by_assessment", lambda assessment_id: [])
    monkeypatch.setattr(views, "publish_assessment_with_rubric", publish)
    monkeypatch.setattr(routes, "create_rubric_criterion", create)
    monkeypatch.setattr(routes, "update_rubric_criterion", update)
    monkeypatch.setattr(routes, "delete_rubric_criterion", remove)
    state["create"] = create
    return state


def form_data(**overrides):
    return {"title": "Analysis", "description": "Explain reasoning.", "weight": "40", **overrides}


def test_ac1_teacher_adds_a_criterion_and_sees_saved_values(teacher_client, rubric_state):
    response = teacher_client.post("/teacher/assessments/7/rubric", data=form_data(), follow_redirects=True)

    assert response.status_code == 200
    assert b"Analysis" in response.data
    assert b"Explain reasoning." in response.data
    assert b"40.00%" in response.data
    assert rubric_state["rows"][0]["assessment_id"] == 7


def test_ac2_edit_form_updates_fields_and_preserves_identity(teacher_client, rubric_state):
    criterion_id = rubric_state["create"](7, "Analysis", "Old description", "40")
    rubric_state["create"](7, "Design", "Other criterion", "60")
    other = rubric_state["rows"][1].copy()
    path = f"/teacher/assessments/7/rubric/{criterion_id}/edit"

    page = teacher_client.get(path)
    response = teacher_client.post(path, data=form_data(title="Updated", description="New description", weight="50"))

    assert page.status_code == 200
    assert b"Old description" in page.data
    assert response.status_code == 302
    assert rubric_state["rows"][0]["title"] == "Updated"
    assert rubric_state["rows"][0]["description"] == "New description"
    assert rubric_state["rows"][0]["criterion_id"] == criterion_id
    assert rubric_state["rows"][0]["assessment_id"] == 7
    assert rubric_state["rows"][1] == other


def test_ac3_removing_one_criterion_keeps_the_other(teacher_client, rubric_state):
    rubric_state["create"](7, "Analysis", "Remove this", "40")
    rubric_state["create"](7, "Design", "Keep this", "60")
    other = rubric_state["rows"][1].copy()

    response = teacher_client.post("/teacher/assessments/7/rubric/1/delete")

    assert response.status_code == 302
    assert rubric_state["rows"] == [other]


@pytest.mark.parametrize("field", ["title", "description", "weight"])
def test_ac4_missing_fields_return_feedback_without_saving(teacher_client, rubric_state, field):
    values = form_data()
    values.pop(field)

    response = teacher_client.post("/teacher/assessments/7/rubric", data=values)

    assert response.status_code == 400
    assert b"This field is required." in response.data
    assert rubric_state["rows"] == []
    assert b"Explain reasoning." in response.data or field == "description"


@pytest.mark.parametrize("weight", ["0", "-1", "100.01", "1.001", "NaN", "not-a-number"])
def test_ac5_invalid_update_returns_feedback_and_preserves_stored_values(teacher_client, rubric_state, weight):
    rubric_state["create"](7, "Analysis", "Original description", "40")
    before = rubric_state["rows"][0].copy()

    response = teacher_client.post("/teacher/assessments/7/rubric/1/edit", data=form_data(weight=weight))

    assert response.status_code == 400
    assert b"Weight must" in response.data
    assert rubric_state["rows"] == [before]


@pytest.mark.parametrize("weights", [[], ["50"], ["60", "60"]])
def test_ac6_invalid_rubric_blocks_publication_with_feedback(teacher_client, rubric_state, weights):
    for weight in weights:
        rubric_state["create"](7, "Analysis", "Description", weight)

    response = teacher_client.post("/teacher/assessments/7/publish")

    assert response.status_code == 400
    assert b"Assessment Could Not Be Published" in response.data
    assert b"at least one" in response.data or b"total 100%" in response.data
    assert rubric_state["assessment"]["status"] == "Draft"


def test_ac6_complete_rubric_allows_publication(teacher_client, rubric_state):
    for weight in ("33.33", "33.33", "33.34"):
        rubric_state["create"](7, "Criterion", "Required description", weight)

    response = teacher_client.post("/teacher/assessments/7/publish")

    assert response.status_code == 302
    assert rubric_state["assessment"]["status"] == "Published"


@pytest.mark.parametrize("status", ["Published", "Closed", "Archived"])
@pytest.mark.parametrize("method,path", [
    ("post", "/teacher/assessments/7/rubric"),
    ("post", "/teacher/assessments/7/rubric/1/edit"),
    ("post", "/teacher/assessments/7/rubric/1/delete"),
    ("get", "/teacher/assessments/7/rubric/1/edit"),
])
def test_ac7_non_draft_rubric_requests_are_rejected_before_mutation(
    teacher_client, rubric_state, monkeypatch, status, method, path,
):
    rubric_state["create"](7, "Analysis", "Original description", "100")
    before = rubric_state["rows"].copy()
    rubric_state["assessment"]["status"] = status
    for name in ("create_rubric_criterion", "update_rubric_criterion", "delete_rubric_criterion"):
        monkeypatch.setattr(routes, name, lambda *args: pytest.fail("locked rubric must not be modified"))

    response = getattr(teacher_client, method)(path, data=form_data())

    assert response.status_code == 400
    assert b"only be changed while the assessment is Draft" in response.data
    assert rubric_state["rows"] == before


@pytest.mark.parametrize("status", ["Published", "Closed", "Archived"])
def test_non_draft_teacher_view_is_read_only(teacher_client, rubric_state, status):
    rubric_state["create"](7, "Analysis", "Original description", "100")
    rubric_state["assessment"]["status"] = status

    response = teacher_client.get("/teacher/assessments/7")

    assert response.status_code == 200
    assert b"Analysis" in response.data and b"100.00%" in response.data
    assert b"read-only" in response.data
    assert b"rubric-criterion-form" not in response.data
    assert b"/rubric/1/edit" not in response.data
    assert b"/rubric/1/delete" not in response.data
