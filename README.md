# 🤖 Listing Hub & AI Editor v3.11.0

Prémiové interaktivní webové řídicí centrum pro kompletní správu inzerce na portálech Bazoš.cz, Facebook Marketplace, Sbazar.cz, Vinted a Aukro.cz, s integrovaným asistentem pro ruční vystavení a balíčky fotek (ZIP), živým noVNC prohlížečem, pokročilým Multi-Source tržním cenovým radarem (Bazoš + Sbazar + Web), AI Gemini Vision poradcem pro fotky a čisté popisy bez markdownu, plně konfigurovatelným kontextem prodejce (Český Krumlov / České Budějovice), AI Bokeh/SPZ editorem fotografií, exekutivním finančním dashboardem prodaných položek s atribucí kanálů a automatickou synchronizací do Google Kalendáře.

---

### 📚 Dokumentace projektu
- 📦 **[Produktová dokumentace (PRODUCT.md)](PRODUCT.md)**: Uživatelská příručka, koncept „Drop & Sell“, workflow a hodnota pro prodejce.
- 🛠️ **[Vývojářská příručka (DEVELOPMENT.md)](DEVELOPMENT.md)**: Architektura aplikace, REST API specifikace, lokální setup a unit testování.
- 🐳 **[Produkční nasazení (DEPLOYMENT.md)](DEPLOYMENT.md)**: Provoz v Dockeru, TrueNAS SCALE, ZFS oprávnění a Nginx reverzní proxy.

---

## 🚀 Hlavní funkce

1. **Moderní Web GUI a Taby (`templates/index.html`)**:
   - **Aktivní inzeráty**: Přehled živých inzerátů z Bazoše se statistikami zhlédnutí, dny od vystavení a počtem fotek.
   - **Věci k prodeji**: Sekce pro expirované věci, koncepty (drafty) a položky, které se zrovna nenabízí aktivně.
   - **Prodané věci**: Kompletní historie prodejů s **Manažerským dashboardem a Executive statistikami** (celkem prodáno v ks, realizovaný zisk a tržby v Kč, průměrná cena položky).
   - **Živý prohlížeč (VNC & Screencast)**: Integrované interaktivní okno přímo v aplikaci pro sledování práce robota na Bazoši a bezpečné jednorázové zadání SMS kódu.
   - **Nastavení**: Plně grafická konfigurace uživatelského profilu, výchozího hesla pro inzeráty, Gemini AI modelu a iCal kalendáře.

2. **Dvoufázové neblokující vystavování (Two-Phase Posting) & Playwright 30s Timeout**:
   - **Fáze 1 (Automatické předvyplnění)**: Robot Playwright na pozadí otevře správnou sekci Bazoše, vyplní veškeré texty, kontaktní údaje, heslo (`heslobazar`), podkategorii a nahraje fotografie. Ihned poté uvolní proces a v aplikaci aktivuje **Revizní banner**.
   - **Fáze 2 (Kontrola a potvrzení)**: Uživatel v živém prohlížeči inzerát zkontroluje, klikne na Bazoši na *Odeslat* a v Listing Hubu stiskne tlačítko **Potvrdit odeslání** (`POST /api/action/confirm`). Systém ověří publikování, získá trvalou URL inzerátu a atomicky jej v DB přepne mezi aktivní.
   - **Optimalizovaný timeout**: Výchozí timeout Playwright operací je sjednocen na 30 sekund s průběžným odbavováním událostí na dedikovaném worker vlákně.

