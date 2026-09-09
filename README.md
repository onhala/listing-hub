# 🤖 Listing Hub & AI Editor v3.6.0

Prémiové interaktivní webové řídicí centrum pro kompletní správu inzerce na portálech Bazoš.cz a Aukro.cz, s integrovaným živým noVNC prohlížečem a pokročilým AI Gemini Vision poradcem pro fotky a ceny.

---

### 📚 Dokumentace projektu
- 📦 **[Produktová dokumentace (PRODUCT.md)](PRODUCT.md)**: Uživatelská příručka, koncept „Drop & Sell“, workflow a hodnota pro prodejce.
- 🛠️ **[Vývojářská příručka (DEVELOPMENT.md)](DEVELOPMENT.md)**: Architektura aplikace, REST API specifikace, lokální setup a unit testování.
- 🐳 **[Produkční nasazení (DEPLOYMENT.md)](DEPLOYMENT.md)**: Provoz v Dockeru, TrueNAS SCALE, ZFS oprávnění a Nginx reverzní proxy.

---

## 🚀 Hlavní funkce

1. **Moderní Web GUI a Taby (`templates/index.html`)**:
   - **Aktivní inzeráty**: Přehled živých inzerátů z Bazoše se statistikami zhlédnutí a počtem fotek.
   - **Věci k prodeji**: Sekce pro expirované věci, koncepty (drafty) a položky, které se zrovna nenabízí aktivně.
   - **Prodané věci**: Kompletní historie prodejů se statistikou zisků.
   - **Živý prohlížeč (VNC)**: Integrované okno noVNC přímo v aplikaci pro sledování práce robota na Bazoši a bezpečné jednorázové zadání SMS kódu.
   - **Nastavení**: Plně grafická konfigurace uživatelského jména, e-mailu, telefonu, výchozího hesla pro inzeráty a Gemini API klíče.

2. **AI Vision-First tvorba inzerátu ("Drop & Sell")**:
   - **Blesková analýza z fotek**: Přetáhněte fotky (drag & drop), vyberte ze souborů nebo vložte přímo ze schránky (`Cmd+V`).
   - Multimodální model **Gemini 2.5 Flash** z fotek rozpozná značku, přesný model, vizuální stav, příslušenství a klíčové parametry.
   - **Varianty nadpisů s vysokým CTR**: AI navrhne 3–5 úderných variant nadpisů s garantovanou délkou do 50 znaků. Výběr jedním kliknutím.
   - **Cenový radar z reálného Bazoše**: Analýza konkurenčních nabídek a doporučení tří cenových hladin (*Rychlý prodej -10 %*, *Férová mediánová cena*, *Prémiová cena +10 %*).
   - **Strukturovaný technický popis**: Generování čtivého a věcného popisu bez otravných klišé a marketingového balastu.
   - **Výběr hlavní fotky**: AI doporučí nejlepší fotku na úvod inzerátu (označení hvězdičkou), kterou Playwright nahraje jako první.

3. **Automatický refresh na pozadí (Background Worker)**:
   - Daemon vlákno periodicky aktualizuje stavy, platnost a zhlédnutí inzerátů z Bazoše.
   - **SMS Guard**: Pokud Bazoš při refreshu vyžaduje SMS, proces se čistě zastaví, stav se přepne na `"needs_sms"` a v UI vyskočí červený varovný banner. Další SMS na pozadí se neodesílají, dokud uživatel neprovede ruční přihlášení.
   - **Timing**: Interval auto-refreshu je plně nastavitelný přímo v Nastavení (od 15 minut do 24 hodin).
   - **Zámek procesu**: Bezpečné sdílení Playwright procesu k zamezení konfliktů mezi pozadím a ručními úpravami.

4. **Nenásilné sledování verzí & Inspektor (GitHub Diff & 1-Click Update)**:
   - Interaktivní widget v zápatí sidebaru zobrazuje verzi a zkrácený git commit hash (`v3.6.0 • [hash]`).
   - Nenásilný plovoucí toast s možností odložení do `localStorage` (žádné rušivé celoobrazovkové bannery).
   - Dialog srovnání nainstalované verze a hashe proti GitHubu s přímým odkazem na diff změn a 1-click upgradem na TrueNAS.

5. **Správa a vyloučení fotografií**:
   - V detailu inzerátu se zobrazují Base64 náhledy všech fotek z lokální složky.
   - Kliknutím na fotku ji lze označit jako vyloučenou – Playwright ji při vystavování přeskočí.
   - Karta inzerátu zobrazuje stav např. `📷 4/5 fotek`.

