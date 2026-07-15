import re
from datetime import datetime, timedelta

def parse_bazos_date(date_text: str) -> str:
    """
    Převede české relativní nebo absolutní datum z Bazoše do formátu YYYY-MM-DD.
    Příklady vstupů: '[29.6. 2026]', '[Dnes - 12:34]', '[Včera]', '29.6. 2026'
    """
    try:
        # Odstraníme hranaté závorky
        cleaned = date_text.replace("[", "").replace("]", "").strip()
        cleaned_lower = cleaned.lower()
        
        if "dnes" in cleaned_lower:
            return datetime.today().strftime("%Y-%m-%d")
        elif "včera" in cleaned_lower:
            return (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        elif "předevčírem" in cleaned_lower:
            return (datetime.today() - timedelta(days=2)).strftime("%Y-%m-%d")
            
        # Standardní české datum, např. "29.6. 2026" nebo "29. 6. 2026"
        # Odstraníme mezery za tečkami
        cleaned = re.sub(r'\s+', '', cleaned) # "29.6.2026"
        
        # Extrahujeme pouze "den.měsíc.rok"
        match = re.search(r'(\d+)\.(\d+)\.(\d+)', cleaned)
        if match:
            day = int(match.group(1))
            month = int(match.group(2))
            year = int(match.group(3))
            parsed_date = datetime(year, month, day)
            return parsed_date.strftime("%Y-%m-%d")
    except Exception:
        pass
    # Fallback na dnešní datum, pokud se nepodaří parsovat
    return datetime.today().strftime("%Y-%m-%d")
