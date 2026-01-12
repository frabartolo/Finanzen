#!/bin/bash
# Rollback Script - Wiederherstellung des letzten Backups
set -e

BACKUP_DIR="./backups"

echo "=== Finanzen Rollback Script ==="

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Finde letztes Backup
echo "Suche nach letztem Backup..."
LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/backup_*.sql.gz 2>/dev/null | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    print_error "Kein Backup gefunden!"
    exit 1
fi

print_success "Gefunden: $LATEST_BACKUP"

# Bestätigung
echo ""
print_warning "WARNUNG: Dieser Vorgang überschreibt die aktuelle Datenbank!"
read -p "Möchtest du fortfahren? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
    echo "Abgebrochen."
    exit 0
fi

# Datenbank wiederherstellen
echo ""
echo "Stelle Datenbank wieder her..."

# Stop services
docker compose stop app cron

# Restore database
gunzip -c "$LATEST_BACKUP" | docker compose exec -T db psql -U finanzen finanzen

if [ $? -eq 0 ]; then
    print_success "Datenbank wiederhergestellt"
else
    print_error "Fehler beim Wiederherstellen der Datenbank!"
    exit 1
fi

# Restart services
echo ""
echo "Starte Services neu..."
docker compose up -d

sleep 5
print_success "Rollback abgeschlossen"

echo ""
echo "Services:"
docker compose ps
