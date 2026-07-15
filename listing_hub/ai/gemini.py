import requests
import re
from typing import Tuple

def strip_markdown_codeblocks(text: str) -> str:
    """
    Strips unwanted markdown code blocks (e.g., ```html ... ```, ```json ... ```, ``` ...)
    from the beginning and end of the text.
    """
    text = text.strip()
    # Match ```optional_language followed by newline, then content, then closing ```
    match = re.match(r'^```[a-zA-Z0-9_\-+]*\s*\n?(.*?)\n?```$', text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    else:
        # Fallback regex strips if there is leading ```lang or trailing ``` with other text around
        text = re.sub(r'^```[a-zA-Z0-9_\-+]*\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    return text.strip()

def improve_text_with_gemini(text: str, field_type: str, instruction_type: str, api_key: str) -> Tuple[bool, str]:
    """
    Volá Gemini API a optimalizuje text inzerátu podle pokynů.
    Vrací tuple (success_boolean, result_text_or_error_message).
    """
    if not api_key:
        return False, "Chybí Gemini API klíč v nastavení."
        
    system_prompt = (
        "Jsi AI asistent na úpravu prodejních textů pro Bazoš a Aukro.\n"
        "Tvým úkolem je vždy vrátit POUZE upravený/opravený text bez jakýchkoliv dodatečných vysvětlení, "
        "pozdravů, uvozovek nebo komentářů. Vracíš pouze finální text, nic víc.\n\n"
        "DŮLEŽITÉ UPOZORNĚNÍ:\n"
        "- NIKDY neobaluj výsledek do markdown formátování!\n"
        "- Nepoužívej žádné ```markdown, ```html, ```json, ```text ani žádné jiné markdown kódové bloky (```).\n"
        "- Vrať pouze čistý surový text bez jakéhokoliv obalení zpětnými apostrofy (backticks).\n"
        "- Nepoužívej HTML tagy.\n\n"
        "Pokyny pro editaci:\n"
        "- Piš v češtině, jasně, čitelně a srozumitelně.\n"
        "- Používej odrážky pro parametry, stav a výhody.\n"
        "- Nepoužívej přehnané marketingové fráze a 'slop' slova (např. 'neuvěřitelná nabídka', 'jedinečná šance', 'TOP stav!!!').\n"
        "- Působ jako solidní, inženýrsky přesný a férový prodejce (podle standardů rodinné firmy TERMS s tradicí od roku 1991).\n"
        "- Text formátuj přehledně pomocí odstavců a klasických odrážek (např. '*' nebo '-').\n"
        "- Udržuj přibližně stejnou délku a rozsah jako původní text. NIKDY text nezkracuj drasticky a vždy dokonči celé myšlenky i věty.\n"
        "- Ponech všechny věcné parametry (výkon, rozměry, stav, doplňky) a kontaktní/odběrové informace z původního textu."
    )
    
    user_prompt = ""
    if field_type == "title":
        if instruction_type == "title_suggestions":
            user_prompt = f"Navrhni 5 různých atraktivních a chytlavých nadpisů pro inzerát na základě tohoto původního nadpisu: '{text}'. Nadpisy musí mít maximálně 50 znaků. VRAŤ POUZE TĚCHTO 5 NADPISŮ, KAŽDÝ NA NOVÉM ŘÁDKU, BEZ ODPOVĚDI OKOLO, BEZ MARKDOWN FORMÁTOVÁNÍ A KÓDOVÝCH BLOKŮ:"
        else:
            user_prompt = f"Vylepši tento nadpis inzerátu na Bazoš (max 50 znaků). VRAŤ POUZE VÝSLEDNÝ NADPIS BEZ UVOZOWEK, VYSVĚTLENÍ A BEZ MARKDOWN FORMÁTOVÁNÍ/KÓDOVÝCH BLOKŮ:\n\n{text}"
    else:
        if instruction_type == "improve":
            user_prompt = f"Vylepši tón a formátování tohoto popisu inzerátu. Zachovej všechny věcné parametry, doplňky a detaily z původního textu. Délka musí odpovídat původnímu rozsahu. VRAŤ POUZE VYLEPŠENÝ POPIS BEZ KOMENTÁŘŮ A BEZ MARKDOWN FORMÁTOVÁNÍ/KÓDOVÝCH BLOKŮ:\n\n{text}"
        elif instruction_type == "fix":
            user_prompt = f"Oprav gramatiku, překlepy a stylistiku v tomto popisu inzerátu. Zachovej všechny původní parametry a délku. VRAŤ POUZE OPRAVENÝ POPIS BEZ MARKDOWN FORMÁTOVÁNÍ/KÓDOVÝCH BLOKŮ:\n\n{text}"
        elif instruction_type == "shorten":
            user_prompt = f"Zkrať tento popis inzerátu, udělej ho stručný a výstižný, ale zachovej klíčové parametry. VRAŤ POUZE STRUČNÝ POPIS BEZ MARKDOWN FORMÁTOVÁNÍ/KÓDOVÝCH BLOKŮ:\n\n{text}"
        elif instruction_type == "lengthen":
            user_prompt = f"Rozšiř tento popis inzerátu o více detailů a detailní rozbor parametrů. VRAŤ POUZE ROZŠÍŘENÝ POPIS BEZ KOMENTÁŘŮ A BEZ MARKDOWN FORMÁTOVÁNÍ/KÓDOVÝCH BLOKŮ:\n\n{text}"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{
            "parts": [
                {"text": user_prompt}
            ]
        }],
        "systemInstruction": {
            "parts": [
                {"text": system_prompt}
            ]
        },
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 4096
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
        if response.status_code != 200:
            return False, f"Chyba Gemini API (Status {response.status_code}): {response.text}"
            
        result_json = response.json()
        raw_text = result_json["candidates"][0]["content"]["parts"][0]["text"]
        improved_text = strip_markdown_codeblocks(raw_text)
        
        if field_type == "title":
            if instruction_type == "title_suggestions":
                cleaned_lines = []
                for line in improved_text.split("\n"):
                    line_str = line.strip()
                    if not line_str:
                        continue
                    cleaned = re.sub(r'^\d+[\.\)\-]\s*', '', line_str).strip()
                    cleaned_lines.append(cleaned[:50].strip())
                improved_text = "\n".join(cleaned_lines)
            else:
                improved_text = improved_text.replace('"', '').replace("'", "").strip()
                improved_text = improved_text[:50].strip()
                
        return True, improved_text
    except Exception as e:
        return False, f"Selhalo volání Gemini API: {str(e)}"
