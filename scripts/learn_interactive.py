#!/usr/bin/env python3
"""
Interaktiver Lernmodus: PDF-Erkennung prüfen/korrigieren und Kategorien zuordnen.

PDF: Buchungen aus einer PDF anzeigen, korrigieren, in die DB schreiben.
Kategorie: Unkategorisierte Transaktionen durchgehen, Kategorie setzen, optional Regel lernen.

TTY erforderlich:
  docker compose exec -it app python3 scripts/learn_interactive.py pdf data/inbox/konto.pdf
  docker compose exec -it app python3 scripts/learn_interactive.py category --limit 30
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.categorization_rules import match_category_name, load_all_rules
from scripts.categorize import Categorizer
from scripts.learned_rules import (
    LEARNED_RULES_PATH,
    append_learned_rule,
    suggest_pattern_from_description,
)
from scripts.parse_pdfs import (
    PDF_DIR,
    PROCESSED_DIR,
    extract_metadata_from_path,
    extract_pdf_text,
    move_with_structure,
    parse_pdf,
    store,
)
from scripts.utils import db_connection, get_db_placeholder


def _require_tty() -> None:
    if not sys.stdin.isatty():
        print(
            "Interaktiver Modus braucht eine TTY.\n"
            "Beispiel: docker compose exec -it app python3 scripts/learn_interactive.py category"
        )
        sys.exit(1)


def _prompt(msg: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    line = input(f"{msg}{suffix}: ").strip()
    return line if line else default


def _parse_de_date(s: str) -> Optional[date]:
    s = s.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_amount(s: str) -> Optional[float]:
    s = s.strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _print_tx_table(transactions: List[Dict[str, Any]]) -> None:
    if not transactions:
        print("  (keine Transaktionen)")
        return
    for i, t in enumerate(transactions, 1):
        d = t["date"]
        dstr = d.isoformat() if hasattr(d, "isoformat") else str(d)
        print(f"  {i:3d}. {dstr}  {t['amount']:>10.2f}  {t.get('description', '')[:70]}")


def _pdf_help() -> None:
    print(
        """
Befehle (PDF-Modus):
  l, list     Transaktionen anzeigen
  t, text     Rohtext-Auszug (pdftotext/pdfplumber)
  e N         Buchung N bearbeiten (Datum, Betrag, Beschreibung)
  d N         Buchung N entfernen
  a, add      Buchung manuell hinzufügen
  s, save     In Datenbank speichern (INSERT, Duplikate ignoriert)
  m, move     Nach save: PDF von inbox nach processed verschieben
  h, help     Diese Hilfe
  q, quit     Beenden ohne Speichern