3. **Kompletní podpora všech 20 rubrik Bazoše & AI doporučování (Bazoš Subdomains)**:
   - **Plné pokrytí všech 20 rubrik**: Kompletní integrace všech specializovaných subdomén portálu Bazoš.cz:
     - `deti.bazos.cz` (Děti a hračky), `dum.bazos.cz` (Dům a zahrada), `nabytek.bazos.cz` (Nábytek), `elektro.bazos.cz` (Elektro a spotřebiče), `sport.bazos.cz` (Sport a outdoor), `auto.bazos.cz` (Auto), `motorky.bazos.cz` (Motorky a čtyřkolky), `stroje.bazos.cz` (Stroje a dílna), `pc.bazos.cz` (PC a počítače), `mobil.bazos.cz` (Mobily a chytré hodinky), `foto.bazos.cz` (Foto a kamery), `hudba.bazos.cz` (Hudba a nástroje), `obleceni.bazos.cz` (Oblečení a obuv), `knihy.bazos.cz` (Knihy a časopisy), `zvirata.bazos.cz` (Zvířata a chovatelství), `vstupenky.bazos.cz` (Vstupenky a lístky), `reality.bazos.cz` (Reality a nemovitosti), `prace.bazos.cz` (Práce a brigády), `sluzby.bazos.cz` (Služby a řemesla), `ostatni.bazos.cz` (Ostatní).
   - **Inteligentní AI & heuristický ranking (`POST /api/ai/suggest-rubrika`)**: Algoritmus analyzuje titulek, popis, kategorii a případnou stávající URL inzerátu. Využívá vážené bodování klíčových slov (titulek váha 90, popis váha 20, shoda v kategorii váha 80, původní URL váha 1000) a speciální regex disambiguaci (např. motorky vs. elektromotory), seřazuje všech 20 rubrik podle relevance a doporučuje top 3 volby s vysvětlením důvodu.
   - **Dvoufázový protokol proti smazání formuláře**: Změna rubriky na Bazoši vyvolává tvrdý reload celé stránky, který maže všechna předvyplněná pole a nahrané fotky. Směrováním bota přímo na cílovou subdoménu (`https://{target_domain}/pridat-inzerat.php`) je reload i riziko ztráty dat 100% eliminováno.
   - **REST API pro rubriky**: Endpoint `GET /api/bazos/rubriky` vrací kompletní katalog rubrik včetně ikon a českých názvů.

4. **Dávkové / hromadné znovuvystavení inzerátů (Batch Reposting)**:
   - **Hromadný výběr položek**: Tlačítko pro aktivaci dávkového režimu v záložkách *Aktivní inzeráty* i *Věci k prodeji*, výběr jednotlivých inzerátů pomocí checkboxů na kartách a tlačítko *Vybrat vše* s plovoucí akční lištou a počítadlem vybraných kusů.
   - **Přehledný dávkový dialog (`batch-repost-modal`)**: Interaktivní správa před spuštěním dávky. U každého vybraného inzerátu lze v přehledné tabulce:
     - Individuálně upravit novou nabídkovou cenu (včetně přecenění / slevy ležáků).
     - Individuálně změnit cílovou rubriku z rozbalovacího seznamu všech 20 rubrik Bazoše.
     - Kdykoliv konkrétní inzerát z dávky odebrat jedním kliknutím.
   - **Postupné bezpečné odbavení fronty (Sequential Queue Execution)**:
     - Běh na pozadí s přehledným plovoucím indikátorem fronty (`batch-queue-indicator`) zobrazujícím aktuální položku `X/N` a její název.
     - Možnost problematický inzerát v průběhu přeskočit tlačítkem *Přeskočit položku* (`btn-batch-skip`) a pokračovat na další.
     - Možnost celou dávku kdykoliv bezpečně zastavit tlačítkem *Zrušit dávku* (`btn-batch-cancel`).
     - Robot Playwright postupně provede bezpečné topování: asynchronní smazání starého inzerátu online přes heslo a vystavení nového s aktualizovanou cenou a rubrikou.

