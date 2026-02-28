#!/usr/bin/env python3
"""
PDF-Kontoauszüge parsen und in Datenbank speichern
Unterstützt rekursive Verarbeitung von Verzeichnisstrukturen
"""

import sys
from pathlib import Path
import pdfplumber
import re
import logging
from datetime import datetime
import shutil

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


def extract_metadata_from_path(pdf_path, inbox_dir):
    """
    Extrahiert Metadaten aus dem Verzeichnispfad
    z.B. data/inbox/2024/01-Januar/Postbank/kontoauszug.pdf
    """
    relative_path = pdf_path.relative_to(inbox_dir)
    parts = relative_path.parts[:-1]  # Ohne Dateiname
    
    metadata = {
        'year': None,
        'month': None,
        'bank': None,
        'path_parts': parts
    }
    
    for part in parts:
        # Jahr erkennen (4 Ziffern)
        if re.match(r'^\d{4}$', part):
            metadata['year'] = int(part)
        
        # Monat erkennen (01-12 oder Monatsname)
        month_match = re.match(r'^(\d{2})', part)
        if month_match:
            metadata['month'] = int(month_match.group(1))
        
        # Bank erkennen (bekannte Banknamen)
        known_banks = ['postbank', 'sparkasse', 'volksbank', 'commerzbank', 'deutsche bank', 'ing']
        if any(bank in part.lower() for bank in known_banks):
            metadata['bank'] = part
    
    return metadata


def parse_ing_transaction(text_block):
    """
    Parser für ING-DiBa Kontoauszüge
    Format: Datum, Buchungstext, Betrag (oft mehrere Zeilen pro Transaktion)
    """
    transactions = []
    
    # ING Format: Datum am Anfang, dann Beschreibung über mehrere Zeilen, Betrag am Ende
    # Beispiel:
    # 01.01.2024
    # REWE Sagt Danke
    # Kartenzahlung
    # -50,00
    
    pattern = r'(\d{2}\.\d{2}\.\d{4})\s*\n(.+?)\n\s*([-]?\d+\.\d{3},\d{2}|[-]?\d+,\d{2})\s*[+-]?'
    matches = re.finditer(pattern, text_block, re.MULTILINE | re.DOTALL)
    
    for match in matches:
        date_str = match.group(1)
        description = match.group(2).strip().replace('\n', ' ')
        amount_str = match.group(3).replace('.', '').replace(',', '.')
        
        try:
            transactions.append({
                'date': datetime.strptime(date_str, '%d.%m.%Y').date(),
                'amount': float(amount_str),
                'description': description,
                'bank': 'ING-DiBa'
            })
        except (ValueError, AttributeError) as e:
            logger.debug(f"ING-Parser: Konnte Zeile nicht parsen: {e}")
            continue
    
    return transactions


def parse_postbank_transaction(text_block):
    """
    Parser für Postbank Kontoauszüge
    Format: Oft tabellarisch mit Buchungstag, Wertstellung, Vorgang, Betrag
    """
    transactions = []
    
    # Postbank Format 1: DD.MM. Beschreibung Betrag
    # Beispiel: 01.01. Gehalt 2.500,00+
    pattern1 = r'(\d{2}\.\d{2}\.)\s+(.+?)\s+(\d+[\.,]\d{2,3}[\.,]\d{2})\s*([+-])'
    
    # Postbank Format 2: DD.MM.YYYY vollständig
    # Beispiel: 01.01.2024 REWE -50,00
    pattern2 = r'(\d{2}\.\d{2}\.\d{4})\s+(.+?)\s+([-]?\d+[\.,]\d{3}[\.,]\d{2}|[-]?\d+[\.,]\d{2})'
    
    for line in text_block.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Versuche Format 1
        match1 = re.search(pattern1, line)
        if match1:
            date_str, description, amount_str, sign = match1.groups()
            # Jahr ergänzen (aktuelles Jahr annehmen)
            current_year = datetime.now().year
            date_str = f"{date_str}{current_year}"
            amount_str = amount_str.replace('.', '').replace(',', '.')
            if sign == '-':
                amount_str = '-' + amount_str
            
            try:
                transactions.append({
                    'date': datetime.strptime(date_str, '%d.%m.%Y').date(),
                    'amount': float(amount_str),
                    'description': description.strip(),
                    'bank': 'Postbank'
                })
                continue
            except (ValueError, AttributeError):
                pass
        
        # Versuche Format 2
        match2 = re.search(pattern2, line)
        if match2:
            date_str, description, amount_str = match2.groups()
            amount_str = amount_str.replace('.', '').replace(',', '.')
            
            try:
                transactions.append({
                    'date': datetime.strptime(date_str, '%d.%m.%Y').date(),
                    'amount': float(amount_str),
                    'description': description.strip(),
                    'bank': 'Postbank'
                })
            except (ValueError, AttributeError) as e:
                logger.debug(f"Postbank-Parser: Konnte Zeile nicht parsen: {e}")
                continue
    
    return transactions


