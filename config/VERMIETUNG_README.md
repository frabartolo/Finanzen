# Vermietung und Verpachtung – Kategorien

## Hierarchie in der Datenbank

**Einnahmen (Vermietung Einnahmen)**  
→ Miete Sonnenberg | Miete Neuhof | Miete Weinbergsgelände  

**Ausgaben (Vermietung Ausgaben)**  
→ Vermietung Pacht | Vermietung Sonnenberg | Vermietung Zum Neuhof | Vermietung Weinbergsgelände  

## Anpassung

- **Neue Kategorien in DB:** Nach Änderung an `categories.yaml` fehlende Kategorien nachziehen:  
  `docker compose exec app python3 scripts/setup_db.py --categories-only`  
  (Volles Setup inkl. Schema: `scripts/setup_db.py` ohne Option.)

- **Automatische Kategorisierung (neu):** Läuft wie bisher über `categorize.py` (inkl. Vermietungs-Regeln).

- **Nachkategorisierung / Analyse:** Im App-Container ausführen (Datenbankzugriff):  
  `docker compose exec app python3 scripts/categorize_vermietung.py`  
  Nutzt `config/vermietung_rules.yaml`. Mit `--dry-run` nur anzeigen, mit `--force` auch bereits kategorisierte Transaktionen prüfen.

- **Mieter zu Objekten:** In `vermietung_rules.yaml` und in `scripts/categorize.py` sind Ameixa, Juros, Jung aktuell **Sonnenberg** zugeordnet. Wenn ein Mieter zu **Zum Neuhof** gehört, die entsprechende Regel auf `Miete Neuhof` umstellen.
