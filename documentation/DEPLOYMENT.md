# Deployment Konfiguration

Dieses Dokument beschreibt die Deployment-Chain für das Finanzen-Projekt.

## 🚀 Deployment-Strategie

### Übersicht

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Git Push   │────▶│  CI/CD       │────▶│  Deployment  │
│  (GitHub)    │     │  (Actions)   │     │  (Server)    │
└──────────────┘     └──────────────┘     └──────────────┘
       │                     │                     │
       │              ┌──────┴──────┐             │
       │              │             │             │
       │          ┌───▼───┐   ┌────▼────┐   ┌────▼────┐
       │          │ Build │   │  Test   │   │ Deploy  │
       │          │ Image │   │  Code   │   │ & Check │
       │          └───────┘   └─────────┘   └─────────┘
       │
       ▼
  ┌──────────────────┐
  │  Docker Images   │
  │  (ghcr.io)       │
  └──────────────────┘
```

## 🔄 CI/CD Pipeline

### 1. Automatisierte Workflows

Die Pipeline verwendet GitHub Actions mit drei Haupt-Workflows:

#### **ci-cd.yml** - Haupt-Deployment-Pipeline
- **Trigger**: Push auf `main` oder `develop`, Pull Requests
- **Schritte**:
  1. **Lint & Test**: Code-Qualität prüfen
  2. **Build Images**: Docker Images für alle Services bauen
  3. **Security Scan**: Trivy-Sicherheitsscans
  4. **Deploy Dev**: Deployment auf Development-Server (branch: `develop`)
  5. **Deploy Prod**: Deployment auf Production-Server (branch: `main`)
  6. **Notifications**: Status-Benachrichtigungen

#### **backup.yml** - Automatische Backups
- **Trigger**: Täglich um 2:00 Uhr, manuell
- **Funktionen**:
  - PostgreSQL Datenbank-Backup
  - Komprimierung (gzip)
  - Rotation (30 Tage)
  - Optional: Remote-Backup

#### **health-check.yml** - Service-Überwachung
- **Trigger**: Alle 15 Minuten, manuell
- **Prüfungen**:
  - Container-Status
  - Grafana-Erreichbarkeit
  - Datenbank-Verbindung
  - Alert bei Fehlern

### 2. Umgebungen

#### Development
- Branch: `develop`
- URL: `http://dev.finanzen.local:3000`
- Auto-Deployment bei Push

#### Production
- Branch: `main`
- URL: `http://finanzen.local:3000`
- Auto-Deployment bei Push
- Backup vor Deployment

## 🛠️ Manuelle Deployment-Scripts

### Deploy Script (`deploy.sh`)

Vollständiges Deployment-Script für lokale oder manuelle Deployments:

```bash
chmod +x deploy.sh
./deploy.sh production
```

**Features**:
- Pre-deployment Checks
- Automatisches Backup
- Image Build & Pull
- Service Health Checks
- Rollback bei Fehlern
- Cleanup alter Backups
- Optional: `--install-prereqs` installiert Docker/Git (Ubuntu/Debian/Fedora); siehe unten

### Frische Installation (neuer Linux-Rechner)

`/opt/finanzen` muss nicht existieren. Üblich ist ein Clone unter `/opt/finanzen`, aber jedes Verzeichnis reicht. `deploy.sh` ermittelt das Projektverzeichnis so: zuerst `FINANZEN_ROOT` (falls gesetzt), sonst `/opt/finanzen` wenn dort eine `docker-compose.yml` liegt, sonst das Verzeichnis, in dem `deploy.sh` liegt.

**Ablauf:**

1. Verzeichnis anlegen und Repository klonen, z. B.:
   `sudo mkdir -p /opt/finanzen && sudo chown "$USER:$USER" /opt/finanzen` und `git clone <repo-url> /opt/finanzen`
2. In das Repo wechseln, `.env` aus `.env.example` erstellen und Passwörter setzen (mindestens `GRAFANA_ADMIN_PASSWORD`).
3. Docker einrichten: `sudo ./deploy.sh --install-prereqs` (installiert Docker Engine inkl. Compose-Plugin sowie Git; Root erforderlich).
4. Den Account, unter dem du `docker compose` / `deploy.sh` ausführst, in die Gruppe `docker` aufnehmen, z. B. `sudo usermod -aG docker "$USER"`, danach neu einloggen oder `newgrp docker`.

**Welcher Linux-User?**

- **Empfohlen (einfach):** Dein normaler Login-User mit `docker`-Gruppe. Kein zusätzlicher Systemuser nötig.
- **Optional (isolierter Betrieb):** Systemuser `finanzen` anlegen, ebenfalls in `docker` aufnehmen, Repo-Verzeichnis ihm zuordnen. Für das optionale `chown` am Ende von `deploy.sh` entweder User `finanzen` existieren lassen oder `FINANZEN_CHOWN_USER=finanzen:finanzen` setzen (siehe Kopfkommentar in `deploy.sh`).

Anschließend: `./deploy.sh production`

### Rollback Script (`rollback.sh`)

Wiederherstellung des letzten Backups:

```bash
chmod +x rollback.sh
./rollback.sh
```

## 📋 Setup-Anleitung

### 1. GitHub Secrets einrichten

Folgende Secrets in GitHub Settings → Secrets → Actions hinzufügen:

#### Development Server
- `DEV_HOST`: IP/Hostname des Dev-Servers
- `DEV_USER`: SSH-Benutzername
- `DEV_SSH_KEY`: SSH Private Key

