#!/usr/bin/env python3
"""
Variante A: Kategorien von bereits gelabelten Transaktionen auf unkategorisierte übertragen.

1) Exakter Treffer: gleiche normalisierte Beschreibung (optional pro Konto).
2) Optional Teilstring: Text einer gelabelten Buchung kommt in einer unkategorisierten vor
   (min. Länge, längster Treffer gewinnt) – z. B. „Kapitalertragsteuer“ in längerem Verwendungszweck.

Trockenlauf standardmäßig; --apply schreibt in die DB.

Beispiele:
  docker compose exec app python3 scripts/propagate_categories.py --dry-run
  docker compose exec app python3 scripts/propagate_categories.py --apply
  docker compose exec app python3 scripts/propagate_categories.py --apply --collapse-dates --substring-min-len 10
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.utils import db_connection, get_db_placeholder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def normalize_description(text: str, collapse_dates: bool = False) -> str:
    """
    Einheitlicher Text für Vergleiche: klein, Whitespace, optional Datumsplatzhalter.
    """
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    if collapse_dates:
        t = re.sub(r"\b\d{1,2}\.\d{1,2}\.\d{2,4}\b", "#d#", t)
        t = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "#d#", t)
    return t


def _majority_category(ids: List[int]) -> Tuple[Optional[int], bool]:
    """Mehrheits-category_id; conflict True wenn mehr als eine Kategorie vorkam."""
    if not ids:
        return None, False
    c = Counter(ids)
    best, cnt = c.most_common(1)[0]
    conflict = len(c) > 1
    return best, conflict


def propagate(
    *,
    dry_run: bool,
    per_account: bool,
    collapse_dates: bool,
    substring_min_len: int,
    use_substring: bool,
    show_samples: bool = False,
) -> Tuple[int, int]:
    """
    Returns: (updated_count, candidates_considered)
    """
    ph = get_db_placeholder()

    with db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, account_id, description, category_id
            FROM transactions
            WHERE category_id IS NOT NULL AND description IS NOT NULL AND TRIM(description) <> ''
            """
        )
        labeled = cursor.fetchall()

        cursor.execute(
            """
            SELECT id, account_id, description
            FROM transactions
            WHERE category_id IS NULL AND description IS NOT NULL AND TRIM(description) <> ''
            """
        )
        unlabeled = cursor.fetchall()

    logger.info(
        "Referenz: %s bereits kategorisierte Transaktionen (mit Beschreibung), "
        "%s unkategorisierte mit Text.",
        len(labeled),
        len(unlabeled),
    )
    if not labeled:
        logger.warning(
            "Keine gelabelten Transaktionen – Propagierung hat nichts zum Anwenden. "
            "Zuerst z. B. „categorize.py“ (Regeln) oder manuelle Zuordnung ausführen, "
            "dann propagate_categories erneut starten."
        )
        return 0, len(unlabeled)

    # Referenz: (account_id?, norm) -> category_id (Mehrheit)
    ref_exact: Dict[Tuple[Optional[int], str], List[int]] = {}
    # Für Teilstring: Liste (account_id?, norm, category_id) pro gelabelte Zeile
    ref_rows: List[Tuple[Optional[int], str, int]] = []

    for tid, acc_id, desc, cat_id in labeled:
        norm = normalize_description(desc, collapse_dates=collapse_dates)
        if not norm:
            continue
        key = (acc_id if per_account else None, norm)
        ref_exact.setdefault(key, []).append(cat_id)
        ref_rows.append((acc_id if per_account else None, norm, cat_id))

    if per_account:
        labeled_by_acc = Counter(acc for _t, acc, _d, _c in labeled)
        unlabeled_by_acc = Counter(acc for _t, acc, _d in unlabeled)
        logger.info(
            "Gelabelt pro Konto (account_id → Anzahl): %s | Unkategorisiert pro Konto: %s",
            dict(labeled_by_acc),
            dict(unlabeled_by_acc),
        )
        # Hinweis wenn gelabelte und unkategorisierte kaum überlappen
        labeled_accs = set(labeled_by_acc)
        unlabeled_accs = set(unlabeled_by_acc)
        overlap = labeled_accs & unlabeled_accs
        if unlabeled_accs and labeled_accs and not overlap:
            logger.warning(
                "Gelabelte und unkategorisierte Transaktionen liegen auf verschiedenen Konten – "
                "mit Standard (pro Konto) gibt es keine Treffer. Versuche: --global-scope"
            )

    # Auflösen Mehrheit pro key
    exact_map: Dict[Tuple[Optional[int], str], int] = {}
    for key, cats in ref_exact.items():
        best, conflict = _majority_category(cats)
        if best is None:
            continue
        if conflict:
            logger.warning(
                "Gleiche norm. Beschreibung, unterschiedliche Kategorien (key=%s) → Mehrheit category_id=%s",
                key,
                best,
            )
        exact_map[key] = best

    updates: List[Tuple[int, int, str]] = []  # (transaction_id, category_id, reason)

    for tid, acc_id, desc in unlabeled:
        norm = normalize_description(desc, collapse_dates=collapse_dates)
        if not norm:
            continue

        key = (acc_id if per_account else None, norm)
        if key in exact_map:
            updates.append((tid, exact_map[key], "exact"))
            continue

        if use_substring and substring_min_len > 0:
            acc_filter = acc_id if per_account else None
            # Längster zuerst → eindeutig spezifischster Treffer
            for r_acc, r_norm, r_cat in sorted(
                ref_rows, key=lambda r: -len(r[1])
            ):
                if per_account and r_acc != acc_filter:
                    continue
                if len(r_norm) < substring_min_len:
                    continue
                if r_norm in norm:
                    updates.append(
                        (tid, r_cat, f"substring(len={len(r_norm)})")
                    )
                    break

    if show_samples and (ref_rows or unlabeled):
        # Stichproben: normierte Texte von gelabelt vs. ungelabelt (für Diagnose)
        seen_labeled: OrderedDict[str, None] = OrderedDict()
        for _acc, norm, _cat in ref_rows[:15]:
            seen_labeled[norm[:80] + ("…" if len(norm) > 80 else "")] = None
        seen_unlabeled: OrderedDict[str, None] = OrderedDict()
        for _tid, _acc, desc in unlabeled[:15]:
            n = normalize_description(desc, collapse_dates=collapse_dates)
            seen_unlabeled[(n[:80] + ("…" if len(n) > 80 else ""))] = None
        logger.info("Beispiele norm. Beschreibung (gelabelt): %s", list(seen_labeled.keys())[:5])
        logger.info("Beispiele norm. Beschreibung (unkategorisiert): %s", list(seen_unlabeled.keys())[:5])

    if dry_run:
        for tid, cid, reason in updates[:50]:
            logger.info("[DRY-RUN] id=%s → category_id=%s (%s)", tid, cid, reason)
        if len(updates) > 50:
            logger.info("[DRY-RUN] … und %s weitere", len(updates) - 50)
        logger.info(
            "Zusammenfassung (Dry-Run): %s Zuordnungen möglich, %s unkategorisierte mit Text geprüft",
            len(updates),
            len(unlabeled),
        )
        return len(updates), len(unlabeled)

    applied = 0
    with db_connection() as conn:
        cursor = conn.cursor()
        for tid, cid, _reason in updates:
            cursor.execute(
                f"UPDATE transactions SET category_id = {ph} WHERE id = {ph} AND category_id IS NULL",
                (cid, tid),
            )
            applied += cursor.rowcount
        conn.commit()

    logger.info(
        "Übernommen: %s Zeilen aktualisiert (Kandidaten mit Vorschlag: %s)",
        applied,
        len(updates),
    )
    if applied == 0 and len(unlabeled) > 0 and len(labeled) > 0 and per_account:
        logger.warning(
            "Keine Zuordnung – oft liegen gelabelte und unkategorisierte auf verschiedenen Konten. "
            "Erneut mit --global-scope versuchen."
        )
    return applied, len(unlabeled)


