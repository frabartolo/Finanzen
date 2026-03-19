#!/usr/bin/env python3
"""
Transaktionen automatisch kategorisieren
Unterstützt regelbasierte und optionale ML-basierte Kategorisierung
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Pfad zum Projekt-Root hinzufügen
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.utils import load_config, db_connection, get_db_placeholder
from scripts.categorization_rules import CategoryRule, load_all_rules

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class Categorizer:
    """Hauptklasse für die Kategorisierung"""

    def __init__(self):
        self.rules: List[CategoryRule] = []
        self.category_cache: Dict[str, int] = {}
        self._load_rules()
        self._load_categories()

    def _load_categories(self):
        """Lädt alle Kategorien aus der Datenbank in einen Cache"""
        try:
            with db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name FROM categories")
                for cat_id, cat_name in cursor.fetchall():
                    self.category_cache[cat_name.lower()] = cat_id
            logger.info("✅ %s Kategorien geladen", len(self.category_cache))
        except Exception as e:
            logger.error("❌ Fehler beim Laden der Kategorien: %s", e)

    def _load_rules(self):
        """Lädt Regeln aus config/categorization_rules.yaml + optional settings."""
        try:
            settings = load_config("settings")
            extra = settings.get("categorization_rules") or None
            self.rules = load_all_rules(extra if isinstance(extra, dict) else None)
        except Exception as e:
            logger.warning(
                "⚠️ Fehler beim Laden der Regeln: %s – versuche nur YAML-Standard",
                e,
            )
            try:
                self.rules = load_all_rules(None)
            except Exception as e2:
                logger.error("❌ Keine Regeln ladbar: %s", e2)
                self.rules = []

    def categorize_transaction(self, transaction: Dict) -> Optional[int]:
        """
        Kategorisiert eine einzelne Transaktion

        Args:
            transaction: Dict mit 'description' und 'amount'

        Returns:
            category_id oder None
        """
        description = transaction.get("description", "")

        if not description:
            return None

        for rule in self.rules:
            if rule.matches(description):
                category_name_lower = rule.category_name.lower()

                if category_name_lower in self.category_cache:
                    category_id = self.category_cache[category_name_lower]
                    logger.debug(
                        "✓ Regel-Match: '%s' → %s",
                        description[:50],
                        rule.category_name,
                    )
                    return category_id

        logger.debug("⚠ Keine Regel gefunden für: '%s'", description[:50])
        return None

    def categorize_all(self, force_recategorize: bool = False) -> Tuple[int, int]:
        """
        Kategorisiert alle unkategorisierten Transaktionen

        Args:
            force_recategorize: Wenn True, auch bereits kategorisierte neu zuordnen

        Returns:
            Tuple (kategorisiert, gesamt)
        """
        logger.info("🏷️ Starte Kategorisierung...")

        try:
            with db_connection() as conn:
                cursor = conn.cursor()
                ph = get_db_placeholder()

                if force_recategorize:
                    cursor.execute("SELECT id, description, amount FROM transactions")
                else:
                    cursor.execute(
                        "SELECT id, description, amount FROM transactions "
                        "WHERE category_id IS NULL"
                    )

                transactions = cursor.fetchall()
                total_count = len(transactions)

                if total_count == 0:
                    logger.info("✅ Keine unkategorisierten Transaktionen gefunden")
                    return 0, 0

                logger.info("📊 %s Transaktionen zu kategorisieren", total_count)

                categorized_count = 0
                for trans_id, description, amount in transactions:
                    category_id = self.categorize_transaction(
                        {
                            "description": description,
                            "amount": amount,
                        }
                    )

                    if category_id:
                        cursor.execute(
                            f"UPDATE transactions SET category_id = {ph} WHERE id = {ph}",
                            (category_id, trans_id),
                        )
                        categorized_count += 1

                conn.commit()
                logger.info(
                    "✅ %s/%s Transaktionen kategorisiert",
                    categorized_count,
                    total_count,
                )
                return categorized_count, total_count

        except Exception as e:
            logger.error("❌ Fehler bei der Kategorisierung: %s", e)
            return 0, 0


def main():
    """Hauptfunktion"""
    parser = argparse.ArgumentParser(description="Transaktionen kategorisieren")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Auch bereits kategorisierte Transaktionen neu zuordnen",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Detaillierte Debug-Ausgabe",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    categorizer = Categorizer()
    categorized, total = categorizer.categorize_all(force_recategorize=args.force)

    if total > 0:
        percentage = (categorized / total) * 100
        logger.info("📈 Erfolgsrate: %.1f%%", percentage)


if __name__ == "__main__":
    main()
