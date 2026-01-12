#!/bin/bash
# Health Check Script - Kann lokal oder via Monitoring ausgeführt werden
set -e

GRAFANA_URL=${GRAFANA_URL:-http://localhost:3000}
DB_CONTAINER=${DB_CONTAINER:-finanzen_db}
ALERT_EMAIL=${ALERT_EMAIL:-""}

# Exit Codes
EXIT_OK=0
EXIT_WARNING=1
EXIT_CRITICAL=2

check_container() {
    local container=$1
    if docker ps --filter "name=$container" --filter "status=running" | grep -q "$container"; then
        return 0
    else
        return 1
    fi
}

check_grafana() {
    if curl -f -s "$GRAFANA_URL/api/health" > /dev/null; then
        return 0
    else
        return 1
    fi
}

check_database() {
    if docker exec "$DB_CONTAINER" mysqladmin ping -u finanzen -pchange_me_secure_password > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
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

# Container Checks
for container in finanzen_db finanzen_app finanzen_cron finanzen_grafana; do
    if check_container "$container"; then
        echo "✓ $container läuft"
    else
        echo "✗ $container läuft NICHT!"
        ((ERRORS++))
    fi
done

echo ""

# Grafana Check
if check_grafana; then
    echo "✓ Grafana erreichbar"
else
    echo "✗ Grafana nicht erreichbar!"
    ((ERRORS++))
fi

# Database Check
if check_database; then
    echo "✓ Datenbank bereit"
else
    echo "✗ Datenbank nicht bereit!"
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
