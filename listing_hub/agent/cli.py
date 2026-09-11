#!/usr/bin/env python3
"""
Listing Hub CLI Client for AI Agents & Automation.
Author: Ondřej Hála

A robust, token-efficient command-line tool for interacting with Listing Hub.
Supports JSON output (--json) for seamless LLM parsing and direct execution.
"""

import os
import sys
import json
import argparse
import requests
from typing import Optional, Dict, Any

DEFAULT_SERVER = os.environ.get("LISTING_HUB_SERVER", "http://127.0.0.1:5001")
API_PREFIX = "/api/agent/v1"


def get_headers(token: Optional[str] = None) -> Dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    auth_token = token or os.environ.get("LISTING_HUB_API_TOKEN")
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    return headers


def make_request(method: str, url: str, headers: Dict[str, str], json_data: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None, timeout: float = 30.0) -> requests.Response:
    return requests.request(
        method=method,
        url=url,
        headers=headers,
        json=json_data,
        params=params,
        timeout=timeout
    )


# ============================================================================
# Local SQLite Fallbacks (when server is offline for read-only queries)
# ============================================================================

def local_db_summary() -> Dict[str, Any]:
    import listing_hub.core.db as db
    from listing_hub.core.version import APP_VERSION
    all_ads = db.get_all_listings()

    active_count = 0
    draft_count = 0
    sold_count = 0
    expiring_soon = []

    for ad in all_ads:
        portal_states = ad.get("portal_states", {})
        bazos = portal_states.get("bazos", {})
        status = (bazos.get("status") or "Aktivní").lower()
        url = (bazos.get("url") or ad.get("url") or "").strip()
        days_old = int(ad.get("days_old") or 0)

        if status in ("prodané", "sold"):
            sold_count += 1
        elif not url:
            draft_count += 1
        else:
            active_count += 1
            if days_old >= 50:
                expiring_soon.append({
                    "id": ad.get("id"),
                    "title": ad.get("title"),
                    "days_old": days_old,
                    "price": ad.get("price", 0),
                    "url": url
                })

    return {
        "status": "ok",
        "mode": "sqlite_fallback",
        "summary": {
            "total_listings": len(all_ads),
            "active_count": active_count,
            "draft_count": draft_count,
            "sold_count": sold_count,
            "needs_review_count": 0,
            "expiring_soon_count": len(expiring_soon),
            "expiring_soon": expiring_soon,
            "worker": {
                "running": False,
                "state": "unknown",
                "action_type": None,
                "listing_id": None,
                "error": None,
                "needs_sms": False
            },
            "app_version": APP_VERSION
        }
    }


def local_db_list(status_filter: str = "all", search: str = "", limit: int = 50) -> Dict[str, Any]:
    import listing_hub.core.db as db
    all_ads = db.get_all_listings()
    results = []

    for ad in all_ads:
        portal_states = ad.get("portal_states", {})
        bazos = portal_states.get("bazos", {})
        status_raw = (bazos.get("status") or "Aktivní").lower()
        url = (bazos.get("url") or ad.get("url") or "").strip()

        if status_raw in ("prodané", "sold"):
            canonical_status = "sold"
        elif not url:
            canonical_status = "draft"
        else:
            canonical_status = "active"

        if status_filter != "all" and canonical_status != status_filter:
            continue

        title = ad.get("title") or ""
        desc = ad.get("description") or ""
        if search and search not in title.lower() and search not in desc.lower():
            continue

        results.append({
            "id": ad.get("id"),
            "title": title,
            "price": ad.get("price", 0),
            "status": canonical_status,
            "category": ad.get("category") or "",
            "condition": ad.get("condition") or "",
            "days_old": int(ad.get("days_old") or 0),
            "views": bazos.get("views", 0),
            "url": url,
            "local_photos_dir": ad.get("local_photos_dir") or ""
        })

        if len(results) >= limit:
            break

    return {
        "status": "ok",
        "mode": "sqlite_fallback",
        "count": len(results),
        "listings": results
    }


# ============================================================================
# Command Handlers
# ============================================================================

