"""A rubric owns the criterion objects belonging to one assessment."""
from dataclasses import dataclass, replace
from decimal import Decimal


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


class AssessmentRubric:
    """Composition: this object creates and manages its own criterion objects."""

    def __init__(self, assessment_id, rows=()):
        self.assessment_id = assessment_id
        self._criteria = [RubricCriterion(**row) for row in rows]
        if any(item.assessment_id != assessment_id for item in self._criteria):
            raise ValueError("A rubric criterion must belong to this assessment.")

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
            None, self.assessment_id, title, description, Decimal(str(weight))
        )
        self._criteria.append(criterion)
        return criterion

    def update_criterion(self, criterion_id, title, description, weight):
        current = self.get_criterion(criterion_id)
        updated = replace(
            current, title=title, description=description, weight=Decimal(str(weight))
        )
        self._criteria[self._criteria.index(current)] = updated
        return updated

    def remove_criterion(self, criterion_id):
        self._criteria.remove(self.get_criterion(criterion_id))
