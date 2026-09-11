# ADR 0002: Dvoufázový protokol lidského dohledu (Two-Phase Human-in-the-Loop Protocol) pro AI agenty

* **Status:** Přijato (Accepted)
* **Datum:** 2026-09-11
* **Autor:** Ondřej Hála
* **Kontext:** Listing Hub (`/Users/ondre/Projects/listing-hub`)

---

## 1. Kontext a problém

Portály pro spotřebitelskou inzerci (zejména Bazoš.cz) uplatňují přísné mechanismy detekce robotů a spamu:
1. **SMS ověření telefonního čísla:** Při zadávání nového inzerátu nebo změně parametrů je často vyžadováno ověření pomocí jednorázového SMS kódu zaslaného na telefonní číslo inzerenta.
2. **Ochrana proti banu:** Plně automatizované odesílání inzerátů bez lidského dohledu vede k vysokému riziku penalizace telefonního čísla nebo zablokování IP adresy.
3. **Zodpovědnost za obsah:** Inzeráty obsahují právně a finančně závazné údaje (prodejní cena, popis technického stavu, kontaktní údaje). AI agent nesmí finálně publikovat inzerát na veřejný trh bez explicitního schválení uživatelem.

V lidském webovém rozhraní Listing Hubu byl tento problém úspěšně vyřešen konceptem **„Dvoufázového vystavování s živou kontrolou“**:
* Fáze 1: Playwright robot předvyplní formulář a nahraje fotky, načež se zastaví ve stavu `READY_FOR_REVIEW`.
* Uživatel v záložce *Živý prohlížeč* (noVNC / CDP screencast) zkontroluje údaje, v případě potřeby vyřeší SMS kód, klikne na Bazoši na *Odeslat* a následně v aplikaci potvrdí banner.

Pro AI agenty (Antigravity) je nutné tento proces formalizovat do deterministického, neblokujícího protokolu, který zabrání zablokování agenta (deadlock / timeout), poskytne jasné stavové přechody a zaručí stoprocentní bezpečnost inzerce.

---

## 2. Rozhodnutí

Rozhodli jsme se zavést formální **Dvoufázový Human-in-the-Loop (HITL) protokol pro AI agenty**.

AI agent má striktně **zakázáno** pokoušet se o automatické dokončení odeslání inzerátu na Bazoši. Agent působí jako inteligentní autopilot (Copilot), který provede kompletní přípravu, ale předání do produkce přenechává člověku.

### Stavový diagram protokolu:

```
                  ┌──────────────────────┐
                  │      IDLE (DB)       │
                  └──────────┬───────────┘
                             │
                  POST /api/agent/v1/actions/post
                             │
                  ┌──────────▼───────────┐
                  │       RUNNING        │
                  │ (Playwright Autopilot)
                  └──────────┬───────────┘
                             │
                     Formulář vyplněn +
                     fotografie nahrány
                             │
                  ┌──────────▼───────────┐
                  │   READY_FOR_REVIEW   │ ◄─── Agent informuje uživatele
                  │  (Zastavený worker)  │      s odkazem na Live Browser
                  └─────┬──────────┬─────┘
                        │          │
   Uživatel klikne      │          │ Uživatel zamítne /
   "Odeslat" na Bazoši  │          │ timeout / zrušení
                        │          │
   POST .../actions/confirm        POST .../actions/cancel
                        │          │
                  ┌─────▼─────┐ ┌──▼──────────┐
                  │ COMPLETED │ │  CANCELLED  │
                  │(DB: Aktivní)│(DB: Koncept) │
                  └───────────┘ └─────────────┘
```

---

## 3. Detailní specifikace fází protokolu

### Fáze 1: Autonomní předvyplnění (Autopilot Phase)
1. **Příprava inzerátu:** Agent připraví data inzerátu:
   * `title`: Max. 50 znaků (přísný limit Bazoše, bez markdown hvězdiček).
   * `description`: Strukturovaný text s odrážkami (`- `), bez markdown formátování (`*`, `**`), které Bazoš nepodporuje.
   * `price`: Validní celočíselná cena v Kč.
   * `category` & `target_domain`: Správná subdoména Bazoše (např. `dum.bazos.cz`), aby nedošlo k promazání formuláře změnou rubriky.
   * `photos_dir`: Ověřená lokální složka fotografií.
2. **Spuštění akce:** Agent odešle `POST /api/agent/v1/actions/post` s payloadem:
   ```json
   {
     "listing_id": "123",
     "target_domain": "dum.bazos.cz"
   }
   ```
