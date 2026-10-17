-- IFN636-114: add rubric criteria without rebuilding existing assessments.
-- Apply once to the existing homework_portal database before deploying this story.
CREATE TABLE rubric_criteria (
    criterion_id INT PRIMARY KEY AUTO_INCREMENT,
    assessment_id INT NOT NULL,
    title VARCHAR(150) NOT NULL,
    description TEXT NOT NULL,
    weight DECIMAL(5,2) NOT NULL,
    CONSTRAINT chk_rubric_criterion_title_required
        CHECK (CHAR_LENGTH(TRIM(title)) > 0),
    CONSTRAINT chk_rubric_criterion_description_required
        CHECK (CHAR_LENGTH(TRIM(description)) > 0),
    CONSTRAINT chk_rubric_criterion_weight_range
        CHECK (weight > 0 AND weight <= 100),
    KEY idx_rubric_criteria_assessment (assessment_id, criterion_id),
    FOREIGN KEY (assessment_id)
        REFERENCES assessments(assessment_id)
        ON DELETE CASCADE
);
