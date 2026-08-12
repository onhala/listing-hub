import os
import sys
import json
import re
import base64
import requests
from flask import Flask, render_template, jsonify, request
from pathlib import Path

# Přidáme aktuální adresář do sys.path, abychom mohli importovat post_to_bazos
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import multiprocessing
import threading
import asyncio

from post_to_bazos import load_data, save_listings, run_playwright_action, cli_update_listings_from_bazos, LISTINGS_PATH, session_manager
from listing_hub.core.config import CONFIG_PATH, SESSION_STATE_PATH
import uuid
import listing_hub.core.db as db
from listing_hub.ai.gemini import improve_text_with_gemini

app = Flask(__name__)

# Konfigurace Flasku pro běh za Nginx reverzní proxy
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

playwright_process = None

from datetime import datetime

def log_debug(msg):
    try:
        with open("/tmp/thread_debug.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {msg}\n")
    except Exception:
        pass

def process_target(ad, user_config, action_type, extra_val):
    log_debug("1. Background thread started")
    
    # Monkey-patch save_listings to avoid race conditions/overwriting
    import post_to_bazos
    original_save_listings = post_to_bazos.save_listings
    
    def safe_merge_save_listings(local_data):
        log_debug("Safe merge save_listings triggered")
        fresh_data, _ = post_to_bazos.load_data()
        
        fresh_active = {ad["local_photos_dir"]: ad for ad in fresh_data.get("active_listings", []) if "local_photos_dir" in ad}
        fresh_sold = {ad["local_photos_dir"]: ad for ad in fresh_data.get("sold_listings", []) if "local_photos_dir" in ad}
        
        # Merge sold_listings updates
        for local_ad in local_data.get("sold_listings", []):
            ad_id = local_ad.get("local_photos_dir")
            if not ad_id:
                continue
            if ad_id in fresh_active:
                ad = fresh_active.pop(ad_id)
                fresh_data["active_listings"] = [a for a in fresh_data["active_listings"] if a.get("local_photos_dir") != ad_id]
                fresh_data["sold_listings"].append(ad)
                fresh_sold[ad_id] = ad
            
            target_ad = fresh_sold.get(ad_id) or fresh_active.get(ad_id)
            if target_ad:
                for key in ["views", "status", "url", "date_created", "notes"]:
                    if key in local_ad:
                        target_ad[key] = local_ad[key]

        # Merge active_listings updates
        for local_ad in local_data.get("active_listings", []):
            ad_id = local_ad.get("local_photos_dir")
            if not ad_id:
                continue
            if ad_id in fresh_sold:
                ad = fresh_sold.pop(ad_id)
                fresh_data["sold_listings"] = [a for a in fresh_data["sold_listings"] if a.get("local_photos_dir") != ad_id]
                fresh_data["active_listings"].append(ad)
                fresh_active[ad_id] = ad
                
            target_ad = fresh_active.get(ad_id) or fresh_sold.get(ad_id)
            if target_ad:
                for key in ["views", "status", "url", "date_created", "notes"]:
                    if key in local_ad:
                        target_ad[key] = local_ad[key]
                        
        original_save_listings(fresh_data)
        log_debug("Safe merge save_listings completed")
        
    post_to_bazos.save_listings = safe_merge_save_listings
    
    # Set up a new event loop for this background process
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    log_debug("2. Asyncio event loop configured")
    
    try:
        listings_data, _ = load_data()
        log_debug(f"3. Data loaded, action_type={action_type}")
        if action_type in ("sync_views", "auto_refresh"):
            try:
                from listing_hub.portals.bazos.bazos_portal import BazosPortal
                from listing_hub.core.config import load_user_config
                BazosPortal().sync_listings(load_user_config())
                log_debug("5. Done BazosPortal().sync_listings")
                
                # Zaznamenáme čas úspěšné aktualizace
                from post_to_bazos import CONFIG_PATH
                if CONFIG_PATH.exists():
                    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                        full_config = json.load(f)
                    full_config.setdefault("user", {})
                    full_config["user"]["auto_refresh_status"] = "ok"
                    from datetime import timezone
                    full_config["user"]["last_refresh_time"] = datetime.now(timezone.utc).isoformat()
                    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                        json.dump(full_config, f, ensure_ascii=False, indent=2)
            except Exception as inner_e:
                log_debug(f"Inner Exception during sync: {inner_e}")
                if "SMS_REQUIRED" in str(inner_e):
                    from post_to_bazos import CONFIG_PATH
                    if CONFIG_PATH.exists():
                        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                            full_config = json.load(f)
                        full_config.setdefault("user", {})
                        full_config["user"]["auto_refresh_status"] = "needs_sms"
                        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                            json.dump(full_config, f, ensure_ascii=False, indent=2)
                raise inner_e
        else:
            log_debug("4. Calling run_playwright_action")
            success = run_playwright_action(ad, user_config, action=action_type, extra_val=extra_val, is_web=True)
            log_debug(f"5. Done run_playwright_action, success={success}")
            if not success:
                with open("/tmp/playwright_error.txt", "w", encoding="utf-8") as f:
                    f.write("Akce byla stornována nebo selhala.")
    except Exception as e:
        log_debug(f"ERR: {e}")
        with open("/tmp/playwright_error.txt", "w", encoding="utf-8") as f:
            f.write(str(e))
    finally:
        log_debug("6. Process target finished")