5. **Správa prodaných inzerátů (Sold Archive & Analytics)**:
   - **Jednoduché označení prodeje**: Tlačítko *Prodáno* přímo na kartě inzerátu, v modalu smazání (Choice Cards) i v patičce detailního editoru (`POST /api/listings/<listing_id>/mark_sold`).
   - **Finanční evidence a real-time kalkulace**: Dialog umožňuje zadat reálnou prodejní cenu (`sale_price`), datum obchodu (`sold_at`) a interní poznámku k nákupu (`sold_notes`, např. jméno kupujícího, poskytnutá sleva). Rozhraní v reálném čase vizuálně indikuje odchylku od původní ceny (zelený odznak pro plnou cenu, červený pro slevu, modrý pro přirážku).
   - **Automatické online stažení z Bazoše**: Volitelný checkbox *„Smazat inzerát na Bazoši (pokud je vystaven)“* automaticky spustí Playwright workera na pozadí, který inzerát na Bazoši přes uložené heslo vymaže, aby po realizovaném prodeji nechodily další zprávy a hovory.
   - **Manažerský dashboard / Executive statistiky (`GET /api/listings/sold_stats`)**: V záložce *Prodané věci* je integrován živý finanční a výkonnostní přehled:
     - 🤝 **Celkem prodáno**: Celkový počet úspěšně zobchodovaných položek (ks).
     - 💰 **Realizovaný zisk a tržby**: Souhrnná částka z reálně uskutečněných prodejů v Kč.
     - 📊 **Průměrná realizovaná cena**: Průměrná výše tržby na jeden prodaný inzerát.
     - 🏷️ **Průměrná sleva & úspěšnost**: Vizuální indikace slevy a marže u jednotlivých transakcí.
   - **Strukturovaná karta prodané položky**: Zelený odznak `PRODÁNO`, realizovaná částka, odchylka v %, datum obchodu a kurzívou zvýrazněná interní poznámka.
   - **100% Reverzibilita („Vrátit k prodeji“ - `POST /api/listings/<listing_id>/restore_sold`)**: Při odstoupení kupujícího nebo chybě stačí kliknout na *Vrátit k prodeji* – položka se vrátí mezi *Věci k prodeji*, prodejní pole se vynulují a inzerát je ve stavu `Expirováno` připraven k okamžitému znovuvystavení.

6. **Dynamické načítání Google AI (Gemini) modelů z uživatelského účtu**:
   - **Dynamické zjištění modelů (`GET /api/ai/models`)**: Aplikace se dotazuje přímo na Google Generative Language API (`/v1beta/models`) a načítá modely aktivní na uživatelském účtu s podporou parametru `force=true` pro okamžité obnovení.
   - **Automatické nahrazení ukončených modelů**: Modely vyřazené Googlem (např. `gemini-2.5-pro`) jsou automaticky detekovány a v rozhraní nahrazeny doporučeným modelem `gemini-2.5-flash` nebo preview verzí pro hlubokou analýzu `gemini-3.1-pro-preview`.
   - **Inteligentní sanitace katalogu**: Zobrazeny jsou pouze modely podporující metodu `generateContent`. Nepoužitelné embedding, imagen či interní eval modely jsou automaticky odfiltrovány.
   - **Robustní offline fallback**: Pokud není zadán API klíč, nastane výpadek sítě nebo Google API vrátí chybu, systém bezpečně přepne na vestavěný seznam `DEFAULT_FALLBACK_MODELS`.
   - **In-memory cache**: Seznam modelů je ukládán do mezipaměti na 15 minut pro minimalizaci latence a šetření limitů Google API.

7. **Řazení a filtrace inzerátů (Sorting & Real-time Search)**:
   - **Kompletní sada kritérií řazení**: Dostupné v záložkách *Aktivní inzeráty*, *Věci k prodeji* i *Prodané věci*:
     - **Podle data vystavení / data prodeje**: Od nejnovějšího po nejstarší (`sold_at_desc`) i vzestupně (`sold_at_asc`).
     - **Podle stáří ve dnech**: Od nejstarších ležáků k přecenění (`days_old_desc`) po čerstvě vystavené (`days_old_asc`).
     - **Podle ceny**: Od nejdražšího (`price_desc`) po nejlevnější (`price_asc`).
     - **Podle zhlédnutí**: Podle zájmu kupujících (`views_desc`).
     - **Abecedně**: Podle názvu položky (`title_asc`).
   - **Okamžité vyhledávání (Instant Search)**: Dynamické vyhledávací pole v nástrojové liště okamžitě filtruje zobrazené karty podle shody v titulku, popisu, ceně či kategorii bez nutnosti obnovovat stránku.

8. **Bezpečné mazání inzerátů s Choice Cards & úklidem fotografií**:
   - **Volba rozsahu smazání**: U publikovaných inzerátů si uživatel v modalu vybere mezi *Smazat pouze z databáze*, *Smazat z Bazoše i databáze* (s automatickým vyplněním hesla pro výmaz na Bazoši) nebo přímým *Označit jako prodané*.
   - **Úklid disku**: Volitelný checkbox *Smazat také lokální složku s fotkami* (`delete_photos: true`) spolehlivě uvolní místo na disku.
   - **Bezpečnostní pojistka**: Mazání složek probíhá přes `safe_delete_photos_dir()` s kontrolou relativních cest a striktní ochranou proti Path Traversal.

