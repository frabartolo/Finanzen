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
- `data/inbox/` - Hier PDFs ablegen für automatische Verarbeitung
- `scripts/` - Python-Scripts für Datenerfassung und -verarbeitung
- `db/` - Datenbank-Schema und Migrationen
- `grafana/` - Dashboard-Konfigurationen
- `cron/` - Cron-Jobs für Automatisierung

## 🔄 Automatisierung

Das System führt automatisch folgende Tasks aus:

- **Täglich 06:00**: FinTS-Daten von Banken abrufen
- **Alle 2 Stunden**: Neue PDFs im Inbox-Ordner verarbeiten
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

- [📖 Vollständige Dokumentation](DOKUMENTATION.md) - Installation, Konfiguration, API-Referenz
- [📋 Changelog](CHANGELOG.md) - Version History & Änderungen
- [🐛 Troubleshooting](DOKUMENTATION.md#troubleshooting) - Häufige Probleme & Lösungen

## 📝 Lizenz

Private Nutzung - Alle Rechte vorbehalten