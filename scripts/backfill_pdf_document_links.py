#!/usr/bin/env python3
"""
Verknüpft bestehende PDF-Buchungen (source=pdf) nachträglich mit PDF-Dateien.

Geht alle PDFs unter data/processed/ (optional data/inbox/) durch, legt/aktualisiert
documents-Einträge und setzt transactions.document_id per transaction_hash.

Kein DB-Leeren nötig. Bereits gesetzte document_id werden nur bei --force überschrieben.

Beispiele:
  docker compose exec app python3 scripts/backfill_pdf_document_links.py --dry-run
  docker compose exec app python3 scripts/backfill_pdf_document_links.py --confirm
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.parse_pdfs import (
    PDF_DIR,
    PROCESSED_DIR,
    MAX_DESCRIPTION_LENGTH,
    extract_metadata_from_path,
    get_account_id_by_bank,
    parse_pdf,
)
from scripts.pdf_documents import file_sha256, path_to_relative, upsert_pdf_document
from scripts.utils import compute_transaction_hash, db_connection, get_db_placeholder


def find_pdfs(*roots: Path) -> List[Path]:
    seen = set()
    out: List[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*.pdf")):
            if p.is_file():
                key = p.resolve()
                if key not in seen:
                    seen.add(key)
                    out.append(p)
    return out


def link_pdf(
    pdf_path: Path,
    *,
    dry_run: bool,
    force: bool,
) -> Tuple[int, int, int]:
    """
    Returns: (matched_updates, already_linked, parse_errors)
    """
    inbox = PDF_DIR.resolve()
    metadata = None
    try:
        if pdf_path.resolve().is_relative_to(inbox):
            metadata = extract_metadata_from_path(pdf_path, inbox)
    except ValueError:
        pass

    data = parse_pdf(pdf_path, metadata, for_link_backfill=True)
    if not data:
        return 0, 0, 1

    transactions = data.get("transactions") or []
    if not transactions:
        return 0, 0, 0

    account_id = get_account_id_by_bank(data.get("bank")) if data.get("bank") else 1
    rel = path_to_relative(pdf_path)
    try:
        fhash = file_sha256(pdf_path)
    except OSError:
        fhash = None

    matched = 0
    already = 0

    ph = get_db_placeholder()
    with db_connection() as conn:
        cursor = conn.cursor()
        if dry_run:
            doc_id = -1
        else:
            # Nur Metadaten + Verknüpfung – kein Volltext (vermeidet TEXT-Limit / Absturz)
            doc_id = upsert_pdf_document(
                cursor,
                ph,
                relative_path=rel,
                file_name=pdf_path.name,
                account_id=account_id,
                raw_text=None,
                file_hash=fhash,
            )

        for trans in transactions:
            desc = (trans.get("description") or "")[:MAX_DESCRIPTION_LENGTH]
            tx_hash = compute_transaction_hash(
                account_id, trans["date"], trans["amount"], desc, "pdf"
            )
            if dry_run:
                cursor.execute(
                    f"""SELECT id, document_id FROM transactions
                    WHERE account_id = {ph} AND transaction_hash = {ph} AND source = 'pdf'""",
                    (account_id, tx_hash),
                )
                row = cursor.fetchone()
                if row:
                    if row[1] is None:
                        matched += 1
                    elif row[1] == doc_id or force:
                        already += 1
                continue

            if force:
                cursor.execute(
                    f"""UPDATE transactions SET document_id = {ph}
                    WHERE account_id = {ph} AND transaction_hash = {ph} AND source = 'pdf'""",
                    (doc_id, account_id, tx_hash),
                )
            else:
                cursor.execute(
                    f"""UPDATE transactions SET document_id = {ph}
                    WHERE account_id = {ph} AND transaction_hash = {ph}
                      AND source = 'pdf' AND document_id IS NULL""",
                    (doc_id, account_id, tx_hash),
                )
            if cursor.rowcount > 0:
                matched += 1
            else:
                cursor.execute(
                    f"""SELECT document_id FROM transactions
                    WHERE account_id = {ph} AND transaction_hash = {ph} AND source = 'pdf'""",
                    (account_id, tx_hash),
                )
                row = cursor.fetchone()
                if row and row[0] is not None:
                    already += 1

        if not dry_run:
            conn.commit()

    return matched, already, 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PDF-Dateien mit bestehenden PDF-Transaktionen verknüpfen"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Änderungen in der DB schreiben (ohne nur Vorschau)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur zählen, nichts schreiben (implizit ohne --confirm)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bereits gesetzte document_id überschreiben",
    )
    parser.add_argument(
        "--include-inbox",
        action="store_true",
        help="Auch data/inbox/ berücksichtigen",
    )
    args = parser.parse_args()

    dry_run = args.dry_run or not args.confirm
    if not args.confirm and not args.dry_run:
        print("Bitte --dry-run (Vorschau) oder --confirm (ausführen) angeben.")
        sys.exit(1)

    roots = [PROCESSED_DIR]
    if args.include_inbox:
        roots.insert(0, PDF_DIR)

    pdfs = find_pdfs(*roots)
    if not pdfs:
        print("Keine PDFs gefunden unter processed/ (ggf. --include-inbox).")
        sys.exit(0)

    print(f"{'[DRY-RUN] ' if dry_run else ''}{len(pdfs)} PDF(s) …")
    total_match = 0
    total_already = 0
    total_err = 0

    for pdf in pdfs:
        m, a, e = link_pdf(pdf, dry_run=dry_run, force=args.force)
        total_match += m
        total_already += a
        total_err += e
        if m or e:
            print(f"  {pdf.name}: +{m} verknüpft, {a} schon verknüpft" + (" [Parse-Fehler]" if e else ""))

    print(
        f"\nFertig: {total_match} Buchungen verknüpft, "
        f"{total_already} bereits mit PDF, {total_err} Parse-Fehler."
    )
    if dry_run:
        print("Zum Schreiben: --confirm")


if __name__ == "__main__":
    main()
