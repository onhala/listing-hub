import json
import sqlite3
import uuid
import os
from pathlib import Path
from listing_hub.core.db import init_db, save_listing, DB_PATH

JSON_PATH = Path("/Users/ondre/Projects/listing-hub/bazos_active_listings.json")

def migrate():
    print("Inicializuji databázi...")
    init_db()
    
    if not JSON_PATH.exists():
        print(f"JSON databáze nenalezena na {JSON_PATH}. Není co migrovat.")
        return
        
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # Původní JSON struktura mohla obsahovat různé listy:
    # "active_listings", "sold_listings", "unsold_listings" atd.
    categories_to_migrate = ["active_listings", "sold_listings", "unsold_listings"]
    
    count = 0
    for cat in categories_to_migrate:
        listings = data.get(cat, [])
        print(f"Migruji kategorii {cat} ({len(listings)} inzerátů)...")
        
        for item in listings:
            # Původní JSON neměl UUID inzerátu, vygenerujeme ho na základě cesty k fotkám nebo náhodně
            listing_id = item.get("id")
            if not listing_id:
                listing_id = str(uuid.uuid4())
                
            # Připravíme data pro listings tabulku
            listing_data = {
                "id": listing_id,
                "title": item.get("title", "Bez názvu"),
                "description": item.get("description", ""),
                "price": item.get("price", 0),
                "category": item.get("category", ""),
                "condition": item.get("condition", ""),
                "local_photos_dir": item.get("local_photos_dir", ""),
                "location": item.get("location", ""),
                "notes": item.get("notes", ""),
                "ad_password_b64": item.get("ad_password_b64", ""),
                "bookmarklet_uri": item.get("bookmarklet_uri", ""),
                "days_old": item.get("days_old", 0),
                "created_at": item.get("date_created"),
                "target_bazos": 1,
                "target_aukro": 0
            }
            
            # Pokud inzerát má Bazoš URL nebo ID, uložíme ho do portal_states
            portal_states = {}
            if item.get("url") or item.get("status"):
                # Pokusíme se extrahovat ID inzerátu z URL
                url = item.get("url", "")
                portal_item_id = None
                if "/inzerat/" in url:
                    try:
                        # Příklad: https://dum.bazos.cz/inzerat/221258802/vykonny... -> 221258802
                        portal_item_id = url.split("/inzerat/")[1].split("/")[0]
                    except Exception:
                        pass
                
                # Zmapujeme status
                status = item.get("status", "Aktivní")
                if cat == "sold_listings":
                    status = "Prodané"
                
                portal_states["bazos"] = {
                    "portal_item_id": portal_item_id,
                    "url": url,
                    "status": status,
                    "views": item.get("views", 0),
                    "last_synced": None
                }
                
            save_listing(listing_data, portal_states)
            count += 1
            
    print(f"✅ Migrace úspěšně dokončena. Celkem přeneseno {count} inzerátů do {DB_PATH}.")

if __name__ == "__main__":
    migrate()