def main() -> None:
    p = argparse.ArgumentParser(
        description="Kategorien von gelabelten auf ungelabelte Transaktionen propagieren (Variante A)"
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="Änderungen in der DB schreiben (ohne nur Dry-Run)",
    )
    p.add_argument(
        "--global-scope",
        action="store_true",
        help="Gleiche Beschreibung über alle Konten zusammenführen (Standard: nur je Konto)",
    )
    p.add_argument(
        "--collapse-dates",
        action="store_true",
        help="Datumsangaben im Text durch Platzhalter ersetzen (ähnliche Kontoauszugszeilen)",
    )
    p.add_argument(
        "--no-substring",
        action="store_true",
        help="Nur exakte Treffer, keinen Teilstring-Vergleich",
    )
    p.add_argument(
        "--substring-min-len",
        type=int,
        default=8,
        metavar="N",
        help="Mindestlänge des gelabelten Texts für Teilstring-Match (Default: 8)",
    )
    p.add_argument("-q", "--quiet", action="store_true", help="Weniger Log-Ausgabe")
    p.add_argument(
        "--show-samples",
        action="store_true",
        help="Stichproben normierter Beschreibungen (gelabelt vs. unkategorisiert) ausgeben",
    )
    args = p.parse_args()

    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    dry_run = not args.apply
    if dry_run:
        logger.info("Modus: Dry-Run (keine DB-Änderung). Zum Schreiben: --apply")

    propagate(
        dry_run=dry_run,
        per_account=not args.global_scope,
        collapse_dates=args.collapse_dates,
        substring_min_len=max(1, args.substring_min_len),
        use_substring=not args.no_substring,
        show_samples=args.show_samples,
    )


if __name__ == "__main__":
    main()
