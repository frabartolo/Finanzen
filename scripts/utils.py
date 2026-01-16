#!/usr/bin/env python3
"""
Hilfsfunktionen für die Finanz-Scripts
"""

import yaml
import os
import sqlite3
import re
from pathlib import Path
from typing import Dict, Any


def expand_env_vars(text: str) -> str:
    """Umgebungsvariablen in Text expandieren (${VAR} Format)"""
    def replace_var(match):
        var_name = match.group(1)
        return os.getenv(var_name, match.group(0))  # Fallback: ursprünglicher Text
    
    return re.sub(r'\$\{([^}]+)\}', replace_var, text)


def expand_dict_env_vars(data: Any) -> Any:
    """Umgebungsvariablen in Dict/List-Struktur rekursiv expandieren"""
    if isinstance(data, dict):
        return {key: expand_dict_env_vars(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [expand_dict_env_vars(item) for item in data]
    elif isinstance(data, str):
        return expand_env_vars(data)
    else:
        return data


def load_config(config_name: str) -> Dict[str, Any]:
    """YAML-Konfiguration laden mit Umgebungsvariablen-Unterstützung"""
    config_path = Path(__file__).parent.parent / "config" / f"{config_name}.yaml"
    
    if not config_path.exists():
        raise FileNotFoundError(f"Konfiguration nicht gefunden: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config_data = yaml.safe_load(f)
    
    # Umgebungsvariablen expandieren
    return expand_dict_env_vars(config_data)


def get_db_connection():
    """Datenbankverbindung herstellen"""
    settings = load_config('settings')
    db_config = settings.get('database', {})
    db_type = db_config.get('type', 'mariadb')
    
    if db_type == 'mysql' or db_type == 'mariadb':
        import mysql.connector
        return mysql.connector.connect(
            host=os.getenv('DB_HOST', 'finanzen_db'),
            port=int(os.getenv('DB_PORT', '3306')),
            database=os.getenv('DB_NAME', 'finanzen'),
            user=os.getenv('DB_USER', 'finanzen'),
            password=os.getenv('DB_PASSWORD', ''),
            connect_timeout=5
        )
    else:
        raise ValueError(f"Nicht unterstützter Datenbanktyp: {db_type}")


def get_db_placeholder():
    """Datenbankspezifische Platzhalter für SQL-Queries"""
    return '%s'  # MySQL/MariaDB Platzhalter


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

