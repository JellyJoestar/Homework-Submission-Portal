-- IFN636-103: count successful attempts on the single current submission row.
-- Existing submissions represent one successful attempt, so the safe backfill is 1.
ALTER TABLE submissions
    ADD COLUMN attempt_count BIGINT UNSIGNED NOT NULL DEFAULT 1,
    ADD CONSTRAINT chk_submissions_attempt_count_positive
        CHECK (attempt_count >= 1);
