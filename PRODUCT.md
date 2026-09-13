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

### 2. Architektura rubrik Bazoše & Prevence reloadu formuláře (All 20 Subdomains & AI Ranking)
Na portálu Bazoš.cz je každá z hlavních tematických sekcí provozována na samostatné subdoméně (`dum.bazos.cz`, `elektro.bazos.cz`, `auto.bazos.cz` atd.). 

- **Technická podstata problému (Reload Traversal Trap):**
  Pokud uživatel otevře formulář pro přidání inzerátu na jedné subdoméně a následně v rozbalovacím seznamu zvolí jinou rubriku, JavaScript Bazoše provede okamžitý tvrdý reload celé stránky (`window.location`) na novou subdoménu. U standardních automatizačních nástrojů to vede k fatálnímu selhání: veškeré dosud předvyplněné texty, parametry a nahrané fotografie jsou nenávratně ztraceny a formulář se načte prázdný.

- **Dvoufázové řešení v Listing Hubu:**
  1. **Kompletní pokrytí všech 20 rubrik Bazoše**: Aplikace plně podporuje celý ekosystém Bazoše:
     - `deti.bazos.cz` (Děti a hračky), `dum.bazos.cz` (Dům a zahrada), `nabytek.bazos.cz` (Nábytek), `elektro.bazos.cz` (Elektro a spotřebiče), `sport.bazos.cz` (Sport a outdoor), `auto.bazos.cz` (Auto), `motorky.bazos.cz` (Motorky a čtyřkolky), `stroje.bazos.cz` (Stroje a dílna), `pc.bazos.cz` (PC a počítače), `mobil.bazos.cz` (Mobily a chytré hodinky), `foto.bazos.cz` (Foto a kamery), `hudba.bazos.cz` (Hudba a nástroje), `obleceni.bazos.cz` (Oblečení a obuv), `knihy.bazos.cz` (Knihy a časopisy), `zvirata.bazos.cz` (Zvířata a chovatelství), `vstupenky.bazos.cz` (Vstupenky a lístky), `reality.bazos.cz` (Reality a nemovitosti), `prace.bazos.cz` (Práce a brigády), `sluzby.bazos.cz` (Služby a řemesla), `ostatni.bazos.cz` (Ostatní).
  2. **AI & Heuristický Ranking (`rank_target_domains`)**: Systém ještě před startem automatizace analyzuje titulek, popis, kategorii a stávající URL inzerátu. Vážené skórování klíčových slov (titulek váha 90, popis váha 20, shoda kategorie váha 80, stávající URL váha 1000) doplněné o kontextové regex filtry (např. odlišení motocyklů od elektromotorů) vyhodnotí relevanci všech 20 rubrik a nabídne uživateli top 3 doporučení s jasným odůvodněním.
  3. **Upfront potvrzovací dialog**: Cílová rubrika je potvrzena uživatelem ještě před otevřením relace prohlížeče.
  4. **Přímé směrování bez reloadu**: Playwright robot je naveden přímo na `https://{target_domain}/pridat-inzerat.php`. K žádné změně rubriky za běhu formuláře nedochází, reload je stoprocentně eliminován a data zůstávají v naprostém bezpečí.

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

### 4. Dávkové znovuvystavení inzerátů (Batch Reposting) & Inteligentní správa fronty
Při pravidelném obnovování a topování inzerce na Bazoši eliminuje Listing Hub nutnost klikat každý inzerát jednotlivě:

- **Hromadný výběr inzerátů**:
  - Tlačítko pro aktivaci dávkového režimu přímo v záložkách *Aktivní inzeráty* i *Věci k prodeji*.
  - Výběr jednotlivých položek pomocí checkboxů na kartách inzerátů, nebo hromadné označení všech zobrazených položek tlačítkem *Vybrat vše*.
  - Plovoucí spodní lišta s počítadlem vybraných položek a tlačítkem pro otevření dávkového dialogu.
- **Interaktivní dávkový dialog (`batch-repost-modal`)**:
  - Přehledná tabulka všech vybraných položek s miniaturami fotografií.
  - **Individuální úprava ceny**: Možnost přímo v řádku tabulky přenastavit prodejní cenu (např. aplikovat slevu u dlouhodobých ležáků).
  - **Individuální volba rubriky**: Každé položce lze samostatně změnit cílovou rubriku ze všech 20 dostupných subdomén Bazoše.
  - **Snadné vyřazení**: Tlačítko pro odebrání položky z dávky před spuštěním.
