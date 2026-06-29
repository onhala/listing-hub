import os
import sys
import json
import base64
import requests
from flask import Flask, render_template, jsonify, request
from pathlib import Path

# Přidáme aktuální adresář do sys.path, abychom mohli importovat post_to_bazos
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from post_to_bazos import load_data, save_listings, run_playwright_action, cli_update_listings_from_bazos, CONFIG_PATH, LISTINGS_PATH

app = Flask(__name__)

# Konfigurace portu
PORT = 5001

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/listings", methods=["GET"])
def get_listings():
    listings_data, _ = load_data()
    return jsonify(listings_data)

@app.route("/api/config", methods=["GET"])
def get_config():
    _, user_config = load_data()
    return jsonify(user_config)

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
        
        full_config["user"] = new_user_config
        
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(full_config, f, ensure_ascii=False, indent=2)
            
        return jsonify({"status": "success", "message": "Konfigurace uložena."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/listings/save", methods=["POST"])
def save_listing_endpoint():
    try:
        updated_ad = request.json
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
        # Vygenerujeme unikátní složku pro fotky na základě názvu
        title_slug = "".join([c if c.isalnum() else "_" for c in new_ad_data.get("title", "novy_inzerat").lower()])
        photos_dir = f"photos/{title_slug}"
        os.makedirs(photos_dir, exist_ok=True)
        
        # Nastavíme výchozí hodnoty
        new_ad = {
            "title": new_ad_data.get("title", ""),
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
    try:
        payload = request.json or {}
        ad_id = payload.get("local_photos_dir") # používáme složku jako unikátní klíč inzerátu
        
        listings_data, user_config = load_data()
        
        # Najdeme inzerát podle local_photos_dir
        selected_ad = None
        for ad in listings_data.get("active_listings", []):
            if ad.get("local_photos_dir") == ad_id:
                selected_ad = ad
                break
                
        if not selected_ad:
            for ad in listings_data.get("sold_listings", []):
                if ad.get("local_photos_dir") == ad_id:
                    selected_ad = ad
                    break
                    
        if not selected_ad and action_type != "sync_views":
            return jsonify({"status": "error", "message": "Inzerát nebyl nalezen."}), 404
            
        if action_type == "sync_views":
            # Synchronizace všech inzerátů z Bazoše
            cli_update_listings_from_bazos(listings_data, is_web=True)
            save_listings(listings_data)
            return jsonify({"status": "success", "message": "Zhlédnutí inzerátů byla synchronizována s Bazošem."})
            
        # Pro ostatní akce (post, edit_price, delete)
        extra_val = payload.get("extra_val") # např. nová cena
        
        # Spustíme neblokující Playwright akci
        success = run_playwright_action(selected_ad, user_config, action=action_type, extra_val=extra_val, is_web=True)
        
        if success:
            # Uložíme případné změny (např. pokud se změnila URL u 'post')
            save_listings(listings_data)
            return jsonify({"status": "success", "message": f"Akce '{action_type}' úspěšně spuštěna a zpracována."})
        else:
            return jsonify({"status": "error", "message": f"Akce '{action_type}' selhala nebo byla přerušena."}), 500
            
    except Exception as e:
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
            "Jsi expert na online prodej, psychologii zákazníka a inzerci na českém Bazoši.\n"
            "Tvým úkolem je pomoci uživateli upravit a vylepšit text inzerátu tak, aby působil profesionálně, "
            "důvěryhodně, srozumitelně a maximalizoval šanci na rychlý prodej za dobrou cenu.\n"
            "Dodržuj tyto zásady:\n"
            "- Piš v češtině, jasně a čitelně.\n"
            "- Používej odrážky pro parametry, stav a výhody.\n"
            "- Nepoužívej přehnané marketingové fráze a 'slop' slova (např. 'neuvěřitelná nabídka', 'jedinečná šance', 'TOP stav!!!').\n"
            "- Působ jako solidní, inženýrsky přesný a férový prodejce (podle standardů rodinné firmy TERMS).\n"
            "- Text formátuj přehledně, aby se na Bazoši dobře četl (Bazoš nepodporuje HTML, takže používej odstavce a klasické textové odrážky - např. '*' nebo '-').\n"
        )
        
        user_prompt = ""
        if field_type == "title":
            if instruction_type == "title_suggestions":
                user_prompt = f"Navrhni 5 různých atraktivních a chytlavých nadpisů pro inzerát na základě tohoto původního nadpisu: '{text}'. Nadpisy musí mít maximálně 50 znaků (limit Bazoše). Vrať pouze seznam nadpisů, každý na novém řádku, bez dalšího okecávání."
            else:
                user_prompt = f"Vylepši tento nadpis inzerátu na Bazoš (limit 50 znaků): '{text}'. Odpověz pouze jedním výsledným nadpisem bez uvozovek a vysvětlování."
        else:
            if instruction_type == "improve":
                user_prompt = f"Vylepši a zatraktivni tento popis inzerátu pro Bazoš. Zdůrazni klíčové vlastnosti, stav věci a přidej přehledné formátování pomocí odrážek:\n\n{text}"
            elif instruction_type == "fix":
                user_prompt = f"Oprav gramatické chyby, překlepy a vylepši stylistiku tohoto popisu inzerátu, ale zachovej jeho původní délku a smysl:\n\n{text}"
            elif instruction_type == "shorten":
                user_prompt = f"Zkrať tento popis inzerátu na podstatné informace, parametry a stav, aby byl stručný a úderný:\n\n{text}"
            elif instruction_type == "lengthen":
                user_prompt = f"Rozšiř tento popis inzerátu. Přidej více detailů, vysvěli možné scénáře použití a doplň přátelskou výzvu k akci (např. možnost osobního odběru nebo zaslání):\n\n{text}"
        
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
            return jsonify({"status": "success", "result": improved_text})
        except (KeyError, IndexError) as parse_err:
            return jsonify({"status": "error", "message": f"Selhalo parsování odpovědi Gemini API: {str(parse_err)}"}), 500
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--dry-run":
        print("Flask syntax OK.")
        sys.exit(0)
    app.run(host="127.0.0.1", port=PORT, debug=True)
