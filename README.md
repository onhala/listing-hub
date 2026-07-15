# 🤖 Listing Hub & AI Editor v3.0.0

Prémiové interaktivní webové řídicí centrum pro kompletní správu inzerce na portálech Bazoš.cz a Aukro.cz, s integrovaným živým noVNC prohlížečem a pokročilým AI Gemini editorem textů. 

Tento nástroj byl vyvinut speciálně pro dynamické a přehledné inzerování většího množství věcí s maximální úsporou času a plně automatickým obnovováním dat.

---

## 🚀 Hlavní funkce

1. **Moderní Web GUI a Taby (`templates/index.html`)**:
   - **Aktivní inzeráty**: Přehled živých inzerátů z Bazoše se statistikami zhlédnutí a počtem fotek.
   - **Věci k prodeji**: Sekce pro expirované věci, koncepty (drafty) a položky, které se zrovna nenabízí aktivně.
   - **Prodané věci**: Kompletní historie prodejů se statistikou zisků.
   - **Živý prohlížeč (VNC)**: Integrované okno noVNC přímo v aplikaci pro sledování práce robota na Bazoši a bezpečné jednorázové zadání SMS kódu.
   - **Nastavení**: Plně grafická konfigurace uživatelského jména, e-mailu, telefonu, výchozího hesla pro inzeráty a Gemini API klíče.

2. **Automatický refresh na pozadí (Background Worker)**:
   - Daemon vlákno periodicky aktualizuje stavy, platnost a zhlédnutí inzerátů z Bazoše.
   - **SMS Guard**: Pokud Bazoš při refreshu vyžaduje SMS, proces se čistě zastaví, stav se přepne na `"needs_sms"` a v UI vyskočí červený varovný banner. Další SMS na pozadí se neodesílají, dokud uživatel neprovede ruční přihlášení.
   - **Timing**: Interval auto-refreshu je plně nastavitelný přímo v Nastavení (od 15 minut do 24 hodin).
   - **Zámek procesu**: Bezpečné sdílení Playwright procesu k zamezení konfliktů mezi pozadím a ručními úpravami.

3. **Pokročilý AI Editor a Gemini Integrace**:
   - Tlačítko **Vylepšit pomocí AI** u popisu a nadpisu inzerátu.
   - Gemini automaticky opraví překlepy, zlepší prodejní tón a navrhne optimalizované varianty nadpisů.

4. **Správa a vyloučení fotografií**:
   - V detailu inzerátu se zobrazují Base64 náhledy všech fotek z lokální složky.
   - Kliknutím na fotku ji lze označit jako vyloučenou – Playwright ji při vystavování přeskočí.
   - Karta inzerátu zobrazuje stav např. `📷 4/5 fotek`.

5. **Čítače a ochrana nadpisů (Limit 50 znaků)**:
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

Aplikaci lze snadno provozovat na **TrueNAS SCALE** (Cobia/Dragonfish/Electric Eel) jako **Custom App**.

### 1. Nastavení aplikace v TrueNAS
Při vytváření aplikace v TrueNAS SCALE (sekce **Apps** -> **Discover Apps** -> **Custom App**) vyplňte následující parametry:

- **Application Name**: `bazos-automat`
- **Image Repository**: `ghcr.io/onhala/bazos-automat`
- **Image Tag**: `latest`
- **Port Forwarding (Networking)**:
  - Port `5001` -> Host Port `5001` (Flask Web GUI)
  - Port `6080` -> Host Port `6080` (noVNC stream pro zadání SMS)
- **Environment Variables**:
  - `DISPLAY` = `:99`
  - `PYTHONUNBUFFERED` = `1`
  - *(Volitelně)* `BAZOS_EMAIL`, `BAZOS_PASSWORD`, `BAZOS_PHONE`, `GEMINI_API_KEY` (viz sekce konfigurace)
- **Storage (Host Path Mounts)**:
  Pro zachování dat a fotek při aktualizacích namapujte následující svazky (Host Path):
  - `/app/bazos_config.json` -> Cesta k souboru s konfigurací na vašem poolu
  - `/app/bazos_active_listings.json` -> Cesta k souboru s databází inzerátů
  - `/app/bazos_session.json` -> Cesta k souboru s přihlašovací relací Bazoše
  - `/app/photos` -> Cesta k adresáři s lokálními fotografiemi inzerátů

### 2. Automatické aktualizace a kontrola verzí na TrueNAS SCALE
- **Detekce nové verze**: TrueNAS SCALE automaticky periodicky dotazuje GitHub Container Registry (`ghcr.io`). Pokud detekuje novější sestavení s tagem `latest`, zobrazí u aplikace tlačítko **Update**.
- **Self-Update z UI**: Vzhledem k tomu, že kontejner je neměnný (immutable), Flask webové rozhraní při detekci nové verze zobrazí v sidebaru upozornění a po kliknutí ti ukáže instrukce pro TrueNAS. 
- Pro aktualizaci stačí kliknout na **Update** přímo v administračním rozhraní **TrueNAS SCALE -> Apps**, čímž systém stáhne nejnovější image a bezpečně kontejner zrekonstruuje bez ztráty nastavení (díky namapovaným Host Path svazkům).

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
