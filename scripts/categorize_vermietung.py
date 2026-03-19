#!/usr/bin/env python3
"""
Nachkategorisierung: Transaktionen den Kategorien „Vermietung und Verpachtung“ zuordnen.
Nutzt config/vermietung_rules.yaml. Eignet sich für einmalige Anpassung und Analyse.

Wird im App-Container ausgeführt (Datenbank + mysql.connector):
  docker compose exec app python3 scripts/categorize_vermietung.py --dry-run
  docker compose exec app python3 scripts/categorize_vermietung.py
  docker compose exec app python3 scripts/categorize_vermietung.py --force
"""

import sys
import re
import argparse
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.utils import db_connection, get_db_placeholder


def load_vermietung_rules():
    """Lädt Regeln aus config/vermietung_rules.yaml."""
    path = Path(__file__).parent.parent / "config" / "vermietung_rules.yaml"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("rules", [])


def get_category_ids(conn):
    """Mapping Kategoriename -> id."""
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM categories")
    return {name: id_ for id_, name in cur.fetchall()}


def run(dry_run=False, force=False, verbose=False):
    rules = load_vermietung_rules()
    if not rules:
        print("Keine Regeln in config/vermietung_rules.yaml gefunden.")
        return 0, 0

    try:
        with db_connection() as conn:
            ph = get_db_placeholder()
            cat_ids = get_category_ids(conn)

            rule_cats = {r.get("category") for r in rules if r.get("category")}
            missing = rule_cats - set(cat_ids.keys())
            if missing:
                print(
                    "Hinweis: Diese Kategorien aus den Regeln fehlen in der DB "
                    "(evtl. setup_db.py ausführen):"
                )
                for c in sorted(missing):
                    print(f"  - {c}")
            if verbose:
                print(
                    "In DB vorhandene Vermietungs-Kategorien:",
                    [
                        c
                        for c in sorted(cat_ids.keys())
                        if "miete" in c.lower()
                        or "vermietung" in c.lower()
                        or "pacht" in c.lower()
                    ],
                )

            cursor = conn.cursor()
            if force:
                cursor.execute("SELECT id, description, amount FROM transactions")
            else:
                cursor.execute(
                    "SELECT id, description, amount FROM transactions WHERE category_id IS NULL"
                )
            rows = cursor.fetchall()
            updated = 0

            if verbose and rows:
                print("Beispiel-Buchungstexte (erste 5):")
                for tid, description, amount in rows[:5]:
                    desc = (description or "").strip()[:60]
                    print(f"  id={tid} amount={amount} | {desc!r}")

            for tid, description, amount in rows:
                description = (description or "").strip()
                amount = float(amount or 0)
                for rule in rules:
                    pattern = rule.get("description_pattern")
                    cat_name = rule.get("category")
                    if not pattern or not cat_name or cat_name not in cat_ids:
                        continue
                    amount_min = rule.get("amount_min")
                    amount_max = rule.get("amount_max")
                    if amount_min is not None and amount < amount_min:
                        continue
                    if amount_max is not None and amount > amount_max:
                        continue
                    if re.search(pattern, description):
                        if not dry_run:
                            cursor.execute(
                                f"UPDATE transactions SET category_id = {ph} WHERE id = {ph}",
                                (cat_ids[cat_name], tid),
                            )
                        updated += 1
                        print(f"  [{tid}] {description[:50]}... → {cat_name}")
                        break

            if not dry_run and updated:
                conn.commit()
            return updated, len(rows)
    except ModuleNotFoundError as e:
        if "mysql" in str(e).lower():
            print("Hinweis: mysql.connector fehlt. Skript im App-Container ausführen:")
            print(
                "  docker compose exec app python3 scripts/categorize_vermietung.py [--dry-run] [--force]"
            )
            sys.exit(1)
        raise


def main():
    p = argparse.ArgumentParser(description="Vermietung/Verpachtung nachkategorisieren")
    p.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts ändern")
    p.add_argument("--force", action="store_true", help="Auch bereits kategorisierte prüfen")
    p.add_argument("-v", "--verbose", action="store_true", help="Hinweise + Beispiel-Buchungstexte anzeigen")
    args = p.parse_args()

    print("Vermietung/Verpachtung – Nachkategorisierung")
    if args.dry_run:
        print("(Dry-Run – keine Änderungen)")
    updated, total = run(dry_run=args.dry_run, force=args.force, verbose=args.verbose)
    print(f"Zugeordnet: {updated} von {total} Transaktionen.")


if __name__ == "__main__":
    main()
