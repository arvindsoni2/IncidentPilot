#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
COMPOSE_FILE="$SCRIPT_DIR/../../infra/compose.yaml"
RUNTIME="${INCIDENTPILOT_RUNTIME:-docker}"

case "$RUNTIME" in
  docker)
    COMPOSE_COMMAND="docker compose"
    ;;
  podman)
    COMPOSE_COMMAND="podman compose"
    ;;
  *)
    echo "Unsupported runtime: $RUNTIME (expected docker or podman)" >&2
    exit 2
    ;;
esac

run_compose() {
  # Arguments are supplied only by the fixed scenario scripts in this folder.
  case "$COMPOSE_COMMAND" in
    "docker compose")
      docker compose -f "$COMPOSE_FILE" "$@"
      ;;
    "podman compose")
      podman compose -f "$COMPOSE_FILE" "$@"
      ;;
  esac
}
