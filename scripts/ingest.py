#!/usr/bin/env python3
"""
Haupt-Service für Finanzen-App
"""

import os
import time
import logging
from datetime import datetime

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_environment():
    """Prüfe Umgebungsvariablen und Konfiguration"""
    logger.info("Prüfe Umgebungsvariablen...")
    
    required_vars = ['DB_HOST', 'DB_USER', 'DB_PASSWORD', 'DB_NAME']
    for var in required_vars:
        value = os.getenv(var)
        if value:
            logger.info(f"{var}: {'*' * len(value) if 'PASSWORD' in var else value}")
        else:
            logger.warning(f"{var}: NICHT GESETZT")
    
    # Prüfe Verzeichnisse
    directories = ['/app/data', '/app/data/logs', '/app/config']
    for directory in directories:
        if os.path.exists(directory):
            logger.info(f"Verzeichnis vorhanden: {directory}")
        else:
            logger.warning(f"Verzeichnis fehlt: {directory}")

def test_database_connection():
    """Teste Datenbankverbindung"""
    try:
        import mysql.connector
        logger.info("MySQL Connector erfolgreich importiert")
        
        config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', '3306')),
            'user': os.getenv('DB_USER', 'finanzen'),
            'password': os.getenv('DB_PASSWORD', ''),
            'database': os.getenv('DB_NAME', 'finanzen')
        }
        
        logger.info(f"Verbinde zu Datenbank: {config['host']}:{config['port']}")
        connection = mysql.connector.connect(**config)
        cursor = connection.cursor()
        cursor.execute("SELECT 'Database connection OK' as status")
        result = cursor.fetchone()
        logger.info(f"Datenbank-Test: {result[0]}")
        cursor.close()
        connection.close()
        return True
        
    except Exception as e:
        logger.error(f"Datenbankverbindung fehlgeschlagen: {e}")
        return False

def main_loop():
    """Hauptschleife - läuft kontinuierlich"""
    logger.info("Starte Haupt-Service-Loop...")
    
    while True:
        try:
            logger.info(f"Service läuft - {datetime.now()}")
            # Hier würden später die echten Tasks laufen
            time.sleep(300)  # 5 Minuten warten
            
        except KeyboardInterrupt:
            logger.info("Service wird beendet...")
            break
        except Exception as e:
            logger.error(f"Fehler im Service: {e}")
            time.sleep(60)  # Bei Fehler 1 Minute warten

if __name__ == "__main__":
    logger.info("=== Finanzen App gestartet ===")
    
    try:
        # Umgebung prüfen
        check_environment()
        
        # Datenbank testen
        db_ok = test_database_connection()
        
        if db_ok:
            logger.info("Alle Checks erfolgreich - Service läuft kontinuierlich")
            main_loop()
        else:
            logger.error("Datenbank nicht verfügbar - Service läuft im Debug-Modus")
            # Trotzdem laufen lassen für Debugging
            while True:
                logger.info("Warte auf Datenbankverbindung...")
                if test_database_connection():
                    logger.info("Datenbank jetzt verfügbar!")
                    main_loop()  # Starte main_loop nach erfolgreicher DB-Verbindung
                    break
                time.sleep(30)
                
    except Exception as e:
        logger.error(f"Kritischer Fehler beim Start: {e}")
        # Auch bei Fehlern kontinuierlich laufen lassen
        logger.info("Fallback: Service läuft im Fehlermodus...")
        while True:
            logger.error("Service im Fehlermodus - warte 5 Minuten...")
            time.sleep(300)