"""
    )


def run_pdf_mode(pdf_path: Path, *, move_after_save: bool) -> None:
    if not pdf_path.is_file():
        print(f"Datei nicht gefunden: {pdf_path}")
        sys.exit(1)

    inbox = PDF_DIR
    metadata = None
    if pdf_path.resolve().is_relative_to(inbox.resolve()):
        metadata = extract_metadata_from_path(pdf_path, inbox)

    print(f"\n=== PDF-Lernmodus: {pdf_path.name} ===\n")
    data = parse_pdf(pdf_path, metadata)
    raw_text = ""
    extract_method = "none"
    if not data:
        print("Parser lieferte keine Daten – versuche nur Text-Extraktion.")
        raw_text, extract_method = extract_pdf_text(pdf_path)
        data = {
            "raw_text": raw_text,
            "transactions": [],
            "metadata": metadata,
            "bank": None,
        }
    else:
        raw_text = data.get("raw_text") or ""

    transactions: List[Dict[str, Any]] = list(data.get("transactions") or [])
    bank = data.get("bank")
    if bank:
        print(f"Erkannte Bank: {bank}")
    print(f"Erkannte Buchungen: {len(transactions)}")
    _print_tx_table(transactions)
    _pdf_help()

    do_move = move_after_save
    saved = False

    while True:
        cmd = _prompt("\nBefehl").lower().split()
        if not cmd:
            continue
        op = cmd[0]

        if op in ("q", "quit", "exit"):
            if saved and do_move and pdf_path.exists():
                try:
                    if pdf_path.resolve().is_relative_to(inbox.resolve()):
                        move_with_structure(pdf_path, inbox, PROCESSED_DIR)
                        print(f"Verschoben nach processed/: {pdf_path.name}")
                except Exception as e:
                    print(f"Verschieben fehlgeschlagen: {e}")
            print("Beendet.")
            break

        if op in ("h", "help", "?"):
            _pdf_help()
            continue

        if op in ("l", "list"):
            _print_tx_table(transactions)
            continue

        if op in ("t", "text"):
            excerpt = (raw_text or data.get("raw_text") or "")[:4000]
            print("\n--- Textauszug ---\n")
            print(excerpt or "(leer)")
            print("--- Ende ---\n")
            continue

        if op in ("d", "del", "delete") and len(cmd) >= 2:
            try:
                idx = int(cmd[1]) - 1
                if 0 <= idx < len(transactions):
                    removed = transactions.pop(idx)
                    print(f"Entfernt: {removed.get('description', '')[:50]}")
                else:
                    print("Ungültige Nummer.")
            except ValueError:
                print("Syntax: d N")
            continue

        if op in ("e", "edit") and len(cmd) >= 2:
            try:
                idx = int(cmd[1]) - 1
                if not (0 <= idx < len(transactions)):
                    print("Ungültige Nummer.")
                    continue
                t = transactions[idx]
                dstr = _prompt("Datum DD.MM.YYYY", t["date"].strftime("%d.%m.%Y") if hasattr(t["date"], "strftime") else str(t["date"]))
                new_d = _parse_de_date(dstr)
                if new_d:
                    t["date"] = new_d
                astr = _prompt("Betrag", str(t["amount"]))
                new_a = _parse_amount(astr)
                if new_a is not None:
                    t["amount"] = new_a
                t["description"] = _prompt("Beschreibung", t.get("description", ""))[:500]
                print("Aktualisiert:")
                _print_tx_table([t])
            except ValueError:
                print("Syntax: e N")
            continue

        if op in ("a", "add"):
            dstr = _prompt("Datum DD.MM.YYYY")
            new_d = _parse_de_date(dstr)
            if not new_d:
                print("Ungültiges Datum.")
                continue
            astr = _prompt("Betrag")
            new_a = _parse_amount(astr)
            if new_a is None:
                print("Ungültiger Betrag.")
                continue
            desc = _prompt("Beschreibung")[:500]
            transactions.append({"date": new_d, "amount": new_a, "description": desc})
            print("Hinzugefügt.")
            continue

        if op in ("m", "move"):
            do_move = True
            print("Nach dem nächsten save wird die PDF nach processed/ verschoben (falls unter inbox/).")
            continue

        if op in ("s", "save"):
            if not transactions:
                print("Keine Buchungen zum Speichern.")
                continue
            payload = {
                "raw_text": raw_text or data.get("raw_text", ""),
                "transactions": transactions,
                "metadata": metadata,
                "bank": bank,
                "pdf_path": pdf_path,
            }
            ok, doc_id = store(payload)
            if ok:
                saved = True
                print(
                    f"In Datenbank gespeichert (Duplikate übersprungen). "
                    f"Dokument-ID: {doc_id or '—'}"
                )
                print("Tipp: danach  category  für Kategorien, oder  categorize.py")
            else:
                print("Speichern fehlgeschlagen – Logs prüfen.")
            continue

        print("Unbekannter Befehl. h = Hilfe")


def _load_category_names() -> List[str]:
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM categories ORDER BY name")
        return [row[0] for row in cur.fetchall()]


def _resolve_category_id(name: str, categorizer: Categorizer) -> Optional[int]:
    key = name.strip().lower()
    if key in categorizer.category_cache:
        return categorizer.category_cache[key]
    # Nummer aus Liste?
    return None


def run_category_mode(*, limit: int, account_id: Optional[int]) -> None:
    rules = load_all_rules()
    categorizer = Categorizer()
    names = _load_category_names()
    if not names:
        print("Keine Kategorien in der DB. Zuerst setup_db.py --categories-only ausführen.")
        sys.exit(1)

    ph = get_db_placeholder()
    query = """
        SELECT t.id, t.date, t.amount, t.description, t.account_id
        FROM transactions t
        WHERE t.category_id IS NULL
    """
    params: List[Any] = []
    if account_id is not None:
        query += f" AND t.account_id = {ph}"
        params.append(account_id)
    query += " ORDER BY t.date DESC, t.id DESC LIMIT %s"
    params.append(limit)

    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, tuple(params))
        rows = cur.fetchall()

    if not rows:
        print("Keine unkategorisierten Transaktionen in diesem Ausschnitt.")
        return

    print(f"\n=== Kategorie-Lernmodus ({len(rows)} Buchungen) ===")
    print(f"Gelernte Regeln: {LEARNED_RULES_PATH}")
    print("Eingabe: Kategoriename oder Nummer aus Liste | s=überspringen | q=beenden\n")

    for n, (tid, tdate, amount, description, acc_id) in enumerate(rows, 1):
        desc = description or ""
        suggestion = match_category_name(desc, rules)
        if suggestion:
            print(f"\n[{n}/{len(rows)}] Vorschlag (Regel): {suggestion}")
        print(f"  ID {tid} | {tdate} | {amount:>10.2f} | Konto {acc_id}")
        print(f"  {desc[:120]}")

        while True:
            choice = _prompt("Kategorie (Nr/Name), s=skip, q=quit, ?=Liste").strip()
            if choice.lower() in ("q", "quit"):
                print("Beendet.")
                return
            if choice.lower() in ("s", "skip", ""):
                break
            if choice == "?":
                for i, nm in enumerate(names, 1):
                    print(f"  {i:3d}. {nm}")
                continue

            cat_name: Optional[str] = None
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(names):
                    cat_name = names[idx]
            else:
                cat_name = choice

            if not cat_name:
                print("Unbekannte Eingabe.")
                continue

            cat_id = _resolve_category_id(cat_name, categorizer)
            if cat_id is None:
                print(f"Kategorie '{cat_name}' nicht in der DB.")
                continue

            with db_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    f"UPDATE transactions SET category_id = {ph} WHERE id = {ph}",
                    (cat_id, tid),
                )
                conn.commit()
            print(f"  → gespeichert: {cat_name}")

            learn = _prompt("Regel für künftige Buchungen lernen? (j/n)", "j").lower()
            if learn in ("j", "ja", "y", "yes"):
                default_pat = suggest_pattern_from_description(desc)
                pat = _prompt("Regex-Muster", default_pat)
                pri = _prompt("Priorität", "76")
                try:
                    priority = int(pri)
                except ValueError:
                    priority = 76
                if append_learned_rule(cat_name, pat, priority=priority, note=f"learn_interactive tx#{tid}"):
                    print(f"  → Regel in {LEARNED_RULES_PATH.name} gespeichert")
                    rules = load_all_rules()
                    categorizer._load_rules()
                else:
                    print("  → Regel existiert bereits (unverändert)")
            break

    print("\nFertig. Optional: python3 scripts/categorize.py  für Rest mit Regeln.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Interaktiver Lernmodus (PDF + Kategorien)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_pdf = sub.add_parser("pdf", help="PDF parsen, Buchungen prüfen/korrigieren, speichern")
    p_pdf.add_argument("path", type=Path, help="Pfad zur PDF")
    p_pdf.add_argument(
        "--move",
        action="store_true",
        help="Nach save: PDF von data/inbox nach data/processed verschieben",
    )

    p_cat = sub.add_parser("category", help="Unkategorisierte Buchungen zuordnen + Regeln lernen")
    p_cat.add_argument("--limit", type=int, default=25, help="Max. Anzahl Buchungen (Default: 25)")
    p_cat.add_argument("--account-id", type=int, default=None, help="Nur dieses Konto")

    args = parser.parse_args()
    _require_tty()

    if args.command == "pdf":
        run_pdf_mode(args.path.resolve(), move_after_save=args.move)
    elif args.command == "category":
        run_category_mode(limit=max(1, args.limit), account_id=args.account_id)


if __name__ == "__main__":
    main()
