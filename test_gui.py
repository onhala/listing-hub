import os
import sys
import time
from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = "/Users/ondre/.gemini/antigravity/brain/8655f474-7b26-4848-bcf5-35b13807a238/test_screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def test_bazos_automat_gui():
    print("🚀 Spouštím E2E testy pro Bazoš Automat GUI...")
    
    with sync_playwright() as p:
        # Spustíme prohlížeč v headless režimu pro automatické testování
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        
        # Zapneme výpis logů a chyb z konzole prohlížeče
        page.on("console", lambda msg: print(f"🖥️ [BROWSER CONSOLE] {msg.type}: {msg.text}"))
        def log_page_error(err):
            print(f"🚨 [BROWSER ERROR] {err}")
            if hasattr(err, 'message'):
                print(f"   Message: {err.message}")
            if hasattr(err, 'stack'):
                print(f"   Stack: {err.stack}")
        page.on("pageerror", log_page_error)
        page.on("requestfailed", lambda req: print(f"❌ [REQUEST FAILED] {req.url}: {req.failure}"))
        page.on("response", lambda res: print(f"📥 [RESPONSE] {res.status} {res.url}") if res.status >= 400 else None)
        
        # 1. Načtení hlavní stránky
        print("\n📥 1. Načítám hlavní stránku http://localhost:5001...")
        page.goto("http://localhost:5001")
        page.wait_for_load_state("networkidle")
        
        # Ověření titulku stránky
        title = page.title()
        print(f"   - Titulek stránky: '{title}'")
        assert "Bazoš Automat" in title, f"Neočekávaný titulek: {title}"
        
        # Vyfocení výchozího stavu
        screenshot_path = os.path.join(SCREENSHOT_DIR, "01_dashboard.png")
        page.screenshot(path=screenshot_path)
        print(f"   - Snímek uložen do: {screenshot_path}")
        
        # 2. Ověření načtení inzerátů (spinner zmizí, inzeráty nebo prázdný stav se zobrazí)
        print("\n📋 2. Ověřuji načtení inzerátů...")
        page.wait_for_selector("#active-listings-list")
        listings_count = page.locator("#active-listings-list .ad-card").count()
        print(f"   - Nalezeno aktivních inzerátů: {listings_count}")
        
        # 3. Test přepínání záložek
        print("\n🔄 3. Testuji přepínání záložek...")
        
        # Záložka: Prodané věci
        print("   - Přepínám na: Prodané věci")
        page.click("text=Prodané věci")
        page.wait_for_timeout(500)
        assert page.is_visible("#tab-sold-listings"), "Záložka Prodané věci není viditelná!"
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "02_sold_listings.png"))
        
        # Záložka: Věci k prodeji
        print("   - Přepínám na: Věci k prodeji")
        page.click("text=Věci k prodeji")
        page.wait_for_timeout(500)
        assert page.is_visible("#tab-unsold-listings"), "Záložka Věci k prodeji není viditelná!"
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "02b_unsold_listings.png"))
        
        # Záložka: Živý prohlížeč (VNC)
        print("   - Přepínám na: Živý prohlížeč")
        page.click("text=Živý prohlížeč")
        page.wait_for_timeout(1000)
        assert page.is_visible("#tab-browser"), "Záložka Živý prohlížeč není viditelná!"
        
        # Ověření, že VNC iframe obsahuje správné noVNC URL
        iframe_src = page.locator("#vnc-iframe").get_attribute("src")
        print(f"   - noVNC iframe src: {iframe_src}")
        assert "/novnc/" in iframe_src or "6080" in iframe_src, f"Neočekávaná URL noVNC: {iframe_src}"
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "03_live_browser.png"))
        
        # Záložka: Nastavení
        print("   - Přepínám na: Nastavení")
        page.click("text=Nastavení")
        page.wait_for_timeout(500)
        assert page.is_visible("#tab-config"), "Záložka Nastavení není viditelná!"
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "04_settings.png"))
        
        # 4. Test formuláře nastavení (Uložení konfigurace)
        print("\n⚙️ 4. Testuji úpravu a uložení nastavení...")
        original_name = page.locator("#config-name").input_value()
        test_name = f"Test_Ondra_{int(time.time())}"
        
        print(f"   - Původní jméno: '{original_name}'")
        print(f"   - Zapisuji nové testovací jméno: '{test_name}'")
        
        page.fill("#config-name", test_name)
        
        # Kliknutí na uložit nastavení
        print("   - Klikám na 'Uložit nastavení'...")
        page.click("#btn-save-config")
        
        # Počkáme na reakci (notifikaci nebo uložení)
        page.wait_for_timeout(1000)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "05_settings_saved.png"))
        
        # Vrátíme původní jméno, abychom neponičili ostrá data
        print(f"   - Obnovuji původní jméno: '{original_name}'")
        page.fill("#config-name", original_name)
        page.click("#btn-save-config")
        page.wait_for_timeout(500)
        
        # 5. Test spuštění synchronizace s Bazošem
        print("\n⚡ 5. Testuji tlačítko 'Synchronizovat s Bazošem'...")
        # Přepneme zpět na aktivní inzeráty
        page.click("text=Aktivní inzeráty")
        page.wait_for_timeout(500)
        
        # Kliknutí na synchronizovat
        print("   - Klikám na 'Synchronizovat s Bazošem'")
        page.click("#btn-sync-views")
        
        # Ověření, že se tab automaticky přepnul na Živý prohlížeč (VNC)
        page.wait_for_timeout(1000)
        assert page.is_visible("#tab-browser"), "Po kliknutí na synchronizaci se tab automaticky nepřepnul na Živý prohlížeč!"
        print("   - ✓ Tab se úspěšně automaticky přepnul na Živý prohlížeč (VNC)")
        
        # Ověření, že se zobrazil Playwright stavový řádek na spodku stránky
        page.wait_for_selector("#playwright-status", state="visible")
        is_status_visible = page.is_visible("#playwright-status")
        print(f"   - Zobrazen Playwright stavový řádek: {is_status_visible}")
        assert is_status_visible, "Playwright stavový řádek se nezobrazil po kliknutí na synchronizaci!"
        
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "06_sync_running.png"))
        
        # 6. Test přerušení běžící operace
        print("\n🛑 6. Testuji přerušení (zrušení) běžící operace...")
        assert page.is_visible("#btn-cancel-action"), "Tlačítko 'Přerušit' není viditelné v běžícím stavu!"
        print("   - Klikám na tlačítko 'Přerušit'")
        page.click("#btn-cancel-action")
        
        # Čekáme, až stavový řádek zmizí
        print("   - Čekám na zmizení stavového řádku...")
        page.wait_for_selector("#playwright-status", state="hidden", timeout=5000)
        is_status_visible_after = page.is_visible("#playwright-status")
        print(f"   - Stavový řádek je viditelný po přerušení: {is_status_visible_after}")
        assert not is_status_visible_after, "Stavový řádek nezmizel ani po kliknutí na Přerušit!"
        print("   - ✓ Stavový řádek úspěšně zmizel a operace byla přerušena.")
        
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "07_sync_cancelled.png"))
        
        # 7. Test detekce chyb (Error Handling) při neplatném telefonu
        print("\n❌ 7. Testuji detekci chyb v konfiguraci...")
        page.click("text=Nastavení")
        page.wait_for_timeout(500)
        
        original_phone = page.locator("#config-phone").input_value()
        print("   - Nastavuji neplatné telefonní číslo...")
        page.fill("#config-phone", "123")
        page.click("#btn-save-config")
        page.wait_for_timeout(500)
        
        page.click("text=Aktivní inzeráty")
        page.wait_for_timeout(500)
        print("   - Spouštím synchronizaci s neplatným telefonem...")
        page.click("#btn-sync-views")
        
        # Čekáme, až se stavový řádek nejprve zobrazí
        page.wait_for_selector("#playwright-status", state="visible", timeout=3000)
        # Čekáme, až stavový řádek zmizí s chybou
        page.wait_for_selector("#playwright-status", state="hidden", timeout=15000)
        print("   - ✓ Stavový řádek správně zmizel (chyba detekována)")
        
        # Vrátíme původní telefon
        page.click("text=Nastavení")
        page.wait_for_timeout(500)
        page.fill("#config-phone", original_phone)
        page.click("#btn-save-config")
        page.wait_for_timeout(500)

        # 8. Test integrity stavu a zamezení race condition
        print("\n🔒 8. Testuji ochranu dat před přepsáním (State Integrity)...")
        page.click("text=Aktivní inzeráty")
        page.wait_for_timeout(500)
        
        # Spustíme synchronizaci
        page.click("#btn-sync-views")
        page.wait_for_selector("#playwright-status", state="visible")
        
        # Během běhu synchronizace změníme jméno v nastavení přes GUI
        page.click("text=Nastavení")
        page.wait_for_timeout(500)
        temp_test_name = f"Integrity_Test_{int(time.time())}"
        page.fill("#config-name", temp_test_name)
        page.click("#btn-save-config")
        page.wait_for_timeout(500)
        
        # Nyní stornujeme běžící synchronizaci
        page.click("text=Živý prohlížeč")
        page.wait_for_timeout(500)
        page.click("#btn-cancel-action")
        page.wait_for_selector("#playwright-status", state="hidden", timeout=5000)
        
        # Ověříme, že změněné jméno v nastavení na disku zůstalo zachováno
        page.click("text=Nastavení")
        page.wait_for_timeout(500)
        current_name_after = page.locator("#config-name").input_value()
        print(f"   - Jméno v nastavení po stornu: '{current_name_after}'")
        assert current_name_after == temp_test_name, f"Race condition detekována! Jméno bylo přepsáno: {current_name_after}"
        print("   - ✓ Data byla úspěšně sloučena, nedošlo k přepsání GUI změn.")
        
        # Vrátíme původní jméno
        page.fill("#config-name", original_name)
        page.click("#btn-save-config")
        page.wait_for_timeout(500)
        
        print("\n✅ Všechny E2E/GUI testy úspěšně proběhly!")
        browser.close()

if __name__ == "__main__":
    try:
        test_bazos_automat_gui()
    except Exception as e:
        print(f"\n❌ Test selhal s chybou: {e}")
        sys.exit(1)
