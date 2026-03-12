#!/usr/bin/env python3
"""
Repariert die korrupte documents-Tabelle (DROP + CREATE).
Läuft mit: python scripts/repair_documents_table.py [--confirm]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.utils import get_db_connection


def repair():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DROP TABLE IF EXISTS documents")
        cursor.execute("""
            CREATE TABLE documents (
                id INT AUTO_INCREMENT PRIMARY KEY,
                raw_text TEXT,
                amount DECIMAL(15,2),
                category VARCHAR(255),
                INDEX idx_documents_category (category)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        conn.commit()
        print("✅ Tabelle documents repariert (neu erstellt)")
        return True
    except Exception as e:
        conn.rollback()
        print(f"❌ Fehler: {e}")
        return False
    finally:
        conn.close()


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--confirm", action="store_true", help="Reparatur bestätigen")
    args = p.parse_args()
    if not args.confirm:
        print("Bitte --confirm angeben, um die documents-Tabelle neu zu erstellen.")
        print("  python scripts/repair_documents_table.py --confirm")
        sys.exit(1)
    ok = repair()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
