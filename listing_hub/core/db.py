import sqlite3
import os
from pathlib import Path
from datetime import datetime

from listing_hub.core.config import DATA_DIR
DB_PATH = DATA_DIR / "listings.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Inicializuje SQLite tabulky pro inzeráty a stavy portálů."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabulka inzerátů
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            price INTEGER DEFAULT 0,
            category TEXT,
            condition TEXT,
            local_photos_dir TEXT,
            location TEXT,
            notes TEXT,
            ad_password_b64 TEXT,
            bookmarklet_uri TEXT,
            days_old INTEGER DEFAULT 0,
            created_at TEXT,
            target_bazos INTEGER DEFAULT 1,
            target_aukro INTEGER DEFAULT 0
        )
    """)
    
    # Tabulka stavů na jednotlivých portálech
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portal_states (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id TEXT NOT NULL,
            portal_name TEXT NOT NULL,
            portal_item_id TEXT,
            url TEXT,
            status TEXT,
            views INTEGER DEFAULT 0,
            last_synced TEXT,
            FOREIGN KEY (listing_id) REFERENCES listings (id) ON DELETE CASCADE,
            UNIQUE(listing_id, portal_name)
        )
    """)
    
    conn.commit()
    conn.close()

def save_listing(listing_data, portal_states=None):
    """Vloží nebo aktualizuje inzerát v databázi (včetně stavů portálů)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO listings (
                id, title, description, price, category, condition, 
                local_photos_dir, location, notes, ad_password_b64, 
                bookmarklet_uri, days_old, created_at, target_bazos, target_aukro
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                description=excluded.description,
                price=excluded.price,
                category=excluded.category,
                condition=excluded.condition,
                local_photos_dir=excluded.local_photos_dir,
                location=excluded.location,
                notes=excluded.notes,
                ad_password_b64=excluded.ad_password_b64,
                bookmarklet_uri=excluded.bookmarklet_uri,
                days_old=excluded.days_old,
                created_at=excluded.created_at,
                target_bazos=excluded.target_bazos,
                target_aukro=excluded.target_aukro
        """, (
            listing_data.get("id"),
            listing_data.get("title"),
            listing_data.get("description"),
            listing_data.get("price", 0),
            listing_data.get("category"),
            listing_data.get("condition"),
            listing_data.get("local_photos_dir"),
            listing_data.get("location"),
            listing_data.get("notes"),
            listing_data.get("ad_password_b64"),
            listing_data.get("bookmarklet_uri"),
            listing_data.get("days_old", 0),
            listing_data.get("created_at") or datetime.now().strftime("%Y-%m-%d"),
            listing_data.get("target_bazos", 1),
            listing_data.get("target_aukro", 0)
        ))
        
        if portal_states:
            for portal_name, state in portal_states.items():
                cursor.execute("""
                    INSERT INTO portal_states (
                        listing_id, portal_name, portal_item_id, url, status, views, last_synced
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(listing_id, portal_name) DO UPDATE SET
                        portal_item_id=excluded.portal_item_id,
                        url=excluded.url,
                        status=excluded.status,
                        views=excluded.views,
                        last_synced=excluded.last_synced
                """, (
                    listing_data.get("id"),
                    portal_name,
                    state.get("portal_item_id"),
                    state.get("url"),
                    state.get("status"),
                    state.get("views", 0),
                    state.get("last_synced") or datetime.now().isoformat()
                ))
                
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_all_listings():
    """Vrátí všechny inzeráty včetně jejich stavů na portálech."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM listings")
    listings_rows = cursor.fetchall()
    
    result = []
    for row in listings_rows:
        listing = dict(row)
        
        # Načtení stavů pro tento inzerát
        cursor.execute("SELECT * FROM portal_states WHERE listing_id = ?", (listing["id"],))
        states_rows = cursor.fetchall()
        
        listing["portal_states"] = {state["portal_name"]: dict(state) for state in states_rows}
        result.append(listing)
        
    conn.close()
    return result

def delete_listing(listing_id):
    """Smaže inzerát a jeho kaskádované stavy z databáze."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
