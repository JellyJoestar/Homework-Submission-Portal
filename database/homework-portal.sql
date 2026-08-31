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

INSERT INTO units (unit_code, unit_name)
VALUES ('IFN636', 'Software Life Cycle Management');
