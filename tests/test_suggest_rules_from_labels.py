import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.suggest_rules_from_labels import (
    extract_keywords,
    suggest_dominant_tokens,
    suggest_repeated_norms,
    yaml_escape_single,
)


def test_extract_keywords_filters_short_and_generic():
    assert "zahlung" not in extract_keywords("SEPA Zahlung an REWE")
    assert "rewe" in extract_keywords("SEPA Zahlung an REWE")


def test_yaml_escape_single():
    assert yaml_escape_single("a'b") == "a''b"


def test_suggest_repeated_norms():
    rows = [
        ("Steuern", "Kapitalertragsteuer"),
        ("Steuern", "Kapitalertragsteuer"),
        ("Steuern", "Kapitalertragsteuer"),
        ("Bankgebühren", "Sollzinssatz"),
    ]
    s = suggest_repeated_norms(
        rows,
        collapse_dates=False,
        min_repeat=3,
        min_norm_len=8,
        max_pattern_len=80,
        majority=0.7,
    )
    cats = {x[0] for x in s}
    assert "Steuern" in cats


def test_suggest_dominant_tokens():
    rows = [("Steuern", f"Kapitalertragsteuer Buchung {i}") for i in range(8)]
    rows += [("Lebensmittel", "REWE Markt")] * 3
    s = suggest_dominant_tokens(
        rows,
        min_token_len=5,
        min_occurrences=6,
        dominance=0.8,
    )
    patterns = " ".join(x[1] for x in s)
    assert "kapitalertragsteuer" in patterns.lower()
