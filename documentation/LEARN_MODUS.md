# Interaktiver Lernmodus

Wenn PDF-Erkennung oder Kategorisierung nicht passt, kannst du Buchungen **manuell prüfen** und das System **Regeln beibringen**.

## Voraussetzung

TTY (interaktive Eingabe):

```bash
cd /pfad/zum/Finanzen
docker compose exec -it app python3 scripts/learn_interactive.py --help
```

## 1. PDF prüfen und korrigieren

```bash
docker compose exec -it app python3 scripts/learn_interactive.py pdf data/inbox/kontoauszug.pdf
```

- Zeigt erkannte Buchungen (pdftotext → pdfplumber → Parser)
- `e 3` – Buchung 3 bearbeiten (Datum, Betrag, Text)
- `d 2` – falsche Buchung entfernen
- `a` – Buchung manuell hinzufügen
- `t` – Rohtext ansehen (hilft bei Parser-Problemen)
- `s` – korrigierte Liste in die Datenbank schreiben
- `m` dann `s` – nach dem Speichern PDF nach `data/processed/` verschieben
- `q` – beenden

## 2. Kategorien zuordnen und Regeln lernen

```bash
docker compose exec -it app python3 scripts/learn_interactive.py category --limit 30
```

- Zeigt unkategorisierte Transaktionen
- Vorschlag aus bestehenden Regeln (falls vorhanden)
- Kategorie per **Name** oder **Nummer** aus `?` (Liste)
- Nach Zuordnung: optional **Regel lernen** → landet in `config/categorization_rules_learned.yaml`
- `categorize.py` nutzt Standard- + **gelernte** Regeln automatisch

Regel-Datei bearbeiten oder ins Repo committen, wenn du sie dauerhaft behalten willst.

## 3. Ergänzend (ohne TTY)

```bash
# Stichprobe unkategorisierter Texte
docker compose exec app python3 scripts/categorize.py --peek 30

# Regel-Vorschläge aus bereits kategorisierten Buchungen
docker compose exec app python3 scripts/suggest_rules_from_labels.py
```

## Ablauf-Empfehlung

1. PDF mit **learn_interactive pdf** prüfen und speichern  
2. **learn_interactive category** für Zuordnung + Regeln  
3. `docker compose exec app python3 scripts/categorize.py` für den Rest