# Konfigurace portu
PORT = 5001

@app.route("/")
def index():
    return render_template("index.html")

from flask_sock import Sock
import time

sock = Sock(app)

@sock.route("/api/screencast/ws")
def screencast_ws(ws):
    """Stream live Playwright browser frames to HTML5 Canvas via thread-safe CDP frame buffer."""
    last_frame_bytes = None
    while True:
        try:
            frame = getattr(session_manager, "latest_frame", None)
            if frame and frame != last_frame_bytes:
                ws.send(frame)
                last_frame_bytes = frame
            time.sleep(0.08) # ~12 FPS
        except Exception:
            break

@app.route("/api/screencast/input", methods=["POST"])
def screencast_input():
    """Handle mouse clicks and keyboard input from HTML5 Canvas via thread-safe CDP dispatching."""
    data = request.json or {}
    action = data.get("action")
    
    if not session_manager.page or session_manager.page.is_closed():
        try:
            session_manager.get_session()
            if session_manager.page:
                session_manager.page.goto("https://www.bazos.cz/moje-inzeraty.php")
        except Exception as e:
            return jsonify({"status": "error", "message": f"Cannot initialize browser session: {e}"}), 500
        
    try:
        if action == "click":
            x = data.get("x", 0)
            y = data.get("y", 0)
            success = session_manager.send_cdp_click(x, y)
            return jsonify({"status": "ok" if success else "error", "action": "click", "x": x, "y": y})
        elif action == "type":
            text = data.get("text", "")
            success = session_manager.send_cdp_type(text)
            return jsonify({"status": "ok" if success else "error", "action": "type", "text": text})
        elif action == "key":
            key = data.get("key", "")
            success = session_manager.send_cdp_key(key)
            return jsonify({"status": "ok" if success else "error", "action": "key", "key": key})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
        
    return jsonify({"status": "ignored"}), 400

