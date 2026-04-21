# Grafana Datasource Provisioning

Die Datei `datasources.yaml` wird beim Deployment automatisch aus `datasources.yaml.template` 
erzeugt (envsubst ersetzt `${DB_PASSWORD}`). 

**Nicht** `deploy.sh` verwenden? Dann manuell:

```bash
export DB_PASSWORD="dein_db_passwort"
envsubst '${DB_PASSWORD}' < datasources.yaml.template > datasources.yaml
```

Oder das MariaDB-Passwort in Grafana unter Connections → Data sources → MariaDB → Save & test manuell setzen.

Zusätzlich liegt hier `energie-monitor.yaml` (Infinity-Datasource für den optionalen Container `energie_monitor`, siehe `docker-compose.energie-monitor.yml` im Repo-Root).
