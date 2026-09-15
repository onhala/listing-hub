import os
import sqlite3
from pathlib import Path
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
        # Tabulka historie zhlédnutí pro sledování trendů (časové řady)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS listing_views_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id TEXT NOT NULL,
                portal_name TEXT NOT NULL,
                views INTEGER NOT NULL,
                recorded_at TEXT NOT NULL,
                FOREIGN KEY (listing_id) REFERENCES listings (id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_views_hist_time ON listing_views_history(listing_id, recorded_at)")

        # Automatická migrace: prodejní atributy pro archivaci prodaných věcí
        for col, col_type in [("sale_price", "INTEGER"), ("sold_at", "TEXT"), ("sold_notes", "TEXT"), ("sold_channel", "TEXT")]:
            try:
                cursor.execute(f"ALTER TABLE listings ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass

        # Automatická migrace: TOP status pro Bazoš a metadata portálů
        for col, col_type in [
            ("is_top", "INTEGER DEFAULT 0"), 
            ("top_expires_at", "TEXT"), 
            ("top_info", "TEXT"),
            ("portal_label", "TEXT"),
            ("published_at", "TEXT")
        ]:
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
                sale_price, sold_at, sold_notes, sold_channel
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                sold_notes=COALESCE(excluded.sold_notes, listings.sold_notes),
                sold_channel=COALESCE(excluded.sold_channel, listings.sold_channel)
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
            listing_data.get("sold_notes"),
            listing_data.get("sold_channel")
        ))
        
        if portal_states:
            for portal_name, state in portal_states.items():
                cursor.execute("""
                    INSERT INTO portal_states (
                        listing_id, portal_name, portal_item_id, url, status, views, last_synced,
                        is_top, top_expires_at, top_info, portal_label, published_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(listing_id, portal_name) DO UPDATE SET
                        portal_item_id=excluded.portal_item_id,
                        url=excluded.url,
                        status=excluded.status,
                        views=excluded.views,
                        last_synced=excluded.last_synced,
                        is_top=excluded.is_top,
                        top_expires_at=excluded.top_expires_at,
                        top_info=excluded.top_info,
                        portal_label=COALESCE(excluded.portal_label, portal_states.portal_label),
                        published_at=COALESCE(excluded.published_at, portal_states.published_at)
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
                    state.get("top_info"),
                    state.get("portal_label"),
                    state.get("published_at")
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
    notes: Optional[str] = None,
    sold_channel: Optional[str] = None
) -> bool:
    """Označí inzerát jako prodaný, nastaví prodejní cenu, datum a uzavře aktivní publikace."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Ověření existence inzerátu
        cursor.execute("SELECT price, sold_channel FROM listings WHERE id = ?", (listing_id,))
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
        clean_channel = sold_channel.strip() if isinstance(sold_channel, str) and sold_channel.strip() else None

        cursor.execute("""
            UPDATE listings
            SET sale_price = ?, sold_at = ?, sold_notes = ?, sold_channel = COALESCE(?, sold_channel)
            WHERE id = ?
        """, (final_price, clean_sold_at, clean_notes, clean_channel, listing_id))

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

def record_manual_publication(
    listing_id: str,
    portal_name: str,
    portal_label: Optional[str] = None,
    url: Optional[str] = None,
    notes: Optional[str] = None
) -> bool:
    """Zaznamená ruční publikaci inzerátu na externím portálu (FB, Sbazar, Vinted, Aukro, atd.)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, price, title FROM listings WHERE id = ?", (listing_id,))
        listing = cursor.fetchone()
        if not listing:
            return False

        now_iso = datetime.now().isoformat()
        today = datetime.now().strftime("%Y-%m-%d")
        clean_url = url.strip() if url and url.strip() else ""
        clean_portal_name = (portal_name or "custom").strip().lower()
        clean_label = portal_label.strip() if portal_label and portal_label.strip() else clean_portal_name.capitalize()

        cursor.execute("""
            INSERT INTO portal_states (
                listing_id, portal_name, url, status, views, last_synced, portal_label, published_at
            ) VALUES (?, ?, ?, 'Aktivní', 0, ?, ?, ?)
            ON CONFLICT(listing_id, portal_name) DO UPDATE SET
                url = CASE WHEN excluded.url != '' THEN excluded.url ELSE portal_states.url END,
                status = 'Aktivní',
                last_synced = excluded.last_synced,
                portal_label = excluded.portal_label,
                published_at = COALESCE(portal_states.published_at, excluded.published_at)
        """, (listing_id, clean_portal_name, clean_url, now_iso, clean_label, today))

        cursor.execute("""
            INSERT INTO listing_publications (
                listing_id, portal_name, url, price, status, views, published_at
            ) VALUES (?, ?, ?, ?, 'active', 0, ?)
        """, (listing_id, clean_portal_name, clean_url, listing["price"] or 0, today))

        if notes and notes.strip():
            cursor.execute("SELECT notes FROM listings WHERE id = ?", (listing_id,))
            curr_notes = cursor.fetchone()["notes"] or ""
            new_notes = (curr_notes + "\n" + notes.strip()).strip() if curr_notes else notes.strip()
            cursor.execute("UPDATE listings SET notes = ? WHERE id = ?", (new_notes, listing_id))

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def update_listing_portal_url(listing_id: str, portal_name: str, url: str) -> bool:
    """Aktualizuje externí URL pro konkrétní portál inzerátu."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        clean_url = url.strip() if url else ""
        clean_portal_name = (portal_name or "custom").strip().lower()
        cursor.execute("""
            UPDATE portal_states
            SET url = ?, last_synced = ?
            WHERE listing_id = ? AND portal_name = ?
        """, (clean_url, datetime.now().isoformat(), listing_id, clean_portal_name))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

def update_listing_portal_views(listing_id: str, portal_name: str, views: int) -> bool:
    """Aktualizuje počet zhlédnutí pro konkrétní portál inzerátu a zapíše snapshot do historie."""
    if views is None or views < 0 or not listing_id:
        return False
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        clean_portal_name = (portal_name or "custom").strip().lower()
        now_iso = datetime.now().isoformat()
        cursor.execute("""
            UPDATE portal_states
            SET views = ?, last_synced = ?
            WHERE listing_id = ? AND portal_name = ?
        """, (int(views), now_iso, listing_id, clean_portal_name))
        updated = cursor.rowcount > 0

        # Aktualizujeme také listing_publications pokud existuje
        cursor.execute("""
            UPDATE listing_publications
            SET views = ?
            WHERE listing_id = ? AND portal_name = ?
        """, (int(views), listing_id, clean_portal_name))

        conn.commit()
    finally:
        conn.close()

    if updated:
        record_views_snapshot(listing_id, clean_portal_name, int(views))
    return updated

def get_active_external_portal_urls() -> List[Dict[str, Any]]:
    """Vrátí všechny aktivní externí portály (mimo Bazoš), které mají vyplněnou platnou URL."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT ps.listing_id, ps.portal_name, ps.portal_label, ps.url, ps.views, l.title
            FROM portal_states ps
            JOIN listings l ON ps.listing_id = l.id
            WHERE ps.status = 'Aktivní'
              AND ps.portal_name != 'bazos'
              AND ps.url IS NOT NULL
              AND ps.url != ''
        """)
        return [dict(r) for r in cursor.fetchall()]
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

