#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$SCRIPT_DIR/common.sh"

run_compose stop postgres
echo "FS-002 active: incidentpilot-demo-postgres is stopped."
