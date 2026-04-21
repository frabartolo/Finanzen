#!/usr/bin/env bash
#
# Deploy / Aktualisierung: energie-monitor-app im Finanzen-Docker-Stack
#
# Voraussetzung: Repo-Layout (Default)
#   Finanzen/                     ← dieses Skript liegt hier
#   energie-monitor-app/          ← Geschwisterverzeichnis
#
# Aufruf (nach git pull / clone), typisch aus dem Finanzen-Repo:
#   ./deploy-energie-monitor.sh              # Default: base (wie deploy.sh: nur docker-compose.yml + Energie)
#   ./deploy-energie-monitor.sh production   # + docker-compose.prod.yml
#   ./deploy-energie-monitor.sh development  # + docker-compose.dev.yml
#
# Optionen:
#   --full-stack       Gesamten Compose-Stack neu bauen/hochfahren (alle Services),
#                      nicht nur energie_monitor (länger, mehr Nebenwirkungen).
#   --no-git-pull      Kein git pull in Finanzen- und Energie-Repo.
#   --skip-datasource  Kein envsubst für MariaDB-Grafana-Datasource (Finanzen).
#
# Umgebungsvariablen:
#   FINANZEN_ROOT          Absoluter Pfad zum Finanzen-Repo (Default: Verzeichnis dieses Skripts)
#   ENERGIE_MONITOR_ROOT   Absoluter Pfad zum energie-monitor-app Repo (Default: FINANZEN_ROOT/../energie-monitor-app)
#   ENERGIE_HOST_PORT      Host-Port für die Energie-API (Default: 8080), siehe docker-compose.energie-monitor.yml
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
deploy-energie-monitor.sh

  ./deploy-energie-monitor.sh [base|production|development] [--full-stack] [--no-git-pull] [--skip-datasource]

  base (Default):        docker-compose.yml + docker-compose.energie-monitor.yml
  production:            docker-compose.yml + docker-compose.prod.yml + docker-compose.energie-monitor.yml
  development:           docker-compose.yml + docker-compose.dev.yml + docker-compose.energie-monitor.yml

Ohne --full-stack wird nur der Service „energie_monitor“ gebaut und gestartet (übrige Container unverändert).

Umgebung:
  FINANZEN_ROOT=/pfad/zu/Finanzen ENERGIE_MONITOR_ROOT=/pfad/zu/energie-monitor-app ./deploy-energie-monitor.sh
EOF
}

MODE="base"
FULL_STACK=false
NO_GIT_PULL=false
SKIP_DATASOURCE=false
POS_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --full-stack) FULL_STACK=true ;;
    --no-git-pull) NO_GIT_PULL=true ;;
    --skip-datasource) SKIP_DATASOURCE=true ;;
    --help|-h) usage; exit 0 ;;
    -*)
      echo "Unbekannte Option: $arg" >&2
      usage >&2
      exit 1
      ;;
    *) POS_ARGS+=("$arg") ;;
  esac
done

