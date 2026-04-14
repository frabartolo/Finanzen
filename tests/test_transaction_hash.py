"""Tests für compute_transaction_hash (idempotente Imports)."""
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.utils import compute_transaction_hash


def test_hash_stable():
    h1 = compute_transaction_hash(1, date(2024, 3, 1), 550.0, "Miete", "pdf")
    h2 = compute_transaction_hash(1, date(2024, 3, 1), 550.0, "Miete", "pdf")
    assert h1 == h2
    assert len(h1) == 64


def test_hash_differs_on_amount():
    a = compute_transaction_hash(1, date(2024, 3, 1), 550.0, "X", "pdf")
    b = compute_transaction_hash(1, date(2024, 3, 1), 551.0, "X", "pdf")
    assert a != b


def test_hash_same_across_import_sources():
    """Gleiche Buchung aus PDF vs. FinTS/CSV soll denselben Hash haben."""
    a = compute_transaction_hash(1, date(2024, 3, 1), 10.0, "X", "pdf")
    b = compute_transaction_hash(1, date(2024, 3, 1), 10.0, "X", "fints")
    assert a == b


def test_amount_normalization():
    """550 und 550.00 ergeben gleichen Hash."""
    a = compute_transaction_hash(1, date(2024, 1, 1), 550, "D", "pdf")
    b = compute_transaction_hash(1, date(2024, 1, 1), 550.00, "D", "pdf")
    assert a == b
