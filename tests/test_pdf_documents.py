"""Tests für PDF-Dokument-Pfade."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.pdf_documents import path_to_relative, PROJECT_ROOT


def test_path_to_relative_under_project():
    p = PROJECT_ROOT / "data" / "inbox" / "test.pdf"
    rel = path_to_relative(p)
    assert rel.replace("\\", "/") == "data/inbox/test.pdf"
