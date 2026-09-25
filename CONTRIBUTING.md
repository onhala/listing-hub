# 🤝 Příručka pro vývojáře a přispěvatele (Contributing Guide)

Vítejte v projektu **Listing Hub**! Tento dokument shrnuje pravidla pro vývoj, konvence kódu, proces tvorby větví, psaní testů a odesílání Pull Requestů.

---

## 🗺️ 1. Architektonická mapa projektu

Projekt je rozdělen do modulárních balíčků uvnitř [`listing_hub/`](listing_hub/):

```text
listing_hub/
├── core/            # Databáze (db.py), konfigurace (config.py), verze (version.py), kalendář
├── portals/         # Portálové adaptéry (Bazoš, Sbazar, Vinted, FB Marketplace, Aukro)
│   ├── base.py      # AbstractPortal - rozhraní pro všechny portály
│   ├── registry.py  # PortalRegistry - dynamický registr a detekce z URL
│   └── scrapers/    # 3úrovňový univerzální scraper zhlédnutí inzerátů
├── ai/              # Google Gemini Vision (vision.py), poradce cen (advisor.py), photo editor
├── agent/           # REST API (api.py), CLI (cli.py) a FastMCP server (mcp_server.py)
├── metrics/         # Prometheus OpenMetrics exporter (exporter.py)
└── export/          # Exportní moduly (OneDrive, Excel)
```

---

## ⚡ 2. Rychlý lokální setup

### Požadavky:
- Python 3.11 nebo novější
- Git

### Postup instalace:
```bash
# 1. Klonování repozitáře
git clone https://github.com/onhala/listing-hub.git
cd listing-hub

# 2. Vytvoření virtuálního prostředí
python3 -m venv .venv
source .venv/bin/activate  # macOS / Linux
# nebo: .venv\Scripts\activate  # Windows

# 3. Instalace závislostí
pip install -r requirements.txt

# 4. Instalace Playwright Chromium prohlížeče
playwright install chromium

# 5. Spuštění testů pro ověření setupu
pytest
```

---

## 🌿 3. Git Workflow & Konvence větví

Pro vývoj nových funkcí nebo oprav chyb vždy vytvářejte samostatné tematické větve z větve `main`:

### Názvy větví:
- `feature/<kratky-popis>` – pro nové funkce a portály (např. `feature/sbazar-sync`, `feature/dark-mode`)
- `fix/<kratky-popis>` – pro opravy chyb (např. `fix/sms-timeout`, `fix/bazos-category-parser`)
- `refactor/<kratky-popis>` – pro úpravy architektury a čištění kódu
- `docs/<kratky-popis>` – pro úpravy a doplnění dokumentace

---

## ✍️ 4. Formát commit zpráv (Conventional Commits)

Držíme standard **Conventional Commits** pro přehledný changelog a automatické verzování:

```text
<typ>(<volitelny-scope>): <strucny popis v pritomnem case>

[volitelne podrobnejsi body]
```

### Příklady typů:
- `feat`: nová funkcionalita (např. `feat(portals): add Vinted price update adapter`)
- `fix`: oprava chyby (např. `fix(bazos): resolve form reload on category switch`)
- `docs`: změna v dokumentaci (např. `docs(api): document search rank endpoint`)
- `test`: přidání nebo úprava unit testů (např. `test(scrapers): add test cases for JSON-LD`)
- `refactor`: změna kódu bez vlivu na chování (např. `refactor(db): extract connection pool helper`)
- `chore`: úpravy build skriptů, CI workflow nebo závislostí

---

## 🧱 5. Jak přidat nový inzertní portál

Díky modulární architektuře v `listing_hub.portals` je přidání nového portálu otázkou 3 jednoduchých kroků:

1. **Vytvoření adaptéru**: Vytvořte třídu dědící z `AbstractPortal` v novém balíčku, např. `listing_hub/portals/novy_portal/novy_portal.py`:
   ```python
   from listing_hub.portals.base import AbstractPortal
   from typing import List, Dict, Any, Optional

   class NovyPortal(AbstractPortal):
       @property
       def name(self) -> str:
           return "novy_portal"

       @property
       def display_name(self) -> str:
           return "NovýPortál.cz"

       @property
       def supported_domains(self) -> List[str]:
           return ["novyportal.cz", "www.novyportal.cz"]

       def extract_item_id_from_url(self, url: str) -> Optional[str]:
           # Logika extrakce ID z URL
           ...
   ```
2. **Registrace v `PortalRegistry`**: V [`listing_hub/portals/registry.py`](listing_hub/portals/registry.py) importujte a zaregistrujte instanci:
   ```python
   self.register(NovyPortal())
   ```
3. **Přidání unit testů**: Vytvořte testy v `tests/unit/test_portals_registry.py` ověřující validaci URL, extrakci ID a chování metod.

---

## 🧪 6. Testování a Kontrola kvality

Všechny změny musí být pokryty unit testy. Před odesláním PR ověřte, že celá testovací sada prochází:

```bash
# Spuštění celé sady testů
pytest

# Detailní výpis s tracebackem
pytest -v --tb=short

# Spuštění testů pro portály
pytest tests/unit/test_portals_registry.py tests/unit/test_universal_scraper_extended.py
```

---

## 🔒 7. Bezpečnostní zásady & Ochrana soukromí

1. **Žádné citlivé údaje v Gitu**: Nikdy necommitujte API klíče, hesla k Bazoši ani tokeny. Konfigurace patří do `config/config.json` (který je v `.gitignore`).
2. **Path Traversal Guard**: Při práci s fotografiemi vždy ověřujte cesty pomocí `target.is_relative_to(PHOTOS_DIR)` (viz funkce `safe_delete_photos_dir()` v `app.py`).
3. **EXIF Sanitace**: Všechny nahrávané fotografie procházejí automatickým očištěním o GPS metadata domova a EXIF rotací.
4. **Clean Plaintext Standard**: Texty inzerátů a generované popisy nesmí obsahovat markdownové hvězdičky (`*`, `**`), které Bazoš nepodporuje.

---

## 🚀 8. Postup odeslání Pull Requestu

1. Vytvořte si větev (`git checkout -b feature/moje-novinka`).
2. Implementujte změny a napište odpovídající testy.
3. Spusťte `pytest` a ujistěte se, že všechny testy prochází.
4. Vytvořte commit dle konvence Conventional Commits.
5. Pushněte větev na GitHub (`git push origin feature/moje-novinka`).
6. Otevřete Pull Request – automaticky se aktivuje šablona PR a spustí se GitHub Actions CI pipeline.
