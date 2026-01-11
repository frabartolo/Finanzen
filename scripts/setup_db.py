#!/usr/bin/env python3
"""
Datenbank initialisieren und mit Grunddaten befüllen
"""
import sys
from pathlib import Path
import yaml

# Pfad zum Projekt-Root hinzufügen
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.utils import get_db_connection, load_config


def init_database():
    """Datenbank-Tabellen erstellen"""
    print("📦 Initialisiere Datenbank...")
    
    # Schema-Datei laden und ausführen
    schema_path = Path(__file__).parent.parent / "db" / "schema.sql"
    
    try:
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.executescript(schema_sql)
        conn.commit()
        conn.close()
        
        print("✅ Datenbank-Schema erstellt")
        return True
    except Exception as e:
        print(f"❌ Fehler beim Erstellen des Schemas: {e}")
        return False


def populate_categories():
    """Kategorien aus config/categories.yaml in Datenbank einfügen"""
    print("📋 Füge Kategorien ein...")
    
    try:
        categories_config = load_config('categories')
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Income-Kategorien
        for category in categories_config.get('categories', {}).get('income', []):
            cursor.execute(
                "INSERT OR IGNORE INTO categories (name, type) VALUES (?, ?)",
                (category, 'income')
            )
        
        # Expense-Kategorien
        for category in categories_config.get('categories', {}).get('expenses', []):
            cursor.execute(
                "INSERT OR IGNORE INTO categories (name, type) VALUES (?, ?)",
                (category, 'expense')
            )
        
        conn.commit()
        conn.close()
        
        print("✅ Kategorien eingefügt")
        return True
    except Exception as e:
        print(f"❌ Fehler beim Einfügen der Kategorien: {e}")
        return False


def populate_accounts():
    """Konten aus config/accounts.yaml in Datenbank einfügen"""
    print("🏦 Füge Konten ein...")
    
    try:
        accounts_config = load_config('accounts')
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for account in accounts_config.get('accounts', []):
            cursor.execute(
                "INSERT OR IGNORE INTO accounts (name, type, bank, iban) VALUES (?, ?, ?, ?)",
                (account['name'], account['type'], account.get('bank', ''), account.get('iban', ''))
            )
        
        conn.commit()
        conn.close()
        
        print("✅ Konten eingefügt")
        return True
    except Exception as e:
        print(f"❌ Fehler beim Einfügen der Konten: {e}")
        return False


def main():
    """Hauptfunktion"""
    print("🚀 Starte Datenbank-Setup...")
    print("-" * 50)
    
    success = True
    success &= init_database()
    success &= populate_categories()
    success &= populate_accounts()
    
    print("-" * 50)
    if success:
        print("✅ Datenbank-Setup erfolgreich abgeschlossen!")
    else:
        print("⚠️ Setup mit Fehlern abgeschlossen. Bitte Logs prüfen.")
        sys.exit(1)


if __name__ == "__main__":
    main()
