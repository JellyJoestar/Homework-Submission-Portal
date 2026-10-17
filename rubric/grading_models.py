"""A submission owns the grades awarded against its assessment rubric."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CriterionGrade:
    submission_id: int
    criterion_id: int
    mark: Decimal
    comment: str = ""
