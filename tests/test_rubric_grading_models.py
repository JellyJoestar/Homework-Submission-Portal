"""FR-RUB-02 value rules, ownership, completeness and weighted arithmetic."""
from decimal import Decimal
import pytest
from rubric.grading_models import CriterionGrade, SubmissionGrading
from rubric.models import AssessmentRubric, RubricValidationError


def rubric(weights=("40", "60")):
    return AssessmentRubric(7, [
        dict(criterion_id=index, assessment_id=7, title=f"Criterion {index}", description="Evidence", weight=weight)
        for index, weight in enumerate(weights, 1)
    ])


def rows(first="80", second="90", comment=""):
    return [dict(criterion_id=1, mark=first, comment=comment), dict(criterion_id=2, mark=second)]


@pytest.mark.parametrize("mark", [None, "", " ", "NaN", "Infinity", "-Infinity", "-0.01", "100.01", "3.333", "abc", True, [], {}, "1e9999"])
def test_ac4_invalid_mark_is_rejected(mark):
    with pytest.raises(RubricValidationError) as error:
        SubmissionGrading(9, rubric(), rows(first=mark))
    assert "mark_1" in error.value.errors


@pytest.mark.parametrize("mark", ["0", "100", "0.01", "99.99", 0, 100, Decimal("75.50")])
def test_ac1_ac4_valid_marks_are_two_decimal_values_owned_by_submission(mark):
    grading = SubmissionGrading(9, rubric(), rows(first=mark))
    assert grading.grades[0].mark == Decimal(str(mark))
    assert grading.grades[0].mark.as_tuple().exponent == -2
    assert grading.grades[0].submission_id == 9


@pytest.mark.parametrize("input_rows", [None, {}, [], [dict(criterion_id=1, mark="80")],
    [dict(criterion_id=1, mark=80), dict(criterion_id=1, mark=90)],
    [dict(criterion_id=1, mark=80), dict(criterion_id=999, mark=90)],
    [dict(criterion_id=True, mark=80), dict(criterion_id=2, mark=90)],
    [dict(criterion_id=1.0, mark=80), dict(criterion_id=2, mark=90)],
    [dict(criterion_id="x", mark=80), dict(criterion_id=2, mark=90)],
    [dict(criterion_id=1, mark=80, submission_id=99), dict(criterion_id=2, mark=90)],
    [None, dict(criterion_id=2, mark=90)]])
def test_ac5_missing_duplicate_foreign_or_malformed_criteria_are_rejected(input_rows):
    with pytest.raises(RubricValidationError):
        SubmissionGrading(9, rubric(), input_rows)


@pytest.mark.parametrize("weights,marks,expected", [
    (("40", "60"), ("80", "90"), "86.00"),
    (("50", "50"), ("0.01", "0"), "0.01"),
    (("50", "50"), ("0.01", "0.01"), "0.01"),
    (("33.33", "66.67"), ("78.91", "89.12"), "85.72"),
    (("40", "60"), ("0", "0"), "0.00"),
    (("40", "60"), ("100", "100"), "100.00"),
])
def test_ac6_weighted_result_rounds_once_half_up(weights, marks, expected):
    assert SubmissionGrading(9, rubric(weights), rows(*marks)).final_grade == Decimal(expected)


def test_ac2_ac3_comment_only_update_keeps_result_and_mark_update_recalculates():
    initial = SubmissionGrading(9, rubric(), rows(comment="Original"))
    commented = SubmissionGrading(9, rubric(), rows(comment="Updated"))
    revised = SubmissionGrading(9, rubric(), rows(first="50"))
    assert initial.final_grade == commented.final_grade == Decimal("86.00")
    assert commented.grades[0].comment == "Updated"
    assert revised.final_grade == Decimal("74.00")


@pytest.mark.parametrize("comment", ["", None, "  Useful evidence.  "])
def test_optional_comment_normalizes_text(comment):
    grade = CriterionGrade(9, 1, "50", comment)
    assert grade.comment == (comment or "").strip()


@pytest.mark.parametrize("comment", [42, [], "界" * 21846], ids=["number", "list", "too-many-utf8-bytes"])
def test_invalid_comments_are_rejected_before_persistence(comment):
    with pytest.raises(RubricValidationError):
        SubmissionGrading(9, rubric(), rows(comment=comment))


@pytest.mark.parametrize("definition", [AssessmentRubric(7), rubric(("30", "60"))])
def test_incomplete_or_invalid_rubric_cannot_be_graded(definition):
    with pytest.raises(RubricValidationError):
        SubmissionGrading(9, definition, rows())
