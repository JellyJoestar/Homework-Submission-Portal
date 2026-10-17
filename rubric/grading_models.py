"""A submission owns the grades awarded against its assessment rubric."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CriterionGrade:
    submission_id: int
    criterion_id: int
    mark: Decimal
    comment: str = ""


class SubmissionGrading:
    """Composition: construct the criterion grades owned by this submission."""

    def __init__(self, submission_id, rubric, rows):
        self.submission_id = submission_id
        self.rubric = rubric
        self.grades = tuple(CriterionGrade(submission_id=submission_id, **row) for row in rows)
