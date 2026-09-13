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

BAZOS_ALL_SUBDOMAINS = [
    {"domain": "deti.bazos.cz", "label": "Děti a hračky", "icon": "fa-child"},
    {"domain": "dum.bazos.cz", "label": "Dům a zahrada", "icon": "fa-house-chimney-window"},
    {"domain": "nabytek.bazos.cz", "label": "Nábytek", "icon": "fa-couch"},
    {"domain": "elektro.bazos.cz", "label": "Elektro a spotřebiče", "icon": "fa-bolt"},
    {"domain": "sport.bazos.cz", "label": "Sport a outdoor", "icon": "fa-person-running"},
    {"domain": "auto.bazos.cz", "label": "Auto", "icon": "fa-car"},
    {"domain": "motorky.bazos.cz", "label": "Motorky a čtyřkolky", "icon": "fa-motorcycle"},
    {"domain": "stroje.bazos.cz", "label": "Stroje a dílna", "icon": "fa-gears"},
    {"domain": "pc.bazos.cz", "label": "PC a počítače", "icon": "fa-laptop"},
    {"domain": "mobil.bazos.cz", "label": "Mobily a chytré hodinky", "icon": "fa-mobile-screen"},
    {"domain": "foto.bazos.cz", "label": "Foto a kamery", "icon": "fa-camera"},
    {"domain": "hudba.bazos.cz", "label": "Hudba a nástroje", "icon": "fa-guitar"},
    {"domain": "obleceni.bazos.cz", "label": "Oblečení a obuv", "icon": "fa-shirt"},
    {"domain": "knihy.bazos.cz", "label": "Knihy a časopisy", "icon": "fa-book"},
    {"domain": "zvirata.bazos.cz", "label": "Zvířata a chovatelství", "icon": "fa-paw"},
    {"domain": "vstupenky.bazos.cz", "label": "Vstupenky a lístky", "icon": "fa-ticket"},
    {"domain": "reality.bazos.cz", "label": "Reality a nemovitosti", "icon": "fa-building"},
    {"domain": "prace.bazos.cz", "label": "Práce a brigády", "icon": "fa-briefcase"},
    {"domain": "sluzby.bazos.cz", "label": "Služby a řemesla", "icon": "fa-handshake"},
    {"domain": "ostatni.bazos.cz", "label": "Ostatní", "icon": "fa-box-archive"},
]

DOMAIN_KEYWORDS = {
    "deti.bazos.cz": [
        "plamenak", "hrack", "kocarek", "postylka", "detsk", "odrazedlo", "autosedacka", 
        "plen", "babov", "panenk", "lego", "plysak", "stavebnice", "duplo", "kojeneck",
        "choditko", "nositko", "lehatko detske", "fusak", "detske", "detska", "detsky"
    ],
    "dum.bazos.cz": [
        "sekac", "sekack", "drtic", "stepkov", "zahrada", "zahradni", "vrtack", "pila",
        "krovinorez", "naradi", "gril", "bazen", "cerpadlo", "kotel", "kamna", "dvere",
        "okna", "malotraktor", "kultivator", "vyzinac", "strunovka", "kosa", "hadice",
        "hnojivo", "sklenik", "foliovnik", "plot", "dlazba", "stavebni", "thuje", "rostlin"
    ],
    "nabytek.bazos.cz": [
        "stul", "stoly", "zidle", "skrin", "komoda", "postel", "matrace", "sedacka",
        "pohovka", "kreslo", "stolek", "jidelni", "sedak", "skrinka", "policka", "police",
        "nabytek", "obyvaci", "kuchyn", "linka", "botnik", "regal", "knihovna", "valenda",
        "palanda", "letiste", "satna"
    ],
    "elektro.bazos.cz": [
        "prack", "lednic", "mrazak", "susick", "kavovar", "vysavac", "televiz", "tv",
        "mikrovln", "trouba", "sporak", "mycka", "reproduktor", "repro", "soundbar",
        "mixer", "zehlicka", "ventilator", "klimatizace", "robot"
    ],
    "sport.bazos.cz": [
        "kolo", "horske kolo", "silnicni kolo", "ebike", "elektrokolo", "lyze", "snowboard",
        "fitness", "cinky", "stan", "spacak", "raketa", "brusle", "kolobezka", "paddleboard",
        "surfing", "kajak", "clun", "posilovac", "rotoped", "helma lyzarska"
    ],
    "auto.bazos.cz": [
        "auto", "automobil", "osobni auto", "skoda", "vw", "volkswagen", "audi", "bmw", "ford",
        "peugeot", "renault", "mercedes", "hyundai", "kia", "alu kola", "pneumatiky", "pneu",
        "zimni pneu", "letni pneu", "autodily", "tazne", "stresni box", "r line", "tsi", "tdi"
    ],
    "motorky.bazos.cz": [
        "motorka", "motorky", "motocykl", "skutr", "ctyrkolka", "moped", "enduro",
        "babeta", "babetta", "yamaha", "honda", "suzuki", "kawasaki", "ktm", "pitbike",
        "helma na moto", "moto bunda", "kombineza moto"
    ],
    "stroje.bazos.cz": [
        "soustruh", "frezk", "freza", "vysokozdviz", "traktorbagr", "vzv", "hydraulick",
        "svarecka", "kompresor", "lis", "hoblovka", "protahovacka", "pasova pila", "zetor", "desta"
    ],
    "pc.bazos.cz": [
        "pocitac", "notebook", "laptop", "monitor", "grafick", "rtx", "gtx", "geforce",
        "intel", "amd", "ryzen", "ram", "ssd", "procesor", "zakladni deska", "klavesnice",
        "mys herni", "ipad", "macbook", "imac"
    ],
    "mobil.bazos.cz": [
        "mobil", "telefon", "mobilni telefon", "iphone", "samsung galaxy", "xiaomi",
        "redmi", "smartphone", "smartwatch", "apple watch", "kryt na mobil", "nabijecka"
    ],
    "foto.bazos.cz": [
        "foto", "fotoaparat", "objektiv", "zrcadlovka", "bezzrcadlovka", "canon", "nikon",
        "sony alpha", "fujifilm", "gopro", "stativ", "blesk", "dron", "dji"
    ],
    "hudba.bazos.cz": [
        "kytara", "akusticka kytara", "elektricka kytara", "baskytara", "klavesy", "piano",
        "klavir", "bici", "kombo", "mikrofon", "syntezator", "housle", "akordeon", "harmonika"
    ],
    "obleceni.bazos.cz": [
        "obleceni", "bunda", "kabat", "saty", "sukne", "kalhoty", "dziny", "boty", "tenisky",
        "lodicky", "kabelka", "mikina", "tricko", "svetr", "sako", "oblek"
    ],
    "knihy.bazos.cz": [
        "kniha", "knihy", "roman", "encyklopedie", "ucebnice", "komiks", "casopis", "cteni",
        "sci fi", "fantasy", "knizka", "knizky"
    ],
    "zvirata.bazos.cz": [
        "pes", "fena", "stene", "kocka", "kote", "kun", "akvarium", "terarium", "klec",
        "papousek", "kralik", "morce", "granule", "jezdecke"
    ],
    "vstupenky.bazos.cz": [
        "vstupenk", "listek", "listky", "voucher", "darkovy poukaz", "permanentka",
        "koncert", "festival", "divadlo", "zapas"
    ],
    "reality.bazos.cz": [
        "byt", "byty", "pozemek", "chata", "chalupa", "pronajem", "garaz", "kancelar",
        "nebytovy", "prodej bytu", "najem"
    ],
    "prace.bazos.cz": [
        "prace", "brigada", "zamestnani", "volne misto", "prijmeme", "hpp", "dpp", "mzda",
        "plat", "nastup"
    ],
    "sluzby.bazos.cz": [
        "sluzby", "remeslo", "zednik", "instalater", "stehovani", "rekonstrukce", "doucovani",
        "opravy", "malir", "preprava", "cisteni"
    ],
    "ostatni.bazos.cz": [
        "ostatni", "sberatel", "mince", "bankovky", "znamky", "starozitnost", "vojenske",
        "odznak", "model"
    ]
}

