import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from contextlib import contextmanager
from collections.abc import Generator

from listing_hub.core.config import DATA_DIR
DB_PATH = DATA_DIR / "listings.db"

def get_db_connection() -> sqlite3.Connection:
    """Vytvoří a nakonfiguruje nové spojení s SQLite databází."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def db_session() -> Generator[sqlite3.Connection, None, None]:
    """Kontextový manažer pro bezpečné otevření a automatické uzavření SQLite spojení."""
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()

def init_db() -> None:
    """Inicializuje SQLite tabulky pro inzeráty a stavy portálů."""
    conn = get_db_connection()
    try:
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

        # Automatická migrace: prodejní atributy pro archivaci prodaných věcí
        for col, col_type in [("sale_price", "INTEGER"), ("sold_at", "TEXT"), ("sold_notes", "TEXT")]:
            try:
                cursor.execute(f"ALTER TABLE listings ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass

        # Automatická migrace: TOP status pro Bazoš
        for col, col_type in [("is_top", "INTEGER DEFAULT 0"), ("top_expires_at", "TEXT"), ("top_info", "TEXT")]:
            try:
                cursor.execute(f"ALTER TABLE portal_states ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass

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
    finally:
        conn.close()

def save_listing(listing_data: Dict[str, Any], portal_states: Optional[Dict[str, Any]] = None) -> None:
    """Vloží nebo aktualizuje inzerát v databázi (včetně stavů portálů a informací o prodeji)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO listings (
                id, title, description, price, category, condition, 
                local_photos_dir, location, notes, ad_password_b64, 
                bookmarklet_uri, days_old, created_at, target_bazos, target_aukro,
                sale_price, sold_at, sold_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                target_aukro=excluded.target_aukro,
                sale_price=COALESCE(excluded.sale_price, listings.sale_price),
                sold_at=COALESCE(excluded.sold_at, listings.sold_at),
                sold_notes=COALESCE(excluded.sold_notes, listings.sold_notes)
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
            listing_data.get("target_aukro", 0),
            listing_data.get("sale_price"),
            listing_data.get("sold_at"),
            listing_data.get("sold_notes")
        ))
        
        if portal_states:
            for portal_name, state in portal_states.items():
                cursor.execute("""
                    INSERT INTO portal_states (
                        listing_id, portal_name, portal_item_id, url, status, views, last_synced,
                        is_top, top_expires_at, top_info
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(listing_id, portal_name) DO UPDATE SET
                        portal_item_id=excluded.portal_item_id,
                        url=excluded.url,
                        status=excluded.status,
                        views=excluded.views,
                        last_synced=excluded.last_synced,
                        is_top=excluded.is_top,
                        top_expires_at=excluded.top_expires_at,
                        top_info=excluded.top_info
                """, (
                    listing_data.get("id"),
                    portal_name,
                    state.get("portal_item_id"),
                    state.get("url"),
                    state.get("status"),
                    state.get("views", 0),
                    state.get("last_synced") or datetime.now().isoformat(),
                    1 if state.get("is_top") else 0,
                    state.get("top_expires_at"),
                    state.get("top_info")
                ))
                
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_all_listings() -> List[Dict[str, Any]]:
    """Vrátí všechny inzeráty včetně jejich stavů na portálech."""
    conn = get_db_connection()
    try:
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

            # Propagace TOP statusu z Bazoš portal_state
            bazos_state = listing["portal_states"].get("bazos", {})
            listing["is_top"] = bool(bazos_state.get("is_top", 0))
            listing["top_expires_at"] = bazos_state.get("top_expires_at")
            listing["top_info"] = bazos_state.get("top_info")

            # Načtení publikací (historie)
            cursor.execute("SELECT * FROM listing_publications WHERE listing_id = ? ORDER BY id ASC", (listing["id"],))
            pubs = [dict(p) for p in cursor.fetchall()]
            listing["publications"] = pubs
            listing["publication_count"] = len(pubs) if pubs else 1
            listing["cumulative_views"] = sum(p.get("views", 0) for p in pubs)
            listing["is_reposted"] = len(pubs) > 1

            result.append(listing)
            
        return result
    finally:
        conn.close()

