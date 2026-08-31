from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from typing import Literal
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_RESUME_FILE_BYTES = 8 * 1024 * 1024
MAX_PDF_PAGES = 30
MAX_EXTRACTED_CHARS = 100_000
MIN_EXTRACTED_CHARS = 40
MAX_DOCX_ENTRIES = 2_048
MAX_DOCX_UNCOMPRESSED_BYTES = 24 * 1024 * 1024
MAX_DOCX_XML_BYTES = 12 * 1024 * 1024

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

ResumeFormat = Literal["pdf", "docx"]
ExtractionMethod = Literal["pdf_text", "docx_xml"]


class ResumeExtractionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ResumeExtractionResult:
    text: str
    extraction_method: ExtractionMethod
    metadata: dict[str, int | str]


def _normalized_extension(file_name: str) -> str:
    return PurePosixPath(file_name.replace("\\", "/")).suffix.casefold()


def validate_resume_upload_metadata(
    file_name: str,
    mime_type: str,
    size_bytes: int,
) -> ResumeFormat:
    if size_bytes <= 0:
        raise ResumeExtractionError("empty_file", "Resume file must not be empty.")
    if size_bytes > MAX_RESUME_FILE_BYTES:
        raise ResumeExtractionError(
            "resume_too_large",
            "Resume files are limited to 8 MiB.",
        )

    extension = _normalized_extension(file_name)
    normalized_mime = mime_type.split(";", 1)[0].strip().casefold()
    if extension == ".pdf" and normalized_mime == PDF_MIME:
        return "pdf"
    if extension == ".docx" and normalized_mime == DOCX_MIME:
        return "docx"
    raise ResumeExtractionError(
        "unsupported_resume_type",
        "Resume must be a PDF or DOCX with a matching file type.",
    )


def _normalize_extracted_text(value: str) -> str:
    value = value.replace("\x00", "")
    lines: list[str] = []
    for raw_line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = re.sub(r"[\t\f\v ]+", " ", raw_line).strip()
        if line:
            lines.append(line)
    normalized = "\n".join(lines).strip()
    if len(normalized) < MIN_EXTRACTED_CHARS:
        raise ResumeExtractionError(
            "insufficient_text",
            "Resume did not contain enough extractable text.",
        )
    if len(normalized) > MAX_EXTRACTED_CHARS:
        raise ResumeExtractionError(
            "extracted_text_too_large",
            "Extracted resume text exceeds the 100,000 character limit.",
        )
    return normalized


def extract_pdf_text(data: bytes) -> ResumeExtractionResult:
    if not data.startswith(b"%PDF-"):
        raise ResumeExtractionError("invalid_pdf_signature", "Uploaded file is not a valid PDF.")
    try:
        reader = PdfReader(BytesIO(data), strict=False)
    except (PdfReadError, ValueError, TypeError) as exc:
        raise ResumeExtractionError("malformed_pdf", "PDF could not be parsed.") from exc

    if reader.is_encrypted:
        raise ResumeExtractionError(
            "encrypted_pdf",
            "Encrypted or password-protected PDFs are not supported.",
        )
    page_count = len(reader.pages)
    if page_count == 0:
        raise ResumeExtractionError("empty_pdf", "PDF contains no pages.")
    if page_count > MAX_PDF_PAGES:
        raise ResumeExtractionError(
            "pdf_page_limit",
            f"PDF resumes are limited to {MAX_PDF_PAGES} pages.",
        )

    parts: list[str] = []
    extracted_chars = 0
    try:
        for page in reader.pages:
            page_text = page.extract_text() or ""
            extracted_chars += len(page_text)
            if extracted_chars > MAX_EXTRACTED_CHARS:
                raise ResumeExtractionError(
                    "extracted_text_too_large",
                    "Extracted resume text exceeds the 100,000 character limit.",
                )
            parts.append(page_text)
    except ResumeExtractionError:
        raise
    except Exception as exc:
        raise ResumeExtractionError("pdf_text_error", "PDF text extraction failed.") from exc

    text = _normalize_extracted_text("\n".join(parts))
    return ResumeExtractionResult(
        text=text,
        extraction_method="pdf_text",
        metadata={"page_count": page_count, "character_count": len(text)},
    )


def _validate_docx_archive(archive: ZipFile) -> None:
    entries = archive.infolist()
    if len(entries) > MAX_DOCX_ENTRIES:
        raise ResumeExtractionError(
            "docx_entry_limit",
            "DOCX archive contains too many entries.",
        )
    total_uncompressed = 0
    for entry in entries:
        path = PurePosixPath(entry.filename)
        if path.is_absolute() or ".." in path.parts:
            raise ResumeExtractionError("unsafe_docx_path", "DOCX archive contains an unsafe path.")
        total_uncompressed += entry.file_size
        if total_uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
            raise ResumeExtractionError(
                "docx_uncompressed_limit",
                "DOCX archive expands beyond the safe extraction limit.",
            )
    names = {entry.filename for entry in entries}
    if "[Content_Types].xml" not in names or "word/document.xml" not in names:
        raise ResumeExtractionError("malformed_docx", "DOCX is missing required document parts.")


def _docx_xml_text(root: ElementTree.Element) -> str:
    output: list[str] = []

    def walk(element: ElementTree.Element) -> None:
        local_name = element.tag.rsplit("}", 1)[-1]
        if local_name == "t" and element.text:
            output.append(element.text)
        elif local_name == "tab":
            output.append("\t")
        elif local_name in {"br", "cr"}:
            output.append("\n")
        for child in element:
            walk(child)
        if local_name in {"p", "tr"}:
            output.append("\n")

    walk(root)
    return "".join(output)


def extract_docx_text(data: bytes) -> ResumeExtractionResult:
    if not data.startswith(b"PK"):
        raise ResumeExtractionError("invalid_docx_signature", "Uploaded file is not a valid DOCX.")
    try:
        with ZipFile(BytesIO(data)) as archive:
            _validate_docx_archive(archive)
            document_info = archive.getinfo("word/document.xml")
            if document_info.file_size > MAX_DOCX_XML_BYTES:
                raise ResumeExtractionError(
                    "docx_xml_limit",
                    "DOCX document XML exceeds the safe extraction limit.",
                )
            document_xml = archive.read("word/document.xml")
            try:
                root = ElementTree.fromstring(document_xml)
            except ElementTree.ParseError as exc:
                raise ResumeExtractionError(
                    "malformed_docx_xml",
                    "DOCX document XML could not be parsed.",
                ) from exc
            text = _normalize_extracted_text(_docx_xml_text(root))
            return ResumeExtractionResult(
                text=text,
                extraction_method="docx_xml",
                metadata={
                    "archive_entries": len(archive.infolist()),
                    "character_count": len(text),
                },
            )
    except ResumeExtractionError:
        raise
    except (BadZipFile, KeyError, ValueError, OSError) as exc:
        raise ResumeExtractionError("malformed_docx", "DOCX could not be parsed.") from exc


def extract_resume_text(
    data: bytes,
    file_name: str,
    mime_type: str,
) -> ResumeExtractionResult:
    resume_format = validate_resume_upload_metadata(file_name, mime_type, len(data))
    if resume_format == "pdf":
        return extract_pdf_text(data)
    return extract_docx_text(data)
