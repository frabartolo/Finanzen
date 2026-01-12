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

Auf dem Zielserver:

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
# - DB_PASSWORD: Sicheres Passwort setzen
# - DB_ROOT_PASSWORD: Sicheres Root-Passwort setzen
# - ENCRYPTION_KEY: Key generieren mit: openssl rand -hex 32

# Erstes Deployment
chmod +x deploy.sh
./deploy.sh

# HINWEIS: Das Datenbank-Passwort in deploy.sh und health-check.sh
# muss manuell angepasst werden, wenn ein anderes Passwort als
# 'change_me_secure_password' verwendet wird.
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

### Manueller Backup
```bash
docker compose exec -T db pg_dump -U finanzen finanzen | gzip > backup_manual.sql.gz
```

### Health Check manuell
```bash
# Datenbank
docker compose exec db pg_isready -U finanzen

# Grafana
curl http://localhost:3000/api/health

# Container Status
docker compose ps
```

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