def parse_generic_transaction(line):
    """
    Generischer Parser für verschiedene Formate (Fallback)
    """
    # Format 1: DD.MM.YYYY Betrag Beschreibung
    pattern1 = r'(\d{2}\.\d{2}\.\d{4})\s+([-+]?\d+[.,]\d{2})\s+(.+)'
    match1 = re.match(pattern1, line)
    if match1:
        date_str, amount_str, description = match1.groups()
        return {
            'date': datetime.strptime(date_str, '%d.%m.%Y').date(),
            'amount': float(amount_str.replace(',', '.').replace('+', '')),
            'description': description.strip()
        }
    
    # Format 2: DD.MM.YY Beschreibung Betrag
    pattern2 = r'(\d{2}\.\d{2}\.\d{2,4})\s+(.+?)\s+([-+]?\d+[.,]\d{2})$'
    match2 = re.search(pattern2, line)
    if match2:
        date_str, description, amount_str = match2.groups()
        # Jahr ggf. ergänzen
        if len(date_str.split('.')[-1]) == 2:
            year = int(date_str.split('.')[-1])
            year = 2000 + year if year < 50 else 1900 + year
            date_str = f"{date_str[:-2]}{year}"
        return {
            'date': datetime.strptime(date_str, '%d.%m.%Y').date(),
            'amount': float(amount_str.replace(',', '.').replace('+', '')),
            'description': description.strip()
        }
    
    return None


def detect_bank_from_text(text):
    """Erkennt die Bank anhand des PDF-Textes"""
    text_lower = text.lower()
    
    if 'ing-diba' in text_lower or 'ing diba' in text_lower or 'www.ing.de' in text_lower:
        return 'ING-DiBa'
    elif 'postbank' in text_lower:
        return 'Postbank'
    
    return None