9. **Multi-Source Tržní Cenový Radar (Bazoš + Sbazar + Web + Gemini)**:
   - **Komplexní přehled trhu**: Automatické prohledávání Bazoš.cz, veřejného API Sbazar.cz a webu pro zjištění reálných tržních cen z druhé ruky.
   - **Vyloučení vlastního inzerátu**: Cenový poradce chytře vyřazuje ze srovnání tvůj vlastní inzerát.
   - **Tři cenové úrovně**: Výpočet hladin *Rychlý prodej (-10 %)*, *Férová mediánová cena* a *Prémiový stav (+10 %)*.
   - **Inteligentní AI odhad**: Pokud na inzertních serverech chybí nabídky, Gemini AI doplní tržní ocenění nového i použitého kusu.
   - **Tlačítko „Přepočítat trh“**: V průvodci novým inzerátem lze kdykoliv po úpravě titulku jedním kliknutím bleskově ověřit aktuální ceny konkurence.

10. **Čisté inženýrské popisy pro Bazoš (Clean Plaintext Standard)**:
    - **Striktní eliminace hvězdiček**: Popisy generované AI neobsahují žádné nepodporované markdown hvězdičky (`*`, `**`).
    - **Přehledná struktura**: Odrážky s pomlčkou (`- `) a sekce oddělené velkými písmeny (`PARAMETRY:`, `STAV:`, `PŘÍSLUŠENSTVÍ:`).
    - **Plně nastavitelný kontext prodejce & dopravy**: V Nastavení lze kdykoliv upravit styl prodejce (inženýrský, férový, bez slopu) i šablonu osobního předání a odeslání přes Zásilkovnu/Balíkovnu (výchozí: Český Krumlov / České Budějovice).

11. **AI Bokeh & SPZ Editor fotografií (`rembg` + Pillow)**:
    - **Profesionální Bokeh efekt**: Automatická detekce popředí předmětu a plynulé rozostření pozadí s přirozeným gradientem podlahy (Jemné / Střední / Silné).
    - **Zamazání citlivých údajů**: Interaktivní nástroj pro tažení myší přes SPZ automobilů, sériová čísla či obličeje.
    - **Porovnání s originálem & Přímý zápis**: Tlačítko pro okamžité srovnání s původním snímkem a uložení přímo do složky inzerátu nebo průvodce.

12. **AI Vision-First tvorba inzerátu ("Drop & Sell")**:
    - **Blesková analýza z fotek**: Přetáhněte fotky (drag & drop), vyberte ze souborů nebo vložte přímo ze schránky (`Cmd+V`).
    - Multimodální model **Gemini 2.5 Flash** z fotek rozpozná značku, přesný model, vizuální stav, příslušenství a klíčové parametry.
    - **Varianty nadpisů s vysokým CTR**: AI navrhne 3–5 úderných variant nadpisů s garantovanou délkou do 50 znaků. Výběr jedním kliknutím.
    - **Výběr hlavní fotky**: AI doporučí nejlepší fotku na úvod inzerátu (označení hvězdičkou), kterou Playwright nahraje jako první.

13. **Google Kalendář & iCal Synchronizace (RFC 5545 Webcal)**:
    - **Automatický odběr termínů vypršení**: Přímý Webcal/iCal feed zabezpečený privátním tokenem (`/api/calendar/feed.ics?token=...`).
    - **60denní cyklus Bazoše**: Celodenní událost v den expirace s notifikacemi 3 dny předem a v den expirace.
    - **Přímé prolinkování**: Každá událost obsahuje přímý odkaz na Bazoš i lokální Listing Hub pro okamžité obnovení či editaci.
    - **Archiv prodejů**: Prodané věci zůstávají v kalendáři jako vizuální archiv (`✅ PRODÁNO: ...`).

14. **Automatický refresh na pozadí (Background Worker & SMS Guard)**:
    - Daemon vlákno periodicky aktualizuje stavy, platnost a zhlédnutí inzerátů z Bazoše.
    - **SMS Guard**: Pokud Bazoš při refreshu vyžaduje SMS, proces se čistě zastaví, stav se přepne na `"needs_sms"` a v UI vyskočí červený varovný banner. Další SMS na pozadí se neodesílají, dokud uživatel neprovede ruční přihlášení.
    - **Timing**: Interval auto-refreshu je plně nastavitelný přímo v Nastavení (od 15 minut do 24 hodin).
    - **Zámek procesu**: Bezpečné sdílení Playwright procesu k zamezení konfliktů mezi pozadím a ručními úpravami.

