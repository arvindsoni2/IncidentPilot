COMPOSE ?= docker compose -f infra/compose.yaml

.PHONY: install lint test eval check verify compose-check compose-build ci-local

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

compose-check:
	$(COMPOSE) config --quiet

compose-build:
	$(COMPOSE) build

ci-local: verify compose-check compose-build
