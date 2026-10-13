"""Functional tests for IFN636-59: Allowing late submission configuration."""
import views

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