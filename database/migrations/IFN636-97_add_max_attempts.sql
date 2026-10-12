-- IFN636-97: add the assessment attempt limit without rebuilding existing data.
-- MySQL 8.0.16 and later enforce the named CHECK constraint.
ALTER TABLE assessments
    ADD COLUMN max_attempts INT NOT NULL DEFAULT 1,
    ADD CONSTRAINT chk_assessments_max_attempts_nonnegative
        CHECK (max_attempts >= 0);
