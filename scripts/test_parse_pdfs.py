#!/usr/bin/env python3
"""
Test für PDF-Parser (ING, Postbank)
Prüft ob Transaktionen korrekt extrahiert werden – insbesondere mehrzeilige Beschreibungen
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.parse_pdfs import (
    parse_ing_transaction,
    parse_postbank_transaction,
    MAX_DESCRIPTION_LENGTH,
)


def test_ing_multiline():
    """ING-Format wie im Screenshot: Datum, Gutschrift/Dauerauftrag, Name, Verwendungszweck"""
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
    assert len(trans) == 1, f"Erwarte 1 Transaktion, bekam {len(trans)}"
    t = trans[0]
    assert t["amount"] == 500.0
    assert "Stefan Wilhelm" in t["description"]
    assert "STRAFZINSEN" in t["description"]
    assert len(t["description"]) <= MAX_DESCRIPTION_LENGTH
    print("✓ ING mehrzeilig: OK")


def test_ing_description_length():
    """Keine 27k-Zeichen-Beschreibungen mehr"""
    # Simuliert Text wo früher der ganze PDF-Inhalt als eine Transaktion gefangen wurde
    long_desc = "A" * 1000 + "\nBuchungstext"
    text = f"01.01.2024\n{long_desc}\n-50,00\n"
    trans = parse_ing_transaction(text)
    if trans:
        assert len(trans[0]["description"]) <= MAX_DESCRIPTION_LENGTH
    print("✓ ING max Länge: OK")


def test_postbank_no_bis():
    """Postbank: 'bis' sollte nicht als Beschreibung erscheinen"""
    # Format 2 - Zeile die früher "bis" lieferte
    text = "2024-06-01 02.06.2024  bis  3107,00"
    # Unser Parser erwartet DD.MM.YYYY - diese Zeile hat anderes Format
    text2 = "02.06.2024  bis  3107,00"
    trans = parse_postbank_transaction(text2)
    # Entweder keine Transaktion (weil "bis" gefiltert) oder "Unbekannter Vorgang"
    for t in trans:
        assert t["description"].lower() != "bis"
    print("✓ Postbank kein 'bis': OK")


def main():
    print("🧪 Teste PDF-Parser (ING, Postbank)\n")
    errors = []
    for name, fn in [
        ("ING mehrzeilig", test_ing_multiline),
        ("ING max Beschreibungslänge", test_ing_description_length),
        ("Postbank 'bis'-Filter", test_postbank_no_bis),
    ]:
        try:
            fn()
        except AssertionError as e:
            errors.append(f"{name}: {e}")
        except Exception as e:
            errors.append(f"{name}: {e}")
    if errors:
        print("\n❌ Fehler:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("\n✅ Alle Parser-Tests bestanden")


if __name__ == "__main__":
    main()
