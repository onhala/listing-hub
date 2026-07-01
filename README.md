# 🤖 Bazoš Automat & AI Editor v3.0.0

Prémiové interaktivní webové řídicí centrum pro kompletní správu inzerce na portálu Bazoš.cz, s integrovaným živým noVNC prohlížečem a pokročilým AI Gemini editorem textů. 

Tento nástroj byl vyvinut speciálně pro dynamické a přehledné inzerování většího množství věcí s maximální úsporou času, eliminací opakovaného SMS ověřování a plně automatickým obnovováním dat.

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
   - Gemini automaticky opraví překlepy, zlepší prodejní tón (s ohledem na rodinnou inženýrskou tradici firmy) a navrhne optimalizované varianty nadpisů.

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

### 1. Spuštění kontejnerů
V kořenovém adresáři projektu jednoduše spusť:
```bash
docker compose build
docker compose up -d
```

### 2. Přístup k aplikacím
- **Webové rozhraní**: [http://localhost:5001](http://localhost:5001)
- **noVNC Prohlížeč (samostatný)**: [http://localhost:6080](http://localhost:6080)

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