15. **Nenásilné sledování verzí & Inspektor (GitHub Diff & 1-Click Update)**:
    - Interaktivní widget v zápatí sidebaru zobrazuje verzi a zkrácený git commit hash (`v3.8.8 • [hash]`).
    - Nenásilný plovoucí toast s možností odložení do `localStorage` (žádné rušivé celoobrazovkové bannery).
    - Dialog srovnání nainstalované verze a hashe proti GitHubu s přímým odkazem na diff změn a 1-click upgradem na TrueNAS.

16. **Správa a vyloučení fotografií**:
    - V detailu inzerátu se zobrazují Base64 náhledy všech fotek z lokální složky.
    - Kliknutím na fotku ji lze označit jako vyloučenou – Playwright ji při vystavování přeskočí.
    - Karta inzerátu zobrazuje stav např. `📷 4/5 fotek`.

17. **Čítače a ochrana nadpisů (Limit 50 znaků)**:
    - Real-time čítače s varovným barevným tónem (žlutá/červená) u políček nadpisů.
    - Automatická backend sanitace zkracuje nadpisy na max 50 znaků k zamezení ořezání na straně Bazoše.

18. **AI Agent Interface (Antigravity Skill, FastMCP & CLI)**:
    - **Nativní podpora pro agenty**: Dedikované REST API (`/api/agent/v1/*`), FastMCP stdio server (`scripts/listing_hub_mcp.py`) a CLI klient (`scripts/listing_hub_cli.py`).
    - **Dvoufázový Human-in-the-Loop protokol**: Robot předvyplní formulář na Bazoši (Fáze 1) a předá živý screencast uživateli. Teprve po odeslání potvrdí a aktivuje inzerát (Fáze 2).
    - **Architektura & Use Casy**: Kanonický slovník v [CONTEXT.md](CONTEXT.md), architektonická rozhodnutí v [docs/adr/](docs/adr/) a podrobné scénáře v [docs/agent_use_cases.md](docs/agent_use_cases.md).

19. **Asistent ručního zveřejnění & Multi-portál evidence (Cross-Portal Publishing)**:
    - **Podpora dalších inzertních platforem**: Evidence a rychlé vystavení na **Facebook Marketplace**, **Sbazar.cz**, **Vinted**, **Aukro.cz**, ruční **Bazoš** i **vlastní platformy**.
    - **1-Click Copy Asistent**: Okamžité zkopírování nadpisu, ceny a formátovaného popisu do schránky jedním kliknutím bez nutnosti přepínat okna.
    - **📥 Stažení fotek v ZIP archivu (`GET /api/photos/<listing_id>/zip`)**: Vygeneruje a bleskově stáhne všechny fotky daného inzerátu v jednom přehledně očíslovaném ZIP balíčku pro snadné drag & drop nahrání na externí weby.
    - **Barevné odznaky portálů**: Karty inzerátů vizuálně indikují aktivní publikace (modrý FB, červený Sbazar, tyrkysový Vinted, fialový Bazoš, žluté Aukro) s možností prokliku na živý inzerát nebo rychlého doplnění URL (`+URL`).

20. **Atribuce prodejních kanálů (Sales Attribution)**:
    - Výběr kanálu v modalu *Prodáno* (*Bazoš.cz*, *FB Marketplace*, *Sbazar.cz*, *Vinted*, *Aukro.cz*, *Osobní předání*, *Jiný kanál*).
    - Zobrazení realizovaného kanálu přímo na kartě prodané položky a agregace tržeb v databázi (`sold_channel`).

21. **Ochrana soukromí fotografií & SMS Relay Webhook**:
    - **EXIF Sanitace & Auto-Orient**: Odstranění GPS souřadnic domova a metadat z fotografií při nahrání s automatickým narovnáním rotace z mobilních telefonů.
    - **Webhook pro SMS ověření (`POST /api/sms/relay`)**: Přijímá SMS kódy z iOS Zkratek nebo Android Taskeru a automaticky je předává Playwright robotovi.

