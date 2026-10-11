"""Functional tests for IFN636-90: preview submitted files in the portal."""
from preview.factory import DocxPreview, PdfPreview, PreviewFactory, UnsupportedPreview


def test_factory_chooses_the_preview_for_each_file_type():
    # Act
    pdf = PreviewFactory.get_preview("report.pdf", "report.pdf")
    docx = PreviewFactory.get_preview("essay.docx", "Essay.DOCX")
    other = PreviewFactory.get_preview("notes.txt", "notes.txt")

    # Assert
    assert isinstance(pdf, PdfPreview)
    assert isinstance(docx, DocxPreview)
    assert isinstance(other, UnsupportedPreview)


def test_teacher_previews_a_pdf_inline(teacher_client, submissions):
    # Act
    response = teacher_client.get("/teacher/submissions/1/preview")

    # Assert
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.headers["Content-Disposition"].startswith("inline")


def test_student_previews_their_docx_as_html(student_client, submissions):
    # Act
    response = student_client.get("/student/submissions/2/preview")

    # Assert
    assert response.status_code == 200
    assert b"<strong>My Assessment Essay</strong>" in response.data


def test_missing_file_shows_a_controlled_error(teacher_client, submissions):
    # Act
    response = teacher_client.get("/teacher/submissions/5/preview")

    # Assert
    assert response.status_code == 404
    assert b"The submitted file is not available." in response.data
