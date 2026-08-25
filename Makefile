.PHONY: bootstrap reset-local verify-local stop-local logs-local backup-local restore-local release-local install-question-bank import-question-bank validate-question-bank test-content build-attachment-question-bank validate-attachment-question-bank sync-attachment-question-bank publish-attachment-question-bank build-attachment-execution-bank validate-attachment-execution-bank sync-attachment-execution-bank verify-attachment-question-bank-db promote-large-question-corpus

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

install-question-bank:
	@test -n "$(BANK)" || (echo "Usage: make install-question-bank BANK=/path/to/rigor_source_backed_question_bank.zip" >&2; exit 2)
	uv run python scripts/install_source_backed_question_bank.py "$(BANK)"

validate-question-bank:
	uv run python scripts/import_source_backed_question_bank.py --validate-only

import-question-bank:
	docker compose exec -T api python /app/scripts/import_source_backed_question_bank.py \
		--database-url postgresql+psycopg://rigor_migrator:rigor_migrator_local_only@postgres:5432/rigor

build-attachment-question-bank:
	@test -n "$(INPUT)" || (echo "Usage: make build-attachment-question-bank INPUT=/path/to/serving_feed_deduplicated.jsonl [OUTPUT=/path/to/output-dir]" >&2; exit 2)
	uv run python scripts/build_attachment_practice_bank.py \
		--input "$(INPUT)" \
		--output-dir "$(if $(OUTPUT),$(OUTPUT),data/question_upload/attachment-v1)"

validate-attachment-question-bank:
	@test -n "$(BANK)" || (echo "Usage: make validate-attachment-question-bank BANK=/path/to/question_bank_with_solutions_explanations.jsonl" >&2; exit 2)
	uv run python scripts/sync_attachment_question_bank.py --mode validate --input "$(BANK)"

sync-attachment-question-bank:
	@test -n "$(BANK)" || (echo "Usage: make sync-attachment-question-bank BANK=/path/to/question_bank_with_solutions_explanations.jsonl" >&2; exit 2)
	docker compose exec -T api python /app/scripts/sync_attachment_question_bank.py \
		--mode sync \
		--input "$(BANK)" \
		--database-url postgresql+psycopg://rigor_migrator:rigor_migrator_local_only@postgres:5432/rigor

publish-attachment-question-bank:
	@test -n "$(BANK)" || (echo "Usage: make publish-attachment-question-bank BANK=/path/to/question_bank_with_solutions_explanations.jsonl" >&2; exit 2)
	docker compose exec -T api python /app/scripts/sync_attachment_question_bank.py \
		--mode sync \
		--publish-all \
		--input "$(BANK)" \
		--database-url postgresql+psycopg://rigor_migrator:rigor_migrator_local_only@postgres:5432/rigor

build-attachment-execution-bank:
	@test -n "$(BANK)" || (echo "Usage: make build-attachment-execution-bank BANK=/path/to/question_bank_with_solutions_explanations.jsonl [OUTPUT=/path/to/output-dir]" >&2; exit 2)
	@mkdir -p "$(if $(OUTPUT),$(OUTPUT),data/question_upload/attachment-v2)"
	uv run python scripts/build_attachment_execution_bank.py \
		--input "$(BANK)" \
		--output "$(if $(OUTPUT),$(OUTPUT),data/question_upload/attachment-v2)/question_bank_execution_candidates.jsonl" \
		--report "$(if $(OUTPUT),$(OUTPUT),data/question_upload/attachment-v2)/execution_readiness_report.json"

validate-attachment-execution-bank:
	@test -n "$(BANK)" || (echo "Usage: make validate-attachment-execution-bank BANK=/path/to/question_bank_execution_candidates.jsonl" >&2; exit 2)
	uv run python scripts/sync_execution_ready_attachment_question_bank.py --mode validate --input "$(BANK)"

sync-attachment-execution-bank:
	@test -n "$(BANK)" || (echo "Usage: make sync-attachment-execution-bank BANK=/path/to/question_bank_execution_candidates.jsonl" >&2; exit 2)
	docker compose exec -T api python /app/scripts/sync_execution_ready_attachment_question_bank.py \
		--mode sync \
		--publish-all \
		--source-revision attachment-question-bank-v2-execution \
		--input "$(BANK)" \
		--database-url postgresql+psycopg://rigor_migrator:rigor_migrator_local_only@postgres:5432/rigor

verify-attachment-question-bank-db:
	docker compose exec -T api python /app/scripts/verify_attachment_question_bank_db.py \
		--database-url postgresql+psycopg://rigor_migrator:rigor_migrator_local_only@postgres:5432/rigor \
		--expected "$(if $(EXPECTED),$(EXPECTED),11979)" \
		--version attachment-v2-execution

promote-large-question-corpus:
	@test -n "$(INPUT)" || (echo "Usage: make promote-large-question-corpus INPUT=/path/to/corpus.parquet OUTPUT=/path/to/promoted.jsonl REPORT=/path/to/report.json" >&2; exit 2)
	@test -n "$(OUTPUT)" || (echo "OUTPUT is required" >&2; exit 2)
	@test -n "$(REPORT)" || (echo "REPORT is required" >&2; exit 2)
	uv run python scripts/promote_large_question_corpus.py --input "$(INPUT)" --output "$(OUTPUT)" --report "$(REPORT)"

test-content:
	uv run python scripts/validate_content.py
	uv run python scripts/test_content_references.py
	@if [ -f content/imported/source-backed/question-bank.zip.b64 ]; then \
		uv run python scripts/import_source_backed_question_bank.py --validate-only; \
	fi
