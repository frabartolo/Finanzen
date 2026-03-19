#!/usr/bin/env python3
"""
Variante B: Regel-Vorschläge aus bereits kategorisierten Transaktionen (DB).

Zwei Heuristiken (nur Vorschläge – manuell in categorization_rules.yaml prüfen/einfügen):

1) Wiederkehrende normalisierte Beschreibung: kommt mindestens N-mal in derselben Kategorie vor
   (bei Mehrfach-Kategorien nur wenn eine Kategorie ≥70 % der Treffer hat).

2) „Charakteristische“ Schlüsselwörter: Wort kommt überwiegend in einer Kategorie vor
   (Dominanz-Schwelle, z. B. 82 % aller Vorkommen des Worts).

Ausgabe: YAML-Fragment auf stdout.

Beispiel:
  docker compose exec app python3 scripts/suggest_rules_from_labels.py
  docker compose exec app python3 scripts/suggest_rules_from_labels.py --collapse-dates --min-repeat 3
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.utils import db_connection
from scripts.propagate_categories import normalize_description

# Häufige, mehrdeutige Wörter (oft in vielen Kategorien)
GENERIC_TOKENS: Set[str] = {
    "zahlung",
    "überweisung",
    "uberweisung",
    "buchung",
    "gutschrift",
    "lastschrift",
    "dauerauftrag",
    "auftrag",
    "konto",
    "kontoinhaber",
    "datum",
    "betrag",
    "referenz",
    "iban",
    "bic",
    "end",
    "zu",
    "von",
    "mit",
    "nach",
    "siehe",
    "beleg",
    "postbank",
    "ing",
    "girokonto",
    "tagesgeld",
}


def extract_keywords(text: str, min_len: int = 4) -> List[str]:
    words = re.findall(r"[a-zäöüß0-9]+", (text or "").lower())
    return [w for w in words if len(w) >= min_len and w not in GENERIC_TOKENS]


def load_labeled() -> List[Tuple[str, str]]:
    """(category_name, description)"""
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT c.name, t.description
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.description IS NOT NULL AND TRIM(t.description) <> ''
            """
        )
        return [(str(row[0]), str(row[1] or "")) for row in cur.fetchall()]


def suggest_repeated_norms(
    rows: List[Tuple[str, str]],
    *,
    collapse_dates: bool,
    min_repeat: int,
    min_norm_len: int,
    max_pattern_len: int,
    majority: float,
) -> List[Tuple[str, str, int, str]]:
    """
    Returns list of (category, pattern_regex, priority, note).
    """
    bucket: Dict[str, Counter] = defaultdict(Counter)
    for cat, desc in rows:
        n = normalize_description(desc, collapse_dates=collapse_dates)
        if len(n) < min_norm_len:
            continue
        bucket[n][cat] += 1

    out: List[Tuple[str, str, int, str]] = []
    for norm, cat_counts in bucket.items():
        total = sum(cat_counts.values())
        if total < min_repeat:
            continue
        top_cat, top_cnt = cat_counts.most_common(1)[0]
        if top_cnt / total < majority:
            continue
        snippet = norm if len(norm) <= max_pattern_len else norm[:max_pattern_len]
        pattern = re.escape(snippet)
        out.append(
            (
                top_cat,
                pattern,
                58,
                f"wiederholt {top_cnt}x (von {total} gleicher Text)",
            )
        )
    return out


def suggest_dominant_tokens(
    rows: List[Tuple[str, str]],
    *,
    min_token_len: int,
    min_occurrences: int,
    dominance: float,
) -> List[Tuple[str, str, int, str]]:
    """
    Returns (category, pattern with \\b..., priority, note).
    """
    token_cat: Dict[str, Counter] = defaultdict(Counter)
    for cat, desc in rows:
        seen = set(extract_keywords(desc, min_len=min_token_len))
        for tok in seen:
            token_cat[tok][cat] += 1

    out: List[Tuple[str, str, int, str]] = []
    for tok, cat_counts in token_cat.items():
        total = sum(cat_counts.values())
        if total < min_occurrences:
            continue
        best_cat, bc = cat_counts.most_common(1)[0]
        if bc / total < dominance:
            continue
        if len(cat_counts) > 1 and bc <= total - bc:
            continue
        pattern = rf"\b{re.escape(tok)}\b"
        out.append(
            (
                best_cat,
                pattern,
                52,
                f"Wort „{tok}“ in {bc}/{total} Vorkommen → {best_cat}",
            )
        )
    return out


