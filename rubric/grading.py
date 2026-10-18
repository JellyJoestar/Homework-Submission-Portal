"""Facade coordinating rubric grading reads, domain rules and atomic writes."""
import db
from rubric.grading_models import SubmissionGrading


class RubricGradingFacade:
    def __init__(self, repository=db):
        self.repository = repository

    def review(self, submission):
        rubric = self.repository.get_rubric_by_assessment(submission["assessment_id"])
        grades = self.repository.get_criterion_grades(submission["submission_id"]) if rubric.criteria else []
        return rubric, {grade["criterion_id"]: grade for grade in grades}

    def save(self, submission_id, rows):
        with self.repository.grading_transaction(submission_id) as (cursor, submission, rubric):
            grading = SubmissionGrading(submission_id, rubric, rows)
            self.repository.store_criterion_grades(cursor, grading)
            self.repository.store_rubric_result(cursor, grading)
        return grading


grading_facade = RubricGradingFacade()
