# 🤖 Bazoš Automat v1.2

Prémiové interaktivní řídicí centrum (CLI Dashboard) pro kompletní správu inzerce na portálu Bazoš.cz, evidenci historie prodejů a automatickou synchronizaci do profesionální Excel tabulky přímo na OneDrive TERMS.

Tento nástroj byl vyvinut speciálně pro dynamické a přehledné inzerování většího množství věcí s maximální úsporou času a eliminací opakovaného SMS ověřování.

---

## 🚀 Hlavní funkce

1. **Poloautomatické vystavení (`[1]`)**:
   - Automaticky otevře Google Chrome přes Playwright, vyplní veškeré údaje z lokální databáze (nadpis, popis, cena, kontakt, PSČ, heslo) a vybere nejvhodnější kategorii na základě shody klíčových slov.
   - Nahraje všechny fotografie ze specifické lokální složky inzerátu.
   - Vyčká na SMS ověření uživatele a po úspěšném odeslání umožní ihned pokračovat nebo uložit URL inzerátu pro budoucí správu.

2. **Interaktivní průvodce přidáním věci (`[2]`)**:
   - Rychlé přidání nové věci do databáze (Název, Cena, Popis, Stav, Složka s fotkami).
   - Automaticky vytvoří čistou podsložku na ploše pro nahrání fotografií.

3. **Změna ceny inzerátu (`[3]`)**:
   - Umožňuje změnit cenu místně v databázi a volitelně spustit robota, který automaticky přejde do administrace inzerátu na Bazoši, zadá heslo a předvyplní novou cenu pro rychlé uložení.

4. **Znovuvystavení & Topování zdarma (`[4]`)**:
   - Smaže stávající inzerát z Bazoše pomocí hesla a ihned jej vystaví znovu, čímž se inzerát posune na první místa (topování zdarma).
   - **Nové:** Při znovuvystavení se skript automaticky zeptá, zda chceš při této příležitosti změnit i cenu věci.

5. **Zaznamenání prodeje (`[5]`)**:
   - Přesune aktivní inzerát do historie prodejů, zeptá se na skutečnou prodejní cenu a volitelné poznámky (kdo koupil, slevy atd.).
   - Uvolní věc z aktivních inzerátů a zaznamená datum prodeje.

6. **Přehledná tabulka v terminálu (`[6]`)**:
   - Vykreslí barevné, perfektně naformátované tabulky aktivních inzerátů a historie prodejů (včetně celkového zisku a cenových rozdílů) přímo v konzoli.

7. **Aktualizace stavů z Bazoše (`[7]`)**:
   - Spustí rychlou synchronizaci reálného stavu inzerátů přímo z Bazoše (na pozadí, bez nutnosti otevírat prohlížeč).
   - Aktualizuje počet zhlédnutí (views), reálné datum vystavení a automaticky detekuje, zda inzerát nebyl vymazán nebo nevypršela jeho platnost (v tom případě změní stav na **Expirováno** a zvýrazní jej červeně).
   - Po dokončení automaticky uloží aktualizovaná data a promítne změny na OneDrive.

8. **Synchronizace s OneDrive (`[8]`)**:
   - Automaticky (po každé změně) i manuálně synchronizuje celou databázi s Excel tabulkou `Inzerce - bazos.xlsx` na OneDrive.
   - Tabulka používá prémiový **TERMS vizuální styl** (tmavě fialové záhlaví `#4B2C82`, zapnutá mřížka, zelené/oranžové stavové štítky, automatická šířka sloupců a Excel vzorce pro součty prodejů).

---

## 🛠️ Instalace a spuštění

Nástroj je plně přenosný a spravovaný přes tento GitHub repozitář.

### 1. Příprava virtuálního prostředí
V adresáři projektu spusť následující příkazy:
```bash
# Vytvoření virtuálního prostředí
python3 -m venv .venv

# Aktivace a instalace závislostí
.venv/bin/pip install openpyxl tabulate playwright requests beautifulsoup4

# Instalace prohlížeče Chromium pro Playwright
.venv/bin/playwright install chromium
```

### 2. Konfigurace profilu (`bazos_config.json`)
Před prvním spuštěním uprav soubor `bazos_config.json` podle svých kontaktních údajů (výchozí e-mail, telefon, výchozí heslo v Base64 pro inzeráty):
```json
{
  "user": {
    "email": "tuj_email@example.com",
    "phone": "777123456",
    "phone_verified": "+420777123456",
    "default_ad_password_b64": "aGVzbG8xMjM="
  }
}
```

### 3. Spuštění CLI Dashboardu
Hlavní řídicí panel spustíš jednoduše příkazem:
```bash
.venv/bin/python post_to_bazos.py
```

---

## 🔍 Analýza konkurenčních cen (`bazos_analyzer.py`)

Skript `bazos_analyzer.py` slouží k rychlé analýze cen podobného zboží přímo na Bazoši. Stáhne aktuální inzeráty konkurence, spočítá průměr, medián a doporučí 3 cenové strategie (rychlý prodej, férová cena, prémiová cena).

### Použití analyzátoru:
```bash
.venv/bin/python bazos_analyzer.py "Sekačka HECHT" [minimální_cena] [maximální_cena]
```

**Příklad:**
```bash
.venv/bin/python bazos_analyzer.py "Drtič větví" 1000 5000
```
Skript vypíše podrobný přehled s doporučenými cenami a odkazem na Top 5 nejbližších konkurenčních nabídek.
