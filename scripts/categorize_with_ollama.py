#!/usr/bin/env python3
"""
Variante C: Ollama (z. B. deepseek-r1:8b) für Kategorie-Vorschläge zu unkategorisierten Transaktionen.

Nutzt settings.ollama.model_categorization (Fallback: ollama.model).
Dry-Run standardmäßig; --apply schreibt in die DB.

Beispiele:
  docker compose exec app python3 scripts/categorize_with_ollama.py --limit 5
  docker compose exec app python3 scripts/categorize_with_ollama.py --apply --limit 20
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.utils import db_connection, get_db_placeholder, load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _get_ollama_categorization_config() -> dict:
    cfg = load_config("settings")
    root = cfg.get("settings", cfg)
    ollama = (root or {}).get("ollama", {})
    model = ollama.get("model_categorization") or ollama.get("model", "deepseek-r1:8b")
    host = os.getenv("OLLAMA_HOST") or ollama.get("host") or ""
    return {
        "enabled": bool(ollama.get("enabled")),
        "host": host.rstrip("/"),
        "model": model,
        "timeout": int(ollama.get("timeout", 60)),
    }


def _ollama_suggest_category(
    description: str,
    category_names: List[str],
    *,
    host: str,
    model: str,
    timeout: int,
) -> Optional[str]:
    """
    Fragt Ollama nach einer Kategorie für die Buchungsbeschreibung.
    Returns: exakter Kategoriename aus category_names oder None.
    """
    names_str = ", ".join(sorted(category_names))
    prompt = f"""Wähle genau eine Kategorie aus der folgenden Liste für diese Buchungsbeschreibung.
Kategorien (nur diese verwenden): {names_str}

Buchungsbeschreibung: "{description[:600]}"

Antworte ausschließlich mit dem exakten Kategorienamen aus der Liste, sonst nichts."""

    try:
        body = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
        }).encode("utf-8")
        req = Request(
            f"{host}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        response_text = (data.get("response") or "").strip()
        # Deepseek-R1 / Reasoning-Modelle: <think>...</think> entfernen
        response_text = re.sub(
            r"<think>[\s\S]*?</think>", "", response_text, flags=re.IGNORECASE
        ).strip()
        response_text = response_text.split("\n")[0].strip().strip('"\'')
        if not response_text:
            return None
        low = response_text.lower()
        for name in category_names:
            if name.lower() == low:
                return name
        for name in category_names:
            if low in name.lower() or name.lower() in low:
                return name
        return None
    except (URLError, HTTPError, json.JSONDecodeError, OSError) as e:
        logger.warning("Ollama-Abfrage fehlgeschlagen: %s", e)
        return None


def run(
    dry_run: bool = True,
    limit: int = 30,
) -> Tuple[int, int]:
    """
    Lädt unkategorisierte Transaktionen, fragt Ollama pro Zeile, optional DB-Update.
    Returns: (aktualisiert, geprüft).
    """
    cfg = _get_ollama_categorization_config()
    if not cfg.get("enabled") or not cfg.get("host"):
        logger.error("Ollama nicht aktiv oder host fehlt (settings.ollama).")
        return 0, 0

    host = cfg["host"]
    model = cfg["model"]
    timeout = cfg["timeout"]
    logger.info("Ollama-Kategorisierung: Modell %s, Host %s", model, host)

    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM categories ORDER BY name")
        category_rows = cur.fetchall()
        category_names = [r[1] for r in category_rows]
        name_to_id = {r[1]: r[0] for r in category_rows}

        cur.execute(
            """
            SELECT id, description
            FROM transactions
            WHERE category_id IS NULL
              AND description IS NOT NULL
              AND TRIM(description) <> ''
            ORDER BY date DESC, id DESC
            LIMIT %s
            """,
            (max(1, limit),),
        )
        rows = cur.fetchall()

    if not category_names:
        logger.error("Keine Kategorien in der DB.")
        return 0, 0
    if not rows:
        logger.info("Keine unkategorisierten Transaktionen mit Beschreibung.")
        return 0, 0

    ph = get_db_placeholder()
    updates: List[Tuple[int, int, str]] = []  # (trans_id, category_id, category_name)

    for i, (trans_id, description) in enumerate(rows, 1):
        desc_short = (description or "")[:80].replace("\n", " ")
        suggested = _ollama_suggest_category(
            description or "",
            category_names,
            host=host,
            model=model,
            timeout=timeout,
        )
        if suggested and suggested in name_to_id:
            cat_id = name_to_id[suggested]
            updates.append((trans_id, cat_id, suggested))
            logger.info("[%s/%s] id=%s → %s | %s", i, len(rows), trans_id, suggested, desc_short)
        else:
            logger.info("[%s/%s] id=%s → (kein Treffer) | %s", i, len(rows), trans_id, desc_short)

    if dry_run:
        logger.info("Dry-Run: %s Vorschläge (keine DB-Änderung). Zum Schreiben: --apply", len(updates))
        return len(updates), len(rows)

    applied = 0
    with db_connection() as conn:
        cur = conn.cursor()
        for trans_id, cat_id, _ in updates:
            cur.execute(
                f"UPDATE transactions SET category_id = {ph} WHERE id = {ph} AND category_id IS NULL",
                (cat_id, trans_id),
            )
            applied += cur.rowcount
        conn.commit()
    logger.info("Übernommen: %s von %s Vorschlägen in DB geschrieben.", applied, len(updates))
    return applied, len(rows)


def main() -> None:
    p = argparse.ArgumentParser(
        description="Kategorie-Vorschläge per Ollama (Variante C, Modell aus settings.ollama.model_categorization)"
    )
    p.add_argument("--apply", action="store_true", help="Vorschläge in der DB speichern")
    p.add_argument("--limit", type=int, default=30, metavar="N", help="Max. Anzahl zu prüfender Transaktionen")
    args = p.parse_args()

    run(dry_run=not args.apply, limit=max(1, args.limit))


if __name__ == "__main__":
    main()
