.PHONY: bootstrap reset-local verify-local stop-local logs-local backup-local restore-local release-local release-check rebuild-question-bank install-question-bank import-question-bank validate-question-bank assess-question-bank materialize-question-bank test-content release-agents release-agents-enforce

SOURCE_REVIEW_OUTPUT ?= content/imported/source-backed/materialized/python
SOURCE_BANK_ARCHIVE ?= content/imported/source-backed/question-bank.zip.b64
SOURCE_BANK_REBUILD_WORK ?= .work/source-bank-rebuild
SOURCE_BANK_AGENT_WORK ?= .work/source-bank-release-agents
SOURCE_ARCHIVE_DIR ?=
REVIEWED_CORPUS ?=
RELEASE_DATABASE_URL ?=
GOVERNANCE_APPROVAL ?=
RUN_SUBMIT_PROOF ?=

bootstrap:
	./scripts/start-populated-local

reset-local:
	docker compose down --volumes --remove-orphans
	./scripts/start-populated-local

verify-local:
	docker compose config --quiet
	curl --fail --silent http://localhost:8002/readyz
	curl --fail --silent http://localhost:3001 >/dev/null
	docker compose exec -T execution-controller python -m rigor_api.local_execution_health

stop-local:
	docker compose down --remove-orphans

logs-local:
	docker compose logs --tail=200 web api execution-controller python-runner sql-runner postgres valkey

backup-local:
	sh scripts/backup-local

restore-local:
	@test -n "$(BACKUP)" || (echo "Usage: make restore-local BACKUP=backups/<backup-directory>" >&2; exit 2)
	sh scripts/restore-local "$(BACKUP)"

release-local:
	sh scripts/release-local

# Reconstruct the reviewed bank from repository-pinned upstream revisions. This is
# intentionally fail closed while any source in source-lock.json is unresolved.
rebuild-question-bank:
	uv run python scripts/rebuild_source_backed_question_bank.py \
		--work "$(SOURCE_BANK_REBUILD_WORK)" \
		--install \
		--install-target "$(SOURCE_BANK_ARCHIVE)"

# Full PR release gate. A committed binary corpus is not required when the exact
# reviewed corpus can be deterministically reconstructed, but reconstruction must
# succeed from the checked-in lock before the rest of the release evidence runs.
release-check: rebuild-question-bank
	$(MAKE) test-content
	$(MAKE) validate-question-bank
	$(MAKE) assess-question-bank
	sh scripts/release-local

# Multi-agent source-bank audit. Missing external evidence is reported as BLOCKED
# while hard contradictions/errors are reported as FAIL. Use the enforce target
# when every release concern must be green.
release-agents:
	uv run python scripts/source_bank_release_agents.py \
		--work "$(SOURCE_BANK_AGENT_WORK)" \
		$(if $(SOURCE_ARCHIVE_DIR),--source-archive-dir "$(SOURCE_ARCHIVE_DIR)",) \
		$(if $(REVIEWED_CORPUS),--reviewed-corpus "$(REVIEWED_CORPUS)",) \
		$(if $(RELEASE_DATABASE_URL),--database-url "$(RELEASE_DATABASE_URL)",) \
		$(if $(GOVERNANCE_APPROVAL),--approval-file "$(GOVERNANCE_APPROVAL)",) \
		$(if $(RUN_SUBMIT_PROOF),--run-submit-proof "$(RUN_SUBMIT_PROOF)",)

release-agents-enforce:
	uv run python scripts/source_bank_release_agents.py \
		--work "$(SOURCE_BANK_AGENT_WORK)" \
		$(if $(SOURCE_ARCHIVE_DIR),--source-archive-dir "$(SOURCE_ARCHIVE_DIR)",) \
		$(if $(REVIEWED_CORPUS),--reviewed-corpus "$(REVIEWED_CORPUS)",) \
		$(if $(RELEASE_DATABASE_URL),--database-url "$(RELEASE_DATABASE_URL)",) \
		$(if $(GOVERNANCE_APPROVAL),--approval-file "$(GOVERNANCE_APPROVAL)",) \
		$(if $(RUN_SUBMIT_PROOF),--run-submit-proof "$(RUN_SUBMIT_PROOF)",) \
		--enforce-release

install-question-bank:
	@test -n "$(BANK)" || (echo "Usage: make install-question-bank BANK=/path/to/rigor_source_backed_question_bank.zip" >&2; exit 2)
	uv run python scripts/install_source_backed_question_bank.py "$(BANK)"

validate-question-bank:
	uv run python scripts/import_source_backed_question_bank.py --validate-only

assess-question-bank:
	@test -f "$(SOURCE_BANK_ARCHIVE)" || (echo "Install or rebuild the source-backed bank before assessment" >&2; exit 2)
	uv run python scripts/assess_source_backed_candidates.py \
		--output content/imported/source-backed/readiness.json

# Source-backed IMP-* packages are review artifacts until publication approval.
# Materialize them outside content/questions so the canonical content synchronizer
# cannot mistake review-stage packages for approved native catalog entries.
materialize-question-bank:
	uv run python scripts/source_python_batch.py >/dev/null
	uv run python scripts/install_source_python_packages.py \
		--output "$(SOURCE_REVIEW_OUTPUT)" --force
	uv run python scripts/install_source_python_packages.py \
		--output "$(SOURCE_REVIEW_OUTPUT)" --check >/dev/null

import-question-bank:
	docker compose exec -T api python /app/scripts/import_source_backed_question_bank.py \
		--database-url postgresql+psycopg://rigor_migrator:rigor_migrator_local_only@postgres:5432/rigor

test-content: materialize-question-bank
	uv run python scripts/validate_content.py \
		--extra-package-root "$(SOURCE_REVIEW_OUTPUT)"
	uv run python scripts/test_content_references.py \
		--extra-package-root "$(SOURCE_REVIEW_OUTPUT)"
	@if [ -f "$(SOURCE_BANK_ARCHIVE)" ]; then \
		uv run python scripts/import_source_backed_question_bank.py --validate-only; \
		uv run python scripts/assess_source_backed_candidates.py --output /tmp/source-backed-readiness.json; \
	fi
