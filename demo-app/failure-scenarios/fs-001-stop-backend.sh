#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$SCRIPT_DIR/common.sh"

run_compose stop backend
echo "FS-001 active: incidentpilot-demo-backend is stopped."
