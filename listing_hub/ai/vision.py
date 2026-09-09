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

def analyze_photos_with_vision(
    image_bytes_list: List[bytes],
    user_notes: str = "",
    api_key: str = "",
    run_market_advisor: bool = True
) -> Tuple[bool, Dict[str, Any], str]:
    """
    Multimodální analýza fotografií předmětu pomocí Gemini 2.5 Flash.
    Rozpozná předmět, model, stav, příslušenství, navrhne nadpisy (max 50 znaků),
    vygeneruje přesvědčivý inženýrský popis a volitelně dotáže Bazoš na tržní ceny.
    
    Vrací: (success_bool, result_dict, error_message)
    """
    if not api_key:
        return False, {}, "Chybí Gemini API klíč v nastavení."
        
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
        "- Odpověz POUZE jako validní JSON objekt odpovídající specifikované struktuře, bez dalších textů a kódových bloků."
    )

    user_prompt = (
        "Důkladně analyzuj tyto fotografie a extrahuj následující údaje o předmětu:\n"
        "1. Identifikuj značku, přesný model / typové označení (zejména z výrobních štítků či nápisů).\n"
        "2. Vyhodnoť stav předmětu (opotřebení, čistotu, viditelná poškození či zachovalost).\n"
        "3. Zaznamenej všechno viditelné příslušenství (kabely, kufry, nabíječky, adaptéry, baterie, doplňky).\n"
        "4. Navrhni 3 až 5 atraktivních nadpisů (každý STRIKTNĚ max 50 znaků!).\n"
        "5. Sestav kompletní strukturovaný popis připravený k okamžitému vystavení.\n"
        "6. Doporuč index nejlepší titulní fotky (0-indexed; fotka celku s nejlepším úhlem a světlem).\n"
        "7. Přidej doporučení pro prodejce (např. chybějící fotka štítku, nejasný detail)."
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

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
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
        
        # Validace a sanitace nadpisů na max 50 znaků
        titles = parsed_data.get("titles", [])
        sanitized_titles = []
        for t in titles:
            t_clean = t.replace('"', '').replace("'", "").strip()
            sanitized_titles.append(t_clean[:50].strip())
        parsed_data["titles"] = sanitized_titles
        
        rec_title = parsed_data.get("recommended_title", "")
        if rec_title:
            parsed_data["recommended_title"] = rec_title.replace('"', '').replace("'", "").strip()[:50].strip()
        elif sanitized_titles:
            parsed_data["recommended_title"] = sanitized_titles[0]
            
        # Zajištění titulní fotky
        cover_idx = parsed_data.get("best_cover_photo_index", 0)
        if not isinstance(cover_idx, int) or cover_idx < 0 or cover_idx >= len(image_bytes_list):
            parsed_data["best_cover_photo_index"] = 0

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