def yaml_escape_single(s: str) -> str:
    """Einfaches YAML-Single-Quoted String."""
    return s.replace("'", "''")


def main() -> None:
    p = argparse.ArgumentParser(description="Regel-Vorschläge aus gelabelten Transaktionen (Variante B)")
    p.add_argument("--collapse-dates", action="store_true", help="Wie propagate: Daten normalisieren")
    p.add_argument("--min-repeat", type=int, default=2, metavar="N", help="Mind. gleiche norm. Beschreibung pro Top-Kategorie")
    p.add_argument("--min-norm-len", type=int, default=12, help="Mindestlänge normierter Text für Heuristik 1")
    p.add_argument("--majority", type=float, default=0.7, help="Anteil gleicher Kategorie bei wiederholtem Text")
    p.add_argument("--min-token-len", type=int, default=5, help="Mindestlänge Schlüsselwort")
    p.add_argument("--min-token-occ", type=int, default=6, help="Mind. Vorkommen eines Worts gesamt")
    p.add_argument("--dominance", type=float, default=0.82, help="Anteil des dominierenden Worts in einer Kategorie")
    p.add_argument("--max-pattern-len", type=int, default=90, help="Abgeschnittene Länge für Muster aus vollem Text")
    p.add_argument("--no-repeats", action="store_true", help="Nur Schlüsselwort-Heuristik")
    p.add_argument("--no-tokens", action="store_true", help="Nur Wiederholungs-Heuristik")
    p.add_argument("--limit", type=int, default=80, help="Max. Anzahl ausgegebener Regeln insgesamt")
    args = p.parse_args()

    rows = load_labeled()
    if not rows:
        print("# Keine gelabelten Transaktionen mit Beschreibung.", file=sys.stderr)
        sys.exit(1)

    combined: List[Tuple[str, str, int, str, str]] = []

    if not args.no_repeats:
        for cat, pat, prio, note in suggest_repeated_norms(
            rows,
            collapse_dates=args.collapse_dates,
            min_repeat=args.min_repeat,
            min_norm_len=args.min_norm_len,
            max_pattern_len=args.max_pattern_len,
            majority=args.majority,
        ):
            combined.append((cat, pat, prio, note, "repeat"))

    if not args.no_tokens:
        for cat, pat, prio, note in suggest_dominant_tokens(
            rows,
            min_token_len=args.min_token_len,
            min_occurrences=args.min_token_occ,
            dominance=args.dominance,
        ):
            combined.append((cat, pat, prio, note, "token"))

    # Duplikat-Pattern vermeiden
    seen_pat: Set[str] = set()
    unique: List[Tuple[str, str, int, str, str]] = []
    for item in combined:
        if item[1] in seen_pat:
            continue
        seen_pat.add(item[1])
        unique.append(item)

    unique.sort(key=lambda x: (-x[2], x[0], x[1]))
    unique = unique[: max(1, args.limit)]

    print("# --- Vorschlag: ans Ende von config/categorization_rules.yaml unter rules: einfügen ---")
    print("# Vorher prüfen: mit bestehenden Regeln kollidierende Prioritäten anpassen.")
    print()
    for cat, pat, prio, note, kind in unique:
        print(f"  # [{kind}] {note}")
        print(f"  - category: {cat}")
        print(f"    pattern: '{yaml_escape_single(pat)}'")
        print(f"    priority: {prio}")
        print()

    print(f"# --- Ende ({len(unique)} Vorschläge) ---", file=sys.stderr)


if __name__ == "__main__":
    main()
