#!/usr/bin/env python3
"""
Kategorisierungsregeln aus YAML laden und validieren.
Standardregeln: config/categorization_rules.yaml
Zusätzlich: settings.yaml → categorization_rules (Dict-Format, wie bisher).
"""

from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class CategoryRule:
    """Eine Regel für die Kategorisierung."""

    def __init__(self, pattern: str, category_name: str, priority: int = 10):
        self.pattern = re.compile(pattern, re.IGNORECASE)
        self.category_name = category_name
        self.priority = priority

    def matches(self, text: str) -> bool:
        return bool(self.pattern.search(text))

    def __repr__(self):
        return (
            f"CategoryRule({self.pattern.pattern!r}, {self.category_name!r}, "
            f"priority={self.priority})"
        )


def _validate_pattern(pattern: str, context: str) -> None:
    if not pattern or not isinstance(pattern, str):
        raise ValueError(f"{context}: 'pattern' muss ein nicht-leerer String sein")
    try:
        re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        raise ValueError(f"{context}: ungültiges Regex: {e}") from e


def rules_from_list_entries(entries: List[Dict[str, Any]], source: str) -> List[CategoryRule]:
    """Validiert Liste von {category, pattern, priority?} aus categorization_rules.yaml."""
    out: List[CategoryRule] = []
    for i, entry in enumerate(entries):
        ctx = f"{source}[{i}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{ctx}: Eintrag muss ein Objekt sein")
        category = entry.get("category")
        pattern = entry.get("pattern")
        priority = entry.get("priority", 10)
        if not category or not isinstance(category, str):
            raise ValueError(f"{ctx}: 'category' fehlt oder ist kein String")
        _validate_pattern(pattern, ctx)
        if not isinstance(priority, (int, float)) or isinstance(priority, bool):
            raise ValueError(f"{ctx}: 'priority' muss eine Zahl sein")
        out.append(CategoryRule(str(pattern), category.strip(), int(priority)))
    return out


def rules_from_settings_dict(rules_config: Dict[str, Any], source: str) -> List[CategoryRule]:
    """
    Legacy-Format aus settings.yaml:
    Kategorie-Name -> Liste von Pattern-Strings oder {pattern, priority}.
    """
    out: List[CategoryRule] = []
    for category_name, patterns in rules_config.items():
        if not isinstance(category_name, str) or not category_name.strip():
            logger.warning("%s: überspringe ungültigen Kategorienamen: %r", source, category_name)
            continue
        if not isinstance(patterns, list):
            logger.warning("%s: Kategorie %r – erwartete Liste, bekam %s", source, category_name, type(patterns))
            continue
        for j, pattern_config in enumerate(patterns):
            ctx = f"{source}['{category_name}'][{j}]"
            if isinstance(pattern_config, str):
                pattern = pattern_config
                priority = 10
            elif isinstance(pattern_config, dict):
                pattern = pattern_config.get("pattern", "")
                priority = pattern_config.get("priority", 10)
            else:
                continue
            if not pattern:
                continue
            _validate_pattern(pattern, ctx)
            if not isinstance(priority, (int, float)) or isinstance(priority, bool):
                raise ValueError(f"{ctx}: 'priority' muss eine Zahl sein")
            out.append(CategoryRule(str(pattern), category_name.strip(), int(priority)))
    return out


def load_default_rules_from_file(
    path: Optional[Path] = None,
) -> List[CategoryRule]:
    """Lädt rules[] aus config/categorization_rules.yaml."""
    base = Path(__file__).resolve().parent.parent / "config" / "categorization_rules.yaml"
    path = path or base
    if not path.exists():
        logger.warning("Keine Datei %s – keine Standard-Regeln aus YAML", path)
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    entries = data.get("rules")
    if entries is None:
        logger.warning("%s: Schlüssel 'rules' fehlt oder ist leer", path)
        return []
    if not isinstance(entries, list):
        raise ValueError(f"{path}: 'rules' muss eine Liste sein")
    return rules_from_list_entries(entries, source=str(path))


def merge_and_sort_rules(
    base: List[CategoryRule], extra: List[CategoryRule]
) -> List[CategoryRule]:
    combined = base + extra
    combined.sort(key=lambda r: r.priority, reverse=True)
    return combined


def match_category_name(description: str, rules: List[CategoryRule]) -> Optional[str]:
    """
    Höchste Priorität gewinnt bei mehreren Treffern (gleiche Logik wie Categorizer).
    Gibt den Kategorienamen zurück oder None.
    """
    if not (description or "").strip():
        return None
    best: Optional[Tuple[int, str]] = None  # (priority, category_name)
    for rule in rules:
        if rule.matches(description):
            if best is None or rule.priority > best[0]:
                best = (rule.priority, rule.category_name)
    return best[1] if best else None


def load_all_rules(settings_categorization_rules: Optional[Dict[str, Any]] = None) -> List[CategoryRule]:
    """
    Standard aus YAML + optional Zusatzregeln aus settings (Dict-Format).
    """
    base = load_default_rules_from_file()
    extra: List[CategoryRule] = []
    if settings_categorization_rules:
        extra = rules_from_settings_dict(settings_categorization_rules, "settings.categorization_rules")
    rules = merge_and_sort_rules(base, extra)
    if extra:
        logger.info(
            "📋 %s Regeln geladen (%s aus YAML + %s aus settings)",
            len(rules),
            len(base),
            len(extra),
        )
    else:
        logger.info("📋 %s Kategorisierungsregeln aus YAML geladen", len(rules))
    return rules
