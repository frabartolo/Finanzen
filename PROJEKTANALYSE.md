# Projektanalyse: Finanzen

Stand: 2026-03-19

## Kurzfazit
Das Projekt ist bereits solide aufgebaut (lokale Verarbeitung, Docker-Stack, Verschlüsselung für Credentials, klare Script-Trennung). Für die nächste Reifestufe sind vor allem **Betriebsstabilität**, **Testbarkeit** und **Sicherheits-Härtung** die größten Hebel.

---

## Positiv aufgefallen

1. **Lokaler, datenschutzfreundlicher Ansatz** mit klar formuliertem Zielbild und Automatisierung via Cron.  
2. **Sicherheitsfundament vorhanden** (Fernet + PBKDF2, getrennte Credential-Verwaltung).  
3. **Pragmatische Modularisierung** über einzelne Python-Skripte für Fetching, Parsing, Kategorisierung und Sync.
4. **Monitoring/Operations-Bausteine vorhanden** (Health-Check, Deployment/Rollback, Grafana Provisioning).

---

## Wichtigste Verbesserungsfelder (priorisiert)

## P1 — Sicherheit & Produktionshärtung

### 1) Keine Default-Credentials im Runtime-Setup
- In `docker-compose.yml` ist Grafana mit `admin/admin` vordefiniert. Das ist für lokale Entwicklung okay, sollte aber in produktionsnahen Umgebungen per `.env`/Secrets erzwungen überschrieben werden.
- Empfehlung:
  - `GF_SECURITY_ADMIN_PASSWORD` auf `${GRAFANA_ADMIN_PASSWORD}` umstellen.
  - Startup-Check ergänzen: Deployment abbrechen, wenn Default-Passwörter gesetzt sind.

### 2) Versions-Pinning bei Container-Images
- `grafana/grafana:latest` ist nicht reproduzierbar. Bei Updates können ungeplante Breaking Changes auftreten.
- Empfehlung: Version pinnen (z. B. `grafana/grafana:11.1.0`) und Update-Prozess dokumentieren.

### 3) DB-Port nicht standardmäßig veröffentlichen
- `3306:3306` öffnet die Datenbank unnötig nach außen.
- Empfehlung: Nur intern im Docker-Netz erreichbar machen; Port-Mapping optional via Profil (`docker compose --profile debug`).

---

## P1 — Zuverlässigkeit & Datenqualität

### 4) Eindeutigkeit von Transaktionen sicherstellen
- Im Schema fehlt eine technische Duplikat-Schranke für wiederholte Imports.
- Empfehlung:
  - `external_id`/`hash` pro Transaktion einführen.
  - Unique-Index (z. B. `account_id + date + amount + hash`) für idempotente Ingestion.

### 5) Kategorisierungsregeln stärker aus Code in Konfiguration verschieben
- Große Regelblöcke sind direkt im Code eingebettet. Das erschwert Pflege, Reviews und domänenspezifische Anpassungen.
- Empfehlung:
  - Regelbasis in `config/settings.yaml`/separate `rules.yaml` auslagern.
  - Loader mit Schema-Validierung ergänzen (z. B. Pflichtfelder `pattern`, `category`, `priority`).

### 6) Robustere Fehlerbehandlung bei DB-Zugriff
- Mehrere Stellen öffnen Verbindungen/Kursoren ohne konsequenten `finally`/Context-Manager-Pfad.
- Empfehlung:
  - Einheitliche DB-Helfer (`with_connection()`), inklusive Retry/Backoff und sauberem Close.

---

## P2 — Teststrategie & Wartbarkeit

### 7) Von Script-basierten Tests zu pytest-Suite
- Aktuelle Tests sind ausführbare Skripte mit `print`/`sys.exit`. Das funktioniert, skaliert aber schlecht.
- Empfehlung:
  - `tests/`-Struktur + `pytest` + Fixtures.
  - Unit-Tests für Parser/Kategorisierung, Integrations-Tests gegen Test-DB (Container).
  - CI-Pipeline mit mindestens: Lint, Type-Check, Test, Security-Scan.

### 8) Typisierung und statische Qualität erhöhen
- Bereits vorhandene Type Hints sind ein guter Anfang.
- Empfehlung:
  - `mypy`/`pyright` + `ruff`/`black` einführen.
  - Public Functions konsequent typisieren, insbesondere Datenstrukturen für Transaktionen.

### 9) Einstiegspunkt konsolidieren
- Mehrere Einstiegsskripte (`run.sh`, einzelne Python-Skripte) sind praktikabel, aber inkonsistent.
- Empfehlung:
  - Ein CLI-Einstieg (z. B. `python -m finanzen <command>` via `argparse`/`typer`) mit Subcommands.

---

## P2 — Observability

### 10) Strukturierte Logs + Metriken
- Logging ist vorhanden, aber überwiegend textuell.
- Empfehlung:
  - JSON-Logging optional aktivierbar.
  - Kernmetriken erfassen: `transactions_ingested_total`, `categorization_success_rate`, `parse_failures_total`, Laufzeiten je Job.

### 11) Health Checks um fachliche Readiness ergänzen
- Neben Prozess-Health sollte fachliche Bereitschaft geprüft werden:
  - DB erreichbar + Migrationen aktuell
  - Konfiguration valide
  - Credential Store zugreifbar

---

## 30-60-90 Tage Vorschlag

### 0-30 Tage (Quick Wins)
- Grafana-Passwort/Version härten
- DB-Port nur optional freigeben
- `pytest`-Grundgerüst + erste CI-Pipeline
- zentraler DB-Context-Manager

### 31-60 Tage
- Idempotenz-Konzept für Ingestion (Hash + Unique-Index)
- Kategorisierungsregeln aus Code in YAML überführen
- Schema-Validierung für Konfiguration

### 61-90 Tage
- Strukturierte Logs + Metriken
- E2E-Tests (FinTS/PDF Mockdaten)
- Optional: serviceorientierte Trennung (Fetch/Parse/Categorize als Jobs)

---

## Konkrete nächste Tasks (umsetzbar in Tickets)

1. **SEC-01:** Entferne `grafana:latest`, pinne Version, Passwort via Env-Variable erzwingen.  
2. **OPS-02:** Mache DB-Port-Mapping optional (Debug-Profil).  
3. **DATA-03:** Führe `transaction_hash` ein + Unique-Index + Backfill-Skript.  
4. **QA-04:** Migriere `scripts/test_*.py` in `tests/` mit `pytest`.  
5. **ARCH-05:** Regelengine entkoppeln (YAML-first + Validierung).

