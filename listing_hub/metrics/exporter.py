import re
from datetime import datetime, timezone
from typing import Dict, Any, List

from listing_hub.core.db import get_metrics_snapshot_data
from listing_hub.core.config import load_user_config

def sanitize_label_value(val: Any) -> str:
    """Sanitizuje hodnotu pro použití v Prometheus labelu."""
    if val is None:
        return ""
    s = str(val)
    # Nahradíme zpětná lomítka, uvozovky a nové řádky
    s = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", "")
    # Omezíme délku na max 60 znaků pro předcházení kardinalitnímu bloatu
    if len(s) > 60:
        s = s[:57] + "..."
    return s.strip()

def parse_iso_to_unix(iso_str: str) -> float:
    """Převede ISO timestamp na unix sekundy."""
    if not iso_str:
        return 0.0
    try:
        # Odstranění 'Z' na konci nebo standardní ISO
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        try:
            # Fallback pro formát YYYY-MM-DD
            dt = datetime.strptime(iso_str, "%Y-%m-%d")
            return dt.replace(tzinfo=timezone.utc).timestamp()
        except Exception:
            return 0.0

def generate_prometheus_metrics() -> str:
    """
    Vygeneruje kompletní sadu metrik Listing Hubu v oficiálním formátu
    Prometheus text exposition format (version 0.0.4 / OpenMetrics).
    """
    lines: List[str] = []
    
    # 1. Základní stav služby
    lines.append("# HELP listinghub_up Indikátor dostupnosti a běhu služby Listing Hub (1 = online)")
    lines.append("# TYPE listinghub_up gauge")
    lines.append("listinghub_up 1")
    lines.append("")

    # Získání dat z databáze a konfigurace
    try:
        data = get_metrics_snapshot_data()
        user_config = load_user_config()
    except Exception as e:
        # V případě kritického selhání DB vrátíme alespoň chybový indikátor
        lines.append("# HELP listinghub_db_error Indikátor chyby čtení z databáze (1 = chyba)")
        lines.append("# TYPE listinghub_db_error gauge")
        lines.append("listinghub_db_error 1")
        return "\n".join(lines) + "\n"

    active_portal_listings = data.get("active_portal_listings", [])
    counts_by_status = data.get("counts_by_status", {})
    sold_stats = data.get("sold_stats", {})
    portal_aggs = data.get("portal_aggs", [])
    active_inv_value = data.get("active_inventory_value", 0)

    # 2. Celkový počet inzerátů dle životního cyklu
    lines.append("# HELP listinghub_listings_count Celkový počet inzerátů v systému rozdělených podle stavu")
    lines.append("# TYPE listinghub_listings_count gauge")
    for status in ["active", "unsold", "sold"]:
        count = counts_by_status.get(status, 0)
        lines.append(f'listinghub_listings_count{{status="{status}"}} {count}')
    lines.append("")

    # 3. Hodnota aktivního skladu
    lines.append("# HELP listinghub_active_inventory_value_czk Celková nabídková hodnota aktivního skladu v Kč")
    lines.append("# TYPE listinghub_active_inventory_value_czk gauge")
    lines.append(f"listinghub_active_inventory_value_czk {active_inv_value}")
    lines.append("")

    # 4. Celková zhlédnutí a zhlédnutí dle jednotlivých inzerátů (Trendy)
    total_views = sum(int(row.get("views") or 0) for row in active_portal_listings)
    lines.append("# HELP listinghub_listing_views_total Celkový kumulativní součet zhlédnutí všech aktivních inzerátů")
    lines.append("# TYPE listinghub_listing_views_total gauge")
    lines.append(f"listinghub_listing_views_total {total_views}")
    lines.append("")

    lines.append("# HELP listinghub_listing_views Aktuální počet zhlédnutí inzerátu na daném portálu")
    lines.append("# TYPE listinghub_listing_views gauge")
    for row in active_portal_listings:
        l_id = sanitize_label_value(row.get("id"))
        title = sanitize_label_value(row.get("title"))
        portal = sanitize_label_value(row.get("portal_name"))
        category = sanitize_label_value(row.get("category"))
        views = int(row.get("views") or 0)
        lines.append(f'listinghub_listing_views{{id="{l_id}",title="{title}",portal="{portal}",category="{category}"}} {views}')
    lines.append("")

    # 5. Nabídková cena inzerátů
    lines.append("# HELP listinghub_listing_price_czk Nabídková cena inzerátu v Kč")
    lines.append("# TYPE listinghub_listing_price_czk gauge")
    for row in active_portal_listings:
        l_id = sanitize_label_value(row.get("id"))
        title = sanitize_label_value(row.get("title"))
        portal = sanitize_label_value(row.get("portal_name"))
        price = int(row.get("price") or 0)
        lines.append(f'listinghub_listing_price_czk{{id="{l_id}",title="{title}",portal="{portal}"}} {price}')
    lines.append("")

    # 6. Stáří inzerátů ve dnech (pro detekci ležáků)
    lines.append("# HELP listinghub_listing_days_old Stáří inzerátu ve dnech od vystavení")
    lines.append("# TYPE listinghub_listing_days_old gauge")
    for row in active_portal_listings:
        l_id = sanitize_label_value(row.get("id"))
        title = sanitize_label_value(row.get("title"))
        portal = sanitize_label_value(row.get("portal_name"))
        days_old = int(row.get("days_old") or 0)
        lines.append(f'listinghub_listing_days_old{{id="{l_id}",title="{title}",portal="{portal}"}} {days_old}')
    lines.append("")

    # 7. Placené TOPování
    lines.append("# HELP listinghub_listing_is_top Indikátor aktivního placeného TOPování (1 = ano, 0 = ne)")
    lines.append("# TYPE listinghub_listing_is_top gauge")
    for row in active_portal_listings:
        l_id = sanitize_label_value(row.get("id"))
        title = sanitize_label_value(row.get("title"))
        portal = sanitize_label_value(row.get("portal_name"))
        is_top = 1 if row.get("is_top") else 0
        lines.append(f'listinghub_listing_is_top{{id="{l_id}",title="{title}",portal="{portal}"}} {is_top}')
    lines.append("")

    # 8. Portálové agregace (počet inzerátů a zhlédnutí dle portálu)
    lines.append("# HELP listinghub_portal_listings_count Počet aktivních inzerátů na daném portálu")
    lines.append("# TYPE listinghub_portal_listings_count gauge")
    for p in portal_aggs:
        portal = sanitize_label_value(p.get("portal_name"))
        p_count = int(p.get("active_count") or 0)
        lines.append(f'listinghub_portal_listings_count{{portal="{portal}"}} {p_count}')
    lines.append("")

    lines.append("# HELP listinghub_portal_views_total Celkový součet zhlédnutí inzerátů na daném portálu")
    lines.append("# TYPE listinghub_portal_views_total gauge")
    for p in portal_aggs:
        portal = sanitize_label_value(p.get("portal_name"))
        p_views = int(p.get("total_views") or 0)
        lines.append(f'listinghub_portal_views_total{{portal="{portal}"}} {p_views}')
    lines.append("")

    lines.append("# HELP listinghub_portal_last_sync_timestamp_seconds Unix timestamp poslední úspěšné synchronizace portálu")
    lines.append("# TYPE listinghub_portal_last_sync_timestamp_seconds gauge")
    for p in portal_aggs:
        portal = sanitize_label_value(p.get("portal_name"))
        last_sync_ts = parse_iso_to_unix(p.get("last_sync") or "")
        lines.append(f'listinghub_portal_last_sync_timestamp_seconds{{portal="{portal}"}} {last_sync_ts:.0f}')
    lines.append("")

    # 9. Finanční statistiky prodejů
    total_sold = sold_stats.get("total_sold", 0)
    total_profit = sold_stats.get("total_profit", 0)
    avg_price = sold_stats.get("avg_price", 0)

    lines.append("# HELP listinghub_sales_total_czk Celkové kumulativní tržby z realizovaných prodejů v Kč")
    lines.append("# TYPE listinghub_sales_total_czk counter")
    lines.append(f"listinghub_sales_total_czk {total_profit}")
    lines.append("")

    lines.append("# HELP listinghub_sales_count_total Celkový počet úspěšně prodaných inzerátů")
    lines.append("# TYPE listinghub_sales_count_total counter")
    lines.append(f"listinghub_sales_count_total {total_sold}")
    lines.append("")

    lines.append("# HELP listinghub_sales_avg_price_czk Průměrná realizovaná cena prodaných položek v Kč")
    lines.append("# TYPE listinghub_sales_avg_price_czk gauge")
    lines.append(f"listinghub_sales_avg_price_czk {avg_price}")
    lines.append("")

    # 10. Prodeje dle kanálů
    by_channel = sold_stats.get("by_channel", {})
    if by_channel:
        lines.append("# HELP listinghub_sales_by_channel_total_czk Realizované tržby rozdělené podle prodejního kanálu v Kč")
        lines.append("# TYPE listinghub_sales_by_channel_total_czk gauge")
        for ch, ch_data in by_channel.items():
            ch_name = sanitize_label_value(ch)
            lines.append(f'listinghub_sales_by_channel_total_czk{{channel="{ch_name}"}} {ch_data.get("profit", 0)}')
        lines.append("")

        lines.append("# HELP listinghub_sales_by_channel_count Počet prodaných kusů rozdělených podle prodejního kanálu")
        lines.append("# TYPE listinghub_sales_by_channel_count gauge")
        for ch, ch_data in by_channel.items():
            ch_name = sanitize_label_value(ch)
            lines.append(f'listinghub_sales_by_channel_count{{channel="{ch_name}"}} {ch_data.get("count", 0)}')
        lines.append("")

    # 11. Provozní stav a automatizace
    auto_refresh_status = user_config.get("auto_refresh_status", "ok")
    status_numeric = 1 if auto_refresh_status == "ok" else 0
    lines.append("# HELP listinghub_baza_auto_refresh_status Provozní stav Bazoš auto-refresh workeru (1 = OK, 0 = vyžaduje SMS nebo chyba)")
    lines.append("# TYPE listinghub_baza_auto_refresh_status gauge")
    lines.append(f"listinghub_baza_auto_refresh_status {status_numeric}")
    lines.append("")

    last_refresh_time = user_config.get("last_refresh_time", "")
    last_refresh_ts = parse_iso_to_unix(last_refresh_time)
    lines.append("# HELP listinghub_last_refresh_timestamp_seconds Unix timestamp posledního auto-refresh cyklu")
    lines.append("# TYPE listinghub_last_refresh_timestamp_seconds gauge")
    lines.append(f"listinghub_last_refresh_timestamp_seconds {last_refresh_ts:.0f}")
    lines.append("")

    return "\n".join(lines) + "\n"
