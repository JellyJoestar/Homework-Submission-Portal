"""Functional tests for IFN636-59: Allowing late submission configuration."""
import views
import io
from datetime import datetime, timedelta

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
                       "allow_late": False
                       }
    monkeypatch.setattr(views, "get_assessment_by_id", lambda *args: fake_assessment)

    # Act
    response = student_client.post("/student/assessments/2/submit", 
                                   data={"submission_file": (io.BytesIO(b"fake submission file"), "report.pdf")})
    
    # Assert
    assert response.status_code == 403
    assert b"The due date has passed. Late submissions are not allowed." in response.data



def test_blocked_message_after_due_date(student_client, monkeypatch):
    monkeypatch.setattr(views.grading_facade, "published_rubric", lambda assessment_id: None)
    fake_assessment = {"assessment_id": 2,
                       "title": "Overdue Assessment",
                       "description": "description",
                       "criteria": "criteria",
                       "due_date": datetime(2026, 1, 1, 12, 0),                       
                       "unit_id": 1,
                       "status": "Published",
                       "max_attempts": 1,
                       "allow_late": False
                       }
    monkeypatch.setattr(views, "get_assessment_by_id", lambda *args: fake_assessment)
    monkeypatch.setattr(views, "get_resources_by_assessment", lambda *args: [])
    monkeypatch.setattr(views, "get_submission_by_assessment_and_student", lambda *args: None)
    
    # Act
    response = student_client.get("/student/assessments/2")
    
    # Assert
    assert response.status_code == 200
    assert b"The due date has passed. Late submissions are not allowed." in response.data
    assert b"submission-upload-form" not in response.data
    
    
    
def test_late_submission_is_late_true(student_client, monkeypatch):
    fake_overdue_allowed = {"assessment_id": 10,
                            "title": "Overdue assessment",
                            "description": "description",
                            "criteria": "criteria",
                            "due_date": datetime(2026, 1, 1, 12, 0),                       
                            "unit_id": 1,
                            "status": "Published",
                            "max_attempts": 1,
                            "allow_late": True
                            }
    saved_kwargs = {}

    monkeypatch.setattr(views, "get_assessment_by_id", lambda *args: fake_overdue_allowed)
    monkeypatch.setattr(
        views,
        "get_submission_by_assessment_and_student",
        lambda *args: None,
    )
    monkeypatch.setattr(views, "save_submission_attempt",
                        lambda *args, **kwargs: (saved_kwargs.update(kwargs), {"submission_id": 99, "replaced_stored_filename": None})[1]
                        )
    monkeypatch.setattr(views, "remove_submission_file", lambda *args: None)

    # Act
    response = student_client.post("/student/assessments/10/submit",
                                   data={"submission_file": (io.BytesIO(b"fake submission file"), "report.pdf")})
    
    # Assert
    assert response.status_code == 302
    assert saved_kwargs.get("is_late") is True



def test_on_time_submission_is_late_false(student_client, monkeypatch):
    fake_future_assessment = {"assessment_id": 11,
                              "title": "Future assessment",
                              "description": "description",
                              "criteria": "criteria",
                              "due_date": datetime(2030, 1, 1, 12, 0),                       
                              "unit_id": 1,
                              "status": "Published",
                              "max_attempts": 1,
                              "allow_late": True
                              }
    saved_kwargs = {}

    monkeypatch.setattr(views, "get_assessment_by_id", lambda *args: fake_future_assessment)
    monkeypatch.setattr(
        views,
        "get_submission_by_assessment_and_student",
        lambda *args: None,
    )
    monkeypatch.setattr(views, "save_submission_attempt",
                        lambda *args, **kwargs: (saved_kwargs.update(kwargs), {"submission_id": 100, "replaced_stored_filename": None})[1]
                        )
    monkeypatch.setattr(views, "remove_submission_file", lambda *args: None)

    # Act
    response = student_client.post("/student/assessments/11/submit",
                                   data={"submission_file": (io.BytesIO(b"fake submission file"), "report.pdf")})
    
    # Assert
    assert response.status_code == 302
    assert saved_kwargs.get("is_late") is False



