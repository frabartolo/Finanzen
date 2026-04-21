# Finanzen - Automatisierte lokale Finanzübersicht

Eine vollautomatisierte, lokale und datenschutzfreundliche Lösung zur Verwaltung und Visualisierung deiner Finanzen.

## 🎯 Ziel

Vollautomatisierter Finanzüberblick – komplett lokal, sicher und reproduzierbar. Keine Cloud-Dienste, volle Kontrolle über deine Daten.

## ✨ Features

- **Automatische Datenerfassung**
  - FinTS/HBCI-Integration für Banktransaktionen
  - PDF-Parsing für Kontoauszüge
  - Manuelle Eingabemöglichkeit
  
- **Intelligente Kategorisierung**
  - Regelbasierte automatische Kategorisierung mit Prioritäts-System
  - Custom-Regeln in YAML konfigurierbar
  - Machine Learning für bessere Zuordnung (optional)
  - Manuelle Korrekturen möglich

- **Visualisierung**
  - Grafana-Dashboards für detaillierte Analysen (8 vorkonfigurierte Panels)
  - Zeitreihen, Pie Charts, Tabellen
  - Optional: Home Assistant Integration
  - Echtzeit-Updates (Auto-Refresh alle 5 Min)

- **Datenschutz & Sicherheit**
  - 100% lokal, keine Cloud
  - Verschlüsselte Credentials mit Fernet-Encryption
  - PBKDF2-Key-Derivation
  - Sichere Datenbank mit MariaDB
  - Kein Datenversand nach außen

- **Automatisierung**
  - Cron-Jobs für tägliche Updates
  - Monitoring & Health-Checks
  - Automatische Log-Rotation
  - Fehler-Benachrichtigungen

## 🏗️ Architektur

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Datenquellen   │────▶│  Verarbeitung    │────▶│  Datenbank   │
│                 │     │                  │     │              │
│ • Bank (FinTS)  │     │ • fetch_fints.py │     │  SQLite/     │
│ • PDF-Auszüge   │     │ • parse_pdfs.py  │     │  PostgreSQL  │
│ • Manuelle      │     │ • categorize.py  │     │              │
│   Eingabe       │     │ • ingest.py      │     │              │
└─────────────────┘     └──────────────────┘     └──────────────┘
                                                          │
                                                          ▼
                                                  ┌──────────────┐
                                                  │ Visualisier. │
                                                  │              │
                                                  │ • Grafana    │
                                                  │ • Home Ass.  │
                                                  └──────────────┘
