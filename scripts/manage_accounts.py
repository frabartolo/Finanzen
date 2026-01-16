#!/usr/bin/env python3
"""
Kontoverwaltung - Konten anzeigen, testen und verwalten
"""

import sys
from pathlib import Path
from typing import List, Dict
import logging

# Pfad zum Projekt-Root hinzufügen
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.utils import load_config, get_db_connection
from scripts.fetch_postbank import PostbankFinTSClient, setup_account_in_db

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def list_configured_accounts():
    """Alle konfigurierten Konten anzeigen"""
    print("\n" + "="*60)
    print("🏦 KONFIGURIERTE KONTEN")
    print("="*60)
    
    accounts_config = load_config('accounts')
    
    for i, account in enumerate(accounts_config.get('accounts', []), 1):
        print(f"\n{i}. {account['name']}")
        print(f"   Bank: {account.get('bank', 'Nicht angegeben')}")
        print(f"   Typ: {account.get('type', 'Nicht angegeben')}")
        print(f"   IBAN: {account.get('iban', 'Nicht angegeben')}")
        if account.get('blz'):
            print(f"   BLZ: {account['blz']}")
        if account.get('endpoint'):
            print(f"   FinTS: ✅ Konfiguriert")
        else:
            print(f"   FinTS: ❌ Nicht konfiguriert")


def list_database_accounts():
    """Alle Konten aus der Datenbank anzeigen"""
    print("\n" + "="*60)
    print("💾 KONTEN IN DATENBANK")
    print("="*60)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT a.id, a.name, a.type, a.bank, a.iban, 
                   COUNT(t.id) as transaction_count,
                   MAX(t.date) as last_transaction
            FROM accounts a
            LEFT JOIN transactions t ON a.id = t.account_id
            GROUP BY a.id
            ORDER BY a.name
        """)
        
        accounts = cursor.fetchall()
        
        if not accounts:
            print("❌ Keine Konten in der Datenbank gefunden")
            return
        
        for account in accounts:
            acc_id, name, acc_type, bank, iban, trans_count, last_trans = account
            print(f"\nID {acc_id}: {name}")
            print(f"   Bank: {bank or 'Nicht angegeben'}")
            print(f"   Typ: {acc_type}")
            print(f"   IBAN: {iban or 'Nicht angegeben'}")
            print(f"   Transaktionen: {trans_count}")
            if last_trans:
                print(f"   Letzte Transaktion: {last_trans}")
            else:
                print(f"   Letzte Transaktion: Keine vorhanden")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Lesen der Datenbank: {e}")


def test_fints_connection(account_name: str = None):
    """FinTS-Verbindung für ein Konto testen"""
    accounts_config = load_config('accounts')
    
    if account_name:
        # Spezifisches Konto testen
        account = next((acc for acc in accounts_config.get('accounts', []) 
                       if acc['name'].lower() == account_name.lower()), None)
        if not account:
            print(f"❌ Konto '{account_name}' nicht gefunden")
            return
        accounts_to_test = [account]
    else:
        # Alle Konten mit FinTS-Konfiguration testen
        accounts_to_test = [acc for acc in accounts_config.get('accounts', []) 
                           if acc.get('blz') and acc.get('endpoint')]
    
    print("\n" + "="*60)
    print("🔍 FINTS-VERBINDUNGSTEST")
    print("="*60)
    
    for account in accounts_to_test:
        print(f"\n🧪 Teste Verbindung: {account['name']}")
        
        client = PostbankFinTSClient(account)
        if client.connect():
            print(f"✅ Verbindung erfolgreich!")
            
            # Kontostand testen
            balance = client.get_account_balance()
            if balance is not None:
                print(f"💰 Aktueller Kontostand: {balance:.2f} EUR")
        else:
            print(f"❌ Verbindung fehlgeschlagen!")


def sync_accounts_to_db():
    """Alle konfigurierten Konten in die Datenbank synchronisieren"""
    print("\n" + "="*60)
    print("🔄 SYNCHRONISIERE KONTEN IN DATENBANK")
    print("="*60)
    
    # Prüfen ob Datenbank verfügbar ist
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES LIKE 'accounts'")
        if not cursor.fetchone():
            print("❌ Datenbank-Tabellen existieren noch nicht!")
            print("   Lösung: ./deploy.sh production ausführen")
            return
        conn.close()
    except Exception as e:
        print(f"❌ Datenbank nicht verfügbar: {e}")
        print("   Lösung: ./deploy.sh production ausführen")
        return
    
    accounts_config = load_config('accounts')
    
    for account in accounts_config.get('accounts', []):
        account_id = setup_account_in_db(account)
        if account_id:
            print(f"✅ {account['name']} → DB ID {account_id}")


def show_recent_transactions(limit: int = 10):
    """Neueste Transaktionen anzeigen"""
    print(f"\n" + "="*60)
    print(f"📊 LETZTE {limit} TRANSAKTIONEN")
    print("="*60)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT t.date, a.name, t.amount, t.description, t.source
            FROM transactions t
            JOIN accounts a ON t.account_id = a.id
            ORDER BY t.date DESC, t.created_at DESC
            LIMIT %s
        """, (limit,))
        
        transactions = cursor.fetchall()
        
        if not transactions:
            print("❌ Keine Transaktionen gefunden")
            return
        
        for trans in transactions:
            date, account, amount, desc, source = trans
            amount_str = f"{amount:+.2f} EUR"
            print(f"{date} | {account:20s} | {amount_str:>12s} | {desc[:50]}")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Lesen der Transaktionen: {e}")


def main():
    """Hauptmenü"""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "list":
            list_configured_accounts()
            list_database_accounts()
        elif command == "test":
            account_name = sys.argv[2] if len(sys.argv) > 2 else None
            test_fints_connection(account_name)
        elif command == "sync":
            sync_accounts_to_db()
        elif command == "transactions":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            show_recent_transactions(limit)
        else:
            print(f"❌ Unbekannter Befehl: {command}")
    else:
        # Vollständiger Überblick
        list_configured_accounts()
        list_database_accounts()
        show_recent_transactions()


if __name__ == "__main__":
    main()