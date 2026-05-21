#!/usr/bin/env python3
"""
Repariert die korrupte documents-Tabelle (DROP + CREATE).
Läuft mit: python scripts/repair_documents_table.py [--confirm]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.utils import db_connection


def repair():
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE transactions SET document_id = NULL WHERE document_id IS NOT NULL"
            )
            try:
                cursor.execute(
                    "ALTER TABLE transactions DROP FOREIGN KEY fk_transactions_document"
                )
            except Exception:
                pass
            cursor.execute("DROP TABLE IF EXISTS documents")
            cursor.execute("""
                CREATE TABLE documents (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    source_path VARCHAR(512) NULL,
                    file_name VARCHAR(255) NULL,
                    file_sha256 CHAR(64) NULL,
                    account_id INT NULL,
                    raw_text MEDIUMTEXT,
                    amount DECIMAL(15,2) NULL,
                    category VARCHAR(255) NULL,
                    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_documents_source_path (source_path),
                    INDEX idx_documents_account (account_id),
                    INDEX idx_documents_sha256 (file_sha256),
                    INDEX idx_documents_category (category)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            conn.commit()
        print("✅ Tabelle documents repariert (neu erstellt)")
        return True
    except Exception as e:
        print(f"❌ Fehler: {e}")
        return False


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
