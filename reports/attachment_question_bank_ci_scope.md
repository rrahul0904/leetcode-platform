# Attachment question-bank CI scope

The repository-wide CI already runs on pull requests and provides PostgreSQL 18, migrations, seeded taxonomy, Ruff, Pyright, Pytest, execution-image builds, and security scans. The attachment-bank changes intentionally use that existing gate rather than creating a weaker parallel pipeline.

Additional attachment-focused tests live in `tests/test_attachment_execution_bank.py` and the exact database release check lives in `scripts/verify_attachment_question_bank_db.py`.
