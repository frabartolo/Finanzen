#!/usr/bin/env python3
"""
Hilfsfunktionen für die Finanz-Scripts
"""

import yaml
import os
import sqlite3
from pathlib import Path
from typing import Dict, Any


def load_config(config_name: str) -> Dict[str, Any]:
    """YAML-Konfiguration laden"""
    config_path = Path(__file__).parent.parent / "config" / f"{config_name}.yaml"
    
    if not config_path.exists():
        raise FileNotFoundError(f"Konfiguration nicht gefunden: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_db_connection():
    """Datenbankverbindung herstellen"""
    settings = load_config('settings')
    db_config = settings.get('database', {})
    db_type = db_config.get('type', 'sqlite')
    
    if db_type == 'sqlite':
        db_path = Path(__file__).parent.parent / db_config.get('path', 'data/db/finance.db')
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(str(db_path))
    
    elif db_type == 'mysql' or db_type == 'mariadb':
        import mysql.connector
        return mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '3306'),
            database=os.getenv('DB_NAME', 'finanzen'),
            user=os.getenv('DB_USER', 'finanzen'),
            password=os.getenv('DB_PASSWORD', '')
        )
    
    else:
        raise ValueError(f"Nicht unterstützter Datenbanktyp: {db_type}")


def get_account_by_iban(iban: str):
    """Account-ID anhand der IBAN abrufen"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM accounts WHERE iban = ?", (iban,))
    result = cursor.fetchone()
    conn.close()
    return result


def format_amount(amount: float, currency: str = 'EUR') -> str:
    """Betrag formatieren"""
    return f"{amount:,.2f} {currency}".replace(',', ' ').replace('.', ',')


def ensure_dir(path: Path) -> None:
    """Sicherstellen, dass Verzeichnis existiert"""
    path.mkdir(parents=True, exist_ok=True)

