#!/usr/bin/env python3
"""
PDF-Kontoauszüge parsen und in Datenbank speichern
Unterstützt rekursive Verarbeitung von Verzeichnisstrukturen
"""

import os
import sys
import json
import re
import logging
import shutil
from pathlib import Path
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# Pfad zum Projekt-Root hinzufügen
sys.path.insert(0, str(Path(__file__).parent.parent))

# OCR (optional) – Fallback bei kaputten Fonts
try:
    from pdf2image import convert_from_path
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

from scripts.utils import get_db_connection, get_db_placeholder, ensure_dir, load_config

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Absolute Pfade (cwd in Container: /app), verhindert Pfad-Probleme beim Verschieben
PDF_DIR = (Path(__file__).parent.parent / "data" / "inbox").resolve()
PROCESSED_DIR = (Path(__file__).parent.parent / "data" / "processed").resolve()
MAX_DESCRIPTION_LENGTH = 500  # Verhindert 27k-Zeichen-Fehler bei Parser-Pathern
OCR_DPI = 200  # DPI für PDF→Bild (höher = genauer, langsamer)


def _get_ollama_config() -> dict:
    """Ollama-Konfiguration aus settings laden."""
    try:
        cfg = load_config("settings")
        s = cfg.get("settings", cfg)
        return (s or cfg).get("ollama", {})
    except Exception:
        return {}


def _ollama_available() -> bool:
    o = _get_ollama_config()
    return bool(o.get("enabled")) and bool(o.get("host"))


def extract_with_ollama(text: str, bank_hint: str = None) -> list:
    """
    Sendet Text an Ollama-LLM und bittet um strukturierte Transaktions-Extraktion.
    Returns: Liste von {date, amount, description}
    """
    cfg = _get_ollama_config()
    if not cfg.get("enabled"):
        return []
    host = os.getenv("OLLAMA_HOST") or cfg.get("host", "")
    if not host:
        return []
    host = host.rstrip("/")
    model = cfg.get("model", "qwen2.5:7b")
    timeout = int(cfg.get("timeout", 60))
    prompt = f"""Extrahiere alle Bank-Transaktionen (Umsätze) aus dem folgenden Kontoauszug-Text.
Erkennbare Bank: {bank_hint or 'unbekannt'}

Antworte NUR mit einem JSON-Array, ein Objekt pro Transaktion:
[{{"date": "DD.MM.YYYY", "amount": Zahl (negativ für Abbuchung), "description": "Beschreibung"}}]

Beispiele:
- Einnahme 550,00 am 01.03.2023: {{"date": "01.03.2023", "amount": 550.00, "description": "SEPA Überweisung von ..."}}
- Ausgabe 28,80 am 09.03.2023: {{"date": "09.03.2023", "amount": -28.80, "description": "..."}}

Keine Transaktionen gefunden: []

Text:
---
{text[:8000]}
---"""
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
        response_text = data.get("response", "").strip()
        # JSON aus Antwort extrahieren (evtl. in Markdown-Codeblock)
        json_match = re.search(r"\[[\s\S]*\]", response_text)
        if not json_match:
            return []
        arr = json.loads(json_match.group(0))
        out = []
        for item in arr:
            if isinstance(item, dict) and "date" in item and "amount" in item:
                out.append({
                    "date": item["date"],
                    "amount": float(item["amount"]),
                    "description": str(item.get("description", ""))[:MAX_DESCRIPTION_LENGTH],
                })
        return out
    except (URLError, HTTPError, json.JSONDecodeError, ValueError) as e:
        logger.warning(f"   Ollama-Fallback fehlgeschlagen: {e}")
        return []


