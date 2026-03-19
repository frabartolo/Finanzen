#!/bin/bash
# Quick-Start Script für Finanzen-App
# Führt alle notwendigen Setup-Schritte automatisch aus

set -e

# Farben
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Finanzen App - Quick Start Setup    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Funktion für Erfolgsmeldung
success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Funktion für Info
info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Funktion für Warnung
warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Funktion für Fehler
error() {
    echo -e "${RED}✗ $1${NC}"
}

# 1. Prüfe Voraussetzungen
info "Prüfe Voraussetzungen..."

if ! command -v docker &> /dev/null; then
    error "Docker ist nicht installiert!"
    echo "  Installiere Docker: https://docs.docker.com/get-docker/"
    exit 1
fi
success "Docker gefunden"

if ! command -v docker compose &> /dev/null; then
    error "Docker Compose ist nicht installiert!"
    exit 1
fi
success "Docker Compose gefunden"

if ! command -v python3 &> /dev/null; then
    error "Python 3 ist nicht installiert!"
    exit 1
fi
success "Python 3 gefunden"

echo ""

# 2. .env Datei erstellen
info "Erstelle .env Datei..."

if [ -f ".env" ]; then
    warning ".env bereits vorhanden - überspringe"
else
    cp .env.example .env
    success ".env erstellt"
    
    # Generiere sichere Passwörter
    DB_PASS=$(openssl rand -base64 16)
    DB_ROOT_PASS=$(openssl rand -base64 16)
    
    # Encryption Key generieren
    info "Generiere Encryption Key..."
    ENC_KEY=$(python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")
    
    # In .env schreiben
    sed -i "s/DB_PASSWORD=.*/DB_PASSWORD=$DB_PASS/" .env
    sed -i "s/DB_ROOT_PASSWORD=.*/DB_ROOT_PASSWORD=$DB_ROOT_PASS/" .env
    sed -i "s/ENCRYPTION_KEY=.*/ENCRYPTION_KEY=$ENC_KEY/" .env
    
    success "Sichere Passwörter und Encryption Key generiert"
    warning "WICHTIG: Bewahre den Encryption Key sicher auf!"
fi

echo ""

# 3. Verzeichnisse erstellen
info "Erstelle Verzeichnisse..."
mkdir -p data/{db,inbox,logs,processed}
mkdir -p backups
success "Verzeichnisse erstellt"

echo ""

# 4. Docker-Container starten
info "Starte Docker-Container..."
docker compose up -d
success "Container gestartet"

echo ""

# 5. Warte auf Datenbank
info "Warte auf Datenbank-Initialisierung (30 Sekunden)..."
sleep 30
success "Datenbank sollte bereit sein"

echo ""

# 6. Datenbank initialisieren
info "Initialisiere Datenbank..."
docker compose exec -T app python3 scripts/setup_db.py || warning "Datenbank möglicherweise bereits initialisiert"

echo ""

# 7. Abschlussmeldung
echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Setup erfolgreich abgeschlossen! 🎉   ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Nächste Schritte:${NC}"
echo ""
echo "1. Bankzugangsdaten sicher speichern:"
echo -e "   ${YELLOW}docker compose exec app python3 scripts/credential_manager.py store POSTBANK_LOGIN \"ihr_login\"${NC}"
echo -e "   ${YELLOW}docker compose exec app python3 scripts/credential_manager.py store POSTBANK_PIN \"ihr_pin\"${NC}"
echo ""
echo "2. Konten in config/accounts.yaml eintragen"
echo "   (Nur Platzhalter verwenden: \${POSTBANK_LOGIN})"
echo ""
echo "3. Erste Transaktionen abrufen:"
echo -e "   ${YELLOW}docker compose exec app python3 scripts/fetch_fints.py${NC}"
echo ""
echo "4. Grafana aufrufen:"
echo -e "   ${BLUE}http://localhost:3000${NC}"
echo -e "   Login: ${YELLOW}admin / admin${NC} (beim ersten Login ändern!)"
echo ""
echo "📚 Vollständige Dokumentation: documentation/DOKUMENTATION.md"
echo ""
echo -e "${GREEN}Viel Erfolg mit Ihrer Finanzverwaltung!${NC}"
echo ""
