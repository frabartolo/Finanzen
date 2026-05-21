#!/usr/bin/env python3
"""PDF-Dokumente in der DB und Verknüpfung zu Transaktionen."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def path_to_relative(path: Path) -> str:
    """Pfad relativ zum Projekt-Root (für source_path in der DB)."""
    p = path.resolve()
    try:
        return str(p.relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(p)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def upsert_pdf_document(
    cursor: Any,
    ph: str,
    *,
    relative_path: str,
    file_name: str,
    account_id: Optional[int],
    raw_text: Optional[str],
    file_hash: Optional[str] = None,
) -> int:
    """
    Legt ein PDF-Dokument an oder aktualisiert es (gleicher source_path).
    Returns: documents.id
    """
    cursor.execute(
        f"SELECT id FROM documents WHERE source_path = {ph}",
        (relative_path,),
    )
    row = cursor.fetchone()
    if row:
        doc_id = int(row[0])
        cursor.execute(
            f"""UPDATE documents SET
                file_name = {ph},
                account_id = {ph},
                raw_text = {ph},
                file_sha256 = COALESCE({ph}, file_sha256)
            WHERE id = {ph}""",
            (file_name, account_id, raw_text, file_hash, doc_id),
        )
        return doc_id

    cursor.execute(
        f"""INSERT INTO documents
            (source_path, file_name, file_sha256, account_id, raw_text)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph})""",
        (relative_path, file_name, file_hash, account_id, raw_text),
    )
    return int(cursor.lastrowid)


def update_document_source_path(
    cursor: Any,
    ph: str,
    document_id: int,
    new_relative_path: str,
    new_file_name: Optional[str] = None,
) -> None:
    """Nach Verschieben inbox → processed den Pfad in der DB anpassen."""
    if new_file_name:
        cursor.execute(
            f"UPDATE documents SET source_path = {ph}, file_name = {ph} WHERE id = {ph}",
            (new_relative_path, new_file_name, document_id),
        )
    else:
        cursor.execute(
            f"UPDATE documents SET source_path = {ph} WHERE id = {ph}",
            (new_relative_path, document_id),
        )


def get_document_by_id(cursor: Any, ph: str, document_id: int) -> Optional[Tuple]:
    cursor.execute(
        f"SELECT id, source_path, file_name, account_id, imported_at FROM documents WHERE id = {ph}",
        (document_id,),
    )
    return cursor.fetchone()
