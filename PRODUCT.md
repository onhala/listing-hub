# 📦 Produktová dokumentace: Listing Hub & AI Editor

**Listing Hub** je moderní webové řídicí centrum navržené pro automatizovanou, efektivní a bezpečnou správu inzerce na českých inzertních portálech (primárně **Bazoš.cz** s architekturou připravenou pro **Aukro.cz**).

Aplikace radikálně zjednodušuje prodej vybavení z domácnosti, dílny či firmy díky kombinaci multimodální umělé inteligence, živého tržního radaru a asistované automatizace prohlížeče (Human-in-the-Loop).

---

## 🎯 Produktová vize: „Drop & Sell“

Tradiční tvorba inzerátu na Bazoši je zdlouhavá a plná třecích ploch:
- Manuální vymýšlení poutavého nadpisu tak, aby nepřekročil striktní limit 50 znaků.
- Zdlouhavé luštění technických parametrů a přepisování výrobních štítků.
- Zkoumání konkurenčních cen na Bazoši a Sbazaru pro nastavení férové ceny.
- Nekonečné formuláře, nahrávání a přerovnávání fotografií.
- Riziko nechtěného vymazání celého formuláře při změně kategorie na Bazoši.

**Listing Hub přináší koncept „Drop & Sell“:**
Uživateli stačí vzít telefon, nafotit prodávanou věc ze všech úhlů (včetně štítku a příslušenství) a přetáhnout fotky do aplikace (případně vložit přes `Cmd+V`). O vše ostatní se během **2 sekund** postará multimodální model **Google Gemini 2.5 Flash** napojený na živý tržní cenový radar.

> **Měřitelný přínos:** Doba přípravy a vystavení inzerátu se zkracuje z původních 5–15 minut na **pouhých 20 sekund**.

---

## 🚀 Klíčové uživatelské scénáře a inovace

### 1. AI Vision Průvodce vystavením nového inzerátu
- **Univerzální nahrání fotek:** Drag & Drop souborů, klasický výběr i přímé vložení ze schránky (`Ctrl+V` / `Cmd+V`).
- **Inteligentní extrakce detailů:**
  - Přesné rozpoznání značky, modelu a sériového/produktového čísla ze štítku.
  - Vizuální vyhodnocení stavu (oděrky, opotřebení, kompletnost).
  - Detekce příslušenství (originální obal, nabíječka, kufřík, kabely).
- **Optimalizované nadpisy s vysokým CTR:**
  - AI vygeneruje 3 až 5 atraktivních variant nadpisu.
  - Garance limitu do 50 znaků s vizuálním počítadlem (`42/50 znaků`) a backendovou ochranou proti oříznutí.
  - Výběr a dosazení nadpisu jedním kliknutím na interaktivní čip.
- **Multi-Source tržní cenový radar (Bazoš + Sbazar + Web + Gemini):**
  - Okamžitý výpočet mediánu cen s automatickým vyloučením vlastního inzerátu ze srovnání.
  - Tři doporučené cenové hladiny:
    1. 🔴 **Rychlý prodej (-10 %)**: Pro okamžité uvolnění místa.
    2. 🟣 **Férová tržní cena**: Reálný medián aktuální nabídky na trhu (výchozí volba).
    3. 🟢 **Prémiový stav (+10 %)**: Pro zboží v záruce či kompletním balení.
  - Tlačítko **„Přepočítat trh“** pro okamžité přecenění po změně názvu či parametrů.
- **Věcný inženýrský popis (Clean Plaintext Standard):**
  - Striktní eliminace markdownových hvězdiček (`*`, `**`), které Bazoš nepodporuje a zobrazuje jako nečistý text.
  - Strukturované odrážky pomlčkami (`- `) a jasně oddělené sekce velkými písmeny (`PARAMETRY:`, `STAV:`, `PŘÍSLUŠENSTVÍ:`).
  - Přizpůsobený kontext prodejce (lokality osobního předání, šablony pro Zásilkovnu/Balíkovnu).
