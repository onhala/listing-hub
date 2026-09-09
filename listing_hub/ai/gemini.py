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

def clean_bazos_text(text: str) -> str:
    """
    Očistí text inzerátu od markdownu (hvězdičky, tučné písmo, kurzíva).
    Bazoš nepodporuje markdown, takže **text** a *text* působí neprofesionálně a nevzhledně.
    Převádí odrážky na čisté pomlčky ('- ') a odstraňuje veškeré markdown hvězdičky.
    """
    if not text:
        return ""
    
    # 1. Nejprve odstraníme kódové bloky
    text = strip_markdown_codeblocks(text)
    
    # 2. Odstranění markdown tučného písma (**text** nebo __text__) -> text
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    
    # 3. Zpracování po řádcích (odrážky a inline hvězdičky)
    lines = []
    for line in text.splitlines():
        # Odrážka s hvězdičkou nebo puntíkem na začátku řádku -> pomlčka
        cleaned_line = re.sub(r'^\s*[\*\•]\s+', '- ', line)
        # Odstranění kurzívy *text*
        cleaned_line = re.sub(r'(?<!\w)\*([^\*\n]+?)\*(?!\w)', r'\1', cleaned_line)
        # Odstranění osamocených hvězdiček na začátku/konci
        cleaned_line = re.sub(r'^\s*\*+\s*', '', cleaned_line)
        cleaned_line = re.sub(r'\s*\*+\s*$', '', cleaned_line)
        cleaned_line = cleaned_line.replace('**', '').replace('***', '')
        lines.append(cleaned_line)
        
    cleaned_text = "\n".join(lines)
    # Zredukujeme vícenásobné prázdné řádky
    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
    return cleaned_text.strip()

def improve_text_with_gemini(
    text: str,
    field_type: str,
    instruction_type: str,
    api_key: str,
    model: str = "gemini-2.5-flash",
    seller_context: str = ""
) -> Tuple[bool, str]:
    """
    Volá Gemini API a optimalizuje text inzerátu podle pokynů.
    Vrací tuple (success_boolean, result_text_or_error_message).
    """
    if not api_key:
        return False, "Chybí Gemini API klíč v nastavení."
        
    model = model or "gemini-2.5-flash"
    seller_line = seller_context.strip() or "Působ jako solidní, inženýrsky přesný a férový prodejce bez přehnaných marketingových frází a slopu."
        
    system_prompt = (
        "Jsi AI asistent na úpravu prodejních textů pro Bazoš a Aukro.\n"
        "Tvým úkolem je vždy vrátit POUZE upravený/opravený text bez jakýchkoliv dodatečných vysvětlení, "
        "pozdravů, uvozovek nebo komentářů. Vracíš pouze finální text, nic víc.\n\n"
        "DŮLEŽITÉ UPOZORNĚNÍ:\n"
        "- STRIKTNÍ ZÁKAZ POUŽÍVÁNÍ HVĚZDIČEK (*) A MARKDOWNU V TEXTU: Bazoš nepodporuje markdown! Nikdy nepoužívej tučné písmo s hvězdičkami (**text**), kurzívu (*text*) ani odrážky s hvězdičkami (* odrážka).\n"
        "- Nepoužívej žádné ```markdown, ```html, ```json, ```text ani žádné jiné markdown kódové bloky (```).\n"
        "- Vrať pouze čistý surový text bez jakéhokoliv obalení zpětnými apostrofy (backticks).\n"
        "- Nepoužívej HTML tagy.\n\n"
        "Pokyny pro editaci:\n"
        "- Piš v češtině, jasně, čitelně a srozumitelně.\n"
        "- Pro odrážky parametrů a výhod používej výhradně pomlčku s mezerou ('- ').\n"
        "- Pro nadpisy sekcí používej velká písmena bez hvězdiček (např. 'PARAMETRY:', 'STAV:', 'VÝHODY:').\n"
        "- Nepoužívej přehnané marketingové fráze a 'slop' slova (např. 'neuvěřitelná nabídka', 'jedinečná šance', 'TOP stav!!!').\n"
        f"- {seller_line}\n"
        "- Text formátuj přehledně pomocí odstavců a odrážek s pomlčkou ('- ').\n"
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
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
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
        if field_type == "title":
            improved_text = strip_markdown_codeblocks(raw_text)
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
        else:
            improved_text = clean_bazos_text(raw_text)
                
        return True, improved_text
    except Exception as e:
        return False, f"Selhalo volání Gemini API: {str(e)}"
