import re
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from listing_hub.portals.bazos.date_parser import parse_bazos_date

def scrape_listings_from_html(html_content: str) -> List[Dict[str, Any]]:
    """
    Vyparsuje inzeráty ze stránky Moje inzeráty na Bazoši.
    """
    if not html_content:
        return []
        
    soup = BeautifulSoup(html_content, "html.parser")
    ad_elements = soup.find_all(class_=re.compile(r"\binzeraty\b"))
    
    scraped_listings = []
    
    for el in ad_elements:
        try:
            nadpis_el = el.find(class_="nadpis") or el.find(class_="inzeratynadpis") or el.find("h2")
            if not nadpis_el:
                continue
            a_tags = nadpis_el.find_all("a")
            a_tag = next((a for a in a_tags if a.get_text().strip()), None)
            if not a_tag and a_tags:
                a_tag = a_tags[0]
            if not a_tag:
                continue
                
            title_text = a_tag.get_text().strip()
            ad_url = a_tag.get("href", "").strip()
            
            if ad_url.startswith("//"):
                ad_url = "https:" + ad_url
            elif ad_url.startswith("/"):
                ad_url = "https://www.bazos.cz" + ad_url
            elif not ad_url.startswith("http"):
                ad_url = "https://" + ad_url
                
            cena_el = el.find(class_="inzeratycena")
            price_val = 0
            if cena_el:
                cena_text = cena_el.get_text().replace(" ", "").replace("\xa0", "")
                price_match = re.search(r"(\d+)", cena_text)
                if price_match:
                    price_val = int(price_match.group(1))
                    
            views_el = el.find(class_="inzeratyview")
            views_val = 0
            if views_el:
                views_text = views_el.get_text().replace(" ", "").replace("\xa0", "")
                views_match = re.search(r"(\d+)", views_text)
                if views_match:
                    views_val = int(views_match.group(1))
                    
            date_el = el.find(class_="velikost10")
            date_str = ""
            if date_el:
                date_text = date_el.get_text().strip()
                date_str = parse_bazos_date(date_text)
                
            # --- TOP status ---
            is_top = False
            top_expires_at = None
            top_info = None
            top_count = None
            ztop_el = el.find(class_="ztop")
            if ztop_el:
                is_top = True
                title_attr = ztop_el.get("title", "")
                top_info = title_attr or ztop_el.get_text(strip=True)
                # Parsovat datum expirace: "TOP 1x Platí do 20.9. 2026"
                exp_match = re.search(r"Plat\u00ed do (\d{1,2})\.(\d{1,2})\.\s*(\d{4})", title_attr)
                if exp_match:
                    day, month, year = exp_match.groups()
                    top_expires_at = f"{year}-{int(month):02d}-{int(day):02d}"
                cnt_match = re.search(r"TOP\s*(\d+)x", title_attr)
                if cnt_match:
                    top_count = int(cnt_match.group(1))

            scraped_listings.append({
                "title": title_text,
                "url": ad_url,
                "price": price_val,
                "views": views_val,
                "date_created": date_str,
                "is_top": is_top,
                "top_expires_at": top_expires_at,
                "top_info": top_info,
                "top_count": top_count,
            })
        except Exception:
            continue
            
    return scraped_listings
