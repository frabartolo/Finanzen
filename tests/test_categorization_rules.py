"""Schema / Loader für categorization_rules."""
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.categorization_rules import (
    load_default_rules_from_file,
    rules_from_list_entries,
    rules_from_settings_dict,
)


def test_default_yaml_loads():
    rules = load_default_rules_from_file()
    assert len(rules) >= 40


def test_invalid_regex_in_list_raises():
    with pytest.raises(ValueError, match="ungültiges Regex"):
        rules_from_list_entries(
            [{"category": "X", "pattern": "(unclosed", "priority": 1}],
            "test",
        )


def test_settings_dict_accepts_string_pattern():
    rules = rules_from_settings_dict(
        {"TestCat": [r"\bfoo\b", {"pattern": r"\bbar\b", "priority": 20}]},
        "unit",
    )
    assert len(rules) == 2
    assert rules[1].priority == 20


def test_rules_yaml_file_has_list_schema():
    path = Path(__file__).resolve().parent.parent / "config" / "categorization_rules.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "rules" in data
    assert isinstance(data["rules"], list)
    for entry in data["rules"][:3]:
        assert "category" in entry and "pattern" in entry
