import io
import os
import re
import json
import base64
import requests
from typing import List, Dict, Any, Tuple, Optional
from PIL import Image, ImageOps

from listing_hub.ai.gemini import strip_markdown_codeblocks

def prepare_image_for_gemini(image_data: bytes, max_size: Tuple[int, int] = (1280, 1280), quality: int = 80) -> Tuple[str, str]:
    """
    Zpracuje surové bajty obrázku:
    1. Automaticky otočí dle EXIF orientace.
    2. Zmenší rozměry na max_size pro bleskový upload do Gemini API.
    3. Zkomprimuje do JPEG s nastavenou kvalitou.
    4. Vrátí tuple (base64_string, mime_type).
    """
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            img = ImageOps.exif_transpose(img)
            
            # Převedeme do RGB, pokud je např. RGBA nebo Palette
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
                
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=quality, optimize=True)
            jpeg_bytes = output.getvalue()
            b64_str = base64.b64encode(jpeg_bytes).decode("utf-8")
            return b64_str, "image/jpeg"
    except Exception:
        # Fallback na původní bajty bez resize
        b64_str = base64.b64encode(image_data).decode("utf-8")
        return b64_str, "image/jpeg"

def normalize_vision_data(parsed_data: Dict[str, Any], total_photos: int) -> Dict[str, Any]:
    """
    Robustní normalizátor výstupu z Gemini Vision.
    Zajišťuje, že klíčové atributy (item_identification, titles, recommended_title,
    description, category) jsou vždy přítomny a správně naformátovány bez ohledu
    na to, zda model použil česká či anglická synonyma nebo plochou strukturu.
    """
    if not isinstance(parsed_data, dict):
        parsed_data = {}

    # 1. Item identification
    ident = parsed_data.get("item_identification")
    if not isinstance(ident, dict):
        ident = {}

    full_name = (
        ident.get("full_name") or parsed_data.get("full_name") or
        parsed_data.get("item_name") or parsed_data.get("name") or
        parsed_data.get("predmet") or parsed_data.get("nazev") or ""
    )
    brand = ident.get("brand") or parsed_data.get("brand") or parsed_data.get("znacka") or ""
    model = ident.get("model") or parsed_data.get("model") or parsed_data.get("typ") or ""
    condition_cz = (
        ident.get("condition_cz") or ident.get("condition") or
        parsed_data.get("condition_cz") or parsed_data.get("condition") or
        parsed_data.get("stav") or "Zachovalý stav"
    )
    cat_gen = (
        ident.get("category_general") or parsed_data.get("category_general") or
        parsed_data.get("category") or parsed_data.get("kategorie") or "Ostatní"
    )
    accessories = ident.get("accessories") or parsed_data.get("accessories") or parsed_data.get("prislusenstvi") or []
    if isinstance(accessories, str):
        accessories = [accessories]

    if not full_name and (brand or model):
        full_name = f"{brand} {model}".strip()

    parsed_data["item_identification"] = {
        "full_name": full_name,
        "brand": brand,
        "model": model,
        "condition": ident.get("condition") or "used",
        "condition_cz": condition_cz,
        "category_general": cat_gen,
        "accessories": accessories
    }

    # 2. Titles & recommended_title (max 50 chars)
    raw_titles = (
        parsed_data.get("titles") or parsed_data.get("nadpisy") or
        parsed_data.get("navrhy_nadpisu") or parsed_data.get("titulky") or []
    )
    if isinstance(raw_titles, str):
        raw_titles = [raw_titles]

    sanitized_titles = []
    for t in raw_titles:
        if isinstance(t, str) and t.strip():
            t_clean = re.sub(r'^\d+[\.\)\-]\s*', '', t).replace('"', '').replace("'", "").strip()
            if t_clean:
                sanitized_titles.append(t_clean[:50].strip())

    rec_title = (
        parsed_data.get("recommended_title") or parsed_data.get("doporuceny_nadpis") or
        parsed_data.get("title") or parsed_data.get("hlavni_nadpis") or ""
    )
    if rec_title and isinstance(rec_title, str):
        rec_title = rec_title.replace('"', '').replace("'", "").strip()[:50].strip()
    elif sanitized_titles:
        rec_title = sanitized_titles[0]
    elif full_name:
        rec_title = full_name[:50].strip()
    else:
        rec_title = "Inzerát"

    if rec_title and rec_title not in sanitized_titles:
        sanitized_titles.insert(0, rec_title)

    parsed_data["titles"] = sanitized_titles
    parsed_data["recommended_title"] = rec_title

    # 3. Description
    desc = (
        parsed_data.get("description") or parsed_data.get("popis") or
        parsed_data.get("inzerat") or parsed_data.get("text") or
        parsed_data.get("text_inzeratu") or ""
    )
    if not desc and full_name:
        desc = (
            f"Prodám {full_name}.\n\n"
            f"Stav: {condition_cz}.\n\n"
            f"Osobní předání s možností vyzkoušení (České Budějovice a okolí / Rožnov u ČB) nebo bezpečné odeslání přes Zásilkovnu / Balíkovnu."
        )
    parsed_data["description"] = desc

    # 4. Category
    cat = parsed_data.get("category") or parsed_data.get("kategorie") or cat_gen
    parsed_data["category"] = cat

    # 5. Price estimation fallback
    raw_price = (
        parsed_data.get("estimated_price_czk") or parsed_data.get("cena") or
        parsed_data.get("odhad_ceny") or parsed_data.get("price") or 0
    )
    try:
        parsed_data["estimated_price_czk"] = int(float(raw_price))
    except (ValueError, TypeError):
        parsed_data["estimated_price_czk"] = 0

    # 6. Best cover photo index
    cover_idx = parsed_data.get("best_cover_photo_index")
    if cover_idx is None:
        cover_idx = parsed_data.get("photo_recommendations", {}).get("cover_photo_index", 0)
    try:
        cover_idx = int(cover_idx)
        if cover_idx < 0 or cover_idx >= total_photos:
            cover_idx = 0
    except (ValueError, TypeError):
        cover_idx = 0
    parsed_data["best_cover_photo_index"] = cover_idx

    # 7. Photo recommendations / quality tips
    photo_rec = parsed_data.get("photo_recommendations")
    if not isinstance(photo_rec, dict):
        photo_rec = {}
    tips = photo_rec.get("quality_tips") or parsed_data.get("quality_tips") or parsed_data.get("tipy") or []
    if isinstance(tips, str):
        tips = [tips]
    if not tips:
        tips = ["Fotografie jsou ostré a zachycují stav předmětu."]
    photo_rec["quality_tips"] = tips
    photo_rec["cover_photo_index"] = cover_idx
    parsed_data["photo_recommendations"] = photo_rec

    return parsed_data