- **Výběr titulní fotografie:**
  - AI vyhodnotí nejlepší úhel a čistotu pozadí a označí hlavní fotografii hvězdičkou.
  - Robot Playwright zajistí, že tato fotografie bude na Bazoši nahrána na prvním místě.

---

### 2. Ochrana proti promazání formuláře (Upfront Rubrika Confirmation)
Na Bazoš.cz způsobuje změna rubriky (či domény jako `dum.bazos.cz` -> `stroje.bazos.cz`) kompletní znovunačtení stránky, což u běžných nástrojů vede k nevratnému smazání všech vyplněných textů a nahraných fotek.

- **Jak to řeší Listing Hub:**
  - Před spuštěním robota aplikace otevře **potvrzovací modál rubriky**.
  - Systém podle klíčových slov a kategorie inzerátu automaticky předvybere správnou rubriku (např. *zahradní technika* -> `dum.bazos.cz`, *počítače* -> `pc.bazos.cz`, *nářadí* -> `stroje.bazos.cz`).
  - Uživatel cílovou sekci potvrdí nebo upraví jedním kliknutím.
  - Robot poté otevírá Bazoš přímo na správné adrese – **žádná data se neztratí a formulář se nikdy nepromaže**.

---

### 3. Dvoufázové vystavování s živou kontrolou (Safe Prefill & Live Review)
Listing Hub kombinuje rychlost robotické automatizace s jistotou lidského dohledu (Supervised Copilot):

- **Fáze 1: Bezpečné předvyplnění (Autopilot)**:
  - Playwright otevře Bazoš v zabezpečené relaci a automaticky vyplní veškerá textová pole, kontakty, heslo a nahraje fotky.
  - Robot se před odesláním bezpečně zastaví ve stavu `ready_for_review`.
- **Fáze 2: Živá kontrola a potvrzovací banner (Human-in-the-Loop)**:
  - Uživatel je automaticky přepnut do záložky **Živý prohlížeč** s interaktivním screencastem.
  - V záhlaví se zobrazí zřetelný stavový banner:
    > *„Formulář inzerátu byl předvyplněn! Zkontroluj údaje na obrazovce, v prohlížeči klikni na Odeslat a poté potvrď zde.“*
  - Uživatel má plnou kontrolu (může v prohlížeči cokoliv upravit nebo vyřešit SMS/CAPTCHA) a klikne na Bazoši na *Odeslat*.
  - Následně klikne na banneru na **„Potvrdit odeslání“**. Systém zkontroluje úspěšné založení inzerátu, převezme novou živou URL (`/inzerat/<id>/`) a uloží inzerát do databáze jako aktivní.
  - V případě pochybností lze akci tlačítkem **„Zrušit akci“** čistě přerušit bez nechtěného publikování.

---

### 4. Správa inzerátů a kompletní životní cyklus

Aplikace organizuje inzeráty do logických kategorií odpovídajících reálnému životnímu cyklu:

| Stav inzerátu | Kde se nachází | Popis stavu |
| :--- | :--- | :--- |
| **Koncept (Draft)** | *Věci k prodeji* | Položka vytvořená přes Drop & Sell, připravená s texty a fotkami, zatím nevystavená online. |
| **Předvyplňování** | *Živý prohlížeč* | Běžící robot Playwright na pozadí, streamovaný do interaktivního plátna. |
| **Ke kontrole** | *Živý prohlížeč* | Formulář na Bazoši je vyplněn, čeká na schválení uživatelem a potvrzení bannerem. |
| **Aktivní** | *Aktivní inzeráty* | Živý inzerát na Bazoši s počtem zhlédnutí, dny do expirace a přímým odkazem. |
| **Vyžaduje SMS** | *Varovný banner v UI* | Bazoš vyžaduje ověření telefonního čísla. Worker se zastavil a čeká na intervenci. |
| **Prodané** | *Prodané věci* | Realizovaný prodej se statistikou zisku, archivovaný pro účetnictví a exporty. |
| **Smazáno** | *Odstraněno* | Vymazáno z databáze a portálů podle zvolené úrovně mazání. |

