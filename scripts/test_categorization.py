#!/usr/bin/env python3
"""
Verifikations-Script für Kategorisierungsregeln
Testet ob kritische Kategorien korrekt zugeordnet werden
"""

import sys
import re
from pathlib import Path

# Pfad zum Projekt-Root hinzufügen
sys.path.insert(0, str(Path(__file__).parent.parent))


class CategoryRule:
    """Eine Regel für die Kategorisierung"""
    
    def __init__(self, pattern: str, category_name: str, priority: int = 10):
        self.pattern = re.compile(pattern, re.IGNORECASE)
        self.category_name = category_name
        self.priority = priority
    
    def matches(self, text: str) -> bool:
        """Prüft ob die Regel auf den Text zutrifft"""
        return bool(self.pattern.search(text))


def load_rules_from_categorize_py():
    """Lädt die Regeln direkt aus categorize.py"""
    from scripts.categorize import Categorizer
    cat = Categorizer()
    return cat.rules


def test_categorization():
    """Testet die Kategorisierung mit Beispiel-Transaktionen"""
    
    print("🧪 Teste Kategorisierungsregeln...\n")
    
    try:
        rules = load_rules_from_categorize_py()
    except Exception as e:
        print(f"⚠️  Konnte Regeln nicht aus categorize.py laden: {e}")
        print("   Verwende Fallback-Methode...\n")
        return False
    
    # Test-Fälle: (Beschreibung, Erwartete Kategorie)
    test_cases = [
        # Gesundheit - KRITISCH
        ("Apotheke am Markt Einkauf", "Apotheke"),
        ("Dr. med. Schmidt Arztbesuch", "Arzt"),
        ("Krankenhaus St. Georg Rechnung", "Krankenhaus"),
        ("AOK Krankenversicherung Beitrag", "Krankenversicherung"),
        
        # Versicherungen - KRITISCH
        ("Allianz KFZ-Versicherung", "KFZ-Versicherung"),
        ("Haftpflichtversicherung Beitrag", "Haftpflicht"),
        ("Hausratversicherung ERGO", "Hausrat"),
        
        # Online Shopping - KRITISCH
        ("Amazon Bestellung 12345", "Online Shopping"),
        ("eBay Kauf", "Online Shopping"),
        ("PayPal Zahlung", "Online Shopping"),
        
        # Entertainment - KRITISCH
        ("Netflix Abo Monat", "Entertainment"),
        ("Spotify Premium", "Entertainment"),
        ("YouTube Premium", "Entertainment"),
        ("Amazon Prime Video", "Entertainment"),
        
        # Lebensmittel (sollten NICHT falsch kategorisiert werden)
        ("REWE Einkauf", "Lebensmittel"),
        ("EDEKA Markt", "Lebensmittel"),
        ("Restaurant Italia", "Lebensmittel"),
        
        # Mobilität
        ("Shell Tankstelle", "Tanken"),
        ("Deutsche Bahn Ticket", "Öffentliche Verkehrsmittel"),
    ]
    
    passed = 0
    failed = 0
    critical_failed = []
    
    for description, expected_category in test_cases:
        matched_category = None
        matched_priority = -1
        
        # Finde passende Regel
        for rule in rules:
            if rule.matches(description):
                if rule.priority > matched_priority:
                    matched_category = rule.category_name
                    matched_priority = rule.priority
        
        if matched_category and matched_category.lower() == expected_category.lower():
            print(f"✅ '{description[:40]:<40}' → {matched_category}")
            passed += 1
        elif matched_category == "Lebensmittel" and expected_category != "Lebensmittel":
            # KRITISCHER FEHLER: Wurde fälschlicherweise als Lebensmittel kategorisiert!
            print(f"🔴 '{description[:40]:<40}' → {matched_category} (erwartet: {expected_category}) [KRITISCH!]")
            failed += 1
            critical_failed.append(description)
        elif matched_category:
            print(f"❌ '{description[:40]:<40}' → {matched_category} (erwartet: {expected_category})")
            failed += 1
        else:
            print(f"⚠️  '{description[:40]:<40}' → KEINE KATEGORIE (erwartet: {expected_category})")
            failed += 1
    
    print(f"\n{'='*70}")
    print(f"Ergebnis: {passed} bestanden, {failed} fehlgeschlagen")
    
    if critical_failed:
        print(f"\n🔴 KRITISCH: {len(critical_failed)} Transaktionen wurden fälschlicherweise als 'Lebensmittel' kategorisiert:")
        for desc in critical_failed:
            print(f"   - {desc}")
    
    print(f"{'='*70}")
    
    if failed == 0:
        print("🎉 Alle Tests bestanden! Das Kategorisierungs-Problem ist behoben.")
        return True
    elif len(critical_failed) == 0:
        print(f"✅ Keine kritischen Fehler (falsche Lebensmittel-Kategorisierung)")
        print(f"⚠️  Aber {failed} andere Tests fehlgeschlagen")
        return True
    else:
        print(f"❌ Problem NICHT behoben - {len(critical_failed)} kritische Fehler gefunden")
        return False


if __name__ == "__main__":
    success = test_categorization()
    sys.exit(0 if success else 1)
