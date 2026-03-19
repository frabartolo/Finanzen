"""pytest: Kategorisierungsregeln (YAML, ohne Datenbank)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.categorization_rules import load_default_rules_from_file


def _resolve(description: str, rules):
    """Gleiche Logik wie das frühere scripts/test_categorization.py (höchste Priorität gewinnt)."""
    matched_category = None
    matched_priority = -1
    for rule in rules:
        if rule.matches(description):
            if rule.priority > matched_priority:
                matched_category = rule.category_name
                matched_priority = rule.priority
    return matched_category


@pytest.fixture(scope="module")
def rules():
    r = load_default_rules_from_file()
    assert r, "config/categorization_rules.yaml sollte Regeln enthalten"
    return r


@pytest.mark.parametrize(
    "description,expected",
    [
        ("Apotheke am Markt Einkauf", "Apotheke"),
        ("Dr. med. Schmidt Arztbesuch", "Arzt"),
        ("Krankenhaus St. Georg Rechnung", "Krankenhaus"),
        ("AOK Krankenversicherung Beitrag", "Krankenversicherung"),
        ("Allianz KFZ-Versicherung", "KFZ-Versicherung"),
        ("Haftpflichtversicherung Beitrag", "Haftpflicht"),
        ("Hausratversicherung ERGO", "Hausrat"),
        ("Amazon Bestellung 12345", "Online Shopping"),
        ("eBay Kauf", "Online Shopping"),
        ("PayPal Zahlung", "Online Shopping"),
        ("Netflix Abo Monat", "Entertainment"),
        ("Spotify Premium", "Entertainment"),
        ("YouTube Premium", "Entertainment"),
        ("Amazon Prime Video", "Entertainment"),
        ("REWE Einkauf", "Lebensmittel"),
        ("EDEKA Markt", "Lebensmittel"),
        ("Restaurant Italia", "Lebensmittel"),
        ("Shell Tankstelle", "Tanken"),
        ("Deutsche Bahn Ticket", "Öffentliche Verkehrsmittel"),
        ("Kapitalertragsteuer", "Steuern"),
        ("Solidaritätszuschlag 2. Kontoinhaber", "Steuern"),
        ("Sollzinssatz laut Anlage", "Bankgebühren"),
        ("Kontoabrechnung Saldo der Abschlussposten", "Kontoauszug"),
        ("bis 30.06.2025 Kontoinhaber Stefan", "Kontoauszug"),
    ],
)
def test_rule_expected_category(description, expected, rules):
    got = _resolve(description, rules)
    assert got and got.lower() == expected.lower(), (
        f"{description!r} → {got!r}, erwartet {expected!r}"
    )


def test_no_false_lebensmittel_for_critical(rules):
    """Kritische Kategorien dürfen nicht fälschlich als Lebensmittel enden."""
    critical = [
        ("AOK Krankenversicherung Beitrag", "Krankenversicherung"),
        ("Allianz KFZ-Versicherung", "KFZ-Versicherung"),
        ("Netflix Abo Monat", "Entertainment"),
    ]
    for description, expected in critical:
        got = _resolve(description, rules)
        assert got != "Lebensmittel", f"{description} wurde fälschlich Lebensmittel"
        assert got and got.lower() == expected.lower()
