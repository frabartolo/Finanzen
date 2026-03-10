#!/bin/bash
# MariaDB Recovery: Frische Datenbank aus letztem Backup
# Nutzung: ./scripts/recover_db.sh
# Voraussetzung: .env geladen, neuestes Backup in backups/

set -e
cd "$(dirname "$0")/.."
[ -f .env ] && export $(grep -v '^#' .env | xargs)
DB_USER=${DB_USER:-finanzen}
DB_PASSWORD=${DB_PASSWORD:?DB_PASSWORD fehlt in .env}
DB_NAME=${DB_NAME:-finanzen}

echo "=== MariaDB Recovery ==="
echo "Stoppe Container..."
docker compose down

BACKUP=$(ls -t backups/backup_*.sql.gz 2>/dev/null | head -1)
if [ -z "$BACKUP" ]; then
    echo "Kein Backup gefunden! Nutze backup_*.sql"
    BACKUP=$(ls -t backups/backup_*.sql 2>/dev/null | head -1)
fi

if [ -z "$BACKUP" ]; then
    echo "FEHLER: Kein Backup in backups/ gefunden"
    exit 1
fi

echo "Backup: $BACKUP"
echo "Sichere beschädigtes Datenverzeichnis..."
sudo mv data/db "data/db.corrupt.$(date +%Y%m%d_%H%M%S)" 2>/dev/null || mv data/db "data/db.corrupt.$(date +%Y%m%d_%H%M%S)"

echo "Erstelle leeres Datenverzeichnis..."
mkdir -p data/db

echo "Starte MariaDB (frisch initialisieren)..."
docker compose up -d finanzen_db

echo "Warte auf MariaDB-Start (bis zu 60s)..."
for i in $(seq 1 30); do
    if docker compose exec -T finanzen_db mariadb -u "$DB_USER" -p"$DB_PASSWORD" -e "SELECT 1;" 2>/dev/null; then
        echo "MariaDB läuft!"
        break
    fi
    sleep 2
done

echo "Stelle Backup wieder her..."
if [[ "$BACKUP" == *.gz ]]; then
    gunzip -c "$BACKUP" | docker compose exec -T finanzen_db mariadb -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME"
else
    docker compose exec -T finanzen_db mariadb -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" < "$BACKUP"
fi

echo "Starte alle Container..."
docker compose up -d

echo "=== Recovery abgeschlossen ==="