def handle_summary(args: argparse.Namespace) -> int:
    url = f"{args.server.rstrip('/')}{API_PREFIX}/summary"
    headers = get_headers(args.token)

    data = None
    try:
        resp = make_request("GET", url, headers, timeout=args.timeout)
        if resp.status_code == 200:
            data = resp.json()
        else:
            print(f"Error {resp.status_code}: {resp.text}", file=sys.stderr)
            return 1
    except requests.exceptions.ConnectionError:
        # Fallback to local SQLite if server not running
        try:
            data = local_db_summary()
        except Exception as e:
            print(f"Server offline and SQLite fallback failed: {e}", file=sys.stderr)
            return 1

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    s = data.get("summary", {})
    w = s.get("worker", {})
    mode_tag = f" ({data.get('mode')})" if data.get("mode") else ""

    print("=" * 60)
    print(f"📦 Listing Hub Summary v{s.get('app_version', '3.x')}{mode_tag}")
    print("=" * 60)
    print(f"Total Listings:  {s.get('total_listings', 0)}")
    print(f"  • Active:      {s.get('active_count', 0)}")
    print(f"  • Drafts:      {s.get('draft_count', 0)}")
    print(f"  • Sold:        {s.get('sold_count', 0)}")
    print(f"  • In Review:   {s.get('needs_review_count', 0)}")
    print("-" * 60)
    print(f"🤖 Worker State: {w.get('state', 'idle').upper()} (running: {w.get('running', False)})")
    if w.get("action_type"):
        print(f"   Current Action: {w.get('action_type')} (listing: {w.get('listing_id')})")
    if w.get("error"):
        print(f"   ⚠️ Worker Error: {w.get('error')}")
    if w.get("needs_sms"):
        print("   🚨 SMS Guard: SMS verification required on Bazos!")

    exp = s.get("expiring_soon", [])
    if exp:
        print("-" * 60)
        print(f"⚠️ Expiring Soon (>= 50 days): {len(exp)} listing(s)")
        for item in exp:
            print(f"   - [{item.get('days_old')}d] {item.get('title')} ({item.get('price')} Kč) [ID: {item.get('id')}]")
    print("=" * 60)
    return 0


def handle_list(args: argparse.Namespace) -> int:
    url = f"{args.server.rstrip('/')}{API_PREFIX}/listings"
    headers = get_headers(args.token)
    params = {"status": args.status, "limit": args.limit}
    if args.search:
        params["search"] = args.search

    data = None
    try:
        resp = make_request("GET", url, headers, params=params, timeout=args.timeout)
        if resp.status_code == 200:
            data = resp.json()
        else:
            print(f"Error {resp.status_code}: {resp.text}", file=sys.stderr)
            return 1
    except requests.exceptions.ConnectionError:
        try:
            data = local_db_list(status_filter=args.status, search=args.search or "", limit=args.limit)
        except Exception as e:
            print(f"Server offline and SQLite fallback failed: {e}", file=sys.stderr)
            return 1

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    listings = data.get("listings", [])
    if not listings:
        print(f"No listings found (filter: status='{args.status}', search='{args.search or ''}').")
        return 0

    print(f"Found {len(listings)} listing(s):")
    print("-" * 80)
    print(f"{'STATUS':<12} {'PRICE':<10} {'DAYS':<6} {'VIEWS':<6} {'TITLE'}")
    print("-" * 80)
    for l in listings:
        status_str = l.get("status", "").upper()
        price_str = f"{l.get('price', 0)} Kč"
        days_str = f"{l.get('days_old', 0)}d"
        views_str = str(l.get("views", 0))
        title = l.get("title", "")
        if len(title) > 42:
            title = title[:39] + "..."
        print(f"{status_str:<12} {price_str:<10} {days_str:<6} {views_str:<6} {title} (ID: {l.get('id')})")
    print("-" * 80)
    return 0


