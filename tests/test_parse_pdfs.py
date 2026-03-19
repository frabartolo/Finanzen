"""pytest: PDF-Parser (ING, Postbank) ohne DB."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.parse_pdfs import (
    parse_ing_transaction,
    parse_postbank_transaction,
    MAX_DESCRIPTION_LENGTH,
)


def test_ing_multiline():
    text = """
06.05.2025
06.05.2025
Gutschrift/Dauerauftrag Stefan Wilhelm
STRAFZINSEN
Referenz: 000000009802
500,00
Neuer Saldo
"""
    trans = parse_ing_transaction(text)
    assert len(trans) == 1
    t = trans[0]
    assert t["amount"] == 500.0
    assert "Stefan Wilhelm" in t["description"]
    assert "STRAFZINSEN" in t["description"]
    assert len(t["description"]) <= MAX_DESCRIPTION_LENGTH


def test_ing_description_length():
    long_desc = "A" * 1000 + "\nBuchungstext"
    text = f"01.01.2024\n{long_desc}\n-50,00\n"
    trans = parse_ing_transaction(text)
    if trans:
        assert len(trans[0]["description"]) <= MAX_DESCRIPTION_LENGTH


def test_postbank_no_bis():
    text2 = "02.06.2024  bis  3107,00"
    trans = parse_postbank_transaction(text2)
    for t in trans:
        assert t["description"].lower() != "bis"
