#!/usr/bin/env python3
"""Persistente Regeln aus dem interaktiven Lernmodus."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

import yaml

from scripts.categorization_rules import (
    CategoryRule,
    load_default_rules_from_file,
    merge_and_sort_rules,
    rules_from_list_entries,
)

LEARNED_RULES_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "categorization_rules_learned.yaml"
)


def load_learned_rules_from_file() -> List[CategoryRule]:
    if not LEARNED_RULES_PATH.exists():
        return []
    with open(LEARNED_RULES_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    entries = data.get("rules")
    if not entries:
        return []
    if not isinstance(entries, list):
        raise ValueError(f"{LEARNED_RULES_PATH}: 'rules' muss eine Liste sein")
    return rules_from_list_entries(entries, source=str(LEARNED_RULES_PATH))


def list_learned_rule_patterns() -> List[Tuple[str, str]]:
    """(category, pattern) für Duplikat-Check."""
    return [(r.category_name, r.pattern.pattern) for r in load_learned_rules_from_file()]


def append_learned_rule(
    category: str,
    pattern: str,
    *,
    priority: int = 76,
    note: str = "",
) -> bool:
    """
    Hängt eine Regel an categorization_rules_learned.yaml an.
    Returns False wenn (category, pattern) bereits existiert.
    """
    category = category.strip()
    pattern = pattern.strip()
    if not category or not pattern:
        raise ValueError("category und pattern dürfen nicht leer sein")

    path = LEARNED_RULES_PATH
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    rules = data.get("rules")
    if rules is None:
        rules = []
    if not isinstance(rules, list):
        rules = []

    try:
        compiled = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        raise ValueError(f"Ungültiges Regex: {e}") from e

    for entry in rules:
        if not isinstance(entry, dict):
            continue
        if (
            entry.get("category", "").strip() == category
            and entry.get("pattern", "").strip() == pattern
        ):
            return False

    new_entry = {
        "category": category,
        "pattern": pattern,
        "priority": int(priority),
    }
    if note:
        new_entry["note"] = note.strip()
    rules.append(new_entry)
    data["rules"] = rules

    header = (
        "# Regeln aus dem interaktiven Lernmodus (scripts/learn_interactive.py)\n"
        "# Werden mit config/categorization_rules.yaml zusammengeführt.\n\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        yaml.dump(
            {"rules": rules},
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
    return True


def suggest_pattern_from_description(description: str) -> str:
    """Einfaches Regex-Muster aus einem Buchungstext vorschlagen."""
    from scripts.suggest_rules_from_labels import extract_keywords

    desc = (description or "").strip()
    words = extract_keywords(desc, min_len=5)
    if not words:
        words = extract_keywords(desc, min_len=4)
    if words:
        token = max(words, key=len)
        return rf"\b{re.escape(token)}\b"
    snippet = re.sub(r"\s+", " ", desc.lower())[:40]
    return re.escape(snippet) if snippet else r".+"