6. **Čítače a ochrana nadpisů (Limit 50 znaků)**:
   - Real-time čítače s varovným barevným tónem (žlutá/červená) u políček nadpisů.
   - Automatická backend sanitace zkracuje nadpisy na max 50 znaků k zamezení ořezání na straně Bazoše.

---

## 🛠️ Rychlé spuštění v Dockeru (Doporučeno)

Aplikace je plně kontejnerizovaná a obsahuje kompletní prostředí včetně Xvfb, Fluxboxu a noVNC serveru pro grafické streamování prohlížeče.

### 1. Spuštění kontejnerů lokálně
V kořenovém adresáři projektu jednoduše spusť:
```bash
docker compose build
docker compose up -d
```

### 2. Přístup k aplikacím
- **Webové rozhraní**: [http://localhost:5001](http://localhost:5001)
- **noVNC Prohlížeč (samostatný)**: [http://localhost:6080](http://localhost:6080)

---

## 🐳 TrueNAS SCALE Deployment

Aplikace je plně optimalizována pro **TrueNAS SCALE** (včetně verze 24.10+ Electric Eel s nativním Docker Compose i starších Cobia/Dragonfish s Custom Apps).

Pro rychlé nasazení je v repozitáři připraven šablonový soubor [`docker-compose.truenas.yml`](docker-compose.truenas.yml).

### 1. Řešení ZFS oprávnění (PUID / PGID 568)
TrueNAS SCALE standardně provozuje kontejnery a svazky pod systémovým uživatelem `apps` (`UID 568`, `GID 568`). Kontejner obsahuje automatický `docker-entrypoint.sh`, který při startu přizpůsobí oprávnění perzistentních složek `/app/config`, `/app/data` a `/app/photos` podle zadaných proměnných `PUID` a `PGID`:
```yaml
environment:
  - PUID=568
  - PGID=568
```
Tím je zcela vyřešen problém s chybami `Permission Denied` při zápisu inzerátů a fotek.

### 2. Okamžité aktualizace (Zero-Latency Updates)
Už žádné čekání na 24hodinový cron TrueNASu pro detekci nových verzí. K dispozici jsou 3 možnosti:
1. **1-Click z Web UI**: Po vydání nové verze se v aplikaci zobrazí upozornění. V modalu stačí kliknout na **"Aktualizovat ihned na TrueNAS"** – Listing Hub zavolá TrueNAS REST API (`POST /api/v2.0/app/upgrade`) a server okamžitě stáhne nový image a provede restart. (Nastavte v sekci *Nastavení* TrueNAS URL a API klíč).
2. **Automatický webhook z GitHub Actions**: V GitHub Actions workflow (`docker-build-push.yml`) je integrován krok, který při sestavení nového image automaticky odešle push notifikaci do vašeho TrueNAS SCALE API (stačí nastavit GitHub Secrets `TRUENAS_URL` a `TRUENAS_API_KEY`).
3. **Watchtower sidecar**: Součástí `docker-compose.truenas.yml` je lehký Watchtower kontejner kontrolující nový image každých 120 sekund.

### 3. Stav kontejneru (Healthcheck) & OCI Metadata
Kontejner obsahuje nativní `HEALTHCHECK` volající stav background workeru (`/api/refresh/status`) a bohaté OCI/TrueNAS labely (`com.truenas.app.webui.port`, kategorie, ikona), takže se v rozhraní TrueNAS SCALE zobrazuje jako **Healthy** s přímým odkazem na Web UI.

---

## 🛠️ Lokální instalace (Pro vývojáře)

Pokud nechcete používat Docker, můžete aplikaci spustit lokálně ve virtuálním prostředí.

### 1. Příprava virtuálního prostředí
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium
```

### 2. Spuštění Flask serveru
```bash
.venv/bin/python app.py
```
Aplikace poběží na adrese [http://localhost:5001](http://localhost:5001).

---

## 🔍 Analýza konkurenčních cen (`bazos_analyzer.py`)

Nástroj stále obsahuje CLI skript pro analýzu cen podobného zboží:
```bash
.venv/bin/python bazos_analyzer.py "Sekačka HECHT" [minimální_cena] [maximální_cena]
```
Skript stáhne konkurenční inzeráty a spočítá průměrné ceny a doporučí prodejní strategie.
