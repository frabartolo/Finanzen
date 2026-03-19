#!/usr/bin/env python3
"""
Hilfsfunktionen für die Finanz-Scripts
"""

import yaml
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Optional
import logging

logger = logging.getLogger(__name__)


def expand_env_vars(text: str) -> str:
    """Umgebungsvariablen in Text expandieren (${VAR} Format)"""
    def replace_var(match):
        var_name = match.group(1)
        
        # Zuerst versuchen aus verschlüsseltem Store zu laden
        value = get_secure_credential(var_name)
        if value:
            return value
        
        # Fallback: aus Environment
        return os.getenv(var_name, match.group(0))
    
    return re.sub(r'\$\{([^}]+)\}', replace_var, text)


def get_secure_credential(key: str) -> Optional[str]:
    """
    Holt eine Credential aus dem verschlüsselten Store
    
    Args:
        key: Credential-Key (z.B. "POSTBANK_PIN")
    
    Returns:
        Credential-Wert oder None
    """
    try:
        from scripts.credential_manager import CredentialManager
        manager = CredentialManager()
        return manager.get_credential(key)
    except Exception as e:
        logger.debug(f"Credential '{key}' nicht im verschlüsselten Store: {e}")
        return None


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


@contextmanager
def db_connection(retries: int = 3, backoff_base: float = 0.5) -> Iterator[Any]:
    """
    Kontextmanager: Verbindung mit Retries beim Connect, sauberes close im finally.
    Aufrufer führt commit/rollback selbst aus.
    """
    last_error: Optional[BaseException] = None
    conn = None
    for attempt in range(max(1, retries)):
        try:
            conn = get_db_connection()
            break
        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                time.sleep(backoff_base * (2**attempt))
            else:
                raise last_error from None
    assert conn is not None
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            logger.debug("db_connection: Fehler beim Schließen der Verbindung", exc_info=True)


def get_db_placeholder():
    """Datenbankspezifische Platzhalter für SQL-Queries"""
    return '%s'  # MySQL/MariaDB Platzhalter


def get_account_by_iban(iban: str):
    """Account-ID anhand der IBAN abrufen"""
    with db_connection() as conn:
        cursor = conn.cursor()
        ph = get_db_placeholder()
        cursor.execute(f"SELECT id, name FROM accounts WHERE iban = {ph}", (iban,))
        return cursor.fetchone()


def format_amount(amount: float, currency: str = 'EUR') -> str:
    """Betrag formatieren"""
    return f"{amount:,.2f} {currency}".replace(',', ' ').replace('.', ',')


def ensure_dir(path: Path) -> None:
    """Sicherstellen, dass Verzeichnis existiert"""
    path.mkdir(parents=True, exist_ok=True)


def compute_transaction_hash(
    account_id: int,
    date,
    amount,
    description: str,
    source: str,
) -> str:
    """
    Deterministischer Hash für idempotente Imports (Duplikat-Schutz).
    Gleiche logische Buchung = gleicher Hash bei gleichem account_id, date, amount, description, source.
    """
    import hashlib
    from decimal import Decimal, InvalidOperation

    if hasattr(date, "isoformat"):
        dkey = date.isoformat()
    else:
        dkey = str(date)
    try:
        aq = Decimal(str(amount)).quantize(Decimal("0.01"))
        akey = format(aq, "f")
    except (InvalidOperation, TypeError, ValueError):
        akey = str(amount)
    desc = (description or "").strip()
    key = f"{account_id}|{dkey}|{akey}|{desc}|{source or ''}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


