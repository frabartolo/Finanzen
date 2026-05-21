"""Tests für PDF-Text-Extraktion (pdftotext / pdfplumber)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import parse_pdfs as pp


def test_pdftotext_builds_layout_command(tmp_path, monkeypatch):
    pdf = tmp_path / "konto.pdf"
    pdf.write_bytes(b"%PDF-1.4 minimal")

    monkeypatch.setattr(pp, "pdftotext_available", lambda: True)
    monkeypatch.setattr(pp, "_get_pdf_parsing_config", lambda: {"pdftotext_layout": True})

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        m = MagicMock()
        m.returncode = 0
        m.stdout = "Postbank\n01.01.2024  -50,00 EUR"
        m.stderr = ""
        return m

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    text = pp.extract_text_with_pdftotext(pdf)
    assert "Postbank" in text
    cmd = captured["cmd"]
    assert cmd[0] == "pdftotext"
    assert "-layout" in cmd
    assert "-enc" in captured["cmd"]
    assert "UTF-8" in captured["cmd"]
    assert str(pdf) in captured["cmd"]
    assert captured["cmd"][-1] == "-"


def test_extract_pdf_text_prefers_longer_pdftotext(monkeypatch):
    monkeypatch.setattr(
        pp,
        "extract_text_with_pdftotext",
        lambda _p: "A" * 200,
    )
    monkeypatch.setattr(
        pp,
        "extract_text_with_pdfplumber",
        lambda _p: "B" * 50,
    )
    text, method = pp.extract_pdf_text(Path("/tmp/x.pdf"))
    assert method == "pdftotext"
    assert len(text) == 200


def test_extract_pdf_text_fallback_to_pdfplumber(monkeypatch):
    monkeypatch.setattr(pp, "extract_text_with_pdftotext", lambda _p: "")
    monkeypatch.setattr(
        pp,
        "extract_text_with_pdfplumber",
        lambda _p: "ING-DiBa Kontoauszug\n500,00",
    )
    text, method = pp.extract_pdf_text(Path("/tmp/x.pdf"))
    assert method == "pdfplumber"
    assert "ING-DiBa" in text
