#!/usr/bin/env python3
"""
Datenbank aufräumen: Transaktionen und Dokumente löschen
Verwendung: python scripts/reset_db.py [--confirm]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.utils import db_connection


def reset_transaction_data(confirm: bool = False):
    """Löscht alle Transaktionen und Dokumente (Stammdaten bleiben erhalten)"""
    if not confirm:
        print("❌ Bitte --confirm angeben, um Transaktionen und Dokumente zu löschen.")
        print("   Beispiel: python scripts/reset_db.py --confirm")
        return False

    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM transactions")
            tx_count = cursor.rowcount
            cursor.execute("DELETE FROM documents")
            doc_count = cursor.rowcount
            conn.commit()
        print(f"✅ {tx_count} Transaktion(en) gelöscht")
        print(f"✅ {doc_count} Dokument(e) gelöscht")
        print("   Konten und Kategorien bleiben unverändert.")
        return True
    except Exception as e:
        print(f"❌ Fehler: {e}")
        return False


def main():
    import argparse
    p = argparse.ArgumentParser(description="Datenbank leeren (Transaktionen + Dokumente)")
    p.add_argument("--confirm", action="store_true", help="Bestätigung zum Löschen")
    args = p.parse_args()
    ok = reset_transaction_data(confirm=args.confirm)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
