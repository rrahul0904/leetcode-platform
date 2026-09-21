# CODEX IMPLEMENTATION PROMPT — CareerOS Wave 3: Resume Ingestion

## Mission

Extend the existing SkillForge CareerOS implementation with a production-oriented resume ingestion path.

Do **not** create a new repository, Vercel project, standalone application, authentication system, upload system, or database. Work only in:

- repository: `rrahul0904/leetcode-platform`
- base branch: `agent/careeros-wave-2`
- implementation branch: `agent/careeros-wave-3-resume-ingestion`

This wave must reuse the existing candidate authentication boundary, private `candidate_files` object-storage flow, PostgreSQL RLS conventions, CareerOS persistence, and `/career` product surface.

## End-to-end user flow

```text
Candidate chooses resume.pdf / resume.docx
  -> browser computes SHA-256
  -> existing /api/v1/files/presign-upload (category=resume)
  -> browser PUTs directly to private S3
  -> CareerOS extraction endpoint verifies the candidate-owned object
  -> bounded PDF/DOCX text extraction
  -> career_documents stores normalized text + file provenance
  -> /career uses document_id for job analysis
  -> candidate sees fit/gaps/interview pack
```

The pasted-text resume workflow must remain available as a fallback.

## Non-negotiable security and product invariants

1. Raw resume binaries remain in private object storage. Do not store PDF/DOCX bytes in PostgreSQL.
2. A candidate may never read, extract, analyze, or mutate another candidate's file or CareerOS document.
3. Resume uploads are limited to PDF and DOCX for this wave.
4. Resume extraction has a stricter limit than the generic candidate-file system: maximum 8 MiB per resume.
5. PDF extraction is text-only. Do not add OCR in this wave.
6. Reject encrypted PDFs, malformed PDFs, oversized PDFs, PDFs above 30 pages, malformed DOCX archives, and DOCX zip bombs.
7. Extracted text is capped at 100,000 characters and must contain at least 40 non-whitespace characters.
8. Do not trust client MIME metadata alone. Verify PDF magic bytes and DOCX ZIP/document structure.
9. If an uploaded object does not match recorded size/checksum, quarantine the `candidate_files` row and do not create a CareerOS document.
10. Extraction is idempotent per `candidate_file_id`.
11. Job analysis accepts a candidate-owned `document_id` so the browser does not need to resend extracted resume text.
12. Keep deterministic job-fit analysis working without an LLM key.
13. Do not deploy or merge automatically. Open a stacked draft PR and require green CI.

## Backend implementation

### 1. Migration `20260831_0020`

Extend `career_documents` with:

- `candidate_file_id UUID NULL REFERENCES candidate_files(id) ON DELETE SET NULL`
- `extraction_method VARCHAR(32) NOT NULL DEFAULT 'pasted'`
- `extraction_metadata JSONB NOT NULL DEFAULT '{}'::jsonb`

Add:

- partial unique index for non-null `candidate_file_id`
- check constraint allowing `pasted`, `pdf_text`, `docx_xml`

Update database readiness and migration-cycle assertions to `20260831_0020` and require the new columns/index/RLS-preserving table.

### 2. Resume extractor module

Create a focused module such as `rigor_api/resume_extraction.py`.

Expose pure/testable functions:

- `validate_resume_upload_metadata(file_name, mime_type, size_bytes)`
- `extract_resume_text(data, file_name, mime_type)`
- `extract_pdf_text(data)`
- `extract_docx_text(data)`

Limits:

- `MAX_RESUME_FILE_BYTES = 8 * 1024 * 1024`
- `MAX_PDF_PAGES = 30`
- `MAX_EXTRACTED_CHARS = 100_000`
- bounded DOCX archive entry count and bounded uncompressed archive size

Use `pypdf` for text-bearing PDF extraction. DOCX parsing may use the Python standard library (`zipfile` + `xml.etree.ElementTree`) so no second document library is required.

### 3. Object retrieval

Reuse `S3Presigner` from the existing object-storage module. The extraction endpoint may generate a short-lived candidate-owned GET URL and retrieve at most `MAX_RESUME_FILE_BYTES + 1` bytes with a strict timeout.

Do not expose storage credentials to the client. Do not make arbitrary URL-fetch endpoints.

### 4. Candidate file lifecycle

Enhance the existing presign flow for `category=resume`:

- reject non-PDF/DOCX extension/MIME combinations
- reject resume size > 8 MiB

Extraction endpoint behavior:

- pending upload + valid object -> extract -> mark file `available`
- checksum/size/signature mismatch -> mark `quarantined`, return validation error
- invalid/malformed document -> mark `quarantined`, return validation error
- already extracted candidate file -> return existing CareerOS document idempotently
- foreign candidate file -> 404, not 403

### 5. CareerOS API

Add:

`POST /api/v1/career/resumes/{file_id}/extract`

Response should include at least:

- `document_id`
- `candidate_file_id`
- `file_name`
- `mime_type`
- `extraction_method`
- `character_count`
- `created_at`

Modify job analysis request contract to accept exactly one of:

- `resume_text`
- `document_id`

When `document_id` is supplied, load the candidate-owned `career_documents.raw_text` server-side and use the existing deterministic analyzer. Save the analysis against that same document id.

## Web implementation

Update `/career` with a resume source control:

- `Upload PDF/DOCX`
- `Paste resume text`

Upload path:

1. validate extension/type/8 MiB limit locally
2. SHA-256 with browser Web Crypto
3. call existing presign endpoint with `category=resume`
4. PUT directly to returned S3 URL
5. call CareerOS extraction endpoint
6. store returned `document_id` in component state
7. analyze jobs using `document_id`

UI states must be explicit:

- hashing
- uploading
- extracting
- ready
- failed

Show the selected file name and extracted character count. Let the user remove/replace the uploaded resume before analysis.

Keep pasted resume text working independently.

## Tests

Backend tests must cover:

- resume metadata allow/reject cases
- DOCX text extraction from an in-memory ZIP fixture
- malformed DOCX rejection
- zip-bomb/uncompressed-size rejection
- PDF magic validation
- PDF page limit / encrypted PDF rejection
- extraction text length limits
- checksum and size mismatch quarantine behavior
- successful candidate-owned extraction
- idempotent re-extraction
- foreign-candidate file isolation
- analysis using `document_id`
- pasted-text analysis remains compatible

Web tests must cover:

- file type/size validation
- presign -> PUT -> extract sequence
- document-id analysis payload
- pasted text fallback
- upload failure and extraction failure states

## CI acceptance

All must pass:

```bash
uv sync --frozen --all-packages
uv run ruff check apps/api/src apps/api/tests
uv run pyright apps/api/src packages/question-schema/src scripts
uv run pytest -q
pnpm --filter @rigor/web lint
pnpm --filter @rigor/web typecheck
pnpm --filter @rigor/web test
pnpm --filter @rigor/web build
uv run alembic upgrade head
```

The migration-cycle workflow must also prove downgrade/re-upgrade succeeds and the expected head is `20260831_0020`.

## Explicitly out of scope for this wave

- OCR / scanned-resume recognition
- AI resume rewriting
- cover-letter generation
- automated job application submission
- email sending
- recruiter scraping
- a second storage provider
- a second auth system
- production deployment

## Definition of done

A candidate can upload a text-bearing PDF or DOCX resume, have it safely extracted into a candidate-owned CareerOS document, analyze a target job by document id, refresh the page without losing the persisted document/job history, and remain isolated from every other candidate by server authorization and PostgreSQL RLS.
