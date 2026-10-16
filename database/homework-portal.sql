SET default_storage_engine = InnoDB;

DROP DATABASE IF EXISTS homework_portal;

CREATE DATABASE homework_portal;

-- Create DB user (used by our app)
-- CHANGE PASSWORD IN A PRODUCTION ENVIRONMENT
-- This password should only be used in local development
CREATE USER IF NOT EXISTS 'homework_portal' @'%' IDENTIFIED BY 'homework_portal';

GRANT ALL PRIVILEGES ON homework_portal.* TO 'homework_portal' @'%';

FLUSH PRIVILEGES;

USE homework_portal;

CREATE TABLE units (
    unit_id INT PRIMARY KEY AUTO_INCREMENT,
    unit_code VARCHAR(20) NOT NULL UNIQUE,
    unit_name VARCHAR(100) NOT NULL
);

CREATE TABLE users (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('Teacher', 'Student') NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE assessments (
    assessment_id INT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(150) NOT NULL,
    description TEXT,
    criteria TEXT,
    due_date DATETIME,
    unit_id INT NOT NULL,
    allow_late BOOLEAN NOT NULL DEFAULT FALSE,
    max_attempts INT NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'Draft',
    CONSTRAINT chk_assessments_max_attempts_nonnegative
        CHECK (max_attempts >= 0),
    FOREIGN KEY (unit_id)
        REFERENCES units(unit_id)
);

CREATE TABLE assessment_resources (
    resource_id INT PRIMARY KEY AUTO_INCREMENT,
    assessment_id INT NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL,
    uploaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (assessment_id)
        REFERENCES assessments(assessment_id)
        ON DELETE CASCADE
);

CREATE TABLE submissions (
    submission_id INT PRIMARY KEY AUTO_INCREMENT,
    assessment_id INT NOT NULL,
    student_id INT NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL,
    attempt_count BIGINT UNSIGNED NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'Submitted',
    mark DECIMAL(5,2) NULL,
    feedback TEXT NULL,
    is_late BOOLEAN NOT NULL DEFAULT FALSE,
    submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_submissions_attempt_count_positive
        CHECK (attempt_count >= 1),

    FOREIGN KEY (assessment_id)
        REFERENCES assessments(assessment_id)
        ON DELETE CASCADE,

    FOREIGN KEY (student_id)
        REFERENCES users(user_id),

    UNIQUE (assessment_id, student_id)
);

INSERT INTO units (unit_code, unit_name)
VALUES ('IFN636', 'Software Life Cycle Management');

-- Demo accounts. The password for all of them is: Password123!
-- (hashes generated with werkzeug.security.generate_password_hash)
INSERT INTO users (email, password_hash, role, first_name, last_name)
VALUES
    ('teacher@portal.edu.au', 'scrypt:32768:8:1$KfzOQEfjw0y0Dr0R$65cc2e0f9d1e27eba6ea80be4e7250318ba171c5e1c983d106d65f09beeaabcd8f41cb1065fecc920cc4d9c05bf9979c108edad4a5b748f8e1176d9d9ceb0e70', 'Teacher', 'Tess', 'Teacher'),
    ('student1@portal.edu.au', 'scrypt:32768:8:1$KfzOQEfjw0y0Dr0R$65cc2e0f9d1e27eba6ea80be4e7250318ba171c5e1c983d106d65f09beeaabcd8f41cb1065fecc920cc4d9c05bf9979c108edad4a5b748f8e1176d9d9ceb0e70', 'Student', 'Sam', 'Student'),
    ('student2@portal.edu.au', 'scrypt:32768:8:1$KfzOQEfjw0y0Dr0R$65cc2e0f9d1e27eba6ea80be4e7250318ba171c5e1c983d106d65f09beeaabcd8f41cb1065fecc920cc4d9c05bf9979c108edad4a5b748f8e1176d9d9ceb0e70', 'Student', 'Alex', 'Student');

-- Demo late submission data for Postman CI test
INSERT INTO assessments (assessment_id, title, description, criteria, due_date, unit_id, allow_late, status)
VALUES 
    (3, 'Testing Late Assessment', 'Testing late submission rejection', 'criteria', '2026-01-01 12:00:00', 1, FALSE, 'Published'),
    (4, 'Testing Late Assessment Allowed', 'Testing late submission acception', 'criteria', '2026-01-01 12:00:00', 1, TRUE, 'Published');
