"""A rubric owns the criterion objects belonging to one assessment."""
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation


class RubricValidationError(ValueError):
    def __init__(self, errors):
        self.errors = dict(errors)
        super().__init__(" ".join(self.errors.values()))


class RubricCriterionNotFoundError(Exception):
    """The requested criterion does not belong to this assessment's rubric."""


class RubricNotEditableError(Exception):
    """The assessment is no longer Draft."""


@dataclass(frozen=True)
class RubricCriterion:
    criterion_id: int | None
    assessment_id: int
    title: str
    description: str
    weight: Decimal

    def __post_init__(self):
        errors = {}
        title = self.title.strip() if isinstance(self.title, str) else ""
        description = (
            self.description.strip() if isinstance(self.description, str) else ""
        )
        if not title:
            errors["title"] = "Title is required."
        elif len(title) > 150:
            errors["title"] = "Title must be at most 150 characters."
        if not description:
            errors["description"] = "Description is required."
        elif len(description.encode("utf-8")) > 65535:
            errors["description"] = "Description is too long."

        weight = None
        if self.weight is None or str(self.weight).strip() == "":
            errors["weight"] = "Weight is required."
        else:
            try:
                weight = Decimal(str(self.weight).strip())
                if not weight.is_finite() or not Decimal("0") < weight <= Decimal("100"):
                    errors["weight"] = "Weight must be greater than 0 and at most 100."
                elif weight != weight.quantize(Decimal("0.01")):
                    errors["weight"] = "Weight must have at most two decimal places."
            except InvalidOperation:
                errors["weight"] = "Weight must be a valid number."
        if errors:
            raise RubricValidationError(errors)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "weight", weight.quantize(Decimal("0.01")))


class AssessmentRubric:
    """Composition: this object creates and manages its own criterion objects."""

    def __init__(self, assessment_id, rows=()):
        self.assessment_id = assessment_id
        self._criteria = [RubricCriterion(**row) for row in rows]
        if any(item.assessment_id != assessment_id for item in self._criteria):
            raise RubricValidationError(
                {"rubric": "A rubric criterion must belong to this assessment."}
            )

    @property
    def criteria(self):
        return tuple(self._criteria)

    @property
    def total_weight(self):
        return sum((item.weight for item in self._criteria), Decimal("0"))

    def get_criterion(self, criterion_id):
        for criterion in self._criteria:
            if criterion.criterion_id == criterion_id:
                return criterion
        raise RubricCriterionNotFoundError

    def add_criterion(self, title, description, weight):
        criterion = RubricCriterion(
            None, self.assessment_id, title, description, weight
        )
        self._criteria.append(criterion)
        return criterion

    def update_criterion(self, criterion_id, title, description, weight):
        current = self.get_criterion(criterion_id)
        updated = replace(
            current, title=title, description=description, weight=weight
        )
        self._criteria[self._criteria.index(current)] = updated
        return updated

    def remove_criterion(self, criterion_id):
        self._criteria.remove(self.get_criterion(criterion_id))

    def validate_for_publication(self):
        if not self._criteria:
            raise RubricValidationError(
                {"rubric": "Add at least one rubric criterion before publishing."}
            )
        if self.total_weight != Decimal("100.00"):
            raise RubricValidationError(
                {"rubric": (
                    "Rubric weights must total 100%. "
                    f"Current total: {self.total_weight:.2f}%."
                )}
            )
