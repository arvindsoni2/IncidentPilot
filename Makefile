COMPOSE ?= docker compose -f infra/compose.yaml

.PHONY: install lint test eval check verify smoke-clean compose-check compose-build ci-local

install:
	uv sync --group dev

lint:
	uv run ruff check .

test:
	uv run pytest

eval:
	uv run incidentpilot evals run

check: lint test

verify: check eval

smoke-clean:
	bash scripts/clean_checkout_smoke.sh

compose-check:
	$(COMPOSE) config --quiet

compose-build:
	$(COMPOSE) build

ci-local: verify smoke-clean compose-check compose-build
