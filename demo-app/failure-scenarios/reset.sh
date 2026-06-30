#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$SCRIPT_DIR/common.sh"

run_compose up -d postgres backend frontend
echo "Demo backend, frontend, and postgres restored to the healthy baseline."