3. **Předvyplnění prohlížeče:** Backend spustí Playwright worker v režimu `is_web=True`. Worker otevře `pridat-inzerat.php`, vyplní všechny parametry, nahraje fotografie a přepne stav v `ActionStateManager` na `READY_FOR_REVIEW`.

### Mezifáze: HITL Předání řízení člověku (Human Delegation Gate)
1. **Agent detekuje stav:** Při periodickém dotazu `GET /api/agent/v1/actions/status` (nebo po dokončení příkazu) obdrží agent odpověď:
   ```json
   {
     "state": "READY_FOR_REVIEW",
     "listing_id": "123",
     "live_preview_url": "http://127.0.0.1:5001/#screencast",
     "instructions": "Formulář na Bazoši je předvyplněn. Zkontrolujte prosím živý náhled v prohlížeči, vyřešte případný SMS kód, klikněte na Bazoši na 'Odeslat' a poté potvrďte dokončení."
   }
   ```
2. **Komunikace s uživatelem:** Agent přeruší automatické akce a předá zprávu uživateli s odkazem na webové rozhraní:
   > *„Ondro, inzerát pro [Položka] jsem na Bazoši kompletně předvyplnil a fotky nahrál. Otevři prosím [Živý prohlížeč](http://127.0.0.1:5001/#screencast), zkontroluj formulář, klikni na Bazoši na 'Odeslat' a napiš mi, až to bude hotové.“*

### Fáze 2: Potvrzení a zaevidování (Confirmation & Settlement)
1. **Uživatelská interakce:** Uživatel na živém screencastu zkontroluje údaje, případně přepíše drobnost, zadá SMS kód (pokud byl vyžádán) a klikne na Bazoši na tlačítko *Odeslat*.
2. **Spuštění potvrzení:** Na pokyn uživatele (nebo po explicitním schválení) agent zavolá:
   `POST /api/agent/v1/actions/confirm`
3. **Validace odeslání backendem (`_check_page_submitted`):**
   * Backend zkontroluje DOM stránky v aktivní relaci Playwrightu.
   * **Stále na formuláři:** Pokud je stránka stále na `pridat-inzerat.php` a pole `nadpis` je viditelné, inzerát ještě nebyl odeslán. Backend vrátí HTTP 422:
     ```json
     {
       "status": "error",
       "error_code": "STILL_ON_FORM",
       "message": "Inzerát ještě nebyl odeslán na Bazoši. Zkontrolujte formulář a klikněte v prohlížeči na 'Odeslat'."
     }
     ```
   * **Úspěšně odesláno:** Pokud stránka opustila formulář a zobrazuje odkaz na nový inzerát (`/inzerat/<id>/`), backend:
     * Extrahuje živou URL a `portal_item_id`.
     * Nastaví stav inzerátu v SQLite databázi na `Aktivní`.
     * Zapíše aktuální datum do `created_at` a vynuluje počítadlo zhlédnutí (`views: 0`).
     * Uzavře relaci prohlížeče a nastaví stav akce na `COMPLETED`.
     * Vrátí agentovi HTTP 200 s detailem inzerátu a finální URL.

### Alternativní větev: Stornování akce (Abort Path)
Pokud uživatel v mezifázi inzerát odmítne nebo si přeje proces přerušit:
* Agent zavolá `POST /api/agent/v1/actions/cancel`.
* Worker okamžitě ukončí proces Playwrightu, zavře kontext prohlížeče a resetuje stav na `IDLE`.
* Inzerát zůstane v SQLite bezpečně uložen ve stavu `Koncept (Draft)`.

---

## 4. Důsledky a přínosy

### Pozitivní:
1. **Absolutní ochrana telefonního čísla a IP adresy:** Eliminace rizika zablokování účtu Bazošem v důsledku nekontrolovaných automatických POST requestů.
2. **Člověk v centru rozhodování:** Uživatel má plnou kontrolu nad cenou a podmínkami předtím, než se inzerát objeví na veřejném internetu.
3. **Odolnost proti CAPTCHA a SMS výzvám:** Živý screencast umožňuje člověku vyřešit jakoukoliv interaktivní výzvu, aniž by došlo k pádu agenta.
4. **Deterministický auditní záznam:** Zápis do lokální databáze proběhne teprve v okamžiku, kdy je potvrzena reálná URL živého inzerátu na Bazoši.

### Omezení:
* Proces vystavení nelze provádět plně bezobslužně (např. dávkové noční vystavování 50 inzerátů bez přítomnosti člověka). Toto omezení je záměrným architektonickým a bezpečnostním rozhodnutím.
