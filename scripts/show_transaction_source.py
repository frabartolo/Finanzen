#!/usr/bin/env python3
"""Zeigt Quelle einer Buchung (PDF-Pfad, Importquelle)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.utils import db_connection, get_db_placeholder


def main() -> None:
    p = argparse.ArgumentParser(description="Buchung und zugehöriges PDF anzeigen")
    p.add_argument("transaction_id", type=int, nargs="?", help="transactions.id")
    p.add_argument("--last", type=int, default=0, help="Letzte N PDF-Buchungen ohne Filter")
    args = p.parse_args()

    ph = get_db_placeholder()
    with db_connection() as conn:
        cur = conn.cursor()
        if args.transaction_id:
            cur.execute(
                f"""
                SELECT t.id, t.date, t.amount, t.description, t.source,
                       d.id, d.source_path, d.file_name
                FROM transactions t
                LEFT JOIN documents d ON t.document_id = d.id
                WHERE t.id = {ph}
                """,
                (args.transaction_id,),
            )
            rows = cur.fetchall()
        elif args.last > 0:
            cur.execute(
                f"""
                SELECT t.id, t.date, t.amount, LEFT(t.description, 80), t.source,
                       d.id, d.source_path, d.file_name
                FROM transactions t
                LEFT JOIN documents d ON t.document_id = d.id
                WHERE t.document_id IS NOT NULL
                ORDER BY t.id DESC
                LIMIT {ph}
                """,
                (args.last,),
            )
            rows = cur.fetchall()
        else:
            p.print_help()
            sys.exit(1)

    if not rows:
        print("Keine Treffer.")
        return

    for row in rows:
        tid, dt, amt, desc, src, did, spath, fname = row
        print(f"\nBuchung #{tid}  {dt}  {amt:.2f}  [{src}]")
        print(f"  {desc}")
        if did:
            print(f"  PDF (documents.id={did}): {spath or fname}")
        else:
            print("  Kein PDF verknüpft (z. B. FinTS/CSV)")


if __name__ == "__main__":
    main()
