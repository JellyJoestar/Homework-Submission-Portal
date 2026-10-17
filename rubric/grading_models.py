"""A submission owns the grades awarded against its assessment rubric."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from rubric.models import RubricValidationError


@dataclass(frozen=True)
class CriterionGrade:
    submission_id: int
    criterion_id: int
    mark: Decimal
    comment: str = ""

    def __post_init__(self):
        errors = {}
        key = f"mark_{self.criterion_id}"
        try:
            if self.mark is None or str(self.mark).strip() == "":
                raise ValueError("A mark is required for every criterion.")
            if isinstance(self.mark, bool):
                raise ValueError("Mark must be a valid number.")
            mark = Decimal(str(self.mark).strip())
            if not mark.is_finite() or not Decimal("0") <= mark <= Decimal("100"):
                raise ValueError("Mark must be between 0 and 100.")
            if mark != mark.quantize(Decimal("0.01")):
                raise ValueError("Mark must have at most two decimal places.")
        except (InvalidOperation, ValueError) as error:
            errors[key] = str(error) if isinstance(error, ValueError) else "Mark must be a valid number."
        comment = "" if self.comment is None else self.comment
        if not isinstance(comment, str):
            errors[f"comment_{self.criterion_id}"] = "Comment must be text."
        elif len(comment.encode("utf-8")) > 65535:
            errors[f"comment_{self.criterion_id}"] = "Comment is too long."
        if errors:
            raise RubricValidationError(errors)
        object.__setattr__(self, "mark", mark.quantize(Decimal("0.01")))
        object.__setattr__(self, "comment", comment.strip())


class SubmissionGrading:
    """Composition: construct the criterion grades owned by this submission."""

    def __init__(self, submission_id, rubric, rows):
        self.submission_id = submission_id
        self.rubric = rubric
        rubric.validate_for_publication()
        if not isinstance(rows, (list, tuple)):
            raise RubricValidationError({"grading": "Send the complete list of criterion grades."})
        grades, errors, seen = [], {}, set()
        expected = {criterion.criterion_id for criterion in rubric.criteria}
        for row in rows:
            if not isinstance(row, dict) or set(row) - {"criterion_id", "mark", "comment"}:
                errors["grading"] = "Each grade must contain a criterion ID, mark and optional comment."
                continue
            raw_id = row.get("criterion_id")
            if isinstance(raw_id, bool) or not isinstance(raw_id, (int, str)) or not str(raw_id).isdigit():
                errors["grading"] = "Criterion IDs must be valid integers."
                continue
            try:
                criterion_id = int(raw_id)
            except ValueError:
                errors["grading"] = "Criterion IDs must be valid integers."
                continue
            if criterion_id not in expected:
                errors["grading"] = "A criterion does not belong to this submission's assessment."
                continue
            if criterion_id in seen:
                errors["grading"] = "Each criterion must appear exactly once."
            seen.add(criterion_id)
            try:
                grades.append(CriterionGrade(submission_id, criterion_id, row.get("mark"), row.get("comment", "")))
            except RubricValidationError as error:
                errors.update(error.errors)
        for criterion_id in expected - seen:
            errors[f"mark_{criterion_id}"] = "A mark is required for every criterion."
        if errors:
            raise RubricValidationError(errors)
        self.grades = tuple(grades)
