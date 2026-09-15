import pytest
from unittest.mock import patch, MagicMock
import urllib.error

from listing_hub.portals.scrapers.universal import (
    parse_views_from_html,
    scrape_listing_views,
    _extract_domain_specific,
    _extract_json_ld,
    _extract_heuristic
)

def test_extract_sportovnivozy():
    url = "https://www.sportovnivozy.cz/254764-volkswagen-arteon"
    html = """
    <div class="content">
        <p style='padding-top: 5px; width: 150px;'>
            <span class='colorSeda3'>Počet zobrazení detailu: <strong>715x</strong></span>
        </p>
    </div>
    """
    assert parse_views_from_html(url, html) == 715

def test_extract_rajveteranu():
    url = "https://www.rajveteranu.cz/12345-skoda-100"
    html = "<span class='colorSeda3'>Počet zobrazení detailu: <strong>142</strong></span>"
    assert parse_views_from_html(url, html) == 142

def test_extract_motorkari():
    url = "https://www.motorkari.cz/motobazar/honda-cb-500.html"
    html = "<div class='info'>Zobrazeno: <strong>320</strong></div>"
    assert parse_views_from_html(url, html) == 320

def test_extract_bazos_fallback():
    url = "https://auto.bazos.cz/inzerat/123456/auto.php"
    html = "<div>Cena: 50 000 Kč<br>Vidělo: 88 lidí</div>"
    assert parse_views_from_html(url, html) == 88

def test_extract_json_ld():
    url = "https://neznamybazar.cz/inzerat/999"
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "Kolo Author",
            "interactionStatistic": {
                "@type": "InteractionCounter",
                "userInteractionCount": 420
            }
        }
        </script>
    </head>
    </html>
    """
    assert parse_views_from_html(url, html) == 420

def test_extract_heuristic_czech():
    url = "https://vlastnibazar.cz/ad/10"
    html = "<div class='stats'>Celkem <strong>158</strong> zhlédnutí inzerátu</div>"
    assert parse_views_from_html(url, html) == 158

def test_extract_heuristic_english():
    url = "https://someportal.com/listing/45"
    html = "<p class='meta'>Views: 995</p>"
    assert parse_views_from_html(url, html) == 995

def test_extract_no_match():
    url = "https://unknown.com/page"
    html = "<html><body><h1>Pouze text bez statistik</h1></body></html>"
    assert parse_views_from_html(url, html) is None
    assert parse_views_from_html(url, "") is None

def test_scrape_listing_views_success():
    url = "https://www.sportovnivozy.cz/254764-arteon"
    mock_response = MagicMock()
    mock_response.headers.get.return_value = "text/html; charset=utf-8"
    mock_response.read.return_value = b"Po\xc4\x8det zobrazen\xc3\xad detailu: <strong>550x</strong>"
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        views = scrape_listing_views(url)
        assert views == 550

def test_scrape_listing_views_network_error():
    url = "https://www.sportovnivozy.cz/broken-link"
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("DNS failure")):
        assert scrape_listing_views(url) is None

def test_scrape_listing_views_non_html_ignored():
    url = "https://example.com/image.png"
    mock_response = MagicMock()
    mock_response.headers.get.return_value = "image/png"
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        assert scrape_listing_views(url) is None

def test_scrape_listing_views_invalid_url():
    assert scrape_listing_views("") is None
    assert scrape_listing_views("ftp://invalid.scheme") is None
    assert scrape_listing_views(None) is None
