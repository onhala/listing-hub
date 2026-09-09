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


def normalize_cz(text: str) -> str:
    """Normalizuje český text (odstraní diakritiku, převede na malá písmena a odstraní speciální znaky)."""
    import unicodedata
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', str(text).lower())
    ascii_text = ''.join(c for c in nfkd if not unicodedata.combining(c))
    cleaned = re.sub(r'[^a-z0-9]', ' ', ascii_text)
    return ' '.join(cleaned.split())


CATEGORY_SYNONYMS = {
    # Dům a zahrada (dum.bazos.cz)
    "technika": ["drtic", "stepkovac", "krovinorez", "vyzinac", "plotostrih", "trakturek", "zahradni", "vetvi"],
    "sekack": ["sekacka", "sekacky", "vyzinac", "strunovka", "strunova", "pojezdem", "travu"],
    "naradi": ["aku", "vrtacka", "bruska", "pila", "kladivo", "sroubovak", "gola", "klice", "sverak", "naradi", "flexa"],
    "pily": ["motorova pila", "retezova pila", "okruzni pila", "pokosova pila", "mafl", "pila", "pily"],
    "grily": ["gril", "udirna", "bbq", "plynovy gril"],
    "bazeny": ["bazen", "virivka", "bazenova", "filtrace", "piskova"],
    "cerpadla": ["cerpadlo", "vodarna", "kalove", "ponorne"],
    "kotle": ["kotel", "kamna", "bojler", "radiator", "kaminka", "topeni", "krb"],
    "dvere": ["dvere", "vrata", "brana", "branka", "plot", "oploceni"],
    "okna": ["okno", "okna", "parapet", "zaluzie"],
    "rostliny": ["rostlina", "thuje", "palma", "stromek", "sazenice"],
    "malotraktory": ["malotraktor", "kultivator", "rotavator", "vari"],
    "stavebni": ["cihly", "dlazba", "beton", "cement", "leseni", "ytong", "polystyren", "prkna", "trubky"],
    
    # Nábytek (nabytek.bazos.cz)
    "stoly": ["stul", "stoly", "stolek", "psaci", "konferencni", "pracovni stul", "jidelni stul"],
    "zidle": ["zidle", "zidli", "sedak", "kreslo", "barovka", "barove"],
    "jidelni": ["jidelni", "jidelna", "kout"],
    "skrine": ["skrin", "skrine", "satni", "komoda", "botnik", "regal", "policka"],
    "postele": ["postel", "postele", "letiste", "palanda", "valenda"],
    "matrace": ["matrace", "rost", "rosty"],
    "sedacky": ["sedacka", "sedaci", "gauc", "pohovka", "kanape"],
    "kresla": ["kreslo", "kresla", "usat", "usakov"],
    "kuchyne": ["kuchyn", "kuchyne", "linka", "drez"],
    "obyvaky": ["obyvaci", "stena"],
    "knihovny": ["knihovna", "police"],
    "zahradni": ["zahradni stul", "zahradni zidle", "zahradni nabytek", "lehatko", "houpacka"],
    
    # Elektro (elektro.bazos.cz)
    "lednic": ["lednice", "chladnicka", "mrazak", "mraznicka", "kombinovana"],
    "prack": ["pracka", "susicka", "pracku"],
    "televiz": ["televize", "televizor", "tv", "smart tv", "oled", "qled"],
    "kavovar": ["kavovar", "espresso", "kapslovy", "kava"],
    "vysavac": ["vysavac", "roboticky"],
    
    # Sport (sport.bazos.cz)
    "kola": ["kolo", "horske", "silnicni", "elektrokolo", "ebike", "bicykl"],
    "lyze": ["lyze", "lyzaky", "snowboard", "bezky", "hulky"],
    "fitness": ["cinky", "rotoped", "lavice", "posilovaci", "hrazda", "pas"],
    
    # Děti (deti.bazos.cz)
    "kocarky": ["kocarek", "kocar", "korba", "golfky"],
    "autosedacky": ["autosedacka", "vajicko", "isofix"],
    "hracky": ["hracka", "lego", "plysak", "stavebnice"],
}


def match_best_category_option(options: list, title: str, description: str = "", category: str = "") -> tuple:
    """
    Vybere nejvhodnější položku z nabídky <option> prvků na základě názvu, popisu a kategorie inzerátu.
    options: seznam dvojic (value, label)
    Vrací: (best_value, best_label, best_score)
    """
    if not options:
        return (None, "", -1)

    t_norm = normalize_cz(title)
    d_norm = normalize_cz(description)
    c_norm = normalize_cz(category)
    t_words = [w for w in t_norm.split() if len(w) >= 3]
    c_words = [w for w in c_norm.split() if len(w) >= 3]

    best_val = None
    best_lbl = ""
    best_score = -1

    for val, label in options:
        if not val or val in ('', '0'):
            continue
        v_norm = normalize_cz(val)
        l_norm = normalize_cz(label)
        score = 0

        # 1. Shoda s názvem inzerátu (nejvyšší priorita)
        if l_norm and l_norm in t_norm:
            score += 100
        for tw in t_words:
            if len(tw) >= 5 and (tw[:5] in l_norm or l_norm.startswith(tw[:5])):
                score += 80
            elif len(tw) >= 4 and (tw[:4] in l_norm or l_norm.startswith(tw[:4])):
                score += 50

        # 2. Synonymická shoda podle klíčových slov v názvu
        for syn_key, syn_words in CATEGORY_SYNONYMS.items():
            if syn_key in v_norm or syn_key in l_norm:
                for sw in syn_words:
                    if sw in t_norm:
                        score += 70
                    if sw in d_norm:
                        score += 20

        # 3. Shoda s kategorií zadanou v systému Listing Hub
        if c_norm and (c_norm in l_norm or l_norm in c_norm):
            score += 40
        for cw in c_words:
            if len(cw) >= 4 and (cw[:4] in l_norm or l_norm.startswith(cw[:4])):
                score += 20

        # 4. Doplňková shoda s popisem
        if l_norm and l_norm in d_norm:
            score += 15

        if score > best_score:
            best_score = score
            best_val = val
            best_lbl = label

    # Pokud žádná možnost nezískala kladné skóre, zkusíme fallback na "ostatni" nebo první neprázdnou
    if (best_val is None or best_score <= 0) and options:
        for val, label in options:
            if val and val not in ('', '0'):
                l_norm = normalize_cz(label)
                if "ostatni" in l_norm or "dalsi" in l_norm:
                    return (val, label, 1)
        # Pokud ani ostatni neexistuje, vrátíme první validní
        for val, label in options:
            if val and val not in ('', '0'):
                return (val, label, 0)

    return (best_val, best_lbl, best_score)