#### Production Server
- `PROD_HOST`: IP/Hostname des Prod-Servers
- `PROD_USER`: SSH-Benutzername
- `PROD_SSH_KEY`: SSH Private Key

#### Optional
- `SLACK_WEBHOOK`: Slack Webhook URL für Notifications
- `BACKUP_REMOTE_PATH`: Remote-Pfad für Backups (z.B. S3)

### 2. Server vorbereiten

Auf dem Zielserver. Für eine kompakte Checkliste auf einem leeren Rechner siehe oben **Frische Installation (neuer Linux-Rechner)**; im Folgenden die manuelle Variante mit Docker-Install-Skript:

```bash
# Repository klonen
cd /opt
git clone https://github.com/frabartolo/Finanzen.git finanzen
cd finanzen

# Docker & Docker Compose installieren
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Verzeichnisse erstellen
mkdir -p data/{db,inbox,logs,processed} backups

# Umgebungsvariablen konfigurieren
cp .env.example .env
nano .env

# WICHTIG: Folgende Werte in .env anpassen:
# - DB_PASSWORD: Sicheres Passwort (mindestens 12 Zeichen)
# - DB_ROOT_PASSWORD: Sicheres Root-Passwort (mindestens 12 Zeichen)
# - ENCRYPTION_KEY: Generieren mit: openssl rand -hex 32

# Konfiguration validieren
chmod +x validate-env.sh
./validate-env.sh

# Scripts ausführbar machen
chmod +x deploy.sh health-check.sh rollback.sh

# Erstes Deployment
./deploy.sh

# HINWEIS: Alle Scripts lesen automatisch die Passwörter aus der .env Datei
```

### 3. Lokales Setup für Development

```bash
# Repository klonen
git clone https://github.com/frabartolo/Finanzen.git
cd Finanzen

# Development Branch
git checkout -b develop

# Lokales Deployment
./deploy.sh development
```

## 🔒 Sicherheit

### Container Security
- Automatische Trivy-Scans bei jedem Build
- SARIF-Upload zu GitHub Security
- Regelmäßige Base-Image Updates

### Secrets Management
- Alle sensiblen Daten in GitHub Secrets
- Keine Secrets im Code
- SSH-Key basierte Authentifizierung

### Backup-Strategie
- Tägliche automatische Backups
- 30 Tage Retention
- Komprimierte Speicherung
- Optional: Off-site Backups

## 🎯 Deployment-Checklist

### Vor dem Deployment
- [ ] Tests lokal durchgeführt
- [ ] Secrets konfiguriert
- [ ] Server-Zugriff getestet
- [ ] Backup-Strategie geprüft

### Nach dem Deployment
- [ ] Health Checks erfolgreich
- [ ] Grafana erreichbar
- [ ] Cron-Jobs laufen
- [ ] Logs prüfen
- [ ] Backup-Job testen

## 📊 Monitoring

### Service-Status prüfen
```bash
docker compose ps
docker compose logs -f
```

### Grafana Dashboard
- URL: `http://localhost:3000`
- Default Login: `admin/admin`

### Logs
```bash
# App Logs
docker compose logs -f app

# Cron Logs
docker compose logs -f cron

# Datenbank Logs
docker compose logs -f db

# Alle Logs
docker compose logs -f
```

## 🔧 Troubleshooting

### Deployment schlägt fehl
```bash
# Logs prüfen
docker compose logs

# Container neu starten
docker compose restart

# Kompletter Neustart
docker compose down
docker compose up -d
```

### Rollback durchführen
```bash
./rollback.sh
```

### Konfiguration validieren
```bash
# Prüfe .env auf Sicherheitsprobleme
./validate-env.sh
```

### Manueller Backup
```bash
# Lädt automatisch Passwort aus .env
docker compose exec -T db mysqldump -u finanzen -p$DB_PASSWORD finanzen | gzip > backup_manual.sql.gz
```

### Health Check manuell
```bash
# Script ausführen (lädt automatisch .env)
./health-check.sh

# Oder manuell:
# Datenbank
docker compose exec db mysqladmin ping -u finanzen -p$DB_PASSWORD

# Grafana
curl http://localhost:3000/api/health

# Container Status
docker compose ps
```

## 🔒 Produktions-Härtung (Stand 2026)

- **Grafana:** Image gepinnt (`grafana/grafana:11.4.3`), Admin-Passwort nur über `GRAFANA_ADMIN_PASSWORD` in `.env` (nicht `admin`). `deploy.sh` bricht ab, wenn das Passwort fehlt oder `admin` ist.
- **MariaDB:** Standardmäßig kein Port `3306` auf dem Host; nur im Docker-Netz erreichbar. Für lokalen DB-Zugriff:  
  `docker compose -f docker-compose.yml -f docker-compose.debug-db.yml up -d`
- **Transaktionen:** Spalte `transaction_hash` + Unique-Index für idempotente Imports. Nach Upgrade einmalig:  
  `docker compose exec app python scripts/backfill_transaction_hash.py --confirm`  
  (setzt Hashes, entfernt echte Duplikate, legt Index an). `deploy.sh` führt `setup_db.py --migrations-only` aus.

## 📝 Weitere Ressourcen

- [GitHub Actions Dokumentation](https://docs.github.com/en/actions)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [PostgreSQL Backup Guide](https://www.postgresql.org/docs/current/backup.html)

## 🤝 Contribution

Bei Änderungen an der Deployment-Pipeline:
1. Feature-Branch erstellen
2. Änderungen testen
3. Pull Request erstellen
4. Review abwarten
5. Merge nach Freigabe