def test_teacher_sees_late_badge(teacher_client, monkeypatch):
    # UNIT = {"unit_id": 1, "unit_code": "IFN636", "unit_name": "Software Life Cycle Management"}
    fake_assessment = {"assessment_id": 12,
                        "title": "Fake assessment for badge",
                        "description": "description",
                        "criteria": "criteria",
                        "due_date": datetime(2026, 1, 1, 12, 0),                       
                        "unit_id": 1,
                        "status": "Published",
                        "max_attempts": 1,
                        "allow_late": True
                        }
    fake_submission = [{"submission_id": 1,
                        "student_name": "Sam Student",
                        "original_filename": "report.pdf",
                        "status": "Submitted",
                        "submitted_at": datetime(2026, 10, 1, 12, 0),
                        "is_late": True
                        }]

    monkeypatch.setattr(views, "get_assessment_by_id", lambda *args: fake_assessment)
    monkeypatch.setattr(views, "get_submissions_by_assessment", lambda *args: fake_submission)
    
    # Act
    response = teacher_client.get("/teacher/assessments/12/submissions")
    
    # Assert
    assert response.status_code == 200
    assert b"Late" in response.data



def test_student_sees_late_badge(student_client, monkeypatch):
    fake_submissions = [{"submission_id": 1,
                         "unit_code": "IFN636",
                         "assessment_title": "Test",
                         "original_filename": "report.pdf",
                         "status": "Submitted",
                         "submitted_at": datetime(2026, 10, 1, 12, 0),
                         "is_late": True
                         }]
    monkeypatch.setattr(views, "get_submissions_by_student", lambda *args: fake_submissions)
    
    # Act
    response = student_client.get("/student/submissions")
    
    # Assert
    assert response.status_code == 200
    assert b"Submitted Late" in response.data
    


def test_submission_one_minute_before_due_date(student_client, monkeypatch):
    due_date = datetime(2026, 1, 1, 12, 0)
    one_minute_before = due_date - timedelta(minutes=1)
    fake_assessment = {"assessment_id": 13,
                       "title": "One minute before submission",
                       "description": "description",
                       "criteria": "criteria",
                       "due_date": due_date,           
                       "unit_id": 1,
                       "status": "Published",
                       "max_attempts": 1,
                       "allow_late": False
                       }
    saved_kwargs = {}

    monkeypatch.setattr(views, "get_assessment_by_id", lambda *args: fake_assessment)
    monkeypatch.setattr(views, "datetime", type("FakeDateTime", (datetime,), {"now": classmethod(lambda *args: one_minute_before)}))
    monkeypatch.setattr(views, "save_submission_attempt",
                        lambda *args, **kwargs: (saved_kwargs.update(kwargs), {"submission_id": 100, "replaced_stored_filename": None})[1]
                        )
    monkeypatch.setattr(views, "remove_submission_file", lambda *args: None)
    monkeypatch.setattr(views, "get_submission_by_assessment_and_student", lambda *args: None)
    
    # Act
    response = student_client.post("/student/assessments/13/submit", 
                                   data={"submission_file": (io.BytesIO(b"fake submission file"), "report.pdf")}
                                   )

    # Assert
    assert response.status_code == 302
    assert saved_kwargs.get("is_late") is False



def test_submission_one_minute_after_due_date_is_blocked(student_client, monkeypatch):
    due_date = datetime(2026, 1, 1, 12, 0)
    one_minute_after = due_date + timedelta(minutes=1)
    fake_assessment = {"assessment_id": 14,
                       "title": "One minute after submission",
                       "description": "description",
                       "criteria": "criteria",
                       "due_date": due_date,            
                       "unit_id": 1,
                       "status": "Published",
                       "max_attempts": 1,
                       "allow_late": False
                       }

    monkeypatch.setattr(views, "get_assessment_by_id", lambda *args: fake_assessment)
    monkeypatch.setattr(views, "datetime", type("FakeDateTime", (datetime,), {"now": classmethod(lambda *args: one_minute_after)}))
    
    # Act
    response = student_client.post("/student/assessments/14/submit",
                                   data={"submission_file": (io.BytesIO(b"fake submission file"), "report.pdf")}
                                   )
    
    # Assert
    assert response.status_code == 403
    assert b"The due date has passed. Late submissions are not allowed." in response.data
