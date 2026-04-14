# Projektanalyse: Finanzen

Stand Analyse: 2026-03-19 · **Umsetzungsstand: 2026-03-19**

## Umsetzungsstand (erledigt)

| Punkt | Status | Kurz |
|-------|--------|------|
| **1** Grafana kein Default-Passwort | ✅ | `GF_SECURITY_ADMIN_PASSWORD` aus `.env`; `deploy.sh` bricht bei fehlendem Passwort / `admin` ab |
| **2** Grafana-Image pinnen | ✅ | `grafana/grafana:11.4.3` in `docker-compose.yml` |
| **3** DB-Port nicht öffentlich | ✅ | Kein `3306:3306` im Standard-Compose; optional `docker-compose.debug-db.yml` (127.0.0.1) |
| **4** Transaktions-Duplikate | ✅ | `transaction_hash` + Unique-Index; `INSERT IGNORE`; `backfill_transaction_hash.py`; siehe `DEPLOYMENT.md` |
| **5** Regeln in Konfiguration | ✅ | `config/categorization_rules.yaml` + `scripts/categorization_rules.py` (Validierung); Zusatz in `settings.yaml` möglich |
| **6** DB-Zugriff | ✅ | `db_connection()` in `utils.py` (Contextmanager, Retries/Backoff); genutzt in categorize, parse_pdfs, fetch_*, backfill, manage_accounts, reset_db, repair_documents, categorize_vermietung; `setup_db.py` noch direkt `get_db_connection` |
| **7** pytest-Suite | ✅ | `tests/test_categorization.py`, `test_categorization_rules.py`, `test_parse_pdfs.py`, `test_transaction_hash.py`; `scripts/test_*.py` rufen pytest auf |

---

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

### 1) Keine Default-Credentials im Runtime-Setup — ✅ umgesetzt
- ~~In `docker-compose.yml` ist Grafana mit `admin/admin` vordefiniert.~~ Ersetzt durch `GRAFANA_ADMIN_PASSWORD` (siehe `.env.example`); `deploy.sh` validiert.
- Empfehlung:
  - ~~`GF_SECURITY_ADMIN_PASSWORD` auf `${GRAFANA_ADMIN_PASSWORD}` umstellen.~~
  - ~~Startup-Check~~ → in `deploy.sh` integriert.

### 2) Versions-Pinning bei Container-Images — ✅ umgesetzt
- ~~`grafana/grafana:latest`~~ → **`grafana/grafana:11.4.3`**; Hinweise in `documentation/DEPLOYMENT.md`.

### 3) DB-Port nicht standardmäßig veröffentlichen — ✅ umgesetzt
- ~~`3306:3306`~~ entfernt aus Standard-`docker-compose.yml`; optional **`docker-compose.debug-db.yml`** (Bind `127.0.0.1:3306`).

---

## P1 — Zuverlässigkeit & Datenqualität

### 4) Eindeutigkeit von Transaktionen sicherstellen — ✅ umgesetzt
- ~~Im Schema fehlt eine technische Duplikat-Schranke~~ → Spalte **`transaction_hash`**, Unique **`(account_id, transaction_hash)`**, `compute_transaction_hash()` (Konto+Datum+Betrag+Beschreibung, **ohne** Importquelle), **`INSERT IGNORE`** in PDF/FinTS/CSV-Imports, **`scripts/backfill_transaction_hash.py`**, Migration in `setup_db.py` / `deploy.sh`.

### 5) Kategorisierungsregeln stärker aus Code in Konfiguration verschieben — ✅ umgesetzt
- ~~Regelblöcke im Code~~ → **`config/categorization_rules.yaml`** (`rules:` mit `category`, `pattern`, `priority`).
- **`scripts/categorization_rules.py`**: Laden, Regex-Validierung, optionales Merge mit `settings.yaml` → `categorization_rules` (Dict-Format wie bisher).
- **`scripts/categorize.py`** nutzt nur noch den Loader.

### 6) Robustere Fehlerbehandlung bei DB-Zugriff — ✅ umgesetzt (Kernpfade)
- **`scripts.utils.db_connection`**: Contextmanager, Connect-Retries mit exponentiellem Backoff, sauberes `close`.
- Eingesetzt u. a. in `categorize`, `parse_pdfs`, `fetch_fints`, `fetch_postbank`, `backfill_transaction_hash`, `categorize_vermietung`, `manage_accounts`, `reset_db`, `repair_documents_table`, `get_account_by_iban`.
- **`setup_db.py`**: weiterhin direktes `get_db_connection` (Migration/Setup; bei Bedarf später vereinheitlichen).

---

## P2 — Teststrategie & Wartbarkeit

### 7) Von Script-basierten Tests zu pytest-Suite — ✅ umgesetzt (ohne Test-DB)
- **`tests/`:** `test_transaction_hash`, `test_categorization`, `test_categorization_rules`, `test_parse_pdfs`.
- **`scripts/test_categorization.py`** / **`test_parse_pdfs.py`:** rufen `pytest` auf (Kompatibilität).
- Offen (optional): Integrations-Tests gegen Test-DB, gemeinsame Fixtures.

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
- ~~Grafana-Passwort/Version härten~~ ✅
- ~~DB-Port nur optional freigeben~~ ✅
- ~~`pytest`-Grundgerüst + CI~~ ✅
- ~~zentraler DB-Context-Manager~~ ✅ (`db_connection`)

### 31-60 Tage
- ~~Idempotenz-Konzept für Ingestion (Hash + Unique-Index)~~ ✅
- ~~Kategorisierungsregeln aus Code in YAML überführen~~ ✅
- Schema-Validierung für Konfiguration → 🔶 (Regeln validiert; restliche `settings.yaml` optional)

### 61-90 Tage
- Strukturierte Logs + Metriken
- E2E-Tests (FinTS/PDF Mockdaten)
- Optional: serviceorientierte Trennung (Fetch/Parse/Categorize als Jobs)

---

## Konkrete nächste Tasks (umsetzbar in Tickets)

1. ~~**SEC-01:** Entferne `grafana:latest`, pinne Version, Passwort via Env-Variable erzwingen.~~ ✅  
2. ~~**OPS-02:** Mache DB-Port-Mapping optional (Debug-Profil).~~ ✅ (`docker-compose.debug-db.yml`)  
3. ~~**DATA-03:** Führe `transaction_hash` ein + Unique-Index + Backfill-Skript.~~ ✅  
4. ~~**QA-04:** Migriere `scripts/test_*.py` in `tests/` mit `pytest`.~~ ✅  
5. ~~**ARCH-05:** Regelengine entkoppeln (YAML-first + Validierung).~~ ✅ (`categorization_rules.yaml` + Loader)

