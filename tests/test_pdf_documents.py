"""Tests für PDF-Dokument-Pfade und raw_text-Kürzung."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.pdf_documents import (
    RAW_TEXT_MAX_BYTES,
    path_to_relative,
    truncate_raw_text_for_db,
    PROJECT_ROOT,
)


def test_path_to_relative_under_project():
    p = PROJECT_ROOT / "data" / "inbox" / "test.pdf"
    rel = path_to_relative(p)
    assert rel.replace("\\", "/") == "data/inbox/test.pdf"


def test_truncate_raw_text_by_bytes_not_chars():
    # Viele Umlaute/Sonderzeichen → viele UTF-8-Bytes pro Zeichen
    text = "ä" * 30_000
    out = truncate_raw_text_for_db(text)
    assert out is not None
    assert len(out.encode("utf-8")) <= RAW_TEXT_MAX_BYTES + 500
