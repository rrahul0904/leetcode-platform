"""Add large-corpus serving metadata, import checkpoints, and runtime links.

Revision ID: 20260824_0016
Revises: 20260802_0015
Create Date: 2026-08-24
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260824_0016"
down_revision: str | None = "20260802_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE knowledge_corpus_import_batches (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          corpus_name text NOT NULL,
          corpus_version text NOT NULL,
          batch_id text NOT NULL,
          source_filename text NOT NULL,
          source_sha256 varchar(64) NOT NULL,
          manifest_sha256 varchar(64),
          expected_rows bigint,
          physical_rows bigint,
          checkpoint_row bigint NOT NULL DEFAULT 0,
          status text NOT NULL DEFAULT 'pending',
          counters jsonb NOT NULL DEFAULT '{}'::jsonb,
          failure_summary jsonb NOT NULL DEFAULT '[]'::jsonb,
          started_at timestamptz,
          completed_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          CONSTRAINT uq_knowledge_corpus_batch
            UNIQUE (corpus_name, corpus_version, batch_id),
          CONSTRAINT ck_knowledge_corpus_batch_sha
            CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
          CONSTRAINT ck_knowledge_corpus_manifest_sha
            CHECK (manifest_sha256 IS NULL OR manifest_sha256 ~ '^[0-9a-f]{64}$'),
          CONSTRAINT ck_knowledge_corpus_batch_counts
            CHECK (
              checkpoint_row >= 0
              AND (expected_rows IS NULL OR expected_rows >= 0)
              AND (physical_rows IS NULL OR physical_rows >= 0)
            ),
          CONSTRAINT ck_knowledge_corpus_batch_status
            CHECK (status IN ('pending', 'running', 'blocked', 'failed', 'completed'))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_knowledge_corpus_batch_status
        ON knowledge_corpus_import_batches
          (corpus_name, corpus_version, status, updated_at DESC)
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_knowledge_corpus_batch_identity()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF NEW.source_filename IS DISTINCT FROM OLD.source_filename
             OR NEW.source_sha256 IS DISTINCT FROM OLD.source_sha256
             OR NEW.manifest_sha256 IS DISTINCT FROM OLD.manifest_sha256
             OR NEW.expected_rows IS DISTINCT FROM OLD.expected_rows
             OR NEW.physical_rows IS DISTINCT FROM OLD.physical_rows THEN
            RAISE EXCEPTION
              'knowledge corpus batch source identity is immutable for %/%/%',
              OLD.corpus_name, OLD.corpus_version, OLD.batch_id;
          END IF;

          IF NEW.checkpoint_row < OLD.checkpoint_row THEN
            NEW.checkpoint_row := OLD.checkpoint_row;
          END IF;

          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_knowledge_corpus_batch_identity
        BEFORE UPDATE ON knowledge_corpus_import_batches
        FOR EACH ROW EXECUTE FUNCTION enforce_knowledge_corpus_batch_identity()
        """
    )

    op.execute(
        """
        CREATE TABLE knowledge_problem_serving_metadata (
          problem_id uuid PRIMARY KEY
            REFERENCES knowledge_problems(id) ON DELETE CASCADE,
          corpus_batch_id uuid
            REFERENCES knowledge_corpus_import_batches(id) ON DELETE RESTRICT,
          source_question_id text NOT NULL,
          source_row_number bigint NOT NULL,
          corpus_version text NOT NULL,
          content_fingerprint varchar(64) NOT NULL,
          canonical_classification text NOT NULL,
          platform text,
          subtopic text,
          seniority text,
          industry text,
          business_context text,
          original_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          CONSTRAINT ck_knowledge_serving_source_row
            CHECK (source_row_number >= 1),
          CONSTRAINT ck_knowledge_serving_fingerprint
            CHECK (content_fingerprint ~ '^[0-9a-f]{64}$'),
          CONSTRAINT ck_knowledge_serving_classification
            CHECK (canonical_classification IN (
              'canonical_candidate',
              'legitimate_variant',
              'near_concept_duplicate',
              'reference_only',
              'runnable_candidate',
              'review_required',
              'rejected_quarantined'
            )),
          CONSTRAINT uq_knowledge_serving_source_identity
            UNIQUE (corpus_version, source_question_id),
          CONSTRAINT uq_knowledge_serving_fingerprint
            UNIQUE (corpus_version, content_fingerprint)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_knowledge_serving_filters
        ON knowledge_problem_serving_metadata
          (canonical_classification, platform, seniority, industry, subtopic)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_knowledge_serving_batch
        ON knowledge_problem_serving_metadata (corpus_batch_id, source_row_number)
        """
    )

    op.execute(
        """
        CREATE TABLE knowledge_problem_runtime_links (
          problem_id uuid PRIMARY KEY
            REFERENCES knowledge_problems(id) ON DELETE CASCADE,
          question_id uuid NOT NULL
            REFERENCES questions(id) ON DELETE RESTRICT,
          question_version_id uuid NOT NULL
            REFERENCES question_versions(id) ON DELETE RESTRICT,
          runtime text NOT NULL,
          link_status text NOT NULL DEFAULT 'review',
          package_hash varchar(64),
          verification_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
          verified_at timestamptz,
          revoked_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
          CONSTRAINT ck_knowledge_runtime_link_runtime
            CHECK (runtime IN ('python', 'postgresql')),
          CONSTRAINT ck_knowledge_runtime_link_status
            CHECK (link_status IN ('review', 'verified', 'revoked')),
          CONSTRAINT ck_knowledge_runtime_link_hash
            CHECK (package_hash IS NULL OR package_hash ~ '^[0-9a-f]{64}$'),
          CONSTRAINT ck_knowledge_runtime_link_verified
            CHECK (
              link_status <> 'verified'
              OR (package_hash IS NOT NULL AND verified_at IS NOT NULL)
            ),
          CONSTRAINT ck_knowledge_runtime_link_revoked
            CHECK (link_status <> 'revoked' OR revoked_at IS NOT NULL)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_knowledge_runtime_link_lookup
        ON knowledge_problem_runtime_links
          (link_status, runtime, question_version_id)
        """
    )

    # A browser may create low-trust interaction evidence, but it must never be
    # able to manufacture Run/Submit/solve/fail outcomes. Trusted execution
    # projection explicitly enables the transaction-local session flag before
    # inserting those durable events.
    op.execute("DROP POLICY IF EXISTS knowledge_activity_owner ON knowledge_activity_events")
    op.execute(
        """
        CREATE POLICY knowledge_activity_owner_read
        ON knowledge_activity_events
        FOR SELECT
        USING (
          candidate_id=NULLIF(current_setting('rigor.user_id', true), '')::uuid
          OR (session_user='rigor_migrator'
              AND current_setting('rigor.maintenance_bypass', true)='on')
        )
        """
    )
    op.execute(
        """
        CREATE POLICY knowledge_activity_owner_insert
        ON knowledge_activity_events
        FOR INSERT
        WITH CHECK (
          (session_user='rigor_migrator'
           AND current_setting('rigor.maintenance_bypass', true)='on')
          OR (
            candidate_id=NULLIF(current_setting('rigor.user_id', true), '')::uuid
            AND (
              event_type IN (
                'problem_viewed', 'session_started', 'draft_saved',
                'bookmark_changed', 'revision_changed', 'notes_saved',
                'session_time_recorded'
              )
              OR (
                current_setting('rigor.trusted_evidence', true)='on'
                AND event_type IN (
                  'public_tests_run', 'submission_completed',
                  'problem_solved', 'problem_failed'
                )
              )
            )
          )
        )
        """
    )

    # Candidate-serving roles may read these facts. Only migration/admin paths
    # should mutate import identities or runtime verification state.
    op.execute("GRANT SELECT ON knowledge_corpus_import_batches TO rigor_app")
    op.execute("GRANT SELECT ON knowledge_problem_serving_metadata TO rigor_app")
    op.execute("GRANT SELECT ON knowledge_problem_runtime_links TO rigor_app")
    op.execute("GRANT SELECT ON knowledge_corpus_import_batches TO rigor_readonly")
    op.execute("GRANT SELECT ON knowledge_problem_serving_metadata TO rigor_readonly")
    op.execute("GRANT SELECT ON knowledge_problem_runtime_links TO rigor_readonly")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS knowledge_activity_owner_insert ON knowledge_activity_events")
    op.execute("DROP POLICY IF EXISTS knowledge_activity_owner_read ON knowledge_activity_events")
    op.execute(
        """
        CREATE POLICY knowledge_activity_owner
        ON knowledge_activity_events
        USING (
          candidate_id=NULLIF(current_setting('rigor.user_id', true), '')::uuid
          OR (session_user='rigor_migrator'
              AND current_setting('rigor.maintenance_bypass', true)='on')
        )
        WITH CHECK (
          candidate_id=NULLIF(current_setting('rigor.user_id', true), '')::uuid
          OR (session_user='rigor_migrator'
              AND current_setting('rigor.maintenance_bypass', true)='on')
        )
        """
    )
    op.execute("DROP TABLE IF EXISTS knowledge_problem_runtime_links")
    op.execute("DROP TABLE IF EXISTS knowledge_problem_serving_metadata")
    op.execute("DROP TRIGGER IF EXISTS trg_knowledge_corpus_batch_identity ON knowledge_corpus_import_batches")
    op.execute("DROP FUNCTION IF EXISTS enforce_knowledge_corpus_batch_identity()")
    op.execute("DROP TABLE IF EXISTS knowledge_corpus_import_batches")
