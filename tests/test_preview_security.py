
def test_anonymous_user_is_redirected_to_login(client, submissions):
    # Act
    response = client.get("/student/submissions/2/preview")

    # Assert
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login")


def test_student_cannot_preview_another_students_submission(student_client, submissions):
    # Act: submission 4 belongs to another student
    response = student_client.get("/student/submissions/4/preview")

    # Assert: no file content is returned
    assert response.status_code == 404
    assert b"%PDF" not in response.data


def test_preview_of_a_docx_with_a_javascript_link_cannot_run_scripts(student_client, submissions):
    # Act: submission 3 has a link to "javascript:alert(document.cookie)"
    response = student_client.get("/student/submissions/3/preview")

    # Assert
    assert response.status_code == 200
    assert response.headers["Content-Security-Policy"] == "sandbox"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