def rank_target_domains(title: str, description: str = "", category: str = "", original_url: str = "") -> list:
    """
    Ohodnotí a seřadí všech 20 subdomén Bazoše podle relevance k inzerátu.
    Vrací seznam dictů seřazených sestupně podle score:
    [{'domain': '...', 'label': '...', 'score': int, 'matched_keywords': list[str], 'icon': '...'}]
    """
    t_norm = normalize_cz(title)
    d_norm = normalize_cz(description)
    c_norm = normalize_cz(category)
    url_lower = (original_url or "").lower()

    # Zjistíme doménu z existující URL
    existing_sub = extract_subdomain(original_url) if original_url else ""
    if existing_sub == "www.bazos.cz":
        existing_sub = ""

    results = []
    for item in BAZOS_ALL_SUBDOMAINS:
        dom = item["domain"]
        lbl = item["label"]
        icon = item.get("icon", "fa-tag")
        score = 0
        matched = []

        # 1. Původní URL je nejsilnější vazba
        if existing_sub and existing_sub == dom:
            score += 1000
            matched.append(f"původní adresa ({dom})")

        # 2. Specifická pravidla pro motorky (aby se nepletly se slovem motor/elektromotor)
        if dom == "motorky.bazos.cz":
            if re.search(r'\b(moto|motorka|motorky|motocykl|skutr|ctyrkolka|moped|enduro|babeta)\b', t_norm):
                score += 120
                matched.append("motocykl/skútr")
        # 3. Kategoriová shoda
        dom_base = dom.split('.')[0]
        if c_norm and dom_base in c_norm:
            score += 80
            matched.append(f"kategorie ({dom_base})")

        # 4. Klíčová slova v titulku (nejvyšší váha) a popisu
        kw_list = DOMAIN_KEYWORDS.get(dom, [])
        for kw in kw_list:
            if kw in t_norm:
                score += 90
                if kw not in matched:
                    matched.append(kw)
            elif kw in d_norm:
                score += 20
                if kw not in matched and len(matched) < 4:
                    matched.append(kw)

        results.append({
            "domain": dom,
            "label": lbl,
            "icon": icon,
            "score": score,
            "matched_keywords": matched
        })

    # Seřadíme sestupně podle skóre
    results.sort(key=lambda x: x["score"], reverse=True)
    return results

def get_target_domain(title: str, original_url: str = "", category: str = "", description: str = "") -> str:
    """Určí cílovou subdoménu Bazoše na základě názvu věci, původní URL, kategorie a popisu."""
    ranked = rank_target_domains(title=title, description=description, category=category, original_url=original_url)
    if ranked and ranked[0]["score"] > 0:
        return ranked[0]["domain"]
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