def count_photos(photos_dir, excluded_list=None):
    if not photos_dir or not os.path.isdir(photos_dir):
        return 0, 0
    try:
        raw_files = os.listdir(photos_dir)
        img_files = [f for f in raw_files if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        total = len(img_files)
        excluded = set(excluded_list or [])
        included = len([f for f in img_files if f not in excluded])
        return total, included
    except Exception:
        return 0, 0

@app.route("/api/listings", methods=["GET"])
def get_listings():
    all_ads = db.get_all_listings()
    
    active_listings = []
    sold_listings = []
    
    for ad in all_ads:
        # Check portal states status or map from DB values
        # Let's map listing fields to what template/js expects
        # In json it was: {local_photos_dir, title, description, price, url, views, status, date_created, notes}
        
        # We need excluded_photos which might be stored in notes or as JSON. Wait, how was excluded_photos handled?
        # In database listings table:
        # We have id, title, description, price, category, condition, local_photos_dir, location, notes, ad_password_b64, bookmarklet_uri, days_old, created_at, target_bazos, target_aukro
        # The portal_states has views, url, status, last_synced, etc.
        # Let's see how portal_states are mapped back or how to format ad representation.
        
        # In DB, let's load portal_states
        portal_states = ad.get("portal_states", {})
        bazos_state = portal_states.get("bazos", {})
        aukro_state = portal_states.get("aukro", {})
        
        # Format for front-end compatibility
        # If it has a status in portal_states, we can use it, or default to listings.condition or 'Aktivní'
        # Let's check status. If bazos status is 'Prodané', we put it in sold_listings, else active_listings.
        # Wait, the status is mapped to "Aktivní" or "Prodané" in JSON.
        
        status = "Aktivní"
        if bazos_state:
            status = bazos_state.get("status", "Aktivní")
        elif aukro_state:
            status = aukro_state.get("status", "Aktivní")
            
        ad_dict = {
            "id": ad.get("id"),
            "title": ad.get("title"),
            "description": ad.get("description"),
            "price": ad.get("price"),
            "category": ad.get("category"),
            "condition": ad.get("condition"),
            "local_photos_dir": ad.get("local_photos_dir"),
            "location": ad.get("location"),
            "notes": ad.get("notes"),
            "target_bazos": ad.get("target_bazos"),
            "target_aukro": ad.get("target_aukro"),
            # We map bazos state for backwards compatibility if needed:
            "url": bazos_state.get("url", ""),
            "views": bazos_state.get("views", 0),
            "status": status,
            "date_created": ad.get("created_at") or "",
            "portal_states": portal_states
        }
        
        if status in ["Prodané", "Sold", "prodané"]:
            sold_listings.append(ad_dict)
        else:
            active_listings.append(ad_dict)

    return jsonify({
        "active_listings": active_listings,
        "sold_listings": sold_listings
    })

@app.route("/api/photos", methods=["GET"])
def get_photos():
    photos_dir = request.args.get("photos_dir", "")
    if not photos_dir or not os.path.isdir(photos_dir):
        return jsonify({"photos": []})
    try:
        raw_files = os.listdir(photos_dir)
        img_files = sorted(
            [f for f in raw_files if f.lower().endswith(('.jpg', '.jpeg', '.png'))],
            key=lambda x: (not x.startswith("foto_"), x)
        )
        photos = []
        for fname in img_files:
            fpath = os.path.join(photos_dir, fname)
            try:
                with open(fpath, "rb") as f:
                    data = base64.b64encode(f.read()).decode("utf-8")
                ext = fname.rsplit(".", 1)[-1].lower()
                mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
                photos.append({"filename": fname, "data_url": f"data:{mime};base64,{data}"})
            except Exception:
                photos.append({"filename": fname, "data_url": ""})
        return jsonify({"photos": photos})
    except Exception as e:
        return jsonify({"error": str(e), "photos": []}), 500

@app.route("/api/photos/upload", methods=["POST"])
def upload_photos():
    try:
        photos_dir = request.form.get("photos_dir", "").strip()
        if not photos_dir:
            return jsonify({"status": "error", "message": "Chybí složka pro fotky."}), 400
            
        os.makedirs(photos_dir, exist_ok=True)
        uploaded_files = request.files.getlist("photos") or request.files.getlist("files")
        if not uploaded_files:
            return jsonify({"status": "error", "message": "Nebyly přiloženy žádné fotky."}), 400

        existing = [f for f in os.listdir(photos_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
        counter = len(existing) + 1
        saved = []

        for file in uploaded_files:
            if file and file.filename:
                orig_filename = file.filename
                ext = orig_filename.rsplit(".", 1)[-1].lower() if "." in orig_filename else "jpg"
                if ext not in ("jpg", "jpeg", "png", "webp"):
                    ext = "jpg"
                filename = f"foto_{counter}.{ext}"
                counter += 1
                save_path = os.path.join(photos_dir, filename)
                file.save(save_path)
                saved.append(filename)

        return jsonify({"status": "success", "message": f"Úspěšně nahráno {len(saved)} fotek.", "saved_files": saved})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/config", methods=["GET"])
def get_config():
    _, user_config = load_data()
    return jsonify(user_config)

@app.route("/api/refresh/status", methods=["GET"])
def get_refresh_status():
    _, user_config = load_data()
    return jsonify({
        "auto_refresh_enabled": user_config.get("auto_refresh_enabled", False),
        "auto_refresh_interval": int(user_config.get("auto_refresh_interval", 720)),
        "auto_refresh_status": user_config.get("auto_refresh_status", "ok"),
        "last_refresh_time": user_config.get("last_refresh_time", ""),
        "is_running": playwright_process.is_alive() if playwright_process else False
    })

# Detekce chodu v Dockeru
IS_DOCKER = os.path.exists("/.dockerenv")

@app.route("/api/version/check", methods=["GET"])
def check_version():
    import subprocess
    
    # 1. Zjistíme lokální commit hash
    local_hash = "unknown"
    try:
        local_hash = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        pass
        
    # 2. Zjistíme nejnovější commit hash z GitHubu
    latest_hash = "unknown"
    latest_message = ""
    try:
        url = "https://api.github.com/repos/onhala/listing-hub/commits/main"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            commit_data = res.json()
            latest_hash = commit_data.get("sha", "")
            latest_message = commit_data.get("commit", {}).get("message", "")
    except Exception:
        pass
        
    update_available = False
    if local_hash != "unknown" and latest_hash != "unknown" and local_hash != latest_hash:
        update_available = True
        
    return jsonify({
        "local_hash": local_hash[:8] if local_hash != "unknown" else "unknown",
        "latest_hash": latest_hash[:8] if latest_hash != "unknown" else "unknown",
        "latest_message": latest_message,
        "update_available": update_available,
        "is_docker": IS_DOCKER
    })

@app.route("/api/version/update", methods=["POST"])
def update_version():
    if IS_DOCKER:
        return jsonify({"status": "error", "message": "V Dockeru nelze spustit přímou aktualizaci souborů."}), 400
        
    import subprocess
    import os
    
    try:
        # Spustíme git pull
        output = subprocess.check_output(["git", "pull", "origin", "main"], text=True, stderr=subprocess.STDOUT)
        
        # Plánovaný restart aplikace (supervisor ji restartuje automaticky po ukončení)
        def restart_app():
            import time
            time.sleep(2)
            os._exit(0)
            
        import threading
        threading.Thread(target=restart_app).start()
        
        return jsonify({"status": "success", "message": f"Aktualizace proběhla úspěšně:\n{output}"})
    except Exception as err:
        return jsonify({"status": "error", "message": f"Chyba při aktualizaci: {str(err)}"}), 500


@app.route("/api/config", methods=["POST"])
def save_config_endpoint():
    try:
        new_user_config = request.json
        # Načíst starý config, abychom zachovali strukturu
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                full_config = json.load(f)
        else:
            full_config = {}
            
        old_user = full_config.get("user", {})
        
        # Zachovat stavové klíče
        merged_user = {**old_user, **new_user_config}
        
        # Pokud posíláme prázdný klíč a starý existoval, zachováme ho
        if not new_user_config.get("gemini_api_key") and old_user.get("gemini_api_key"):
            merged_user["gemini_api_key"] = old_user["gemini_api_key"]
            
        full_config["user"] = merged_user
        
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(full_config, f, ensure_ascii=False, indent=2)
        return jsonify({"status": "success", "message": "Konfigurace uložena."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/listings/save", methods=["POST"])
def save_listing_endpoint():
    try:
        updated_ad = request.json
        if "title" in updated_ad:
            updated_ad["title"] = updated_ad["title"][:50].strip()
            
        # Get ID from data (it must have an ID for SQLite)
        listing_id = updated_ad.get("id")
        if not listing_id:
            return jsonify({"status": "error", "message": "Chybí ID inzerátu."}), 400
            
        # Prepare listing data for DB
        listing_data = {
            "id": listing_id,
            "title": updated_ad.get("title", "Bez názvu"),
            "description": updated_ad.get("description", ""),
            "price": int(updated_ad.get("price", 0)),
            "category": updated_ad.get("category", ""),
            "condition": updated_ad.get("condition", ""),
            "local_photos_dir": updated_ad.get("local_photos_dir", ""),
            "location": updated_ad.get("location", ""),
            "notes": updated_ad.get("notes", ""),
            "ad_password_b64": updated_ad.get("ad_password_b64", ""),
            "bookmarklet_uri": updated_ad.get("bookmarklet_uri", ""),
            "days_old": int(updated_ad.get("days_old", 0)),
            "created_at": updated_ad.get("date_created") or updated_ad.get("created_at"),
            "target_bazos": int(updated_ad.get("target_bazos", 1)),
            "target_aukro": int(updated_ad.get("target_aukro", 0))
        }
        
        # Also store portal states if they exist
        portal_states = updated_ad.get("portal_states") or {}
        # If there's legacy Bazoš state on the listing object itself (views, url, status):
        if "url" in updated_ad or "views" in updated_ad:
            portal_states.setdefault("bazos", {})
            if "url" in updated_ad:
                portal_states["bazos"]["url"] = updated_ad["url"]
            if "views" in updated_ad:
                portal_states["bazos"]["views"] = updated_ad["views"]
            if "status" in updated_ad:
                portal_states["bazos"]["status"] = updated_ad["status"]
                
        db.save_listing(listing_data, portal_states)
        return jsonify({"status": "success", "message": "Inzerát uložen."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/listings/add", methods=["POST"])
def add_listing_endpoint():
    try:
        new_ad_data = request.json
        title = new_ad_data.get("title", "novy_inzerat").strip()
        title_trimmed = title[:50].strip()
        
        # Vygenerujeme unikátní složku pro fotky na základě názvu
        title_slug = "".join([c if c.isalnum() else "_" for c in title_trimmed.lower()])
        photos_dir = f"photos/{title_slug}"
        os.makedirs(photos_dir, exist_ok=True)
        
        # Generate new unique ID for SQLite database
        listing_id = str(uuid.uuid4())
        
        # Nastavíme výchozí hodnoty
        new_ad = {
            "id": listing_id,
            "title": title_trimmed,
            "description": new_ad_data.get("description", ""),
            "price": int(new_ad_data.get("price", 0)),
            "category": new_ad_data.get("category", ""),
            "local_photos_dir": photos_dir,
            "url": "",
            "views": 0,
            "status": "Aktivní",
            "date_created": "",
            "notes": "",
            "target_bazos": int(new_ad_data.get("target_bazos", 1)),
            "target_aukro": int(new_ad_data.get("target_aukro", 0))
        }
        
        # Save to database
        db.save_listing(new_ad, {
            "bazos": {
                "portal_item_id": None,
                "url": "",
                "status": "Aktivní",
                "views": 0,
                "last_synced": None
            }
        })
        
        return jsonify({"status": "success", "message": "Inzerát přidán.", "ad": new_ad})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/listings/delete", methods=["POST", "DELETE"])
def delete_listing_endpoint():
    """Endpoint pro kompletní smazání inzerátu z databázi."""
    try:
        data = request.json or {}
        listing_id = data.get("id")
        if not listing_id:
            return jsonify({"status": "error", "message": "Chybí ID inzerátu"}), 400
        db.delete_listing(listing_id)
        return jsonify({"status": "success", "message": "Inzerát úspěšně smazán."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/action/<action_type>", methods=["POST"])
def run_action(action_type):
    global playwright_process
    try:
        if playwright_process and playwright_process.is_alive():
            return jsonify({"status": "error", "message": "Jiná operace již běží."}), 400

        # Odstraníme předchozí chybu, pokud existuje
        if os.path.exists("/tmp/playwright_error.txt"):
            try:
                os.remove("/tmp/playwright_error.txt")
            except Exception:
                pass

        payload = request.json or {}
        ad_id = payload.get("local_photos_dir") or payload.get("id")
        
        listings_data, user_config = load_data()
        
        # Najdeme inzerát podle ID, local_photos_dir nebo názvu
        selected_ad = None
        if ad_id and ad_id != "all":
            all_candidates = listings_data.get("active_listings", []) + listings_data.get("sold_listings", [])
            for ad in all_candidates:
                if (ad.get("id") == ad_id or 
                    ad.get("local_photos_dir") == ad_id or 
                    (ad.get("local_photos_dir") and ad_id in ad.get("local_photos_dir")) or
                    ad.get("title") == ad_id):
                    selected_ad = ad
                    break
                        
            if not selected_ad:
                return jsonify({"status": "error", "message": f"Inzerát '{ad_id}' nebyl nalezen."}), 404
                
        # Pro ostatní akce (post, edit_price, delete)
        extra_val = payload.get("extra_val") # např. nová cena
        
        # Spustíme neblokující Playwright akci na pozadí jako samostatný vláknový worker
        playwright_process = threading.Thread(
            target=process_target, 
            args=(selected_ad, user_config, action_type, extra_val),
            daemon=True
        )
        playwright_process.start()
        
        return jsonify({"status": "success", "message": f"Akce '{action_type}' úspěšně spuštěna na pozadí."})
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/action/status", methods=["GET"])
def action_status():
    global playwright_process
    running = False
    error = None
    
    if playwright_process:
        if playwright_process.is_alive():
            running = True
        else:
            if os.path.exists("/tmp/playwright_error.txt"):
                try:
                    with open("/tmp/playwright_error.txt", "r", encoding="utf-8") as f:
                        error = f.read().strip()
                except Exception:
                    pass
                    
    return jsonify({
        "running": running,
        "error": error
    })

@app.route("/api/action/cancel", methods=["POST"])
def cancel_action():
    global playwright_process
    try:
        if playwright_process and playwright_process.is_alive():
            log_debug("CANCEL: Cancelling active worker thread")
            # Zapíšeme, že operace byla přerušena
            with open("/tmp/playwright_error.txt", "w", encoding="utf-8") as f:
                f.write("Operace byla přerušena uživatelem.")
                
        return jsonify({"status": "success", "message": "Operace byla přerušena."})
    except Exception as e:
        log_debug(f"CANCEL ERR: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/ai/improve", methods=["POST"])
def ai_improve():
    try:
        payload = request.json
        text = payload.get("text", "")
        field_type = payload.get("field", "description") # 'title' nebo 'description'
        instruction_type = payload.get("instruction", "improve") # 'improve', 'fix', 'shorten', 'lengthen', 'title_suggestions'
        
        _, user_config = load_data()
        api_key = user_config.get("gemini_api_key", "")
        
        if not api_key:
            return jsonify({"status": "error", "message": "Chybí Gemini API klíč v nastavení."}), 400
            
        # Sestavíme system prompt pro optimalizaci prodejního textu na Bazoši
        system_prompt = (
            "Jsi AI asistent na úpravu prodejních textů pro Bazoš. "
            "Tvým úkolem je vždy vrátit POUZE upravený/opravený text bez jakýchkoliv dodatečných vysvětlení, "
            "pozdravů, uvozovek nebo komentářů. Vracíš pouze finální text, nic víc.\n\n"
            "Pokyny pro editaci:\n"
            "- Piš v češtině, jasně, čitelně a srozumitelně.\n"
            "- Používej odrážky pro parametry, stav a výhody.\n"
            "- Nepoužívej přehnané marketingové fráze a 'slop' slova (např. 'neuvěřitelná nabídka', 'jedinečná šance', 'TOP stav!!!').\n"
            "- Působ jako solidní, inženýrsky přesný a férový prodejce (podle standardů rodinné firmy TERMS s tradicí od roku 1991).\n"
            "- Text formátuj přehledně pomocí odstavců a klasických odrážek (např. '*' nebo '-').\n"
            "- Udržuj přibližně stejnou délku a rozsah jako původní text. NIKDY text nezkracuj drasticky a vždy dokonči celé myšlenky i věty.\n"
            "- Ponech všechny věcné parametry (výkon, rozměry, stav, doplňky) a kontaktní/odběrové informace z původního textu."
        )
        
        user_prompt = ""
        if field_type == "title":
            if instruction_type == "title_suggestions":
                user_prompt = f"Navrhni 5 různých atraktivních a chytlavých nadpisů pro inzerát na základě tohoto původního nadpisu: '{text}'. Nadpisy musí mít maximálně 50 znaků. VRAŤ POUZE TĚCHTO 5 NADPISŮ, KAŽDÝ NA NOVÉM ŘÁDKU, BEZ ODPOVĚDI OKOLO:"
            else:
                user_prompt = f"Vylepši tento nadpis inzerátu na Bazoš (max 50 znaků). VRAŤ POUZE VÝSLEDNÝ NADPIS BEZ UVOZOWEK A VYSVĚTLENÍ:\n\n{text}"
        else:
            if instruction_type == "improve":
                user_prompt = f"Vylepši tón a formátování tohoto popisu inzerátu. Zachovej všechny věcné parametry, doplňky a detaily z původního textu. Délka musí odpovídat původnímu rozsahu. VRAŤ POUZE VYLEPŠENÝ POPIS BEZ KOMENTÁŘŮ:\n\n{text}"
            elif instruction_type == "fix":
                user_prompt = f"Oprav gramatiku, překlepy a stylistiku v tomto popisu inzerátu. Zachovej všechny původní parametry a délku. VRAŤ POUZE OPRAVENÝ POPIS:\n\n{text}"
            elif instruction_type == "shorten":
                user_prompt = f"Zkrať tento popis inzerátu, udělej ho stručný a výstižný, ale zachovej klíčové parametry. VRAŤ POUZE STRUČNÝ POPIS:\n\n{text}"
            elif instruction_type == "lengthen":
                user_prompt = f"Rozšiř tento popis inzerátu o více detailů a detailní rozbor parametrů. VRAŤ POUZE ROZŠÍŘENÝ POPIS BEZ KOMENTÁŘŮ:\n\n{text}"
        
        success, result_text = improve_text_with_gemini(text, field_type, instruction_type, api_key)
        if not success:
            status_code = 500
            match = re.search(r"Status (\d+)", result_text)
            if match:
                status_code = int(match.group(1))
            return jsonify({"status": "error", "message": result_text}), status_code
            
        return jsonify({"status": "success", "result": result_text})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/advisor/price/<listing_id>", methods=["GET"])
def api_get_price_recommendation(listing_id):
    try:
        from listing_hub.ai.advisor import get_price_recommendation
        res = get_price_recommendation(listing_id)
        if "error" in res:
            return jsonify({"status": "error", "message": res["error"]}), 400
        return jsonify({"status": "success", "data": res})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/action/repost_with_new_price", methods=["POST"])
def api_repost_with_new_price():
    try:
        global playwright_process
        if playwright_process and playwright_process.is_alive():
            return jsonify({"status": "error", "message": "Jiná akce robota právě probíhá. Počkejte na dokončení."}), 409

        payload = request.json or {}
        listing_id = payload.get("listing_id")
        new_price = payload.get("new_price")

        if not listing_id or new_price is None:
            return jsonify({"status": "error", "message": "Chybí listing_id nebo new_price."}), 400

        # 1. Aktualizujeme cenu v SQLite databázi
        from listing_hub.core.db import get_db_connection, save_listing
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM listings WHERE id = ?", (listing_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return jsonify({"status": "error", "message": "Inzerát nebyl nalezen."}), 404
            
        listing_data = dict(row)
        listing_data["price"] = int(new_price)
        
        # Načteme a zachováme stavy portálů
        cursor.execute("SELECT * FROM portal_states WHERE listing_id = ?", (listing_id,))
        states_rows = cursor.fetchall()
        portal_states = {state["portal_name"]: dict(state) for state in states_rows}
        conn.close()
        
        save_listing(listing_data, portal_states)

        # 2. Spustíme znovuvystavení inzerátu (topování) na pozadí jako Playwright proces
        # Převedeme na formát pro legacy automat
        ad_legacy = {
            "title": listing_data["title"],
            "description": listing_data["description"],
            "price": listing_data["price"],
            "local_photos_dir": listing_data["local_photos_dir"],
            "url": portal_states.get("bazos", {}).get("url", ""),
            "ad_password_b64": listing_data["ad_password_b64"]
        }

        playwright_process = threading.Thread(
            target=process_target,
            args=(ad_legacy, user_config, "repost", None),
            daemon=True
        )
        playwright_process.start()

        return jsonify({
            "status": "success",
            "message": f"Cena inzerátu byla změněna na {new_price} Kč a bylo spuštěno znovuvystavení na Bazoši."
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def background_refresh_worker():
    import time
    from datetime import datetime, timedelta
    from post_to_bazos import load_data
    
    log_debug("Background refresh worker thread started.")
    while True:
        try:
            # 1. Zkontrolujeme, zda právě neběží jiná Playwright akce
            global playwright_process
            if playwright_process:
                if playwright_process.is_alive():
                    time.sleep(15)
                    continue
                else:
                    # Předchozí vlákno dokončilo práci
                    playwright_process = None
                
            # 2. Načteme konfiguraci
            _, user_config = load_data()
            
            auto_enabled = user_config.get("auto_refresh_enabled", False)
            auto_interval_minutes = int(user_config.get("auto_refresh_interval", 720))
            auto_status = user_config.get("auto_refresh_status", "ok")
            last_refresh_str = user_config.get("last_refresh_time", "")
            
            # Pokud není auto-refresh zapnutý nebo vyžaduje SMS, přeskočíme
            if not auto_enabled or auto_status == "needs_sms":
                time.sleep(15)
                continue
                
            # 3. Zkontrolujeme, zda uplynul interval
            should_refresh = False
            if not last_refresh_str:
                should_refresh = True
            else:
                try:
                    from datetime import timezone
                    last_refresh = datetime.fromisoformat(last_refresh_str)
                    if last_refresh.tzinfo is None:
                        last_refresh = last_refresh.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) - last_refresh >= timedelta(minutes=auto_interval_minutes):
                        should_refresh = True
                except Exception:
                    should_refresh = True
                    
            if should_refresh:
                log_debug(f"Triggering auto_refresh on background thread. Interval={auto_interval_minutes}m")
                # Spustíme synchronizaci na pozadí jako samostatné vlákno
                playwright_process = threading.Thread(
                    target=process_target,
                    args=(None, user_config, "auto_refresh", None),
                    daemon=True
                )
                playwright_process.start()
                
        except Exception as err:
            log_debug(f"Error in background worker loop: {err}")
            
        time.sleep(15)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--dry-run":
        print("Flask syntax OK.")
        sys.exit(0)
        
    # Inicializace databázových tabulek
    from listing_hub.core.db import init_db
    init_db()
        
    import threading
    t = threading.Thread(target=background_refresh_worker, daemon=True)
    t.start()
    
    app.run(host="0.0.0.0", port=PORT, debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true', threaded=True)