def parse_pdf(path, metadata=None):
    """PDF-Datei parsen und Transaktionsdaten extrahieren"""
    logger.info(f"📄 Parse PDF: {path.name}")
    
    try:
        with pdfplumber.open(path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        
        # Bank automatisch erkennen
        detected_bank = detect_bank_from_text(text)
        if detected_bank:
            logger.info(f"   🏦 Bank erkannt: {detected_bank}")
            if metadata:
                metadata['detected_bank'] = detected_bank
        
        transactions = []
        
        # Bankspezifische Parser verwenden
        if detected_bank == 'ING-DiBa':
            transactions = parse_ing_transaction(text)
        elif detected_bank == 'Postbank':
            transactions = parse_postbank_transaction(text)
        
        # Fallback: Generischer Parser (zeilenweise)
        if not transactions:
            logger.info("   ℹ️ Verwende generischen Parser")
            for line in text.split('\n'):
                transaction = parse_generic_transaction(line)
                if transaction:
                    transactions.append(transaction)
        
        # Fallback: Wenn keine strukturierten Transaktionen gefunden wurden
        if not transactions:
            logger.warning(f"⚠️ Keine Transaktionen in {path.name} gefunden, speichere als Dokument")
            amount_match = re.search(r"Betrag\s+([-+]?\d+[.,]\d{2})", text)
            return {
                "raw_text": text,
                "transactions": [],
                "amount": float(amount_match.group(1).replace(',', '.')) if amount_match else None,
                "metadata": metadata,
                "bank": detected_bank
            }
        
        logger.info(f"✓ {len(transactions)} Transaktion(en) gefunden")
        return {
            "raw_text": text,
            "transactions": transactions,
            "metadata": metadata,
            "bank": detected_bank
        }
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Parsen von {path.name}: {e}")
        return None


def get_account_id_by_bank(bank_name):
    """Ermittelt die account_id basierend auf dem Banknamen"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        ph = get_db_placeholder()
        
        # Suche Account anhand des Banknamens
        cursor.execute(f"SELECT id FROM accounts WHERE bank LIKE {ph} LIMIT 1", (f"%{bank_name}%",))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0]
        else:
            logger.warning(f"⚠️ Kein Account für Bank '{bank_name}' gefunden, verwende Standard-Account")
            return 1
            
    except Exception as e:
        logger.error(f"❌ Fehler beim Abrufen der Account-ID: {e}")
        return 1


def store(data, account_id=None):
    """Geparste Daten in Datenbank speichern"""
    if not data:
        return False
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        ph = get_db_placeholder()
        
        # Account-ID bestimmen
        if account_id is None:
            # Versuche aus erkannter Bank zu ermitteln
            if data.get('bank'):
                account_id = get_account_id_by_bank(data['bank'])
            else:
                account_id = 1  # Fallback
        
        stored_count = 0
        
        # Transaktionen speichern
        if data.get('transactions'):
            for trans in data['transactions']:
                # Prüfe ob Transaktion bereits existiert (Duplikate vermeiden)
                cursor.execute(
                    f"""SELECT COUNT(*) FROM transactions 
                        WHERE account_id = {ph} AND date = {ph} 
                        AND amount = {ph} AND description = {ph}""",
                    (account_id, trans['date'], trans['amount'], trans['description'])
                )
                if cursor.fetchone()[0] > 0:
                    logger.debug(f"   ⏭️ Duplikat übersprungen: {trans['description'][:30]}...")
                    continue
                
                # Neue Transaktion einfügen
                cursor.execute(
                    f"""INSERT INTO transactions 
                        (account_id, date, amount, description, source) 
                        VALUES ({ph}, {ph}, {ph}, {ph}, {ph})""",
                    (account_id, trans['date'], trans['amount'], 
                     trans['description'], 'pdf')
                )
                stored_count += 1
        else:
            # Fallback: Als Dokument speichern
            cursor.execute(
                f"INSERT INTO documents (raw_text, amount) VALUES ({ph}, {ph})",
                (data["raw_text"], data.get("amount"))
            )
            stored_count += 1
        
        conn.commit()
        conn.close()
        
        if stored_count > 0:
            logger.info(f"💾 {stored_count} Datensatz/Datensätze gespeichert")
        return True
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Speichern: {e}")
        if conn:
            conn.rollback()
        return False


def find_all_pdfs(directory):
    """Findet rekursiv alle PDF-Dateien in einem Verzeichnis"""
    pdf_files = []
    for path in Path(directory).rglob('*.pdf'):
        if path.is_file():
            pdf_files.append(path)
    return sorted(pdf_files)


def move_with_structure(source, inbox_dir, processed_dir):
    """
    Verschiebt Datei unter Beibehaltung der Verzeichnisstruktur
    z.B. inbox/2024/01/file.pdf -> processed/2024/01/file.pdf
    """
    relative_path = source.relative_to(inbox_dir)
    target = processed_dir / relative_path
    
    # Zielverzeichnis erstellen
    target.parent.mkdir(parents=True, exist_ok=True)
    
    # Datei verschieben
    shutil.move(str(source), str(target))
    logger.debug(f"→ Verschoben nach: {relative_path}")


def main():
    """Alle PDFs im Inbox-Ordner rekursiv verarbeiten"""
    logger.info("🚀 Starte rekursive PDF-Verarbeitung...")
    
    ensure_dir(PDF_DIR)
    ensure_dir(PROCESSED_DIR)
    
    # Rekursiv alle PDFs finden
    pdf_files = find_all_pdfs(PDF_DIR)
    
    if not pdf_files:
        logger.info("📭 Keine PDFs zum Verarbeiten gefunden")
        return
    
    logger.info(f"📊 {len(pdf_files)} PDF(s) in Verzeichnisstruktur gefunden")
    
    # Zeige Verzeichnisstruktur
    unique_dirs = set(pdf.parent.relative_to(PDF_DIR) for pdf in pdf_files)
    if unique_dirs != {Path('.')}:
        logger.info(f"📁 Verzeichnisse: {len(unique_dirs)}")
        for dir_path in sorted(unique_dirs):
            if str(dir_path) != '.':
                count = sum(1 for pdf in pdf_files if pdf.parent.relative_to(PDF_DIR) == dir_path)
                logger.info(f"   ├─ {dir_path}: {count} PDF(s)")
    
    processed_count = 0
    error_count = 0
    
    for pdf in pdf_files:
        try:
            # Metadaten aus Pfad extrahieren
            metadata = extract_metadata_from_path(pdf, PDF_DIR)
            
            # PDF parsen
            data = parse_pdf(pdf, metadata)
            
            # In Datenbank speichern
            if data and store(data):
                # Nach erfolgreicher Verarbeitung verschieben (mit Struktur)
                move_with_structure(pdf, PDF_DIR, PROCESSED_DIR)
                processed_count += 1
                logger.info(f"✅ Verarbeitet: {pdf.relative_to(PDF_DIR)}")
            else:
                error_count += 1
                logger.error(f"❌ Fehler bei: {pdf.relative_to(PDF_DIR)}")
                
        except Exception as e:
            error_count += 1
            logger.error(f"❌ Unerwarteter Fehler bei {pdf.name}: {e}")
    
    logger.info("=" * 60)
    logger.info(f"✅ Erfolgreich verarbeitet: {processed_count}/{len(pdf_files)}")
    if error_count > 0:
        logger.warning(f"⚠️ Fehler: {error_count}/{len(pdf_files)}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()