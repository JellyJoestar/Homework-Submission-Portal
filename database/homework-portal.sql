USE homework_portal_db;

CREATE TABLE units (
    unit_id INT PRIMARY KEY AUTO_INCREMENT,
    unit_code VARCHAR(20) NOT NULL UNIQUE,
    unit_name VARCHAR(100) NOT NULL
);

CREATE TABLE assessments (
    assessment_id INT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(150) NOT NULL,
    description TEXT,
    due_date DATETIME NULL,
    unit_id INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Draft',

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

INSERT INTO units (unit_code, unit_name)
VALUES ('IFN636', 'Software Life Cycle Management');
