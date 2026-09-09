# 📦 Produktová dokumentace: Listing Hub & AI Editor

**Listing Hub** je moderní webové řídicí centrum navržené pro automatizovanou, efektivní a inteligentní správu inzerce na českých inzertních portálech (především **Bazoš.cz** s připraveným rozšířením na **Aukro.cz**).

Aplikace radikálně zjednodušuje a zrychluje proces prodeje přebytečného hardwaru, elektroniky, nářadí a vybavení z domácnosti, dílny či firmy.

---

## 🎯 Produktová vize: „Drop & Sell“

Tradiční tvorba inzerátu na Bazoši je zdlouhavá a frustrující:
- Manuální vymýšlení poutavého nadpisu tak, aby se vešel do přísného limitu 50 znaků.
- Dohledávání technických parametrů a přepisování výrobních štítků.
- Zkoumání konkurenčních cen na Bazoši pro nastavení férové ceny.
- Zdlouhavé nahrávání a organizace fotografií.

**Listing Hub přináší koncept „Drop & Sell“:**
Uživateli stačí vzít telefon, nafotit prodávanou věc ze všech úhlů (včetně štítku a příslušenství) a přetáhnout fotky do aplikace (nebo vložit přes `Cmd+V`). O vše ostatní se během **2 sekund** postará multimodální umělá inteligence **Google Gemini 2.5 Flash** napojená na živý tržní scraper.

> **Výsledek:** Doba přípravy a vystavení inzerátu se zkracuje z původních 5–10 minut na **pouhých 20 sekund**.

---

## 🚀 Klíčové funkce a uživatelské scénáře

### 1. AI Vision Průvodce vystavením nového inzerátu
- **Univerzální nahrání fotek:** Podpora přetažení myší (Drag & Drop), výběru souborů i přímého vložení ze schránky (`Ctrl+V` / `Cmd+V`).
- **Inteligentní extrakce detailů:**
  - Přesné rozpoznání značky, modelu a produktového čísla ze štítku.
  - Vizuální vyhodnocení stavu (např. *použité, drobné oděrky na krytu, kompletní balení*).
  - Detekce příslušenství (originální kufřík, nabíječka, kabely).
- **Optimalizované nadpisy (Vysoké CTR):**
  - Model vygeneruje 3 až 5 atraktivních variant nadpisů.
  - Garance limitu do 50 znaků s vizuálním čítačem (např. `42/50 znaků`).
  - Výběr a dosazení nadpisu jedním kliknutím na interaktivní štítek (chip).
- **Multi-Source tržní cenový radar (Bazoš + Sbazar + Web + Gemini):**
  - Propojení s reálnými inzeráty na Bazoši, veřejným API Sbazaru i webem – okamžitý výpočet mediánu cen s automatickým vyřazením vlastního inzerátu ze srovnání.
  - Tři doporučené cenové úrovně předvyplněné v interaktivních kartách:
    1. 🔴 **Rychlý prodej (-10 %)**: Pro okamžité oslovení kupců a rychlé uvolnění místa.
    2. 🟣 **Férová tržní cena**: Medián aktuální nabídky na trhu (výchozí zvolená hodnota).
    3. 🟢 **Prémiový stav (+10 %)**: Pro zboží v záruce, kompletním balení nebo bezvadném stavu.
  - Tlačítko **„Přepočítat trh“** pro okamžité přehodnocení cen po změně názvu či parametrů.
- **Věcný inženýrský popis bez hvězdiček a klišé (Clean Plaintext):**
  - AI generuje strukturovaný, věcný a profesionální text bez nepodporovaných markdown hvězdiček (`*`, `**`).
  - Odrážky jsou formátovány jako čisté pomlčky (`- `), sekce nadepsány velkými písmeny (`PARAMETRY:`, `STAV:`, `PŘÍSLUŠENSTVÍ:`).
  - Vždy zakomponovány solidní informace o možnostech osobního předání a bezpečné přepravě.
  - Žádný laciný marketingový balast typu *"TOP STAV!!!!"* nebo *"NEVÁHEJTE!!!"*.
- **Výběr titulní fotografie:**
  - AI doporučí fotografii s nejlepším úhlem a čistým pozadím (označí ji hvězdičkou).
  - Robot Playwright zajistí, že tato fotografie bude na Bazoši nahrána na prvním místě.

---

### 2. Správa a životní cyklus inzerátů
Aplikace rozděluje položky do logických přehledných sekcí:
- **Aktivní inzeráty:** Živé inzeráty vystavené na portálech s počtem zhlédnutí, datem a přímým odkazem.
- **Věci k prodeji:** Koncepty, položky k nafocení, expirované nabídky a inzeráty připravené k opětovnému vystavení.
- **Prodané věci:** Historie úspěšně realizovaných prodejů se statistikou zisku.
- **Vyloučení fotografií:** Možnost kliknutím na náhled vyřadit konkrétní fotku (např. rozmazaný detail), aniž by bylo nutné ji mazat z disku.

---

### 3. Automatický refresh na pozadí & SMS Guard
- Na pozadí běží bezpečný worker, který v nastavených intervalech (výchozí 12 hodin) kontroluje platnost a počet zhlédnutí inzerátů.
- **SMS Guard:** Pokud Bazoš při obnovení platnosti vyžaduje SMS ověření, worker se bezpečně zastaví a v aplikaci zobrazí varovný banner. Tím zamezí blokaci telefonního čísla nebo vyčerpání SMS limitu.

---

### 4. Živý prohlížeč (noVNC integrace)
- Přímo v záložce *Živý prohlížeč* má uživatel k dispozici noVNC okno streamující virtuální obrazovku prohlížeče Playwright.
- V případě potřeby (např. SMS ověření nebo CAPTCHA) může uživatel jedním kliknutím zapnout interaktivní režim a kód zadat přímo bez nutnosti otevírat externí nástroje.

---

### 5. Nenásilné aktualizace a integrace s TrueNAS SCALE
- **Nenásilné notifikace:** Místo rušivých celoobrazovkových bannerů aplikace informuje o nové verzi elegantním odložitelným toastem a decentním widgetem v zápatí sidebaru.
- **Transparentní kontrola:** Dialog stavu verze zobrazuje přesné srovnání nainstalovaného a dostupného git commit hashe, zprávu posledního commitu a přímý odkaz na GitHub Diff.
- **1-Click TrueNAS Upgrade:** Uživatelé provozující aplikaci na TrueNAS SCALE mohou provést okamžitý restart a stažení nového image jedním kliknutím z webového rozhraní.
