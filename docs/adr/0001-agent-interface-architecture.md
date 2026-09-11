# ADR 0001: Architektura rozhraní pro AI agenty (Unified Hybrid Model)

* **Status:** Přijato (Accepted)
* **Datum:** 2026-09-11
* **Autor:** Ondřej Hála
* **Kontext:** Listing Hub (`/Users/ondre/Projects/listing-hub`)

---

## 1. Kontext a problém

Aplikace **Listing Hub** slouží k automatizované správě, oceňování a asistovanému vystavování inzerátů na českých inzertních portálech (primárně Bazoš.cz, s modularitou pro Aukro.cz). Systém je postaven na stacku Python 3.11 (Flask), SQLite (`listings.db`), Playwright (automatizace prohlížeče Chromium s noVNC/CDP screencastem) a Google Gemini 2.5 Flash (multimodální analýza fotografií a tržní radar).

S rozvojem pokročilých AI agentů (zejména ekosystému **Antigravity**) vyvstala potřeba umožnit agentům plnohodnotně, bezpečně a autonomně spolupracovat se systémem Listing Hub:
* Vyhledávat a číst existující inzeráty (aktivní, prodané, koncepty).
* Vytvářet nové koncepty inzerátů ze souborů fotografií na disku s využitím AI Vision analýzy.
* Spouštět a monitorovat procesy předvyplnění formulářů v prohlížeči.
* Aktualizovat ceny a topovat inzeráty na trhu.
* Bezpečně mazat inzeráty včetně lokálních fotografií.

Bylo nutné rozhodnout o optimální architektuře rozhraní pro agenty a vyhodnotit tři architektonické varianty.

---

## 2. Vyhodnocení zvažovaných variant (Architectural Grilling)

### Varianta A: Headless Agent REST API + CLI Tool + Antigravity Skill (volání CLI přes Bash)
* **Princip:** Flask backend poskytne REST API, nad nímž vznikne dedikovaný skript `listing_hub_cli.py`. Agent volá CLI příkazy přes systémový shell (`run_command` / bash).
* **Výhody:**
  * Okamžitá použitelnost v jakémkoliv terminálu a snadné ladění přes `curl`.
  * Nezávislost na MCP runtime; snadná skriptovatelnost v Cronu či shell skriptech.
* **Nevýhody a úskalí:**
  * **Vysoká latence a režie:** Každé volání spouští nový Python proces (interpret + importy knihoven ~150–250 ms na příkaz).
  * **Tokenová neefektivita:** Agent konzumuje kontext na generování bash příkazů a zpracování formátovaného stdout/stderr výstupu.
  * **Riziko shell injection:** Předávání uživatelských parametrů (názvy inzerátů, cesty k fotkám) vyžaduje striktní escapování v bash příkazech.
  * **Absence obousměrného streamování:** Agent musí pro zjištění stavu workeru provádět aktivní polling spouštěním dalších CLI příkazů.

### Varianta B: Nativní MCP Server (Model Context Protocol) přes stdio / SSE
* **Princip:** Implementace samostatného serveru protokolu MCP (`FastMCP`) vystavujícího nástroje (`tools`) a zdroje (`resources`) přímo pro LLM agenty.
* **Výhody:**
  * **Maximální tokenová efektivita:** Přímé volání typovaných JSON funkcí s validovanými Pydantic schématy. Žádný balast shellu.
  * **Nulová režie na proces:** Persistentní JSON-RPC spojení přes stdio s latencí v jednotkách milisekund.
  * **Vysoká bezpečnost:** Vstupní parametry jsou přímo deserializovány z JSONu, eliminace rizika injektáže shellových příkazů.
* **Nevýhody a úskalí:**
  * **Vendor/Protocol lock-in:** Nástroje jsou přístupné výhradně z prostředí podporujících MCP. Chybí snadná cesta pro ad-hoc terminálové použití či skripty mimo LLM.
  * **Riziko souběhu a stavové divergence:** Pokud by MCP server přistupoval k SQLite databázi nebo Playwright instanci přímo mimo běžící Flask proces, hrozí zamykání SQLite databáze (`database is locked`) a nekonzistence stavového automatu `ActionStateManager`.

### Varianta C: Unified Hybrid Architecture (Vítězná varianta)
* **Princip:** Čtyřvrstvá hybridní architektura:
  1. **Kanonické REST API (`/api/agent/v1/...`)**: Přímo integrované do běžícího Flask backendu v `app.py`. Je jediným autoritativním bodem pravdy pro stavový automat (`ActionStateManager`), Playwright relace a SQLite transakce.
  2. **Nativní FastMCP Server (`listing_hub_mcp.py`)**: Lehký stdio/SSE server, který překládá volání MCP nástrojů na volání lokálního REST API.
  3. **Samostatný CLI klient (`listing_hub_cli.py`)**: Robustní terminálový nástroj s přepínačem `--json` a čitelným formátováním, komunikující rovněž přes REST API.
  4. **Antigravity Skill (`listing-hub`)**: Dovednost definující pro AI asistenty mentální model, přesná pravidla, bezpečnostní mantinely a dvoufázový protokol.
