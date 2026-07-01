import os
import sys
import json
import base64
import requests
from flask import Flask, render_template, jsonify, request
from pathlib import Path

# Přidáme aktuální adresář do sys.path, abychom mohli importovat post_to_bazos
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import multiprocessing
import asyncio

from post_to_bazos import load_data, save_listings, run_playwright_action, cli_update_listings_from_bazos, CONFIG_PATH, LISTINGS_PATH, session_manager

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
    log_debug("1. Background process started")
    
    # Catch SIGTERM to cleanly shut down Playwright session
    import signal
    import sys
    def sigterm_handler(signum, frame):
        log_debug("SIGTERM received, closing Playwright session manager...")
        try:
            from post_to_bazos import session_manager
            session_manager.close()
        except Exception as e:
            log_debug(f"SIGTERM handler close failed: {e}")
        sys.exit(15)
        
    signal.signal(signal.SIGTERM, sigterm_handler)
    
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
            log_debug("4. Calling cli_update_listings_from_bazos")
            is_auto = (action_type == "auto_refresh")
            try:
                cli_update_listings_from_bazos(listings_data, is_web=True, is_auto_refresh=is_auto)
                log_debug("5. Done cli_update_listings_from_bazos")
                post_to_bazos.save_listings(listings_data)
                
                # Zaznamenáme čas úspěšné aktualizace
                from post_to_bazos import CONFIG_PATH
                if CONFIG_PATH.exists():
                    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                        full_config = json.load(f)
                    full_config.setdefault("user", {})
                    full_config["user"]["auto_refresh_status"] = "ok"
                    full_config["user"]["last_refresh_time"] = datetime.now().isoformat()
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
    listings_data, _ = load_data()
    
    # Obohatíme inzeráty o počty fotek
    for ad in listings_data.get("active_listings", []):
        total, included = count_photos(ad.get("local_photos_dir"), ad.get("excluded_photos"))
        ad["photos_count"] = total
        ad["photos_upload_count"] = included
        
    for ad in listings_data.get("sold_listings", []):
        total, included = count_photos(ad.get("local_photos_dir"), ad.get("excluded_photos"))
        ad["photos_count"] = total
        ad["photos_upload_count"] = included
        
    return jsonify(listings_data)

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
        url = "https://api.github.com/repos/onhala/bazos-automat/commits/main"
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
            
        listings_data, _ = load_data()
        
        # Hledáme inzerát v aktivních i prodaných
        found = False
        for i, ad in enumerate(listings_data.get("active_listings", [])):
            if ad.get("local_photos_dir") == updated_ad.get("local_photos_dir"):
                listings_data["active_listings"][i] = updated_ad
                found = True
                break
                
        if not found:
            for i, ad in enumerate(listings_data.get("sold_listings", [])):
                if ad.get("local_photos_dir") == updated_ad.get("local_photos_dir"):
                    listings_data["sold_listings"][i] = updated_ad
                    found = True
                    break
                    
        if not found:
            # Pokud nebyl nalezen, přidáme do aktivních
            listings_data["active_listings"].append(updated_ad)
            
        save_listings(listings_data)
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
        
        # Nastavíme výchozí hodnoty
        new_ad = {
            "title": title_trimmed,
            "description": new_ad_data.get("description", ""),
            "price": int(new_ad_data.get("price", 0)),
            "local_photos_dir": photos_dir,
            "url": "",
            "views": 0,
            "status": "Aktivní",
            "date_created": "",
            "notes": ""
        }
        
        listings_data, _ = load_data()
        listings_data["active_listings"].append(new_ad)
        save_listings(listings_data)
        
        return jsonify({"status": "success", "message": "Inzerát přidán.", "ad": new_ad})
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
        ad_id = payload.get("local_photos_dir") # používáme složku jako unikátní klíč inzerátu
        
        listings_data, user_config = load_data()
        
        # Najdeme inzerát podle local_photos_dir
        selected_ad = None
        if ad_id and ad_id != "all":
            for ad in listings_data.get("active_listings", []):
                if ad.get("local_photos_dir") == ad_id:
                    selected_ad = ad
                    break
                    
            if not selected_ad:
                for ad in listings_data.get("sold_listings", []):
                    if ad.get("local_photos_dir") == ad_id:
                        selected_ad = ad
                        break
                        
            if not selected_ad:
                return jsonify({"status": "error", "message": "Inzerát nebyl nalezen."}), 404
                
        # Pro ostatní akce (post, edit_price, delete)
        extra_val = payload.get("extra_val") # např. nová cena
        
        # Spustíme neblokující Playwright akci na pozadí jako samostatný proces
        playwright_process = multiprocessing.Process(
            target=process_target, 
            args=(selected_ad, user_config, action_type, extra_val)
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
            elif playwright_process.exitcode != 0 and playwright_process.exitcode is not None:
                if playwright_process.exitcode in [15, -15, -9, 9]:
                    error = "Operace byla přerušena uživatelem."
                else:
                    error = f"Operace selhala s kódem {playwright_process.exitcode}."
                    
    return jsonify({
        "running": running,
        "error": error
    })

@app.route("/api/action/cancel", methods=["POST"])
def cancel_action():
    global playwright_process
    try:
        if playwright_process and playwright_process.is_alive():
            log_debug("CANCEL: Terminating playwright_process")
            playwright_process.terminate()
            playwright_process.join(timeout=2)
            if playwright_process.is_alive():
                playwright_process.kill()
            
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
            "- Text formátuj přehledně pomocí odstavců a klasických odrážek (např. '*' nebo '-')."
        )
        
        user_prompt = ""
        if field_type == "title":
            if instruction_type == "title_suggestions":
                user_prompt = f"Navrhni 5 různých atraktivních a chytlavých nadpisů pro inzerát na základě tohoto původního nadpisu: '{text}'. Nadpisy musí mít maximálně 50 znaků. VRAŤ POUZE TĚCHTO 5 NADPISŮ, KAŽDÝ NA NOVÉM ŘÁDKU, BEZ ODPOVĚDI OKOLO:"
            else:
                user_prompt = f"Vylepši tento nadpis inzerátu na Bazoš (max 50 znaků). VRAŤ POUZE VÝSLEDNÝ NADPIS BEZ UVOZOWEK A VYSVĚTLENÍ:\n\n{text}"
        else:
            if instruction_type == "improve":
                user_prompt = f"VRAŤ POUZE VYLEPŠENÝ POPIS BEZ JAKÝCHKOLIV DALŠÍCH SLOV NEBO POZDRAVŮ:\n\n{text}"
            elif instruction_type == "fix":
                user_prompt = f"VRAŤ POUZE GRAMATICKY A STYLISTICKY OPRAVENÝ POPIS BEZ JAKÝCHKOLIV DALŠÍCH SLOV NEBO POZDRAVŮ:\n\n{text}"
            elif instruction_type == "shorten":
                user_prompt = f"VRAŤ POUZE STRUČNÝ POPIS BEZ JAKÝCHKOLIV DALŠÍCH SLOV NEBO POZDRAVŮ:\n\n{text}"
            elif instruction_type == "lengthen":
                user_prompt = f"VRAŤ POUZE ROZŠÍŘENÝ POPIS BEZ JAKÝCHKOLIV DALŠÍCH SLOV NEBO POZDRAVŮ:\n\n{text}"
        
        # Volání Gemini API
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [{
                "parts": [
                    {"text": system_prompt + "\n\nInstrukce: " + user_prompt}
                ]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 1024
            }
        }
        
        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 200:
            return jsonify({"status": "error", "message": f"Chyba Gemini API: {response.text}"}), response.status_code
            
        result_json = response.json()
        try:
            improved_text = result_json["candidates"][0]["content"]["parts"][0]["text"].strip()
            
            if field_type == "title":
                if instruction_type == "title_suggestions":
                    cleaned_lines = []
                    for line in improved_text.split("\n"):
                        line_str = line.strip()
                        if not line_str:
                            continue
                        # Vyčistit čísla odrážek např. "1. Nadpis" -> "Nadpis"
                        cleaned = re.sub(r'^\d+[\.\)\-]\s*', '', line_str).strip()
                        cleaned_lines.append(cleaned[:50].strip())
                    improved_text = "\n".join(cleaned_lines)
                else:
                    # Odstraníme případné uvozovky, které AI občas generuje
                    improved_text = improved_text.replace('"', '').replace("'", "").strip()
                    improved_text = improved_text[:50].strip()
                    
            return jsonify({"status": "success", "result": improved_text})
        except (KeyError, IndexError) as parse_err:
            return jsonify({"status": "error", "message": f"Selhalo parsování odpovědi Gemini API: {str(parse_err)}"}), 500
            
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
            if playwright_process and playwright_process.is_alive():
                time.sleep(15)
                continue
                
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
                    last_refresh = datetime.fromisoformat(last_refresh_str)
                    if datetime.now() - last_refresh >= timedelta(minutes=auto_interval_minutes):
                        should_refresh = True
                except Exception:
                    should_refresh = True
                    
            if should_refresh:
                log_debug(f"Triggering auto_refresh on background thread. Interval={auto_interval_minutes}m")
                # Spustíme synchronizaci na pozadí jako samostatný proces
                playwright_process = multiprocessing.Process(
                    target=process_target,
                    args=(None, user_config, "auto_refresh", None)
                )
                playwright_process.start()
                
        except Exception as err:
            log_debug(f"Error in background worker loop: {err}")
            
        time.sleep(15)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--dry-run":
        print("Flask syntax OK.")
        sys.exit(0)
        
    import threading
    t = threading.Thread(target=background_refresh_worker, daemon=True)
    t.start()
    
    app.run(host="0.0.0.0", port=PORT, debug=True, threaded=False)



