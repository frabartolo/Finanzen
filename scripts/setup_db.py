#!/usr/bin/env python3
"""
Datenbank initialisieren und mit Grunddaten befüllen
"""
import sys
from pathlib import Path
import yaml

# Pfad zum Projekt-Root hinzufügen
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.utils import get_db_connection, load_config, get_db_placeholder


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


def update_schema_for_hierarchy():
    """Schema für Unterkategorien erweitern"""
    print("🔄 Prüfe Schema auf Hierarchie-Support...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Prüfen ob parent_id Spalte existiert
        cursor.execute("SHOW COLUMNS FROM categories LIKE 'parent_id'")
        if not cursor.fetchone():
            print("   Füge parent_id Spalte hinzu...")
            cursor.execute("ALTER TABLE categories ADD COLUMN parent_id INT NULL")
            cursor.execute("ALTER TABLE categories ADD CONSTRAINT fk_category_parent FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE SET NULL")
            conn.commit()
            print("✅ Schema erfolgreich erweitert")
        else:
            print("✅ Schema unterstützt bereits Hierarchien")
            
    except Exception as e:
        print(f"⚠️ Fehler beim Schema-Update: {e}")
    finally:
        conn.close()
        return True


def insert_category_tree(cursor, items, cat_type, parent_id=None):
    """Rekursives Einfügen von Kategorien und Unterkategorien"""
    ph = get_db_placeholder()
    
    for item in items:
        name = None
        subcategories = []
        
        # Unterscheidung: Einfacher String oder Objekt mit Unterkategorien
        if isinstance(item, str):
            name = item
        elif isinstance(item, dict):
            name = item.get('name')
            subcategories = item.get('children', item.get('subcategories', []))
        
        if not name:
            continue
            
        # Prüfen ob Kategorie existiert
        cursor.execute(f"SELECT id FROM categories WHERE name = {ph} AND type = {ph}", (name, cat_type))
        result = cursor.fetchone()
        
        current_id = None
        if result:
            current_id = result[0]
            # Parent setzen falls noch nicht vorhanden
            if parent_id is not None:
                cursor.execute(f"UPDATE categories SET parent_id = {ph} WHERE id = {ph} AND parent_id IS NULL", (parent_id, current_id))
        else:
            # Neu anlegen
            cursor.execute(
                f"INSERT INTO categories (name, type, parent_id) VALUES ({ph}, {ph}, {ph})", 
                (name, cat_type, parent_id)
            )
            current_id = cursor.lastrowid
        
        # Rekursion für Unterkategorien
        if subcategories and current_id:
            insert_category_tree(cursor, subcategories, cat_type, current_id)


def populate_categories():
    """Kategorien aus config/categories.yaml in Datenbank einfügen"""
    print("📋 Füge Kategorien ein...")
    
    try:
        categories_config = load_config('categories')
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Income-Kategorien
        income_cats = categories_config.get('categories', {}).get('income', [])
        insert_category_tree(cursor, income_cats, 'income')
        
        # Expense-Kategorien
        expense_cats = categories_config.get('categories', {}).get('expenses', [])
        insert_category_tree(cursor, expense_cats, 'expense')
        
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
    success &= update_schema_for_hierarchy()
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
