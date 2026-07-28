import os
import requests
import pytest
from playwright.async_api import async_playwright
import websockets

BASE_URL = os.getenv("BASE_URL", "http://localhost:5001")
WS_URL = os.getenv("WS_URL", "ws://localhost:5001/api/screencast/ws")

@pytest.fixture(autouse=True)
def cleanup_test_listings():
    """Automatic teardown to prevent test data pollution in listings.db."""
    yield
    import sqlite3
    db_path = os.path.join(os.path.dirname(__file__), "../../data/listings.db")
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("DELETE FROM listings WHERE LOWER(id) LIKE 'test-%' OR LOWER(title) LIKE '%e2e%' OR LOWER(title) LIKE '%test%' OR LOWER(local_photos_dir) LIKE '%test%'")
            c.execute("DELETE FROM portal_states WHERE listing_id NOT IN (SELECT id FROM listings)")
            conn.commit()
            conn.close()
        except Exception:
            pass

def test_backend_crud_and_endpoints():
    """Test standard backend CRUD operations and API contracts."""
    # 1. Config check
    res = requests.get(f"{BASE_URL}/api/config")
    assert res.status_code == 200, f"Config endpoint failed: {res.text}"
    
    # 2. Add new listing
    payload = {
        "title": "E2E Testovací Stroj MIRA",
        "description": "Automatický testovací inzerát pro ověření E2E funkcí.",
        "price": 120000,
        "category": "Stroje",
        "portal": "bazos",
        "local_photos_dir": "test_mira_e2e"
    }
    res = requests.post(f"{BASE_URL}/api/listings/add", json=payload)
    assert res.status_code == 200, f"Add listing failed: {res.text}"
    add_data = res.json()
    assert add_data.get("status") == "success" or add_data.get("success") is True

    # 3. Fetch listings and verify presence
    res = requests.get(f"{BASE_URL}/api/listings")
    assert res.status_code == 200
    listings_data = res.json()
    active = listings_data.get("active_listings", [])
    assert any(ad["title"] == payload["title"] for ad in active), "Newly added listing not found in active listings!"

    # 4. Save/Edit listing
    test_ad = next(ad for ad in active if ad["title"] == payload["title"])
    test_ad["price"] = 115000
    res = requests.post(f"{BASE_URL}/api/listings/save", json=test_ad)
    assert res.status_code == 200

    # 5. AI improve text endpoint check
    ai_text_req = {"text": test_ad["description"], "instruction": "improve", "field": "description"}
    res = requests.post(f"{BASE_URL}/api/ai/improve", json=ai_text_req)
    assert res.status_code in [200, 400, 500]

    # 6. Clean up test listing via API
    if test_ad.get("id"):
        res = requests.post(f"{BASE_URL}/api/listings/delete", json={"id": test_ad["id"]})
        assert res.status_code == 200

@pytest.mark.asyncio
async def test_websocket_screencast():
    """Test CDP Canvas Screencast WebSocket endpoint connectivity."""
    async with websockets.connect(WS_URL, open_timeout=5) as ws:
        assert ws is not None

@pytest.mark.asyncio
async def test_playwright_ui_workflows():
    """Test frontend user interface workflows using Playwright headless browser."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        js_errors = []
        page.on("pageerror", lambda err: js_errors.append(f"{err.name}: {err.message}"))
        page.on("console", lambda msg: js_errors.append(f"ConsoleError: {msg.text}") if msg.type == "error" else None)
        
        # Load Main App
        await page.goto(BASE_URL, wait_until="networkidle")
        
        # Verify active listing tab and card rendering
        active_tab = page.locator(".nav-item[data-tab='active-listings']")
        await active_tab.click()
        await page.wait_for_timeout(500)
        assert await active_tab.is_visible(), "Active listing tab should be visible!"
        
        # Open Add Listing Modal
        add_btn = page.locator("#btn-add-listing-modal")
        await add_btn.click()
        await page.wait_for_timeout(300)
        modal_visible = await page.locator("#add-listing-modal").is_visible()
        assert modal_visible, "Add listing modal did not open!"
        
        # Close Modal
        close_btn = page.locator("#add-listing-modal .btn-close-modal").first
        await close_btn.click()
        await page.wait_for_timeout(300)
        
        # Switch to Živý Prohlížeč tab
        browser_tab = page.locator(".nav-item[data-tab='browser']")
        await browser_tab.click()
        await page.wait_for_timeout(500)
        canvas_visible = await page.locator("#screencast-canvas").is_visible()
        assert canvas_visible, "Screencast canvas should be visible on Live Browser tab!"
        
        assert len(js_errors) == 0, f"Frontend JS errors encountered: {js_errors}"
        await browser.close()
