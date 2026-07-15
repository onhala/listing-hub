import re

def extract_ad_id(url: str) -> str:
    """Extrahuje ID inzerátu z URL."""
    if not url:
        return None
    match = re.search(r'/inzerat/(\d+)', url)
    if match:
        return match.group(1)
    return None

def extract_subdomain(url: str) -> str:
    """Extrahuje subdoménu (např. dum.bazos.cz nebo nabytek.bazos.cz) z URL."""
    if not url:
        return "dum.bazos.cz"
    match = re.search(r'https://([^/]+)', url)
    if match:
        return match.group(1)
    return "dum.bazos.cz"

def get_target_domain(title: str, original_url: str = "") -> str:
    """Určí cílovou subdoménu Bazoše na základě názvu věci nebo původní URL."""
    if original_url and "nabytek" in original_url:
        return "nabytek.bazos.cz"
    # Fallback podle klíčových slov
    nabytek_keywords = [
        "stůl", "židle", "skříň", "komoda", "postel", "matrace", 
        "sedačka", "pohovka", "křeslo", "stoly", "židle", "nabytek", 
        "jídelní", "sedák"
    ]
    title_lower = title.lower()
    if any(kw in title_lower for kw in nabytek_keywords):
        return "nabytek.bazos.cz"
    return "dum.bazos.cz"