```

## 🚀 Quick Start

1. **Umgebungsvariablen konfigurieren**
   ```bash
   # .env Datei erstellen
   cp .env.example .env
   
   # Encryption Key generieren
   python3 scripts/encryption.py --generate-key
   # → Key kopieren und in .env als ENCRYPTION_KEY eintragen
   
   # Passwörter und Keys setzen
   nano .env
   
   # Sichere Passwörter setzen:
   # - DB_PASSWORD: Mindestens 12 Zeichen
   # - DB_ROOT_PASSWORD: Mindestens 12 Zeichen
   # - GRAFANA_ADMIN_PASSWORD: nicht „admin“ (Pflicht für docker compose / deploy.sh)
   # - ENCRYPTION_KEY: Generierter Key von oben
   
   # Konfiguration validieren
   chmod +x validate-env.sh
   ./validate-env.sh
   ```

2. **Bankzugangsdaten sicher speichern**
   ```bash
   # Credentials verschlüsselt speichern (empfohlen!)
   python3 scripts/credential_manager.py store POSTBANK_LOGIN "ihr_login"
   python3 scripts/credential_manager.py store POSTBANK_PIN "ihr_pin"
   
   # ODER: Migration aus .env
   python3 scripts/credential_manager.py migrate
   ```

2. **Konten und Kategorien konfigurieren**
   ```bash
   # Bankkonten in config/accounts.yaml eintragen
   # WICHTIG: Keine Passwörter direkt hier! Nur ${PLATZHALTER} verwenden
   
   # Kategorien in config/categories.yaml anpassen
   # Unterstützt hierarchische Strukturen
   
   # Kategorisierungsregeln in config/settings.yaml prüfen
   # Eigene Regex-Patterns hinzufügen möglich
   ```

3. **Deployment durchführen**
   ```bash
   # Deployment-Script ausführbar machen
   chmod +x deploy.sh health-check.sh rollback.sh
   
   # Deployment starten
   ./deploy.sh
   ```

4. **Grafana aufrufen**
   ```
   http://localhost:3000
   Benutzer: admin
   Passwort: admin (beim ersten Login ändern)
   ```

## 📁 Projektstruktur

- `config/` - Konfigurationsdateien (Konten, Kategorien, Einstellungen)
- `data/inbox/` - Hier PDFs und Postbank-CSV-Exports ablegen für automatische Verarbeitung
- `scripts/` - Python-Scripts für Datenerfassung und -verarbeitung
- `db/` - Datenbank-Schema und Migrationen
- `grafana/` - Dashboard-Konfigurationen
- `cron/` - Cron-Jobs für Automatisierung

## 🔄 Automatisierung

Das System führt automatisch folgende Tasks aus:

- **Täglich 06:00**: FinTS-Daten von Banken abrufen
- **Alle 2 Stunden**: Neue PDFs und Postbank-CSV-Dateien im Inbox-Ordner verarbeiten
- **Täglich 07:00**: Transaktionen kategorisieren

Cron-Jobs können in den `cron/*.cron` Dateien angepasst werden.

## 🔧 Manuelle Aktionen

```bash
# FinTS-Daten manuell abrufen
docker compose exec app python3 scripts/fetch_fints.py

# Nur Postbank-Konten
docker compose exec app python3 scripts/fetch_postbank.py

# PDFs manuell verarbeiten (aus data/inbox/)
docker compose exec app python3 scripts/parse_pdfs.py

# Postbank-Umsätze-CSV (Semikolon, Kopf „Umsätze“ / „Buchungstag“)
docker compose exec app python3 scripts/import_postbank_csv.py
# Einzeldatei, ohne Verschieben nach processed/: --no-move
# Konto erzwingen: --account-id 1

# Transaktionen kategorisieren
docker compose exec app python3 scripts/categorize.py

# Mit Force-Option (auch bereits kategorisierte neu zuordnen)
docker compose exec app python3 scripts/categorize.py --force

# Credentials verwalten
docker compose exec app python3 scripts/credential_manager.py list
docker compose exec app python3 scripts/credential_manager.py get KEY

# Daten in DB importieren
docker compose exec app python3 scripts/ingest.py
```

## 🔐 Sicherheit

- Alle sensiblen Daten bleiben lokal
- Bankzugangsdaten werden mit Fernet verschlüsselt gespeichert (AES-128)
- PBKDF2-Key-Derivation mit 100.000 Iterationen
- Keine Verbindung zu externen Diensten (außer deiner Bank via FinTS)
- Docker-Container laufen isoliert
- File-Permissions 0600 für sensible Dateien

**Wichtig:** 
- ENCRYPTION_KEY sicher aufbewahren (Passwort-Manager)
- Bei Verlust des Keys sind Daten unwiederbringlich verloren
- Regelmäßige Backups erstellen

## 📊 Dashboards

Die Grafana-Dashboards zeigen:

- **Statistiken-Panels:**
  - Gesamteinnahmen, Gesamtausgaben, Aktueller Saldo
  
- **Zeitreihen-Charts:**
  - Einnahmen vs. Ausgaben (12 Monate)
  - Saldo-Entwicklung
  
- **Kategorieverteilung:**
  - Top 10 Ausgaben-Kategorien (Pie Chart)
  - Einnahmen nach Kategorie (Pie Chart)
  - Quartalsübersicht (Bar Chart)
  
- **Transaktions-Tabelle:**
  - Letzte 100 Transaktionen mit Filter- und Sortierfunktion
  
- **Features:**
  - Auto-Refresh alle 5 Minuten
  - Zeitraumauswahl (Standard: 30 Tage)
  - Export als CSV/PDF

Zugriff: http://localhost:3000  
Login: admin / admin (beim ersten Start ändern!)

## 🛠️ Erweiterungen

- Integration mit Home Assistant für Benachrichtigungen
- Budget-Alarme bei Überschreitungen
- Export für Steuer-Software
- Analyse von Spar-Potentialen
- Machine Learning für Kategorisierung (scikit-learn)
- REST-API für externe Zugriffe

## 📝 Dokumentation

Alle ausführlichen Anleitungen liegen im Ordner [`documentation/`](documentation/):

- [📖 Vollständige Dokumentation](documentation/DOKUMENTATION.md) – Installation, Konfiguration, API-Referenz
- [📋 Changelog](documentation/CHANGELOG.md) – Version History & Änderungen
- [🐛 Troubleshooting](documentation/DOKUMENTATION.md#troubleshooting) – Häufige Probleme & Lösungen
- [📄 PDF-Import](documentation/PDF_IMPORT_ANLEITUNG.md)
- [🚀 Deployment](documentation/DEPLOYMENT.md)

## Energie-Monitor in Grafana (optional)

Diese Repo-Konfiguration kann den Dienst aus `energie-monitor-app` ins gleiche Docker-Netz (`finanzen_net`) bringen und Grafana per **Infinity**-Datasource auf die JSON-API zeigen lassen.

1. **Repo-Nebeneinander**: `energie-monitor-app` sollte typischerweise neben `Finanzen/` liegen (z. B. `Workspace/energie-monitor-app` und `Workspace/Finanzen`).
2. **`.env` im Energie-Repo** ausfüllen (HA/Volkszähler), wie in `energie-monitor-app/.env.example` beschrieben.
3. **Stack starten** (Beispiel):

```bash
cd Finanzen
chmod +x ./deploy-energie-monitor.sh
./deploy-energie-monitor.sh
# optional mit Prod-/Dev-Overrides:
# ./deploy-energie-monitor.sh production
# ./deploy-energie-monitor.sh development
```

Alternativ manuell:

```bash
docker compose -f docker-compose.yml -f docker-compose.energie-monitor.yml up -d --build
```

4. **Grafana**: Plugin `yesoreyeram-infinity-datasource` wird über `GF_INSTALL_PLUGINS` installiert (beim ersten Start kann das einen Moment dauern). Die Datenquelle **EnergieMonitor** wird aus `grafana/provisioning/datasources/energie-monitor.yaml` provisioniert (Basis-URL: `http://energie_monitor:8080`).
5. **Panel**: Neues Panel → Datenquelle **EnergieMonitor** → Query-Typ **JSON** → URL z. B. `/api/v1/metrics/pv/current` (Methode **GET**). Für Zeitreihen/Aggregate die jeweiligen Endpunkte mit `start`/`end` Query-Parametern nutzen (siehe OpenAPI unter **`http://<host>:8080/docs`** auf dem Finanzen-Rechner, Port über `ENERGIE_HOST_PORT` änderbar).

Hinweis: Wenn du **nur** `docker-compose.prod.yml` nutzt, ist dort zusätzlich `yesoreyeram-infinity-datasource` neben `grafana-piechart-panel` eingetragen.

**Troubleshooting:** `curl` meldet „Connection reset“ auf Port 8080 oder Grafana erreicht `energie_monitor` nicht → im Skript erscheint jetzt eine **Diagnose** (Logs + Docker-Netze). Häufig: **anderes Compose-Projekt** als beim Grafana-Start – dann in `Finanzen/.env` **`COMPOSE_PROJECT_NAME`** setzen (siehe `.env.example`), Stack neu hochfahren bzw. `deploy-energie-monitor.sh` erneut ausführen.

## 📝 Lizenz

Private Nutzung - Alle Rechte vorbehalten