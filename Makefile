.PHONY: bootstrap reset-local verify-local stop-local logs-local backup-local restore-local release-local observability-local verify-observability capacity-local test-content

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

observability-local:
	docker compose -f compose.yaml -f compose.observability.yaml --profile observability up -d --wait execution-metrics prometheus otel-collector grafana

verify-observability:
	docker compose -f compose.yaml -f compose.observability.yaml --profile observability config --quiet
	curl --fail --silent http://localhost:9090/-/ready >/dev/null
	curl --fail --silent http://localhost:3002/api/health >/dev/null
	docker compose -f compose.yaml -f compose.observability.yaml --profile observability exec -T prometheus wget -qO- http://execution-metrics:9108/metrics | grep -q '^rigor_execution_metrics_up 1$$'
	docker compose -f compose.yaml -f compose.observability.yaml --profile observability exec -T prometheus wget -qO- 'http://localhost:9090/api/v1/query?query=rigor_execution_queue_depth' | grep -q '"status":"success"'

capacity-local:
	sh scripts/benchmark-local

test-content:
	uv run python scripts/validate_content.py
	uv run python scripts/test_content_references.py