def get_sold_statistics(include_channels: bool = False) -> Dict[str, Any]:
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
        res = {
            "total_sold": (row["total_sold"] or 0) if row else 0,
            "total_profit": int(row["total_profit"] or 0) if row else 0,
            "avg_price": int(round(row["avg_price"] or 0)) if row else 0,
        }

        if include_channels:
            cursor.execute("""
                SELECT COALESCE(sold_channel, 'bazos') as channel, COUNT(*) as count, SUM(COALESCE(sale_price, price, 0)) as profit
                FROM listings
                WHERE id IN (
                    SELECT listing_id FROM portal_states 
                    WHERE status IN ('Prodané', 'Sold', 'prodané')
                ) OR sold_at IS NOT NULL
                GROUP BY COALESCE(sold_channel, 'bazos')
            """)
            channel_rows = cursor.fetchall()
            res["by_channel"] = {r["channel"]: {"count": r["count"], "profit": int(r["profit"] or 0)} for r in channel_rows}

        return res
    finally:
        conn.close()

def record_views_snapshot(listing_id: str, portal_name: str, views: int) -> None:
    """Zaznamená snapshot počtu zhlédnutí pro časové řady a sledování trendů."""
    if views is None or views < 0 or not listing_id or not portal_name:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        now_str = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO listing_views_history (listing_id, portal_name, views, recorded_at)
            VALUES (?, ?, ?, ?)
        """, (listing_id, portal_name, int(views), now_str))
        conn.commit()
    finally:
        conn.close()

def get_metrics_snapshot_data() -> Dict[str, Any]:
    """Získá kompletní sadu dat potřebnou pro sestavení Prometheus metrik."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 1. Aktivní inzeráty a jejich zhlédnutí podle portálu
        cursor.execute("""
            SELECT l.id, l.title, l.price, l.category, l.days_old, l.created_at, l.local_photos_dir,
                   ps.portal_name, ps.views, ps.is_top, ps.status as portal_status, ps.last_synced
            FROM listings l
            JOIN portal_states ps ON l.id = ps.listing_id
            WHERE ps.status = 'Aktivní'
        """)
        active_portal_rows = [dict(r) for r in cursor.fetchall()]

        # Spočítáme počet fotografií pro každý aktivní inzerát
        from listing_hub.core.config import PROJECT_ROOT
        for row in active_portal_rows:
            p_dir = row.get("local_photos_dir")
            photo_count = 0
            if p_dir:
                path = Path(p_dir)
                if not path.is_absolute():
                    path = PROJECT_ROOT / path
                if path.exists() and path.is_dir():
                    try:
                        photo_count = len([f for f in os.listdir(path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
                    except Exception:
                        photo_count = 0
            row["photo_count"] = photo_count

        # 2. Celkový počet inzerátů dle životního cyklu (active, sold, unsold)
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT l.id) as count,
                CASE 
                    WHEN l.sold_at IS NOT NULL OR EXISTS (
                        SELECT 1 FROM portal_states ps2 WHERE ps2.listing_id = l.id AND ps2.status IN ('Prodané', 'Sold', 'prodané')
                    ) THEN 'sold'
                    WHEN EXISTS (
                        SELECT 1 FROM portal_states ps3 WHERE ps3.listing_id = l.id AND ps3.status = 'Aktivní'
                    ) THEN 'active'
                    ELSE 'unsold'
                END as lifecycle_status
            FROM listings l
            GROUP BY lifecycle_status
        """)
        counts_by_status = {r["lifecycle_status"]: r["count"] for r in cursor.fetchall()}

        # 3. Sumární statistiky prodaných položek a analýza Time-to-Sell
        sold_stats = get_sold_statistics(include_channels=True)
        cursor.execute("""
            SELECT id, title, created_at, sold_at, sold_channel, price, sale_price
            FROM listings
            WHERE (id IN (
                SELECT listing_id FROM portal_states 
                WHERE status IN ('Prodané', 'Sold', 'prodané')
            ) OR sold_at IS NOT NULL)
        """)
        sold_rows = [dict(r) for r in cursor.fetchall()]
        days_to_sell_list = []
        for s in sold_rows:
            c_at = s.get("created_at")
            s_at = s.get("sold_at")
            if c_at and s_at:
                try:
                    dt_c = datetime.strptime(str(c_at)[:10], "%Y-%m-%d")
                    dt_s = datetime.strptime(str(s_at)[:10], "%Y-%m-%d")
                    diff_days = max(0, (dt_s - dt_c).days)
                    s["days_to_sell"] = diff_days
                    days_to_sell_list.append(diff_days)
                except Exception:
                    s["days_to_sell"] = None
            else:
                s["days_to_sell"] = None

        avg_days_to_sell = round(sum(days_to_sell_list) / len(days_to_sell_list), 1) if days_to_sell_list else 0

        # 4. Portálové agregace (počet inzerátů a celková zhlédnutí dle portálu)
        cursor.execute("""
            SELECT portal_name, COUNT(*) as active_count, SUM(COALESCE(views, 0)) as total_views, MAX(last_synced) as last_sync
            FROM portal_states
            WHERE status = 'Aktivní'
            GROUP BY portal_name
        """)
        portal_aggs = [dict(r) for r in cursor.fetchall()]

        # 5. Celková hodnota aktivních inzerátů (unikátní inzeráty s alespoň jedním aktivním portálem)
        cursor.execute("""
            SELECT SUM(COALESCE(price, 0)) as active_value
            FROM listings
            WHERE id IN (SELECT DISTINCT listing_id FROM portal_states WHERE status = 'Aktivní')
        """)
        row_val = cursor.fetchone()
        active_inventory_value = int(row_val["active_value"] or 0) if row_val else 0

        return {
            "active_portal_listings": active_portal_rows,
            "counts_by_status": counts_by_status,
            "sold_stats": sold_stats,
            "sold_items": sold_rows,
            "avg_days_to_sell": avg_days_to_sell,
            "portal_aggs": portal_aggs,
            "active_inventory_value": active_inventory_value
        }
    finally:
        conn.close()

# Automatická inicializace a migrace schématu při načtení modulu
try:
    init_db()
except Exception:
    pass

