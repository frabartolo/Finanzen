#!/bin/bash
# Deployment Script für lokale oder manuelle Deployments
# Optionen: --reset-db   Transaktionen und Dokumente vor Deployment leeren
set -e

RESET_DB=false
for arg in "$@"; do
    case "$arg" in
        --reset-db) RESET_DB=true ;;
    esac
done

ENVIRONMENT=${1:-production}
[ "$1" = "--reset-db" ] && ENVIRONMENT=production
COMPOSE_FILE="docker-compose.yml"
BACKUP_DIR="./backups"

echo "=== Finanzen Deployment Script ==="
echo "Environment: $ENVIRONMENT"
echo "=================================="

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Funktionen
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Lade .env Datei wenn vorhanden
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
    print_success ".env Datei geladen"
else
    print_warning ".env Datei nicht gefunden - verwende Defaults"
fi

# Setze Default-Werte falls nicht in .env
DB_PASSWORD=${DB_PASSWORD:-change_me_secure_password}
DB_USER=${DB_USER:-finanzen}
DB_NAME=${DB_NAME:-finanzen}

# Navigate to project directory and pull latest changes
echo "0. Aktualisiere Code-Repository..."
cd /opt/finanzen

# Standard commit message für automatische Commits
DEPLOY_COMMIT_MSG="Auto-commit before deployment $(date '+%Y-%m-%d %H:%M:%S')"

# Prüfe ob es lokale Änderungen gibt
if [ -n "$(git status --porcelain)" ]; then
    print_warning "Lokale Änderungen gefunden - erstelle automatischen Commit"
    git add -A
    git commit -m "$DEPLOY_COMMIT_MSG"
fi

# Pull latest changes
if git pull --rebase; then
    print_success "Repository aktualisiert"
else
    print_warning "Git pull fehlgeschlagen - fahre mit lokalem Code fort"
fi

# Pre-deployment Checks
echo "1. Pre-deployment Checks..."

# Check Docker
if ! command -v docker &> /dev/null; then
    print_error "Docker ist nicht installiert!"
    exit 1
fi
print_success "Docker gefunden"

# Check Docker Compose
if ! command -v docker compose &> /dev/null; then
    print_error "Docker Compose ist nicht installiert!"
    exit 1
fi
print_success "Docker Compose gefunden"

# Check Config Files
if [ ! -f "config/settings.yaml" ]; then
    print_warning "settings.yaml nicht gefunden - wird beim ersten Start erstellt"
fi

# Berechtigungen sicherstellen (Grafana/Container brauchen Zugriff)
sudo chown -R finanzen:finanzen /opt/finanzen

# Create necessary directories
echo ""
echo "2. Erstelle notwendige Verzeichnisse..."
mkdir -p data/{db,inbox,logs,processed}
mkdir -p "$BACKUP_DIR"
print_success "Verzeichnisse erstellt"

# Backup existing database
echo ""
echo "3. Erstelle Datenbank-Backup..."
if [ -f "data/db/mysql" ] || [ "$(docker ps -q -f name=finanzen_db)" ]; then
    BACKUP_FILE="$BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S).sql"
    if docker compose exec -T finanzen_db mariadb-dump -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" > "$BACKUP_FILE" 2>/dev/null; then
        gzip "$BACKUP_FILE"
        print_success "Backup erstellt: ${BACKUP_FILE}.gz"
    else
        print_warning "Kein Backup erstellt (DB möglicherweise noch nicht initialisiert)"
    fi
else
    print_warning "Keine existierende Datenbank gefunden - überspringe Backup"
fi

# Pull latest images
echo ""
echo "4. Lade Docker Images..."
docker compose pull
print_success "Images aktualisiert"

# Build custom images
echo ""
echo "5. Baue Anwendungs-Images..."
docker compose build --no-cache
print_success "Build abgeschlossen"

