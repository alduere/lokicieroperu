"""Tests for the financial data scraper (BCRP + yfinance)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from scripts.scrapers.financiero import (
    MINERALES,
    FinancieroScraper,
    _fetch_bcrp_usd_pen,
    _fetch_mineral_prices,
)


# ---------------------------------------------------------------------------
# Configuration tests
# ---------------------------------------------------------------------------


def test_minerales_config_has_five_entries() -> None:
    """MINERALES must have exactly 5 entries covering Cu, Au, Ag, Zn, Pb."""
    assert len(MINERALES) == 5
    simbolos = {m["simbolo"] for m in MINERALES}
    assert simbolos == {"Cu", "Au", "Ag", "Zn", "Pb"}


def test_scraper_has_correct_slug() -> None:
    """FinancieroScraper.source_slug must equal 'financiero'."""
    scraper = FinancieroScraper()
    assert scraper.source_slug == "financiero"


# ---------------------------------------------------------------------------
# scrape_day structure test
# ---------------------------------------------------------------------------


def test_scrape_day_returns_expected_structure() -> None:
    """scrape_day should return a dict with fecha, usd_pen, and minerales keys."""
    target = date(2026, 4, 10)

    fake_usd_pen = {"valor": 3.75, "variacion_pct": 0.12}
    fake_minerales = [
        {
            "nombre": "Cobre",
            "simbolo": "Cu",
            "ticker": "HG=F",
            "unidad": "USD/lb",
            "valor": 4.5,
            "variacion_pct": 0.5,
        }
    ]

    with (
        patch(
            "scripts.scrapers.financiero._fetch_bcrp_usd_pen",
            return_value=fake_usd_pen,
        ) as mock_bcrp,
        patch(
            "scripts.scrapers.financiero._fetch_mineral_prices",
            return_value=fake_minerales,
        ) as mock_minerales,
    ):
        scraper = FinancieroScraper()
        result = scraper.scrape_day(target)

    mock_bcrp.assert_called_once_with(target)
    mock_minerales.assert_called_once_with(target)

    assert result["fecha"] == "2026-04-10"
    assert result["usd_pen"]["moneda"] == "USD/PEN"
    assert result["usd_pen"]["valor"] == 3.75
    assert result["usd_pen"]["variacion_pct"] == 0.12
    assert result["minerales"] == fake_minerales


# ---------------------------------------------------------------------------
# BCRP failure graceful degradation
# ---------------------------------------------------------------------------


def test_scrape_day_handles_bcrp_failure() -> None:
    """When BCRP fetch raises, scrape_day must still return with 0.0 defaults."""
    target = date(2026, 4, 10)

    fake_minerales: list = []

    with (
        patch(
            "scripts.scrapers.financiero._fetch_bcrp_usd_pen",
            side_effect=Exception("BCRP API unreachable"),
        ),
        patch(
            "scripts.scrapers.financiero._fetch_mineral_prices",
            return_value=fake_minerales,
        ),
    ):
        scraper = FinancieroScraper()
        result = scraper.scrape_day(target)

    assert result["fecha"] == target.isoformat()
    assert result["usd_pen"]["valor"] == 0.0
    assert result["usd_pen"]["variacion_pct"] == 0.0
    assert result["minerales"] == fake_minerales
