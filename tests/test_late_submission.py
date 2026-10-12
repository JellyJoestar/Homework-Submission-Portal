"""Functional tests for IFN636-59: Allowing late submission execution."""
from db import get_all_assessments


def test_create_assessment_with_late_allowed(teacher_client):
    # Act
    response = teacher_client.post("/teacher/assessments",
        data={"title": "Test late allowed",
              "description": "description",
              "criteria": "criteria",
              "due_date": "2026-10-31T12:00",
              "unit_id": "1",
              "allow_late": "on"  # Return value of checked checkbox 
              }, follow_redirects=True)
    # Assert
    assert response.status_code == 200
    assert b"Test late allowed" in response.data
    
    # Getting the last assessment id from the list
    latest_assessment = get_all_assessments()[-1]
    detail_response = teacher_client.get(f"/teacher/assessments/{latest_assessment['assessment_id']}")
    
    # Assert
    assert detail_response.status_code == 200
    assert b"Allowed" in detail_response.data


def test_create_assessment_with_late_not_allowed(teacher_client):
    # Act
    response = teacher_client.post("/teacher/assessments",
        data={"title": "Test late not allowed",
              "description": "description",
              "criteria": "criteria",
              "due_date": "2026-10-31T12:00",
              "unit_id": "1"
              }, follow_redirects=True)
    # Assert
    assert response.status_code == 200
    assert b"Test late not allowed" in response.data

    # Getting the last assessment id from the list
    latest_assessment = get_all_assessments()[-1]
    detail_response = teacher_client.get(f"/teacher/assessments/{latest_assessment['assessment_id']}")

    # Assert
    assert detail_response.status_code == 200
    assert b"Not Allowed" in detail_response.data