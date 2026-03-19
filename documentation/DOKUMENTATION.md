# 🏦 Finanzen - Vollständige Dokumentation

## 📋 Inhaltsverzeichnis

- [Überblick](#überblick)
- [Installation](#installation)
- [Konfiguration](#konfiguration)
- [Verwendung](#verwendung)
- [Sicherheit](#sicherheit)
- [Wartung](#wartung)
- [Troubleshooting](#troubleshooting)
- [API-Referenz](#api-referenz)

---

## 🎯 Überblick

Die Finanzen-App ist ein vollautomatisiertes, lokales System zur Verwaltung Ihrer persönlichen Finanzen. Alle Daten bleiben auf Ihrem System - kein Cloud-Service, volle Kontrolle.

### Hauptfunktionen

- **Automatischer Bankdaten-Import** via FinTS/HBCI
- **PDF-Parsing** für Kontoauszüge
- **Intelligente Kategorisierung** mit Regelengine
- **Grafana-Dashboards** für Visualisierung
- **Verschlüsselte Credentials** für maximale Sicherheit
- **Automatische Cron-Jobs** für tägliche Updates

---

## 🚀 Installation

### Voraussetzungen

- Docker & Docker Compose
- Git
- Linux/macOS (Windows mit WSL2)

### Quick Start

```bash
# 1. Repository klonen
git clone https://github.com/frabartolo/Finanzen.git
cd Finanzen

# 2. Umgebungsvariablen konfigurieren
cp .env.example .env
nano .env  # Passwörter anpassen!

# 3. Encryption Key generieren
python3 scripts/encryption.py --generate-key
# Key in .env eintragen: ENCRYPTION_KEY=...

# 4. Deployment durchführen
chmod +x deploy.sh
./deploy.sh
```

### Erste Schritte nach Installation

```bash
# Bankzugangsdaten sicher speichern
python3 scripts/credential_manager.py migrate

# Datenbank initialisieren
docker compose exec app python3 scripts/setup_db.py

# Erste Transaktionen abrufen
docker compose exec app python3 scripts/fetch_fints.py

# Kategorisierung durchführen
docker compose exec app python3 scripts/categorize.py
```

---

## ⚙️ Konfiguration

### 1. Umgebungsvariablen (.env)

```bash
# Datenbank
DB_HOST=finanzen_db
DB_PORT=3306
DB_NAME=finanzen
DB_USER=finanzen
DB_PASSWORD=SICHERES_PASSWORT_HIER  # Mindestens 12 Zeichen!
DB_ROOT_PASSWORD=ANDERES_SICHERES_PASSWORT

# Verschlüsselung
ENCRYPTION_KEY=GENERIERTER_KEY_HIER  # Mit --generate-key erstellen

# Timezone
TZ=Europe/Berlin
```

### 2. Konten konfigurieren (config/accounts.yaml)

```yaml
accounts:
  - name: "Postbank Girokonto"
    type: "checking"
    bank: "Postbank"
    iban: "DE46370100500649213501"
    blz: "37010050"
    login_name: "${POSTBANK_LOGIN}"  # Aus verschlüsseltem Store
    pin: "${POSTBANK_PIN}"
    endpoint: "https://banking-be-1.postbank.de/fints30"
```

**Wichtig:** Zugangsdaten nicht direkt in die Datei schreiben! Stattdessen:

```bash
# Credentials verschlüsselt speichern
python3 scripts/credential_manager.py store POSTBANK_LOGIN "ihr_login"
python3 scripts/credential_manager.py store POSTBANK_PIN "ihr_pin"
```

### 3. Kategorien anpassen (config/categories.yaml)

```yaml
categories:
  income:
    - "Gehalt"
    - "Miete Sonnenberg"
  
  expenses:
    - name: "Wohnen"
      subcategories:
        - "Miete"
        - "Strom"
    - "Lebensmittel"
```

### 4. Kategorisierungsregeln

**Standard:** `config/categorization_rules.yaml` – Liste `rules:` mit Einträgen `category`, `pattern`, optional `priority` (Default 10). Regex sind case-insensitive.

**Zusätzlich (optional):** In `config/settings.yaml` unter `categorization_rules` eigene Regeln im Dict-Format – werden mit den YAML-Standardregeln **zusammengeführt** und nach Priorität sortiert.

```yaml
# config/categorization_rules.yaml (Auszug)
rules:
  - category: Gehalt
    pattern: '\b(gehalt|lohn|salary)\b'
    priority: 100
```

```yaml
# settings.yaml – nur für Ergänzungen
categorization_rules:
  "Meine Kategorie":
    - pattern: '\b(beispiel)\b'
      priority: 100
```

---

## 💻 Verwendung

### Manuelle Befehle

```bash
# FinTS-Daten abrufen
docker compose exec app python3 scripts/fetch_fints.py

# Nur Postbank
docker compose exec app python3 scripts/fetch_postbank.py

# PDFs verarbeiten (aus data/inbox/)
docker compose exec app python3 scripts/parse_pdfs.py

# Transaktionen kategorisieren
docker compose exec app python3 scripts/categorize.py

# Unkategorisierte Buchungstexte ansehen (für neue Regeln in categorization_rules.yaml)
docker compose exec app python3 scripts/categorize.py --peek 40
docker compose exec app python3 scripts/categorize.py --peek-frequent 25

# Nach neuen Einträgen in config/categories.yaml: Kategorien in die DB übernehmen
docker compose exec app python3 scripts/setup_db.py --categories-only

# Mit Force-Option (auch bereits kategorisierte neu zuordnen)
docker compose exec app python3 scripts/categorize.py --force

# Variante A: Kategorien von gelabelten Zeilen auf gleiche/ähnliche Texte übertragen
# Standard: nur innerhalb desselben Kontos. Wenn nichts passiert: --global-scope (über alle Konten)
docker compose exec app python3 scripts/propagate_categories.py
docker compose exec app python3 scripts/propagate_categories.py --apply --collapse-dates
docker compose exec app python3 scripts/propagate_categories.py --apply --collapse-dates --global-scope

# Variante B: Regel-Vorschläge aus bereits gelabelten Buchungen (YAML auf stdout, manuell prüfen & in categorization_rules.yaml übernehmen)
docker compose exec app python3 scripts/suggest_rules_from_labels.py
docker compose exec app python3 scripts/suggest_rules_from_labels.py --collapse-dates --min-repeat 3 --limit 50

# Variante C: Ollama (Modell aus settings.ollama.model_categorization, z. B. deepseek-r1:8b) für Kategorie-Vorschläge
docker compose exec app python3 scripts/categorize_with_ollama.py --limit 10
docker compose exec app python3 scripts/categorize_with_ollama.py --apply --limit 20

# Credentials verwalten
docker compose exec app python3 scripts/credential_manager.py list
docker compose exec app python3 scripts/credential_manager.py store KEY VALUE
docker compose exec app python3 scripts/credential_manager.py get KEY
```

### Automatisierung (Cron-Jobs)

Die App führt automatisch folgende Tasks aus:

- **06:00 Uhr:** FinTS-Daten abrufen
- **07:00 Uhr:** Transaktionen kategorisieren
- **Alle 2h:** PDFs aus Inbox verarbeiten
- **08:00 Uhr:** Monitoring-Report
- **Sonntags 03:00:** Alte Logs aufräumen (>90 Tage)

Konfiguration in: `cron/crontab`

### Grafana-Dashboards

Zugriff: http://localhost:3000

- **Login:** Admin-Passwort aus `.env` (`GRAFANA_ADMIN_PASSWORD`)
- **Dashboard:** "Finanzen Übersicht"

Enthält:

- Kontostand-Entwicklung
- Einnahmen vs. Ausgaben
- Kategorieverteilung (Pie Charts)
- Letzte Umsätze (Tabelle)
- Quartalsübersicht

**Hinweis:** Zeilen mit der Kategorie **„Kontoauszug“** (Kontostand-/Abrechnungs-Hinweise, keine echten Umsätze) werden in allen Kennzahlen und in der Umsatz-Tabelle **ausgeblendet**. Sie bleiben in der Datenbank für Nachvollziehbarkeit; eigene SQL-Abfragen können sie weiter anzeigen.

---

## 🔐 Sicherheit

### Verschlüsselte Credentials

```bash
# Encryption Key generieren (EINMALIG!)
python3 scripts/encryption.py --generate-key

# In .env eintragen:
ENCRYPTION_KEY=generierter_key_hier

# Bankdaten verschlüsselt speichern
python3 scripts/credential_manager.py store POSTBANK_LOGIN "ihr_login"
python3 scripts/credential_manager.py store POSTBANK_PIN "ihr_pin"

# Aus .env migrieren (alle Credentials auf einmal)
python3 scripts/credential_manager.py migrate
```

**Wichtig:**

- ENCRYPTION_KEY **niemals** in Git committen!
- Bei Verlust des Keys sind Daten **unwiederbringlich** verloren
- Backup des Keys an sicherem Ort (Passwort-Manager)

### Datenbank-Sicherheit

```bash
# Backups werden automatisch erstellt bei jedem Deployment
# Manuelles Backup:
docker compose exec finanzen_db mariadb-dump \
  -u finanzen -p finanzen > backup_$(date +%Y%m%d).sql

# Restore:
cat backup.sql | docker compose exec -T finanzen_db mariadb \
  -u finanzen -p finanzen
```

### Best Practices

1. ✅ Sichere Passwörter (min. 12 Zeichen, gemischt)
2. ✅ Credentials verschlüsselt speichern
3. ✅ .env nie in Git committen
4. ✅ Regelmäßige Backups
5. ✅ System-Updates installieren
6. ✅ Firewall aktivieren (nur localhost:3000)

---

## 🔧 Wartung

### Logs überprüfen

```bash
# Alle Service-Logs
docker compose logs -f

# Spezifischer Service
docker compose logs -f app
docker compose logs -f cron

# Log-Dateien direkt
tail -f data/logs/fetch_fints.log
tail -f data/logs/categorize.log

# Monitoring-Report manuell
docker compose exec cron /bin/bash /app/cron/monitor.sh
```

### Datenbank-Maintenance

```bash
# Datenbank-Status prüfen
docker compose exec finanzen_db mariadb -u finanzen -p \
  -e "SHOW TABLE STATUS;"

# Ungültige Transaktionen finden
docker compose exec app python3 -c "
from scripts.utils import get_db_connection
conn = get_db_connection()
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM transactions WHERE category_id IS NULL')
print(f'Unkategorisiert: {cursor.fetchone()[0]}')
"

# Statistiken
docker compose exec finanzen_db mariadb -u finanzen -p finanzen -e "
SELECT 
  COUNT(*) as total,
  SUM(CASE WHEN amount > 0 THEN 1 ELSE 0 END) as einnahmen,
  SUM(CASE WHEN amount < 0 THEN 1 ELSE 0 END) as ausgaben
FROM transactions;
"
```

### System-Updates

```bash
# Docker-Images aktualisieren
docker compose pull

# Rebuild mit neuen Abhängigkeiten
docker compose build --no-cache

# Rolling Update (kein Downtime)
./deploy.sh
```

---

## 🔍 Troubleshooting

### Problem: Datenbank nicht erreichbar

```bash
# Container-Status prüfen
docker compose ps

# Container neustarten
docker compose restart finanzen_db

# Logs prüfen
docker compose logs finanzen_db

# Manuelle Verbindung testen
docker compose exec finanzen_db mariadb -u finanzen -p
```

### Problem: FinTS-Verbindung schlägt fehl

```bash
# Credentials prüfen
python3 scripts/credential_manager.py get POSTBANK_LOGIN
python3 scripts/credential_manager.py get POSTBANK_PIN

# Manueller Test
docker compose exec app python3 scripts/fetch_postbank.py

# Logs prüfen
docker compose logs app | grep -i error

# Häufige Ursachen:
# - Falsche Credentials
# - 2FA/TAN-Verfahren erforderlich
# - Bank-Wartungsarbeiten
# - Netzwerkprobleme
```

### Problem: Kategorisierung funktioniert nicht

```bash
# Debug-Modus aktivieren
docker compose exec app python3 scripts/categorize.py --verbose

# Regeln prüfen
cat config/settings.yaml | grep -A 20 categorization_rules

# Kategorien in DB prüfen
docker compose exec finanzen_db mariadb -u finanzen -p finanzen \
  -e "SELECT * FROM categories;"

# Manuelle Kategorisierung mit Force
docker compose exec app python3 scripts/categorize.py --force
```

### Problem: Grafana zeigt keine Daten

```bash
# Datasource testen
curl http://localhost:3000/api/datasources

# Datenbank-Verbindung aus Grafana testen
docker compose exec grafana grafana-cli plugins ls

# Transaktionen in DB prüfen
docker compose exec finanzen_db mariadb -u finanzen -p finanzen \
  -e "SELECT COUNT(*) FROM transactions;"

# Grafana neustarten
docker compose restart grafana
```

### Vollständiger Reset

```bash
# ACHTUNG: Löscht ALLE Daten!
docker compose down -v
rm -rf data/db/*
./deploy.sh
```

---

## 📚 API-Referenz

### Python-Module

#### `utils.py`

```python
from scripts.utils import (
    load_config,           # YAML-Config laden
    get_db_connection,     # DB-Verbindung (roh)
    db_connection,         # Contextmanager: with db_connection() as conn (Retries + close)
    get_db_placeholder,    # SQL-Platzhalter
    get_secure_credential, # Credential aus Store
    format_amount,         # Betrag formatieren
    ensure_dir            # Verzeichnis erstellen
)
```

#### `encryption.py`

```python
from scripts.encryption import (
    CredentialEncryption,  # Verschlüsselungs-Klasse
    encrypt_credential,    # Helper: Verschlüsseln
    decrypt_credential    # Helper: Entschlüsseln
)
```

#### `categorize.py`

```python
from scripts.categorize import Categorizer

cat = Categorizer()
cat.categorize_all(force_recategorize=False)
```

#### `error_handling.py`

```python
from scripts.error_handling import (
    retry,           # Retry-Decorator
    safe_execute,    # Sichere Ausführung
    ErrorContext,    # Context Manager
    validate_config  # Config-Validierung
)

@retry(max_attempts=3, delay=2.0)
def unstable_function():
    pass
```

### Datenbank-Schema

```sql
-- Konten
CREATE TABLE accounts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,
    bank VARCHAR(255),
    iban VARCHAR(34),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Kategorien (hierarchisch)
CREATE TABLE categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    type ENUM('income', 'expense') NOT NULL,
    parent_id INT,
    FOREIGN KEY (parent_id) REFERENCES categories(id)
);

-- Transaktionen
CREATE TABLE transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    date DATE NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    description TEXT,
    category_id INT,
    source VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);
```

---

## 📝 Changelog

### Version 2.0 (Aktuell)

✨ **Neue Features:**
- Verschlüsselte Credential-Verwaltung
- Vollständige Kategorisierungs-Engine mit Regeln
- Grafana-Dashboard mit 8 Panels
- Cron-Monitoring
- Verbessertes Error-Handling
- SQL-Syntax für MariaDB korrigiert

🐛 **Bugfixes:**
- SQL-Platzhalter von ? auf %s geändert
- `executescript` durch einzelne Statements ersetzt
- `INSERT OR IGNORE` → `INSERT IGNORE`
- PDF-Parsing robuster

---

## 🤝 Support & Kontakt

Bei Fragen oder Problemen:

1. Logs überprüfen: `docker compose logs -f`
2. Troubleshooting-Sektion konsultieren
3. GitHub Issues erstellen

---

## 📄 Lizenz

Private Nutzung - Alle Rechte vorbehalten

---

**Erstellt mit ❤️ für datenschutzbewusste Finanzplanung**
