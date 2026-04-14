"""Tests für Postbank-CSV-Import."""

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.import_postbank_csv import (
    parse_de_amount,
    parse_de_date,
    parse_postbank_csv_file,
    extract_iban_from_row,
)


SAMPLE_CSV = """Umsätze
Konto;Filial-/Kontonummer;IBAN;Währung
Postbank Giro extra plus;396 5827639 00;DE46370100500649213501;EUR

1.1.2025 - 31.1.2026
Letzter Kontostand;;;;14.188,53;EUR
Vorgemerkte und noch nicht gebuchte Umsätze sind nicht Bestandteil dieser Übersicht.
Buchungstag;Wert;Umsatzart;Begünstigter / Auftraggeber;Verwendungszweck;IBAN / Kontonummer;BIC;Kundenreferenz;Mandatsreferenz;Gläubiger ID;Fremde Gebühren;Betrag;Abweichender Empfänger;Anzahl der Aufträge;Anzahl der Schecks;Soll;Haben;Währung
30.1.2026;30.1.2026;SEPA Lastschrift;TARGOBANK VISA DD EXTERN;RG. 20 01 4871660023951774;DE21300209005001420092;;NOTPROVIDED;3303817101001;DE63ZZZ00000056647;;-247,11;;;;-247,11;;EUR
27.1.2026;27.1.2026;SEPA Überweisung (Lohn, Gehalt, Rente);R+V Allgemeine Versicherung Aktieng esellschaft;Lohn/Gehalt 00201901/202601;DE30500604000002012247;;2019010014302;;;;5.027,65;;;;;5.027,65;EUR
27.1.2026;27.1.2026;SEPA Lastschrift;AMAZON PAYMENTS EUROPE S.C.A.;028-5975790-1129122 AMZN Mktp DE;DE87300308801908262006;;41O9MVCE0F600B44;GMJ2WEBKY;DE94ZZZ00000561653;;-7,99;;;;-7,99;;EUR
Kontostand;31.1.2026;;;42.077,44;EUR
"""


def test_parse_de_amount() -> None:
    assert parse_de_amount("-247,11") == pytest.approx(-247.11)
    assert parse_de_amount("5.027,65") == pytest.approx(5027.65)
    assert parse_de_amount("") is None
    assert parse_de_amount(None) is None


def test_parse_de_date() -> None:
    assert parse_de_date("30.1.2026") == date(2026, 1, 30)
    assert parse_de_date("Kontostand") is None


def test_extract_iban_from_row() -> None:
    assert (
        extract_iban_from_row(
            ["Postbank Giro", "396 5827639 00", "DE46370100500649213501", "EUR"]
        )
        == "DE46370100500649213501"
    )


def test_parse_postbank_csv_file(tmp_path: Path) -> None:
    p = tmp_path / "umsaetze.csv"
    p.write_text(SAMPLE_CSV, encoding="utf-8")
    iban, txs = parse_postbank_csv_file(p)
    assert iban == "DE46370100500649213501"
    assert len(txs) == 3
    assert txs[0]["date"] == date(2026, 1, 30)
    assert txs[0]["amount"] == pytest.approx(-247.11)
    assert "TARGOBANK" in txs[0]["description"]
    assert txs[1]["amount"] == pytest.approx(5027.65)
    assert txs[2]["amount"] == pytest.approx(-7.99)

