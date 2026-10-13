"""Functional tests for IFN636-59: Allowing late submission configuration."""
import views
import io
from datetime import datetime

UNIT = {"unit_id": 1, "unit_code": "IFN636", "unit_name": "Software Life Cycle Management"}



def test_create_assessment_with_late_allowed(teacher_client, monkeypatch):
    # monkeypatch
    saved = []

    monkeypatch.setattr(views, "get_all_units", lambda: [UNIT])
    monkeypatch.setattr(views, "create_assessment", lambda *args: saved.append(args))
    
    # Act
    response = teacher_client.post("/teacher/assessments",
        data={"title": "Test late allowed",
              "description": "description",
              "criteria": "criteria",
              "due_date": "2026-10-31T12:00",
              "unit_id": "1",
              "max_attempts": "1",
              "allow_late": "on"  # Return value of checked checkbox 
              })
    # Assert
    assert response.status_code == 302
    assert saved[0][-1] is True



def test_create_assessment_with_late_not_allowed(teacher_client, monkeypatch):
    # monkeypatch
    saved = []
    
    monkeypatch.setattr(views, "get_all_units", lambda: [UNIT])
    monkeypatch.setattr(views, "create_assessment", lambda *args: saved.append(args))
    
    # Act
    response = teacher_client.post("/teacher/assessments",
        data={"title": "Test late allowed",
                "description": "description",
                "criteria": "criteria",
                "due_date": "2026-10-31T12:00",
                "unit_id": "1",
                "max_attempts": "1"
                })
    # Assert
    assert response.status_code == 302
    assert saved[0][-1] is False
    
    
    
def test_submission_blocked_after_due_date(student_client, monkeypatch):
    fake_assessment = {"assessment_id": 2,
                       "title": "Overdue Assessment",
                       "description": "description",
                       "criteria": "criteria",
                       "due_date": datetime(2026, 1, 1, 12, 0),                       
                       "unit_id": 1,
                       "status": "Published",
                       "max_attempts": 1,
                       "allow_late": False,
                       }
    monkeypatch.setattr(views, "get_assessment_by_id", lambda *args: fake_assessment)

    # Act
    response = student_client.post("/student/assessments/2/submit", 
        data={"submission_file": (io.BytesIO(b"fake submission file"), "report.pdf")})
    
    # Assert
    assert response.status_code == 403
    assert b"The due date has passed. Late submissions are not allowed." in response.data



def test_blocked_message_after_due_date(student_client, monkeypatch):
    fake_assessment = {"assessment_id": 2,
                       "title": "Overdue Assessment",
                       "description": "description",
                       "criteria": "criteria",
                       "due_date": datetime(2026, 1, 1, 12, 0),                       
                       "unit_id": 1,
                       "status": "Published",
                       "max_attempts": 1,
                       "allow_late": False,
                       }
    monkeypatch.setattr(views, "get_assessment_by_id", lambda *args: fake_assessment)
    monkeypatch.setattr(views, "get_resources_by_assessment", lambda *args: [])
    
    # Act
    response = student_client.get("/student/assessments/2")
    
    # Assert
    assert response.status_code == 200
    assert b"The due date has passed. Late submissions are not allowed." in response.data
    assert b"submission-upload-form" not in response.data