# Aukro Rich Insights & Auction Lifecycle Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rozšířit integraci Aukro.cz v Listing Hubu o dynamiku aukcí (typ nabídky, počet příhozů, odpočet konce s vizuální urgencí, přesná zhlédnutí a možnosti dopravy) s čistým UX na dlaždicích a v detailu inzerátu.

**Architecture:** Rozšíření parseru `AukroPortal` o extrakci aukčních polí z REST API (`offerDetail`), uložení strukturovaných metadat do `portal_states['aukro']` v SQLite a vykreslení inteligentního kompaktního odznaku na kartě v `static/app.js` včetně detailní sekce v modalu inzerátu.

**Tech Stack:** Python 3.11+, Flask, SQLite, Vanilla JS / CSS3, pytest.

---

### Task 1: Rozšíření `AukroPortal.fetch_offer_detail` o aukční metadata a dopravu

**Files:**
- Modify: `listing_hub/portals/aukro/aukro_portal.py:165-215`
- Test: `tests/unit/test_aukro_sync.py`

**Step 1: Napsat selhávající unit test**
Rozšířit test v `tests/unit/test_aukro_sync.py` pro ověření nových polí (`item_type`, `bidders_count`, `next_bid_min`, `ending_time_text`, `bargaining_available`, `shipping_options`).

```python
def test_fetch_offer_detail_rich_metadata(monkeypatch):
    aukro_portal = AukroPortal()
    sample_payload = {
        "itemType": "BIDDING",
        "biddersCount": 2,
        "displayedCount": 56,
        "watchingUserCount": 3,
        "endingTime": "2026-10-04T14:08:12+02:00",
        "endingTimeText": "3 dny",
        "nextBidMinAmount": {"amount": 450, "currency": "CZK"},
        "price": {"amount": 399, "currency": "CZK"},
        "state": "ACTIVE",
        "descriptionStripped": "Popis",
        "bargainingAvailable": True,
        "shippingOptions": [
            {"firstPackagePrice": {"amount": 63.0}, "freeOfCharge": False, "aukroShipping": True}
        ],
        "images": []
    }
    monkeypatch.setattr(requests, "get", lambda *a, **kw: MockResponse(sample_payload))
    detail = aukro_portal.fetch_offer_detail("7082098064")
    assert detail["item_type"] == "BIDDING"
    assert detail["bidders_count"] == 2
    assert detail["views"] == 56
    assert detail["ending_time_text"] == "3 dny"
    assert detail["next_bid_min"] == 450
    assert detail["bargaining_available"] is True
    assert len(detail["shipping_options"]) == 1
```

**Step 2: Spustit test a ověřit, že selže**
Run: `.venv/bin/pytest tests/unit/test_aukro_sync.py -k test_fetch_offer_detail_rich_metadata`
Expected: FAIL (chybějící klíče v dictionary).

**Step 3: Implementovat extrakci v `AukroPortal.fetch_offer_detail`**
V `listing_hub/portals/aukro/aukro_portal.py` vytáhnout:
- `itemType` -> `item_type` (`"BIDDING"` nebo `"BUY_NOW"`)
- `biddersCount` -> `bidders_count` (int)
- `displayedCount` -> `views` (int)
- `nextBidMinAmount.amount` -> `next_bid_min` (float/int)
- `endingTimeText` -> `ending_time_text` (str)
- `bargainingAvailable` -> `bargaining_available` (bool)
- `shippingOptions` -> zjednodušený seznam doprav (název/typ a cena)

**Step 4: Spustit test a ověřit průchod**
Run: `.venv/bin/pytest tests/unit/test_aukro_sync.py -k test_fetch_offer_detail_rich_metadata`
Expected: PASS.

**Step 5: Commit**
```bash
git add listing_hub/portals/aukro/aukro_portal.py tests/unit/test_aukro_sync.py
git commit -m "feat(aukro): extract auction type, bidders, ending time text and shipping in offerDetail"
```

