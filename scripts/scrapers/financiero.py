"""Financial data scraper — USD/PEN from BCRP + mineral prices from yfinance."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import requests

logger = logging.getLogger(__name__)
USER_AGENT = "LokicieroPeru/0.1 (+https://github.com/alduere/lokicieroperu)"
BCRP_API_URL = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
BCRP_SERIES = "PD04637PA0"

MINERALES: list[dict[str, str]] = [
    {"nombre": "Cobre", "simbolo": "Cu", "ticker": "HG=F", "unidad": "USD/lb"},
    {"nombre": "Plata", "simbolo": "Ag", "ticker": "SI=F", "unidad": "USD/oz"},
    {"nombre": "Zinc", "simbolo": "Zn", "ticker": "ZNC=F", "unidad": "USD/lb"},
    {"nombre": "Plomo", "simbolo": "Pb", "ticker": "PB=F", "unidad": "USD/lb"},
    {"nombre": "Oro", "simbolo": "Au", "ticker": "GC=F", "unidad": "USD/oz"},
]

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


def _fetch_mineral_prices(target: date) -> list[dict[str, Any]]:
    """Fetch closing prices for each mineral in MINERALES using yfinance.

    For each ticker, we request a short recent window to get the last two
    closes and compute the day-over-day variation.  On any failure we
    return ``valor=0.0`` and ``variacion_pct=0.0`` so that one bad ticker
    never breaks the whole run.

    Returns:
        List of dicts with keys: nombre, simbolo, ticker, unidad, valor, variacion_pct
    """
    import yfinance as yf  # lazy import — not always needed in tests

    # Fetch enough history to guarantee ≥2 closes (5 trading days ≈ 7+ calendar)
    lookback_start = target - timedelta(days=7)
    end = target + timedelta(days=1)  # yfinance end is exclusive

    results: list[dict[str, Any]] = []

    for mineral in MINERALES:
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
