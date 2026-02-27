#!/usr/bin/env python3
"""
PDF-Kontoauszüge parsen und in Datenbank speichern
"""

import sys
from pathlib import Path
import pdfplumber
import re
import logging

# Pfad zum Projekt-Root hinzufügen
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.utils import get_db_connection, get_db_placeholder, ensure_dir

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

PDF_DIR = Path("data/inbox")
PROCESSED_DIR = Path("data/processed")

def parse_pdf(path):
    """PDF-Datei parsen und Transaktionsdaten extrahieren"""
    logger.info(f"📄 Parse PDF: {path.name}")
    
    try:
        with pdfplumber.open(path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        
        # Beispiel: Betrag extrahieren
        amount = re.search(r"Betrag\s+([\d,]+)", text)
        
        return {
            "raw_text": text,
            "amount": float(amount.group(1).replace(",", ".")) if amount else None
        }
    except Exception as e:
        logger.error(f"❌ Fehler beim Parsen von {path.name}: {e}")
        return None

def store(data):
    """Geparste Daten in Datenbank speichern"""
    if not data:
        return False
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        ph = get_db_placeholder()
        
        cursor.execute(
            f"INSERT INTO documents (raw_text, amount) VALUES ({ph}, {ph})",
            (data["raw_text"], data["amount"])
        )
        conn.commit()
        conn.close()
        
        logger.info(f"💾 Daten in Datenbank gespeichert")
        return True
    except Exception as e:
        logger.error(f"❌ Fehler beim Speichern: {e}")
        return False

def main():
    """Alle PDFs im Inbox-Ordner verarbeiten"""
    logger.info("🚀 Starte PDF-Verarbeitung...")
    
    ensure_dir(PDF_DIR)
    ensure_dir(PROCESSED_DIR)
    
    pdf_files = list(PDF_DIR.glob("*.pdf"))
    
    if not pdf_files:
        logger.info("📭 Keine PDFs zum Verarbeiten gefunden")
        return
    
    logger.info(f"📊 {len(pdf_files)} PDF(s) gefunden")
    
    processed_count = 0
    for pdf in pdf_files:
        data = parse_pdf(pdf)
        if data and store(data):
            # Nach erfolgreicher Verarbeitung verschieben
            pdf.rename(PROCESSED_DIR / pdf.name)
            processed_count += 1
            logger.info(f"✅ Verarbeitet: {pdf.name}")
    
    logger.info(f"✅ {processed_count}/{len(pdf_files)} PDFs erfolgreich verarbeitet")

if __name__ == "__main__":
    main()