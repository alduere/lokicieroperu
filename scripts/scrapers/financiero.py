"""Financial data scraper — USD/PEN from BCRP + mineral prices from yfinance + LME."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
USER_AGENT = "LokicieroPeru/0.1 (+https://github.com/alduere/lokicieroperu)"
BCRP_API_URL = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
BCRP_SERIES = "PD04637PA0"

# Minerals fetched via yfinance
MINERALES_YFINANCE: list[dict[str, str]] = [
    {"nombre": "Cobre", "simbolo": "Cu", "ticker": "HG=F", "unidad": "USD/lb"},
    {"nombre": "Plata", "simbolo": "Ag", "ticker": "SI=F", "unidad": "USD/oz"},
    {"nombre": "Oro", "simbolo": "Au", "ticker": "GC=F", "unidad": "USD/oz"},
]

# Minerals fetched via westmetall.com (LME prices)
MINERALES_LME: list[dict[str, str]] = [
    {"nombre": "Zinc", "simbolo": "Zn", "lme_field": "LME_Zn_cash", "unidad": "USD/mt"},
    {"nombre": "Plomo", "simbolo": "Pb", "lme_field": "LME_Pb_cash", "unidad": "USD/mt"},
]

WESTMETALL_URL = "https://www.westmetall.com/en/markdaten.php"

# How many calendar days back to request in order to guarantee ≥2 business-day values
_BCRP_LOOKBACK_DAYS = 10


def _fetch_bcrp_usd_pen(target: date) -> dict[str, float]:
    """Fetch the USD/PEN exchange rate from the BCRP statistical API.

    Returns:
        {"valor": float, "variacion_pct": float}

    The BCRP series PD04637PA0 contains daily close values.  We request the
    last ``_BCRP_LOOKBACK_DAYS`` calendar days so that we always get at least
    two business-day observations and can compute the daily variation.

    "n.d." (no data) entries are skipped.
    """
    start = target - timedelta(days=_BCRP_LOOKBACK_DAYS)
    url = (
        f"{BCRP_API_URL}/{BCRP_SERIES}/diario"
        f"/{start.strftime('%d%b%Y')}"
        f"/{target.strftime('%d%b%Y')}/json"
    )
    resp = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()

    # Extract numeric values in chronological order, discarding "n.d." entries
    values: list[float] = []
    for period in payload.get("periods", []):
        raw = period.get("values", [None])[0]
        if raw and raw != "n.d.":
            try:
                values.append(float(raw))
            except (TypeError, ValueError):
                logger.debug("BCRP: unparseable value %r — skipping", raw)

    if not values:
        logger.warning("BCRP returned no valid values for %s", target)
        return {"valor": 0.0, "variacion_pct": 0.0}

    valor = values[-1]
    if len(values) >= 2:
        prev = values[-2]
        variacion_pct = round((valor - prev) / prev * 100, 4) if prev else 0.0
    else:
        variacion_pct = 0.0

    return {"valor": round(valor, 4), "variacion_pct": variacion_pct}


def _fetch_yfinance_prices(target: date) -> list[dict[str, Any]]:
    """Fetch closing prices for yfinance-sourced minerals (Cu, Ag, Au)."""
    import yfinance as yf  # lazy import — not always needed in tests

    lookback_start = target - timedelta(days=7)
    end = target + timedelta(days=1)

    results: list[dict[str, Any]] = []

    for mineral in MINERALES_YFINANCE:
        ticker = mineral["ticker"]
        try:
            hist = yf.Ticker(ticker).history(
                start=lookback_start.isoformat(),
                end=end.isoformat(),
            )
            closes = hist["Close"].dropna().tolist()

            if closes:
                valor = round(float(closes[-1]), 4)
                variacion_pct = (
                    round((closes[-1] - closes[-2]) / closes[-2] * 100, 4)
                    if len(closes) >= 2 and closes[-2]
                    else 0.0
                )
            else:
                logger.warning("yfinance: no data for %s on %s", ticker, target)
                valor = 0.0
                variacion_pct = 0.0

        except Exception as exc:  # noqa: BLE001
            logger.error("yfinance fetch failed for %s: %s", ticker, exc)
            valor = 0.0
            variacion_pct = 0.0

        results.append(
            {
                "nombre": mineral["nombre"],
                "simbolo": mineral["simbolo"],
                "ticker": ticker,
                "unidad": mineral["unidad"],
                "valor": valor,
                "variacion_pct": variacion_pct,
            }
        )

    return results


def _fetch_lme_prices() -> list[dict[str, Any]]:
    """Fetch LME cash-settlement prices for Zn and Pb from westmetall.com."""
    results: list[dict[str, Any]] = []

    for mineral in MINERALES_LME:
        lme_field = mineral["lme_field"]
        try:
            resp = requests.get(
                WESTMETALL_URL,
                params={"action": "table", "field": lme_field},
                headers={"User-Agent": USER_AGENT},
                timeout=20,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            tbody = soup.find("tbody")
            if not tbody:
                logger.warning("westmetall: no <tbody> for %s", lme_field)
                results.append(_lme_empty(mineral))
                continue

            rows = tbody.find_all("tr")
            prices: list[float] = []
            for row in rows[:5]:
                cols = row.find_all("td")
                if len(cols) >= 2:
                    raw = cols[1].get_text(strip=True).replace(",", "")
                    try:
                        prices.append(float(raw))
                    except (TypeError, ValueError):
                        continue

            if prices:
                valor = round(prices[0], 2)
                variacion_pct = (
                    round((prices[0] - prices[1]) / prices[1] * 100, 4)
                    if len(prices) >= 2 and prices[1]
                    else 0.0
                )
            else:
                logger.warning("westmetall: no prices parsed for %s", lme_field)
                valor = 0.0
                variacion_pct = 0.0

            results.append(
                {
                    "nombre": mineral["nombre"],
                    "simbolo": mineral["simbolo"],
                    "ticker": lme_field,
                    "unidad": mineral["unidad"],
                    "valor": valor,
                    "variacion_pct": variacion_pct,
                }
            )

        except Exception as exc:  # noqa: BLE001
            logger.error("westmetall fetch failed for %s: %s", lme_field, exc)
            results.append(_lme_empty(mineral))

    return results


def _lme_empty(mineral: dict[str, str]) -> dict[str, Any]:
    return {
        "nombre": mineral["nombre"],
        "simbolo": mineral["simbolo"],
        "ticker": mineral["lme_field"],
        "unidad": mineral["unidad"],
        "valor": 0.0,
        "variacion_pct": 0.0,
    }


def _fetch_mineral_prices(target: date) -> list[dict[str, Any]]:
    """Fetch all mineral prices: yfinance (Cu, Ag, Au) + LME (Zn, Pb)."""
    yf_results = _fetch_yfinance_prices(target)
    lme_results = _fetch_lme_prices()
    return yf_results + lme_results


class FinancieroScraper:
    """Scraper for financial indicators: USD/PEN rate and mineral prices."""

    source_slug = "financiero"

    def scrape_day(self, target: date) -> dict[str, Any]:
        """Scrape financial data for *target* date.

        Returns::

            {
                "fecha": "2026-04-10",
                "usd_pen": {
                    "moneda": "USD/PEN",
                    "valor": 3.75,
                    "variacion_pct": 0.12,
                },
                "minerales": [
                    {
                        "nombre": "Cobre",
                        "simbolo": "Cu",
                        "ticker": "HG=F",
                        "unidad": "USD/lb",
                        "valor": 4.5,
                        "variacion_pct": 0.5,
                    },
                    ...
                ],
            }
        """
        try:
            usd_pen_data = _fetch_bcrp_usd_pen(target)
        except Exception as exc:  # noqa: BLE001
            logger.error("BCRP fetch failed for %s: %s", target, exc)
            usd_pen_data = {"valor": 0.0, "variacion_pct": 0.0}

        try:
            minerales = _fetch_mineral_prices(target)
        except Exception as exc:  # noqa: BLE001
            logger.error("Mineral price fetch failed for %s: %s", target, exc)
            minerales = []

        return {
            "fecha": target.isoformat(),
            "usd_pen": {
                "moneda": "USD/PEN",
                "valor": usd_pen_data["valor"],
                "variacion_pct": usd_pen_data["variacion_pct"],
            },
            "minerales": minerales,
        }
