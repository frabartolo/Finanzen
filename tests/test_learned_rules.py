"""Tests für gelernte Kategorisierungsregeln."""
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.learned_rules import (
    LEARNED_RULES_PATH,
    append_learned_rule,
    load_learned_rules_from_file,
    suggest_pattern_from_description,
)
from scripts.categorization_rules import load_all_rules, match_category_name


@pytest.fixture
def isolated_learned_rules(tmp_path, monkeypatch):
    p = tmp_path / "categorization_rules_learned.yaml"
    p.write_text("rules: []\n", encoding="utf-8")
    monkeypatch.setattr("scripts.learned_rules.LEARNED_RULES_PATH", p)
    return p


def test_append_and_match(isolated_learned_rules, monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)
    assert append_learned_rule("TestKat", r"\buniquevendor99\b", priority=90)
    assert not append_learned_rule("TestKat", r"\buniquevendor99\b")
    rules = load_learned_rules_from_file()
    assert len(rules) == 1
    assert match_category_name("Zahlung an UniqueVendor99 GmbH", rules) == "TestKat"


def test_suggest_pattern():
    pat = suggest_pattern_from_description("SEPA Lastschrift AMAZON PAYMENTS EUROPE")
    assert "amazon" in pat.lower() or "payments" in pat.lower()
