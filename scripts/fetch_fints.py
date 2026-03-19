#!/usr/bin/env python3
"""
FinTS-Daten von Bankkonten abrufen
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict
import logging

# Pfad zum Projekt-Root hinzufügen
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.utils import load_config, get_db_connection, compute_transaction_hash

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_transactions_for_account(account: Dict) -> List[Dict]:
    """
    Transaktionen für ein Konto via FinTS abrufen
    
    Args:
        account: Account-Konfiguration mit IBAN, BLZ, etc.
    
    Returns:
        Liste von Transaktionen
    """
    logger.info(f"🏦 Rufe Transaktionen ab für: {account['name']}")
    
    # Prüfen ob FinTS aktiviert ist
    settings = load_config('settings')
    if not settings.get('fints', {}).get('enabled', False):
        logger.warning("⚠️ FinTS ist deaktiviert. Bitte in config/settings.yaml aktivieren.")
        return []
    
    try:
        from fints.client import FinTS3PinTanClient
        
        # FinTS-Client initialisieren
        # WICHTIG: Zugangsdaten sollten verschlüsselt gespeichert werden!
        client = FinTS3PinTanClient(
            account.get('blz'),
            account.get('login_name'),
            account.get('pin'),  # In Produktion: verschlüsselt laden!
            account.get('endpoint')
        )
        
        # Transaktionen der letzten 30 Tage abrufen
        start_date = datetime.now() - timedelta(days=30)
        accounts = client.get_sepa_accounts()
        
        transactions = []
        for sepa_account in accounts:
            if sepa_account.iban == account.get('iban'):
                raw = client.get_transactions(sepa_account, start_date)
                for t in raw:
                    # Einheitliches Format: Verwendungszweck + Auftraggeber für bessere Kategorisierung
                    if hasattr(t, 'data') and isinstance(getattr(t, 'data'), dict):
                        d = t.data
                        purpose = d.get('purpose', '') or ''
                        name = d.get('applicant_name', '') or ''
                        ref = d.get('customer_reference', '') or ''
                        parts = [p for p in [purpose, name, ref] if p]
                        description = ' | '.join(parts) if parts else purpose or '—'
                        amount_val = d.get('amount')
                        if isinstance(amount_val, dict):
                            amount = float(amount_val.get('amount', 0))
                        else:
                            amount = float(amount_val or 0)
                        booking = d.get('booking_date')
                        if hasattr(booking, 'date'):
                            booking = booking.date()
                        transactions.append({
                            'date': booking or datetime.now().date(),
                            'amount': amount,
                            'purpose': description,
                        })
                    elif isinstance(t, dict):
                        purpose = t.get('purpose', '')
                        name = t.get('applicant_name', '')
                        description = f"{purpose} | {name}".strip(' |') if name else (purpose or '—')
                        transactions.append({
                            'date': t.get('date', datetime.now().date()),
                            'amount': float(t.get('amount', 0)),
                            'purpose': description,
                        })
                    else:
                        continue
                break
        
        logger.info(f"✅ {len(transactions)} Transaktionen abgerufen")
        return transactions
        
    except ImportError:
        logger.error("❌ fints-Bibliothek nicht installiert. Führe aus: pip install fints")
        return []
    except Exception as e:
        logger.error(f"❌ Fehler beim Abrufen der Transaktionen: {e}")
        return []


def save_transactions(transactions: List[Dict], account_id: int) -> None:
    """
    Transaktionen in Datenbank speichern
    
    Args:
        transactions: Liste von Transaktionen
        account_id: ID des Kontos
    """
    if not transactions:
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    inserted = 0
    for trans in transactions:
        try:
            desc = trans["purpose"] or ""
            tx_hash = compute_transaction_hash(
                account_id, trans["date"], trans["amount"], desc, "fints"
            )
            cursor.execute(
                """
                INSERT IGNORE INTO transactions
                (account_id, date, amount, description, source, transaction_hash)
                VALUES (%s, %s, %s, %s, 'fints', %s)
                """,
                (account_id, trans["date"], trans["amount"], desc, tx_hash),
            )
            if cursor.rowcount > 0:
                inserted += 1
        except Exception as e:
            logger.error(f"❌ Fehler beim Speichern der Transaktion: {e}")
    
    conn.commit()
    conn.close()
    
    logger.info(f"💾 {inserted} neue Transaktionen gespeichert")


def fetch_all_accounts() -> None:
    """Alle konfigurierten Konten verarbeiten"""
    logger.info("🚀 Starte FinTS-Abruf...")
    
    accounts_config = load_config('accounts')
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for account in accounts_config.get('accounts', []):
        # Account-ID aus Datenbank holen
        cursor.execute("SELECT id FROM accounts WHERE iban = %s", (account.get('iban'),))
        result = cursor.fetchone()
        
        if result:
            account_id = result[0]
            transactions = fetch_transactions_for_account(account)
            save_transactions(transactions, account_id)
        else:
            logger.warning(f"⚠️ Konto nicht in Datenbank gefunden: {account['name']}")
    
    conn.close()
    logger.info("✅ FinTS-Abruf abgeschlossen")


if __name__ == "__main__":
    fetch_all_accounts()
