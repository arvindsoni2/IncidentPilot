#!/usr/bin/env bash
set -euo pipefail

workspace="$(mktemp -d)"
server_pid=""

cleanup() {
  if [[ -n "${server_pid}" ]]; then
    kill "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
  rm -rf "${workspace}"
}
trap cleanup EXIT

git archive HEAD | tar -xf - -C "${workspace}"
cd "${workspace}"

uv sync --locked --group dev
export INCIDENTPILOT_DATABASE_URL="sqlite:///${workspace}/smoke.db"
export INCIDENTPILOT_CONFIG_FILE="${workspace}/config.example.yaml"
uv run incidentpilot db init
uv run incidentpilot version

uv run incidentpilot web --host 127.0.0.1 --port 18083 \
  >"${workspace}/web.log" 2>&1 &
server_pid=$!

for _attempt in {1..20}; do
  if curl --fail --silent http://127.0.0.1:18083/health \
    >/dev/null; then
    echo "Clean-checkout installation and startup smoke test passed."
    exit 0
  fi
  sleep 0.5
done

cat "${workspace}/web.log"
echo "Clean-checkout web startup did not become healthy." >&2
exit 1
