"""Facade coordinating rubric grading reads, domain rules and atomic writes."""
import db
from decimal import Decimal, InvalidOperation
from rubric.grading_models import SubmissionGrading
from rubric.models import AssessmentRubric, RubricValidationError


class RubricGradingFacade:
    def __init__(self, repository=db):
        self.repository = repository

    def review(self, submission):
        rubric = self.repository.get_rubric_by_assessment(submission["assessment_id"])
        grades = self.repository.get_criterion_grades(submission["submission_id"]) if rubric.criteria else []
        return rubric, {grade["criterion_id"]: grade for grade in grades}

    def published_rubric(self, assessment_id):
        return self.repository.get_published_rubric_by_assessment(assessment_id)

    @staticmethod
    def submission_metadata(submission, student_id):
        """Do not pass unverified grade fields to any student template."""
        if submission.get("student_id") != student_id:
            raise db.SubmissionNotFoundError
        return {key: value for key, value in submission.items() if key not in {
            "mark", "feedback", "rubric_result", "criterion_grades", "grades", "final_grade",
        }}

    def student_submission(self, submission, student_id):
        self.submission_metadata(submission, student_id)
        snapshots = self.repository.get_student_grading_snapshots(student_id, submission["submission_id"])
        return self._student_projection(submission, snapshots.get(submission["submission_id"]), student_id)

    def student_results(self, submissions, student_id):
        owned = [submission for submission in submissions if submission.get("student_id") == student_id]
        if not owned:
            return []
        snapshots = self.repository.get_student_grading_snapshots(student_id)
        return [self._student_projection(submission, snapshots.get(submission["submission_id"]), student_id)
                for submission in owned]

    def _student_projection(self, submission, snapshot, student_id):
        safe = self.submission_metadata(submission, student_id)
        if snapshot is None or snapshot["assessment_status"] not in {"Published", "Closed", "Archived"}:
            return safe
        if not snapshot["criteria"]:
            # Retain historical manual results, but hide feedback until marked.
            if snapshot["grade_count"] == 0 and snapshot["mark"] is not None:
                safe.update(mark=snapshot["mark"], feedback=snapshot["feedback"])
            return safe
        safe["has_rubric"] = True
        if snapshot["grade_count"] != len(snapshot["criteria"]):
            return safe
        try:
            rubric = AssessmentRubric(snapshot["assessment_id"], snapshot["criteria"])
            grading = SubmissionGrading(snapshot["submission_id"], rubric, snapshot["grades"])
            stored_result = Decimal(str(snapshot["mark"]))
            if not stored_result.is_finite() or stored_result != grading.final_grade:
                return safe
        except (RubricValidationError, InvalidOperation, ValueError):
            return safe
        grades = {grade.criterion_id: grade for grade in grading.grades}
        safe["mark"] = stored_result
        safe["rubric_result"] = {
            "final_grade": stored_result,
            "criteria": tuple({
                "criterion_id": criterion.criterion_id, "title": criterion.title,
                "description": criterion.description, "weight": criterion.weight,
                "mark": grades[criterion.criterion_id].mark,
                "comment": grades[criterion.criterion_id].comment,
            } for criterion in rubric.criteria),
        }
        return safe

    def save(self, submission_id, rows):
        with self.repository.grading_transaction(submission_id) as (cursor, submission, rubric):
            grading = SubmissionGrading(submission_id, rubric, rows)
            self.repository.store_criterion_grades(cursor, grading)
            self.repository.store_rubric_result(cursor, grading)
        return grading


grading_facade = RubricGradingFacade()
