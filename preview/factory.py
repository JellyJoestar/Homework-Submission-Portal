from abc import ABC, abstractmethod

import mammoth
from flask import render_template, send_file


class FilePreview(ABC):
    def __init__(self, file_path, original_filename):
        self.file_path = file_path
        self.original_filename = original_filename

    @abstractmethod
    def render(self):
        """Return the response that shows the file in the browser."""


class PdfPreview(FilePreview):
    def render(self):
        # Browsers have their own PDF viewer, so the file is sent as it is
        return send_file(
            self.file_path,
            mimetype="application/pdf",
            as_attachment=False,
            download_name=self.original_filename
        )


class DocxPreview(FilePreview):
    def render(self):
        # Browsers can't show DOCX files, so mammoth converts the content to HTML
        try:
            with open(self.file_path, "rb") as docx_file:
                result = mammoth.convert_to_html(docx_file)
        except Exception:
            return render_template(
                "file_preview.html",
                filename=self.original_filename,
                message="This file could not be previewed. Please download it instead."
            )
        return render_template("file_preview.html", filename=self.original_filename, content=result.value)


class UnsupportedPreview(FilePreview):
    def render(self):
        return render_template(
            "file_preview.html",
            filename=self.original_filename,
            message="Preview not available for this file type."
        )


class PreviewFactory:
    @staticmethod
    def get_preview(file_path, original_filename):
        extension = original_filename.rsplit(".", 1)[-1].lower()
        if extension == "pdf":
            return PdfPreview(file_path, original_filename)
        elif extension == "docx":
            return DocxPreview(file_path, original_filename)
        else:
            return UnsupportedPreview(file_path, original_filename)
