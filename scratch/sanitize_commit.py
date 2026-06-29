#!/usr/bin/env python3
import os
import sys
from pathlib import Path

def sanitize_file(file_path):
    if not os.path.exists(file_path):
        return
        
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        print(f"Chyba při čtení {file_path}: {e}")
        return

    # Seznam náhrad PII
    replacements = {
        "speedratt@gmail.com": "tuj_email@example.com",
        "775650641": "777123456",
        "+420775650641": "+420777123456",
        "lak0mec": "heslo123",
        "bGFrMG1lYw==": "aGVzbG8xMjM=",  # base64 for lak0mec -> heslo123
        "/Users/ondre/": "/Users/user/",
        "Ondřej H.": "Tvoje Jméno",
        "Ondrej H.": "Tvoje Jméno"
    }

    original_content = content
    for old_val, new_val in replacements.items():
        content = content.replace(old_val, new_val)
        
    if content != original_content:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  Vyčištěn soubor: {file_path}")
        except Exception as e:
            print(f"Chyba při zápisu {file_path}: {e}")

def main():
    # 1. Odstranit bazos_config.json a bazos_active_listings.json (pokud existují)
    for filename in ["bazos_config.json", "bazos_active_listings.json", "bazos_active_listings.json.tmp"]:
        if os.path.exists(filename):
            try:
                os.remove(filename)
                print(f"  Odstraněn soubor z commitu: {filename}")
            except Exception as e:
                print(f"Nelze smazat {filename}: {e}")
                
    # 2. Vyčistit kódové soubory a dokumentaci
    for root, dirs, files in os.walk("."):
        # Vynechat složky .git, .venv, scratch atd.
        if any(ignored in root for filename in files for ignored in [".git", ".venv", "scratch"]):
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            # Čistit pouze textové soubory (kód, md, txt, template)
            if file.endswith((".py", ".md", ".txt", ".json", ".template", ".gitignore")):
                sanitize_file(file_path)

if __name__ == "__main__":
    main()
