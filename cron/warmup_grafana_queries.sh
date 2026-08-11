#!/bin/sh
# Alpine-kompatibler Wrapper (finanzen_cron hat kein bash / kein GNU date).
# Usage: warmup_grafana_queries.sh [full|short|recent]
set -u
DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
export PYTHONUNBUFFERED=1
exec python3 "$DIR/warmup_grafana_queries.py" "$@"
