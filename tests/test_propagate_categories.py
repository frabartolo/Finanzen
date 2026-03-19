"""Tests für Normalisierung (propagate_categories, ohne DB)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.propagate_categories import normalize_description


def test_normalize_whitespace():
    assert normalize_description("  Foo   BAR  ") == "foo bar"


def test_normalize_empty():
    assert normalize_description("") == ""
    assert normalize_description("   ") == ""


def test_collapse_dates_ddmmyyyy():
    a = normalize_description("bis 30.06.2025 Kontoinhaber", collapse_dates=True)
    b = normalize_description("bis 15.06.2025 Kontoinhaber", collapse_dates=True)
    assert a == b == "bis #d# kontoinhaber"


def test_collapse_dates_iso():
    t = normalize_description("Buchung 2025-12-31 Ende", collapse_dates=True)
    assert "#d#" in t


def test_no_collapse_dates_default():
    a = normalize_description("30.06.2025")
    assert a == "30.06.2025"
