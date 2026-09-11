"""
Listing Hub Agent REST API (v1).
Author: Ondřej Hála

Provides token-efficient, type-safe REST endpoints for AI agents (Antigravity)
to inspect inventory, evaluate market pricing, draft ads, and orchestrate
the two-phase supervised posting workflow.
"""

import os
import json
import uuid
import hmac
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from flask import Blueprint, request, jsonify

import listing_hub.core.db as db
from listing_hub.core.config import PHOTOS_DIR, PROJECT_ROOT, CONFIG_PATH, load_user_config
from listing_hub.core.version import APP_VERSION
from listing_hub.ai.advisor import analyze_market_prices as unified_market_price_radar

agent_bp = Blueprint("agent_api", __name__)


def check_agent_auth() -> Optional[Any]:
    """
    Validate agent authentication.
    If LISTING_HUB_API_TOKEN is set in environment, enforces constant-time Bearer token check.
    If not set, allows loopback / private network requests by default.
    """
    expected_token = os.environ.get("LISTING_HUB_API_TOKEN")
    if not expected_token:
        remote_ip = request.remote_addr or ""
        is_local = (
            remote_ip in ("127.0.0.1", "::1", "localhost") or
            remote_ip.startswith("172.") or
            remote_ip.startswith("10.") or
            remote_ip.startswith("192.168.")
        )
        if is_local:
            return None
        return jsonify({
            "status": "error",
            "error_code": "AUTH_REQUIRED",
            "message": "LISTING_HUB_API_TOKEN is required for remote connections."
        }), 401

    auth_header = request.headers.get("Authorization", "")
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "X-API-Key" in request.headers:
        token = request.headers.get("X-API-Key", "").strip()
    elif request.args.get("token"):
        token = request.args.get("token", "").strip()

    if not token or not hmac.compare_digest(token, expected_token):
        return jsonify({
            "status": "error",
            "error_code": "AUTH_FAILED",
            "message": "Invalid or missing Bearer API token."
        }), 401
    return None


@agent_bp.before_request
def before_agent_request():
    auth_response = check_agent_auth()
    if auth_response is not None:
        return auth_response


def safe_resolve_photos_dir(raw_photos_dir: Optional[str]) -> Optional[Path]:
    """Safely resolve photo directory ensuring it resides within PHOTOS_DIR."""
    if not raw_photos_dir:
        return None
    try:
        photos_base = PHOTOS_DIR.resolve()
        target = Path(raw_photos_dir)
        if not target.is_absolute():
            target = (photos_base / target).resolve()
        else:
            target = target.resolve()

        if target == photos_base or not target.is_relative_to(photos_base):
            return None
        return target
    except Exception:
        return None


def get_listing_lifecycle_status(listing: Dict[str, Any], worker_status: Optional[Dict[str, Any]] = None) -> str:
    """
    Map listing to canonical Domain Lifecycle Status:
    - Draft: No portal URL assigned
    - Active: Portal URL assigned and not sold
    - Sold: Marked as Prodané / Sold
    - NeedsReview: Worker is currently paused in ready_for_review for this listing
    """
    listing_id = listing.get("id")
    if worker_status and worker_status.get("state") == "ready_for_review" and worker_status.get("listing_id") == listing_id:
        return "needs_review"

    portal_states = listing.get("portal_states", {})
    bazos_state = portal_states.get("bazos", {})
    aukro_state = portal_states.get("aukro", {})

    status_raw = (bazos_state.get("status") or aukro_state.get("status") or "Aktivní").lower()
    if status_raw in ("prodané", "sold"):
        return "sold"

    url = (bazos_state.get("url") or aukro_state.get("url") or listing.get("url") or "").strip()
    if not url:
        return "draft"

    return "active"


# ============================================================================
# 1. Summary Endpoint (Token-efficient dashboard)
# ============================================================================

