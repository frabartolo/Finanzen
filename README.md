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
  - Regelbasierte automatische Kategorisierung
  - Machine Learning für bessere Zuordnung (optional)
  - Manuelle Korrekturen möglich

- **Visualisierung**
  - Grafana-Dashboards für detaillierte Analysen
  - Optional: Home Assistant Integration
  - Echtzeit-Updates

- **Datenschutz**
  - 100% lokal, keine Cloud
  - Verschlüsselte Datenbank
  - Kein Datenversand nach außen

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

1. **Konfiguration anpassen**
   ```bash
   # Bankkonten in config/accounts.yaml eintragen
   # Kategorien in config/categories.yaml anpassen
   # Einstellungen in config/settings.yaml prüfen
   ```

2. **Docker-Container starten**
   ```bash
   docker-compose up -d
   ```

3. **Datenbank initialisieren**
   ```bash
   docker-compose exec app python scripts/setup_db.py
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
python scripts/fetch_fints.py

# PDFs manuell verarbeiten
python scripts/parse_pdfs.py

# Transaktionen kategorisieren
python scripts/categorize.py

# Daten in DB importieren
python scripts/ingest.py
```

## 🔐 Sicherheit

- Alle sensiblen Daten bleiben lokal
- Bankzugangsdaten werden verschlüsselt gespeichert
- Keine Verbindung zu externen Diensten (außer deiner Bank via FinTS)
- Docker-Container laufen isoliert

## 📊 Dashboards

Die Grafana-Dashboards zeigen:

- Kontostand-Entwicklung
- Einnahmen vs. Ausgaben
- Kategorieverteilung
- Monatliche/Jährliche Trends
- Budget-Übersichten

## 🛠️ Erweiterungen

- Integration mit Home Assistant für Benachrichtigungen
- Budget-Alarme bei Überschreitungen
- Export für Steuer-Software
- Analyse von Spar-Potentialen

## 📝 Lizenz

Private Nutzung - Alle Rechte vorbehalten