if [[ ${#POS_ARGS[@]} -gt 0 ]]; then
  MODE="${POS_ARGS[0]}"
fi

FINANZEN_ROOT="${FINANZEN_ROOT:-$SCRIPT_DIR}"
FINANZEN_ROOT="$(cd "$FINANZEN_ROOT" && pwd)"
ENERGIE_MONITOR_ROOT="${ENERGIE_MONITOR_ROOT:-$FINANZEN_ROOT/../energie-monitor-app}"
ENERGIE_MONITOR_ROOT="$(cd "$ENERGIE_MONITOR_ROOT" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok() { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
err() { echo -e "${RED}✗${NC} $*" >&2; }

if [[ ! -f "$FINANZEN_ROOT/docker-compose.yml" ]]; then
  err "docker-compose.yml nicht gefunden unter FINANZEN_ROOT=$FINANZEN_ROOT"
  exit 1
fi

if [[ ! -d "$ENERGIE_MONITOR_ROOT" ]]; then
  err "energie-monitor-app nicht gefunden: $ENERGIE_MONITOR_ROOT"
  err "Tipp: ENERGIE_MONITOR_ROOT=/pfad/zum/repo setzen oder Repos als Geschwister anlegen."
  exit 1
fi

if [[ ! -f "$FINANZEN_ROOT/docker-compose.energie-monitor.yml" ]]; then
  err "docker-compose.energie-monitor.yml fehlt im Finanzen-Repo."
  exit 1
fi

case "$MODE" in
  base|production|development) ;;
  *)
    err "Unbekannter Modus: $MODE (erlaubt: base, production, development)"
    exit 1
    ;;
esac

COMPOSE_FILES=( -f "$FINANZEN_ROOT/docker-compose.yml" )
if [[ "$MODE" == "production" ]]; then
  if [[ ! -f "$FINANZEN_ROOT/docker-compose.prod.yml" ]]; then
    err "docker-compose.prod.yml fehlt (production)."
    exit 1
  fi
  COMPOSE_FILES+=( -f "$FINANZEN_ROOT/docker-compose.prod.yml" )
elif [[ "$MODE" == "development" ]]; then
  if [[ ! -f "$FINANZEN_ROOT/docker-compose.dev.yml" ]]; then
    err "docker-compose.dev.yml fehlt (development)."
    exit 1
  fi
  COMPOSE_FILES+=( -f "$FINANZEN_ROOT/docker-compose.dev.yml" )
fi
COMPOSE_FILES+=( -f "$FINANZEN_ROOT/docker-compose.energie-monitor.yml" )

compose() {
  docker compose "${COMPOSE_FILES[@]}" "$@"
}

if ! command -v docker >/dev/null 2>&1; then
  err "Docker nicht gefunden."
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  err "Docker Compose Plugin nicht verfügbar."
  exit 1
fi
ok "Docker / Compose vorhanden"

git_maybe_pull() {
  local dir="$1"
  local name="$2"
  if [[ "$NO_GIT_PULL" == true ]]; then
    warn "Überspringe git pull ($name)"
    return 0
  fi
  if [[ ! -d "$dir/.git" ]]; then
    warn "Kein Git-Repo in $name – kein pull"
    return 0
  fi
  if [[ -n "$(git -C "$dir" status --porcelain 2>/dev/null)" ]]; then
    warn "Git in $name: lokale Änderungen – kein pull"
    return 0
  fi
  if git -C "$dir" pull --rebase; then
    ok "Git pull ($name)"
  else
    warn "Git pull fehlgeschlagen ($name) – fahre mit lokalem Stand fort"
  fi
}

echo "0. Git aktualisieren (optional)…"
git_maybe_pull "$FINANZEN_ROOT" "Finanzen"
git_maybe_pull "$ENERGIE_MONITOR_ROOT" "energie-monitor-app"

echo "1. Energie-.env prüfen…"
if [[ ! -f "$ENERGIE_MONITOR_ROOT/.env" ]]; then
  if [[ -f "$ENERGIE_MONITOR_ROOT/.env.example" ]]; then
    cp "$ENERGIE_MONITOR_ROOT/.env.example" "$ENERGIE_MONITOR_ROOT/.env"
    err ".env in energie-monitor-app angelegt aus .env.example – bitte Werte eintragen, dann Skript erneut ausführen."
    exit 1
  fi
  err "Keine .env in $ENERGIE_MONITOR_ROOT (und keine .env.example)."
  exit 1
fi
ok "energie-monitor-app/.env vorhanden"

echo "2. Grafana MariaDB-Datasource (Finanzen)…"
cd "$FINANZEN_ROOT"
if [[ "$SKIP_DATASOURCE" == true ]]; then
  warn "Überspringe envsubst für Grafana MariaDB-Datasource"
elif [[ -f "grafana/provisioning/datasources/datasources.yaml.template" ]]; then
  if [[ -f ".env" ]]; then
    set -a
    # shellcheck source=/dev/null
    source ".env"
    set +a
  fi
  if command -v envsubst >/dev/null 2>&1; then
    if [[ -z "${DB_PASSWORD:-}" ]]; then
      warn "DB_PASSWORD nicht gesetzt – envsubst für datasources.yaml übersprungen"
    else
      envsubst '${DB_PASSWORD}' < grafana/provisioning/datasources/datasources.yaml.template \
        > grafana/provisioning/datasources/datasources.yaml
      chmod 644 grafana/provisioning/datasources/datasources.yaml
      ok "grafana/provisioning/datasources/datasources.yaml erzeugt"
    fi
  else
    warn "envsubst nicht installiert – MariaDB-Datasource ggf. unverändert"
  fi
else
  warn "datasources.yaml.template nicht gefunden – Schritt übersprungen"
fi

echo "3. Docker Compose (Modus: $MODE)…"
cd "$FINANZEN_ROOT"
if [[ "$FULL_STACK" == true ]]; then
  warn "Vollständiger Stack-Start (--full-stack) – kann alle Services neu bauen/starten."
  compose build --no-cache
  compose up -d
  ok "Stack up (alle Services)"
else
  compose build energie_monitor
  compose up -d energie_monitor
  ok "Service energie_monitor gebaut und gestartet"
fi

echo "4. Healthchecks…"
HOST_PORT="${ENERGIE_HOST_PORT:-8080}"
if curl -fsS "http://127.0.0.1:${HOST_PORT}/health" >/dev/null; then
  ok "Energie-API health (http://127.0.0.1:${HOST_PORT}/health)"
else
  warn "Health-Check auf Port ${HOST_PORT} fehlgeschlagen (Container startet evtl. noch – Logs: docker compose … logs energie_monitor)"
fi

if docker ps --format '{{.Names}}' | grep -q '^finanzen_grafana$'; then
  if docker exec finanzen_grafana wget -qO- "http://energie_monitor:8080/health" >/dev/null 2>&1; then
    ok "Grafana-Container erreicht energie_monitor intern"
  else
    warn "Grafana-Container konnte energie_monitor:8080 nicht abfragen (läuft Grafana? gleiches Compose-Projekt?)"
  fi
else
  warn "Container finanzen_grafana läuft nicht – interner Check übersprungen"
fi

echo ""
echo "Fertig."
echo "  - Energie OpenAPI/Docs: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo localhost):${HOST_PORT}/docs"
echo "  - Beispiel:             curl -fsS http://127.0.0.1:${HOST_PORT}/api/v1/metrics/pv/current"
printf '  - Compose-Status:      docker compose'
for x in "${COMPOSE_FILES[@]}"; do printf ' %q' "$x"; done
echo ' ps'
echo ""
