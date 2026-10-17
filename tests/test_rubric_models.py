"""FR-RUB-01 domain rules and the rubric's composition relationship."""
from decimal import Decimal

import pytest

from rubric.models import AssessmentRubric, RubricCriterionNotFoundError, RubricValidationError


def criterion_row(criterion_id=1, assessment_id=7, weight="40"):
    return {
        "criterion_id": criterion_id,
        "assessment_id": assessment_id,
        "title": f"Criterion {criterion_id}",
        "description": "Explain the evidence required.",
        "weight": Decimal(weight),
    }


@pytest.mark.parametrize("weight", ["0.01", "33.33", "100", "100.000"])
def test_valid_criterion_is_owned_by_its_rubric(weight):
    rubric = AssessmentRubric(7)
    criterion = rubric.add_criterion("  Analysis  ", "  Explain reasoning.  ", weight)

    assert criterion.assessment_id == 7
    assert criterion.title == "Analysis"
    assert criterion.description == "Explain reasoning."
    assert rubric.criteria == (criterion,)
    assert criterion.weight == Decimal(weight)


@pytest.mark.parametrize("field", ["title", "description", "weight"])
@pytest.mark.parametrize("missing", [None, "", "   "])
def test_each_required_field_rejects_empty_values_without_adding_a_criterion(field, missing):
    rubric = AssessmentRubric(7)
    values = {"title": "Analysis", "description": "Explain reasoning.", "weight": "40"}
    values[field] = missing

    with pytest.raises(RubricValidationError) as error:
        rubric.add_criterion(**values)

    assert field in error.value.errors
    assert rubric.criteria == ()


@pytest.mark.parametrize("weight", ["0", "-1", "100.01", "1.001", "NaN", "sNaN", "Infinity", "abc"])
def test_invalid_weight_does_not_replace_the_current_criterion(weight):
    rubric = AssessmentRubric(7, [criterion_row()])
    before = rubric.criteria

    with pytest.raises(RubricValidationError):
        rubric.update_criterion(1, "Changed", "Changed description", weight)

    assert rubric.criteria == before


def test_update_preserves_identity_and_other_criteria_then_delete_is_scoped():
    rubric = AssessmentRubric(7, [criterion_row(), criterion_row(2, weight="60")])
    unaffected = rubric.criteria[1]

    updated = rubric.update_criterion(1, "Updated", "New description", "50")

    assert updated.criterion_id == 1
    assert updated.assessment_id == 7
    assert updated.weight == Decimal("50.00")
    assert rubric.criteria[1] == unaffected

    rubric.remove_criterion(1)
    assert rubric.criteria == (unaffected,)
    with pytest.raises(RubricCriterionNotFoundError):
        rubric.remove_criterion(99)


def test_criterion_from_a_different_assessment_is_rejected():
    with pytest.raises(RubricValidationError, match="belong to this assessment"):
        AssessmentRubric(7, [criterion_row(assessment_id=8)])


@pytest.mark.parametrize("weights", [[], ["50"], ["60", "60"]])
def test_empty_underweight_or_overweight_rubric_cannot_be_published(weights):
    rubric = AssessmentRubric(7)
    for weight in weights:
        rubric.add_criterion("Analysis", "Explain reasoning.", weight)

    with pytest.raises(RubricValidationError):
        rubric.validate_for_publication()


def test_draft_can_be_built_incrementally_and_decimal_total_is_exact():
    rubric = AssessmentRubric(7)
    rubric.add_criterion("Analysis", "Analysis evidence", "33.33")
    assert rubric.total_weight == Decimal("33.33")
    rubric.add_criterion("Design", "Design evidence", "33.33")
    rubric.add_criterion("Testing", "Testing evidence", "33.34")

    rubric.validate_for_publication()
    assert rubric.total_weight == Decimal("100.00")
