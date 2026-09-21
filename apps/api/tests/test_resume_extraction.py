from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
import rigor_api.resume_extraction as extraction
from rigor_api.resume_extraction import (
    DOCX_MIME,
    MAX_DOCX_ENTRIES,
    MAX_DOCX_UNCOMPRESSED_BYTES,
    MAX_PDF_PAGES,
    MAX_RESUME_FILE_BYTES,
    PDF_MIME,
    ResumeExtractionError,
    extract_docx_text,
    extract_pdf_text,
    validate_resume_upload_metadata,
)

CONTENT_TYPES = b"""<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml" />
</Types>
"""


def docx_bytes(text: str) -> bytes:
    document = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
  </w:body>
</w:document>
""".encode()
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


def test_resume_metadata_accepts_only_matching_pdf_and_docx() -> None:
    assert validate_resume_upload_metadata("resume.pdf", PDF_MIME, 1_024) == "pdf"
    assert validate_resume_upload_metadata("Resume.DOCX", DOCX_MIME, 2_048) == "docx"

    with pytest.raises(ResumeExtractionError, match="PDF or DOCX"):
        validate_resume_upload_metadata("resume.pdf", DOCX_MIME, 1_024)
    with pytest.raises(ResumeExtractionError, match="8 MiB"):
        validate_resume_upload_metadata("resume.pdf", PDF_MIME, MAX_RESUME_FILE_BYTES + 1)
    with pytest.raises(ResumeExtractionError, match="must not be empty"):
        validate_resume_upload_metadata("resume.pdf", PDF_MIME, 0)


def test_docx_extracts_normalized_text() -> None:
    text = (
        "Senior data engineer with Python, SQL, PostgreSQL, AWS, Docker, and measurable "
        "production platform outcomes."
    )
    result = extract_docx_text(docx_bytes(text))
    assert result.extraction_method == "docx_xml"
    assert "Senior data engineer" in result.text
    assert result.metadata["character_count"] == len(result.text)


def test_docx_rejects_missing_document_part() -> None:
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
    with pytest.raises(ResumeExtractionError, match="missing required document parts"):
        extract_docx_text(buffer.getvalue())


def test_docx_rejects_archive_with_too_many_entries() -> None:
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr(
            "word/document.xml",
            b"<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'/>",
        )
        for index in range(MAX_DOCX_ENTRIES):
            archive.writestr(f"word/media/{index}.bin", b"x")
    with pytest.raises(ResumeExtractionError, match="too many entries"):
        extract_docx_text(buffer.getvalue())


def test_docx_rejects_archive_expanding_beyond_limit() -> None:
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr(
            "word/document.xml",
            b"<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'/>",
        )
        archive.writestr("word/media/payload.bin", b"x" * (MAX_DOCX_UNCOMPRESSED_BYTES + 1))
    with pytest.raises(ResumeExtractionError, match="safe extraction limit"):
        extract_docx_text(buffer.getvalue())


def test_pdf_rejects_invalid_magic() -> None:
    with pytest.raises(ResumeExtractionError, match="not a valid PDF"):
        extract_pdf_text(b"not-a-pdf")


def test_pdf_rejects_encryption_and_page_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeReader:
        def __init__(self, _stream: BytesIO, *, strict: bool) -> None:
            assert strict is False
            self.is_encrypted = True
            self.pages: list[object] = []

    monkeypatch.setattr(extraction, "PdfReader", FakeReader)
    with pytest.raises(ResumeExtractionError, match="password-protected"):
        extract_pdf_text(b"%PDF-fake")

    class Page:
        def extract_text(self) -> str:
            return "resume text " * 10

    class TooManyPagesReader:
        def __init__(self, _stream: BytesIO, *, strict: bool) -> None:
            assert strict is False
            self.is_encrypted = False
            self.pages = [Page() for _ in range(MAX_PDF_PAGES + 1)]

    monkeypatch.setattr(extraction, "PdfReader", TooManyPagesReader)
    with pytest.raises(ResumeExtractionError, match=str(MAX_PDF_PAGES)):
        extract_pdf_text(b"%PDF-fake")


def test_pdf_extracts_text_and_enforces_text_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    class Page:
        def __init__(self, text: str) -> None:
            self.text = text

        def extract_text(self) -> str:
            return self.text

    class Reader:
        def __init__(self, _stream: BytesIO, *, strict: bool) -> None:
            assert strict is False
            self.is_encrypted = False
            self.pages = [
                Page(
                    "Principal engineer with Python, PostgreSQL, AWS, system design, and "
                    "distributed platform experience."
                )
            ]

    monkeypatch.setattr(extraction, "PdfReader", Reader)
    result = extract_pdf_text(b"%PDF-fake")
    assert result.extraction_method == "pdf_text"
    assert result.metadata["page_count"] == 1

    class TooMuchTextReader:
        def __init__(self, _stream: BytesIO, *, strict: bool) -> None:
            assert strict is False
            self.is_encrypted = False
            self.pages = [Page("x" * (extraction.MAX_EXTRACTED_CHARS + 1))]

    monkeypatch.setattr(extraction, "PdfReader", TooMuchTextReader)
    with pytest.raises(ResumeExtractionError, match="100,000 character"):
        extract_pdf_text(b"%PDF-fake")
