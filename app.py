import os
import sys
import json
import re
import base64
import requests
from flask import Flask, render_template, jsonify, request, Response
from pathlib import Path

# Přidáme aktuální adresář do sys.path, abychom mohli importovat post_to_bazos
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import multiprocessing
import threading
import asyncio

from post_to_bazos import load_data, save_listings, run_playwright_action, cli_update_listings_from_bazos, LISTINGS_PATH, session_manager
from listing_hub.core.config import CONFIG_PATH, SESSION_STATE_PATH, PHOTOS_DIR, PROJECT_ROOT
import uuid
import listing_hub.core.db as db
from listing_hub.ai.gemini import improve_text_with_gemini
from listing_hub.ai.vision import analyze_photos_with_vision
from listing_hub.core.version import get_version_status, is_docker, APP_VERSION
from listing_hub.core.calendar import generate_ical_feed
from listing_hub.ai.photo_editor import process_photo_pipeline

app = Flask(__name__)

# Konfigurace Flasku pro běh za Nginx reverzní proxy
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

playwright_process = None

from datetime import datetime
import shutil

class ActionStateManager:
    IDLE = "idle"
    RUNNING = "running"
    READY_FOR_REVIEW = "ready_for_review"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"

    def __init__(self):
        self._lock = threading.RLock()
        self.state = self.IDLE
        self.action_type = None
        self.listing_id = None
        self.ad_data = None
        self.error_message = None

    def start_action(self, action_type, listing_id=None, ad_data=None):
        with self._lock:
            self.state = self.RUNNING
            self.action_type = action_type
            self.listing_id = listing_id
            self.ad_data = ad_data
            self.error_message = None

    def set_ready_for_review(self):
        with self._lock:
            self.state = self.READY_FOR_REVIEW

    def set_completed(self):
        with self._lock:
            self.state = self.COMPLETED

    def set_error(self, message):
        with self._lock:
            self.state = self.ERROR
            self.error_message = message

    def set_cancelled(self):
        with self._lock:
            self.state = self.CANCELLED

    def reset(self):
        with self._lock:
            self.state = self.IDLE
            self.action_type = None
            self.listing_id = None
            self.ad_data = None
            self.error_message = None

    def get_status(self):
        with self._lock:
            return {
                "state": self.state,
                "action_type": self.action_type,
                "listing_id": self.listing_id,
                "error": self.error_message
            }

action_state_mgr = ActionStateManager()

def safe_delete_photos_dir(raw_photos_dir):
    """Safely delete directory of photos within PHOTOS_DIR, preventing path traversal."""
    if not raw_photos_dir:
        return False
    try:
        photos_base = Path(PHOTOS_DIR).resolve()
        target = Path(raw_photos_dir)
        if not target.is_absolute():
            target = (photos_base / target).resolve()
        else:
            target = target.resolve()
        
        if target == photos_base or not target.is_relative_to(photos_base):
            log_debug(f"Security: Refusing to delete path outside PHOTOS_DIR: {target}")
            return False
            
        if target.exists() and target.is_dir():
            shutil.rmtree(target)
            log_debug(f"Photos directory safely removed: {target}")
            return True
    except Exception as e:
        log_debug(f"Error removing photos dir {raw_photos_dir}: {e}")
    return False

def log_debug(msg):
    try:
        with open("/tmp/thread_debug.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {msg}\n")
    except Exception:
        pass

def process_target(ad, user_config, action_type, extra_val):
    log_debug("1. Background thread started")
    ad_id = (ad.get("id") or ad.get("local_photos_dir")) if ad else None
    action_state_mgr.start_action(action_type, listing_id=ad_id, ad_data=ad)
    
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
            if success:
                if action_type == "post":
                    action_state_mgr.set_ready_for_review()
                elif action_type == "delete":
                    if ad and ad.get("id"):
                        try:
                            db.delete_listing(ad["id"])
                        except Exception as del_err:
                            log_debug(f"Error cascading db delete: {del_err}")
                    action_state_mgr.set_completed()
                else:
                    action_state_mgr.set_completed()
            else:
                action_state_mgr.set_error("Akce byla stornována nebo selhala.")
                with open("/tmp/playwright_error.txt", "w", encoding="utf-8") as f:
                    f.write("Akce byla stornována nebo selhala.")
    except Exception as e:
        log_debug(f"ERR: {e}")
        action_state_mgr.set_error(str(e))
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
    # Ensure Playwright browser session is running so frames start streaming
    if not session_manager.running or not session_manager.page or session_manager.page.is_closed():
        session_manager.start_worker()

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

@app.route("/api/screencast/start", methods=["POST", "GET"])
def screencast_start():
    """Explicitly start or ping the Playwright browser worker."""
    try:
        session_manager.start_worker()
        return jsonify({"status": "ok", "running": session_manager.running})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/screencast/input", methods=["POST"])
