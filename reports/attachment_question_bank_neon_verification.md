# Isolated PostgreSQL verification environment

An isolated PostgreSQL 18-compatible Neon project was provisioned for question-bank verification so existing production data is not modified.

The external database connector accepts SQL statements but does not accept the local 63 MB JSONL artifact as a file upload. Therefore the release proof is split deliberately:

1. Full source artifact: validate all 11,979 rows locally and build the execution-enriched JSONL with a content SHA-256.
2. PostgreSQL behavior: use the isolated database for schema/index/query/runtime checks with real corpus records.
3. Full application-table proof: run `sync_execution_ready_attachment_question_bank.py` wherever the artifact is mounted, then require `verify_attachment_question_bank_db.py --expected 11979` to pass.

This document must not be interpreted as a claim that all 11,979 full-content records were copied through the SQL-only verification connector.
