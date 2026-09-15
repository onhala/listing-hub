# 🛠️ Vývojářská dokumentace: Listing Hub & AI Editor

Tento dokument slouží jako komplexní technická a architektonická příručka pro vývojáře rozšiřující systém **Listing Hub**.

---

## 1. Architektura systému

Listing Hub je postaven na modulární vrstvené architektuře v Pythonu (Flask) s asynchronním webovým rozhraním ve vanilla JS a odděleným workerem pro automatizaci browseru (Playwright).

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Webové rozhraní (Frontend)                       │
│       HTML5 Templates + Vanilla ES6 JS (app.js) + CSS3 (style.css)      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ REST API (JSON / Multipart)
┌───────────────────────────────────▼────────────────────────────────────┐
│                        Flask Backend (app.py)                          │
├───────────────────┬───────────────────┬────────────────────────────────┤
│  listing_hub.ai   │ listing_hub.core  │     listing_hub.portals        │
│  ──────────────── │ ────────────────  │     ───────────────────        │
│  • vision.py      │ • db.py (SQLite)  │     • bazos_portal.py          │
│  • gemini.py      │ • config.py       │     • aukro_portal.py          │
│  • advisor.py     │ • version.py      │     • session_manager.py       │
└─────────┬─────────┴─────────┬─────────┴────────────────┬───────────────┘
          │                   │                          │
