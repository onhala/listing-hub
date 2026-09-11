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
   - **`db.py`**: SQLite databázová vrstva (`listings.db`). Ukládá inzeráty s dynamickým JSON sloupcem `portal_states`, což umožňuje flexibilní evidenci stavu na Bazoši (URL, zhlédnutí, datum) i budoucí integraci Aukra.
   - **`config.py`**: Správa perzistentní konfigurace (`config/config.json`), base64 hesla a automatická verifikace/oprava přístupových práv svazků pro TrueNAS ZFS.
   - **`version.py`**: Správa verzí (v3.8.7) s 15minutovou in-memory mezipamětí proti GitHub API rate limitu (60 req/h), multi-tier detekce lokálního commitu (`GIT_COMMIT_SHA` env var, `version.json`, `git rev-parse`) a generátor GitHub compare diff odkazů.
   - **Bezpečnost souborového systému**: Funkce `safe_delete_photos_dir()` v `app.py` ověřuje absolutní cesty vůči `PHOTOS_DIR` pomocí `target.is_relative_to(photos_base)` a blokuje jakékoliv pokusy o Directory/Path Traversal útoky (`../`).

2. **`listing_hub.ai`**:
   - **`vision.py`**: Multimodální analýza fotografií pomocí modelu `gemini-2.5-flash`. Provádí automatické EXIF otočení a kompresi obrázků na max 1280 px (odezva do 2 s). Extrahuje parametry, navrhuje 3–5 úderných variant nadpisů do 50 znaků a vybírá nejlepší titulní fotografii. Propojeno s cenovým radarem z Bazoše.
   - **`gemini.py`**: Jazykový model pro dodatečné úpravy a přepisy textů popisu či nadpisu existujících inzerátů (čistý text bez markdown formátování).
   - **`advisor.py`**: Cenový poradce a scraper tržních cen z Bazoše a Sbazaru. Počítá tržní medián, rychlý prodej (-10 %) a prémiovou hladinu (+10 %).

3. **`listing_hub.portals`**:
   - **`bazos/session.py`**: Správce relace Playwright běžící na dedikovaném worker vlákně. Obsahuje CDP Screencast streamování obrazu, frontu uživatelských vstupů a sjednocený timeout 30 sekund (`context.set_default_timeout(30000)` a `run_on_worker(timeout=30.0)`).
   - **`bazos/categories.py`**: Deterministická rezoluce cílové subdomény Bazoše (`get_target_domain`), extrakce subdomény a ID z existujících URL (`extract_subdomain`, `extract_ad_id`), normalizace češtiny s odstraněním diakritiky (`normalize_cz`) a synonymická mapa podkategorií.
   - **Dvoufázové vystavování inzerátů (Two-Phase Posting Lifecycle)**:
     - **Fáze 1 (Předvyplnění formuláře)**: Worker provede navigaci na `https://{target_domain}/pridat-inzerat.php`, vyplní nadpis, popis, cenu, osobní údaje, heslo (`heslobazar`), zvolí podkategorii a nahraje fotky. Při volání z webu (`is_web=True`) worker po nahrání fotek neblokuje proces čekáním, uloží `SESSION_STATE_PATH` a vrací řízení frontendu.
     - **Fáze 2 (Uživatelská revize & Potvrzení)**: Uživatel v živém prohlížeči inzerát zkontroluje, klikne na *Odeslat* a následně v rozhraní Listing Hubu potvrdí akci přes `POST /api/action/confirm`. Backend ověří přesměrování / opuštění formuláře, extrahuje nové URL a zapíše inzerát jako aktivní do SQLite databáze.
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
pytest tests/unit/test_version.py    # Testy detekce verzí (v3.8.7), GitHub cache a diff linku
pytest tests/unit/test_advisor.py    # Testy cenového poradce a výpočtu mediánu
pytest tests/unit/test_db.py         # Testy CRUD operací SQLite databáze
```

---

## 5. Kompletní specifikace REST API

### Správa inzerátů:
- `GET /api/listings`
  - Vrací seznam všech inzerátů rozdělených podle stavů (`active`, `unsold`, `sold`).
- `POST /api/listings/save`
  - Uloží změny v inzerátu (automaticky zkracuje `title` na max 50 znaků).
- `POST /api/listings/create-with-photos` *(Multipart form-data)*
  - Atomicky založí inzerát v DB, uloží nahrané fotky a nastaví označenou titulní fotku jako `foto_1.jpg`.
- `POST /api/listings/delete` *(podporuje také metodu `DELETE`, JSON payload: `{"id": "<listing_id>", "delete_photos": true|false}`)*
  - Odstraní inzerát z databáze SQLite. Pokud je `delete_photos: true`, bezpečně smaže odpovídající lokální složku fotografií s validací proti Path Traversal přes `safe_delete_photos_dir()`.

### Automatizace & Browser akce (Playwright):
- `POST /api/action/<action_type>` *(kde `<action_type>` je `post`, `edit_price` nebo `delete`, JSON payload: `{"id": "<listing_id>", "target_domain": "dum.bazos.cz", "extra_val": ...}`)*
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
  - Přenastaví cenu v DB a automaticky spustí znovuvystavení inzerátu (topování) na pozadí.

### AI Analýza, Gemini & Tržní Radar:
- `POST /api/ai/analyze-photos` *(Multipart form-data)*
  - Multimodální analýza až 10 fotek přes Gemini 2.5 Flash + multi-source cenový radar.
  - Vrací: `recommended_title`, `titles` (3-5 variant), `description` (vyčištěný bez hvězdiček), `condition`, `market_analysis`, `estimated_price_czk`.
- `POST /api/ai/analyze-existing/<listing_id>`
  - Spustí AI Vision analýzu na existujících fotografiích již uloženého inzerátu.
- `POST /api/ai/improve`
  - Jazyková korektura a optimalizace stávajícího textu inzerátu (čistý text bez markdownu).
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

---

## 6. Docker & CI/CD workflow

Kontejner je sestavován pomocí multi-platformního Docker Buildx v GitHub Actions:

- **Soubor workflow**: `.github/workflows/docker-build-push.yml`
- **Build argumenty**: `GIT_COMMIT_SHA=${{ github.sha }}` se ukládá do proměnné prostředí kontejneru.
- **TrueNAS / OCI Labely**: Integrovány přímo v `Dockerfile` (`com.truenas.app.port`, webui, ikona).
- **ZFS Oprávnění**: `docker-entrypoint.sh` automaticky spouští `gosu` a přizpůsobuje vlastnictví perzistentních složek podle `PUID` a `PGID`.
- **Automatický upgrade push**: Workflow po úspěšném sestavení a pushnutí image do `ghcr.io` zavolá TrueNAS REST API, pokud jsou v repozitáři nakonfigurovány Secrets `TRUENAS_URL` a `TRUENAS_API_KEY`.
