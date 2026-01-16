#!/bin/bash
# Finanzen App - Python Script Runner für Ubuntu/Linux
# Verwendung: ./run.sh script_name [arguments]

# Wechsle ins Projektverzeichnis
cd "$(dirname "$0")"

# Python-Executable ermitteln
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
elif [ -f "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
else
    PYTHON="python3"
fi

case "$1" in
    "accounts")
        $PYTHON scripts/manage_accounts.py "${@:2}"
        ;;
    "postbank")
        $PYTHON scripts/fetch_postbank.py "${@:2}"
        ;;
    "categorize")
        $PYTHON scripts/categorize.py "${@:2}"
        ;;
    "fints")
        $PYTHON scripts/fetch_fints.py "${@:2}"
        ;;
    "ingest")
        $PYTHON scripts/ingest.py "${@:2}"
        ;;
    "setup")
        $PYTHON scripts/setup_db.py "${@:2}"
        ;;
    "parse")
        $PYTHON scripts/parse_pdfs.py "${@:2}"
        ;;
    *)
        echo "Verwendung: ./run.sh [accounts|postbank|categorize|fints|ingest|setup|parse] [parameter]"
        echo ""
        echo "Beispiele:"
        echo "  ./run.sh accounts list      - Alle Konten anzeigen"
        echo "  ./run.sh accounts test      - FinTS-Verbindungen testen"
        echo "  ./run.sh accounts sync      - Konten in DB synchronisieren"
        echo "  ./run.sh postbank           - Postbank-Daten abrufen"
        echo "  ./run.sh categorize         - Transaktionen kategorisieren"
        echo "  ./run.sh setup              - Datenbank einrichten"
        echo ""
        echo "Python-Executable: $PYTHON"
        ;;
esac