@agent_bp.route("/summary", methods=["GET"])
def agent_summary():
    """Returns a token-optimized JSON summary of listings and worker state."""
    try:
        all_ads = db.get_all_listings()
        from app import action_state_mgr, playwright_process

        status_info = action_state_mgr.get_status()
        worker_running = bool(playwright_process and playwright_process.is_alive())

        needs_sms = False
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    if cfg.get("user", {}).get("auto_refresh_status") == "needs_sms":
                        needs_sms = True
            except Exception:
                pass

        active_count = 0
        draft_count = 0
        sold_count = 0
        needs_review_count = 0
        expiring_soon = []

        for ad in all_ads:
            canonical_status = get_listing_lifecycle_status(ad, status_info)
            days_old = int(ad.get("days_old") or 0)

            if canonical_status == "sold":
                sold_count += 1
            elif canonical_status == "draft":
                draft_count += 1
            elif canonical_status == "needs_review":
                needs_review_count += 1
                active_count += 1
            else:
                active_count += 1
                if days_old >= 50:
                    portal_states = ad.get("portal_states", {})
                    url = portal_states.get("bazos", {}).get("url") or ad.get("url", "")
                    expiring_soon.append({
                        "id": ad.get("id"),
                        "title": ad.get("title"),
                        "days_old": days_old,
                        "price": ad.get("price", 0),
                        "url": url
                    })

        return jsonify({
            "status": "ok",
            "summary": {
                "total_listings": len(all_ads),
                "active_count": active_count,
                "draft_count": draft_count,
                "sold_count": sold_count,
                "needs_review_count": needs_review_count,
                "expiring_soon_count": len(expiring_soon),
                "expiring_soon": expiring_soon,
                "worker": {
                    "running": worker_running,
                    "state": status_info.get("state"),
                    "action_type": status_info.get("action_type"),
                    "listing_id": status_info.get("listing_id"),
                    "error": status_info.get("error"),
                    "needs_sms": needs_sms
                },
                "app_version": APP_VERSION
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================================
# 2. Listings Query Endpoints
# ============================================================================

@agent_bp.route("/listings", methods=["GET"])
def agent_list_listings():
    """
    List listings with optional status filter, search query, and limit.
    status filter: 'all' | 'draft' | 'active' | 'sold' | 'needs_review'
    """
    try:
        from app import action_state_mgr
        status_info = action_state_mgr.get_status()

        status_filter = request.args.get("status", "all").lower().strip()
        search_query = request.args.get("search", "").lower().strip()
        limit = min(int(request.args.get("limit", 50)), 200)

        all_ads = db.get_all_listings()
        results = []

        for ad in all_ads:
            canonical_status = get_listing_lifecycle_status(ad, status_info)

            if status_filter != "all" and canonical_status != status_filter:
                continue

            title = ad.get("title") or ""
            desc = ad.get("description") or ""
            if search_query and search_query not in title.lower() and search_query not in desc.lower():
                continue

            portal_states = ad.get("portal_states", {})
            bazos_state = portal_states.get("bazos", {})

            # Count photos if local dir exists
            p_dir = ad.get("local_photos_dir")
            p_count = 0
            if p_dir:
                try:
                    resolved_p = Path(p_dir) if Path(p_dir).is_absolute() else (PROJECT_ROOT / p_dir)
                    if resolved_p.exists():
                        p_count = len([f for f in os.listdir(resolved_p) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
                except Exception:
                    pass

            results.append({
                "id": ad.get("id"),
                "title": title,
                "price": ad.get("price", 0),
                "status": canonical_status,
                "category": ad.get("category") or "",
                "condition": ad.get("condition") or "",
                "days_old": int(ad.get("days_old") or 0),
                "views": bazos_state.get("views", 0),
                "url": bazos_state.get("url") or ad.get("url") or "",
                "photos_count": p_count,
                "local_photos_dir": p_dir or "",
                "created_at": ad.get("created_at") or ""
            })

            if len(results) >= limit:
                break

        return jsonify({
            "status": "ok",
            "count": len(results),
            "listings": results
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@agent_bp.route("/listings/<listing_id>", methods=["GET"])
def agent_get_listing(listing_id: str):
    """Retrieve full detail for a single listing."""
    try:
        from app import action_state_mgr
        status_info = action_state_mgr.get_status()

        listing = db.get_listing_by_id(listing_id)
        if not listing:
            # Fallback search by local_photos_dir
            for item in db.get_all_listings():
                if item.get("local_photos_dir") == listing_id:
                    listing = item
                    break

        if not listing:
            return jsonify({"status": "error", "message": f"Listing '{listing_id}' not found"}), 404

        listing_dict = dict(listing)
        canonical_status = get_listing_lifecycle_status(listing_dict, status_info)
        listing_dict["canonical_status"] = canonical_status

        # Collect photo list
        p_dir = listing_dict.get("local_photos_dir")
        photos = []
        if p_dir:
            try:
                resolved_p = Path(p_dir) if Path(p_dir).is_absolute() else (PROJECT_ROOT / p_dir)
                if resolved_p.exists():
                    photos = sorted([f for f in os.listdir(resolved_p) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
            except Exception:
                pass
        listing_dict["photos"] = photos

        return jsonify({
            "status": "ok",
            "listing": listing_dict
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@agent_bp.route("/listings/<listing_id>/history", methods=["GET"])
def agent_get_listing_history(listing_id: str):
    """Retrieve full publication history and price timeline for a listing."""
    try:
        from listing_hub.core.db import get_listing_publications, get_listing_cumulative_stats, get_listing_by_id
        listing = get_listing_by_id(listing_id)
        if not listing:
            for cand in db.get_all_listings():
                if cand.get("local_photos_dir") == listing_id:
                    listing = cand
                    listing_id = cand.get("id")
                    break
        if not listing:
            return jsonify({"status": "error", "message": f"Listing '{listing_id}' not found"}), 404

        publications = get_listing_publications(listing_id)
        cumulative_stats = get_listing_cumulative_stats(listing_id)
        return jsonify({
            "status": "ok",
            "listing_id": listing_id,
            "publications": publications,
            "cumulative_stats": cumulative_stats
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================================
# 3. Draft Ad Creation
# ============================================================================

@agent_bp.route("/draft", methods=["POST"])
def agent_create_draft():
    """
    Atomically create a new Draft listing.
    Payload:
    - title: str (required, max 50 chars)
    - price: int (optional, default 0)
    - description: str (optional)
    - category: str (optional)
    - condition: str (optional)
    - local_photos_dir: str (optional)
    - notes: str (optional)
    - auto_market_radar: bool (optional, runs market radar for price guidance)
    """
    try:
        payload = request.json or {}
        title = (payload.get("title") or "").strip()
        if not title:
            return jsonify({"status": "error", "message": "Missing required field 'title'"}), 400

        title_trimmed = title[:50].strip()
        price = int(payload.get("price") or 0)
        description = (payload.get("description") or "").strip()
        category = (payload.get("category") or "").strip()
        condition = (payload.get("condition") or "Použité").strip()
        local_photos_dir = (payload.get("local_photos_dir") or "").strip()
        notes = (payload.get("notes") or "").strip()
        target_bazos = int(payload.get("target_bazos", 1))
        target_aukro = int(payload.get("target_aukro", 0))

        # Check local_photos_dir if provided
        if local_photos_dir:
            safe_target = safe_resolve_photos_dir(local_photos_dir)
            if not safe_target:
                # If path didn't resolve inside PHOTOS_DIR, reject to prevent traversal
                return jsonify({
                    "status": "error",
                    "error_code": "INVALID_PHOTOS_DIR",
                    "message": f"Photos directory '{local_photos_dir}' must reside strictly within PHOTOS_DIR."
                }), 400

        listing_id = str(uuid.uuid4())
        new_listing = {
            "id": listing_id,
            "title": title_trimmed,
            "description": description,
            "price": price,
            "category": category,
            "condition": condition,
            "local_photos_dir": local_photos_dir,
            "location": payload.get("location") or "Český Krumlov",
            "notes": notes,
            "ad_password_b64": "",
            "bookmarklet_uri": "",
            "days_old": 0,
            "created_at": datetime.now().strftime("%Y-%m-%d"),
            "target_bazos": target_bazos,
            "target_aukro": target_aukro
        }

        portal_states = {
            "bazos": {
                "portal_item_id": None,
                "url": "",
                "status": "Koncept",
                "views": 0,
                "last_synced": datetime.now().isoformat()
            }
        }

        radar_data = None
        if payload.get("auto_market_radar"):
            try:
                radar_data = unified_market_price_radar(
                    item_name=title_trimmed,
                    brand=payload.get("brand", ""),
                    model=payload.get("model", ""),
                    condition=condition,
                    fallback_price=price
                )
                if not price and radar_data.get("stats", {}).get("suggested_fair"):
                    new_listing["price"] = int(radar_data["stats"]["suggested_fair"])
            except Exception as r_err:
                radar_data = {"error": str(r_err)}

        db.save_listing(new_listing, portal_states)

        return jsonify({
            "status": "success",
            "message": "Draft listing created successfully.",
            "listing": new_listing,
            "market_radar": radar_data
        }), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================================
# 4. Two-Phase Posting & Browser Actions
# ============================================================================

@agent_bp.route("/actions/post", methods=["POST"])
def agent_action_post():
    """
    Phase 1: Supervised ad posting initialization.
    Dispatches background worker to prefill Bazos ad form.
    Halts at 'ready_for_review' boundary.
    """
    try:
        from app import playwright_process, process_target, load_data

        if playwright_process and playwright_process.is_alive():
            return jsonify({
                "status": "error",
                "error_code": "WORKER_BUSY",
                "message": "Another automation task is currently in progress."
            }), 409

        if os.path.exists("/tmp/playwright_error.txt"):
            try:
                os.remove("/tmp/playwright_error.txt")
            except Exception:
                pass

        payload = request.json or {}
        listing_id = payload.get("id") or payload.get("listing_id")
        target_domain = payload.get("target_domain")

        if not listing_id:
            return jsonify({"status": "error", "message": "Missing required field 'id' or 'listing_id'"}), 400

        listing = db.get_listing_by_id(listing_id)
        if not listing:
            # Fallback search by local_photos_dir or title
            for item in db.get_all_listings():
                if item.get("local_photos_dir") == listing_id or item.get("title") == listing_id:
                    listing = item
                    break

        if not listing:
            return jsonify({"status": "error", "message": f"Listing '{listing_id}' not found"}), 404

        ad_dict = dict(listing)
        if target_domain:
            ad_dict["target_domain"] = target_domain

        _, user_config = load_data()

        # Launch background worker
        from app import ActionStateManager
        worker_thread = threading.Thread(
            target=process_target,
            args=(ad_dict, user_config, "post", None),
            daemon=True
        )
        import app
        app.playwright_process = worker_thread
        worker_thread.start()

        return jsonify({
            "status": "success",
            "message": "Phase 1 posting initiated. Worker is prefilling the form.",
            "listing_id": listing.get("id"),
            "target_domain": target_domain,
            "hitl_phase": "phase_1_started",
            "screencast_url": "http://127.0.0.1:5001/#screencast",
            "instructions": "Worker will halt in 'ready_for_review'. Verify form on live screencast, click Submit on Bazos, then call POST /api/agent/v1/actions/confirm."
        }), 202
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@agent_bp.route("/actions/status", methods=["GET"])
def agent_action_status():
    """Retrieve current worker and action status."""
    try:
        from app import action_state_mgr, playwright_process

        status_info = action_state_mgr.get_status()
        running = bool(playwright_process and playwright_process.is_alive())
        error = status_info.get("error")

        if not error and os.path.exists("/tmp/playwright_error.txt"):
            try:
                with open("/tmp/playwright_error.txt", "r", encoding="utf-8") as f:
                    error = f.read().strip()
            except Exception:
                pass

        return jsonify({
            "status": "ok",
            "running": running,
            "state": status_info.get("state"),
            "action_type": status_info.get("action_type"),
            "listing_id": status_info.get("listing_id"),
            "error": error,
            "screencast_url": "http://127.0.0.1:5001/#screencast"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@agent_bp.route("/actions/confirm", methods=["POST"])
def agent_action_confirm():
    """
    Phase 2: Finalize submission after human review.
    Verifies that the ad was submitted on Bazos and captures the live URL into DB.
    """
    try:
        from app import confirm_action
        return confirm_action()
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@agent_bp.route("/actions/cancel", methods=["POST"])
def agent_action_cancel():
    """Immediately terminate active worker session and reset action state."""
    try:
        from app import cancel_action
        return cancel_action()
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@agent_bp.route("/actions/repost", methods=["POST"])
def agent_action_repost():
    """
    Repost listing with updated price (top-up ad).
    Payload: { "listing_id": str, "new_price": int, "target_domain": optional str }
    """
    try:
        from app import api_repost_with_new_price
        return api_repost_with_new_price()
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================================
# 5. Purge / Delete Listing
# ============================================================================

@agent_bp.route("/listings/<listing_id>", methods=["DELETE", "POST"])
def agent_delete_listing(listing_id: str):
    """
    Purge listing aggregate from SQLite database.
    Optional query param or json body: delete_photos=true
    """
    try:
        payload = request.json or {}
        delete_photos = bool(payload.get("delete_photos") or request.args.get("delete_photos", "").lower() in ("true", "1"))

        listing = db.get_listing_by_id(listing_id)
        if not listing:
            for item in db.get_all_listings():
                if item.get("local_photos_dir") == listing_id:
                    listing = item
                    listing_id = item.get("id")
                    break

        if not listing:
            return jsonify({"status": "error", "message": f"Listing '{listing_id}' not found"}), 404

        if delete_photos and listing.get("local_photos_dir"):
            from app import safe_delete_photos_dir
            safe_delete_photos_dir(listing["local_photos_dir"])

        db.delete_listing(listing_id)
        return jsonify({
            "status": "success",
            "message": f"Listing '{listing_id}' purged successfully."
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================================
# 6. Market Price Radar Endpoint
# ============================================================================

@agent_bp.route("/radar", methods=["POST"])
def agent_market_radar():
    """
    Query multi-source market radar (Bazoš.cz, Sbazar.cz, Web, Gemini fallback).
    Payload:
    - query or item_name: str (required)
    - brand: str (optional)
    - model: str (optional)
    - condition: str (optional)
    - fallback_price: int (optional)
    """
    try:
        payload = request.json or {}
        item_name = (payload.get("query") or payload.get("item_name") or payload.get("title") or "").strip()
        if not item_name:
            return jsonify({"status": "error", "message": "Missing required parameter 'query' or 'item_name'"}), 400

        brand = (payload.get("brand") or "").strip()
        model = (payload.get("model") or "").strip()
        condition = (payload.get("condition") or "Použité").strip()
        fallback_price = int(payload.get("fallback_price") or 0)

        radar_res = unified_market_price_radar(
            item_name=item_name,
            brand=brand,
            model=model,
            condition=condition,
            fallback_price=fallback_price
        )

        return jsonify({
            "status": "ok",
            "radar": radar_res
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
