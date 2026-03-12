#!/usr/bin/env python3
"""
Transaktionen automatisch kategorisieren
Unterstützt regelbasierte und optionale ML-basierte Kategorisierung
"""

import sys
import re
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import logging

# Pfad zum Projekt-Root hinzufügen
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.utils import load_config, get_db_connection, get_db_placeholder

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CategoryRule:
    """Eine Regel für die Kategorisierung"""
    
    def __init__(self, pattern: str, category_name: str, priority: int = 10):
        self.pattern = re.compile(pattern, re.IGNORECASE)
        self.category_name = category_name
        self.priority = priority
    
    def matches(self, text: str) -> bool:
        """Prüft ob die Regel auf den Text zutrifft"""
        return bool(self.pattern.search(text))
    
    def __repr__(self):
        return f"CategoryRule({self.pattern.pattern!r}, {self.category_name!r}, priority={self.priority})"


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
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, name FROM categories")
            
            for cat_id, cat_name in cursor.fetchall():
                self.category_cache[cat_name.lower()] = cat_id
            
            conn.close()
            logger.info(f"✅ {len(self.category_cache)} Kategorien geladen")
        except Exception as e:
            logger.error(f"❌ Fehler beim Laden der Kategorien: {e}")
    
    def _load_rules(self):
        """Lädt Kategorisierungsregeln aus der Konfiguration"""
        try:
            settings = load_config('settings')
            rules_config = settings.get('categorization_rules', {})
            
            # IMMER mit Default-Regeln starten
            self.rules = self._get_default_rules()
            
            # Custom Rules aus Config HINZUFÜGEN (nicht ersetzen!)
            custom_count = 0
            for category_name, patterns in rules_config.items():
                for pattern_config in patterns:
                    if isinstance(pattern_config, str):
                        pattern = pattern_config
                        priority = 10
                    elif isinstance(pattern_config, dict):
                        pattern = pattern_config.get('pattern', '')
                        priority = pattern_config.get('priority', 10)
                    else:
                        continue
                    
                    if pattern:
                        self.rules.append(CategoryRule(pattern, category_name, priority))
                        custom_count += 1
            
            if custom_count > 0:
                logger.info(f"📋 {len(self.rules)} Regeln geladen ({custom_count} Custom + {len(self.rules)-custom_count} Standard)")
            else:
                logger.info(f"📋 {len(self.rules)} Standard-Kategorisierungsregeln geladen")
            
            # Nach Priorität sortieren (höhere Priorität zuerst)
            self.rules.sort(key=lambda r: r.priority, reverse=True)
            
        except Exception as e:
            logger.warning(f"⚠️ Fehler beim Laden der Regeln: {e} - verwende Default-Regeln")
            self.rules = self._get_default_rules()
    
    def _get_default_rules(self) -> List[CategoryRule]:
        """Standard-Kategorisierungsregeln"""
        return [
            # Einnahmen
            CategoryRule(r'\b(gehalt|lohn|salary)\b', 'Gehalt', priority=100),
            CategoryRule(r'\b(bonus|prämie|sonderzahlung)\b', 'Bonus', priority=100),
            # Vermietung Einnahmen (Kontoauszug: SEPA Überweisung von … Verwendungszweck …)
            CategoryRule(r'\b(monica\s*jung|mietameixa|sebastian\s*juros)\b', 'Miete Sonnenberg', priority=95),
            CategoryRule(r'\b(miete\s*und\s*nebenkosten|miete\s*wohnung)\b', 'Miete Sonnenberg', priority=94),
            CategoryRule(r'\b(sonnenberg|ameixa|juros|jung)\b', 'Miete Sonnenberg', priority=92),
            CategoryRule(r'\b(neuhof|zum neuhof)\b', 'Miete Neuhof', priority=92),
            CategoryRule(r'\b(weinberg|pacht.*einnahme|verpachtung)\b', 'Miete Weinbergsgelände', priority=92),
            CategoryRule(r'\b(miete.*eingang|mietzahlung.*von)\b', 'Miete Sonnenberg', priority=90),
            CategoryRule(r'\b(überweisung.*miete)\b', 'Miete Neuhof', priority=90),
            
            # Wohnen
            CategoryRule(r'\b(miete|kaltmiete|warmmiete)\b', 'Miete', priority=80),
            CategoryRule(r'\b(strom|stadtwerke|energie|e\.on|vattenfall)\b', 'Strom', priority=80),
            CategoryRule(r'\b(internet|telekom|vodafone|1&1|o2)\b', 'Internet', priority=80),
            CategoryRule(r'\b(wasser|abwasser)\b', 'Wohnen', priority=70),
            CategoryRule(r'\b(müll|müllgebühr|entsorgung)\b', 'Wohnen', priority=70),
            CategoryRule(r'\b(versicherung.*wohnung)\b', 'Wohnen', priority=70),
            
            # Mobilität
            CategoryRule(r'\b(tankstelle|tanken|shell|aral|esso|jet|total)\b', 'Tanken', priority=80),
            CategoryRule(r'\b(werkstatt|reparatur|inspektion|tüv|dekra)\b', 'Wartung', priority=80),
            CategoryRule(r'\b(bahn|deutsche bahn|db|train)\b', 'Öffentliche Verkehrsmittel', priority=75),
            CategoryRule(r'\b(bus|ticket|fahrschein|mvg|hvv)\b', 'Öffentliche Verkehrsmittel', priority=75),
            
            # Lebensmittel & Einkauf
            CategoryRule(r'\b(rewe|edeka|aldi|lidl|penny|netto|kaufland)\b', 'Lebensmittel', priority=80),
            CategoryRule(r'\b(supermarkt|lebensmittel)\b', 'Lebensmittel', priority=70),
            CategoryRule(r'\b(bäcker|bäckerei|backhaus)\b', 'Lebensmittel', priority=70),
            CategoryRule(r'\b(metzger|metzgerei|fleischer)\b', 'Lebensmittel', priority=70),
            
            # Gastronomie (bleibt bei Lebensmittel - ist korrekt)
            CategoryRule(r'\b(restaurant|pizza|burger|döner|sushi)\b', 'Lebensmittel', priority=60),
            CategoryRule(r'\b(café|coffee|starbucks|kaffee)\b', 'Lebensmittel', priority=60),
            CategoryRule(r'\b(bar|kneipe|pub)\b', 'Lebensmittel', priority=60),
            
            # Gesundheit - KORRIGIERT
            CategoryRule(r'\b(apotheke|pharma)\b', 'Apotheke', priority=80),
            CategoryRule(r'\b(arzt|zahnarzt)\b', 'Arzt', priority=80),
            CategoryRule(r'\b(krankenhaus|klinik|notaufnahme)\b', 'Krankenhaus', priority=80),
            CategoryRule(r'\b(krankenversicherung|krankenkasse|gesundheitskasse)\b', 'Krankenversicherung', priority=85),
            
            # Versicherungen (spezifisch) - KORRIGIERT
            CategoryRule(r'\b(kfz.*versicherung|autoversicherung)\b', 'KFZ-Versicherung', priority=85),
            CategoryRule(r'\b(haftpflicht.*versicherung|haftpflicht)\b', 'Haftpflicht', priority=85),
            CategoryRule(r'\b(hausrat.*versicherung|hausrat)\b', 'Hausrat', priority=85),
            CategoryRule(r'\b(rechtsschutz|berufsunfähigkeit)\b', 'Versicherungen', priority=75),
            CategoryRule(r'\b(versicherung|insurance)\b', 'Versicherungen', priority=60),
            
            # Vermietung Ausgaben (Pacht, Objektkosten)
            CategoryRule(r'\b(pacht|pachtzins|verpachtung.*zahlung)\b', 'Vermietung Pacht', priority=85),
            CategoryRule(r'\b(sonnenberg.*kosten|sonnenberg.*reparatur|grundsteuer.*sonnenberg)\b', 'Vermietung Sonnenberg', priority=85),
            CategoryRule(r'\b(neuhof.*kosten|neuhof.*reparatur|zum neuhof.*reparatur|grundsteuer.*neuhof)\b', 'Vermietung Zum Neuhof', priority=85),
            CategoryRule(r'\b(weinberg.*kosten|weinberg.*steuer|weinberg.*pacht|grundsteuer.*weinberg)\b', 'Vermietung Weinbergsgelände', priority=85),
            
            # Online-Käufe - KORRIGIERT
            CategoryRule(r'\b(amazon|ebay)\b', 'Online Shopping', priority=70),
            CategoryRule(r'\b(paypal)\b', 'Online Shopping', priority=60),
            
            # Abonnements & Entertainment - KORRIGIERT
            CategoryRule(r'\b(netflix|spotify|youtube.*premium|disney\+|prime.*video)\b', 'Entertainment', priority=80),
            CategoryRule(r'\b(abo|abonnement|subscription)\b', 'Entertainment', priority=60),
        ]
    
    def categorize_transaction(self, transaction: Dict) -> Optional[int]:
        """
        Kategorisiert eine einzelne Transaktion
        
        Args:
            transaction: Dict mit 'description' und 'amount'
        
        Returns:
            category_id oder None
        """
        description = transaction.get('description', '')
        amount = transaction.get('amount', 0)
        
        if not description:
            return None
        
        # Regel-basierte Kategorisierung
        for rule in self.rules:
            if rule.matches(description):
                category_name_lower = rule.category_name.lower()
                
                if category_name_lower in self.category_cache:
                    category_id = self.category_cache[category_name_lower]
                    logger.debug(f"✓ Regel-Match: '{description[:50]}' → {rule.category_name}")
                    return category_id
        
        logger.debug(f"⚠ Keine Regel gefunden für: '{description[:50]}'")
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
            conn = get_db_connection()
            cursor = conn.cursor()
            ph = get_db_placeholder()
            
            # Transaktionen laden
            if force_recategorize:
                cursor.execute("SELECT id, description, amount FROM transactions")
            else:
                cursor.execute("SELECT id, description, amount FROM transactions WHERE category_id IS NULL")
            
            transactions = cursor.fetchall()
            total_count = len(transactions)
            
            if total_count == 0:
                logger.info("✅ Keine unkategorisierten Transaktionen gefunden")
                conn.close()
                return 0, 0
            
            logger.info(f"📊 {total_count} Transaktionen zu kategorisieren")
            
            categorized_count = 0
            for trans_id, description, amount in transactions:
                category_id = self.categorize_transaction({
                    'description': description,
                    'amount': amount
                })
                
                if category_id:
                    cursor.execute(
                        f"UPDATE transactions SET category_id = {ph} WHERE id = {ph}",
                        (category_id, trans_id)
                    )
                    categorized_count += 1
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ {categorized_count}/{total_count} Transaktionen kategorisiert")
            return categorized_count, total_count
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Kategorisierung: {e}")
            return 0, 0


def main():
    """Hauptfunktion"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Transaktionen kategorisieren')
    parser.add_argument('--force', action='store_true', 
                       help='Auch bereits kategorisierte Transaktionen neu zuordnen')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Detaillierte Debug-Ausgabe')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    categorizer = Categorizer()
    categorized, total = categorizer.categorize_all(force_recategorize=args.force)
    
    if total > 0:
        percentage = (categorized / total) * 100
        logger.info(f"📈 Erfolgsrate: {percentage:.1f}%")


if __name__ == "__main__":
    main()
