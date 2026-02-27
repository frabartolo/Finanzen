# Changelog

Alle wichtigen Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

## [2.0.0] - 2026-02-27

### 🎉 Hinzugefügt

- **Verschlüsselte Credential-Verwaltung**
  - Neues Modul `encryption.py` für sichere Verschlüsselung
  - `credential_manager.py` zum Verwalten von Bankzugangsdaten
  - Unterstützung für Fernet-Verschlüsselung mit PBKDF2
  - Migration-Tool für .env → verschlüsselte Datei

- **Vollständige Kategorisierungs-Engine**
  - Regelbasierte automatische Kategorisierung
  - Prioritäts-System für Regeln
  - Regex-Pattern-Matching
  - Custom-Regeln in `settings.yaml`
  - CLI mit `--force` und `--verbose` Optionen
  - Standard-Regeln für gängige Kategorien

- **Grafana-Dashboard**
  - Komplett vorkonfiguriertes Dashboard mit 8 Panels
  - Gesamteinnahmen/Ausgaben/Saldo-Statistiken
  - Zeitreihen-Chart für 12 Monate
  - Top-10 Ausgaben-Kategorien (Pie Chart)
  - Einnahmen nach Kategorie (Pie Chart)
  - Letzte 100 Transaktionen (Tabelle)
  - Quartalsübersicht als Bar Chart
  - Auto-Refresh alle 5 Minuten

- **Error-Handling Framework**
  - Zentrale Exception-Klassen
  - Retry-Decorator mit exponentiellem Backoff
  - `safe_execute()` Helper-Funktion
  - `ErrorContext` Context Manager
  - Config-Validierung

- **Monitoring & Cron**
  - `monitor.sh` Script für Health-Checks
  - Log-Rotation (>90 Tage)
  - Disk-Space-Monitoring
  - Alert-System

- **Dokumentation**
  - Vollständige `DOKUMENTATION.md` (40+ Seiten)
  - Installation, Konfiguration, Troubleshooting
  - API-Referenz
  - Best Practices für Sicherheit

### 🔧 Geändert

- **SQL-Syntax auf MariaDB migriert**
  - Platzhalter `?` → `%s` überall
  - `INSERT OR IGNORE` → `INSERT IGNORE`
  - `executescript()` → einzelne `execute()` Statements

- **Verbesserte Scripts**
  - `parse_pdfs.py` komplett überarbeitet
  - `fetch_fints.py` mit besserer Fehlerbehandlung
  - `utils.py` mit Credential-Integration
  - Konsistentes Logging überall

- **Docker-Konfiguration**
  - Grafana Dashboard-Mount hinzugefügt
  - Umgebungsvariablen für Datasources
  - Bessere Volume-Struktur

- **Cron-Jobs erweitert**
  - Monitoring um 08:00
  - Log-Cleanup sonntags
  - Bessere Error-Logs

### 🐛 Behoben

- SQL-Syntax-Fehler in allen Scripts
- PDF-Parsing fehlgeschlagen bei leeren Seiten
- Credential-Loading aus .env
- Datenbank-Platzhalter-Inkonsistenzen
- `setup_db.py` MySQL-Kompatibilität
- Grafana Datasource-Konfiguration

### 🔒 Sicherheit

- Verschlüsselte Credential-Storage implementiert
- PBKDF2-Key-Derivation
- File-Permissions 0600 für sensible Dateien
- Umgebungsvariablen für DB-Passwörter

### 📚 Dokumentation

- Umfassende DOKUMENTATION.md
- CHANGELOG.md
- Inline-Kommentare verbessert
- Docstrings für alle Funktionen

---

## [1.0.0] - Initial Release

### Hinzugefügt

- Basis-Projektstruktur
- Docker-Compose Setup
- FinTS-Integration (grundlegend)
- PDF-Parsing (grundlegend)
- Datenbank-Schema
- README.md

---

## Legende

- 🎉 Hinzugefügt - Neue Features
- 🔧 Geändert - Änderungen an bestehenden Features
- 🐛 Behoben - Bugfixes
- 🔒 Sicherheit - Security-Updates
- 📚 Dokumentation - Dokumentations-Änderungen
- ⚠️ Deprecated - Bald zu entfernende Features
- ❌ Entfernt - Entfernte Features
