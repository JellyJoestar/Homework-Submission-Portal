import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

    return connection

def get_all_assessments():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            a.assessment_id,
            a.title,
            a.description,
            a.due_date,
            a.status,
            a.unit_id,
            u.unit_code,
            u.unit_name
        FROM assessments a
        JOIN units u
            ON a.unit_id = u.unit_id
        """
    )
    assessments = cursor.fetchall()
    cursor.close()
    connection.close()
    return assessments

def get_assessment_by_id(assessment_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            a.assessment_id,
            a.title,
            a.description,
            a.due_date,
            a.status,
            a.unit_id,
            u.unit_code,
            u.unit_name
        FROM assessments a
        JOIN units u
            ON a.unit_id = u.unit_id
        WHERE a.assessment_id = %s
        """,
        (assessment_id,)
    )
    assessment = cursor.fetchone()
    cursor.close()
    connection.close()
    return assessment

def get_published_assessments():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            a.assessment_id,
            a.title,
            a.description,
            a.due_date,
            a.status,
            a.unit_id,
            u.unit_code,
            u.unit_name
        FROM assessments a
        JOIN units u
            ON a.unit_id = u.unit_id
        WHERE a.status = 'Published'
        ORDER BY a.assessment_id DESC
        """
    )
    assessments = cursor.fetchall()
    cursor.close()
    connection.close()
    return assessments

def get_all_units():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            u.unit_id,
            u.unit_code,
            u.unit_name
        FROM units u
        ORDER BY u.unit_code
        """
    )
    units = cursor.fetchall()
    cursor.close()
    connection.close()
    return units

def create_assessment(title, description, due_date, unit_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO assessments (title, description, due_date, unit_id)
        VALUES (%s, %s, %s, %s)
        """,
        (title, description, due_date, unit_id)
    )
    connection.commit()
    cursor.close()
    connection.close()

def update_assessment(assessment_id, title, description, due_date, unit_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE assessments
        SET title = %s, description = %s, due_date = %s, unit_id = %s
        WHERE assessment_id = %s
        AND status = 'Draft'
        """,
        (title, description, due_date, unit_id, assessment_id)
    )
    connection.commit()
    cursor.close()
    connection.close()

def delete_draft_assessment(assessment_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        DELETE FROM assessments
        WHERE assessment_id = %s
        AND status = 'Draft'
        """,
        (assessment_id,)
    )
    connection.commit()
    cursor.close()
    connection.close()

def update_assessment_status(assessment_id, current_status, new_status):
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE assessments
        SET status = %s
        WHERE assessment_id = %s
        AND status = %s
        """,
        (new_status, assessment_id, current_status)
    )
    updated_rows = cursor.rowcount

    connection.commit()
    cursor.close()
    connection.close()

    return updated_rows

def get_resources_by_assessment(assessment_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            resource_id,
            assessment_id,
            original_filename,
            stored_filename,
            uploaded_at
        FROM assessment_resources
        WHERE assessment_id = %s
        ORDER BY uploaded_at
        """,
        (assessment_id,)
    )
    resources = cursor.fetchall()
    cursor.close()
    connection.close()
    return resources


def get_resource_by_id(resource_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            resource_id,
            assessment_id,
            original_filename,
            stored_filename,
            uploaded_at
        FROM assessment_resources
        WHERE resource_id = %s
        """,
        (resource_id,)
    )

    resource = cursor.fetchone()
    cursor.close()
    connection.close()
    return resource


def create_assessment_resource(assessment_id, original_filename, stored_filename):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO assessment_resources (
            assessment_id,
            original_filename,
            stored_filename
        )
        VALUES (%s, %s, %s)
        """,
        (assessment_id, original_filename, stored_filename)
    )

    connection.commit()
    cursor.close()
    connection.close()


def delete_assessment_resource(resource_id, assessment_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        DELETE FROM assessment_resources
        WHERE resource_id = %s
        AND assessment_id = %s
        """,
        (resource_id, assessment_id)
    )

    connection.commit()
    cursor.close()
    connection.close()