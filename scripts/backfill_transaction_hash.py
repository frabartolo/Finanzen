#!/usr/bin/env python3
"""
Berechnet transaction_hash für alle Zeilen (quellenunabhängig), entfernt echte Duplikate,
legt Unique-Index an (falls noch fehlend).

Nach Umstellung der Hash-Formel (ohne Importquelle) einmal mit --confirm ausführen,
damit bestehende Einträge konsistent sind und CSV/FinTS/PDF nicht doppelt landen.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.utils import db_connection, get_db_placeholder, compute_transaction_hash


INDEX_NAME = "uq_transactions_account_hash"


def _index_exists(cursor) -> bool:
    cursor.execute(
        f"""
        SELECT COUNT(*) FROM information_schema.statistics
        WHERE table_schema = DATABASE() AND table_name = 'transactions'
        AND index_name = {get_db_placeholder()}
        """,
        (INDEX_NAME,),
    )
    return cursor.fetchone()[0] > 0


def main():
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument(
        "--confirm",
        action="store_true",
        help="Backfill ausführen (Hashes neu berechnen, Duplikate löschen)",
    )
    args = p.parse_args()
    if not args.confirm:
        print("Bitte --confirm angeben.")
        print("  python scripts/backfill_transaction_hash.py --confirm")
        sys.exit(1)

    ph = get_db_placeholder()
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SHOW COLUMNS FROM transactions LIKE 'transaction_hash'")
            if not cursor.fetchone():
                cursor.execute(
                    "ALTER TABLE transactions ADD COLUMN transaction_hash VARCHAR(64) NULL "
                    "COMMENT 'SHA-256 hex, idempotenter Import'"
                )
                conn.commit()
                print("✅ Spalte transaction_hash angelegt")

            if _index_exists(cursor):
                cursor.execute(
                    f"ALTER TABLE transactions DROP INDEX {INDEX_NAME}"
                )
                conn.commit()
                print(f"✅ Unique-Index {INDEX_NAME} vorübergehend entfernt (Hash-Update)")

            cursor.execute(
                f"SELECT id, account_id, date, amount, description FROM transactions"
            )
            rows = cursor.fetchall()
            for row in rows:
                tid, acc, d, amt, desc = row
                h = compute_transaction_hash(acc, d, amt, desc or "")
                cursor.execute(
                    f"UPDATE transactions SET transaction_hash = {ph} WHERE id = {ph}",
                    (h, tid),
                )
            conn.commit()
            print(f"✅ {len(rows)} Zeilen mit Hash versehen (quellenunabhängig)")

            cursor.execute(
                """
                DELETE t1 FROM transactions t1
                INNER JOIN transactions t2
                  ON t1.account_id = t2.account_id
                 AND t1.transaction_hash = t2.transaction_hash
                 AND t1.transaction_hash IS NOT NULL
                 AND t1.transaction_hash != ''
                 AND t1.id > t2.id
                """
            )
            deleted = cursor.rowcount
            conn.commit()
            if deleted:
                print(
                    f"✅ {deleted} Duplikat-Zeilen entfernt (jeweils kleinste id behalten)"
                )

            if not _index_exists(cursor):
                cursor.execute(
                    f"CREATE UNIQUE INDEX {INDEX_NAME} "
                    f"ON transactions (account_id, transaction_hash)"
                )
                conn.commit()
                print(f"✅ Unique-Index {INDEX_NAME} angelegt")
    except Exception as e:
        print(f"❌ Fehler: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
