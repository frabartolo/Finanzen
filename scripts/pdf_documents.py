#!/usr/bin/env python3
"""PDF-Dokumente in der DB und Verknüpfung zu Transaktionen."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# MariaDB TEXT max. 65535 *Bytes* (utf8mb4: ein Zeichen kann 4 Bytes sein)
RAW_TEXT_MAX_BYTES = 60_000


def truncate_raw_text_for_db(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    encoded = text.encode("utf-8")
    if len(encoded) <= RAW_TEXT_MAX_BYTES:
        return text
    suffix = f"\n\n[… gekürzt für DB, ursprünglich {len(text)} Zeichen …]"
    suffix_b = suffix.encode("utf-8")
    budget = RAW_TEXT_MAX_BYTES - len(suffix_b)
    if budget < 1000:
        budget = RAW_TEXT_MAX_BYTES // 2
    cut = encoded[:budget]
    while cut and (cut[-1] & 0xC0) == 0x80:
        cut = cut[:-1]
    return cut.decode("utf-8", errors="replace") + suffix


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
    stored_text = truncate_raw_text_for_db(raw_text)
    row = cursor.fetchone()

    def _write(doc_id: Optional[int] = None) -> int:
        if row:
            did = int(row[0])
            cursor.execute(
                f"""UPDATE documents SET
                    file_name = {ph},
                    account_id = {ph},
                    raw_text = {ph},
                    file_sha256 = COALESCE({ph}, file_sha256)
                WHERE id = {ph}""",
                (file_name, account_id, stored_text, file_hash, did),
            )
            return did
        cursor.execute(
            f"""INSERT INTO documents
                (source_path, file_name, file_sha256, account_id, raw_text)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph})""",
            (relative_path, file_name, file_hash, account_id, stored_text),
        )
        return int(cursor.lastrowid)

    try:
        return _write()
    except Exception as exc:
        err = str(exc).lower()
        if "1406" not in err and "data too long" not in err:
            raise
        logger.warning(
            "raw_text zu lang für Spalte – speichere gekürzte Vorschau (Migration MEDIUMTEXT empfohlen)"
        )
        stored_text = truncate_raw_text_for_db((raw_text or "")[:8000])
        return _write()


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