def screencast_input():
    """Handle mouse clicks and keyboard input from HTML5 Canvas via thread-safe CDP dispatching."""
    data = request.json or {}
    action = data.get("action")
    
    if not session_manager.page or session_manager.page.is_closed():
        try:
            session_manager.get_session()
            if session_manager.page:
                session_manager.run_on_worker(lambda p, *_: p.goto("https://www.bazos.cz/moje-inzeraty.php"))
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
        elif action == "scroll":
            x = data.get("x", 0)
            y = data.get("y", 0)
            delta_x = data.get("deltaX", 0)
            delta_y = data.get("deltaY", 0)
            success = session_manager.send_cdp_scroll(x, y, delta_x, delta_y)
            return jsonify({"status": "ok" if success else "error", "action": "scroll"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
        
@app.route("/api/sms_code", methods=["POST"])
def submit_sms_code():
    data = request.json or {}
    code = data.get("code", "").strip()
    # Očistíme kód od mezer a pomlček, pokud obsahuje číslice
    digits_only = "".join(ch for ch in code if ch.isdigit())
    if len(digits_only) >= 4:
        code = digits_only
    if not code:
        return jsonify({"status": "error", "message": "SMS kód je prázdný"}), 400

    if not session_manager.running or not session_manager.page or session_manager.page.is_closed():
        try:
            session_manager.start_worker()
            session_manager.get_session()
        except Exception as e:
            return jsonify({"status": "error", "message": f"Nelze inicializovat prohlížeč: {e}"}), 500
        
    def _fill_sms(page, *args):
        if not page or page.is_closed():
            return {"submitted": False, "message": "Prohlížeč není otevřen."}

        # 1. SMS specifické selektory (klic = Mobilní klíč pro nový inzerát, kodd = SMS kód pro přihlášení)
        # POZOR: teloverit je telefonní číslo, NIKOLIV kód z SMS!
        selectors = [
            "input[name='klic']",
            "input[id='klic']",
            "input[name='kodd']",
            "input[id='kodd']",
            "input[name='cr']",
            "input[name='kod']",
            "input[name='overkod']",
            "input[placeholder*='klíč']",
            "input[placeholder*='klic']",
            "input[placeholder*='kód']",
            "input[placeholder*='kod']",
            "input[placeholder*='SMS']",
            "input[placeholder*='sms']",
            "input[name*='kod']",
            "input[name*='sms']",
            "input[maxlength='6']"
        ]
        code_input = None
        matched_sel = None
        for sel in selectors:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible():
                code_input = loc.first
                matched_sel = sel
                break
                
        # 2. Pokud jsme nenašli SMS pole specifickým selektorem, zkontrolujeme aktivní element
        if not code_input:
            try:
                active_info = page.evaluate('''() => {
                    const el = document.activeElement;
                    if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') && el.type !== 'hidden') {
                        return { name: el.name || '', id: el.id || '', placeholder: el.placeholder || '', type: el.type };
                    }
                    return null;
                }''')
                if active_info:
                    act_name = (active_info.get("name") or "").lower()
                    if act_name not in ("teloverit", "telefon", "telefoni", "hledat", "hlokalita", "mail", "email", "cena", "nadpis"):
                        code_input = page.locator("*:focus")
                        matched_sel = f":focus ({act_name or active_info.get('type')})"
            except Exception:
                pass

        if not code_input:
            # Poskytneme uživateli detailní diagnostiku viditelných prvků
            page_info = page.evaluate('''() => {
                const inputs = Array.from(document.querySelectorAll('input:not([type="hidden"]), select, textarea'))
                    .filter(el => {
                        const r = el.getBoundingClientRect();
                        return r.width > 0 && r.height > 0;
                    })
                    .map(el => el.name || el.id || el.placeholder || el.tagName.toLowerCase());
                return { inputs: inputs, url: window.location.href };
            }''')
            vis_inputs = page_info.get("inputs", [])
            if "teloverit" in vis_inputs:
                return {
                    "submitted": False,
                    "visible_inputs": vis_inputs,
                    "url": page_info.get("url", ""),
                    "message": "Na stránce je pole pro telefonní číslo ('teloverit'), nikoliv pro SMS kód. Odesílá se nejprve telefon."
                }
            return {
                "submitted": False,
                "visible_inputs": vis_inputs,
                "url": page_info.get("url", ""),
                "message": f"Pole pro SMS kód (klic/kodd) nebylo nalezeno. Viditelná pole na stránce: [{', '.join(vis_inputs) if vis_inputs else 'žádná'}]."
            }

        try:
            code_input.click()
        except Exception:
            pass
        code_input.fill(code)
        time.sleep(0.3)
        
        submit_btn = page.locator(
            "form:has(input[name='klic']) input[type='submit'], "
            "form:has(input[name='kodd']) input[type='submit'], "
            "input[type='submit'][value*='Vypsat inzeráty'], "
            "input[type='submit'][value*='Vypsat'], "
            "input[type='submit'][value*='Odeslat'], "
            "input[type='submit'][value*='Ověřit'], "
            "input[type='submit'][value*='Potvrdit'], "
            "button[type='submit']"
        )
        btn_clicked = "Enter keypress"
        if submit_btn.count() > 0 and submit_btn.first.is_visible():
            btn_clicked = submit_btn.first.get_attribute("value") or "Odeslat"
            submit_btn.first.click()
        else:
            code_input.press("Enter")
            
        time.sleep(1.0)
        session_manager.save_state()
        field_name = code_input.get_attribute("name") or code_input.get_attribute("id") or matched_sel or "SMS pole"
        return {
            "submitted": True,
            "target_field": field_name,
            "button_clicked": btn_clicked,
            "url": page.url,
            "message": f"SMS kód byl úspěšně vepsán do pole '{field_name}' a odeslán ({btn_clicked})."
        }
        
    try:
        result = session_manager.run_on_worker(_fill_sms)
        if isinstance(result, dict):
            status = "ok" if result.get("submitted") else "error"
            return jsonify({"status": status, **result})
        success = bool(result)
        return jsonify({"status": "ok" if success else "error", "submitted": success})
    except Exception as e:
        return jsonify({"status": "error", "submitted": False, "message": str(e)}), 500

@app.route("/api/browser/focus-input", methods=["POST"])
def browser_focus_input():
    """Manuálně zaměří (fokusuje) nejpravděpodobnější SMS/code input na aktuální stránce.
    Vrací info o zaměřeném poli, aby uživatel věděl, kam bude psát."""
    if not session_manager.running or not session_manager.page or session_manager.page.is_closed():
        return jsonify({"status": "error", "message": "Prohlížeč není aktivní"}), 400

    def _focus_input(page, *args):
        if not page or page.is_closed():
            return None
        result = page.evaluate(r"""() => {
            const SMS_NAMES = ['klic','kodd','cr','kod','overkod','sms','code','pin'];
            const all = [...document.querySelectorAll(
                "input[type='text'], input[type='number'], input[type='tel'], input:not([type])"
            )].filter(el => {
                const s = window.getComputedStyle(el);
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0
                    && s.display !== 'none'
                    && s.visibility !== 'hidden'
                    && !el.disabled && !el.readOnly;
            });

            // Seřaď – SMS/code pole mají absolutní přednost
            const scored = all.map(el => {
                const n = (el.name || '').toLowerCase();
                const i = (el.id || '').toLowerCase();
                const p = (el.placeholder || '').toLowerCase();
                const skip = ['hledat','search','email','mail','cena','nadpis'];
                let score = 0;
                if (SMS_NAMES.some(k => n.includes(k) || i.includes(k) || p.includes(k))) score += 150;
                if (n === 'teloverit' || i === 'teloverit') score += 50; // telefon má nižší prioritu než SMS klíč
                if (el.maxLength && el.maxLength <= 8) score += 20;
                if (skip.some(k => n.includes(k) || i.includes(k))) score -= 200;
                return { el, score, name: el.name || '', id: el.id || '',
                         placeholder: el.placeholder || '', maxlength: el.maxLength };
            }).sort((a, b) => b.score - a.score);

            if (scored.length === 0) return null;
            const best = scored[0];
            best.el.focus();
            best.el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            // Vizuální highlight na 1.5s
            const orig = best.el.style.outline;
            best.el.style.outline = '3px solid #f59e0b';
            best.el.style.boxShadow = '0 0 12px #f59e0b';
            setTimeout(() => {
                best.el.style.outline = orig;
                best.el.style.boxShadow = '';
            }, 1800);
            return { name: best.name, id: best.id, placeholder: best.placeholder,
                     maxlength: best.maxlength, score: best.score,
                     total_inputs: scored.length };
        }""")
        return result

    try:
        info = session_manager.run_on_worker(_focus_input)
        if info:
            label = info.get("name") or info.get("id") or info.get("placeholder") or "neznámé pole"
            return jsonify({"status": "ok", "focused": True, "field": label, "info": info})
        else:
            return jsonify({"status": "error", "focused": False, "message": "Žádné vstupní pole nenalezeno"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/browser/inspect", methods=["GET"])
@app.route("/api/debug/page", methods=["GET"])
def browser_inspect():
    """Vrací detailní diagnostiku otevřené stránky v prohlížeči: URL, titulek, detekovaný stav Bazoše,
    všechna formulářová pole s fokusem a hodnotami, alerty/chyby a ovládací tlačítka."""
    if not session_manager.running or not session_manager.page or session_manager.page.is_closed():
        return jsonify({
            "status": "closed",
            "url": "",
            "title": "",
            "detected_step": "closed",
            "step_description": "Prohlížeč není spuštěn.",
            "inputs": [],
            "alerts": []
        })

    def _inspect(page, *args):
        if not page or page.is_closed():
            return {"status": "closed"}
        
        info = page.evaluate(r"""() => {
            const inputs = Array.from(document.querySelectorAll('input, textarea, select')).map(el => {
                const rect = el.getBoundingClientRect();
                const isVis = (rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).display !== 'none' && window.getComputedStyle(el).visibility !== 'hidden');
                let valPreview = '';
                if (el.type === 'password') {
                    valPreview = el.value ? '***' : '';
                } else if (el.type === 'checkbox') {
                    valPreview = el.checked ? 'zaškrtnuto' : 'nezaškrtnuto';
                } else {
                    valPreview = el.value ? (el.value.length > 25 ? el.value.substring(0, 25) + '...' : el.value) : '';
                }
                return {
                    tag: el.tagName.toLowerCase(),
                    type: el.type || '',
                    name: el.name || '',
                    id: el.id || '',
                    placeholder: el.placeholder || '',
                    value: valPreview,
                    visible: isVis,
                    focused: (document.activeElement === el),
                    disabled: el.disabled || el.readOnly
                };
            });

            const buttons = Array.from(document.querySelectorAll('input[type="submit"], button')).map(el => {
                const rect = el.getBoundingClientRect();
                const isVis = (rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).display !== 'none' && window.getComputedStyle(el).visibility !== 'hidden');
                return {
                    tag: el.tagName.toLowerCase(),
                    text: (el.value || el.innerText || '').trim(),
                    visible: isVis,
                    type: el.type || 'button'
                };
            }).filter(b => b.visible && b.text.length > 0);

            const alerts = Array.from(document.querySelectorAll('.upozorneni, .chyba, font[color="red"], span[style*="red"], div[style*="red"], p[style*="red"]'))
                .map(el => el.innerText.trim())
                .filter(txt => txt.length > 0 && txt.length < 250);

            return {
                url: window.location.href,
                title: document.title,
                inputs: inputs.filter(i => i.visible || i.type === 'hidden'),
                buttons: buttons,
                alerts: alerts
            };
        }""")

        inputs = info.get("inputs", [])
        has_klic = any(i.get("name") == "klic" and i.get("visible") for i in inputs)
        has_kodd = any(i.get("name") == "kodd" and i.get("visible") for i in inputs)
        has_teloverit = any(i.get("name") == "teloverit" and i.get("visible") for i in inputs)
        has_nadpis = any(i.get("name") == "nadpis" and i.get("visible") for i in inputs)
        has_login_mail = any(i.get("name") in ("mail", "email") and i.get("visible") for i in inputs)

        detected_step = "other"
        step_description = "Běžná stránka"
        if has_klic:
            detected_step = "sms_new_ad"
            step_description = "Bazoš: Zadání SMS Mobilního klíče ('klic') pro vystavení nového inzerátu"
        elif has_kodd:
            detected_step = "sms_login"
            step_description = "Bazoš: Zadání SMS ověřovacího kódu ('kodd') pro přihlášení / správu"
        elif has_teloverit:
            detected_step = "phone_new_ad"
            step_description = "Bazoš: Krok 1 – Zadání telefonního čísla ('teloverit')"
        elif has_nadpis:
            detected_step = "ad_form"
            step_description = "Bazoš: Formulář inzerátu (pole 'nadpis' připraveno)"
        elif has_login_mail:
            detected_step = "login_form"
            step_description = "Bazoš: Přihlašovací formulář (e-mail a telefon)"

        return {
            "status": "running",
            "url": info.get("url", ""),
            "title": info.get("title", ""),
            "detected_step": detected_step,
            "step_description": step_description,
            "inputs": inputs,
            "buttons": info.get("buttons", []),
            "alerts": info.get("alerts", [])
        }

    try:
        res = session_manager.run_on_worker(_inspect)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/browser/fill-field", methods=["POST"])
def browser_fill_field():
    """Umožňuje z UI kliknutím zaměřit a vyplnit konkrétní pole v prohlížeči."""
    if not session_manager.running or not session_manager.page or session_manager.page.is_closed():
        return jsonify({"status": "error", "message": "Prohlížeč není spuštěn"}), 400

    req = request.json or {}
    field_name = req.get("field_name")
    value = req.get("value", "")
    submit = req.get("submit", False)

    if not field_name:
        return jsonify({"status": "error", "message": "Název pole je povinný"}), 400

    def _fill_target(page, *args):
        if not page or page.is_closed():
            return {"status": "error", "message": "Prohlížeč je zavřen"}

        loc = page.locator(f"input[name='{field_name}'], input[id='{field_name}'], textarea[name='{field_name}']")
        if loc.count() == 0:
            loc = page.locator(f"[placeholder*='{field_name}']")
        if loc.count() > 0 and loc.first.is_visible():
            target = loc.first
            target.focus()
            target.scroll_into_view_if_needed()
            try:
                target.evaluate("el => { el.style.outline = '3px solid #10b981'; el.style.boxShadow = '0 0 12px #10b981'; }")
            except Exception:
                pass
            if value:
                target.fill(value)
            if submit:
                submit_btn = target.locator("xpath=ancestor::form//input[@type='submit'] | xpath=ancestor::form//button[@type='submit']")
                if submit_btn.count() > 0 and submit_btn.first.is_visible():
                    submit_btn.first.click()
                else:
                    target.press("Enter")
            return {
                "status": "ok",
                "field": field_name,
                "focused": True,
                "filled": bool(value),
                "submitted": submit,
                "message": f"Pole '{field_name}' bylo zaměřeno" + (f" a vyplněno hodnotou." if value else ".")
            }
        return {"status": "error", "message": f"Pole '{field_name}' nebylo na stránce nalezeno nebo není viditelné."}

    try:
        res = session_manager.run_on_worker(_fill_target)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

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
            
        photos_dir = ad.get("local_photos_dir")
        p_count = 0
        if photos_dir:
            try:
                p_path = Path(photos_dir) if Path(photos_dir).is_absolute() else (PROJECT_ROOT / photos_dir)
                if p_path.exists():
                    all_imgs = [f for f in os.listdir(p_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
                    p_count = len(all_imgs)
            except Exception:
                pass

        ad_dict = {
            "id": ad.get("id"),
            "title": ad.get("title"),
            "description": ad.get("description"),
            "price": ad.get("price"),
            "category": ad.get("category"),
            "condition": ad.get("condition"),
            "local_photos_dir": ad.get("local_photos_dir"),
            "photos_count": p_count,
            "photos_upload_count": min(p_count, 10),
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

def resolve_photos_dir(raw_photos_dir: str) -> str:
    if not raw_photos_dir:
        return str(PHOTOS_DIR)
    p = Path(raw_photos_dir)
    if p.is_absolute():
        return str(p)
    return str(PROJECT_ROOT / p)

@app.route("/api/photos", methods=["GET"])
def get_photos():
    raw_dir = request.args.get("photos_dir", "")
    photos_dir = resolve_photos_dir(raw_dir)
    if not photos_dir or not os.path.isdir(photos_dir):
        return jsonify({"photos": []})
    try:
        raw_files = os.listdir(photos_dir)
        img_files = sorted(
            [f for f in raw_files if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))],
            key=lambda x: (not x.startswith("foto_"), x)
        )
        photos = []
        for fname in img_files:
            fpath = os.path.join(photos_dir, fname)
            try:
                with open(fpath, "rb") as f:
                    data = base64.b64encode(f.read()).decode("utf-8")
                ext = fname.rsplit(".", 1)[-1].lower()
                mime = "image/jpeg" if ext in ("jpg", "jpeg") else ("image/webp" if ext == "webp" else "image/png")
                photos.append({"filename": fname, "data_url": f"data:{mime};base64,{data}"})
            except Exception:
                photos.append({"filename": fname, "data_url": ""})
        return jsonify({"photos": photos})
    except Exception as e:
        return jsonify({"error": str(e), "photos": []}), 500

@app.route("/api/photos/upload", methods=["POST"])
def upload_photos():
    try:
        raw_dir = request.form.get("photos_dir", "").strip()
        photos_dir = resolve_photos_dir(raw_dir)
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
                
                while os.path.exists(os.path.join(photos_dir, f"foto_{counter}.{ext}")):
                    counter += 1

                filename = f"foto_{counter}.{ext}"
                counter += 1
                save_path = os.path.join(photos_dir, filename)
                file.save(save_path)
                saved.append(filename)

        return jsonify({"status": "success", "message": f"Úspěšně nahráno {len(saved)} fotek.", "saved_files": saved})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/photos/delete", methods=["POST", "DELETE"])
def delete_photo():
    try:
        data = request.json or {}
        raw_dir = data.get("photos_dir", "").strip()
        photos_dir = resolve_photos_dir(raw_dir)
        filename = os.path.basename(data.get("filename", "").strip())
        if not photos_dir or not filename:
            return jsonify({"status": "error", "message": "Chybí složka nebo název fotky."}), 400
            
        file_path = os.path.join(photos_dir, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            return jsonify({"status": "success", "message": "Fotka smazána."})
        return jsonify({"status": "error", "message": "Fotka nenalezena."}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/photos/rotate", methods=["POST"])
def rotate_photo():
    try:
        data = request.json or {}
        raw_dir = data.get("photos_dir", "").strip()
        photos_dir = resolve_photos_dir(raw_dir)
        filename = os.path.basename(data.get("filename", "").strip())
        angle = int(data.get("angle", 90))
        if not photos_dir or not filename:
            return jsonify({"status": "error", "message": "Chybí složka nebo název fotky."}), 400

        file_path = os.path.join(photos_dir, filename)
        if not os.path.exists(file_path):
            return jsonify({"status": "error", "message": f"Fotka '{filename}' nenalezena ve složce '{photos_dir}'."}), 404

        try:
            from PIL import Image, ImageOps
            with Image.open(file_path) as img:
                img = ImageOps.exif_transpose(img)
                rotated = img.rotate(-angle, expand=True)
                rotated.save(file_path)
            return jsonify({"status": "success", "message": "Fotka byla otočena."})
        except ImportError:
            return jsonify({"status": "error", "message": "Pillow (PIL) není nainstalována."}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/photos/reorder", methods=["POST"])
def reorder_photos():
    try:
        data = request.json or {}
        raw_dir = data.get("photos_dir", "").strip()
        photos_dir = resolve_photos_dir(raw_dir)
        filenames = data.get("filenames", [])
        if not photos_dir or not os.path.isdir(photos_dir) or not filenames:
            return jsonify({"status": "error", "message": "Chybí složka nebo seznam fotek."}), 400

        temp_renames = []
        for idx, old_fname in enumerate(filenames):
            old_path = os.path.join(photos_dir, old_fname)
            if os.path.exists(old_path):
                ext = old_fname.rsplit(".", 1)[-1].lower() if "." in old_fname else "jpg"
                temp_path = os.path.join(photos_dir, f"__tmp_reorder_{idx}_{uuid.uuid4().hex[:6]}.{ext}")
                os.rename(old_path, temp_path)
                temp_renames.append((temp_path, ext))

        final_filenames = []
        for idx, (tmp_path, ext) in enumerate(temp_renames, 1):
            new_fname = f"foto_{idx}.{ext}"
            new_path = os.path.join(photos_dir, new_fname)
            os.rename(tmp_path, new_path)
            final_filenames.append(new_fname)

        return jsonify({"status": "success", "message": "Pořadí fotek bylo aktualizováno.", "filenames": final_filenames})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/photos/edit/preview", methods=["POST"])
def api_photo_edit_preview():
    try:
        payload = request.get_json(silent=True) or {}
        operations = payload.get("operations", [])
        image_bytes = None

        # 1. Pokud je poslán přímo base64 (např. z wizardu)
        raw_b64 = payload.get("image_b64", "")
        if raw_b64:
            if "," in raw_b64:
                raw_b64 = raw_b64.split(",", 1)[1]
            image_bytes = base64.b64decode(raw_b64)
        else:
            # 2. Načtení z disku přes photos_dir nebo listing_id + filename
            filename = payload.get("filename", "")
            raw_photos_dir = payload.get("photos_dir", "")
            listing_id = payload.get("listing_id", "")

            if not raw_photos_dir and listing_id:
                conn = db.get_db_connection()
                row = conn.cursor().execute("SELECT local_photos_dir FROM listings WHERE id = ?", (listing_id,)).fetchone()
                conn.close()
                if row:
                    raw_photos_dir = row["local_photos_dir"]

            if raw_photos_dir and filename:
                photos_dir = resolve_photos_dir(raw_photos_dir)
                photo_path = Path(photos_dir) / filename
                if photo_path.is_file():
                    image_bytes = photo_path.read_bytes()

        if not image_bytes:
            return jsonify({"status": "error", "message": "Fotografie nebyla nalezena nebo chybí obrazová data."}), 400

        result_bytes = process_photo_pipeline(image_bytes, operations)
        result_b64 = base64.b64encode(result_bytes).decode("utf-8")

        return jsonify({
            "status": "success",
            "data_url": f"data:image/jpeg;base64,{result_b64}"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba při úpravě fotografie: {e}"}), 500

@app.route("/api/photos/edit/save", methods=["POST"])
def api_photo_edit_save():
    try:
        payload = request.get_json(silent=True) or {}
        operations = payload.get("operations", [])
        raw_fn = payload.get("filename", "").strip()
        filename = os.path.basename(raw_fn)
        raw_photos_dir = payload.get("photos_dir", "")
        listing_id = payload.get("listing_id", "")
        raw_b64 = payload.get("image_b64", "")

        if not raw_photos_dir and listing_id:
            conn = db.get_db_connection()
            row = conn.cursor().execute("SELECT local_photos_dir FROM listings WHERE id = ?", (listing_id,)).fetchone()
            conn.close()
            if row:
                raw_photos_dir = row["local_photos_dir"]

        photos_dir = resolve_photos_dir(raw_photos_dir)
        if not filename or not photos_dir:
            return jsonify({"status": "error", "message": "Chybí složka nebo název souboru."}), 400

        photo_path = Path(photos_dir) / filename

        if raw_b64:
            # Přímé uložení hotového base64
            if "," in raw_b64:
                raw_b64 = raw_b64.split(",", 1)[1]
            final_bytes = base64.b64decode(raw_b64)
        elif photo_path.is_file():
            # Aplikace operací na existující soubor
            orig_bytes = photo_path.read_bytes()
            final_bytes = process_photo_pipeline(orig_bytes, operations)
        else:
            return jsonify({"status": "error", "message": "Cílový soubor fotografie nebyl nalezen."}), 404

        # Přímý přepis bez zálohy dle ADR-04
        photo_path.write_bytes(final_bytes)

        return jsonify({
            "status": "success",
            "message": "Fotografie byla úspěšně upravena a uložena."
        })
    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba při ukládání fotografie: {e}"}), 500


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

@app.route("/api/calendar/feed.ics", methods=["GET"])
def get_calendar_feed():
    try:
        _, user_config = load_data()
        configured_token = user_config.get("calendar_token", "").strip()
        
        # Ověření tokenu (přes query parametr token nebo key)
        req_token = (request.args.get("token") or request.args.get("key") or "").strip()
        if configured_token and req_token != configured_token:
            return Response("Neplatný nebo chybějící přístupový token kalendáře.", status=403, mimetype="text/plain; charset=utf-8")

        listings = db.get_all_listings()
        base_url = request.host_url.rstrip("/")
        ical_content = generate_ical_feed(listings, base_hub_url=base_url)

        return Response(
            ical_content,
            mimetype="text/calendar; charset=utf-8",
            headers={
                "Content-Disposition": "inline; filename=listing_hub_calendar.ics",
                "Cache-Control": "no-cache, no-store, must-revalidate"
            }
        )
    except Exception as e:
        return Response(f"Chyba při generování kalendáře: {e}", status=500, mimetype="text/plain; charset=utf-8")

@app.route("/api/calendar/token/regenerate", methods=["POST"])
def regenerate_calendar_token():
    try:
        import secrets
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                full_config = json.load(f)
        else:
            full_config = {}
            
        user_cfg = full_config.get("user", {})
        new_token = secrets.token_hex(16)
        user_cfg["calendar_token"] = new_token
        full_config["user"] = user_cfg

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(full_config, f, ensure_ascii=False, indent=2)

        return jsonify({
            "status": "success",
            "calendar_token": new_token,
            "message": "Přístupový token kalendáře byl úspěšně přegenerován."
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Detekce chodu v Dockeru
IS_DOCKER = is_docker()

@app.route("/api/version/check", methods=["GET"])
def check_version():
    """Vrací stav verze aplikace, lokální i remote hash s podporou in-memory cache."""
    force = request.args.get("force", "").lower() in ("1", "true", "yes")
    status_data = get_version_status(force=force)
    return jsonify(status_data)

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

@app.route("/api/version/truenas-upgrade", methods=["POST"])
def truenas_upgrade():
    """
    Vyvolá okamžitou aktualizaci na TrueNAS SCALE přes REST API nebo Watchtower webhook.
    """
    try:
        _, user_config = load_data()
        
        # 1. Zkontrolujeme přítomnost Watchtower webhooku
        watchtower_url = os.environ.get("WATCHTOWER_WEBHOOK_URL") or user_config.get("watchtower_url", "")
        watchtower_token = os.environ.get("WATCHTOWER_TOKEN") or user_config.get("watchtower_token", "")
        if watchtower_url:
            headers = {"Authorization": f"Bearer {watchtower_token}"} if watchtower_token else {}
            res = requests.post(watchtower_url, headers=headers, timeout=10)
            return jsonify({
                "status": "success",
                "message": f"Watchtower webhook úspěšně odeslán (HTTP {res.status_code}). Kontejner se nyní aktualizuje."
            })

        # 2. Nebo TrueNAS SCALE REST API
        truenas_url = os.environ.get("TRUENAS_URL") or user_config.get("truenas_url", "")
        truenas_api_key = os.environ.get("TRUENAS_API_KEY") or user_config.get("truenas_api_key", "")
        app_name = os.environ.get("TRUENAS_APP_NAME") or user_config.get("truenas_app_name", "listing-hub")

        if not truenas_url or not truenas_api_key:
            return jsonify({
                "status": "error",
                "message": "V nastavení ani v environment proměnných není nakonfigurován TRUENAS_URL a TRUENAS_API_KEY."
            }), 400

        truenas_url = truenas_url.rstrip("/")
        api_endpoint = f"{truenas_url}/api/v2.0/app/upgrade"
        headers = {
            "Authorization": f"Bearer {truenas_api_key}",
            "Content-Type": "application/json"
        }
        payload = {"app_name": app_name}

        res = requests.post(api_endpoint, headers=headers, json=payload, timeout=15, verify=False)
        if res.status_code in (200, 201, 202):
            return jsonify({
                "status": "success",
                "message": "Povel k aktualizaci byl úspěšně předán TrueNAS SCALE. Aplikace se během chvíle restartuje s nejnovější verzí."
            })
        else:
            return jsonify({
                "status": "error",
                "message": f"TrueNAS API vrátilo chybu (Status {res.status_code}): {res.text}"
            }), res.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba při volání TrueNAS: {str(e)}"}), 500

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
            
        if not merged_user.get("gemini_model"):
            merged_user["gemini_model"] = "gemini-2.5-flash"
            
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
    """Endpoint pro kompletní smazání inzerátu z databáze a volitelně i lokálních fotek."""
    try:
        data = request.json or {}
        listing_id = data.get("id")
        delete_photos = data.get("delete_photos", False)
        if not listing_id:
            return jsonify({"status": "error", "message": "Chybí ID inzerátu"}), 400
        
        # Načteme inzerát z DB pro zjištění složky s fotkami
        listing = db.get_listing_by_id(listing_id)
        if not listing:
            # Zkusíme najít podle local_photos_dir
            for item in db.get_all_listings():
                if item.get("local_photos_dir") == listing_id:
                    listing = item
                    listing_id = item.get("id")
                    break

        if delete_photos and listing and listing.get("local_photos_dir"):
            safe_delete_photos_dir(listing["local_photos_dir"])

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
        target_domain = payload.get("target_domain")
        
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
                
        if selected_ad and target_domain:
            selected_ad["target_domain"] = target_domain

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
    status_info = action_state_mgr.get_status()
    running = False
    error = status_info.get("error")
    
    if playwright_process and playwright_process.is_alive():
        running = True
    elif status_info.get("state") == ActionStateManager.RUNNING:
        # Vlákno možná skončilo neočekávaně
        running = False
    
    if not error and os.path.exists("/tmp/playwright_error.txt"):
        try:
            with open("/tmp/playwright_error.txt", "r", encoding="utf-8") as f:
                error = f.read().strip()
        except Exception:
            pass
                    
    return jsonify({
        "running": running,
        "state": status_info.get("state"),
        "action_type": status_info.get("action_type"),
        "listing_id": status_info.get("listing_id"),
        "error": error
    })

@app.route("/api/action/confirm", methods=["POST"])
def confirm_action():
    """Potvrzení odeslání inzerátu uživatelem z webu: ověří úspěch na Bazoši a uloží URL do DB."""
    try:
        def _check_page_submitted(page, *args):
            if not page or page.is_closed():
                return {"submitted": False, "error": "Prohlížeč není otevřen."}
            
            cur_url = page.url or ""
            # Bazoš po odeslání zůstává na /pridat-inzerat.php s potvrzovacím textem nebo přesměruje na /inzerat/<id>/
            # Hledáme odkaz na nově vytvořený inzerát
            ad_link_loc = page.locator("a[href*='/inzerat/']")
            new_ad_url = ""
            if ad_link_loc.count() > 0:
                try:
                    first_link = ad_link_loc.first
                    href = first_link.get_attribute("href") or ""
                    if href:
                        if href.startswith("http"):
                            new_ad_url = href
                        else:
                            # relativní URL např. /inzerat/12345/nadpis.php
                            from urllib.parse import urlparse
                            parsed = urlparse(cur_url)
                            new_ad_url = f"{parsed.scheme}://{parsed.netloc}{href}"
                except Exception:
                    pass

            if "/inzerat/" in cur_url:
                new_ad_url = cur_url

            still_on_form = ("pridat-inzerat.php" in cur_url and 
                             page.locator("input[name='nadpis']").count() > 0 and 
                             page.locator("input[name='nadpis']").first.is_visible())

            return {
                "submitted": bool(new_ad_url) or not still_on_form,
                "new_url": new_ad_url,
                "current_url": cur_url,
                "still_on_form": still_on_form
            }

        inspect_res = session_manager.run_on_worker(_check_page_submitted, timeout=10.0)
        
        if inspect_res.get("still_on_form"):
            return jsonify({
                "status": "error", 
                "message": "Inzerát ještě nebyl odeslán na Bazoši. Zkontrolujte formulář a klikněte v prohlížeči na 'Odeslat'."
            }), 422

        new_url = inspect_res.get("new_url")
        status_info = action_state_mgr.get_status()
        listing_id = status_info.get("listing_id")
        
        if listing_id:
            listing = db.get_listing_by_id(listing_id)
            if listing:
                listing_data = dict(listing)
                portal_states = {
                    "bazos": {
                        "portal_item_id": re.search(r'/inzerat/(\d+)/', new_url).group(1) if new_url and re.search(r'/inzerat/(\d+)/', new_url) else None,
                        "url": new_url or listing.get("url", ""),
                        "status": "Aktivní",
                        "views": 0,
                        "last_synced": datetime.now().isoformat()
                    }
                }
                listing_data["created_at"] = datetime.today().strftime('%Y-%m-%d')
                db.save_listing(listing_data, portal_states)

        action_state_mgr.set_completed()
        return jsonify({
            "status": "success", 
            "message": "Inzerát byl úspěšně potvrzen a uložen do databáze jako aktivní!",
            "url": new_url
        })
    except Exception as e:
        log_debug(f"CONFIRM ERR: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/action/cancel", methods=["POST"])
def cancel_action():
    global playwright_process
    try:
        log_debug("CANCEL: Cancelling active worker thread and closing browser session")
        with open("/tmp/playwright_error.txt", "w", encoding="utf-8") as f:
            f.write("Operace byla přerušena uživatelem.")
        
        try:
            session_manager.cancel_current_action()
        except Exception as sm_e:
            log_debug(f"CANCEL: session_manager.cancel_current_action error: {sm_e}")

        action_state_mgr.set_cancelled()
        playwright_process = None
        return jsonify({"status": "success", "message": "Operace byla přerušena."})
    except Exception as e:
        log_debug(f"CANCEL ERR: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/ai/test", methods=["POST"])
def api_test_gemini():
    try:
        import time
        payload = request.get_json(silent=True) or {}
        _, user_config = load_data()
        
        api_key = payload.get("api_key", "").strip() or user_config.get("gemini_api_key", "").strip()
        model = payload.get("model", "").strip() or user_config.get("gemini_model", "").strip() or "gemini-2.5-flash"
        
        if not api_key:
            return jsonify({
                "status": "error",
                "message": "Chybí Gemini API klíč. Zadejte jej do pole a klikněte na Otestovat spojení."
            }), 400

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        test_payload = {
            "contents": [{
                "parts": [{"text": "Odpověz jedním slovem: OK"}]
            }],
            "generationConfig": {
                "maxOutputTokens": 10,
                "temperature": 0.0
            }
        }
        
        start_time = time.time()
        response = requests.post(url, headers=headers, json=test_payload, timeout=10)
        latency_ms = int((time.time() - start_time) * 1000)
        
        if response.status_code == 200:
            return jsonify({
                "status": "success",
                "model": model,
                "latency_ms": latency_ms,
                "message": f"Spojení s modelem {model} je funkční ({latency_ms} ms)."
            })
        else:
            err_msg = f"Chyba Google AI (Status {response.status_code})"
            try:
                err_data = response.json()
                if "error" in err_data and "message" in err_data["error"]:
                    err_msg += f": {err_data['error']['message']}"
            except Exception:
                err_msg += f": {response.text[:200]}"
            return jsonify({"status": "error", "message": err_msg, "model": model}), 400
    except requests.Timeout:
        return jsonify({"status": "error", "message": "Časový limit vypršel (Google AI neodpovědělo do 10 sekund)."}), 504
    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba testu: {str(e)}"}), 500

@app.route("/api/ai/improve", methods=["POST"])
def ai_improve():
    try:
        payload = request.json
        text = payload.get("text", "")
        field_type = payload.get("field", "description") # 'title' nebo 'description'
        instruction_type = payload.get("instruction", "improve") # 'improve', 'fix', 'shorten', 'lengthen', 'title_suggestions'
        
        _, user_config = load_data()
        api_key = user_config.get("gemini_api_key", "")
        model = user_config.get("gemini_model") or "gemini-2.5-flash"
        seller_context = user_config.get("ai_seller_context", "")
        
        if not api_key:
            return jsonify({"status": "error", "message": "Chybí Gemini API klíč v nastavení."}), 400
            
        success, result_text = improve_text_with_gemini(
            text, field_type, instruction_type, api_key, model=model, seller_context=seller_context
        )
        if not success:
            status_code = 500
            match = re.search(r"Status (\d+)", result_text)
            if match:
                status_code = int(match.group(1))
            return jsonify({"status": "error", "message": result_text}), status_code
            
        return jsonify({"status": "success", "result": result_text})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/ai/analyze-photos", methods=["POST"])
def api_analyze_photos():
    try:
        _, user_config = load_data()
        api_key = user_config.get("gemini_api_key", "")
        model = user_config.get("gemini_model") or "gemini-2.5-flash"
        if not api_key:
            return jsonify({"status": "error", "message": "Chybí Gemini API klíč v nastavení."}), 400

        image_bytes_list = []
        user_notes = ""

        if request.files:
            files = request.files.getlist("photos") or request.files.getlist("files")
            for f in files:
                if f and f.filename:
                    image_bytes_list.append(f.read())
            user_notes = request.form.get("notes", "").strip()
        elif request.is_json:
            payload = request.json or {}
            user_notes = payload.get("notes", "").strip()
            raw_dir = payload.get("photos_dir", "").strip()
            if raw_dir:
                photos_dir = resolve_photos_dir(raw_dir)
                if os.path.isdir(photos_dir):
                    raw_files = sorted([
                        f for f in os.listdir(photos_dir)
                        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
                    ], key=lambda x: (not x.startswith("foto_"), x))
                    for fname in raw_files[:10]:
                        try:
                            with open(os.path.join(photos_dir, fname), "rb") as img_f:
                                image_bytes_list.append(img_f.read())
                        except Exception:
                            pass

        if not image_bytes_list:
            return jsonify({"status": "error", "message": "Nebyly přiloženy žádné fotografie k analýze."}), 400

        delivery_options = user_config.get("ai_delivery_options", "")
        seller_context = user_config.get("ai_seller_context", "")

        success, result_data, error_msg = analyze_photos_with_vision(
            image_bytes_list=image_bytes_list,
            user_notes=user_notes,
            api_key=api_key,
            run_market_advisor=True,
            model=model,
            delivery_options=delivery_options,
            seller_context=seller_context
        )

        if not success:
            return jsonify({"status": "error", "message": error_msg}), 500

        return jsonify({"status": "success", "data": result_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/ai/analyze-existing/<listing_id>", methods=["POST"])
def api_analyze_existing_listing(listing_id):
    try:
        _, user_config = load_data()
        api_key = user_config.get("gemini_api_key", "")
        model = user_config.get("gemini_model") or "gemini-2.5-flash"
        if not api_key:
            return jsonify({"status": "error", "message": "Chybí Gemini API klíč v nastavení."}), 400

        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT local_photos_dir, title, notes FROM listings WHERE id = ?", (listing_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({"status": "error", "message": "Inzerát nebyl nalezen."}), 404

        raw_dir = row["local_photos_dir"] or ""
        photos_dir = resolve_photos_dir(raw_dir)
        if not os.path.isdir(photos_dir):
            return jsonify({"status": "error", "message": "Složka s fotkami inzerátu neexistuje."}), 400

        raw_files = sorted([
            f for f in os.listdir(photos_dir)
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
        ], key=lambda x: (not x.startswith("foto_"), x))

        image_bytes_list = []
        for fname in raw_files[:10]:
            try:
                with open(os.path.join(photos_dir, fname), "rb") as img_f:
                    image_bytes_list.append(img_f.read())
            except Exception:
                pass

        if not image_bytes_list:
            return jsonify({"status": "error", "message": "Ve složce inzerátu nejsou žádné fotky."}), 400

        payload = request.get_json(silent=True) or {}
        user_notes = payload.get("notes") or row["notes"] or ""
        delivery_options = user_config.get("ai_delivery_options", "")
        seller_context = user_config.get("ai_seller_context", "")

        success, result_data, error_msg = analyze_photos_with_vision(
            image_bytes_list=image_bytes_list,
            user_notes=user_notes,
            api_key=api_key,
            run_market_advisor=True,
            model=model,
            delivery_options=delivery_options,
            seller_context=seller_context
        )

        if not success:
            return jsonify({"status": "error", "message": error_msg}), 500

        return jsonify({"status": "success", "data": result_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/listings/create-with-photos", methods=["POST"])
def api_create_listing_with_photos():
    """
    Atomické vytvoření nového inzerátu včetně přímého uložení nahraných fotek
    a volby titulní fotografie.
    """
    try:
        title = request.form.get("title", "").strip() or "Nový inzerát"
        title_trimmed = title[:50].strip()
        description = request.form.get("description", "").strip()
        price = int(request.form.get("price", 0) or 0)
        category = request.form.get("category", "").strip()
        notes = request.form.get("notes", "").strip()
        target_bazos = int(request.form.get("target_bazos", 1))
        target_aukro = int(request.form.get("target_aukro", 0))
        cover_idx = int(request.form.get("cover_photo_index", 0) or 0)

        title_slug = "".join([c if c.isalnum() else "_" for c in title_trimmed.lower()])
        unique_suffix = uuid.uuid4().hex[:6]
        photos_dir = f"photos/{title_slug}_{unique_suffix}"
        abs_photos_dir = Path(resolve_photos_dir(photos_dir))
        os.makedirs(abs_photos_dir, exist_ok=True)

        uploaded_files = request.files.getlist("photos") or request.files.getlist("files")
        saved_files = []
        if uploaded_files:
            temp_files = []
            for idx, file in enumerate(uploaded_files):
                if file and file.filename:
                    orig_name = file.filename
                    ext = orig_name.rsplit(".", 1)[-1].lower() if "." in orig_name else "jpg"
                    if ext not in ("jpg", "jpeg", "png", "webp"):
                        ext = "jpg"
                    temp_name = f"_temp_{idx}.{ext}"
                    temp_path = abs_photos_dir / temp_name
                    file.save(str(temp_path))
                    temp_files.append((temp_path, ext))

            if 0 < cover_idx < len(temp_files):
                cover_item = temp_files.pop(cover_idx)
                temp_files.insert(0, cover_item)

            for idx, (t_path, ext) in enumerate(temp_files, start=1):
                final_name = f"foto_{idx}.{ext}"
                final_path = abs_photos_dir / final_name
                if t_path.exists():
                    os.rename(str(t_path), str(final_path))
                    saved_files.append(final_name)

        listing_id = str(uuid.uuid4())
        new_ad = {
            "id": listing_id,
            "title": title_trimmed,
            "description": description,
            "price": price,
            "category": category,
            "local_photos_dir": photos_dir,
            "url": "",
            "views": 0,
            "status": "Aktivní",
            "date_created": "",
            "notes": notes,
            "target_bazos": target_bazos,
            "target_aukro": target_aukro
        }

        db.save_listing(new_ad, {
            "bazos": {
                "portal_item_id": None,
                "url": "",
                "status": "Aktivní",
                "views": 0,
                "last_synced": None
            }
        })

        return jsonify({
            "status": "success",
            "message": "Inzerát byl úspěšně vytvořen včetně fotografií.",
            "ad": new_ad,
            "saved_photos_count": len(saved_files)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/advisor/price/<listing_id>", methods=["GET"])
def api_get_price_recommendation(listing_id):
    try:
        from listing_hub.ai.advisor import get_price_recommendation
        _, user_config = load_data()
        api_key = user_config.get("gemini_api_key", "")
        gemini_model = user_config.get("gemini_model") or "gemini-2.5-flash"
        res = get_price_recommendation(listing_id, api_key=api_key, gemini_model=gemini_model)
        if "error" in res:
            return jsonify({"status": "error", "message": res["error"]}), 400
        return jsonify({"status": "success", "data": res})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/advisor/market-search", methods=["POST"])
def api_advisor_market_search():
    try:
        payload = request.get_json(silent=True) or {}
        query = payload.get("query", "").strip()
        brand = payload.get("brand", "").strip()
        model = payload.get("model", "").strip()
        condition = payload.get("condition", "used")
        fallback_price = int(payload.get("fallback_price") or 0)
        
        if not query and not (brand or model):
            return jsonify({"status": "error", "message": "Zadejte dotaz pro vyhledání."}), 400

        from listing_hub.ai.advisor import analyze_market_prices
        _, user_config = load_data()
        api_key = user_config.get("gemini_api_key", "")
        gemini_model = user_config.get("gemini_model") or "gemini-2.5-flash"

        res = analyze_market_prices(
            item_name=query,
            brand=brand,
            model=model,
            condition=condition,
            api_key=api_key,
            gemini_model=gemini_model,
            fallback_price=fallback_price
        )
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

        listings_data, user_config = load_data()
        target_domain = payload.get("target_domain")

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
            "ad_password_b64": listing_data["ad_password_b64"],
            "target_domain": target_domain
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



