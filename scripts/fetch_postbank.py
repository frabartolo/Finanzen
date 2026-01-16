#!/usr/bin/env python3
"""
Postbank FinTS Integration - Verbesserte Version mit Postbank-spezifischen Optimierungen
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
import time

# Pfad zum Projekt-Root hinzufügen
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.utils import load_config, get_db_connection

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PostbankFinTSClient:
    """Spezialisierte Klasse für Postbank FinTS-Verbindungen"""
    
    def __init__(self, account_config: Dict):
        self.account_config = account_config
        self.client = None
        self.settings = load_config('settings')
        
    def connect(self) -> bool:
        """Verbindung zur Postbank herstellen"""
        try:
            from fints.client import FinTS3PinTanClient
            
            logger.info(f"🔌 Verbinde mit Postbank für Konto: {self.account_config['name']}")
            
            # Moderne FinTS-Client Initialisierung
            # Verschiedene API-Varianten unterstützen
            try:
                # Neuere fints-Version (mit bank_identifier)
                self.client = FinTS3PinTanClient(
                    blz=self.account_config['blz'],
                    user_id=self.account_config['login_name'],
                    pin=self.account_config['pin'],
                    server=self.account_config['endpoint'],
                    bank_identifier=self.account_config['blz'],
                    product_id=self.settings.get('fints', {}).get('product_id', 'FINANZEN_APP_1.0')
                )
            except TypeError:
                # Ältere fints-Version (ohne bank_identifier)
                self.client = FinTS3PinTanClient(
                    blz=self.account_config['blz'],
                    user_id=self.account_config['login_name'],
                    pin=self.account_config['pin'],
                    server=self.account_config['endpoint'],
                    product_id=self.settings.get('fints', {}).get('product_id', 'FINANZEN_APP_1.0')
                )
            
            # Test-Verbindung
            accounts = self.client.get_sepa_accounts()
            logger.info(f"✅ Verbindung erfolgreich - {len(accounts)} Konten gefunden")
            return True
            
        except ImportError:
            logger.error("❌ fints-Bibliothek nicht installiert!")
            logger.error("   Lösung: pip install fints")
            return False
        except Exception as e:
            logger.error(f"❌ Verbindungsfehler: {e}")
            return False
    
    def get_account_balance(self) -> Optional[float]:
        """Aktuellen Kontostand abrufen"""
        if not self.client:
            return None
            
        try:
            accounts = self.client.get_sepa_accounts()
            for account in accounts:
                if account.iban == self.account_config['iban']:
                    balance = self.client.get_balance(account)
                    logger.info(f"💰 Kontostand {self.account_config['name']}: {balance.amount.amount} EUR")
                    return float(balance.amount.amount)
        except Exception as e:
            logger.error(f"❌ Fehler beim Abrufen des Kontostands: {e}")
        
        return None
    
    def get_transactions(self, days: int = 30) -> List[Dict]:
        """Transaktionen der letzten X Tage abrufen"""
        if not self.client:
            return []
        
        try:
            start_date = datetime.now() - timedelta(days=days)
            end_date = datetime.now()
            
            logger.info(f"📄 Lade Transaktionen vom {start_date.strftime('%d.%m.%Y')} bis {end_date.strftime('%d.%m.%Y')}")
            
            accounts = self.client.get_sepa_accounts()
            transactions = []
            
            for account in accounts:
                if account.iban == self.account_config['iban']:
                    trans_data = self.client.get_transactions(
                        account=account,
                        start_date=start_date,
                        end_date=end_date
                    )
                    
                    # Transaktionen in einheitliches Format konvertieren
                    for trans in trans_data:
                        transactions.append({
                            'date': trans.data.get('booking_date', datetime.now().date()),
                            'amount': float(trans.data.get('amount', {}).get('amount', 0)),
                            'currency': trans.data.get('amount', {}).get('currency', 'EUR'),
                            'purpose': trans.data.get('purpose', ''),
                            'applicant_name': trans.data.get('applicant_name', ''),
                            'applicant_iban': trans.data.get('applicant_iban', ''),
                            'reference': trans.data.get('customer_reference', ''),
                            'raw_data': str(trans.data)
                        })
            
            logger.info(f"✅ {len(transactions)} Transaktionen geladen")
            return transactions
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Laden der Transaktionen: {e}")
            return []


def setup_account_in_db(account_config: Dict) -> Optional[int]:
    """Konto in Datenbank einrichten, falls nicht vorhanden"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Prüfen ob Konto bereits existiert
        cursor.execute("SELECT id FROM accounts WHERE iban = %s", (account_config['iban'],))
        result = cursor.fetchone()
        
        if result:
            account_id = result[0]
            logger.info(f"📋 Konto bereits in DB: {account_config['name']} (ID: {account_id})")
        else:
            # Konto anlegen
            cursor.execute(
                "INSERT INTO accounts (name, type, bank, iban) VALUES (%s, %s, %s, %s)",
                (account_config['name'], account_config['type'], account_config['bank'], account_config['iban'])
            )
            account_id = cursor.lastrowid
            conn.commit()
            logger.info(f"✅ Konto in DB angelegt: {account_config['name']} (ID: {account_id})")
        
        return account_id
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Einrichten des Kontos: {e}")
        return None
    finally:
        conn.close()


