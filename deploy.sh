#!/bin/bash
# Deployment Script für lokale oder manuelle Deployments
set -e

ENVIRONMENT=${1:-production}
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

# Stop running containers
echo ""
echo "6. Stoppe laufende Container..."
docker compose down
print_success "Container gestoppt"

# Start services
echo ""
echo "7. Starte Services..."
docker compose up -d
print_success "Services gestartet"

# Wait for services to be ready
echo ""
echo "8. Warte auf Service-Initialisierung..."
sleep 10

# Health checks
echo ""
echo "9. Health Checks..."

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

# Check Cron Container
if docker compose ps cron | grep -q "Up"; then
    print_success "Cron-Container läuft"
else
    print_error "Cron-Container läuft nicht!"
    docker compose logs cron
    exit 1
fi

# Show running containers
echo ""
echo "10. Laufende Container:"
docker compose ps

# Show recent logs
echo ""
echo "11. Letzte Log-Einträge:"
docker compose logs --tail=20

# Cleanup old backups
echo ""
echo "12. Räume alte Backups auf (älter als 30 Tage)..."
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
