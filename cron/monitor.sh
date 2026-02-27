#!/bin/bash
# Monitoring-Script für Cron-Jobs
# Prüft Logs und meldet Fehler

LOG_DIR="/app/data/logs"
ALERT_FILE="$LOG_DIR/cron_alerts.log"

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=== Finanzen Cron-Job Monitor ==="
echo "Zeitpunkt: $(date)"
echo "=================================="
echo ""

check_log() {
    local log_file=$1
    local job_name=$2
    local max_age_hours=${3:-48}  # Default: 48 Stunden
    
    if [ ! -f "$log_file" ]; then
        echo -e "${RED}✗ $job_name: Log-Datei nicht gefunden${NC}"
        echo "$(date): $job_name - Log-Datei fehlt" >> "$ALERT_FILE"
        return 1
    fi
    
    # Prüfe Alter der letzten Änderung
    local age_minutes=$(( ($(date +%s) - $(stat -c %Y "$log_file")) / 60 ))
    local max_age_minutes=$((max_age_hours * 60))
    
    if [ $age_minutes -gt $max_age_minutes ]; then
        echo -e "${YELLOW}⚠ $job_name: Keine Updates seit $age_minutes Minuten${NC}"
        echo "$(date): $job_name - Keine Updates seit $age_minutes Minuten" >> "$ALERT_FILE"
    else
        echo -e "${GREEN}✓ $job_name: Aktuell (vor $age_minutes Minuten)${NC}"
    fi
    
    # Prüfe auf Fehler in den letzten 100 Zeilen
    local error_count=$(tail -n 100 "$log_file" | grep -ci "error\|fehler\|❌")
    
    if [ $error_count -gt 0 ]; then
        echo -e "${RED}  → $error_count Fehler gefunden in den letzten Einträgen${NC}"
        echo "$(date): $job_name - $error_count Fehler" >> "$ALERT_FILE"
    fi
    
    echo ""
}

# Prüfe einzelne Jobs
check_log "$LOG_DIR/fetch_fints.log" "FinTS-Abruf" 25  # Täglich, Toleranz 25h
check_log "$LOG_DIR/categorize.log" "Kategorisierung" 25  # Täglich, Toleranz 25h
check_log "$LOG_DIR/parse_pdfs.log" "PDF-Parsing" 3  # Alle 2h, Toleranz 3h

# Zeige letzte Alerts
if [ -f "$ALERT_FILE" ]; then
    echo "=== Letzte Alerts (24h) ==="
    find "$ALERT_FILE" -mtime -1 -exec tail -n 20 {} \;
    echo ""
fi

# Disk Space prüfen
echo "=== Disk Space ==="
df -h /app/data | tail -n 1
echo ""

# Docker Container Status (wenn möglich)
if command -v docker &> /dev/null; then
    echo "=== Container Status ==="
    docker ps --filter "name=finanzen" --format "table {{.Names}}\t{{.Status}}\t{{.State}}"
fi

echo ""
echo "=================================="
echo "Monitor-Durchlauf abgeschlossen"
echo "=================================="
