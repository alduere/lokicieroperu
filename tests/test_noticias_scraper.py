"""Tests for the multi-source news scraper (RSS + HTML hybrid)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from scripts.scrapers.noticias import (
    RSS_SOURCES,
    NoticiasScraper,
    _make_id,
)


# ---------------------------------------------------------------------------
# Configuration tests
# ---------------------------------------------------------------------------


def test_rss_sources_defined() -> None:
    """RSS_SOURCES must contain gestion, elcomercio, rpp, andina."""
    for fuente in ("gestion", "elcomercio", "rpp", "andina"):
        assert fuente in RSS_SOURCES, f"'{fuente}' not found in RSS_SOURCES"


def test_rss_sources_have_urls() -> None:
    """Every source in RSS_SOURCES must have at least one URL."""
    for fuente, urls in RSS_SOURCES.items():
        assert len(urls) >= 1, f"'{fuente}' has no URLs in RSS_SOURCES"


# ---------------------------------------------------------------------------
# _make_id tests
# ---------------------------------------------------------------------------


def test_make_id_deterministic() -> None:
    """Same inputs must always produce the same ID."""
    id1 = _make_id("gestion", "https://gestion.pe/economia/articulo-123/")
    id2 = _make_id("gestion", "https://gestion.pe/economia/articulo-123/")
    assert id1 == id2


def test_make_id_starts_with_fuente_prefix() -> None:
    """ID must start with '<fuente>-'."""
    result = _make_id("rpp", "https://rpp.pe/economia/noticia-456/")
    assert result.startswith("rpp-")


def test_make_id_different_for_different_urls() -> None:
    """Different URLs must produce different IDs."""
    id1 = _make_id("andina", "https://andina.pe/noticias/articulo-1/")
    id2 = _make_id("andina", "https://andina.pe/noticias/articulo-2/")
    assert id1 != id2


def test_make_id_format() -> None:
    """ID must be '{fuente}-{12 hex chars}' format."""
    result = _make_id("elcomercio", "https://elcomercio.pe/politica/test/")
    parts = result.split("-", 1)
    assert parts[0] == "elcomercio"
    assert len(parts[1]) == 12
    assert all(c in "0123456789abcdef" for c in parts[1])


# ---------------------------------------------------------------------------
# Scraper attribute tests
# ---------------------------------------------------------------------------


def test_scraper_has_correct_slug() -> None:
    """NoticiasScraper.source_slug must equal 'noticias'."""
    scraper = NoticiasScraper()
    assert scraper.source_slug == "noticias"


# ---------------------------------------------------------------------------
# scrape_day structure test
# ---------------------------------------------------------------------------


def test_scrape_day_returns_expected_structure() -> None:
    """scrape_day must return a dict with 'fecha' and 'items' keys."""
    target = date(2026, 4, 10)
    fake_items = [
        {
            "id": "gestion-abc123456789",
            "titulo": "Noticia de prueba",
            "fuente": "gestion",
            "url": "https://gestion.pe/test/",
            "fecha": datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc).isoformat(),
            "contenido": "Resumen de la noticia.",
        }
    ]

    scraper = NoticiasScraper()
    with (
        patch.object(scraper, "_fetch_rss_source", return_value=fake_items),
        patch.object(scraper, "_fetch_bcrp_rss", return_value=[]),
        patch.object(scraper, "_fetch_semana_economica", return_value=[]),
    ):
        result = scraper.scrape_day(target)

    assert "fecha" in result
    assert "items" in result
    assert result["fecha"] == "2026-04-10"
    assert isinstance(result["items"], list)


def test_scrape_day_deduplicates_items() -> None:
    """scrape_day must deduplicate items by id."""
    target = date(2026, 4, 10)
    item = {
        "id": "gestion-abc123456789",
        "titulo": "Noticia duplicada",
        "fuente": "gestion",
        "url": "https://gestion.pe/test/",
        "fecha": datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc).isoformat(),
        "contenido": "Resumen.",
    }
    # Return the same item twice from different source calls
    scraper = NoticiasScraper()
    with (
        patch.object(scraper, "_fetch_rss_source", return_value=[item, item]),
        patch.object(scraper, "_fetch_bcrp_rss", return_value=[]),
        patch.object(scraper, "_fetch_semana_economica", return_value=[]),
    ):
        result = scraper.scrape_day(target)

    # After deduplication, only 1 item should remain
    ids = [i["id"] for i in result["items"]]
    assert len(ids) == len(set(ids))


def test_scrape_day_handles_source_failure() -> None:
    """When a source raises an exception, scrape_day must not crash."""
    target = date(2026, 4, 10)

    scraper = NoticiasScraper()
    with (
        patch.object(
            scraper,
            "_fetch_rss_source",
            side_effect=Exception("Connection error"),
        ),
        patch.object(scraper, "_fetch_bcrp_rss", return_value=[]),
        patch.object(scraper, "_fetch_semana_economica", return_value=[]),
    ):
        # Must not raise
        result = scraper.scrape_day(target)

    assert "fecha" in result
    assert "items" in result


def test_scrape_day_handles_bcrp_failure() -> None:
    """When BCRP RSS raises, scrape_day must not crash."""
    target = date(2026, 4, 10)

    scraper = NoticiasScraper()
    with (
        patch.object(scraper, "_fetch_rss_source", return_value=[]),
        patch.object(
            scraper,
            "_fetch_bcrp_rss",
            side_effect=Exception("BCRP unreachable"),
        ),
        patch.object(scraper, "_fetch_semana_economica", return_value=[]),
    ):
        result = scraper.scrape_day(target)

    assert result["fecha"] == target.isoformat()
    assert isinstance(result["items"], list)


def test_scrape_day_handles_semana_economica_failure() -> None:
    """When Semana Económica scraping raises, scrape_day must not crash."""
    target = date(2026, 4, 10)

    scraper = NoticiasScraper()
    with (
        patch.object(scraper, "_fetch_rss_source", return_value=[]),
        patch.object(scraper, "_fetch_bcrp_rss", return_value=[]),
        patch.object(
            scraper,
            "_fetch_semana_economica",
            side_effect=Exception("SE scrape failed"),
        ),
    ):
        result = scraper.scrape_day(target)

    assert result["fecha"] == target.isoformat()
    assert isinstance(result["items"], list)


def test_scrape_day_items_sorted_by_fecha_desc() -> None:
    """Items must be sorted by 'fecha' in descending order."""
    target = date(2026, 4, 10)
    earlier = {
        "id": "gestion-aaa000000001",
        "titulo": "Noticia antigua",
        "fuente": "gestion",
        "url": "https://gestion.pe/antigua/",
        "fecha": datetime(2026, 4, 10, 8, 0, tzinfo=timezone.utc).isoformat(),
        "contenido": "Antigua.",
    }
    later = {
        "id": "gestion-bbb000000002",
        "titulo": "Noticia nueva",
        "fuente": "gestion",
        "url": "https://gestion.pe/nueva/",
        "fecha": datetime(2026, 4, 10, 16, 0, tzinfo=timezone.utc).isoformat(),
        "contenido": "Nueva.",
    }

    scraper = NoticiasScraper()
    with (
        patch.object(scraper, "_fetch_rss_source", return_value=[earlier, later]),
        patch.object(scraper, "_fetch_bcrp_rss", return_value=[]),
        patch.object(scraper, "_fetch_semana_economica", return_value=[]),
    ):
        result = scraper.scrape_day(target)

    items = result["items"]
    if len(items) >= 2:
        assert items[0]["fecha"] >= items[1]["fecha"]