---

### Task 2: Uložení obohacených dat do `portal_states['aukro']` v `sync_listings`

**Files:**
- Modify: `listing_hub/portals/aukro/aukro_portal.py:270-360`
- Test: `tests/unit/test_aukro_sync.py`

**Step 1: Napsat selhávající test pro `sync_listings`**
Ověřit, že po synchronizaci obsahuje `portal_states['aukro']` pole `item_type`, `bidders_count`, `next_bid_min`, `ending_time_text` a chytré formátování `top_info`.

```python
def test_sync_listings_preserves_rich_metadata(monkeypatch):
    # test verify portal_states["aukro"] has item_type and bidders_count
    ...
```

**Step 2: Spustit test a ověřit selhání**
Run: `.venv/bin/pytest tests/unit/test_aukro_sync.py -k test_sync_listings_preserves_rich_metadata`
Expected: FAIL.

**Step 3: Upravit `sync_listings` v `aukro_portal.py`**
Do ukládaného slovníku `aukro_state` v `sync_listings` přidat:
```python
"item_type": detail.get("item_type", "BUY_NOW"),
"bidders_count": detail.get("bidders_count", 0),
"next_bid_min": detail.get("next_bid_min"),
"ending_time_text": detail.get("ending_time_text"),
"bargaining_available": detail.get("bargaining_available", False),
"shipping_options": detail.get("shipping_options", []),
```
A aktualizovat `top_info`:
- Pokud aukce s příhozy: `f"{bidders} příh. · sleduje {watchers}"`
- Pokud aukce bez příhozů: `f"Aukce · sleduje {watchers}"`
- Pokud Kup teď: `f"Kup teď · sleduje {watchers}"`

**Step 4: Spustit testy**
Run: `.venv/bin/pytest tests/unit/test_aukro_sync.py`
Expected: All 10 passed.

**Step 5: Commit**
```bash
git add listing_hub/portals/aukro/aukro_portal.py tests/unit/test_aukro_sync.py
git commit -m "feat(aukro): persist enriched auction state in portal_states"
```

---

### Task 3: Metoda `fetch_seller_profile` pro reputaci účtu v nastavení

**Files:**
- Modify: `listing_hub/portals/aukro/aukro_portal.py`
- Modify: `app.py`
- Test: `tests/unit/test_aukro_sync.py`

**Step 1: Napsat unit test pro `fetch_seller_profile`**
Ověřit stažení reputace (počet recenzí a % spokojenost) ze SSR cache profilu nebo `offerDetail.seller`.

**Step 2: Implementovat `fetch_seller_profile(username)`**
Vrátí: `{"rating": 156, "positive_pct": 99.4, "feedback_count": 157}`.
Přidat endpoint `GET /api/portals/aukro/profile` do `app.py`.

**Step 3: Spustit testy**
Run: `.venv/bin/pytest tests/unit/test_aukro_sync.py`
Expected: PASS.

**Step 4: Commit**
```bash
git add listing_hub/portals/aukro/aukro_portal.py app.py tests/unit/test_aukro_sync.py
git commit -m "feat(aukro): add seller reputation fetching and API endpoint"
```

---

### Task 4: UI – Vylepšený odznak na dlaždici inzerátu (`renderPortalBadgesHtml`)

**Files:**
- Modify: `static/app.js:1150-1200`
- Modify: `static/style.css` (pokud jsou potřeba třídy pro urgenci)

**Step 1: Rozšíření logiky v `renderPortalBadgesHtml` v `static/app.js`**
Pokud `normKey === "aukro"`:
1. **Formát & příhozy:**
   - Pokud `state.item_type === "BIDDING"`: zobrazit ikonu `🔨` s počtem příhozů (`${state.bidders_count || 0} příh.`).
   - Pokud `state.item_type === "BUY_NOW"`: zobrazit ikonu `⚡ Kup teď`.