def analyze_photos_with_vision(
    image_bytes_list: List[bytes],
    user_notes: str = "",
    api_key: str = "",
    run_market_advisor: bool = True,
    model: str = "gemini-2.5-flash"
) -> Tuple[bool, Dict[str, Any], str]:
    """
    Multimodální analýza fotografií předmětu pomocí Gemini Vision API.
    Rozpozná předmět, model, stav, příslušenství, navrhne nadpisy (max 50 znaků),
    vygeneruje přesvědčivý inženýrský popis a volitelně dotáže Bazoš na tržní ceny.
    
    Vrací: (success_bool, result_dict, error_message)
    """
    if not api_key:
        return False, {}, "Chybí Gemini API klíč v nastavení."
        
    model = model or "gemini-2.5-flash"
        
    if not image_bytes_list:
        return False, {}, "Nebyly přiloženy žádné fotografie k analýze."

    system_instruction = (
        "Jsi špičkový expert na oceňování zboží, identifikaci produktů a tvorbu prodejních inzerátů pro inzertní portály Bazoš.cz a Aukro.cz.\n"
        "Tvým úkolem je na základě přiložených fotografií důkladně identifikovat nabízený předmět a sestavit atraktivní, věcný a inženýrsky přesný inzerát.\n\n"
        "STYL A STANDARD PRODEJCE (Rodinná firma TERMS, tradice od 1991):\n"
        "- Piš v perfektní češtině, seriózně, transparentně a srozumitelně.\n"
        "- ŽÁDNÝ MARKETINGOVÝ SLOP: Přísný zákaz frází jako 'NEVÁHEJTE!!', 'TOP STAV!!!', 'SUPER AKCE', 'NEUVĚŘITELNÁ NABÍDKA'.\n"
        "- Uveď pravdivý stav, upozorni na případné viditelné kosmetické vady nebo škrábance (zvyšuje důvěru kupujícího).\n"
        "- Využij odrážky pro technické parametry a obsah balení.\n"
        "- Do popisu vždy zakomponuj standardní možnost předání: 'Osobní předání s možností vyzkoušení (České Budějovice a okolí / Rožnov u ČB) nebo bezpečné odeslání přes Zásilkovnu / Balíkovnu.'\n"
        "- DŮLEŽITÉ: Všechny navržené nadpisy MUSÍ mít maximálně 50 znaků (limit Bazoše)!\n"
        "- Odpověz POUZE jako validní JSON objekt bez dalších textů a kódových bloků.\n\n"
        "POVINNÁ STRUKTURA JSON ODPOVĚDI:\n"
        "{\n"
        '  "item_identification": {\n'
        '    "full_name": "Přesný název předmětu včetně značky a typu (např. Aku vrtačka DeWalt DCD796)",\n'
        '    "brand": "Značka (např. DeWalt)",\n'
        '    "model": "Model / typ (např. DCD796)",\n'
        '    "condition": "used / like_new / for_parts",\n'
        '    "condition_cz": "Zachovalý stav / Jako nový / Plně funkční",\n'
        '    "category_general": "Kategorie (např. Nářadí, Zahrada, Elektronika)",\n'
        '    "accessories": ["nabíječka", "2x baterie", "kufr TSTAK"]\n'
        "  },\n"
        '  "recommended_title": "Hlavní doporučený nadpis (STRIKTNĚ max 50 znaků!)",\n'
        '  "titles": [\n'
        '    "1. atraktivní nadpis (max 50 znaků)",\n'
        '    "2. technický nadpis (max 50 znaků)",\n'
        '    "3. úderný nadpis (max 50 znaků)"\n'
        "  ],\n"
        '  "description": "Kompletní strukturovaný inženýrský popis inzerátu v češtině...",\n'
        '  "category": "Kategorie na Bazoši (např. Nářadí)",\n'
        '  "estimated_price_czk": 2500,\n'
        '  "best_cover_photo_index": 0,\n'
        '  "photo_recommendations": {\n'
        '    "cover_photo_index": 0,\n'
        '    "quality_tips": ["Fotografie jsou ostré a zachycují stav předmětu."]\n'
        "  }\n"
        "}"
    )

    user_prompt = (
        "Důkladně analyzuj tyto fotografie a extrahuj údaje o předmětu do požadovaného JSON formátu:\n"
        "1. Identifikuj značku, přesný model / typové označení (zejména z výrobních štítků či nápisů).\n"
        "2. Vyhodnoť stav předmětu (opotřebení, čistotu, viditelná poškození či zachovalost).\n"
        "3. Zaznamenej všechno viditelné příslušenství (kabely, kufry, nabíječky, adaptéry, baterie, doplňky).\n"
        "4. Navrhni 3 až 5 atraktivních nadpisů (každý STRIKTNĚ max 50 znaků!).\n"
        "5. Sestav kompletní strukturovaný popis připravený k okamžitému vystavení.\n"
        "6. Odhadni férovou tržní cenu v Kč (estimated_price_czk).\n"
        "7. Doporuč index nejlepší titulní fotky (0-indexed; fotka celku s nejlepším úhlem a světlem).\n"
        "8. Přidej doporučení pro prodejce (např. chybějící fotka štítku, nejasný detail)."
    )
    
    if user_notes:
        user_prompt += f"\n\nPoznámka a upřesnění od prodejce k těmto fotkám:\n'{user_notes}'"

    # Sestavíme multimodální obsah (parts)
    contents_parts: List[Dict[str, Any]] = []
    
    # Přidáme optimalizované obrázky
    for idx, img_bytes in enumerate(image_bytes_list[:10]):  # Limit max 10 fotek na jedno volání
        b64_img, mime_type = prepare_image_for_gemini(img_bytes)
        contents_parts.append({
            "inline_data": {
                "mime_type": mime_type,
                "data": b64_img
            }
        })
        
    # Přidáme textový prompt
    contents_parts.append({"text": user_prompt})

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": contents_parts
        }],
        "systemInstruction": {
            "parts": [
                {"text": system_instruction}
            ]
        },
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.2,
            "maxOutputTokens": 4096
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code != 200:
            return False, {}, f"Chyba Gemini Vision API (Status {response.status_code}): {response.text}"
            
        result_json = response.json()
        raw_text = result_json["candidates"][0]["content"]["parts"][0]["text"]
        cleaned_text = strip_markdown_codeblocks(raw_text)
        
        parsed_data = json.loads(cleaned_text)
        parsed_data = normalize_vision_data(parsed_data, len(image_bytes_list))

        # Pokud je zapnutý market advisor, spustíme analýzu Bazoše
        if run_market_advisor:
            search_query = parsed_data.get("item_identification", {}).get("full_name") or \
                           parsed_data.get("item_identification", {}).get("model") or \
                           parsed_data.get("recommended_title", "")
                           
            # Očistíme query pro vyhledávání na Bazoši
            brand = parsed_data.get("item_identification", {}).get("brand", "")
            model = parsed_data.get("item_identification", {}).get("model", "")
            if brand and model:
                search_query = f"{brand} {model}"
            elif not search_query:
                search_query = parsed_data.get("recommended_title", "")[:30]

            if search_query:
                try:
                    from listing_hub.ai.advisor import analyze_bazos_prices
                    market_analysis = analyze_bazos_prices(search_query)
                    parsed_data["market_analysis"] = market_analysis
                except Exception as e:
                    parsed_data["market_analysis"] = {"error": f"Nepodařilo se načíst tržní ceny: {str(e)}"}
                    
        return True, parsed_data, ""
    except json.JSONDecodeError as jde:
        return False, {}, f"Chyba při dekódování JSON z Gemini: {str(jde)}"
    except Exception as e:
        return False, {}, f"Selhala analýza fotografií: {str(e)}"
