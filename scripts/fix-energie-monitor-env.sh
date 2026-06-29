#!/usr/bin/env bash
# Korrigiert energie-monitor-app/.env (Zähler-UUIDs) und startet energie_monitor neu.
# Auf dem finanzen-Server ausführen, z. B.:
#   cd /opt/finanzen && ./scripts/fix-energie-monitor-env.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FINANZEN_ROOT="${FINANZEN_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
ENERGIE_MONITOR_ROOT="${ENERGIE_MONITOR_ROOT:-$FINANZEN_ROOT/../energie-monitor-app}"
ENV_FILE="$ENERGIE_MONITOR_ROOT/.env"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
ok() { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
err() { echo -e "${RED}✗${NC} $*" >&2; }

if [[ ! -f "$ENV_FILE" ]]; then
  err ".env nicht gefunden: $ENV_FILE"
  exit 1
fi

backup="${ENV_FILE}.bak.$(date +%Y%m%d_%H%M%S)"
cp "$ENV_FILE" "$backup"
ok "Backup: $backup"

set_kv() {
  local key="$1"
  local val="$2"
  if grep -q "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
  else
    echo "${key}=${val}" >> "$ENV_FILE"
  fi
}

# Korrekte UUIDs (Hauptzähler Bezug/Einspeisung/Leistung, PV-Leistung)
set_kv "VOLKSZAEHLER_UUID_HAUS" "a2f18610-8532-11ee-a24c-55bc0301a7e5"
set_kv "VOLKSZAEHLER_UUID_GRID_EXPORT" "e9c980d0-8535-11ee-b557-d53f4de75bcf"
set_kv "VOLKSZAEHLER_UUID_HAUS_POWER" "159efc60-8536-11ee-a109-71c0d1e154eb"
set_kv "VOLKSZAEHLER_UUID_PV" "22fbe320-8539-11ee-95c0-472a1d9972ce"
set_kv "VOLKSZAEHLER_RAW_UNIT" "Wh"
set_kv "PV_MEASUREMENT" "instantaneous_power_kw"
set_kv "PV_PEAK_POWER_KWP" "11.28"
set_kv "PV_HISTORY_ENABLED" "true"
set_kv "PV_HISTORY_THROUGH_YEAR" "2024"
set_kv "ENERGY_TIMEZONE" "Europe/Berlin"

ok "UUIDs in .env gesetzt"

echo ""
echo "Relevante Zeilen:"
grep -E '^VOLKSZAEHLER_UUID_|^PV_MEASUREMENT=' "$ENV_FILE" || true

echo ""
echo "Container neu starten…"
cd "$FINANZEN_ROOT"
if [[ -f ".env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source ".env"
  set +a
fi

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.energie-monitor.yml)
if [[ -f docker-compose.prod.yml ]]; then
  COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.energie-monitor.yml)
fi

"${COMPOSE[@]}" up -d --force-recreate energie_monitor
ok "energie_monitor neu gestartet"

sleep 3
HOST_PORT="${ENERGIE_HOST_PORT:-8080}"
if curl -fsS "http://127.0.0.1:${HOST_PORT}/health" >/dev/null; then
  ok "Health OK"
else
  warn "Health-Check fehlgeschlagen – Logs: ${COMPOSE[*]} logs --tail=50 energie_monitor"
fi

echo ""
echo "Bilanz 2025 prüfen:"
curl -fsS "http://127.0.0.1:${HOST_PORT}/api/v1/energy/balance?start=2025-01-01&end=2025-12-31&timezone=Europe/Berlin" \
  | python3 -m json.tool 2>/dev/null || true

echo ""
echo "Erwartung: balance_method=export_meter, grid_import_net_kwh ~13982, grid_export_kwh ~7029"