22. **Prometheus Metriky & Monitoring v Grafaně (`GET /metrics`)**:
    - **OpenMetrics / Prometheus Exporter**: Nativní endpoint `GET /metrics` exportující metriky zhlédnutí inzerátů, trendů, expiračních lhůt, prodejních statistik a stavu workerů.
    - **Historické snapshoty zhlédnutí**: Automatické ukládání historie zhlédnutí při synchronizaci inzerátů pro sledování rychlosti růstu popularity (`listing_views_history`).
    - **Metriky úspěšnosti a fotografií**: Korelace počtu fotografií s rychlostí prodeje (`days_to_sell`, `photos_count`), hlídání expiračních lhůt (countdown do smazání Bazošem) a SMS guard monitoring.



---

## 🌐 Přehled klíčových REST API endpointů

Kompletní specifikace a parametry jsou detailně popsány ve [Vývojářské příručce (DEVELOPMENT.md)](DEVELOPMENT.md).

### Rubriky Bazoše & Doporučování
- `GET /api/bazos/rubriky` – Vrátí katalog všech 20 rubrik Bazoše s identifikátory, českými názvy a ikonami.
- `POST /api/ai/suggest-rubrika` – Doporučí nejvhodnější rubriku pro inzerát na základě analýzy titulku, popisu, kategorie a existující URL (`listing_id`, `title`, `description`, `category`, `url`).

### AI Modely & Textový Asistent
- `GET /api/ai/models` – Dynamický seznam dostupných modelů Gemini z uživatelského Google AI účtu (`api_key`, `force`), s automatickou náhradou ukončených verzí (`gemini-2.5-pro` -> `gemini-2.5-flash` / `gemini-3.1-pro-preview`) a offline fallbackem.
- `POST /api/ai/analyze-photos` – Multimodální analýza fotografií přes Gemini Flash + tržní cenový radar.
- `POST /api/ai/improve` – Jazyková korektura a úprava textu bez markdownových hvězdiček.

### Správa inzerátů & Životní cyklus
- `GET /api/listings` – Přehled inzerátů rozdělených podle stavů (`active`, `unsold`, `sold`).
- `POST /api/listings/save` – Uložení změn inzerátu s automatickým zkrácením titulku do 50 znaků.
- `POST /api/listings/<listing_id>/mark_sold` – Označení inzerátu jako prodaného (`sale_price`, `sold_at`, `notes`, `sold_channel`, `delete_on_bazos`).
- `POST /api/listings/<listing_id>/restore_sold` – Vrácení prodaného inzerátu zpět mezi neprodané koncepty.
- `GET /api/listings/sold_stats` – Souhrnné statistiky realizovaných prodejů (`total_sold`, `total_profit`, `avg_price`).
- `POST /api/listings/delete` – Bezpečné smazání inzerátu s volitelným úklidem fotek na disku.

### Multi-portál Evidence & Asistence
- `POST /api/listings/<listing_id>/publish-manual` – Zaznamená ruční publikaci inzerátu na externím portálu (`portal_name`, `portal_label`, `url`, `notes`).
- `POST /api/listings/<listing_id>/portal-url` – Rychlé doplnění nebo aktualizace URL odkazu na živý inzerát pro daný portál.
- `GET /api/photos/<listing_id>/zip` – Zabalí a stáhne všechny fotografie inzerátu v jediném seřazeném ZIP balíčku.
- `POST /api/sms/relay` – Webhook pro příjem a automatické vyplnění SMS ověřovacího kódu z mobilu (`text`, `code`, `token`).

### Automatizace & Dávkové akce (Playwright)
- `POST /api/action/<action_type>` – Spuštění úlohy na pozadí (`post`, `edit_price`, `delete`, `repost`).
- `GET /api/action/status` – Aktuální stav workeru (`IDLE`, `RUNNING`, `READY_FOR_REVIEW`, `COMPLETED`).
- `POST /api/action/confirm` – Potvrzení odeslání inzerátu (Fáze 2 HITL protokolu).
- `POST /api/action/cancel` – Zrušení běžící akce a uvolnění prohlížeče.
- `POST /api/action/repost_with_new_price` – Přenastavení ceny a bezpečné znovuvystavení inzerátu (topování).

### Metriky & Monitoring (Prometheus)
- `GET /metrics` – Nativní Prometheus OpenMetrics (0.0.4) formát se statistikami zhlédnutí, expirací, prodejů a stavu automatizací pro scraping TrueNAS Prometheus serverem.



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