def save_transactions_to_db(transactions: List[Dict], account_id: int) -> int:
    """Transaktionen in Datenbank speichern"""
    if not transactions:
        return 0
    
    conn = get_db_connection()
    cursor = conn.cursor()
    inserted = 0
    
    try:
        for trans in transactions:
            # Duplikatsprüfung (gleiche Transaktion bereits vorhanden?)
            cursor.execute(
                """SELECT id FROM transactions 
                   WHERE account_id = %s AND date = %s AND amount = %s AND description = %s""",
                (account_id, trans['date'], trans['amount'], trans['purpose'])
            )
            
            if cursor.fetchone() is None:
                cursor.execute(
                    """INSERT INTO transactions (account_id, date, amount, description, source)
                       VALUES (%s, %s, %s, %s, 'fints')""",
                    (account_id, trans['date'], trans['amount'], 
                     f"{trans['purpose']} | {trans['applicant_name']}")
                )
                inserted += 1
        
        conn.commit()
        logger.info(f"💾 {inserted} neue Transaktionen in DB gespeichert")
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Speichern: {e}")
    finally:
        conn.close()
    
    return inserted


def fetch_postbank_account(account_config: Dict) -> bool:
    """Einzelnes Postbank-Konto verarbeiten"""
    logger.info(f"🏦 Verarbeite Konto: {account_config['name']}")
    
    # Account in DB einrichten
    account_id = setup_account_in_db(account_config)
    if not account_id:
        return False
    
    # FinTS-Client initialisieren
    client = PostbankFinTSClient(account_config)
    if not client.connect():
        return False
    
    # Kontostand abrufen
    balance = client.get_account_balance()
    
    # Transaktionen abrufen
    settings = load_config('settings')
    days = settings.get('fints', {}).get('default_days', 30)
    transactions = client.get_transactions(days)
    
    # Transaktionen speichern
    saved = save_transactions_to_db(transactions, account_id)
    
    logger.info(f"✅ Konto {account_config['name']} verarbeitet: {saved} neue Transaktionen")
    return True


def main():
    """Alle Postbank-Konten verarbeiten"""
    logger.info("🚀 Starte Postbank FinTS-Abruf...")
    
    # Konfiguration laden
    accounts_config = load_config('accounts')
    settings = load_config('settings')
    
    if not settings.get('fints', {}).get('enabled', False):
        logger.error("❌ FinTS ist deaktiviert! Bitte in config/settings.yaml aktivieren.")
        return
    
    success_count = 0
    total_accounts = 0
    
    for account in accounts_config.get('accounts', []):
        if account.get('bank', '').lower() == 'postbank':
            total_accounts += 1
            if fetch_postbank_account(account):
                success_count += 1
            
            # Kurze Pause zwischen Konten
            time.sleep(2)
    
    logger.info(f"🎉 Postbank-Abruf abgeschlossen: {success_count}/{total_accounts} Konten erfolgreich")


if __name__ == "__main__":
    main()