def handle_get(args: argparse.Namespace) -> int:
    url = f"{args.server.rstrip('/')}{API_PREFIX}/listings/{args.id}"
    headers = get_headers(args.token)

    try:
        resp = make_request("GET", url, headers, timeout=args.timeout)
        if resp.status_code != 200:
            print(f"Error {resp.status_code}: {resp.text}", file=sys.stderr)
            return 1
        data = resp.json()
    except Exception as e:
        print(f"Request failed: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    l = data.get("listing", {})
    print("=" * 60)
    print(f"📄 {l.get('title')}")
    print("=" * 60)
    print(f"ID:          {l.get('id')}")
    print(f"Status:      {l.get('canonical_status', '').upper()}")
    print(f"Price:       {l.get('price')} Kč")
    print(f"Category:    {l.get('category') or 'N/A'}")
    print(f"Condition:   {l.get('condition') or 'N/A'}")
    print(f"Location:    {l.get('location') or 'N/A'}")
    print(f"Photos Dir:  {l.get('local_photos_dir') or 'N/A'}")
    photos = l.get("photos", [])
    print(f"Photos ({len(photos)}): {', '.join(photos[:5])}{' ...' if len(photos) > 5 else ''}")
    print("-" * 60)
    print("Description:")
    if l.get("portal_states"):
        for portal, state in l.get("portal_states").items():
            print(f"Portal [{portal}]: status={state.get('status')} views={state.get('views')} url={state.get('url')}")
    pubs = l.get("publications") or []
    if getattr(args, "history", False) or len(pubs) > 1:
        print("-" * 60)
        print(f"🔄 Publication History ({len(pubs)} publication(s), cumulative views: {l.get('cumulative_views', 0)}):")
        for idx, p in enumerate(pubs, 1):
            stat = p.get('status', '').upper()
            reason = f" ({p.get('close_reason')})" if p.get('close_reason') else ""
            dates = f"{p.get('published_at')} -> {p.get('closed_at') or 'active'}"
            print(f"  #{idx} [{stat}{reason}] {p.get('price')} Kč | {p.get('views', 0)} views | {dates} | {p.get('url') or ''}")
    print("=" * 60)
    return 0


def handle_draft(args: argparse.Namespace) -> int:
    url = f"{args.server.rstrip('/')}{API_PREFIX}/draft"
    headers = get_headers(args.token)

    payload = {
        "title": args.title,
        "price": args.price or 0,
        "description": args.desc or "",
        "category": args.category or "",
        "condition": args.condition or "Použité",
        "local_photos_dir": args.dir or "",
        "notes": args.notes or "",
        "auto_market_radar": args.radar
    }

    try:
        resp = make_request("POST", url, headers, json_data=payload, timeout=args.timeout)
        data = resp.json()
        if resp.status_code not in (200, 201):
            print(f"Error {resp.status_code}: {data.get('message', resp.text)}", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"Failed to create draft: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    l = data.get("listing", {})
    print(f"✅ Draft created successfully! ID: {l.get('id')}")
    print(f"Title: {l.get('title')}")
    print(f"Price: {l.get('price')} Kč")
    if data.get("market_radar"):
        r = data.get("market_radar")
        stats = r.get("stats", {})
        print(f"📊 Market Radar: Fair: {stats.get('suggested_fair')} Kč | Quick: {stats.get('suggested_quick_sale')} Kč | Premium: {stats.get('suggested_premium')} Kč")
    return 0


def handle_post(args: argparse.Namespace) -> int:
    url = f"{args.server.rstrip('/')}{API_PREFIX}/actions/post"
    headers = get_headers(args.token)

    payload = {"listing_id": args.id}
    if args.domain:
        payload["target_domain"] = args.domain

    try:
        resp = make_request("POST", url, headers, json_data=payload, timeout=args.timeout)
        data = resp.json()
        if resp.status_code not in (200, 202):
            print(f"Error {resp.status_code}: {data.get('message', resp.text)}", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"Failed to initiate posting: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    print("=" * 60)
    print("🚀 Phase 1 Posting Initiated (Autopilot Mode)")
    print("=" * 60)
    print(f"Listing ID:      {args.id}")
    if args.domain:
        print(f"Target Domain:   {args.domain}")
    print(f"Live Screencast: {data.get('screencast_url', 'http://127.0.0.1:5001/#screencast')}")
    print("-" * 60)
    print("👉 INSTRUCTIONS FOR USER / AGENT:")
    print("1. The background worker is prefilling the Bazos form and will halt in 'ready_for_review'.")
    print("2. Open the Live Browser view (screencast) to inspect the filled fields and solve SMS/CAPTCHA if prompted.")
    print("3. Click 'Odeslat' (Submit) in the browser on Bazos.")
    print("4. Execute: `listing-hub confirm` (or call POST /actions/confirm) to finalize and save the live URL.")
    print("=" * 60)
    return 0


def handle_status(args: argparse.Namespace) -> int:
    url = f"{args.server.rstrip('/')}{API_PREFIX}/actions/status"
    headers = get_headers(args.token)

    try:
        resp = make_request("GET", url, headers, timeout=args.timeout)
        data = resp.json()
    except Exception as e:
        print(f"Failed to get status: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    print(f"Worker Running: {data.get('running')}")
    print(f"State:          {data.get('state', '').upper()}")
    print(f"Action Type:    {data.get('action_type') or 'None'}")
    print(f"Listing ID:     {data.get('listing_id') or 'None'}")
    if data.get("error"):
        print(f"Error:          {data.get('error')}")
    print(f"Screencast:     {data.get('screencast_url')}")
    return 0


def handle_confirm(args: argparse.Namespace) -> int:
    url = f"{args.server.rstrip('/')}{API_PREFIX}/actions/confirm"
    headers = get_headers(args.token)

    try:
        resp = make_request("POST", url, headers, timeout=args.timeout)
        data = resp.json()
        if resp.status_code != 200:
            print(f"Error {resp.status_code}: {data.get('message', resp.text)}", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"Confirmation failed: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    print("🎉 Listing submission successfully confirmed!")
    print(f"Message: {data.get('message')}")
    if data.get("url"):
        print(f"Live Ad URL: {data.get('url')}")
    return 0


def handle_cancel(args: argparse.Namespace) -> int:
    url = f"{args.server.rstrip('/')}{API_PREFIX}/actions/cancel"
    headers = get_headers(args.token)

    try:
        resp = make_request("POST", url, headers, timeout=args.timeout)
        data = resp.json()
    except Exception as e:
        print(f"Cancellation failed: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    print(f"🛑 {data.get('message', 'Action cancelled.')}")
    return 0


def handle_repost(args: argparse.Namespace) -> int:
    url = f"{args.server.rstrip('/')}{API_PREFIX}/actions/repost"
    headers = get_headers(args.token)

    payload = {
        "listing_id": args.id,
        "new_price": args.new_price
    }
    if args.domain:
        payload["target_domain"] = args.domain

    try:
        resp = make_request("POST", url, headers, json_data=payload, timeout=args.timeout)
        data = resp.json()
        if resp.status_code != 200:
            print(f"Error {resp.status_code}: {data.get('message', resp.text)}", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"Repost failed: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    print(f"🔄 {data.get('message', 'Repost initiated.')}")
    return 0


def handle_delete(args: argparse.Namespace) -> int:
    url = f"{args.server.rstrip('/')}{API_PREFIX}/listings/{args.id}"
    headers = get_headers(args.token)
    payload = {"delete_photos": args.delete_photos}

    try:
        resp = make_request("DELETE", url, headers, json_data=payload, timeout=args.timeout)
        data = resp.json()
        if resp.status_code != 200:
            print(f"Error {resp.status_code}: {data.get('message', resp.text)}", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"Delete failed: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    print(f"🗑️ {data.get('message', 'Listing deleted.')}")
    return 0


def handle_radar(args: argparse.Namespace) -> int:
    url = f"{args.server.rstrip('/')}{API_PREFIX}/radar"
    headers = get_headers(args.token)
    payload = {
        "query": args.query,
        "brand": args.brand or "",
        "model": args.model or "",
        "condition": args.condition or "Použité",
        "fallback_price": args.price or 0
    }

    try:
        resp = make_request("POST", url, headers, json_data=payload, timeout=max(args.timeout, 45.0))
        data = resp.json()
        if resp.status_code != 200:
            print(f"Error {resp.status_code}: {data.get('message', resp.text)}", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"Radar check failed: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    radar = data.get("radar", {})
    stats = radar.get("stats", {})

    print("=" * 60)
    print(f"📊 Market Radar: {args.query}")
    print("=" * 60)
    print(f"Sources Checked: {', '.join(radar.get('sources_checked', []))}")
    print(f"Sample Count:    {len(radar.get('listings', []))} listings analyzed")
    print("-" * 60)
    print(f"Price Range:     {stats.get('min', 0)} Kč - {stats.get('max', 0)} Kč")
    print(f"Market Median:   {stats.get('median', 0)} Kč")
    print("-" * 60)
    print("🎯 Recommended Price Points:")
    print(f"  • Quick Sale (-10%): {stats.get('suggested_quick_sale', 0)} Kč")
    print(f"  • Fair Market:       {stats.get('suggested_fair', 0)} Kč")
    print(f"  • Premium (+10%):    {stats.get('suggested_premium', 0)} Kč")
    if stats.get("reference_new_price"):
        print(f"  • Reference New:     {stats.get('reference_new_price')} Kč")
    if radar.get("reasoning"):
        print(f"AI Reasoning:    {radar.get('reasoning')}")
    print("=" * 60)
    return 0


# ============================================================================
# Argument Parser Definition
# ============================================================================

def build_parser() -> argparse.ArgumentParser:
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--server", default=DEFAULT_SERVER, help=f"Listing Hub server URL (default: {DEFAULT_SERVER})")
    common_parser.add_argument("--token", default=None, help="Bearer API token (or set LISTING_HUB_API_TOKEN)")
    common_parser.add_argument("--timeout", type=float, default=30.0, help="Request timeout in seconds (default: 30)")
    common_parser.add_argument("--json", action="store_true", help="Output raw JSON for machine consumption")

    parser = argparse.ArgumentParser(
        prog="listing-hub",
        description="Listing Hub Agent CLI: Autonomous classifieds management.",
        parents=[common_parser]
    )

    subparsers = parser.add_subparsers(dest="subcommand", required=True, help="Subcommand to execute")

    # summary
    p_summary = subparsers.add_parser("summary", parents=[common_parser], help="Show inventory and worker dashboard summary")
    p_summary.set_defaults(func=handle_summary)

    # list
    p_list = subparsers.add_parser("list", parents=[common_parser], help="List listings by status and filter")
    p_list.add_argument("--status", choices=["all", "draft", "active", "sold", "needs_review"], default="all", help="Filter by status")
    p_list.add_argument("--search", default="", help="Search query on title or description")
    p_list.add_argument("--limit", type=int, default=50, help="Max results (default: 50)")
    p_list.set_defaults(func=handle_list)

    # get
    p_get = subparsers.add_parser("get", parents=[common_parser], help="Get complete details of a single listing")
    p_get.add_argument("id", help="Listing ID or local photos dir")
    p_get.add_argument("--history", action="store_true", help="Include full publication history timeline")
    p_get.set_defaults(func=handle_get)

    # draft
    p_draft = subparsers.add_parser("draft", parents=[common_parser], help="Create a new draft listing")
    p_draft.add_argument("title", help="Listing title (max 50 chars)")
    p_draft.add_argument("--price", type=int, default=0, help="Asking price in CZK")
    p_draft.add_argument("--desc", default="", help="Description text")
    p_draft.add_argument("--dir", default="", help="Photos directory relative to photos/")
    p_draft.add_argument("--category", default="", help="Category name")
    p_draft.add_argument("--condition", default="Použité", help="Condition (default: Použité)")
    p_draft.add_argument("--notes", default="", help="Internal seller notes")
    p_draft.add_argument("--radar", action="store_true", help="Automatically query market radar for price")
    p_draft.set_defaults(func=handle_draft)

    # post
    p_post = subparsers.add_parser("post", parents=[common_parser], help="Initiate Phase 1 supervised ad posting on Bazos")
    p_post.add_argument("id", help="Listing ID or photos dir to post")
    p_post.add_argument("--domain", default=None, help="Explicit target domain (e.g. dum.bazos.cz)")
    p_post.set_defaults(func=handle_post)

    # status
    p_status = subparsers.add_parser("status", parents=[common_parser], help="Check worker and action status")
    p_status.set_defaults(func=handle_status)

    # confirm
    p_confirm = subparsers.add_parser("confirm", parents=[common_parser], help="Phase 2: Confirm submission after human review")
    p_confirm.set_defaults(func=handle_confirm)

    # cancel
    p_cancel = subparsers.add_parser("cancel", parents=[common_parser], help="Cancel active posting or worker action")
    p_cancel.set_defaults(func=handle_cancel)

    # repost
    p_repost = subparsers.add_parser("repost", parents=[common_parser], help="Repost listing with updated price (top-up)")
    p_repost.add_argument("id", help="Listing ID to repost")
    p_repost.add_argument("new_price", type=int, help="New price in CZK")
    p_repost.add_argument("--domain", default=None, help="Explicit target domain")
    p_repost.set_defaults(func=handle_repost)

    # delete
    p_delete = subparsers.add_parser("delete", parents=[common_parser], help="Purge listing from DB")
    p_delete.add_argument("id", help="Listing ID to delete")
    p_delete.add_argument("--delete-photos", action="store_true", help="Also safely delete local photos")
    p_delete.set_defaults(func=handle_delete)

    # radar
    p_radar = subparsers.add_parser("radar", parents=[common_parser], help="Query multi-source market price radar")
    p_radar.add_argument("query", help="Item name or query to search")
    p_radar.add_argument("--brand", default="", help="Item brand")
    p_radar.add_argument("--model", default="", help="Item model")
    p_radar.add_argument("--condition", default="Použité", help="Condition")
    p_radar.add_argument("--price", type=int, default=0, help="Fallback price in CZK")
    p_radar.set_defaults(func=handle_radar)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
