#!/bin/bash
# Validiert die .env Datei und prüft auf sichere Passwörter

echo "=== .env Validierung ==="
echo ""

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

# Prüfe ob .env existiert
if [ ! -f ".env" ]; then
    echo -e "${RED}✗ .env Datei nicht gefunden!${NC}"
    echo "  Erstelle sie mit: cp .env.example .env"
    exit 1
fi

echo -e "${GREEN}✓ .env Datei gefunden${NC}"
echo ""

# Lade .env
export $(grep -v '^#' .env | xargs)

# Prüfe kritische Variablen
echo "Prüfe kritische Variablen:"

# DB_PASSWORD
if [ -z "$DB_PASSWORD" ]; then
    echo -e "${RED}✗ DB_PASSWORD ist nicht gesetzt!${NC}"
    ((ERRORS++))
elif [ "$DB_PASSWORD" == "change_me_secure_password" ]; then
    echo -e "${RED}✗ DB_PASSWORD verwendet Default-Wert (unsicher!)${NC}"
    ((ERRORS++))
elif [ ${#DB_PASSWORD} -lt 12 ]; then
    echo -e "${YELLOW}⚠ DB_PASSWORD sollte mindestens 12 Zeichen haben${NC}"
    ((WARNINGS++))
else
    echo -e "${GREEN}✓ DB_PASSWORD ist gesetzt${NC}"
fi

# DB_ROOT_PASSWORD
if [ -z "$DB_ROOT_PASSWORD" ]; then
    echo -e "${RED}✗ DB_ROOT_PASSWORD ist nicht gesetzt!${NC}"
    ((ERRORS++))
elif [ "$DB_ROOT_PASSWORD" == "change_me_root_password" ]; then
    echo -e "${RED}✗ DB_ROOT_PASSWORD verwendet Default-Wert (unsicher!)${NC}"
    ((ERRORS++))
elif [ ${#DB_ROOT_PASSWORD} -lt 12 ]; then
    echo -e "${YELLOW}⚠ DB_ROOT_PASSWORD sollte mindestens 12 Zeichen haben${NC}"
    ((WARNINGS++))
else
    echo -e "${GREEN}✓ DB_ROOT_PASSWORD ist gesetzt${NC}"
fi

# ENCRYPTION_KEY
if [ -z "$ENCRYPTION_KEY" ]; then
    echo -e "${YELLOW}⚠ ENCRYPTION_KEY ist nicht gesetzt${NC}"
    echo "  Generiere einen mit: openssl rand -hex 32"
    ((WARNINGS++))
elif [ "$ENCRYPTION_KEY" == "generate_a_secure_key_here" ]; then
    echo -e "${RED}✗ ENCRYPTION_KEY verwendet Default-Wert!${NC}"
    echo "  Generiere einen mit: openssl rand -hex 32"
    ((ERRORS++))
else
    echo -e "${GREEN}✓ ENCRYPTION_KEY ist gesetzt${NC}"
fi

# DB_TYPE
if [ "$DB_TYPE" != "mariadb" ] && [ "$DB_TYPE" != "mysql" ]; then
    echo -e "${YELLOW}⚠ DB_TYPE sollte 'mariadb' oder 'mysql' sein (aktuell: $DB_TYPE)${NC}"
    ((WARNINGS++))
else
    echo -e "${GREEN}✓ DB_TYPE ist korrekt ($DB_TYPE)${NC}"
fi

# Optionale Variablen
echo ""
echo "Optionale Variablen:"

if [ -z "$FINTS_PRODUCT_ID" ] || [ "$FINTS_PRODUCT_ID" == "your_product_id" ]; then
    echo -e "${YELLOW}⚠ FINTS_PRODUCT_ID nicht konfiguriert (FinTS wird nicht funktionieren)${NC}"
else
    echo -e "${GREEN}✓ FINTS_PRODUCT_ID ist gesetzt${NC}"
fi

# Zusammenfassung
echo ""
echo "================================"
if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}FEHLER: $ERRORS kritische Probleme gefunden!${NC}"
    echo "Bitte behebe diese vor dem Deployment."
    exit 1
elif [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}WARNUNG: $WARNINGS Warnungen gefunden${NC}"
    echo "Diese sollten behoben werden, sind aber nicht kritisch."
    exit 0
else
    echo -e "${GREEN}✓ Alle Prüfungen bestanden!${NC}"
    echo "Die .env Datei ist bereit für das Deployment."
    exit 0
fi