- **Vyloučení fotografií:** Možnost kliknutím na náhled vyřadit konkrétní fotku (např. méně zdařilý detail), aniž by bylo nutné mazat soubor z disku.

---

### 5. Víceúrovňové mazání inzerátů a hygiena úložiště

Při mazání inzerátu nabízí Listing Hub inteligentní kontextové možnosti podle toho, zda je inzerát publikován, a umožňuje bezpečnou očistu disku:

1. **Mazání konceptů (Draft Cleanup):**
   - U nevystavených inzerátů provede systém okamžitý čistý výmaz z lokální SQLite databáze bez spouštění externích robotů.
2. **Volby pro publikované inzeráty:**
   - 🔴 **Smazat z Bazoše i z aplikace (Doporučeno):** Robot Playwright se pomocí uloženého hesla přihlásí na Bazoš, inzerát smaže online a následně jej kaskádově odstraní z lokální databáze.
   - ⚪ **Smazat pouze z této aplikace:** Odstraní záznam pouze z lokální databáze; inzerát na Bazoši zůstane aktivní pro ruční dožití.
3. **Volitelná likvidace lokálních fotografií:**
   - Zaškrtávací volba *„Smazat také složku s lokálními fotografiemi na disku“* uvolní místo na disku/NAS serveru.
4. **Bezpečnostní ochrana proti Path Traversal (`safe_delete_photos_dir`):**
   - Striktní validace cest v Pythonu ověřuje, že mazaný adresář leží výhradně uvnitř složky `photos/` a nerovná se kořenovému adresáři. Jakýkoliv pokus o podstrčení relativní či systémové cesty (`../`) je zablokován.

---

### 6. Automatický refresh na pozadí, SMS Guard & iCal kalendář
- **Periodický refresh:** Worker na pozadí v nastavených intervalech (výchozí 12 hodin) aktualizuje počty zhlédnutí a kontroluje platnost inzerátů.
- **SMS Guard:** Pokud Bazoš při obnovení platnosti vyžaduje SMS ověření, proces se okamžitě bezpečně zastaví a v aplikaci zobrazí červený varovný banner. Tím zamezí blokaci telefonního čísla nebo vyčerpání SMS limitu.
- **iCal / Google Kalendář synchronizace:** Přímý Webcal feed generuje celodenní události v den 60denní expirace inzerátů na Bazoši s předstihem 3 dnů a přímými prolinky do aplikace.

---

### 7. Živý prohlížeč (noVNC & Screencast integrace)
- Přímo v záložce *Živý prohlížeč* má uživatel k dispozici noVNC / Screencast okno streamující virtuální obrazovku prohlížeče Playwright.
- Uživatel může kdykoliv převzít řízení (klikání, psaní, skrolování kolečkem i postranní lištou) pro zadání SMS kódu, řešení CAPTCHA či finální odeslání inzerátu.

---

### 8. AI Bokeh & SPZ Editor fotografií
- **Automatický Bokeh efekt:** Oddělení popředí prodávaného předmětu od rušivého pozadí (garáž, dílna) s přirozeným gradientem.
- **Anonymizace citlivých údajů:** Interaktivní rozostření SPZ vozidel, výrobních sériových čísel či obličejů před vystavením.

---

### 9. Nenásilné aktualizace a integrace s TrueNAS SCALE
- **Nenásilné notifikace:** Decentní odložitelný toast a widget v patičce sidebaru namísto rušivých dialogů.
- **Transparentní kontrola:** Srovnání nainstalovaného a dostupného git commit hashe s přímým odkazem na GitHub Compare Diff.
- **1-Click TrueNAS Upgrade:** Uživatelé provozující aplikaci na TrueNAS SCALE mohou provést okamžitý restart a stažení nového kontejneru jedním kliknutím.
