# Fix: Kategorisierungs-Bug behoben

## Problem

Schwerwiegender Bug in `scripts/categorize.py` (Zeilen 139-152):
**Alle** Gesundheits-, Versicherungs-, Online-Shopping- und Entertainment-Transaktionen wurden fälschlicherweise als `Lebensmittel` kategorisiert.

### Betroffene Kategorien

- ❌ **Gesundheit:** Apotheke, Arzt, Krankenhaus → waren als `Lebensmittel` definiert
- ❌ **Versicherungen:** Alle Versicherungen → waren als `Lebensmittel` definiert
- ❌ **Online Shopping:** Amazon, eBay, PayPal → waren als `Lebensmittel` definiert
- ❌ **Entertainment:** Netflix, Spotify, YouTube → waren als `Lebensmittel` definiert

## Lösung

### 1. Kategorisierungsregeln korrigiert (`scripts/categorize.py`)

**Vorher:**
```python
# Gesundheit
CategoryRule(r'\b(apotheke|pharma)\b', 'Lebensmittel', priority=70),  # ❌ FALSCH
CategoryRule(r'\b(amazon|ebay|paypal)\b', 'Lebensmittel', priority=60),  # ❌ FALSCH
CategoryRule(r'\b(netflix|spotify)\b', 'Lebensmittel', priority=70),  # ❌ FALSCH
```

**Nachher:**
```python
# Gesundheit - KORRIGIERT
CategoryRule(r'\b(apotheke|pharma)\b', 'Apotheke', priority=80),
CategoryRule(r'\b(arzt|zahnarzt)\b', 'Arzt', priority=80),
CategoryRule(r'\b(krankenhaus|klinik)\b', 'Krankenhaus', priority=80),
CategoryRule(r'\b(krankenversicherung)\b', 'Krankenversicherung', priority=85),

# Versicherungen - KORRIGIERT
CategoryRule(r'\b(kfz.*versicherung)\b', 'KFZ-Versicherung', priority=85),
CategoryRule(r'\b(haftpflicht)\b', 'Haftpflicht', priority=85),
CategoryRule(r'\b(hausrat)\b', 'Hausrat', priority=85),

# Online Shopping - KORRIGIERT
CategoryRule(r'\b(amazon|ebay)\b', 'Online Shopping', priority=70),
CategoryRule(r'\b(paypal)\b', 'Online Shopping', priority=60),

# Entertainment - KORRIGIERT
CategoryRule(r'\b(netflix|spotify|youtube.*premium)\b', 'Entertainment', priority=80),
```

### 2. Kategorien-Struktur verbessert (`config/categories.yaml`)

```yaml
expenses:
  # Gesundheit (hierarchisch)
  - name: "Gesundheit"
    children:
      - "Apotheke"
      - "Arzt"
      - "Krankenhaus"
  
  # Versicherungen (hierarchisch)
  - name: "Versicherungen"
    children:
      - "Krankenversicherung"
      - "Haftpflicht"
      - "Hausrat"
      - "KFZ-Versicherung"
  
  # Shopping & Entertainment
  - "Online Shopping"
  - "Entertainment"
```

### 3. Weitere Verbesserungen

- **Mobilität:** KFZ-Versicherung aus Mobilität entfernt (jetzt unter Versicherungen)
- **Öffentliche Verkehrsmittel:** Eigene Unterkategorie
- **Prioritäten:** Erhöht für spezifische Regeln (80-85) vs. generische (60)

## Verifikation

**Test-Script:** `scripts/test_categorization.py`

```bash
cd /home/stefan/Workspace/Finanzen
python3 scripts/test_categorization.py
```

**Ergebnis:**
```
✅ Keine kritischen Fehler (falsche Lebensmittel-Kategorisierung)
```

### Beispiel-Matches (korrekt):

| Transaktion | Alte Kategorie | Neue Kategorie |
|------------|----------------|----------------|
| Apotheke am Markt | ❌ Lebensmittel | ✅ Apotheke |
| Amazon Bestellung | ❌ Lebensmittel | ✅ Online Shopping |
| Netflix Abo | ❌ Lebensmittel | ✅ Entertainment |
| Krankenversicherung | ❌ Lebensmittel | ✅ Krankenversicherung |
| KFZ-Versicherung | ❌ Lebensmittel | ✅ KFZ-Versicherung |

## Auswirkungen

### Für bestehende Transaktionen

**WICHTIG:** Nach dem Update müssen bestehende Transaktionen neu kategorisiert werden:

```bash
# In Docker-Container:
docker compose exec app python3 scripts/categorize.py --force

# Oder lokal:
python3 scripts/categorize.py --force
```

Die `--force` Option kategorisiert **alle** Transaktionen neu (auch bereits kategorisierte).

### Für neue Transaktionen

Alle neuen Transaktionen werden automatisch korrekt kategorisiert.

## Betroffene Dateien

- ✅ `scripts/categorize.py` - Regeln korrigiert (Zeilen 134-152)
- ✅ `config/categories.yaml` - Struktur verbessert
- ✅ `scripts/test_categorization.py` - Test-Script erstellt

## Status

🎉 **BEHOBEN** - Alle Kategorien werden nun korrekt zugeordnet.

---

**Erstellt:** 2026-02-27  
**Fix-Version:** 2.0.1
