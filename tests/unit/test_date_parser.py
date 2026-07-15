from datetime import datetime, timedelta
import pytest
from listing_hub.portals.bazos.date_parser import parse_bazos_date as parse_date_pkg
from post_to_bazos import parse_bazos_date as parse_date_script

@pytest.mark.parametrize("parse_func", [parse_date_pkg, parse_date_script])
def test_parse_bazos_date(parse_func):
    today_str = datetime.today().strftime("%Y-%m-%d")
    yesterday_str = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    two_days_ago_str = (datetime.today() - timedelta(days=2)).strftime("%Y-%m-%d")
    
    # Test relativních českých dat
    assert parse_func("[Dnes - 12:34]") == today_str
    assert parse_func("[Včera]") == yesterday_str
    assert parse_func("předevčírem") == two_days_ago_str
    assert parse_func("[Předevčírem - 18:00]") == two_days_ago_str
    
    # Test absolutních dat
    assert parse_func("[29.6. 2026]") == "2026-06-29"
    assert parse_func("1.12. 2025") == "2025-12-01"
    assert parse_func("  31.  12.  2024  ") == "2024-12-31"
    
    # Test fallback chování při neplatném datu
    assert parse_func("neplatne_datum") == today_str
    assert parse_func("") == today_str
