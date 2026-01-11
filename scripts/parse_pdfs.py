import pdfplumber
import re
import sqlite3
from pathlib import Path

PDF_DIR = Path("data/inbox")

def parse_pdf(path):
    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages)
    # Beispiel: Betrag extrahieren
    amount = re.search(r"Betrag\s+([\d,]+)", text)
    return {
        "raw_text": text,
        "amount": float(amount.group(1).replace(",", ".")) if amount else None
    }

def store(data):
    conn = sqlite3.connect("data/db/finance.db")
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO documents (raw_text, amount)
        VALUES (?, ?)
    """, (data["raw_text"], data["amount"]))
    conn.commit()

def main():
    for pdf in PDF_DIR.glob("*.pdf"):
        data = parse_pdf(pdf)
        store(data)
        pdf.rename(Path("data/processed") / pdf.name)

if __name__ == "__main__":
    main()