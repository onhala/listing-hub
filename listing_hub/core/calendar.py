import re
import secrets
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Any, Optional

def escape_ical_text(text: str) -> str:
    """Escapes special characters according to RFC 5545 (commas, semicolons, backslashes, newlines)."""
    if not text:
        return ""
    text = text.replace("\\", "\\\\")
    text = text.replace(";", "\\;")
    text = text.replace(",", "\\,")
    text = text.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
    return text

def parse_listing_created_date(listing: Dict[str, Any]) -> date:
    """Extrahuje datum vytvoření inzerátu nebo provede fallback na základě days_old."""
    raw_created = listing.get("created_at")
    if raw_created:
        try:
            cleaned = str(raw_created).split("T")[0].split(" ")[0].strip()
            return datetime.strptime(cleaned, "%Y-%m-%d").date()
        except Exception:
            pass
        try:
            match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", str(raw_created))
            if match:
                d, m, y = match.groups()
                return date(int(y), int(m), int(d))
        except Exception:
            pass

    days_old = listing.get("days_old", 0)
    try:
        days_old = int(days_old or 0)
    except (ValueError, TypeError):
        days_old = 0
    return date.today() - timedelta(days=days_old)

def generate_ical_feed(listings: List[Dict[str, Any]], base_hub_url: str = "") -> str:
    """
    Generuje kompletní iCalendar feed (RFC 5545) pro Google Kalendář, Apple Kalendář a Outlook.
    Každý inzerát má celodenní událost přesně v den 60denní expirace na Bazoši.
    Prodané inzeráty zůstávají jako časový archiv s prefixem [PRODÁNO] a bez alarmů.
    """
    now_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Listing Hub//Bazos Calendar Feed//CS",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Listing Hub - Expirace inzerátů",
        "X-WR-CALDESC:Přehled 60denní expirace inzerátů z Bazoš.cz a Listing Hubu",
        "X-WR-TIMEZONE:Europe/Prague"
    ]

    for item in listings:
        status_val = str(item.get("status", "")).strip().lower()
        if status_val in ("smazáno", "smazano", "deleted", "archived"):
            continue

        portal_states = item.get("portal_states") or {}
        bazos_state = portal_states.get("bazos", {})
        bazos_url = bazos_state.get("url") or item.get("url") or ""
        bazos_status = str(bazos_state.get("status") or "").strip().lower()

        is_sold = (
            status_val in ("prodané", "prodane", "sold") or
            bazos_status in ("prodané", "prodane", "sold")
        )

        listing_id = item.get("id") or secrets.token_hex(8)
        title = item.get("title") or "Inzerát bez názvu"
        price = item.get("price", 0)
        try:
            price_formatted = f"{int(price):,} Kč".replace(",", " ")
        except (ValueError, TypeError):
            price_formatted = f"{price} Kč"

        created_date = parse_listing_created_date(item)
        exp_date = created_date + timedelta(days=60)
        exp_date_next = exp_date + timedelta(days=1)

        dtstart_str = exp_date.strftime("%Y%m%d")
        dtend_str = exp_date_next.strftime("%Y%m%d")
        created_str = created_date.strftime("%d.%m.%Y")
        exp_str = exp_date.strftime("%d.%m.%Y")

        hub_url = f"{base_hub_url.rstrip('/')}/#tab-active" if base_hub_url else ""
        if is_sold and base_hub_url:
            hub_url = f"{base_hub_url.rstrip('/')}/#tab-sold"

        desc_lines = [
            f"📦 Inzerát: {title}",
            f"💰 Cena: {price_formatted}",
            f"📅 Zveřejněno: {created_str}",
            f"⏳ Vyprší na Bazoši: {exp_str} (60 dní)" if not is_sold else "✅ Stav: Prodané",
        ]
        if bazos_url:
            desc_lines.append(f"🔗 Bazoš: {bazos_url}")
        if hub_url:
            desc_lines.append(f"⚡ Listing Hub: {hub_url}")

        description_raw = "\n".join(desc_lines)
        description_escaped = escape_ical_text(description_raw)

        if is_sold:
            summary_raw = f"✅ PRODÁNO: {title} ({price_formatted})"
        else:
            summary_raw = f"⚠️ Vyprší inzerát: {title} ({price_formatted})"
        summary_escaped = escape_ical_text(summary_raw)

        uid = f"listinghub-{listing_id}@roboton.com"

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now_utc}",
            f"DTSTART;VALUE=DATE:{dtstart_str}",
            f"DTEND;VALUE=DATE:{dtend_str}",
            f"SUMMARY:{summary_escaped}",
            f"DESCRIPTION:{description_escaped}",
        ])

        if bazos_url:
            lines.append(f"URL:{bazos_url}")
        elif hub_url:
            lines.append(f"URL:{hub_url}")

        if not is_sold:
            lines.extend([
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                f"DESCRIPTION:{escape_ical_text(f'Inzerát za 3 dny vyprší: {title}')}",
                "TRIGGER:-P3D",
                "END:VALARM"
            ])
            lines.extend([
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                f"DESCRIPTION:{escape_ical_text(f'Dnes vyprší inzerát na Bazoši: {title}')}",
                "TRIGGER:-PT0M",
                "END:VALARM"
            ])

        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
