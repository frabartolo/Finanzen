#!/bin/bash
# Health Check Script - Kann lokal oder via Monitoring ausgeführt werden
set -e

# Lade .env Datei wenn vorhanden
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Setze Default-Werte
GRAFANA_URL=${GRAFANA_URL:-http://localhost:3000}
DB_CONTAINER=${DB_CONTAINER:-finanzen_db}
ALERT_EMAIL=${ALERT_EMAIL:-""}
DB_PASSWORD=${DB_PASSWORD:-change_me_secure_password}
DB_USER=${DB_USER:-finanzen}

# Exit Codes
EXIT_OK=0
EXIT_WARNING=1
EXIT_CRITICAL=2

check_container() {
    local container=$1
    local retries=3
    local wait_time=2
    
    for ((i=1; i<=retries; i++)); do
        if docker ps --filter "name=$container" --filter "status=running" --format "{{.Names}}" | grep -q "^${container}$"; then
            # Zusätzlich prüfen ob Container wirklich gesund ist
            local health_status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "none")
            if [ "$health_status" = "none" ] || [ "$health_status" = "healthy" ]; then
                return 0
            fi
        fi
        
        if [ $i -lt $retries ]; then
            sleep $wait_time
        fi
    done
    
    return 1
}

check_grafana() {
    local retries=3
    local wait_time=3
    
    for ((i=1; i<=retries; i++)); do
        if curl -f -s --connect-timeout 10 --max-time 15 "$GRAFANA_URL/api/health" > /dev/null; then
            return 0
        fi
        
        if [ $i -lt $retries ]; then
            sleep $wait_time
        fi
    done
    
    return 1
}

check_database() {
    local retries=5
    local wait_time=5
    
    for ((i=1; i<=retries; i++)); do
        if docker exec "$DB_CONTAINER" mysqladmin ping -u "$DB_USER" -p"$DB_PASSWORD" --connect-timeout=10 > /dev/null 2>&1; then
            return 0
        fi
        
        if [ $i -lt $retries ]; then
            echo "Datenbank-Verbindungsversuch $i/$retries fehlgeschlagen, warte ${wait_time}s..."
            sleep $wait_time
        fi
    done
    
    return 1
}

check_disk_space() {
    local usage=$(df -h . | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ "$usage" -gt 90 ]; then
        return 2
    elif [ "$usage" -gt 80 ]; then
        return 1
    else
        return 0
    fi
}

# Main Check
ERRORS=0
WARNINGS=0

echo "=== Finanzen Health Check ==="
echo "$(date)"
echo ""

# Warte kurz damit Services Zeit haben sich zu stabilisieren
echo "Warte 10 Sekunden für Service-Stabilisierung..."
sleep 10
echo ""

# Container Checks
echo "Prüfe Container-Status..."
for container in finanzen_db finanzen_app finanzen_cron finanzen_grafana; do
    echo -n "Prüfe $container... "
    if check_container "$container"; then
        echo "✓ läuft"
    else
        echo "✗ läuft NICHT!"
        # Zeige Container-Status für Debugging
        docker ps -a --filter "name=$container" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true
        ((ERRORS++))
    fi
done

echo ""

# Database Check (zuerst, da andere Services davon abhängen)
echo -n "Prüfe Datenbankverbindung... "
if check_database; then
    echo "✓ Datenbank bereit"
else
    echo "✗ Datenbank nicht bereit!"
    echo "  Debugging-Info:"
    docker exec "$DB_CONTAINER" mysqladmin ping -u "$DB_USER" -p"$DB_PASSWORD" 2>&1 | head -3 || true
    docker logs "$DB_CONTAINER" --tail=5 2>/dev/null || true
    ((ERRORS++))
fi

# Grafana Check
echo -n "Prüfe Grafana-Verbindung... "
if check_grafana; then
    echo "✓ Grafana erreichbar"
else
    echo "✗ Grafana nicht erreichbar!"
    echo "  URL: $GRAFANA_URL/api/health"
    ((ERRORS++))
fi

# Disk Space Check
echo ""
check_disk_space
DISK_STATUS=$?
if [ $DISK_STATUS -eq 0 ]; then
    echo "✓ Speicherplatz OK"
elif [ $DISK_STATUS -eq 1 ]; then
    echo "⚠ Speicherplatz: Warnung (>80%)"
    ((WARNINGS++))
else
    echo "✗ Speicherplatz: Kritisch (>90%)"
    ((ERRORS++))
fi

# Log Check (letzte 5 Minuten)
echo ""
echo "Letzte Fehler in Logs:"
docker compose logs --since 5m 2>&1 | grep -i "error\|critical\|fatal" | tail -5 || echo "Keine Fehler gefunden"

# Exit basierend auf Status
echo ""
if [ $ERRORS -gt 0 ]; then
    echo "Status: KRITISCH ($ERRORS Fehler)"
    exit $EXIT_CRITICAL
elif [ $WARNINGS -gt 0 ]; then
    echo "Status: WARNUNG ($WARNINGS Warnungen)"
    exit $EXIT_WARNING
else
    echo "Status: OK"
    exit $EXIT_OK
fi
