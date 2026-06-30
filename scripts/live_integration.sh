#!/usr/bin/env bash
set -euo pipefail

runtime="${RUNTIME:-docker}"
case "${runtime}" in
  docker)
    compose=(docker compose -f infra/compose.yaml)
    ;;
  podman)
    compose=(podman compose -f infra/compose.yaml)
    ;;
  *)
    echo "Unsupported runtime: ${runtime}" >&2
    exit 2
    ;;
esac

cleanup() {
  "${compose[@]}" up -d postgres backend frontend >/dev/null 2>&1 || true
  "${compose[@]}" down -v >/dev/null 2>&1 || true
}
trap cleanup EXIT

"${compose[@]}" up -d --build

export INCIDENTPILOT_LIVE_TESTS=1
export INCIDENTPILOT_DEFAULT_RUNTIME="${runtime}"
export INCIDENTPILOT_CONFIG_FILE="${PWD}/config.example.yaml"
database_path="/tmp/incidentpilot-live-${runtime}.db"
rm -f "${database_path}"
export INCIDENTPILOT_DATABASE_URL="sqlite:///${database_path}"
export INCIDENTPILOT_EVAL_OUTPUT_DIRECTORY="/tmp/incidentpilot-live-evals-${runtime}"
export LLM_TIMEOUT_SECONDS=2
export LLM_MAX_RETRIES=0

uv run pytest tests/live -m live
