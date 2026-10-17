-- Requires IFN636-114_add_rubric_criteria.sql. Apply once before application activation.
CREATE TABLE criterion_grades (
    criterion_grade_id INT PRIMARY KEY AUTO_INCREMENT,
    submission_id INT NOT NULL,
    criterion_id INT NOT NULL,
    mark DECIMAL(5,2) NOT NULL,
    comment TEXT NULL,
    CONSTRAINT chk_criterion_grades_mark_range CHECK (mark >= 0 AND mark <= 100),
    UNIQUE KEY uq_criterion_grades_submission_criterion (submission_id, criterion_id),
    FOREIGN KEY (submission_id) REFERENCES submissions(submission_id) ON DELETE CASCADE,
    FOREIGN KEY (criterion_id) REFERENCES rubric_criteria(criterion_id) ON DELETE CASCADE
);
