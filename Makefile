.PHONY: bootstrap reset-local verify-local

bootstrap:
	./scripts/start-populated-local

reset-local:
	docker compose down --volumes --remove-orphans
	./scripts/start-populated-local

verify-local:
	docker compose config --quiet
	curl --fail --silent http://localhost:8002/readyz
	curl --fail --silent http://localhost:3001 >/dev/null

