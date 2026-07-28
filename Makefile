.PHONY: bootstrap reset-local verify-local test-content

bootstrap:
	./scripts/start-populated-local

reset-local:
	docker compose down --volumes --remove-orphans
	./scripts/start-populated-local

verify-local:
	docker compose config --quiet
	curl --fail --silent http://localhost:8002/readyz
	curl --fail --silent http://localhost:3001 >/dev/null

test-content:
	uv run python scripts/validate_content.py
	uv run python scripts/test_content_references.py
