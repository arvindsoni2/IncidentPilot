COMPOSE ?= docker compose -f infra/compose.yaml
RUNTIME ?= docker

.PHONY: install lint test eval check verify smoke-clean compose-check compose-build live-integration visual-smoke profile-database ci-local

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

live-integration:
	RUNTIME="$(RUNTIME)" bash scripts/live_integration.sh

visual-smoke:
	uv run python tests/visual/playwright_smoke.py

profile-database:
	uv run python scripts/profile_database.py

ci-local: verify smoke-clean compose-check compose-build
