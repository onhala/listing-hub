#!/usr/bin/env python3
import json
import urllib.parse
import re
from pathlib import Path

# Cesty k souborům
SCRIPT_DIR = Path(__file__).parent.parent.resolve()
LISTINGS_PATH = SCRIPT_DIR / "bazos_active_listings.json"

def sanitize_bookmarklet(uri):
    if not uri or not uri.startswith("javascript:"):
        return uri
        
    # URL-decode the bookmarklet code
    decoded = urllib.parse.unquote(uri)
    
    # Replacement map for PII inside decoded code
    replacements = {
        "speedratt@gmail.com": "tuj_email@example.com",
        "775650641": "777123456",
        "+420775650641": "+420777123456",
        "lak0mec": "heslo123",
        "Ondřej H.": "Tvoje Jméno",
        "Ondrej H.": "Tvoje Jméno",
        "Český Krumlov 381 01": "Praha 100 00",
        "Český Krumlov": "Praha"
    }
    
    for old_val, new_val in replacements.items():
        decoded = decoded.replace(old_val, new_val)
        
    # Also handle possible unicode escapes like \u0159 inside decoded code
    decoded = decoded.replace("Ond\\u0159ej H.", "Tvoje Jm\\u00e9no")
    
    # URL-re-encode the bookmarklet code
    # We must preserve the 'javascript:' prefix unescaped
    encoded_code = urllib.parse.quote(decoded[11:])
    
    return "javascript:" + encoded_code

def sanitize_listings():
    if not LISTINGS_PATH.exists():
        print(f"Soubor {LISTINGS_PATH} neexistuje.")
        return
        
    with open(LISTINGS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    replacements = {
        "speedratt@gmail.com": "tuj_email@example.com",
        "775650641": "777123456",
        "+420775650641": "+420777123456",
        "lak0mec": "heslo123",
        "bGFrMG1lYw==": "aGVzbG8xMjM=",  # base64 for lak0mec -> heslo123
        "Český Krumlov 381 01": "Praha 100 00",
        "Český Krumlov": "Praha",
        "Ondřej H.": "Tvoje Jméno",
        "Ondrej H.": "Tvoje Jméno"
    }
    
    def process_item(item):
        for key, val in item.items():
            if isinstance(val, str):
                # Replace absolute path pointing to /Users/ondre/ with /Users/user/
                val = val.replace("/Users/ondre/", "/Users/user/")
                
                # Perform basic replacements
                for old_val, new_val in replacements.items():
                    val = val.replace(old_val, new_val)
                    
                if key == "bookmarklet_uri":
                    val = sanitize_bookmarklet(val)
                    
                item[key] = val
            elif isinstance(val, int) or isinstance(val, float):
                # If there are any numbers that match the phone number, replace them
                if val == 775650641:
                    item[key] = 777123456
            elif isinstance(val, list):
                item[key] = [process_val(x) for x in val]
            elif isinstance(val, dict):
                item[key] = process_dict(val)
                
    def process_val(val):
        if isinstance(val, str):
            val = val.replace("/Users/ondre/", "/Users/user/")
            for old_val, new_val in replacements.items():
                val = val.replace(old_val, new_val)
            return val
        elif isinstance(val, dict):
            return process_dict(val)
        elif isinstance(val, list):
            return [process_val(x) for x in val]
        return val

    def process_dict(d):
        new_d = {}
        for k, v in d.items():
            new_d[k] = process_val(v)
        return new_d

    # Process active listings
    if "active_listings" in data:
        for item in data["active_listings"]:
            process_item(item)
            
    # Process sold listings
    if "sold_listings" in data:
        for item in data["sold_listings"]:
            process_item(item)
            
    with open(LISTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"✓ Soubor {LISTINGS_PATH.name} byl úspěšně vyčištěn od PII.")

if __name__ == "__main__":
    sanitize_listings()
