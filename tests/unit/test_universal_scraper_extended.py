"""
tests.unit.test_universal_scraper_extended
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Rozšířené testy pro univerzální scraper zhlédnutí inzerátů (listing_hub.portals.scrapers.universal).
Pokrývá:
1. Doménově specifické extraktory (Bazoš CZ/SK, Sbazar, Aukro, Vinted, Sportovní vozy, Ráj veteránů, Motorkáři)
2. JSON-LD / Schema.org mikrodota
3. Heuristické regulární výrazy a oddělovače tisíců
4. Chybové stavy sítě, Content-Type filtraci a timeouty
"""

import pytest
from unittest.mock import patch, MagicMock
import urllib.error

from listing_hub.portals.scrapers.universal import (
    parse_views_from_html,
    scrape_listing_views,
    _extract_domain_specific,
    _extract_json_ld,
    _extract_heuristic,
    _parse_digits_with_separators
)


# --- 1. Doménově specifické extraktory ---

def test_extract_domain_specific_bazos():
    html_cz = '<div class="inzeratyview">Vidělo: <strong>345</strong> lidí</div>'
    html_sk = '<div class="inzeratyview">Videlo: <strong>890</strong> ľudí</div>'
    assert _extract_domain_specific("https://auto.bazos.cz/inzerat/1/auto.php", html_cz) == 345
    assert _extract_domain_specific("https://auto.bazos.sk/inzerat/2/auto.php", html_sk) == 890


def test_extract_domain_specific_sbazar():
    html_json = '<script>window.__INITIAL_DATA__ = {"viewsCount": 1250};</script>'
    assert _extract_domain_specific("https://www.sbazar.cz/inzerat/123-vw-golf", html_json) == 1250

    html_alt = '{"view_count": 480}'
    assert _extract_domain_specific("https://sbazar.cz/inzerat/456", html_alt) == 480

    html_tag = '<p>Zobrazeno: <strong>72</strong></p>'
    assert _extract_domain_specific("https://sbazar.cz/inzerat/789", html_tag) == 72


def test_extract_domain_specific_aukro():
    html_json = '{"viewsCount": 980, "title": "Hodinky"}'
    assert _extract_domain_specific("https://aukro.cz/nabidka/7023849102", html_json) == 980

    html_plain = '<div>15 zobrazení za 24 hodin</div>'
    assert _extract_domain_specific("https://aukro.cz/vintage-123", html_plain) == 15


def test_extract_domain_specific_vinted():
    html_json = '{"item": {"id": 1, "view_count": 312}}'
    assert _extract_domain_specific("https://www.vinted.cz/items/49281-bunda", html_json) == 312

    html_plural = '{"views_count": 654}'
    assert _extract_domain_specific("https://vinted.com/items/8877", html_plural) == 654


def test_extract_domain_specific_sportovnivozy_and_motorkari():
    html_spv = '<p>Počet zobrazení detailu: <strong>1420x</strong></p>'
    assert _extract_domain_specific("https://www.sportovnivozy.cz/12345-porsche", html_spv) == 1420

    html_raj = '<p>180x</strong></span></span></p>'
    assert _extract_domain_specific("https://rajveteranu.cz/678-tatra", html_raj) == 180

    html_moto = '<div>Zhlédnuto: <strong>510</strong></div>'
    assert _extract_domain_specific("https://www.motorkari.cz/motobazar/yamaha", html_moto) == 510


# --- 2. Strukturovaná metadata (Schema.org / JSON-LD) ---

def test_extract_json_ld_interaction_statistic():
    html = """
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Kávovar DeLonghi",
        "interactionStatistic": {
            "@type": "InteractionCounter",
            "interactionType": "https://schema.org/ViewAction",
            "userInteractionCount": 875
        }
    }
    </script>
    """
    assert _extract_json_ld(html) == 875


def test_extract_json_ld_array_structure():
    html = """
    <script type="application/ld+json">
    [
        {"@type": "BreadcrumbList"},
        {
            "@type": "ItemPage",
            "interactionStatistic": [
                {"userInteractionCount": 420}
            ]
        }
    ]
    </script>
    """
    assert _extract_json_ld(html) == 420


def test_extract_json_ld_direct_properties():
    html = '<script type="application/ld+json">{"@type": "NewsArticle", "viewCount": 2300}</script>'
    assert _extract_json_ld(html) == 2300


# --- 3. Univerzální heuristický regex engine ---

def test_parse_digits_with_separators():
    assert _parse_digits_with_separators("1 250") == 1250
    assert _parse_digits_with_separators("1.500") == 1500
    assert _parse_digits_with_separators("1,800") == 1800
    assert _parse_digits_with_separators("45") == 45
    assert _parse_digits_with_separators("") is None
    assert _parse_digits_with_separators(None) is None


def test_extract_heuristic_patterns():
    # České tvary
    assert _extract_heuristic("Počet zobrazení: 1 500") == 1500
    assert _extract_heuristic("Zhlédnuto: 450x") == 450
    assert _extract_heuristic("123 zhlédnutí") == 123
    assert _extract_heuristic("340x zobrazeno") == 340
    assert _extract_heuristic("Vidělo: 88") == 88

    # Anglické tvary
    assert _extract_heuristic("Views: 5 000") == 5000
    assert _extract_heuristic("1,200 impressions") == 1200
    assert _extract_heuristic("pageviews: 950") == 950


def test_parse_views_from_html_pipeline():
    # 1. Zvládne prázdný vstup
    assert parse_views_from_html("https://example.com", "") is None
    assert parse_views_from_html("https://example.com", None) is None

    # 2. Heuristický fallback na neznámém webu
    custom_html = '<div class="stats-box">Počet shlédnutí: 780</div>'
    assert parse_views_from_html("https://muj-bazar.cz/inzerat/1", custom_html) == 780


# --- 4. Síťové volání & Bezpečnostní mechanismy ---

def test_scrape_listing_views_invalid_url():
    assert scrape_listing_views("") is None
    assert scrape_listing_views("   ") is None
    assert scrape_listing_views("ftp://invalid.com") is None
    assert scrape_listing_views("not-a-url") is None


def test_scrape_listing_views_non_html_skipped():
    mock_resp = MagicMock()
    mock_resp.headers = {"Content-Type": "image/jpeg"}
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        assert scrape_listing_views("https://example.com/photo.jpg") is None


def test_scrape_listing_views_network_error_recovery():
    with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("url", 404, "Not Found", {}, None)):
        assert scrape_listing_views("https://example.com/404") is None

    with patch("urllib.request.urlopen", side_effect=TimeoutError("Connection timed out")):
        assert scrape_listing_views("https://example.com/timeout") is None

    with patch("urllib.request.urlopen", side_effect=OSError("Network unreachable")):
        assert scrape_listing_views("https://example.com/down") is None


def test_scrape_listing_views_success_pipeline():
    mock_resp = MagicMock()
    mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
    mock_resp.read.return_value = b'<html><body><div>Zobrazeno: 420x</div></body></html>'
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        views = scrape_listing_views("https://example.com/inzerat/1")
        assert views == 420
