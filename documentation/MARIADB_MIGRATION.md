# MariaDB Migration - Zusammenfassung

## ✅ Durchgeführte Änderungen

Das Projekt wurde von PostgreSQL auf **MariaDB 11.2** umgestellt.

### Geänderte Dateien

1. **Docker & Infrastruktur**
   - [docker-compose.yml](../docker-compose.yml) - MariaDB Container statt PostgreSQL
   - [requirements.txt](../requirements.txt) - `mysql-connector-python` statt `psycopg2`
   - [db/schema.sql](../db/schema.sql) - MySQL-kompatibles Schema

2. **Scripts mit .env-Integration**
   - [deploy.sh](../deploy.sh) - Liest Passwörter aus `.env`
   - [health-check.sh](../health-check.sh) - Liest Passwörter aus `.env`
   - [rollback.sh](../rollback.sh) - Liest Passwörter aus `.env`
   - **NEU:** [validate-env.sh](../validate-env.sh) - Validiert `.env` Konfiguration

3. **Anwendungscode**
   - [scripts/utils.py](../scripts/utils.py) - MariaDB-Verbindungslogik
   - [config/settings.yaml](../config/settings.yaml) - Datenbank-Typ auf `mariadb`

4. **Grafana**
   - [grafana/provisioning/datasources.yaml](../grafana/provisioning/datasources.yaml) - MySQL-Datasource

5. **CI/CD**
   - [.github/workflows/ci-cd.yml](../.github/workflows/ci-cd.yml) - Deployment-Pipeline
   - [.github/workflows/backup.yml](../.github/workflows/backup.yml) - Backup-Workflow
   - [.github/workflows/health-check.yml](../.github/workflows/health-check.yml) - Health-Check

6. **Dokumentation**
   - [.env.example](../.env.example) - MariaDB-Konfiguration
   - [DEPLOYMENT.md](DEPLOYMENT.md) - Aktualisierte Anleitung
   - [README.md](../README.md) - Aktualisierte Quick-Start-Anleitung

## 🔐 Sicherheitsverbesserungen

### Passwort-Management
Alle Scripts lesen jetzt Passwörter aus der `.env`-Datei:

```bash
# Vorher (unsicher):
mysqldump -u finanzen -pchange_me_secure_password

# Nachher (sicher):
mysqldump -u "$DB_USER" -p"$DB_PASSWORD"
```

### Validierung
Neues Script zur Validierung der Konfiguration:

```bash
./validate-env.sh
```

Prüft:
- ✅ Existenz der `.env`-Datei
- ✅ Keine Default-Passwörter
- ✅ Passwort-Länge (min. 12 Zeichen)
- ✅ Encryption Key gesetzt
- ✅ Korrekte DB-Typ Konfiguration

## 🚀 Deployment auf Proxmox-Server

### 1. Server vorbereiten

```bash
# Als root auf dem Proxmox-Server
cd /opt
git clone https://github.com/frabartolo/Finanzen.git finanzen
cd finanzen

# Docker installieren
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Verzeichnisse erstellen
mkdir -p data/{db,inbox,logs,processed} backups
```

### 2. Konfiguration

```bash
# .env erstellen
cp .env.example .env
nano .env
```

**Mindestens ändern:**
```env
DB_PASSWORD=dein_sicheres_passwort_hier
DB_ROOT_PASSWORD=dein_root_passwort_hier
ENCRYPTION_KEY=generiere_mit_openssl_rand_hex_32
```

**Key generieren:**
```bash
openssl rand -hex 32
```

### 3. Validieren

```bash
chmod +x validate-env.sh
./validate-env.sh
```

### 4. Deployment

```bash
chmod +x deploy.sh health-check.sh rollback.sh
./deploy.sh
```

## 📋 Verfügbare Befehle

```bash
# Deployment durchführen
./deploy.sh

# Konfiguration validieren
./validate-env.sh

# Health Check
./health-check.sh

# Rollback (letztes Backup wiederherstellen)
./rollback.sh

# Container-Status
docker compose ps

# Logs anzeigen
docker compose logs -f

# Manuelles Backup
docker compose exec -T db mysqldump -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" | gzip > backup_manual.sql.gz
```

## 🔄 GitHub Actions

Die CI/CD-Pipeline ist konfiguriert für automatisches Deployment:

### Benötigte GitHub Secrets

- `PROD_HOST` - IP/Hostname des Servers
- `PROD_USER` - SSH-Benutzername
- `PROD_SSH_KEY` - SSH Private Key

### Workflow

1. Push auf `main` → Automatisches Deployment
2. Täglich 02:00 Uhr → Automatisches Backup
3. Alle 15 Minuten → Health Check

## ⚠️ Migration von bestehendem PostgreSQL

Falls du bereits eine PostgreSQL-Datenbank hast:

```bash
# 1. PostgreSQL Backup exportieren
docker compose exec -T db pg_dump -U finanzen finanzen > postgres_backup.sql

# 2. SQL-Syntax anpassen (AUTO_INCREMENT, etc.)
# Manuelle Anpassung notwendig!

# 3. In MariaDB importieren
docker compose exec -T db mysql -u finanzen -p"$DB_PASSWORD" finanzen < mariadb_backup.sql
```

## 📊 Datenbank-Zugriff

```bash
# MariaDB Console
docker compose exec db mysql -u finanzen -p"$DB_PASSWORD" finanzen

# Root-Zugriff
docker compose exec db mysql -u root -p"$DB_ROOT_PASSWORD"

# Externes Tool (z.B. DBeaver)
Host: localhost (oder Server-IP)
Port: 3306
User: finanzen
Database: finanzen
```

## 🎯 Nächste Schritte

1. ✅ GitHub Secrets konfigurieren
2. ✅ `.env` auf dem Server erstellen und anpassen
3. ✅ `validate-env.sh` ausführen
4. ✅ `./deploy.sh` ausführen
5. ✅ Grafana aufrufen: `http://server-ip:3000`
6. ✅ Konten und Kategorien konfigurieren

## 📝 Notizen

- **Port**: MariaDB läuft auf Port `3306` (statt `5432`)
- **Charset**: UTF-8 (utf8mb4_unicode_ci)
- **Engine**: InnoDB für alle Tabellen
- **Backups**: Automatisch täglich um 02:00 Uhr
- **Retention**: 30 Tage

Bei Fragen oder Problemen siehe [DEPLOYMENT.md](DEPLOYMENT.md) oder [README.md](../README.md).