2. **Odpočet a urgence konce aukce:**
   - Zkontrolovat `state.ending_time`:
     - Pokud zbývá `< 24 hodin`: odznak `⏳ ${hoursLeft}h` ve zvýrazněné oranžovo-červené barvě s pulzujícím indikátorem.
     - Pokud zbývá více dní: odznak `⏳ ${state.ending_time_text || daysLeft}`.
3. **Statistiky zhlédnutí a sledujících:**
   - Zobrazit přesná zhlédnutí `👁️ ${viewsVal}` a sledující `⭐ ${watchersVal}`.

**Step 2: Vizuální test v prohlížeči / headless snapshot**
Ověřit, že odznak je kompaktní, neodsouvá nadpis ani cenu a nezpůsobuje zalamování do více řádků na běžném rozlišení.

**Step 3: Commit**
```bash
git add static/app.js static/style.css
git commit -m "feat(ux): display auction format, live bids count, and ending countdown on Aukro badges"
```

---

### Task 5: UI – Sekce „Aukro detaily a doprava“ v modalu inzerátu

**Files:**
- Modify: `templates/index.html` (modal edit/detail inzerátu)
- Modify: `static/app.js` (populace dat při otevření modalu)

**Step 1: Přidat kontejner do detailu inzerátu v `templates/index.html`**
Kompaktní bento-box sekce pro portálové detaily (zobrazí se pouze, pokud má inzerát `portal_states.aukro`).
- Typ prodeje (Aukce / Kup teď)
- Aktuální příhoz & minimální další příhoz
- Konec nabídky s přesným datem a časem
- Nastavené možnosti dopravy (ikona Balíkovna/Zásilkovna + cena)
- Možnost smlouvání (Povoleno / Nepovoleno)

**Step 2: Naplnit data v `openEditModal` / `openDetailModal` v `static/app.js`**
Při kliknutí na inzerát se z `currentAd.portal_states.aukro` vytáhnou detaily a dynamicky vyplní do této sekce.

**Step 3: Commit**
```bash
git add templates/index.html static/app.js
git commit -m "feat(ux): add rich Aukro auction & shipping info section to listing modal"
```

---

### Task 6: UI – Zobrazení reputace prodejce v záložce Nastavení

**Files:**
- Modify: `templates/index.html:515-525`
- Modify: `static/app.js:710-725`

**Step 1: Přidat vizuální badge vedle pole `config-aukro-username` v `templates/index.html`**
```html
<div id="aukro-seller-reputation-badge" style="display: none; margin-top: 0.5rem; font-size: 0.8rem;">
    <!-- e.g. ⭐ 156 hodnocení | 99.4 % spokojenost -->
</div>
```

**Step 2: V `loadConfig()` v `static/app.js` zavolat `/api/portals/aukro/profile`**
Pokud je nastaveno uživatelské jméno, načíst statistiky prodejce a vykreslit zelený odznak ověřeného prodejce s reputací.

**Step 3: Commit**
```bash
git add templates/index.html static/app.js
git commit -m "feat(ux): display seller feedback and satisfaction rating in settings"
```

---

### Task 7: Finální ověření, test suite a vydání verze

**Files:**
- Modify: `listing_hub/core/version.py`
- Modify: `README.md`, `PRODUCT.md`, `DEVELOPMENT.md`

**Step 1: Spustit kompletní unit testy**
Run: `.venv/bin/pytest tests/unit/ -v`
Expected: Všech 275+ testů prochází bez varování.

**Step 2: Bump verze na `v3.18.0` a aktualizace dokumentace**

**Step 3: Commit, tag a push**
```bash
git commit -m "chore(release): bump version to v3.18.0 (Aukro rich insights & auction lifecycle)"
git tag -a v3.18.0 -m "Release v3.18.0: Aukro rich insights & auction lifecycle"
git push origin main --tags
```