def extract_text_with_ocr(pdf_path: Path) -> str:
    """
    PDF via Tesseract OCR lesen (Fallback bei kaputten Fonts).
    Rendert jede Seite als Bild, führt OCR aus.
    """
    if not OCR_AVAILABLE:
        return ""
    try:
        images = convert_from_path(str(pdf_path), dpi=OCR_DPI, fmt="png")
        texts = []
        for img in images:
            # deu+eng für Kontoauszüge (Deutsch + engl. Fachbegriffe)
            text = pytesseract.image_to_string(img, lang="deu+eng")
            texts.append(text or "")
        return "\n".join(texts)
    except Exception as e:
        logger.warning(f"   OCR fehlgeschlagen: {e}")
        return ""


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
    Unterstützt:
    - Tabellenformat: eine Zeile = Datum [Valuta] Beschreibung Betrag
    - Blockformat: Datum, mehrzeilige Beschreibung, Betrag
    """
    transactions = []
    seen = set()  # (date, amount, desc) für Duplikat-Vermeidung

    def add_tx(date_str, desc, amount_str):
        key = (date_str, amount_str, desc[:80])
        if key in seen:
            return
        seen.add(key)
        try:
            am = float(amount_str.replace('.', '').replace(',', '.'))
            transactions.append({
                'date': datetime.strptime(date_str, '%d.%m.%Y').date(),
                'amount': am,
                'description': desc.strip()[:MAX_DESCRIPTION_LENGTH],
                'bank': 'ING-DiBa'
            })
        except (ValueError, AttributeError):
            pass

    # ING Tabellenformat: Zeile = "DD.MM.YYYY [DD.MM.YYYY] Beschreibung  Betrag"
    # z.B. "06.03.2025  06.03.2025  Gutschrift/Dauerauftrag Stefan Wilhelm  2.000,00"
    # Betrag am Zeilenende, optional +/-
    table_pattern = (
        r'(\d{2}\.\d{2}\.\d{4})\s+'
        r'(?:\d{2}\.\d{2}\.\d{4}\s+)?'
        r'(.+?)\s+'
        r'([-]?\d{1,3}(?:\.\d{3})*,\d{2}|[-]?\d+,\d{2})\s*[+-]?\s*$'
    )
    for line in text_block.split('\n'):
        m = re.search(table_pattern, line, re.MULTILINE)
        if m:
            add_tx(m.group(1), m.group(2), m.group(3))

    # ING Blockformat: Datum, mehrzeilige Beschreibung, Betrag
    block_pattern = (
        r'(\d{2}\.\d{2}\.\d{4})\s*\n([\s\S]{1,500}?)\n\s*'
        r'([-]?\d+\.\d{3},\d{2}|[-]?\d+,\d{2})\s*[+-]?'
    )
    for match in re.finditer(block_pattern, text_block, re.MULTILINE):
        desc = match.group(2).strip().replace('\n', ' ')
        add_tx(match.group(1), desc, match.group(3))

    return transactions


NOISE_DESC = frozenset({'bis', 'von', 'valuta', 'buchung', 'vorgang', 'verwendungszweck', 'kundenreferenz', 'referenz'})


def _parse_postbank_blocks(text_block):
    """
    Postbank mehrzeilig: SEPA Überweisung von <Name>, Verwendungszweck, Betrag.
    Block = Datumszeile [Valuta] + Vorgang (mehrere Zeilen) + Betrag am Ende.
    Betrag auch am Ende der letzten Beschreibungszeile möglich: "RINP Dauerauftrag  + 550,00"
    """
    out = []
    # Datum, Beschreibung (inkl. Newlines), Betrag (+/- optional, auf gleicher oder nächster Zeile)
    pat = (
        r'(\d{2}\.\d{2}\.\d{4})\s*(?:\d{2}\.\d{2}\.\d{4}\s*\n?)?'
        r'([\s\S]{1,500}?)\s*'
        r'([+-]?\s*\d{1,3}(?:\.\d{3})*,\d{2})\s*'
    )
    for m in re.finditer(pat, text_block, re.MULTILINE):
        date_str, desc, amount_str = m.group(1), m.group(2).strip(), m.group(3)
        desc_clean = desc.replace('\n', ' ').strip()[:MAX_DESCRIPTION_LENGTH]
        if not desc_clean or desc_clean.lower() in NOISE_DESC or len(desc_clean) < 4:
            continue
        try:
            am_str_clean = amount_str.replace(' ', '').replace('.', '').replace(',', '.')
            am = float(am_str_clean)
            out.append({
                'date': datetime.strptime(date_str, '%d.%m.%Y').date(),
                'amount': am,
                'description': desc_clean,
                'bank': 'Postbank'
            })
        except (ValueError, AttributeError):
            pass
    return out


def _extract_statement_year(text_block: str) -> int:
    """Jahr aus Kontoauszug-Header extrahieren (z.B. 'vom 06.03.2015 bis')"""
    m = re.search(r'(?:vom|bis)\s+\d{2}\.\d{2}\.(\d{4})', text_block)
    return int(m.group(1)) if m else datetime.now().year


def parse_postbank_transaction(text_block):
    """
    Parser für Postbank Kontoauszüge
    Unterstützt: Tabellenformat (Buchung, Wert, Vorgang, Soll/Haben), Blockformat
    """
    transactions = []
    block_result = _parse_postbank_blocks(text_block)
    if block_result:
        return block_result

    statement_year = _extract_statement_year(text_block)

    # Postbank Tabellenformat: DD.MM. [DD.MM.] Vorgang  +Betrag / -Betrag
    # z.B. "06.03. 06.03. Gutschr.SEPA Stefan Wilhelm ... + 740,63" oder "... - 28,80"
    table_pattern = (
        r'(\d{2}\.\d{2}\.)\s+(?:\d{2}\.\d{2}\.\s+)?'
        r'(.+?)\s+'
        r'([+-]?\s*\d{1,3}(?:\.\d{3})*,\d{2})\s*[+-]?\s*$'
    )
    for line in text_block.split('\n'):
        m = re.search(table_pattern, line.strip(), re.MULTILINE)
        if m:
            date_str = f"{m.group(1)}{statement_year}"
            desc = m.group(2).strip()[:MAX_DESCRIPTION_LENGTH]
            am_str = m.group(3).replace(' ', '').replace('.', '').replace(',', '.')
            if desc.lower() not in NOISE_DESC and len(desc) >= 4:
                try:
                    transactions.append({
                        'date': datetime.strptime(date_str, '%d.%m.%Y').date(),
                        'amount': float(am_str),
                        'description': desc,
                        'bank': 'Postbank'
                    })
                except (ValueError, AttributeError):
                    pass
            continue

    # Postbank Format 1: DD.MM. Beschreibung Betrag +/-
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
            desc = description.strip()[:MAX_DESCRIPTION_LENGTH]
            if desc.lower() in NOISE_DESC or len(desc) < 5:
                desc = "Unbekannter Vorgang (Postbank Import)"
            current_year = datetime.now().year
            date_str = f"{date_str}{current_year}"
            amount_str = amount_str.replace('.', '').replace(',', '.')
            if sign == '-':
                amount_str = '-' + amount_str
            try:
                transactions.append({
                    'date': datetime.strptime(date_str, '%d.%m.%Y').date(),
                    'amount': float(amount_str),
                    'description': desc,
                    'bank': 'Postbank'
                })
                continue
            except (ValueError, AttributeError):
                pass
        
        # Versuche Format 2
        match2 = re.search(pattern2, line)
        if match2:
            date_str, description, amount_str = match2.groups()
            desc = description.strip()[:MAX_DESCRIPTION_LENGTH]
            if desc.lower() in NOISE_DESC or (len(desc) < 5 and not desc.replace('.', '').replace(',', '').isdigit()):
                desc = "Unbekannter Vorgang (Postbank Import)"
            amount_str = amount_str.replace('.', '').replace(',', '.')
            try:
                transactions.append({
                    'date': datetime.strptime(date_str, '%d.%m.%Y').date(),
                    'amount': float(amount_str),
                    'description': desc,
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
            'description': (description.strip() or '')[:MAX_DESCRIPTION_LENGTH]
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
            'description': (description.strip() or '')[:MAX_DESCRIPTION_LENGTH]
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


def _parse_transactions_from_text(text: str, detected_bank: str) -> list:
    """Transaktionen aus Text extrahieren (ING, Postbank, generisch)."""
    transactions = []
    if detected_bank == 'ING-DiBa':
        transactions = parse_ing_transaction(text)
    elif detected_bank == 'Postbank':
        transactions = parse_postbank_transaction(text)
    if not transactions:
        for line in text.split('\n'):
            tx = parse_generic_transaction(line)
            if tx:
                transactions.append(tx)
    return transactions


def parse_pdf(path, metadata=None):
    """PDF-Datei parsen und Transaktionsdaten extrahieren"""
    logger.info(f"📄 Parse PDF: {path.name}")
    
    try:
        with pdfplumber.open(path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        
        detected_bank = detect_bank_from_text(text)
        if detected_bank:
            logger.info(f"   🏦 Bank erkannt: {detected_bank}")
            if metadata:
                metadata['detected_bank'] = detected_bank
        
        transactions = _parse_transactions_from_text(text, detected_bank)
        
        # OCR-Fallback: Text vorhanden, aber 0 Transaktionen (kaputte Fonts bei PDFs)
        if not transactions and len(text) > 150 and OCR_AVAILABLE:
            logger.info("   🔍 Versuche OCR (Tesseract) – Font-Extraktion lieferte keine Transaktionen")
            ocr_text = extract_text_with_ocr(path)
            if ocr_text:
                bank_from_ocr = detect_bank_from_text(ocr_text) or detected_bank
                transactions = _parse_transactions_from_text(ocr_text, bank_from_ocr)
                if transactions:
                    logger.info(f"   ✓ OCR erfolgreich: {len(transactions)} Transaktion(en)")
                    if bank_from_ocr:
                        detected_bank = bank_from_ocr
                        if metadata:
                            metadata['detected_bank'] = detected_bank
                    text = ocr_text

        # Ollama-Fallback: LLM extrahiert Transaktionen aus Text (nach Tesseract)
        if not transactions and len(text) > 100 and _ollama_available():
            logger.info("   🤖 Versuche Ollama-LLM – OCR/regex lieferte keine Transaktionen")
            raw_list = extract_with_ollama(text, detected_bank)
            for item in raw_list:
                try:
                    dt = datetime.strptime(item["date"], "%d.%m.%Y").date()
                    transactions.append({
                        "date": dt,
                        "amount": float(item["amount"]),
                        "description": (item.get("description") or "")[:MAX_DESCRIPTION_LENGTH],
                        "bank": detected_bank or "Postbank",
                    })
                except (ValueError, KeyError):
                    pass
            if transactions:
                logger.info(f"   ✓ Ollama erfolgreich: {len(transactions)} Transaktion(en)")
        
        # Fallback: Als Dokument speichern
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
                
                desc = (trans['description'] or '')[:MAX_DESCRIPTION_LENGTH]
                cursor.execute(
                    f"""INSERT INTO transactions 
                        (account_id, date, amount, description, source) 
                        VALUES ({ph}, {ph}, {ph}, {ph}, {ph})""",
                    (account_id, trans['date'], trans['amount'], desc, 'pdf')
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
    src = Path(source).resolve()
    inbox = Path(inbox_dir).resolve()
    proc = Path(processed_dir).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Datei nicht mehr vorhanden (evtl. bereits verschoben): {source}")
    relative_path = src.relative_to(inbox)
    target = proc / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(target))
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