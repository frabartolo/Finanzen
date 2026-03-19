# 📄 PDF-Import Anleitung

## 🎯 Überblick

Das `parse_pdfs.py` Script verarbeitet automatisch PDF-Kontoauszüge und importiert die Transaktionen in die Datenbank.

## ✨ Features

- ✅ **Rekursive Verzeichnissuche** - durchsucht alle Unterordner
- ✅ **Verzeichnisstruktur bleibt erhalten** - beim Verschieben nach `processed/`
- ✅ **Bankspezifische Parser** - optimiert für ING-DiBa und Postbank
- ✅ **Automatische Bank-Erkennung** - aus PDF-Inhalt
- ✅ **Duplikaterkennung** - verhindert doppelte Einträge
- ✅ **Metadaten-Extraktion** - Jahr, Monat, Bank aus Ordnernamen

## 📁 Verzeichnisstruktur

### Empfohlene Organisation:

```
data/inbox/
├── ING/
│   ├── 2024/
│   │   ├── 01-Januar/
│   │   │   └── kontoauszug_januar.pdf
│   │   └── 02-Februar/
│   │       └── kontoauszug_februar.pdf
│   └── 2025/
│       └── 01-Januar/
│           └── kontoauszug_januar.pdf
└── Postbank/
    ├── Girokonto/
    │   └── 2024/
    │       └── auszug_q1.pdf
    └── Tagesgeld/
        └── 2024/
            └── auszug_q1.pdf
```

**Wichtig:** Du kannst die Struktur beliebig organisieren - das Script findet alle PDFs automatisch!

## 🚀 Verwendung

### 1. PDFs ablegen

**Auf Windows:**
- Kopiere PDFs in: `C:\Users\stefa\Workspaces\Finanzen\data\inbox\`
- Oder nutze die SMB-Freigabe: `\\finanzen\finanzen-inbox`

**Beliebige Unterordner erstellen:**
```
data/inbox/2024/01-Januar/...
data/inbox/Postbank/Girokonto/...
data/inbox/ING/...
```

### 2. Script ausführen

```bash
# Im Docker-Container
docker compose exec app python3 scripts/parse_pdfs.py
```

### 3. Ergebnisse prüfen

Nach erfolgreicher Verarbeitung:
- PDFs sind verschoben nach: `data/processed/` (mit gleicher Struktur)
- Transaktionen in Datenbank importiert
- Sichtbar im Grafana-Dashboard

## 🏦 Unterstützte Banken

### ING-DiBa
- **Automatische Erkennung:** ✅
- **Parser:** Optimiert für ING-Format
- **Erkennungsmerkmale:** "ING-DiBa", "ING DiBa", "www.ing.de" im PDF

### Postbank
- **Automatische Erkennung:** ✅
- **Parser:** Optimiert für Postbank-Format
- **Erkennungsmerkmale:** "Postbank" im PDF

### Andere Banken
- **Fallback-Parser:** Generischer Parser für Standard-Formate
- **Format:** `DD.MM.YYYY Beschreibung Betrag`

## 📊 Beispiel-Output

```
🚀 Starte rekursive PDF-Verarbeitung...
📊 8 PDF(s) in Verzeichnisstruktur gefunden
📁 Verzeichnisse: 4
   ├─ ING/2024/01-Januar: 2 PDF(s)
   ├─ ING/2024/02-Februar: 1 PDF(s)
   ├─ Postbank/Girokonto/2024: 3 PDF(s)
   ├─ Postbank/Tagesgeld/2024: 2 PDF(s)

📄 Parse PDF: kontoauszug_januar.pdf
   🏦 Bank erkannt: ING-DiBa
✓ 45 Transaktion(en) gefunden
💾 45 Datensatz/Datensätze gespeichert
✅ Verarbeitet: ING/2024/01-Januar/kontoauszug_januar.pdf

📄 Parse PDF: auszug_q1.pdf
   🏦 Bank erkannt: Postbank
✓ 87 Transaktion(en) gefunden
💾 87 Datensatz/Datensätze gespeichert
   ⏭️ 3 Duplikate übersprungen
✅ Verarbeitet: Postbank/Girokonto/2024/auszug_q1.pdf

============================================================
✅ Erfolgreich verarbeitet: 8/8
============================================================
```

## 🔍 Erweiterte Funktionen

### Duplikaterkennung

Das Script prüft vor dem Import, ob eine Transaktion bereits existiert:
- Gleicher Account
- Gleiches Datum
- Gleicher Betrag
- Gleiche Beschreibung

→ Duplikate werden übersprungen

### Metadaten-Extraktion

Aus Ordnernamen werden automatisch extrahiert:
- **Jahr:** 4-stellige Zahlen (z.B. `2024`)
- **Monat:** Zahlen 01-12 (z.B. `01-Januar`, `02`)
- **Bank:** Bekannte Banknamen im Ordnernamen

### Account-Zuordnung

1. **Automatisch:** Bank wird aus PDF erkannt → passender Account aus DB
2. **Fallback:** Erster Account wird verwendet

## ⚠️ Troubleshooting

### Keine Transaktionen gefunden

**Symptom:** Script meldet "Keine Transaktionen gefunden"

**Lösung:**
1. Prüfe PDF-Format - ist es text-basiert? (kein gescanntes Bild)
2. Teste mit: `pdfplumber` - kann Text extrahiert werden?
3. Schicke mir ein Beispiel-PDF zur Format-Analyse

### Falsche Beträge

**Symptom:** Beträge werden falsch geparst

**Lösung:**
1. Prüfe Format im PDF: `1.234,56` vs `1,234.56`
2. Parser erwartet deutsches Format: `1.234,56`
3. Ggf. Parser anpassen in `parse_pdfs.py`

### Account nicht gefunden

**Symptom:** "Kein Account für Bank 'XYZ' gefunden"

**Lösung:**
1. Prüfe `config/accounts.yaml` - ist die Bank eingetragen?
2. Bank-Name muss im `bank:` Feld stehen
3. Script sucht mit `LIKE %Bankname%`

## 🔄 Automatisierung

### Cron-Job einrichten

PDFs automatisch alle 2 Stunden verarbeiten:

```bash
# In cron/parse-pdfs.cron
0 */2 * * * cd /app && python3 scripts/parse_pdfs.py >> /app/data/logs/parse_pdfs.log 2>&1
```

### Nach FinTS-Import

Nach automatischem FinTS-Import auch PDFs verarbeiten:

```bash
# Am Ende von fetch_fints.py
import subprocess
subprocess.run(['python3', 'scripts/parse_pdfs.py'])
```

## 📝 Nächste Schritte

1. ✅ PDFs in `data/inbox/` ablegen
2. ✅ Script ausführen
3. ✅ Ergebnis in Grafana prüfen
4. 🔄 Optional: Kategorisierung durchführen
   ```bash
   docker compose exec app python3 scripts/categorize.py
   ```

## 🆘 Support

Bei Problemen:
1. Logs prüfen: `data/logs/parse_pdfs.log`
2. Debug-Modus aktivieren in `parse_pdfs.py`: `level=logging.DEBUG`
3. Test-PDF bereitstellen für Format-Analyse
