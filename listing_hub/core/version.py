"""
listing_hub.core.version
~~~~~~~~~~~~~~~~~~~~~~~~
Správa a zjišťování verze aplikace, lokálního a vzdáleného git commit hashe,
mezipaměť dotazů na GitHub API (ochrana před 60 req/h rate limitem) a generování diff odkazů.
"""
import os
import time
import subprocess
import logging
from typing import Dict, Any, Optional
import requests

logger = logging.getLogger(__name__)

APP_VERSION = "3.8.8"
GITHUB_REPO = "onhala/listing-hub"
CACHE_TTL_SECONDS = 900  # 15 minut mezipaměť pro GitHub API

# Globální paměť pro cache
_version_cache: Dict[str, Any] = {
    "data": None,
    "timestamp": 0
}

def is_docker() -> bool:
    """Detekuje, zda aplikace běží uvnitř Docker kontejneru."""
    return (
        os.path.exists("/.dockerenv")
        or os.environ.get("IS_DOCKER", "").lower() in ("1", "true", "yes")
        or os.environ.get("CONTAINER", "") == "docker"
    )

def get_environment_name() -> str:
    """Vrací lidsky srozumitelný název běhového prostředí."""
    if is_docker():
        if os.environ.get("PUID") == "568" or os.environ.get("TRUENAS_URL"):
            return "Docker (TrueNAS SCALE)"
        return "Docker kontejner"
    return "Lokální vývoj"

def get_local_commit_sha() -> str:
    """
    Zjišťuje lokální commit SHA aplikace s několika stupni fallbacku:
    1. ENV proměnná GIT_COMMIT_SHA (injektováno při docker buildu)
    2. Soubor /app/version.json nebo ./version.json
    3. Příkaz git rev-parse HEAD (pokud běží v repozitáři)
    """
    # 1. ENV proměnná
    sha = os.environ.get("GIT_COMMIT_SHA", "").strip()
    if sha and sha.lower() != "unknown":
        return sha

    # 2. Lokální version.json (pokud existuje)
    for v_path in ("/app/version.json", "version.json"):
        if os.path.isfile(v_path):
            try:
                import json
                with open(v_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    val = data.get("commit_sha") or data.get("sha")
                    if val and val != "unknown":
                        return str(val).strip()
            except Exception as e:
                logger.debug(f"Chyba při čtení {v_path}: {e}")

    # 3. Příkaz git
    try:
        res = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=2,
            text=True
        ).strip()
        if res:
            return res
    except Exception:
        pass

    return "unknown"

def fetch_latest_github_info() -> Dict[str, Any]:
    """Dotáže se GitHub API na nejnovější commit na větvi main."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/commits/main"
    headers = {
        "User-Agent": f"ListingHub/{APP_VERSION}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            commit_data = res.json()
            sha = commit_data.get("sha", "")
            commit_obj = commit_data.get("commit", {})
            msg = commit_obj.get("message", "").strip()
            first_line_msg = msg.split("\n")[0] if msg else ""
            author_date = commit_obj.get("author", {}).get("date", "")
            author_name = commit_obj.get("author", {}).get("name", "")
            html_url = commit_data.get("html_url", f"https://github.com/{GITHUB_REPO}/commit/{sha}")
            
            return {
                "sha": sha,
                "short_sha": sha[:7] if sha else "unknown",
                "message": first_line_msg,
                "date": author_date,
                "author": author_name,
                "url": html_url,
                "rate_limited": False,
                "error": None
            }
        elif res.status_code == 403:
            logger.warning("GitHub API rate limit překročen (HTTP 403).")
            return {
                "sha": "unknown",
                "short_sha": "unknown",
                "message": "Limit požadavků GitHub API byl vyčerpán.",
                "date": "",
                "author": "",
                "url": f"https://github.com/{GITHUB_REPO}",
                "rate_limited": True,
                "error": "Rate limit exceeded"
            }
        else:
            return {
                "sha": "unknown",
                "short_sha": "unknown",
                "message": f"GitHub vrátil stavový kód {res.status_code}",
                "date": "",
                "author": "",
                "url": f"https://github.com/{GITHUB_REPO}",
                "rate_limited": False,
                "error": f"HTTP {res.status_code}"
            }
    except Exception as err:
        logger.warning(f"Chyba při dotazu na GitHub API: {err}")
        return {
            "sha": "unknown",
            "short_sha": "unknown",
            "message": "Nepodařilo se připojit k GitHubu.",
            "date": "",
            "author": "",
            "url": f"https://github.com/{GITHUB_REPO}",
            "rate_limited": False,
            "error": str(err)
        }

def get_version_status(force: bool = False) -> Dict[str, Any]:
    """
    Získá kompletní stav verzí včetně mezipaměti a porovnání.
    """
    now = time.time()
    cached = False
    
    # 1. Zkontrolujeme cache
    if not force and _version_cache["data"] and (now - _version_cache["timestamp"]) < CACHE_TTL_SECONDS:
        result = dict(_version_cache["data"])
        result["cached"] = True
        return result

    # 2. Zjistíme lokální data
    local_sha = get_local_commit_sha()
    local_short_sha = local_sha[:7] if local_sha != "unknown" else "unknown"
    docker_mode = is_docker()
    env_name = get_environment_name()

    # 3. Zjistíme GitHub data
    remote = fetch_latest_github_info()
    
    # Pokud máme rate limit a máme starší cache s platným sha, použijeme starší sha
    if remote.get("rate_limited") and _version_cache["data"]:
        old_remote = _version_cache["data"].get("latest", {})
        if old_remote.get("sha") and old_remote["sha"] != "unknown":
            remote = old_remote
            cached = True

    latest_sha = remote.get("sha", "unknown")
    latest_short_sha = remote.get("short_sha", "unknown")

    # 4. Detekce dostupnosti aktualizace
    update_available = False
    if local_sha != "unknown" and latest_sha != "unknown":
        update_available = (local_sha.lower() != latest_sha.lower())
    
    # Porovnávací URL
    compare_url = None
    if update_available and local_short_sha != "unknown" and latest_short_sha != "unknown":
        compare_url = f"https://github.com/{GITHUB_REPO}/compare/{local_short_sha}...{latest_short_sha}"

    response_data = {
        "status": "success",
        "app_version": APP_VERSION,
        "local": {
            "version": APP_VERSION,
            "hash": local_short_sha,
            "full_hash": local_sha,
            "is_docker": docker_mode,
            "environment": env_name
        },
        "latest": {
            "version": APP_VERSION,
            "hash": latest_short_sha,
            "full_hash": latest_sha,
            "message": remote.get("message", ""),
            "date": remote.get("date", ""),
            "author": remote.get("author", ""),
            "url": remote.get("url", f"https://github.com/{GITHUB_REPO}"),
            "rate_limited": remote.get("rate_limited", False)
        },
        "compare_url": compare_url,
        "update_available": update_available,
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
        "cached": cached,
        # Zpětná kompatibilita pro stávající frontend volání
        "local_hash": local_short_sha,
        "latest_hash": latest_short_sha,
        "latest_message": remote.get("message", ""),
        "is_docker": docker_mode
    }

    # Uložíme do cache
    _version_cache["data"] = response_data
    _version_cache["timestamp"] = now

    return response_data