- **Sekvenční bezpečné odbavení fronty (Safe Queue Runner)**:
  - Odbavení probíhá sekvenčně (jedna položka po druhé) na dedikovaném workeru, což chrání účet inzerenta před podezřením ze spamu.
  - Plovoucí stavový indikátor fronty (`batch-queue-indicator`) v záhlaví živého prohlížeče informuje o aktuálním postupu (`1/N`) a názvu zpracovávané položky.
  - Tlačítko **„Přeskočit položku“** (`btn-batch-skip`): Umožňuje přeskočit položku vyžadující dodatečné úpravy a plynule přejít na další.
  - Tlačítko **„Zrušit dávku“** (`btn-batch-cancel`): Kdykoliv čistě zastaví frontu bez rozpracovaných zbytků.
  - Robot u každé položky automaticky provede asynchronní smazání starého inzerátu na Bazoši a vystaví nový s upravenou cenou a rubrikou.

---

### 5. Správa prodaných inzerátů, Sold Archive & Executive Dashboard
Aplikace organizuje inzeráty do uceleného životního cyklu reflektujícího skutečný obchodní proces:

| Stav inzerátu | Kde se nachází | Popis stavu |
| :--- | :--- | :--- |
| **Koncept (Draft)** | *Věci k prodeji* | Položka vytvořená přes Drop & Sell, připravená s texty a fotkami, zatím nevystavená online. |
| **Předvyplňování** | *Živý prohlížeč* | Běžící robot Playwright na pozadí, streamovaný do interaktivního plátna. |
| **Ke kontrole** | *Živý prohlížeč* | Formulář na Bazoši je vyplněn, čeká na schválení uživatelem a potvrzení bannerem. |
| **Aktivní** | *Aktivní inzeráty* | Živý inzerát na Bazoši s počtem zhlédnutí, dny do expirace a přímým odkazem. |
| **Vyžaduje SMS** | *Varovný banner v UI* | Bazoš vyžaduje ověření telefonního čísla. Worker se zastavil a čeká na intervenci. |
| **Prodané (Sold)** | *Prodané věci* | Realizovaný prodej s evidencí prodejní ceny, data a poznámek. Zahrnuje Manažerský dashboard. |
| **Expirováno** | *Věci k prodeji* | Položka po vypršení 60denní platnosti nebo vrácená z prodeje, připravená k novému vystavení. |
| **Smazáno** | *Odstraněno* | Vymazáno z databáze a portálů podle zvolené úrovně mazání. |

- **Manažerský dashboard (Executive statistiky):** V záhlaví záložky *Prodané věci* je integrován přehledový panel s klíčovými metrikami prodeje v reálném čase:
  - 📦 **Celkem prodáno**: Celkový počet úspěšně zobchodovaných položek v kusech.
  - 💰 **Realizované tržby**: Souhrnná částka z reálně uskutečněných prodejů v Kč.
  - 📊 **Průměrná cena**: Průměrná výše tržby na jeden prodaný inzerát.
  - 🏷️ **Sleva / Přirážka**: Vizuální indikace cenové odchylky u každé transakce.
- **Workflow „Označit jako prodané“ (`POST /api/listings/<listing_id>/mark_sold`)**:
  - Dostupné na jeden klik z karty inzerátu, modalu mazání i detailního editoru.
  - Dialog umožňuje zadat skutečnou prodejní cenu (`sale_price`), datum obchodu (`sold_at`) a interní poznámku (`sold_notes`, např. osobní předání, sleva na dopravu).
  - Volitelné zaškrtnutí *„Smazat inzerát na Bazoši (pokud je vystaven)“* automaticky spustí asynchronního Playwright workera, který inzerát online smaže, aby prodejce po prodeji nebyl rušen dalšími telefonáty.
- **100% Reverzibilita („Vrátit k prodeji“ - `POST /api/listings/<listing_id>/restore_sold`)**:
  - Při odstoupení kupujícího stačí kliknout na *Vrátit k prodeji*.
  - Položka se vrátí do záložky *Věci k prodeji*, prodejní pole se vynulují a inzerát je připraven k okamžitému znovuvystavení.
- **Vyloučení fotografií**: Možnost kliknutím na náhled vyřadit konkrétní fotku z vystavení bez nutnosti jejího mazání z disku.

---

### 6. Dynamické načítání Google AI (Gemini) modelů & Odolnost vůči výpadkům
Aplikace přistupuje k AI modelům pružně a dynamicky namísto pevně zakódovaných názvů:

- **Dynamické zjištění modelů z účtu (`GET /api/ai/models`)**:
  - Systém volá Google Generative Language API (`/v1beta/models`) přímo s uživatelským API klíčem a zjišťuje přesný seznam modelů, které má daný účet k dispozici.
  - Podpora parametru `force=true` pro okamžité obnovení seznamu při změně klíče.
- **Automatická náhrada ukončených modelů**:
  - Google pravidelně ukončuje starší a preview modely (např. `gemini-2.5-pro`). Pokud uživatel dříve používal model, který již v jeho účtu není k dispozici, Listing Hub jej automaticky a bez pádu nahradí doporučeným modelem `gemini-2.5-flash` nebo analytickým preview modelem `gemini-3.1-pro-preview`.