┌─────────▼─────────┐ ┌───────▼─────────┐        ┌───────▼───────────────┐
│ Gemini 2.5 Flash  │ │  Perzistence    │        │ Playwright Headless   │
│ Multimodal API    │ │  SQLite + JSON  │        │ Chromium + Xvfb / VNC │
└───────────────────┘ └─────────────────┘        └───────────────────────┘
```

### Modulární struktura (`listing_hub/`):

1. **`listing_hub.core`**:
   - **`db.py`**: SQLite databázová vrstva (`listings.db`). Ukládá inzeráty s dynamickým JSON sloupcem `portal_states`, což umožňuje flexibilní evidenci stavu na Bazoši (URL, zhlédnutí, datum, TOP status) i paralelní evidenci na dalších portálech (**Facebook Marketplace**, **Sbazar.cz**, **Vinted**, **Aukro.cz**, ruční Bazoš a vlastní platformy). Podporuje evidenci prodejů (`sale_price`, `sold_at`, `sold_notes`, `sold_channel`) s automatickými migracemi tabulek při startu (`init_db()`), a funkce `record_manual_publication()`, `update_listing_portal_url()`, `mark_listing_as_sold()`, `restore_sold_listing()` a `get_sold_statistics()`.
   - **`config.py`**: Správa perzistentní konfigurace (`config/config.json`), base64 hesla a automatická verifikace/oprava přístupových práv svazků pro TrueNAS ZFS.
   - **`version.py`**: Správa verzí (v3.9.0) s 15minutovou in-memory mezipamětí proti GitHub API rate limitu (60 req/h), multi-tier detekce lokálního commitu (`GIT_COMMIT_SHA` env var, `version.json`, `git rev-parse`) a generátor GitHub compare diff odkazů.
   - **Bezpečnost souborového systému & ochrana soukromí**: Funkce `safe_delete_photos_dir()` v `app.py` ověřuje absolutní cesty vůči `PHOTOS_DIR` pomocí `target.is_relative_to(photos_base)` a blokuje Path Traversal útoky. Funkce `strip_exif_and_normalize()` automaticky narovnává orientaci fotek z mobilů a odstraňuje citlivá EXIF GPS metadata.

2. **`listing_hub.ai`**:
   - **`vision.py`**: Multimodální analýza fotografií pomocí modelu `gemini-2.5-flash`. Provádí automatické EXIF otočení a kompresi obrázků na max 1280 px (odezva do 2 s). Extrahuje parametry, navrhuje 3–5 úderných variant nadpisů do 50 znaků a vybírá nejlepší titulní fotografii. Propojeno s cenovým radarem z Bazoše.
   - **`gemini.py`**: 
     - **Dynamická správa modelů (`get_available_gemini_models`)**: Dotazuje se na Google Generative Language API (`https://generativelanguage.googleapis.com/v1beta/models?key=...`), filtruje metody `generateContent` a vyřazuje nepotřebné embedding, imagen a eval modely.
     - **Automatická náhrada ukončených modelů**: Modely vyřazené Googlem (např. `gemini-2.5-pro`) jsou na aplikační úrovni automaticky detekovány a nahrazeny doporučeným modelem `gemini-2.5-flash` nebo preview modelem `gemini-3.1-pro-preview`.
     - **Odolnost a mezipaměť**: Výsledky jsou cachovány v paměti po dobu 15 minut (`_MODELS_CACHE`). Při výpadku sítě, timeoutu či absenci API klíče se automaticky použije robustní statický fallback `DEFAULT_FALLBACK_MODELS`.
     - **Jazykový asistent & Čistý text (`improve_text_with_gemini`, `clean_bazos_text`)**: Jazykové úpravy inzerátů s přísnou sanitací textu: striktní zákaz nepodporovaných markdownových hvězdiček (`*`, `**`), kódových bloků (```) a převod odrážek na čisté pomlčky (`- `).
   - **`advisor.py`**: Cenový poradce a scraper tržních cen z Bazoše a Sbazaru. Počítá tržní medián, rychlý prodej (-10 %) a prémiovou hladinu (+10 %).

3. **`listing_hub.portals`**:
   - **`bazos/categories.py`**:
     - **Katalog 20 rubrik (`BAZOS_ALL_SUBDOMAINS`)**: Kompletní seznam všech 20 specializovaných subdomén Bazoše (`deti.bazos.cz`, `dum.bazos.cz`, `nabytek.bazos.cz`, `elektro.bazos.cz`, `sport.bazos.cz`, `auto.bazos.cz`, `motorky.bazos.cz`, `stroje.bazos.cz`, `pc.bazos.cz`, `mobil.bazos.cz`, `foto.bazos.cz`, `hudba.bazos.cz`, `obleceni.bazos.cz`, `knihy.bazos.cz`, `zvirata.bazos.cz`, `vstupenky.bazos.cz`, `reality.bazos.cz`, `prace.bazos.cz`, `sluzby.bazos.cz`, `ostatni.bazos.cz`) s českými názvy a ikonami.
     - **Vážený ranking rubrik (`rank_target_domains`)**: Ohodnocuje a řadí všech 20 subdomén podle relevance k inzerátu. Váhy bodování: shoda s existující URL (1000 b), klíčové slovo v titulku (90 b), klíčové slovo v popisu (20 b), shoda kategorie s názvem subdomény (80 b) a specifická regex pravidla (např. motorky vs. elektromotory, 120 b).
     - **Deterministické určení (`get_target_domain`)**: Vybere nejvýše skórující subdoménu s bezpečným fallbackem na `dum.bazos.cz`.
     - **Normalizace češtiny (`normalize_cz`)**: NFKD normalizace textu s odstraněním diakritiky, převodem na malá písmena a očištěním o speciální znaky.
     - **Synonymická mapa (`CATEGORY_SYNONYMS`)**: Rozsáhlý slovník synonym a klíčových slov mapující stovky termínů do podkategorií Bazoše.
   - **`bazos/session.py` a Dvoufázový protokol proti reloadu formuláře**:
     - **Podstata problému reloadu (Form Reload Trap)**: Na portálu Bazoš.cz provozuje každá rubrika samostatnou subdoménu. Změna rubriky uvnitř otevřeného formuláře vyvolává tvrdý reload celé stránky, který okamžitě a nevratně vymaže veškerá vyplněná data a nahrané fotografie.
     - **Architektonické řešení**: Upfront determinace cílové subdomény a otevření formuláře Playwrightem přímo na adrese `https://{target_domain}/pridat-inzerat.php`. Během vyplňování se již rubrika nemění, což 100% eliminuje riziko promazání formuláře.
     - **Dvoufázový životní cyklus (Two-Phase Posting Lifecycle)**:
       - **Fáze 1 (Autonomní předvyplnění)**: Worker provede navigaci na správnou subdoménu, vyplní veškeré údaje, heslo (`heslobazar`), zvolí podkategorii a nahraje fotky. Při volání z webu (`is_web=True`) worker uvolní vlákno a přejde do stavu `READY_FOR_REVIEW`.
       - **Fáze 2 (Uživatelská revize & Potvrzení)**: Uživatel v živém prohlížeči (noVNC / screencast) zkontroluje údaje, případně vyřeší SMS kód, klikne na Bazoši na *Odeslat* a následně v Listing Hubu potvrdí akci přes `POST /api/action/confirm`. Backend ověří dokončení odeslání na Bazoši, extrahuje novou URL a zapíše inzerát jako aktivní do SQLite databáze.
   - **Dávkové znovuvystavení (Batch Reposting Architecture)**:
     - **Frontend fronta (`batchQueue`, `batchIndex`)**: Správa stavu výběru více položek v záložkách aktivních i neprodaných inzerátů.
     - **Dávkový modal (`batch-repost-modal`)**: Umožňuje individuální úpravu prodejní ceny (`batch-row-price`) a cílové rubriky (`batch-row-rubrika`) pro každý vybraný inzerát v dávce před spuštěním.
     - **Sekvenční bezpečné zpracování**: Průchod položkami jedna po druhé na dedikovaném workeru. Zahrnuje indikátor postupu (`batch-queue-indicator`), podporu přeskočení (`btn-batch-skip`) i okamžitého zrušení (`btn-batch-cancel`).
     - **Automatické topování**: Pro každou položku se asynchronně provede smazání původního inzerátu na Bazoši přes heslo a vystavení nového s aktualizovanými parametry.
   - **Správa prodaných inzerátů (Sold Lifecycle Architecture)**:
     - **Perzistence v SQLite**: Sloupce `sale_price` (`INTEGER`), `sold_at` (`TEXT`) a `sold_notes` (`TEXT`) v tabulce `listings`.
     - **Metody v `listing_hub.core.db`**: `mark_listing_as_sold()`, `restore_sold_listing()` a `get_sold_statistics()`.
     - **Asynchronní online výmaz**: Při označení inzerátu za prodaný s volbou `delete_on_bazos=True` spustí backend asynchronní vlákno s Playwright workerem, který na Bazoši inzerát vyhledá, zadá heslo a provede online smazání pro ukončení poptávek.
     - **Plná reverzibilita**: Endpoint `POST /api/listings/<id>/restore_sold` bezpečně vrátí položku zpět do stavu `unsold` (expirováno/k prodeji) s vynulováním prodejních metrik.
   - **`aukro/`**: Modulární rozhraní pro budoucí aukční vystavování.

---

## 2. Lokální vývojové prostředí

### Požadavky:
- Python 3.11 nebo novější
- Chromium (systémové nebo instalované přes Playwright)
- Git

### Instalace krok za krokem:

```bash
# 1. Klonování repozitáře
git clone https://github.com/onhala/listing-hub.git
cd listing-hub

# 2. Vytvoření a aktivace virtuálního prostředí
python3 -m venv .venv
source .venv/bin/activate

# 3. Instalace závislostí
pip install -r requirements.txt

# 4. Instalace prohlížeče Chromium pro Playwright
playwright install chromium

# 5. Spuštění vývojového serveru
python app.py
```
Aplikace běží na: `http://127.0.0.1:5001`.

---

## 3. Konfigurace a proměnné prostředí

Aplikace podporuje konfiguraci buď přes webové rozhraní (*Nastavení* -> uloženo v `config/config.json`), nebo pomocí environmentálních proměnných (vhodné pro Docker):

| Proměnná | Popis | Výchozí hodnota |
| :--- | :--- | :--- |
| `PUID` | UID pro spuštění procesů uvnitř kontejneru | `1000` (pro TrueNAS nastavte `568`) |
| `PGID` | GID pro spuštění procesů uvnitř kontejneru | `1000` (pro TrueNAS nastavte `568`) |
| `GEMINI_API_KEY` | API klíč pro Google Gemini (Vision & Text) | Prázdné |
| `BAZOS_EMAIL` | Výchozí e-mail pro ověření a správu na Bazoši | Prázdné |
| `BAZOS_PHONE` | Telefonní číslo pro SMS ověření | Prázdné |
| `BAZOS_PASSWORD` | Výchozí heslo pro editaci a mazání inzerátů | Prázdné |
| `AUTO_REFRESH_ENABLED` | Povolení periodického refreshe z Bazoše | `true` |
| `AUTO_REFRESH_INTERVAL` | Interval auto-refreshe v minutách | `720` (12 hodin) |
| `TRUENAS_URL` | URL TrueNAS serveru pro 1-click update | Prázdné (např. `http://192.168.1.50`) |
| `TRUENAS_API_KEY` | API klíč TrueNAS SCALE pro aplikaci | Prázdné |
| `TRUENAS_APP_NAME` | Název aplikace v TrueNAS Apps | `bazos-automat` |
| `GIT_COMMIT_SHA` | Injektovaný commit SHA sestaveného image | `unknown` |

---

## 4. Testování a automatizovaná kontrola kvality

Projekt obsahuje rozsáhlou sadu unit testů v adresáři `tests/unit/`:

```bash
# Spuštění celé sady testů
pytest

# Spuštění s výpisem pokrytí
pytest -v --tb=short

# Spuštění specifických sad:
pytest tests/unit/test_categories.py # Testy rezoluce subdomén Bazoše, synonym a normalizace CZ
pytest tests/unit/test_app.py        # Testy REST API (včetně /api/action/confirm, delete a safe_delete_photos_dir)
pytest tests/unit/test_vision.py     # Testy AI Vision a práce s fotkami
pytest tests/unit/test_version.py    # Testy detekce verzí (v3.8.8), GitHub cache a diff linku
pytest tests/unit/test_advisor.py    # Testy cenového poradce a výpočtu mediánu
pytest tests/unit/test_db.py         # Testy CRUD operací SQLite databáze
```

---

## 5. Kompletní specifikace REST API

### Rubriky Bazoše & Doporučování:
- `GET /api/bazos/rubriky`
  - Vrací kompletní katalog všech 20 specializovaných rubrik Bazoše:
    ```json
    {
      "status": "success",
      "rubriky": [
        {"domain": "deti.bazos.cz", "label": "Děti a hračky", "icon": "fa-child"},
        {"domain": "dum.bazos.cz", "label": "Dům a zahrada", "icon": "fa-house-chimney-window"},
        {"domain": "nabytek.bazos.cz", "label": "Nábytek", "icon": "fa-couch"},
        ...
      ]
    }
    ```
- `POST /api/ai/suggest-rubrika` *(JSON payload: `{"listing_id": str|null, "title": str, "description": str, "category": str, "url": str}`)*
  - Analyzuje zadané parametry inzerátu a pomocí algoritmu `rank_target_domains()` ohodnotí a seřadí všech 20 subdomén podle relevance.
  - Vrací:
    ```json
    {
      "status": "success",
      "top_domain": "dum.bazos.cz",
      "top_label": "Dům a zahrada",
      "recommended": [
        {"domain": "dum.bazos.cz", "label": "Dům a zahrada", "score": 190, "matched_keywords": ["sekacka", "zahrada"]},
        ...
      ],
      "all": [...],
      "reason": "Doporučeno na základě: sekacka, zahrada"
    }
    ```

### Správa inzerátů & Životní cyklus:
- `GET /api/listings`
  - Vrací seznam všech inzerátů rozdělených podle stavů (`active`, `unsold`, `sold`).
- `POST /api/listings/save`
  - Uloží změny v inzerátu (automaticky zkracuje `title` na max 50 znaků).
- `POST /api/listings/create-with-photos` *(Multipart form-data)*
  - Atomicky založí inzerát v DB, uloží nahrané fotky a nastaví označenou titulní fotku jako `foto_1.jpg`.
- `POST /api/listings/<listing_id>/mark_sold` *(JSON payload: `{"sale_price": int|null, "sold_at": "YYYY-MM-DD"|null, "notes": str|null, "sold_channel": str|null, "delete_on_bazos": bool}`)*
  - Označí inzerát jako prodaný (`status = 'sold'`), zapíše realizovanou prodejní cenu, datum obchodu, interní poznámku a prodejní kanál (`sold_channel`, např. `facebook`, `sbazar`, `vinted`, `aukro`, `bazos`, `osobne`, `jiny`) do SQLite databáze.
  - Pokud je `delete_on_bazos: true` a inzerát má aktivní URL na Bazoši, spustí asynchronní worker vlákno, které provede online smazání inzerátu na Bazoši pomocí uloženého hesla.
  - Vrací: `{"status": "success", "message": str, "deleted_online": bool}`.
- `POST /api/listings/<listing_id>/restore_sold`
  - Vrátí prodaný inzerát zpět k prodeji (`status = 'unsold'`), vyresetuje `sale_price`, `sold_at` a `sold_notes`. Inzerát se přesune zpět do záložky "Věci k prodeji" (Koncepty/Expirováno) připraven k případnému znovuvystavení.
- `GET /api/listings/sold_stats`
  - Vrací souhrnné manažerské metriky pro dashboard v záložce "Prodané věci":
    ```json
    {
      "status": "success",
      "stats": {"total_sold": 12, "total_profit": 28400, "avg_price": 2366},
      "total_sold": 12,
      "total_profit": 28400,
      "avg_price": 2366
    }
    ```
- `POST /api/listings/delete` *(podporuje také metodu `DELETE`, JSON payload: `{"id": "<listing_id>", "delete_photos": true|false}`)*
  - Odstraní inzerát z databáze SQLite. Pokud je `delete_photos: true`, bezpečně smaže odpovídající lokální složku fotografií s validací proti Path Traversal přes `safe_delete_photos_dir()`.

### Multi-portál Evidence & Asistent Ručního Vystavení:
- `POST /api/listings/<listing_id>/publish-manual` *(JSON payload: `{"portal_name": str, "portal_label": str|null, "url": str|null, "notes": str|null}`)*
  - Zaznamená ruční publikaci inzerátu na externím portálu (Facebook Marketplace, Sbazar, Vinted, Aukro, Bazoš, vlastní).
  - Vytvoří / aktualizuje záznam v `portal_states` se stavem `Aktivní`, uloží datum a volitelnou URL i poznámku.
- `POST /api/listings/<listing_id>/portal-url` *(JSON payload: `{"portal_name": str, "url": str}`)*
  - Umožňuje rychlé doplnění nebo aktualizaci živého URL odkazu pro daný portál bez nutnosti otevírat celou editaci.
- `POST /api/listings/<listing_id>/portal-views` *(JSON payload: `{"portal_name": str, "views": int}`)*
  - Aktualizuje počet zhlédnutí pro zvolený portál v tabulkách `portal_states` i `listing_publications` a okamžitě zapíše snapshot do `listing_views_history` pro Prometheus metriky a Grafanu.
- `POST /api/listings/<listing_id>/portal-views-refresh` *(JSON payload: `{"portal_name": str}`)*
  - Načte uloženou URL pro daný portál a pomocí univerzálního 3úrovňového scraperu (`listing_hub/portals/scrapers/universal.py`) zkusí automaticky zjistit počet zhlédnutí z veřejného webu (např. Sportovní vozy, Ráj veteránů, Motorkáři, Schema.org).
- `GET /api/photos/<listing_id>/zip`
  - Bleskově vygeneruje a streamuje in-memory ZIP archív (`fotky-<id>.zip`) obsahující všechny fotografie inzerátu přehledně seřazené pro snadné nahrání na externí inzertní servery.
- `POST /api/sms/relay` *(JSON payload: `{"text": str|null, "code": str|null, "token": str|null}`)*
  - Webhook pro příjem SMS ověřovacího kódu z telefonu (iOS Zkratky / Android Tasker) s volitelnou token autentizací (`sms_relay_token`), automatickou regex extrakcí 4–8 místného kódu a předáním do aktivní Playwright relace.

### Automatizace, Dávky & Browser akce (Playwright):
- `POST /api/action/<action_type>` *(kde `<action_type>` je `post`, `edit_price`, `delete` nebo `repost`, JSON payload: `{"id": "<listing_id>", "target_domain": "dum.bazos.cz", "extra_val": ...}`)*
  - Spustí neblokující úlohu na pozadí na dedikovaném worker vlákně.
  - Parametr `target_domain` explicitně určuje cílovou subdoménu Bazoše a předchází nechtěnému reloadu stránky.
- `GET /api/action/status`
  - Vrací aktuální stav workeru: `{"running": bool, "state": "IDLE|RUNNING|READY_FOR_REVIEW|COMPLETED|CANCELLED", "action_type": str, "listing_id": str, "error": str}`.
- `POST /api/action/confirm`
  - Dokončení 2. fáze vystavení: worker zkontroluje stav stránky na Bazoši (`_check_page_submitted`).
  - Pokud je uživatel stále na formuláři `pridat-inzerat.php`, vrátí `HTTP 422 Unprocessable Entity`.
  - Pokud byl inzerát odeslán, extrahuje novou URL adresu (`/inzerat/<id>/...`), aktualizuje stav inzerátu v DB na `Aktivní`, nastaví `created_at` a označí akci za dokončenou.
- `POST /api/action/cancel`
  - Okamžitě přeruší běžící worker vlákno, resetuje stav akce a zavře relaci prohlížeče.
- `POST /api/action/repost_with_new_price` *(JSON payload: `{"listing_id": "...", "new_price": 1500, "target_domain": "..."}`)*
  - Přenastaví cenu a rubriku v DB a automaticky spustí bezpečné znovuvystavení inzerátu (topování) na pozadí s vymazáním původního inzerátu.

### AI Modely, Analýza & Tržní Radar:
- `GET /api/ai/models` *(query parametry `api_key` volitelně, `force=true|false`)*
  - Dynamicky zjišťuje dostupné modely Gemini z uživatelského účtu přes Google Generative Language API.
  - Filtruje modely podporující `generateContent`, provádí vyřazení ukončených modelů (`gemini-2.5-pro` -> automatický fallback na `gemini-2.5-flash` nebo `gemini-3.1-pro-preview`) a při nedostupnosti API vrací `DEFAULT_FALLBACK_MODELS`.
  - Vrací: `{"status": "success", "models": [...], "is_fallback": bool, "current_model": str, "message": str}`.
- `POST /api/ai/analyze-photos` *(Multipart form-data)*
  - Multimodální analýza až 10 fotek přes Gemini 2.5 Flash + multi-source cenový radar.
  - Vrací: `recommended_title`, `titles` (3-5 variant), `description` (vyčištěný bez hvězdiček), `condition`, `market_analysis`, `estimated_price_czk`.
- `POST /api/ai/analyze-existing/<listing_id>`
  - Spustí AI Vision analýzu na existujících fotografiích již uloženého inzerátu.
- `POST /api/ai/improve`
  - Jazyková korektura a optimalizace stávajícího textu inzerátu (čistý text bez markdownu a hvězdiček).
- `POST /api/advisor/market-search` *(JSON payload: `{query, brand, model, condition, fallback_price}`)*
  - Spustí multi-source tržní analýzu (Bazoš.cz + Sbazar.cz API + Web + Gemini fallback).
- `GET /api/advisor/price/<listing_id>`
  - Spustí cenového poradce pro existující inzerát (automaticky vylučuje vlastní nabídku).

### Verze & Systémové funkce:
- `GET /api/version/check` *(volitelný parametr `?force=1`)*
  - Vrací stav verze: `app_version`, `local` (hash, prostředí), `latest` (hash, zpráva, datum), `compare_url` a `update_available`. Využívá in-memory cache na 15 minut.
- `POST /api/version/truenas-upgrade`
  - Odešle požadavek na TrueNAS REST API (`/api/v2.0/app/upgrade`) nebo Watchtower webhook pro okamžitý restart a stažení nejnovějšího image.
- `GET /api/refresh/status`
  - Vrací stav background workeru (využíváno také pro Docker `HEALTHCHECK`).
- `GET /api/calendar/feed.ics?token=<token>`
  - Webcal / iCal feed s termíny vypršení 60denní platnosti inzerátů a archívem prodejů.

### Monitoring & Prometheus Telemetrie:
- `GET /metrics`
  - Vrací standardní formát Prometheus text exposition (version 0.0.4 / OpenMetrics) pro centrální sběr v Prometheu a Grafaně.
  - Poskytuje klíčové metriky:
    - `listinghub_up`: Indikátor běhu a dostupnosti služby (1 = online).
    - `listinghub_listing_views`: Aktuální zhlédnutí inzerátu dle portálu a kategorie.
    - `listinghub_listing_views_total`: Celkový kumulativní součet zhlédnutí aktivních inzerátů.
    - `listinghub_listing_days_to_expire`: Zbývající počet dnů do 60denní expirace na Bazoši (`max(0, 60 - days_old)`).
    - `listinghub_listing_photos_count`: Počet fotografií nahraných u inzerátu.
    - `listinghub_active_inventory_value_czk`: Souhrnná nabídková hodnota aktivního skladu v Kč.
    - `listinghub_listing_days_old`: Stáří inzerátů ve dnech (detekce ležáků).
    - `listinghub_portal_listings_count` & `listinghub_portal_views_total`: Statistiky rozdělené dle jednotlivých portálů (Bazoš, Sbazar, FB Marketplace, Vinted, Aukro).
    - `listinghub_sales_total_czk` & `listinghub_sales_count_total`: Kumulativní realizované tržby a počet prodaných kusů.
    - `listinghub_sales_avg_days_to_sell`: Průměrná doba do realizace prodeje ve dnech (*Time-to-Sell*).
    - `listinghub_sales_by_channel_total_czk` & `listinghub_sales_by_channel_count`: Finanční atribuce dle prodejních kanálů.
    - `listinghub_baza_auto_refresh_status`: Provozní stav auto-refresh workeru Bazoše (1 = OK, 0 = vyžaduje SMS nebo chyba).
    - `listinghub_last_refresh_timestamp_seconds`: Unix timestamp posledního dokončeného refresh cyklu.

### AI Agent Interface (Antigravity & MCP):
- `GET /api/agent/v1/summary`
  - Tokenově efektivní dashboard JSON: počty inzerátů (Aktivní, Koncepty, Prodané, V kontrole), inzeráty blížící se 60denní expiraci a stav Playwright workeru včetně SMS guardu.
- `GET /api/agent/v1/listings` *(query parametry `status=all|active|draft|sold|needs_review`, `search`, `limit`)*
  - Filtrovatelný JSON index inzerátů s kanonickým životním cyklem.
- `GET /api/agent/v1/listings/<id>`
  - Kompletní agregát inzerátu včetně fotografií a stavů na portálech.
- `POST /api/agent/v1/draft` *(JSON payload: `title`, `price`, `description`, `category`, `condition`, `local_photos_dir`, `auto_market_radar`)*
  - Atomické založení konceptu inzerátu s volitelným automatickým naceněním tržním radarem.
- `POST /api/agent/v1/actions/post` *(JSON payload: `id` nebo `listing_id`, `target_domain`)*
  - Fáze 1 asistovaného vystavení: Playwright předvyplní formulář a zastaví se ve stavu `ready_for_review`.
- `GET /api/agent/v1/actions/status`
  - Aktuální stav běžící akce, workeru a URL živého screencastu.
- `POST /api/agent/v1/actions/confirm`
  - Fáze 2 lidského dohledu: ověří úspěch na portálu přes DOM a aktivuje inzerát v SQLite.
- `POST /api/agent/v1/actions/cancel`
  - Okamžité stornování relace prohlížeče.
- `POST /api/agent/v1/actions/repost` *(JSON payload: `listing_id`, `new_price`, `target_domain`)*
  - Znovuvystavení inzerátu (topování) se změnou ceny.
- `DELETE /api/agent/v1/listings/<id>` *(volitelný parametr `delete_photos=true`)*
  - Trvalé smazání inzerátu z DB s chroot guardem pro fotky.
- `POST /api/agent/v1/radar` *(JSON payload: `query`, `brand`, `model`, `condition`, `fallback_price`)*
  - Dotaz na multi-source cenový radar (Bazoš + Sbazar + Web).

#### Klientské nástroje pro agenty:
- **CLI klient**: `scripts/listing_hub_cli.py` (podpora přepínače `--json`, SQLite fallback při offline serveru).
- **FastMCP Server**: `scripts/listing_hub_mcp.py` (stdio JSON-RPC 2.0 server pro Claude Desktop, Cursor, Antigravity).
- **Architektonická dokumentace**:
  - Ubiquitous Language: [CONTEXT.md](CONTEXT.md)
  - ADR 0001 (Agent Interface Architecture): [docs/adr/0001-agent-interface-architecture.md](docs/adr/0001-agent-interface-architecture.md)
  - ADR 0002 (Two-Phase HITL Protocol): [docs/adr/0002-two-phase-hitl-protocol.md](docs/adr/0002-two-phase-hitl-protocol.md)
  - Agentic Use Cases: [docs/agent_use_cases.md](docs/agent_use_cases.md)


---

## 6. Docker & CI/CD workflow

Kontejner je sestavován pomocí multi-platformního Docker Buildx v GitHub Actions:

- **Soubor workflow**: `.github/workflows/docker-build-push.yml`
- **Build argumenty**: `GIT_COMMIT_SHA=${{ github.sha }}` se ukládá do proměnné prostředí kontejneru.
- **TrueNAS / OCI Labely**: Integrovány přímo v `Dockerfile` (`com.truenas.app.port`, webui, ikona).
- **ZFS Oprávnění**: `docker-entrypoint.sh` automaticky spouští `gosu` a přizpůsobuje vlastnictví perzistentních složek podle `PUID` a `PGID`.
- **Automatický upgrade push**: Workflow po úspěšném sestavení a pushnutí image do `ghcr.io` zavolá TrueNAS REST API, pokud jsou v repozitáři nakonfigurovány Secrets `TRUENAS_URL` a `TRUENAS_API_KEY`.
