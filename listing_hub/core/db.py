import sqlite3
import os
from pathlib import Path
from datetime import datetime

from listing_hub.core.config import DATA_DIR
DB_PATH = DATA_DIR / "listings.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
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

    # Tabulka historie publikací (1:N k listings)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS listing_publications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id TEXT NOT NULL,
            portal_name TEXT NOT NULL,
            portal_item_id TEXT,
            url TEXT,
            price INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            views INTEGER DEFAULT 0,
            published_at TEXT NOT NULL,
            closed_at TEXT,
            close_reason TEXT,
            FOREIGN KEY (listing_id) REFERENCES listings (id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_listing_pubs_listing ON listing_publications(listing_id, portal_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_listing_pubs_url ON listing_publications(url)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_listing_pubs_item_id ON listing_publications(portal_item_id)")

    # Backfill do listing_publications ze stávajících portal_states, pokud je tabulka prázdná
    cursor.execute("SELECT COUNT(*) FROM listing_publications")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            SELECT ps.listing_id, ps.portal_name, ps.portal_item_id, ps.url, ps.views, l.price, l.created_at
            FROM portal_states ps
            JOIN listings l ON ps.listing_id = l.id
            WHERE ps.url IS NOT NULL AND ps.url != ''
        """)
        active_existing = cursor.fetchall()
        for row in active_existing:
            pub_date = row["created_at"] or datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
                INSERT INTO listing_publications (
                    listing_id, portal_name, portal_item_id, url, price, status, views, published_at
                ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
            """, (
                row["listing_id"],
                row["portal_name"],
                row["portal_item_id"],
                row["url"],
                row["price"] or 0,
                row["views"] or 0,
                pub_date
            ))
    
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

        # Načtení publikací (historie)
        cursor.execute("SELECT * FROM listing_publications WHERE listing_id = ? ORDER BY id ASC", (listing["id"],))
        pubs = [dict(p) for p in cursor.fetchall()]
        listing["publications"] = pubs
        listing["publication_count"] = len(pubs) if pubs else 1
        listing["cumulative_views"] = sum(p.get("views", 0) for p in pubs)
        listing["is_reposted"] = len(pubs) > 1

        result.append(listing)
        
    conn.close()
    return result

def get_listing_by_id(listing_id: str):
    """Vrátí jeden inzerát podle ID včetně stavů portálů nebo None."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM listings WHERE id = ?", (listing_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    listing = dict(row)
    cursor.execute("SELECT * FROM portal_states WHERE listing_id = ?", (listing_id,))
    states_rows = cursor.fetchall()
    listing["portal_states"] = {state["portal_name"]: dict(state) for state in states_rows}

    # Načtení publikací (historie)
    cursor.execute("SELECT * FROM listing_publications WHERE listing_id = ? ORDER BY id ASC", (listing_id,))
    pubs = [dict(p) for p in cursor.fetchall()]
    listing["publications"] = pubs
    listing["publication_count"] = len(pubs) if pubs else 1
    listing["cumulative_views"] = sum(p.get("views", 0) for p in pubs)
    listing["is_reposted"] = len(pubs) > 1

    conn.close()
    return listing

def delete_listing(listing_id: str) -> bool:
    """Smaže inzerát a jeho navázané stavy i historii z databáze v atomické transakci."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        with conn:
            cursor.execute("DELETE FROM listing_publications WHERE listing_id = ?", (listing_id,))
            cursor.execute("DELETE FROM portal_states WHERE listing_id = ?", (listing_id,))
            cur = cursor.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
            return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def record_publication(listing_id: str, portal_name: str, portal_item_id: str, url: str, price: int, published_at: str = None, status: str = "active") -> int:
    """Vloží nový záznam o publikaci inzerátu."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        now_date = published_at or datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
            INSERT INTO listing_publications (
                listing_id, portal_name, portal_item_id, url, price, status, views, published_at
            ) VALUES (?, ?, ?, ?, ?, ?, 0, ?)
        """, (listing_id, portal_name, portal_item_id, url, price, status, now_date))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

def close_active_publication(listing_id: str, portal_name: str, closed_at: str = None, close_reason: str = "reposted", final_views: int = 0):
    """Označí aktivní publikaci pro daný inzerát a portál jako ukončenou (superseded/deleted)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        close_dt = closed_at or datetime.now().strftime("%Y-%m-%d")
        status_val = "superseded" if close_reason == "reposted" else "deleted"
        cursor.execute("""
            UPDATE listing_publications
            SET status = ?, closed_at = ?, close_reason = ?, views = CASE WHEN ? > 0 THEN ? ELSE views END
            WHERE listing_id = ? AND portal_name = ? AND status = 'active'
        """, (status_val, close_dt, close_reason, final_views, final_views, listing_id, portal_name))
        conn.commit()
    finally:
        conn.close()

def get_listing_publications(listing_id: str, portal_name: str = None) -> list:
    """Vrátí chronologickou historii publikací inzerátu (od nejstarší po nejnovější)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if portal_name:
            cursor.execute("""
                SELECT * FROM listing_publications
                WHERE listing_id = ? AND portal_name = ?
                ORDER BY id ASC
            """, (listing_id, portal_name))
        else:
            cursor.execute("""
                SELECT * FROM listing_publications
                WHERE listing_id = ?
                ORDER BY id ASC
            """, (listing_id,))
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()

def get_publication_by_url_or_item_id(portal_name: str, url: str = None, portal_item_id: str = None) -> dict | None:
    """Vyhledá publikaci podle URL nebo ID inzerátu na portálu (slouží pro Zombie Defense)."""
    if not url and not portal_item_id:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if url and portal_item_id:
            cursor.execute("""
                SELECT * FROM listing_publications
                WHERE portal_name = ? AND (url = ? OR portal_item_id = ?)
                LIMIT 1
            """, (portal_name, url.strip(), portal_item_id.strip()))
        elif url:
            cursor.execute("""
                SELECT * FROM listing_publications
                WHERE portal_name = ? AND url = ?
                LIMIT 1
            """, (portal_name, url.strip()))
        else:
            cursor.execute("""
                SELECT * FROM listing_publications
                WHERE portal_name = ? AND portal_item_id = ?
                LIMIT 1
            """, (portal_name, portal_item_id.strip()))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_listing_cumulative_stats(listing_id: str) -> dict:
    """Vrátí kumulativní statistiky inzerátu přes všechny jeho publikace."""
    pubs = get_listing_publications(listing_id)
    total_views = sum(p.get("views", 0) for p in pubs)
    pub_count = len(pubs)
    active_pub = next((p for p in pubs if p.get("status") == "active"), None)
    return {
        "publication_count": pub_count if pub_count > 0 else 1,
        "total_views": total_views,
        "first_published_at": pubs[0]["published_at"] if pubs else None,
        "is_reposted": pub_count > 1,
        "active_publication": active_pub
    }