# Generate Grafana datasource config (Grafana ersetzt keine Env-Vars in Provisioning)
echo ""
echo "6. Erzeuge Grafana-Datasource-Konfiguration..."
if [ -f "grafana/provisioning/datasources/datasources.yaml.template" ]; then
    if command -v envsubst &> /dev/null; then
        envsubst '${DB_PASSWORD}' < grafana/provisioning/datasources/datasources.yaml.template \
            > grafana/provisioning/datasources/datasources.yaml
        chmod 644 grafana/provisioning/datasources/datasources.yaml
        print_success "Datasource-Konfiguration mit DB-Passwort erzeugt"
    else
        print_warning "envsubst nicht gefunden - Grafana-Datasource könnte ohne Passwort starten (MariaDB-Zugriff fehlgeschlagen)"
    fi
else
    print_warning "datasources.yaml.template nicht gefunden"
fi

# Stop running containers
echo ""
echo "7. Stoppe laufende Container..."
docker compose down
print_success "Container gestoppt"

# Entferne korrupte MariaDB tc.log (falls vorhanden - verhindert "Can't init tc log")
if [ -f "data/db/tc.log" ]; then
    rm -f data/db/tc.log 2>/dev/null || sudo rm -f data/db/tc.log 2>/dev/null
    print_success "tc.log entfernt (war korrupt)"
fi

# Start services
echo ""
echo "8. Starte Services..."
docker compose up -d
print_success "Services gestartet"

# Wait for services to be ready
echo ""
echo "9. Warte auf Service-Initialisierung..."
sleep 10

# Health checks
echo ""
echo "10. Health Checks..."

# Check Database
if docker compose exec -T finanzen_db mariadb -u "$DB_USER" -p"$DB_PASSWORD" -e "SELECT 1;" > /dev/null 2>&1; then
    print_success "Datenbank läuft"
else
    print_error "Datenbank nicht erreichbar!"
    docker compose logs finanzen_db
    exit 1
fi

# Check Grafana
if curl -f http://localhost:3000/api/health > /dev/null 2>&1; then
    print_success "Grafana läuft"
else
    print_warning "Grafana noch nicht bereit (startet möglicherweise noch)"
fi

# Check App Container
if docker compose ps app | grep -q "Up"; then
    print_success "App-Container läuft"
else
    print_error "App-Container läuft nicht!"
    docker compose logs app
    exit 1
fi

# Check pdfplumber (PDF-Parsing)
if docker compose exec -T app python -c "import pdfplumber" 2>/dev/null; then
    print_success "pdfplumber (PDF-Parsing) verfügbar"
else
    print_error "pdfplumber fehlt im App-Container! Bitte requirements.txt prüfen."
    exit 1
fi

# Check Cron Container
if docker compose ps cron | grep -q "Up"; then
    print_success "Cron-Container läuft"
else
    print_error "Cron-Container läuft nicht!"
    docker compose logs cron
    exit 1
fi

# Optional: Datenbank leeren (Transaktionen + Dokumente)
if [ "$RESET_DB" = true ]; then
    echo ""
    echo "10b. Leere Transaktionen und Dokumente (--reset-db)..."
    if docker compose exec -T app python scripts/reset_db.py --confirm 2>/dev/null; then
        print_success "Datenbank geleert"
    else
        print_warning "Reset fehlgeschlagen"
    fi
fi

# Show running containers
echo ""
echo "11. Laufende Container:"
docker compose ps

# Show recent logs
echo ""
echo "12. Letzte Log-Einträge:"
docker compose logs --tail=20

# Cleanup old backups
echo ""
echo "13. Räume alte Backups auf (älter als 30 Tage)..."
find "$BACKUP_DIR" -name "backup_*.sql.gz" -mtime +30 -delete
print_success "Cleanup abgeschlossen"

echo ""
echo "=================================="
print_success "Deployment erfolgreich abgeschlossen!"
echo "=================================="
echo ""
echo "Zugriff:"
echo "  - Grafana:  http://localhost:3000 (admin/admin)"
echo "  - Database: localhost:3306"
echo ""
echo "Nützliche Befehle:"
echo "  - Logs anzeigen:     docker compose logs -f"
echo "  - Status prüfen:     docker compose ps"
echo "  - Services neustarten: docker compose restart"
echo "  - Services stoppen:  docker compose down"
echo ""
