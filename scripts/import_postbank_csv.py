#!/usr/bin/env python3
"""
Postbank-CSV-Export (Umsätze, Semikolon, deutsche Zahlen/Datumsformate) parsen
und Transaktionen in die Datenbank schreiben (Quelle: postbank_csv).

Erwartetes Format: Kopf mit „Umsätze“, Kontenzeile mit IBAN, Tabellenkopf
ab „Buchungstag;Wert;Umsatzart;…“.
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.utils import (
    compute_transaction_hash,
    db_connection,
    ensure_dir,
    get_account_by_iban,
    get_db_placeholder,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

MAX_DESCRIPTION_LENGTH = 500

ROOT = Path(__file__).parent.parent
INBOX_DIR = (ROOT / "data" / "inbox").resolve()
PROCESSED_DIR = (ROOT / "data" / "processed").resolve()

IBAN_DE_RE = re.compile(r"\b(DE\d{20})\b")
DATE_CELL_RE = re.compile(r"^\d{1,2}\.\d{1,2}\.\d{4}$")


def parse_de_amount(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_de_date(value: str) -> Optional[date]:
    s = value.strip()
    if not DATE_CELL_RE.match(s):
        return None
    try:
        return datetime.strptime(s, "%d.%m.%Y").date()
    except ValueError:
        return None


def extract_iban_from_row(row: List[str]) -> Optional[str]:
    for cell in row:
        m = IBAN_DE_RE.search(cell.replace(" ", "").upper())
        if m:
            return m.group(1)
    return None


def build_description(row: List[str], hm: Dict[str, int]) -> str:
    parts: List[str] = []
    for key in (
        "Umsatzart",
        "Begünstigter / Auftraggeber",
        "Verwendungszweck",
    ):
        i = hm.get(key)
        if i is None or i >= len(row):
            continue
        v = (row[i] or "").strip()
        if v:
            parts.append(v)
    desc = " | ".join(parts)
    return desc[:MAX_DESCRIPTION_LENGTH]


def row_signed_amount(row: List[str], hm: Dict[str, int]) -> Optional[float]:
    def cell(key: str) -> Optional[str]:
        i = hm.get(key)
        if i is None or i >= len(row):
            return None
        return row[i]

    b = parse_de_amount(cell("Betrag"))
    if b is not None and b != 0.0:
        return b
    h = parse_de_amount(cell("Haben"))
    if h is not None and h != 0.0:
        return h
    s = parse_de_amount(cell("Soll"))
    if s is not None and s != 0.0:
        return s
    return None


def parse_postbank_csv_file(
    path: Path,
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """
    Liefert (iban_aus_kopf_oder_None, liste_von_transaktionen).
    Transaktionen: date, amount, description
    """
    iban: Optional[str] = None
    header_map: Optional[Dict[str, int]] = None
    transactions: List[Dict[str, Any]] = []

    def try_iban(rows: List[str]) -> None:
        nonlocal iban
        if iban:
            return
        found = extract_iban_from_row(rows)
        if found:
            iban = found

    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        text = path.read_text(encoding="cp1252")

    reader = csv.reader(text.splitlines(), delimiter=";")
    for row in reader:
        if not row or all(not (c or "").strip() for c in row):
            continue
        first = (row[0] or "").strip()
        if first == "Umsätze":
            continue
        if header_map is None:
            try_iban(row)
            if (
                len(row) >= 3
                and row[0].strip() == "Buchungstag"
                and row[1].strip() == "Wert"
                and row[2].strip() == "Umsatzart"
            ):
                header_map = {h.strip(): i for i, h in enumerate(row)}
            continue

        if header_map is None:
            continue

        if first in ("Kontostand", "Letzter Kontostand") or first.startswith(
            "Letzter "
        ):
            continue

        bi = header_map.get("Buchungstag")
        if bi is None or bi >= len(row):
            continue
        booking_raw = row[bi].strip()
        trans_date = parse_de_date(booking_raw)
        if trans_date is None:
            continue

        amount = row_signed_amount(row, header_map)
        if amount is None:
            continue

        desc = build_description(row, header_map)
        transactions.append(
            {
                "date": trans_date,
                "amount": amount,
                "description": desc,
            }
        )

    return iban, transactions


def resolve_account_id(
    iban: Optional[str],
    override_id: Optional[int],
) -> Optional[int]:
    if override_id is not None:
        return override_id
    if not iban:
        logger.error("Keine IBAN in der CSV gefunden – bitte --account-id angeben.")
        return None
    row = get_account_by_iban(iban)
    if not row:
        logger.error(
            "Kein Konto mit IBAN %s in der Datenbank. "
            "Konten synchronisieren (z. B. App-Start / manage_accounts) oder --account-id.",
            iban,
        )
        return None
    logger.info("Konto: %s (ID %s)", row[1], row[0])
    return int(row[0])


def save_transactions(
    transactions: List[Dict[str, Any]],
    account_id: int,
) -> int:
    if not transactions:
        return 0
    ph = get_db_placeholder()
    inserted = 0
    with db_connection() as conn:
        cursor = conn.cursor()
        for trans in transactions:
            desc = (trans.get("description") or "")[:MAX_DESCRIPTION_LENGTH]
            tx_hash = compute_transaction_hash(
                account_id,
                trans["date"],
                trans["amount"],
                desc,
                "postbank_csv",
            )
            cursor.execute(
                f"""INSERT IGNORE INTO transactions
                (account_id, date, amount, description, source, transaction_hash)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})""",
                (
                    account_id,
                    trans["date"],
                    trans["amount"],
                    desc,
                    "postbank_csv",
                    tx_hash,
                ),
            )
            if cursor.rowcount > 0:
                inserted += 1
        conn.commit()
    logger.info("%s neue Zeilen importiert (Duplikate übersprungen)", inserted)
    return inserted


def move_with_structure(source: Path, inbox_dir: Path, processed_dir: Path) -> None:
    src = source.resolve()
    inbox = inbox_dir.resolve()
    proc = processed_dir.resolve()
    if not src.exists():
        raise FileNotFoundError(source)
    relative_path = src.relative_to(inbox)
    target = proc / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(target))


def find_all_csv(directory: Path) -> List[Path]:
    return sorted(p for p in directory.rglob("*.csv") if p.is_file())


def process_one_csv(
    path: Path,
    account_id_override: Optional[int],
    *,
    dry_run: bool,
    do_move: bool,
) -> bool:
    iban, transactions = parse_postbank_csv_file(path)
    if not transactions:
        logger.warning("Keine Buchungszeilen in %s (kein Postbank-Format?)", path.name)
        return False

    account_id = resolve_account_id(iban, account_id_override)
    if account_id is None:
        return False

    logger.info(
        "%s: IBAN aus Datei=%s, %s Transaktion(en)",
        path.name,
        iban or "?",
        len(transactions),
    )
    if dry_run:
        for t in transactions[:5]:
            logger.info("  Dry-run: %s  %s  %s", t["date"], t["amount"], t["description"][:60])
        if len(transactions) > 5:
            logger.info("  … und %s weitere", len(transactions) - 5)
        return True

    save_transactions(transactions, account_id)
    if do_move:
        move_with_structure(path, INBOX_DIR, PROCESSED_DIR)
        logger.info("Verschoben nach processed/: %s", path.name)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Postbank-Umsätze-CSV importieren")
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="CSV-Dateien (Default: alle data/inbox/**/*.csv)",
    )
    parser.add_argument(
        "--account-id",
        type=int,
        default=None,
        help="Konto-ID in der DB, falls IBAN-Zuordnung nicht gewünscht/fehlend",
    )
    parser.add_argument(
        "--no-move",
        action="store_true",
        help="Datei nach Import nicht nach data/processed verschieben",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur parsen und loggen, keine DB-Schreibzugriffe",
    )
    args = parser.parse_args()

    ensure_dir(INBOX_DIR)
    ensure_dir(PROCESSED_DIR)

    if args.files:
        paths = [p.resolve() for p in args.files]
    else:
        paths = find_all_csv(INBOX_DIR)
        if not paths:
            logger.info("Keine CSV-Dateien in %s", INBOX_DIR)
            return

    ok = 0
    for p in paths:
        if not p.exists():
            logger.error("Datei fehlt: %s", p)
            continue
        try:
            if process_one_csv(
                p,
                args.account_id,
                dry_run=args.dry_run,
                do_move=not args.no_move,
            ):
                ok += 1
        except Exception as e:
            logger.error("Fehler bei %s: %s", p, e)

    logger.info("Fertig: %s/%s Datei(en) verarbeitet", ok, len(paths))


if __name__ == "__main__":
    main()