- **Inteligentní sanitace katalogu**:
  - Filtrovány jsou výhradně modely podporující metodu `generateContent`. Nepoužitelné embedding modely, imagemodely nebo interní experimenty jsou z nabídky automaticky odstraněny.
- **Robustní offline fallback**:
  - Pokud není zadán API klíč, dojde k výpadku sítě nebo Google API vrátí chybu, aplikace okamžitě aktivuje ověřený lokální katalog `DEFAULT_FALLBACK_MODELS`. Rozhraní zůstává plně stabilní a informuje uživatele přehledným odznakem.
- **15minutová in-memory cache**:
  - Minimalizuje počet dotazů na Google API a šetří limity dotazů.

---

### 7. Pokročilé řazení a okamžitá filtrace inzerátů (Sorting & Real-time Search)
Pro pohodlnou správu desítek až stovek položek obsahuje rozhraní komplexní sadu nástrojů pro uspořádání:

- **Dynamická kritéria řazení**:
  - **Stáří ve dnech**: Řazení od nejstarších ležáků (`days_old_desc`) umožňuje okamžitě identifikovat položky vhodné k přecenění či slevě. Možnost řadit i od nejnovějších (`days_old_asc`).
  - **Datum prodeje / vytvoření**: Uspořádání prodaných věcí podle data obchodu (`sold_at_desc`, `sold_at_asc`).
  - **Cena**: Od nejdražších položek (`price_desc`) po nejlevnější (`price_asc`).
  - **Zhlédnutí**: Podle reálného zájmu kupujících na portálu (`views_desc`).
  - **Název**: Abecední řazení v českém jazyce (`title_asc`).
- **Okamžité fulltextové vyhledávání**:
  - Vyhledávací pole v nástrojové liště okamžitě v reálném čase filtruje zobrazené karty podle shody v titulku, popisu, ceně i kategorii.

---

### 8. Víceúrovňové mazání inzerátů a hygiena úložiště
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

### 9. Automatický refresh na pozadí, SMS Guard & iCal kalendář
- **Periodický refresh:** Worker na pozadí v nastavených intervalech (výchozí 12 hodin) aktualizuje počty zhlédnutí a kontroluje platnost inzerátů.
- **SMS Guard:** Pokud Bazoš při obnovení platnosti vyžaduje SMS ověření, proces se okamžitě bezpečně zastaví a v aplikaci zobrazí červený varovný banner. Tím zamezí blokaci telefonního čísla nebo vyčerpání SMS limitu.
- **iCal / Google Kalendář synchronizace:** Přímý Webcal feed generuje celodenní události v den 60denní expirace inzerátů na Bazoši s předstihem 3 dnů a přímými prolinky do aplikace.

---

### 10. Živý prohlížeč (noVNC & Screencast integrace)
- Přímo v záložce *Živý prohlížeč* má uživatel k dispozici noVNC / Screencast okno streamující virtuální obrazovku prohlížeče Playwright.
- Uživatel může kdykoliv převzít řízení (klikání, psaní, skrolování kolečkem i postranní lištou) pro zadání SMS kódu, řešení CAPTCHA či finální odeslání inzerátu.

---

### 11. AI Bokeh & SPZ Editor fotografií
- **Automatický Bokeh efekt:** Oddělení popředí prodávaného předmětu od rušivého pozadí (garáž, dílna) s přirozeným gradientem.
- **Anonymizace citlivých údajů:** Interaktivní rozostření SPZ vozidel, výrobních sériových čísel či obličejů před vystavením.

---

### 12. Nenásilné aktualizace a integrace s TrueNAS SCALE
- **Nenásilné notifikace:** Decentní odložitelný toast a widget v patičce sidebaru namísto rušivých dialogů.
- **Transparentní kontrola:** Srovnání nainstalovaného a dostupného git commit hashe s přímým odkazem na GitHub Compare Diff.
- **1-Click TrueNAS Upgrade:** Uživatelé provozující aplikaci na TrueNAS SCALE mohou provést okamžitý restart a stažení nového kontejneru jedním kliknutím.

---

### 13. Rozhraní pro AI agenty (Antigravity Skill & FastMCP)
- **Klientské rozhraní pro LLM:** Nativní REST API (`/api/agent/v1/*`), FastMCP stdio server a CLI klient (`listing-hub`) umožňují pokročilým agentům prozkoumávat inventář, spouštět tržní radar a připravovat inzeráty.
- **Asistované dvoufázové vystavování (HITL):** Agent bezpečně předvyplní formulář (Fáze 1) a předá řízení uživateli k vizuální kontrole na živém screencastu. Finální odeslání zůstává plně v rukou uživatele (Fáze 2).
- **Prevence chyb a detekce expirací:** Automatické upozorňování na blížící se 60denní expiraci inzerátů a doporučení cenových úprav u ležáků.

