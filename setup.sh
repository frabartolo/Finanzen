#!/bin/bash
# Setup Script für Ubuntu/Linux - Python Environment und Abhängigkeiten
set -e

echo "=== Finanzen App Setup für Ubuntu ==="
echo "====================================="

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Wechsle ins Projektverzeichnis
cd "$(dirname "$0")"

echo "1. System-Abhängigkeiten prüfen..."

# Python 3 prüfen
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 ist nicht installiert!"
    echo "Installation: sudo apt update && sudo apt install python3 python3-pip python3-venv"
    exit 1
fi
print_success "Python 3 gefunden: $(python3 --version)"

# pip prüfen
if ! python3 -m pip --version &> /dev/null; then
    print_error "pip ist nicht installiert!"
    echo "Installation: sudo apt install python3-pip"
    exit 1
fi
print_success "pip gefunden"

echo ""
echo "2. Python Virtual Environment erstellen..."

# Virtual Environment erstellen
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    print_success "Virtual Environment erstellt"
else
    print_warning "Virtual Environment existiert bereits"
fi

# Virtual Environment aktivieren
source .venv/bin/activate
print_success "Virtual Environment aktiviert"

echo ""
echo "3. Python-Pakete installieren..."

# pip upgraden
.venv/bin/python -m pip install --upgrade pip

# Minimal Requirements installieren (ohne C-Compiler Probleme)
if .venv/bin/python -m pip install -r requirements-minimal.txt; then
    print_success "Minimale Abhängigkeiten installiert"
else
    print_error "Fehler beim Installieren der Abhängigkeiten"
    exit 1
fi

echo ""
echo "4. Konfigurationsdateien prüfen..."

# .env Datei erstellen falls nicht vorhanden
if [ ! -f ".env" ]; then
    cp .env.example .env
    print_success ".env Datei aus Beispiel erstellt"
    print_warning "Bitte .env Datei mit echten Zugangsdaten editieren!"
else
    print_success ".env Datei bereits vorhanden"
fi

# run.sh ausführbar machen
chmod +x run.sh
chmod +x deploy.sh
print_success "Shell-Scripts ausführbar gemacht"

echo ""
echo "5. Verzeichnisse erstellen..."

# Datenverzeichnisse erstellen
mkdir -p data/{db,inbox,logs,processed}
mkdir -p backups
print_success "Datenverzeichnisse erstellt"

echo ""
echo "6. Erste Tests..."

# Test der Konfiguration
if ./run.sh accounts list > /dev/null 2>&1; then
    print_success "Konfigurationstest erfolgreich"
else
    print_warning "Konfigurationstest fehlgeschlagen - möglicherweise fehlt noch die Datenbank"
fi

echo ""
echo "======================================="
print_success "Setup abgeschlossen!"
echo "======================================="
echo ""
echo "Nächste Schritte:"
echo "1. Bearbeiten Sie die .env Datei mit Ihren Zugangsdaten:"
echo "   nano .env"
echo ""
echo "2. Starten Sie das System mit Docker:"
echo "   ./deploy.sh production"
echo ""
echo "3. Testen Sie die Funktionen:"
echo "   ./run.sh accounts list"
echo "   ./run.sh accounts test"
echo "   ./run.sh postbank"
echo ""