#!/usr/bin/env python3
"""
Berechnet transaction_hash für bestehende Zeilen, entfernt echte Duplikate,
legt Unique-Index an (falls noch fehlend).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.utils import get_db_connection, get_db_placeholder, compute_transaction_hash


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--confirm", action="store_true", help="Backfill ausführen")
    args = p.parse_args()
    if not args.confirm:
        print("Bitte --confirm angeben.")
        print("  python scripts/backfill_transaction_hash.py --confirm")
        sys.exit(1)

    ph = get_db_placeholder()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SHOW COLUMNS FROM transactions LIKE 'transaction_hash'")
        if not cursor.fetchone():
            cursor.execute(
                "ALTER TABLE transactions ADD COLUMN transaction_hash VARCHAR(64) NULL "
                "COMMENT 'SHA-256 hex, idempotenter Import'"
            )
            conn.commit()
            print("✅ Spalte transaction_hash angelegt")

        cursor.execute(
            f"SELECT id, account_id, date, amount, description, source FROM transactions "
            f"WHERE transaction_hash IS NULL OR transaction_hash = ''"
        )
        rows = cursor.fetchall()
        for row in rows:
            tid, acc, d, amt, desc, src = row
            h = compute_transaction_hash(acc, d, amt, desc or "", src or "")
            cursor.execute(
                f"UPDATE transactions SET transaction_hash = {ph} WHERE id = {ph}",
                (h, tid),
            )
        conn.commit()
        print(f"✅ {len(rows)} Zeilen mit Hash versehen")

        # Duplikate (gleicher account_id + hash): ältere ID behalten
        cursor.execute(
            """
            DELETE t1 FROM transactions t1
            INNER JOIN transactions t2
              ON t1.account_id = t2.account_id
             AND t1.transaction_hash = t2.transaction_hash
             AND t1.transaction_hash IS NOT NULL
             AND t1.id > t2.id
            """
        )
        deleted = cursor.rowcount
        conn.commit()
        if deleted:
            print(f"✅ {deleted} Duplikat-Zeilen entfernt (jeweils kleinste id behalten)")

        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND table_name = 'transactions' "
            "AND index_name = 'uq_transactions_account_hash'"
        )
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "CREATE UNIQUE INDEX uq_transactions_account_hash "
                "ON transactions (account_id, transaction_hash)"
            )
            conn.commit()
            print("✅ Unique-Index uq_transactions_account_hash angelegt")
        else:
            print("ℹ️ Unique-Index war bereits vorhanden")
    except Exception as e:
        conn.rollback()
        print(f"❌ Fehler: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