def get_listing_by_id(listing_id: str) -> Optional[Dict[str, Any]]:
    """Vrátí jeden inzerát podle ID včetně stavů portálů nebo None."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM listings WHERE id = ?", (listing_id,))
        row = cursor.fetchone()
        if not row:
            return None
        listing = dict(row)
        cursor.execute("SELECT * FROM portal_states WHERE listing_id = ?", (listing_id,))
        states_rows = cursor.fetchall()
        listing["portal_states"] = {state["portal_name"]: dict(state) for state in states_rows}

        # Propagace TOP statusu z Bazoš portal_state
        bazos_state = listing["portal_states"].get("bazos", {})
        listing["is_top"] = bool(bazos_state.get("is_top", 0))
        listing["top_expires_at"] = bazos_state.get("top_expires_at")
        listing["top_info"] = bazos_state.get("top_info")

        # Načtení publikací (historie)
        cursor.execute("SELECT * FROM listing_publications WHERE listing_id = ? ORDER BY id ASC", (listing_id,))
        pubs = [dict(p) for p in cursor.fetchall()]
        listing["publications"] = pubs
        listing["publication_count"] = len(pubs) if pubs else 1
        listing["cumulative_views"] = sum(p.get("views", 0) for p in pubs)
        listing["is_reposted"] = len(pubs) > 1

        return listing
    finally:
        conn.close()

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

def record_publication(
    listing_id: str,
    portal_name: str,
    portal_item_id: Optional[str],
    url: Optional[str],
    price: int,
    published_at: Optional[str] = None,
    status: str = "active"
) -> int:
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

def close_active_publication(
    listing_id: str,
    portal_name: str,
    closed_at: Optional[str] = None,
    close_reason: str = "reposted",
    final_views: int = 0
) -> None:
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

def get_listing_publications(listing_id: str, portal_name: Optional[str] = None) -> List[Dict[str, Any]]:
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

def get_publication_by_url_or_item_id(
    portal_name: str,
    url: Optional[str] = None,
    portal_item_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
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

def get_listing_cumulative_stats(listing_id: str) -> Dict[str, Any]:
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

def mark_listing_as_sold(
    listing_id: str,
    sale_price: Optional[Union[int, float, str]] = None,
    sold_at: Optional[str] = None,
    notes: Optional[str] = None
) -> bool:
    """Označí inzerát jako prodaný, nastaví prodejní cenu, datum a uzavře aktivní publikace."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Ověření existence inzerátu
        cursor.execute("SELECT price FROM listings WHERE id = ?", (listing_id,))
        row = cursor.fetchone()
        if not row:
            return False

        # Bezpečné přetypování ceny
        if sale_price is not None and sale_price != "":
            try:
                final_price = max(0, int(float(sale_price)))
            except (ValueError, TypeError):
                final_price = row["price"] or 0
        else:
            final_price = row["price"] or 0

        clean_sold_at = sold_at.strip() if isinstance(sold_at, str) and sold_at.strip() else datetime.now().strftime("%Y-%m-%d")
        clean_notes = notes.strip() if isinstance(notes, str) else (str(notes) if notes is not None else None)

        cursor.execute("""
            UPDATE listings
            SET sale_price = ?, sold_at = ?, sold_notes = ?
            WHERE id = ?
        """, (final_price, clean_sold_at, clean_notes, listing_id))

        cursor.execute("""
            UPDATE portal_states
            SET status = 'Prodané', last_synced = ?
            WHERE listing_id = ?
        """, (datetime.now().isoformat(), listing_id))

        if cursor.rowcount == 0:
            cursor.execute("""
                INSERT INTO portal_states (listing_id, portal_name, status, last_synced)
                VALUES (?, 'bazos', 'Prodané', ?)
            """, (listing_id, datetime.now().isoformat()))

        cursor.execute("""
            UPDATE listing_publications
            SET status = 'sold', closed_at = ?, close_reason = 'sold'
            WHERE listing_id = ? AND status = 'active'
        """, (clean_sold_at, listing_id))

        conn.commit()
        return True
    finally:
        conn.close()

def restore_sold_listing(listing_id: str) -> bool:
    """Vrátí prodaný inzerát zpět mezi neprodané (Věci k prodeji)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM listings WHERE id = ?", (listing_id,))
        if not cursor.fetchone():
            return False

        cursor.execute("""
            UPDATE listings
            SET sale_price = NULL, sold_at = NULL, sold_notes = NULL
            WHERE id = ?
        """, (listing_id,))

        cursor.execute("""
            UPDATE portal_states
            SET status = 'Expirováno', last_synced = ?
            WHERE listing_id = ?
        """, (datetime.now().isoformat(), listing_id))

        conn.commit()
        return True
    finally:
        conn.close()

def get_sold_statistics() -> Dict[str, Any]:
    """Spočítá souhrnné statistiky pro sekci Prodané věci s ochranou proti duplicitám při multi-portálech."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                COUNT(*) as total_sold,
                SUM(COALESCE(sale_price, price, 0)) as total_profit,
                AVG(COALESCE(sale_price, price, 0)) as avg_price
            FROM listings
            WHERE id IN (
                SELECT listing_id FROM portal_states 
                WHERE status IN ('Prodané', 'Sold', 'prodané')
            ) OR sold_at IS NOT NULL
        """)
        row = cursor.fetchone()
        if not row:
            return {
                "total_sold": 0,
                "total_profit": 0,
                "avg_price": 0
            }
        return {
            "total_sold": row["total_sold"] or 0,
            "total_profit": int(row["total_profit"] or 0),
            "avg_price": int(round(row["avg_price"] or 0))
        }
    finally:
        conn.close()

# Automatická inicializace a migrace schématu při načtení modulu
try:
    init_db()
except Exception:
    pass

