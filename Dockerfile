FROM python:3.11-alpine

# Arbeitsverzeichnis erstellen
WORKDIR /app

# System-Abhängigkeiten installieren (MariaDB/MySQL statt PostgreSQL)
RUN apk add --no-cache \
    gcc \
    musl-dev \
    mysql-dev \
    libffi-dev \
    openssl-dev \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-data-deu \
    mariadb-connector-c-dev \
    pkgconfig

# Python-Abhängigkeiten kopieren und installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Anwendungscode kopieren
COPY scripts/ ./scripts/
COPY config/ ./config/
COPY db/ ./db/

# Logs-Verzeichnis erstellen
RUN mkdir -p /app/data/logs

# Standard-Befehl (läuft kontinuierlich)
CMD ["python", "-u", "scripts/ingest.py"]