* **Výhody:**
  * Spojuje bezkonkurenční rychlost a tokenovou úspornost MCP pro agenty s univerzální dostupností CLI pro shell a skripty.
  * Stoprocentní integrita dat: veškeré operace protékají jedním kanonickým bodem v `app.py`.
  * Flexibilní deployment: funguje lokálně na macOS i při běhu backendu v Dockeru na TrueNAS SCALE (FastMCP a CLI komunikují přes konfigurovatelnou URL a API token).

---

## 3. Rozhodnutí

Rozhodli jsme se implementovat **Variantu C: Unified Hybrid Architecture**.

Systém bude rozdělen do následujících komponent:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        AI Agenti (Antigravity)                         │
└───────────────────┬────────────────────────────────┬───────────────────┘
                    │ MCP (stdio / SSE)              │ Bash / run_command
┌───────────────────▼────────────────────┐ ┌─────────▼───────────────────┐
│     FastMCP Server (listing_hub_mcp)   │ │  CLI Nástroj (listing_hub_cli)│
└───────────────────┬────────────────────┘ └─────────┬───────────────────┘
                    │ HTTP REST (Bearer Token)       │ HTTP REST (Bearer Token)
                    └─────────────────┬──────────────┘
                                      │
┌─────────────────────────────────────▼──────────────────────────────────┐
│                   Flask Backend Core (app.py :5001)                    │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │     Agent API Layer (/api/agent/v1/*)                            │  │
│  │     - Auth: Constant-time Bearer Token check                     │  │
│  │     - Path Traversal Chroot Guard (photos_dir validation)        │  │
│  │     - Unified JSON DTOs & Error Taxonomy                         │  │
│  └──────────────────┬───────────────────────────────┬───────────────┘  │
│                     │                               │                  │
│       ┌─────────────▼───────────────┐ ┌─────────────▼───────────────┐  │
│       │  ActionStateManager (HITL)  │ │  SQLite Layer (db.py)       │  │
│       │  Playwright Worker Session  │ │  Gemini Vision & Radar      │  │
│       └─────────────────────────────┘ └─────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

### Specifikace rozhraní kanonického REST API (`/api/agent/v1/`):
* `GET /api/agent/v1/listings`: Výpis inzerátů s podporou filtrace (`status=active|unsold|sold|all`, `limit`, `query`).
* `GET /api/agent/v1/listings/<id>`: Detail inzerátu včetně portálových stavů a cest k fotografiím.
* `POST /api/agent/v1/listings/draft`: Vytvoření konceptu z lokální složky fotografií nebo explicitních polí.
* `POST /api/agent/v1/listings/<id>/analyze`: Spuštění AI Vision analýzy a tržního cenového radaru.
* `POST /api/agent/v1/actions/post`: Zahájení 1. fáze vystavení inzerátu (předvyplnění formuláře na Bazoši).
* `GET /api/agent/v1/actions/status`: Zjištění stavu probíhající akce workeru.
* `POST /api/agent/v1/actions/confirm`: Dokončení 2. fáze vystavení po lidské kontrole.
* `POST /api/agent/v1/actions/cancel`: Přerušení akce a bezpečné zavření relace prohlížeče.
* `POST /api/agent/v1/listings/<id>/price`: Úprava ceny s volitelným topováním.
* `DELETE /api/agent/v1/listings/<id>`: Smazání inzerátu s volitelnou likvidací fotek na disku.

---

## 4. Důsledky a kompromisy

### Pozitivní:
1. **Jediný zdroj pravdy (SSOT):** Žádné zamykání SQLite mimo Flask, žádné kolize ve vláknech Playwrightu.
2. **Špičková efektivita pro LLM:** FastMCP poskytuje agentům přesná schémata nástrojů bez režie spouštění procesů.
3. **Univerzální provozní fallback:** CLI skript umožňuje plnou funkčnost i v prostředích bez podpory MCP.
4. **Transparentní bezpečnost:** Centrální autentizace a validace cest proti Directory Traversal přímo v aplikační vrstvě.

### Negativní / Vyžadující pozornost:
1. **Režie údržby tří klientských vrstev:** Řešeno sdílením logiky – jak CLI, tak FastMCP server jsou tenkými klienty volajícími totožné REST API.
2. **Závislost na běžící instanci:** Pro běh CLI i MCP musí být spuštěn backend aplikace (lokálně nebo v Dockeru). Pokud backend neběží, klient vrátí jasnou diagnostickou zprávu `CONNECTION_REFUSED`.
