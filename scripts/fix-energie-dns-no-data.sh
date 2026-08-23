#!/usr/bin/env bash
# Non-interactive Fix: Grafana „No data“ wegen DNS (wilhelms/wilhelmshome)
#
# Auf dem Finanzen-Rechner ausführen:
#   cd ~/workspaces/Finanzen && ./scripts/fix-energie-dns-no-data.sh
#
# Optional:
#   VZ_IP=192.168.5.x HA_IP=192.168.5.y ./scripts/fix-energie-dns-no-data.sh
#   ./scripts/fix-energie-dns-no-data.sh --scan   # sucht .0/24 nach :8080/:8123
#
set -euo pipefail

FINANZEN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENERGIE_ROOT="${ENERGIE_MONITOR_ROOT:-$FINANZEN_ROOT/../energie-monitor-app}"
ENV_FILE="${ENERGIE_ENV_FILE:-$ENERGIE_ROOT/.env}"
COMPOSE=(docker compose -f "$FINANZEN_ROOT/docker-compose.yml" -f "$FINANZEN_ROOT/docker-compose.energie-monitor.yml")
SCAN=false

for a in "$@"; do
  case "$a" in
    --scan) SCAN=true ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
  esac
done

ok() { echo "✓ $*"; }
warn() { echo "⚠ $*"; }
err() { echo "✗ $*" >&2; }

need() { command -v "$1" >/dev/null || { err "Befehl fehlt: $1"; exit 1; }; }
need docker
need curl

if [[ ! -f "$ENV_FILE" ]]; then
  err ".env nicht gefunden: $ENV_FILE"
  exit 1
fi

detect_subnet() {
  ip -4 route show default 2>/dev/null | awk '{print $3}' | head -1 | awk -F. '{print $1"."$2"."$3}'
}

scan_ports() {
  local base="${1:-192.168.5}"
  warn "Scanne ${base}.0/24 nach :8080 (VZ) und :8123 (HA) …"
  local vz="" ha=""
  for i in $(seq 1 254); do
    local ip="${base}.$i"
    (timeout 0.12 bash -c "echo >/dev/tcp/$ip/8080" 2>/dev/null && echo "VZ $ip") &
    (timeout 0.12 bash -c "echo >/dev/tcp/$ip/8123" 2>/dev/null && echo "HA $ip") &
    if (( i % 50 == 0 )); then wait; fi
  done
  wait
}

resolve_or_empty() {
  getent hosts "$1" 2>/dev/null | awk '{print $1; exit}'
}

# --- IPs ermitteln ---
VZ_IP="${VZ_IP:-}"
HA_IP="${HA_IP:-}"

if [[ -z "$VZ_IP" ]]; then
  VZ_IP="$(resolve_or_empty wilhelms || true)"
fi
if [[ -z "$HA_IP" ]]; then
  HA_IP="$(resolve_or_empty wilhelmshome || true)"
fi

if $SCAN || [[ -z "$VZ_IP" || -z "$HA_IP" ]]; then
  base="$(detect_subnet)"
  base="${base:-192.168.5}"
  mapfile -t hits < <(scan_ports "$base" 2>/dev/null | sort -u)
  for line in "${hits[@]:-}"; do
    [[ -z "${line:-}" ]] && continue
    echo "  gefunden: $line"
    if [[ -z "$VZ_IP" && "$line" == VZ* ]]; then VZ_IP="${line##* }"; fi
    if [[ -z "$HA_IP" && "$line" == HA* ]]; then HA_IP="${line##* }"; fi
  done
fi

if [[ -z "$VZ_IP" || -z "$HA_IP" ]]; then
  err "IPs unvollständig (VZ_IP='${VZ_IP:-}' HA_IP='${HA_IP:-}')."
  err "Bitte setzen: VZ_IP=… HA_IP=… $0"
  err "Oder Fritzbox-Geräteliste prüfen (Volkszähler :8080, Home Assistant :8123)."
  exit 1
fi

ok "Volkszähler IP: $VZ_IP"
ok "Home Assistant IP: $HA_IP"

# Erreichbarkeit kurz prüfen
for url in "http://$VZ_IP:8080/" "http://$HA_IP:8123/api/"; do
  code="$(curl -sS -m 5 -o /dev/null -w '%{http_code}' "$url" || true)"
  if [[ "$code" == "000" ]]; then
    warn "$url nicht erreichbar (HTTP $code) – .env wird trotzdem aktualisiert"
  else
    ok "$url → HTTP $code"
  fi
done

# --- .env patchen ---
cp -a "$ENV_FILE" "${ENV_FILE}.bak.$(date +%Y%m%d%H%M%S)"
python3 - "$ENV_FILE" "$VZ_IP" "$HA_IP" <<'PY'
import re, sys
from pathlib import Path
path, vz, ha = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
text = path.read_text(encoding="utf-8")

def set_or_add(text, key, value):
    line = f"{key}={value}"
    pat = re.compile(rf"^{re.escape(key)}=.*$", re.M)
    if pat.search(text):
        return pat.sub(line, text)
    return text.rstrip() + "\n" + line + "\n"

text = set_or_add(text, "VOLKSZAEHLER_BASE_URL", f"http://{vz}:8080")
text = set_or_add(text, "HOMEASSISTANT_BASE_URL", f"http://{ha}:8123")
path.write_text(text, encoding="utf-8")
print(path)
PY
ok ".env aktualisiert: $ENV_FILE (Backup *.bak.* angelegt)"

# --- Container neu ---
cd "$FINANZEN_ROOT"
"${COMPOSE[@]}" up -d --force-recreate energie_monitor
ok "energie_monitor neu gestartet"

sleep 3
echo "--- /health ---"
curl -sS -m 5 "http://127.0.0.1:8080/health" || true
echo
echo "--- pv/current ---"
curl -sS -m 10 "http://127.0.0.1:8080/api/v1/metrics/pv/current" || true
echo
echo "--- haus_gesamt/current ---"
curl -sS -m 10 "http://127.0.0.1:8080/api/v1/metrics/haus_gesamt/current" || true
echo

# DNS-Hinweis
if ! getent hosts wilhelms >/dev/null 2>&1; then
  warn "Host-DNS kennt 'wilhelms' weiterhin nicht – IP-Fix in .env bleibt nötig, bis Fritzbox-DNS wieder stimmt."
fi

ok "Fertig. Grafana-Dashboards hart neu laden (Zeitraum prüfen)."
