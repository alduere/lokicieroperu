# Loki-ciero v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebrand to "Loki-ciero" with heraldic Pomeranian logo, add a financial ticker bar (USD/PEN + 5 minerals), and replace the hub homepage with a tabbed news landing page sourcing from 6 Peruvian media outlets.

**Architecture:** The backend adds two new Python scrapers (financiero + noticias) and one new summarizer (noticias) that plug into the existing source registry pipeline. The frontend adds a TickerBar, TabBar, and news listing components to the Astro static site. Data flows: scrape → JSON → summarize → JSON → build.py copies to site/src/data/ → Astro renders statically.

**Tech Stack:** Python 3.11 (requests, feedparser, yfinance, beautifulsoup4, pydantic, google-genai), Astro 5, TailwindCSS 3.4, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-04-12-lokiciero-v2-design.md`

---

## File Structure

### New files

| File | Responsibility |
|------|---------------|
| `scripts/scrapers/financiero.py` | Fetch USD/PEN from BCRP API + mineral prices from yfinance |
| `scripts/scrapers/noticias.py` | Hybrid RSS + HTML scraper for 6 Peruvian news sources |
| `scripts/summarizers/noticias.py` | Gemini-based classification and summarization of news |
| `tests/test_financiero.py` | Unit tests for financial scraper |
| `tests/test_noticias_scraper.py` | Unit tests for news scraper |
| `tests/test_noticias_summarizer.py` | Unit tests for news summarizer |
| `site/src/components/TickerBar.astro` | Financial ticker bar (above masthead) |
| `site/src/components/TabBar.astro` | Top-level tab navigation |
| `site/src/components/NoticiaItem.astro` | Single news item row |
| `site/src/components/FuenteFilter.astro` | Source filter chips |

### Modified files

| File | Change |
|------|--------|
| `pyproject.toml` | Add `feedparser`, `yfinance` dependencies |
| `scripts/lib/schemas.py` | Add `PrensaCruda`, `PrensaResumida`, `DiaPrensa`, `CotizacionMineral`, `CotizacionCambio`, `DatosFinancieros` |
| `scripts/lib/sources.py` | Register `noticias` and `financiero` sources |
| `scripts/build.py` | Sync new source data directories to site |
| `site/src/lib/types.ts` | Add TS interfaces for news + financial data |
| `site/src/lib/data.ts` | Add data loaders for noticias + financiero |
| `site/src/layouts/Base.astro` | Rebrand masthead, add TickerBar + TabBar |
| `site/src/pages/index.astro` | Rewrite as news tab landing page |
| `site/src/styles/global.css` | Add ticker bar + category pill styles |
| `.github/workflows/daily.yml` | Add scrape/summarize steps for noticias + financiero |

---

## Phase 1: Python Backend

### Task 1: Add Python dependencies

**Files:**
- Modify: `pyproject.toml:7-17`

- [ ] **Step 1: Add feedparser and yfinance to dependencies**

```toml
dependencies = [
    "requests>=2.32",
    "beautifulsoup4>=4.12",
    "lxml>=5.2",
    "pydantic>=2.7",
    "google-genai>=0.8",
    "weasyprint>=62",
    "jinja2>=3.1",
    "python-dotenv>=1.0",
    "tenacity>=8.4",
    "feedparser>=6.0",
    "yfinance>=0.2",
]
```

- [ ] **Step 2: Install dependencies**

Run: `cd /home/alduere/notirelevanteperu && uv sync`
Expected: Dependencies resolve and install successfully.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add feedparser and yfinance dependencies"
```

---

### Task 2: Add Pydantic schemas for financial data and press news

**Files:**
- Modify: `scripts/lib/schemas.py` (append after Tribunal Fiscal section, line ~340)

Note: The existing `NoticiaCruda` / `NoticiaResumida` names are used by the consumidor source. The new press news schemas use the prefix `Prensa` to avoid collision.

- [ ] **Step 1: Write tests for new schemas**

Create: `tests/test_schemas_v2.py`

```python
"""Tests for Loki-ciero v2 schemas (financial + press news)."""

from datetime import date, datetime

import pytest

from scripts.lib.schemas import (
    CotizacionCambio,
    CotizacionMineral,
    DatosFinancieros,
    DiaPrensa,
    PrensaCruda,
    PrensaResumida,
)


def test_cotizacion_cambio_basic():
    c = CotizacionCambio(
        moneda="USD/PEN",
        valor=3.72,
        variacion_pct=0.3,
    )
    assert c.moneda == "USD/PEN"
    assert c.valor == 3.72
    assert c.variacion_pct == 0.3


def test_cotizacion_mineral_basic():
    m = CotizacionMineral(
        nombre="Cobre",
        simbolo="Cu",
        precio=4.52,
        unidad="USD/lb",
        variacion_pct=-1.2,
    )
    assert m.simbolo == "Cu"
    assert m.precio == 4.52


def test_datos_financieros_round_trip():
    df = DatosFinancieros(
        fecha=date(2026, 4, 11),
        usd_pen=CotizacionCambio(moneda="USD/PEN", valor=3.72, variacion_pct=0.3),
        minerales=[
            CotizacionMineral(nombre="Cobre", simbolo="Cu", precio=4.52, unidad="USD/lb", variacion_pct=-1.2),
        ],
    )
    data = df.model_dump(mode="json")
    assert data["fecha"] == "2026-04-11"
    assert data["usd_pen"]["valor"] == 3.72
    assert len(data["minerales"]) == 1


def test_prensa_cruda_basic():
    pc = PrensaCruda(
        id="gestion-20260411-001",
        titulo="BCRP mantiene tasa en 4.75%",
        fuente="gestion",
        url="https://gestion.pe/articulo",
        fecha=datetime(2026, 4, 11, 18, 30),
        contenido="El directorio del Banco Central...",
    )
    assert pc.fuente == "gestion"
    assert pc.titulo.startswith("BCRP")


def test_prensa_resumida_basic():
    pr = PrensaResumida(
        id="gestion-20260411-001",
        titulo="BCRP mantiene tasa en 4.75%",
        fuente="gestion",
        fuente_display="Gestión",
        url="https://gestion.pe/articulo",
        fecha=datetime(2026, 4, 11, 18, 30),
        contenido="El directorio del Banco Central...",
        resumen="El BCRP mantuvo la tasa de referencia.",
        categoria="Economía",
        tags=["bcrp", "tasa", "politica monetaria"],
        prompt_version=1,
    )
    assert pr.fuente_display == "Gestión"
    assert pr.categoria == "Economía"
    assert len(pr.tags) == 3


def test_dia_prensa_round_trip():
    dp = DiaPrensa(
        fecha="2026-04-11",
        noticias=[
            PrensaResumida(
                id="gestion-001",
                titulo="Noticia",
                fuente="gestion",
                fuente_display="Gestión",
                url="https://gestion.pe/x",
                fecha=datetime(2026, 4, 11, 10, 0),
                contenido="Texto",
                resumen="Resumen",
                categoria="Economía",
                tags=["tag1"],
                prompt_version=1,
            ),
        ],
        total=1,
        fuentes_activas=["gestion"],
        prompt_version="prensa-v1",
    )
    data = dp.model_dump(mode="json")
    assert data["total"] == 1
    assert data["fuentes_activas"] == ["gestion"]
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `cd /home/alduere/notirelevanteperu && uv run pytest tests/test_schemas_v2.py -v`
Expected: FAIL — `ImportError: cannot import name 'CotizacionCambio'`

- [ ] **Step 3: Add schemas to scripts/lib/schemas.py**

Append after the `TFIndexEntry` class (end of file):

```python
# ── Datos Financieros (tipo de cambio + minerales) ─────────────────────


class CotizacionCambio(BaseModel):
    """Exchange rate quote (e.g. USD/PEN)."""

    moneda: str  # "USD/PEN"
    valor: float
    variacion_pct: float  # % change vs previous day


class CotizacionMineral(BaseModel):
    """Commodity/mineral price quote."""

    nombre: str  # "Cobre", "Plata", etc.
    simbolo: str  # "Cu", "Ag", etc.
    precio: float
    unidad: str  # "USD/lb", "USD/oz"
    variacion_pct: float


class DatosFinancieros(BaseModel):
    """Daily financial data: exchange rate + mineral prices."""

    fecha: date
    usd_pen: CotizacionCambio
    minerales: list[CotizacionMineral]


# ── Noticias de Prensa (multi-source news) ─────────────────────────────

PRENSA_PROMPT_VERSION = "prensa-v1"

# Display name mapping for news sources
FUENTE_DISPLAY: dict[str, str] = {
    "gestion": "Gestión",
    "elcomercio": "El Comercio",
    "rpp": "RPP",
    "andina": "Andina",
    "semanaeconomica": "Semana Económica",
    "bcrp": "BCRP",
}


class PrensaCruda(BaseModel):
    """A news article as fetched from RSS or HTML scraping."""

    id: str
    titulo: str
    fuente: str  # slug: "gestion", "elcomercio", "rpp", "andina", "semanaeconomica", "bcrp"
    url: str
    fecha: datetime
    contenido: str  # full text or excerpt


class PrensaResumida(PrensaCruda):
    """A news article after Gemini summarization."""

    fuente_display: str = ""  # "Gestión", "El Comercio", etc.
    resumen: str | None = None
    categoria: str = "Economía"  # "Economía", "Finanzas", "Política"
    tags: list[str] = Field(default_factory=list)
    prompt_version: str = ""


class DiaPrensa(BaseModel):
    """Processed output for one day of press news."""

    fecha: str
    noticias: list[PrensaResumida]
    total: int
    fuentes_activas: list[str]
    prompt_version: str


class PrensaIndexEntry(BaseModel):
    fecha: date
    total_noticias: int
    fuentes_activas: list[str]
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `cd /home/alduere/notirelevanteperu && uv run pytest tests/test_schemas_v2.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/schemas.py tests/test_schemas_v2.py
git commit -m "feat: add Pydantic schemas for financial data and press news"
```

---

### Task 3: Implement the financial scraper

**Files:**
- Create: `scripts/scrapers/financiero.py`
- Test: `tests/test_financiero.py`

The scraper fetches USD/PEN from the BCRP API and mineral prices from yfinance.

- [ ] **Step 1: Write tests for the financial scraper**

Create: `tests/test_financiero.py`

```python
"""Tests for the financial data scraper."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from scripts.scrapers.financiero import FinancieroScraper, MINERALES


def test_minerales_config_has_five_entries():
    assert len(MINERALES) == 5
    symbols = [m["simbolo"] for m in MINERALES]
    assert "Cu" in symbols
    assert "Au" in symbols
    assert "Ag" in symbols
    assert "Zn" in symbols
    assert "Pb" in symbols


def test_scraper_has_correct_slug():
    s = FinancieroScraper()
    assert s.source_slug == "financiero"


@patch("scripts.scrapers.financiero._fetch_bcrp_usd_pen")
@patch("scripts.scrapers.financiero._fetch_mineral_prices")
def test_scrape_day_returns_expected_structure(mock_minerals, mock_bcrp):
    mock_bcrp.return_value = {"valor": 3.72, "variacion_pct": 0.3}
    mock_minerals.return_value = [
        {"nombre": "Cobre", "simbolo": "Cu", "precio": 4.52, "unidad": "USD/lb", "variacion_pct": -1.2},
    ]

    s = FinancieroScraper()
    result = s.scrape_day(date(2026, 4, 11))

    assert result["fecha"] == "2026-04-11"
    assert result["usd_pen"]["valor"] == 3.72
    assert len(result["minerales"]) == 1
    assert result["minerales"][0]["simbolo"] == "Cu"


@patch("scripts.scrapers.financiero._fetch_bcrp_usd_pen")
@patch("scripts.scrapers.financiero._fetch_mineral_prices")
def test_scrape_day_handles_bcrp_failure(mock_minerals, mock_bcrp):
    mock_bcrp.side_effect = Exception("BCRP API down")
    mock_minerals.return_value = []

    s = FinancieroScraper()
    result = s.scrape_day(date(2026, 4, 11))

    assert result["fecha"] == "2026-04-11"
    assert result["usd_pen"]["valor"] == 0.0
    assert result["usd_pen"]["variacion_pct"] == 0.0
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `cd /home/alduere/notirelevanteperu && uv run pytest tests/test_financiero.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.scrapers.financiero'`

- [ ] **Step 3: Implement the financial scraper**

Create: `scripts/scrapers/financiero.py`

```python
"""Financial data scraper — USD/PEN from BCRP + mineral prices from yfinance.

This scraper does NOT have a summarizer — it produces numeric data that
goes directly to data/processed/financiero/.

Usage:
    uv run python -m scripts.scrape --date 2026-04-11 --source financiero
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import requests

logger = logging.getLogger(__name__)

USER_AGENT = "LokicieroPeru/0.1 (+https://github.com/alduere/lokicieroperu)"

# BCRP API for exchange rate
# Series PD04637PA0 = Tipo de cambio interbancario promedio compra-venta (S/ por US$)
BCRP_API_URL = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
BCRP_SERIES = "PD04637PA0"

# Mineral configuration: name, element symbol, yfinance ticker, unit
MINERALES: list[dict[str, str]] = [
    {"nombre": "Cobre", "simbolo": "Cu", "ticker": "HG=F", "unidad": "USD/lb"},
    {"nombre": "Plata", "simbolo": "Ag", "ticker": "SI=F", "unidad": "USD/oz"},
    {"nombre": "Zinc", "simbolo": "Zn", "ticker": "ZNC=F", "unidad": "USD/lb"},
    {"nombre": "Plomo", "simbolo": "Pb", "ticker": "PB=F", "unidad": "USD/lb"},
    {"nombre": "Oro", "simbolo": "Au", "ticker": "GC=F", "unidad": "USD/oz"},
]


def _fetch_bcrp_usd_pen(target: date) -> dict[str, float]:
    """Fetch USD/PEN exchange rate from BCRP statistical series API.

    Returns dict with 'valor' and 'variacion_pct'.
    """
    # Fetch last 5 business days to compute variation
    start = target - timedelta(days=10)
    url = (
        f"{BCRP_API_URL}/{BCRP_SERIES}/json/"
        f"{start.strftime('%Y-%m-%d')}/{target.strftime('%Y-%m-%d')}"
    )

    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    periods = data.get("periods", [])
    if len(periods) < 1:
        raise ValueError("No exchange rate data returned from BCRP")

    # Get the last two available values
    values = []
    for p in periods:
        for v in p.get("values", []):
            val_str = v.get("value", "").replace(",", "")
            if val_str and val_str != "n.d.":
                values.append(float(val_str))

    if not values:
        raise ValueError("No valid exchange rate values from BCRP")

    current = values[-1]
    previous = values[-2] if len(values) >= 2 else current
    pct = ((current - previous) / previous * 100) if previous else 0.0

    return {"valor": round(current, 4), "variacion_pct": round(pct, 2)}


def _fetch_mineral_prices(target: date) -> list[dict[str, Any]]:
    """Fetch mineral closing prices from yfinance.

    Returns a list of dicts with nombre, simbolo, precio, unidad, variacion_pct.
    """
    import yfinance as yf

    results: list[dict[str, Any]] = []
    # Fetch a few extra days to ensure we get at least 2 closing prices
    start = target - timedelta(days=7)
    end = target + timedelta(days=1)

    for mineral in MINERALES:
        try:
            ticker = yf.Ticker(mineral["ticker"])
            hist = ticker.history(start=start.isoformat(), end=end.isoformat())

            if hist.empty or len(hist) < 1:
                logger.warning("No data for %s (%s)", mineral["nombre"], mineral["ticker"])
                results.append({
                    "nombre": mineral["nombre"],
                    "simbolo": mineral["simbolo"],
                    "precio": 0.0,
                    "unidad": mineral["unidad"],
                    "variacion_pct": 0.0,
                })
                continue

            current = float(hist["Close"].iloc[-1])
            previous = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
            pct = ((current - previous) / previous * 100) if previous else 0.0

            results.append({
                "nombre": mineral["nombre"],
                "simbolo": mineral["simbolo"],
                "precio": round(current, 4),
                "unidad": mineral["unidad"],
                "variacion_pct": round(pct, 2),
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to fetch %s: %s", mineral["nombre"], exc)
            results.append({
                "nombre": mineral["nombre"],
                "simbolo": mineral["simbolo"],
                "precio": 0.0,
                "unidad": mineral["unidad"],
                "variacion_pct": 0.0,
            })

    return results


class FinancieroScraper:
    source_slug = "financiero"

    def scrape_day(self, target: date) -> dict[str, Any]:
        """Fetch financial data for one day.

        Returns a dict with fecha, usd_pen, and minerales.
        The output goes directly to data/processed/ (no summarization needed).
        """
        # Fetch exchange rate
        try:
            usd_pen = _fetch_bcrp_usd_pen(target)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to fetch BCRP exchange rate: %s", exc)
            usd_pen = {"valor": 0.0, "variacion_pct": 0.0}

        # Fetch mineral prices
        minerales = _fetch_mineral_prices(target)

        return {
            "fecha": target.isoformat(),
            "usd_pen": {"moneda": "USD/PEN", **usd_pen},
            "minerales": minerales,
        }
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `cd /home/alduere/notirelevanteperu && uv run pytest tests/test_financiero.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/scrapers/financiero.py tests/test_financiero.py
git commit -m "feat: add financial data scraper (BCRP + yfinance)"
```

---

### Task 4: Implement the news scraper (RSS + HTML hybrid)

**Files:**
- Create: `scripts/scrapers/noticias.py`
- Test: `tests/test_noticias_scraper.py`

- [ ] **Step 1: Write tests for the news scraper**

Create: `tests/test_noticias_scraper.py`

```python
"""Tests for the multi-source news scraper."""

from datetime import date, datetime
from unittest.mock import MagicMock, patch
from xml.etree.ElementTree import Element

import pytest

from scripts.scrapers.noticias import (
    NoticiasScraper,
    RSS_SOURCES,
    _parse_rss_entry,
    _make_id,
)


def test_rss_sources_defined():
    assert "gestion" in RSS_SOURCES
    assert "elcomercio" in RSS_SOURCES
    assert "rpp" in RSS_SOURCES
    assert "andina" in RSS_SOURCES


def test_make_id_deterministic():
    id1 = _make_id("gestion", "https://gestion.pe/articulo-123")
    id2 = _make_id("gestion", "https://gestion.pe/articulo-123")
    assert id1 == id2
    assert id1.startswith("gestion-")


def test_make_id_different_for_different_urls():
    id1 = _make_id("gestion", "https://gestion.pe/articulo-1")
    id2 = _make_id("gestion", "https://gestion.pe/articulo-2")
    assert id1 != id2


def test_scraper_has_correct_slug():
    s = NoticiasScraper()
    assert s.source_slug == "noticias"


@patch("scripts.scrapers.noticias.NoticiasScraper._fetch_rss_source")
def test_scrape_day_returns_expected_structure(mock_fetch):
    mock_fetch.return_value = [
        {
            "id": "gestion-abc123",
            "titulo": "Test article",
            "fuente": "gestion",
            "url": "https://gestion.pe/test",
            "fecha": "2026-04-11T18:30:00",
            "contenido": "Test content",
        }
    ]

    s = NoticiasScraper()
    result = s.scrape_day(date(2026, 4, 11))

    assert result["fecha"] == "2026-04-11"
    assert "items" in result
    assert isinstance(result["items"], list)


@patch("scripts.scrapers.noticias.NoticiasScraper._fetch_rss_source")
def test_scrape_day_handles_source_failure(mock_fetch):
    mock_fetch.side_effect = Exception("RSS timeout")

    s = NoticiasScraper()
    # Should not raise — failures are logged and source is skipped
    result = s.scrape_day(date(2026, 4, 11))

    assert result["fecha"] == "2026-04-11"
    assert isinstance(result["items"], list)
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `cd /home/alduere/notirelevanteperu && uv run pytest tests/test_noticias_scraper.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.scrapers.noticias'`

- [ ] **Step 3: Implement the news scraper**

Create: `scripts/scrapers/noticias.py`

```python
"""Multi-source news scraper — RSS + HTML hybrid.

Sources:
  - Gestión, El Comercio, RPP, Andina: via RSS (feedparser)
  - Semana Económica: via HTML scraping (requests + beautifulsoup4)
  - BCRP: via RSS (comunicados de política monetaria)

Usage:
    uv run python -m scripts.scrape --date 2026-04-11 --source noticias
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import date, datetime, timezone
from typing import Any

import feedparser
import requests
from bs4 import BeautifulSoup

from scripts.lib.schemas import FUENTE_DISPLAY, PrensaCruda

logger = logging.getLogger(__name__)

USER_AGENT = "LokicieroPeru/0.1 (+https://github.com/alduere/lokicieroperu)"
REQUEST_DELAY = 0.5  # politeness between requests
REQUEST_TIMEOUT = 20

# RSS feed URLs per source — economic/financial/political sections
RSS_SOURCES: dict[str, list[str]] = {
    "gestion": [
        "https://gestion.pe/feed/economia/",
        "https://gestion.pe/feed/peru/",
    ],
    "elcomercio": [
        "https://elcomercio.pe/feed/economia/",
        "https://elcomercio.pe/feed/politica/",
    ],
    "rpp": [
        "https://rpp.pe/feed/economia",
    ],
    "andina": [
        "https://andina.pe/agencia/rss/3",  # Economía
        "https://andina.pe/agencia/rss/6",  # Política
    ],
}

# BCRP RSS for official communications
BCRP_RSS_URL = "https://www.bcrp.gob.pe/rss/notas-informativas.xml"


def _make_id(fuente: str, url: str) -> str:
    """Generate a deterministic ID from source + URL."""
    h = hashlib.md5(url.encode(), usedforsecurity=False).hexdigest()[:12]
    return f"{fuente}-{h}"


def _parse_rss_date(entry: dict) -> datetime | None:
    """Parse date from feedparser entry."""
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
        except (ValueError, TypeError):
            pass
    # Fallback: try string parsing
    date_str = entry.get("published") or entry.get("updated", "")
    if date_str:
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    return None


def _parse_rss_entry(entry: dict, fuente: str) -> dict[str, Any] | None:
    """Parse a single RSS feed entry into a raw news dict."""
    titulo = entry.get("title", "").strip()
    link = entry.get("link", "").strip()
    if not titulo or not link:
        return None

    fecha = _parse_rss_date(entry)
    if not fecha:
        return None

    # Extract text content from description/summary
    contenido = ""
    summary = entry.get("summary", "") or entry.get("description", "")
    if summary:
        soup = BeautifulSoup(summary, "lxml")
        contenido = soup.get_text(separator=" ", strip=True)

    return {
        "id": _make_id(fuente, link),
        "titulo": titulo,
        "fuente": fuente,
        "url": link,
        "fecha": fecha.isoformat(),
        "contenido": contenido[:2000],  # cap at 2k chars
    }


class NoticiasScraper:
    source_slug = "noticias"

    def scrape_day(self, target: date) -> dict[str, Any]:
        """Scrape news from all sources for one day.

        Returns dict with fecha + items (list of PrensaCruda dicts).
        """
        all_items: list[dict[str, Any]] = []

        # Fetch RSS sources
        for fuente, urls in RSS_SOURCES.items():
            try:
                items = self._fetch_rss_source(fuente, urls, target)
                all_items.extend(items)
                logger.info("Fetched %d items from %s", len(items), fuente)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to fetch %s: %s", fuente, exc)

        # Fetch BCRP
        try:
            bcrp_items = self._fetch_bcrp_rss(target)
            all_items.extend(bcrp_items)
            logger.info("Fetched %d items from BCRP", len(bcrp_items))
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to fetch BCRP: %s", exc)

        # Fetch Semana Económica (HTML scraping)
        try:
            se_items = self._fetch_semana_economica(target)
            all_items.extend(se_items)
            logger.info("Fetched %d items from Semana Económica", len(se_items))
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to fetch Semana Económica: %s", exc)

        # Deduplicate by id
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for item in all_items:
            if item["id"] not in seen:
                seen.add(item["id"])
                unique.append(item)

        # Sort by fecha descending
        unique.sort(key=lambda x: x.get("fecha", ""), reverse=True)

        logger.info("Total: %d unique news items for %s", len(unique), target.isoformat())

        return {
            "fecha": target.isoformat(),
            "items": unique,
        }

    def _fetch_rss_source(
        self, fuente: str, urls: list[str], target: date
    ) -> list[dict[str, Any]]:
        """Fetch and parse RSS feeds for a single source."""
        items: list[dict[str, Any]] = []

        for url in urls:
            time.sleep(REQUEST_DELAY)
            try:
                feed = feedparser.parse(
                    url,
                    request_headers={"User-Agent": USER_AGENT},
                )
                if feed.bozo and not feed.entries:
                    logger.warning("RSS feed error for %s (%s): %s", fuente, url, feed.bozo_exception)
                    continue

                for entry in feed.entries:
                    parsed = _parse_rss_entry(entry, fuente)
                    if not parsed:
                        continue
                    # Filter to target date (compare date part only)
                    try:
                        entry_date = datetime.fromisoformat(parsed["fecha"]).date()
                    except (ValueError, TypeError):
                        continue
                    if entry_date == target:
                        items.append(parsed)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to parse RSS %s: %s", url, exc)

        return items

    def _fetch_bcrp_rss(self, target: date) -> list[dict[str, Any]]:
        """Fetch BCRP press releases from their RSS feed."""
        time.sleep(REQUEST_DELAY)
        feed = feedparser.parse(
            BCRP_RSS_URL,
            request_headers={"User-Agent": USER_AGENT},
        )

        items: list[dict[str, Any]] = []
        for entry in feed.entries:
            parsed = _parse_rss_entry(entry, "bcrp")
            if not parsed:
                continue
            try:
                entry_date = datetime.fromisoformat(parsed["fecha"]).date()
            except (ValueError, TypeError):
                continue
            if entry_date == target:
                items.append(parsed)

        return items

    def _fetch_semana_economica(self, target: date) -> list[dict[str, Any]]:
        """Scrape Semana Económica homepage for today's articles.

        Semana Económica doesn't have a public RSS feed, so we scrape the
        homepage and extract article links + titles.
        """
        time.sleep(REQUEST_DELAY)
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})

        resp = session.get("https://semanaeconomica.com/", timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        items: list[dict[str, Any]] = []

        # Look for article elements — common patterns in news sites
        for article in soup.select("article, .article-card, .post-card, .story-card"):
            link_el = article.find("a", href=True)
            if not link_el:
                continue

            url = link_el["href"]
            if not url.startswith("http"):
                url = f"https://semanaeconomica.com{url}"

            # Get title
            title_el = article.find(["h1", "h2", "h3", "h4"])
            titulo = title_el.get_text(strip=True) if title_el else link_el.get_text(strip=True)
            if not titulo:
                continue

            # Get excerpt
            excerpt_el = article.find("p")
            contenido = excerpt_el.get_text(strip=True) if excerpt_el else ""

            # We can't reliably get the publish date from the card, so we
            # assume articles on the homepage are from today
            items.append({
                "id": _make_id("semanaeconomica", url),
                "titulo": titulo,
                "fuente": "semanaeconomica",
                "url": url,
                "fecha": datetime(target.year, target.month, target.day, 12, 0, tzinfo=timezone.utc).isoformat(),
                "contenido": contenido[:2000],
            })

        return items
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `cd /home/alduere/notirelevanteperu && uv run pytest tests/test_noticias_scraper.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/scrapers/noticias.py tests/test_noticias_scraper.py
git commit -m "feat: add multi-source news scraper (RSS + HTML hybrid)"
```

---

### Task 5: Implement the news summarizer

**Files:**
- Create: `scripts/summarizers/noticias.py`
- Test: `tests/test_noticias_summarizer.py`

Follows the same pattern as `scripts/summarizers/consumidor.py` but uses the `PrensaCruda` / `PrensaResumida` schemas and classifies by category (Economía/Finanzas/Política).

- [ ] **Step 1: Write tests for the news summarizer**

Create: `tests/test_noticias_summarizer.py`

```python
"""Tests for the press news summarizer."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from scripts.summarizers.noticias import NoticiasSummarizer


def test_summarizer_has_correct_slug():
    s = NoticiasSummarizer()
    assert s.source_slug == "noticias"


def test_empty_day_returns_valid_structure():
    s = NoticiasSummarizer()
    result = s.summarize_day({"fecha": "2026-04-11", "items": []})
    assert result["fecha"] == "2026-04-11"
    assert result["noticias"] == []
    assert result["total"] == 0
    assert result["fuentes_activas"] == []


def test_is_stale_returns_true_for_old_version():
    s = NoticiasSummarizer()
    result = s.is_stale({"noticias": [{"prompt_version": "old-v0"}]})
    assert result is True


def test_is_stale_returns_false_for_current_version():
    from scripts.lib.schemas import PRENSA_PROMPT_VERSION

    s = NoticiasSummarizer()
    result = s.is_stale({"noticias": [{"prompt_version": PRENSA_PROMPT_VERSION}]})
    assert result is False


def test_fallback_returns_unsummarized_item():
    from scripts.lib.schemas import PrensaCruda

    s = NoticiasSummarizer()
    item = PrensaCruda(
        id="test-1",
        titulo="Test",
        fuente="gestion",
        url="https://example.com",
        fecha=datetime(2026, 4, 11, 10, 0),
        contenido="Content",
    )
    result = s._fallback(item)
    assert result.fuente_display == "Gestión"
    assert result.resumen is None
    assert result.prompt_version == ""
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `cd /home/alduere/notirelevanteperu && uv run pytest tests/test_noticias_summarizer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.summarizers.noticias'`

- [ ] **Step 3: Implement the news summarizer**

Create: `scripts/summarizers/noticias.py`

```python
"""Press news summarizer — classifies and summarizes multi-source news.

Uses Gemini to generate: resumen (2-3 sentences), categoria, tags.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any

from scripts.lib.schemas import (
    FUENTE_DISPLAY,
    PRENSA_PROMPT_VERSION,
    DiaPrensa,
    PrensaCruda,
    PrensaIndexEntry,
    PrensaResumida,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres un analista económico y político peruano senior. Clasificas y resumes
noticias económicas, financieras y políticas del Perú para profesionales que
necesitan un resumen ejecutivo rápido.

Para cada noticia devuelves UN objeto con ESTOS campos exactos:

1. id → el id que viene en la entrada, sin modificar.
2. resumen → 2-3 oraciones claras en español peruano. Qué pasó, quién está involucrado,
   por qué importa. NO copies el título. NO uses frases de relleno.
3. categoria → exactamente una de: "Economía", "Finanzas", "Política"
4. tags → 3-5 palabras clave (lowercase, español). Buenos: "tipo de cambio", "bcrp", "minería".
   Malos: "noticia", "perú", "importante".

Devuelve estrictamente {"resultados": [...]} con la misma cantidad y los mismos ids."""

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "resultados": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "resumen": {"type": "string"},
                    "categoria": {"type": "string", "enum": ["Economía", "Finanzas", "Política"]},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "resumen", "categoria", "tags"],
            },
        }
    },
    "required": ["resultados"],
}

BATCH_SIZE = 20


class NoticiasSummarizer:
    source_slug = "noticias"

    def summarize_day(self, parsed_data: dict[str, Any]) -> dict[str, Any]:
        """Summarize press news using Gemini."""
        items_raw = [PrensaCruda(**item) for item in parsed_data["items"]]

        if not items_raw:
            return self._empty_day(parsed_data["fecha"])

        summarized = self._summarize_with_gemini(items_raw)

        fuentes_activas = sorted({n.fuente for n in summarized})
        dia = DiaPrensa(
            fecha=parsed_data["fecha"],
            noticias=summarized,
            total=len(summarized),
            fuentes_activas=fuentes_activas,
            prompt_version=PRENSA_PROMPT_VERSION,
        )
        return dia.model_dump(mode="json")

    def is_stale(self, existing_data: dict[str, Any]) -> bool:
        """Check if existing data needs re-summarization."""
        versions = {
            item.get("prompt_version", "") for item in existing_data.get("noticias", [])
        }
        if not versions:
            return True
        return not all(v == PRENSA_PROMPT_VERSION for v in versions)

    def make_index_entry(self, processed_data: dict[str, Any]) -> dict[str, Any]:
        """Build an index entry from processed data."""
        return PrensaIndexEntry(
            fecha=processed_data["fecha"],
            total_noticias=processed_data.get("total", 0),
            fuentes_activas=processed_data.get("fuentes_activas", []),
        ).model_dump(mode="json")

    def _summarize_with_gemini(
        self, noticias: list[PrensaCruda]
    ) -> list[PrensaResumida]:
        """Run Gemini summarization in batches."""
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not set — returning unsummarized items")
            return [self._fallback(n) for n in noticias]

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        all_results: list[PrensaResumida] = []

        for i in range(0, len(noticias), BATCH_SIZE):
            chunk = noticias[i : i + BATCH_SIZE]
            logger.info(
                "Gemini batch %d/%d — %d news items",
                i // BATCH_SIZE + 1,
                (len(noticias) + BATCH_SIZE - 1) // BATCH_SIZE,
                len(chunk),
            )

            payload = [
                {
                    "id": n.id,
                    "titulo": n.titulo,
                    "fuente": n.fuente,
                    "contenido": n.contenido[:1000],
                }
                for n in chunk
            ]

            prompt = (
                "LOTE DE NOTICIAS A CLASIFICAR Y RESUMIR\n"
                f"Cantidad: {len(payload)}\n\n"
                f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
                'Devuelve {"resultados": [...]} con la misma cantidad y los mismos ids.'
            )

            try:
                resp = client.models.generate_content(
                    model="gemini-2.5-flash-lite",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        response_schema=_RESPONSE_SCHEMA,
                        temperature=0.2,
                        max_output_tokens=16384,
                    ),
                )
                data = json.loads(resp.text or "{}")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Gemini failed for news batch: %s — using fallback", exc)
                all_results.extend(self._fallback(n) for n in chunk)
                continue

            resultados = {r.get("id"): r for r in (data.get("resultados") or [])}
            for n in chunk:
                r = resultados.get(n.id)
                if not r:
                    all_results.append(self._fallback(n))
                    continue
                try:
                    all_results.append(
                        PrensaResumida(
                            **n.model_dump(),
                            fuente_display=FUENTE_DISPLAY.get(n.fuente, n.fuente),
                            resumen=r.get("resumen"),
                            categoria=r.get("categoria", "Economía"),
                            tags=[t.lower().strip() for t in (r.get("tags") or [])][:5],
                            prompt_version=PRENSA_PROMPT_VERSION,
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Could not build summary for %s: %s", n.id, exc)
                    all_results.append(self._fallback(n))

        return all_results

    def _fallback(self, n: PrensaCruda) -> PrensaResumida:
        return PrensaResumida(
            **n.model_dump(),
            fuente_display=FUENTE_DISPLAY.get(n.fuente, n.fuente),
            resumen=None,
            categoria="Economía",
            tags=[],
            prompt_version="",
        )

    def _empty_day(self, fecha: str) -> dict[str, Any]:
        dia = DiaPrensa(
            fecha=fecha,
            noticias=[],
            total=0,
            fuentes_activas=[],
            prompt_version=PRENSA_PROMPT_VERSION,
        )
        return dia.model_dump(mode="json")
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `cd /home/alduere/notirelevanteperu && uv run pytest tests/test_noticias_summarizer.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/summarizers/noticias.py tests/test_noticias_summarizer.py
git commit -m "feat: add press news summarizer (Gemini classification)"
```

---

### Task 6: Register new sources and update build.py

**Files:**
- Modify: `scripts/lib/sources.py:31-93` (add noticias + financiero entries)
- Modify: `scripts/build.py:80-103` (sync financiero data directly to processed)

- [ ] **Step 1: Add noticias and financiero to source registry**

In `scripts/lib/sources.py`, add two new entries to the `SOURCES` dict after the `tribunal-fiscal` entry:

```python
    "noticias": SourceConfig(
        slug="noticias",
        nombre="Noticias",
        subtitulo="Economía, finanzas y política",
        item_label="noticias",
        scraper_cls="scripts.scrapers.noticias.NoticiasScraper",
        summarizer_cls="scripts.summarizers.noticias.NoticiasSummarizer",
        categorias=[
            {"key": "economia", "label": "Economía", "color": "bg-amber-500"},
            {"key": "finanzas", "label": "Finanzas", "color": "bg-green-500"},
            {"key": "politica", "label": "Política", "color": "bg-red-500"},
        ],
    ),
    "financiero": SourceConfig(
        slug="financiero",
        nombre="Datos Financieros",
        subtitulo="Tipo de cambio y minerales",
        item_label="cotizaciones",
        enabled=False,  # no summarizer — only invoked via explicit --source
        scraper_cls="scripts.scrapers.financiero.FinancieroScraper",
        summarizer_cls="",  # no summarizer needed
        categorias=[],
    ),
```

- [ ] **Step 2: Update build.py to handle financiero (no summarization)**

The financiero source outputs its data directly from the scraper — it skips summarization. The `scrape.py` already saves to `data/raw/financiero/<date>/parsed.json`. We need `build.py` to copy this data to `data/processed/financiero/` and then to `site/src/data/financiero/`.

In `scripts/build.py`, add this function after `_sync_site_data()` and call it from `_sync_site_data()`:

```python
def _sync_financiero_data() -> None:
    """Copy raw financiero data directly to processed + site (no summarization)."""
    raw_dir = REPO_ROOT / "data" / "raw" / "financiero"
    processed_dir = DATA_PROCESSED / "financiero"
    site_dir = SITE_DATA / "financiero"

    if not raw_dir.exists():
        return

    processed_dir.mkdir(parents=True, exist_ok=True)
    site_dir.mkdir(parents=True, exist_ok=True)

    for date_dir in raw_dir.iterdir():
        if not date_dir.is_dir():
            continue
        parsed = date_dir / "parsed.json"
        if not parsed.exists():
            continue
        # Copy to processed and site
        date_str = date_dir.name
        shutil.copy2(parsed, processed_dir / f"{date_str}.json")
        shutil.copy2(parsed, site_dir / f"{date_str}.json")

    logger.info("Synced financiero data")
```

Then in `_sync_site_data()`, add before `_generate_hub_summary()`:

```python
    # Sync financiero data (raw → processed → site, no summarization)
    _sync_financiero_data()
```

- [ ] **Step 3: Run existing tests to verify no regressions**

Run: `cd /home/alduere/notirelevanteperu && uv run pytest tests/ -v`
Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add scripts/lib/sources.py scripts/build.py
git commit -m "feat: register noticias + financiero sources, update build pipeline"
```

---

## Phase 2: Astro Frontend

### Task 7: Add TypeScript interfaces for financial + news data

**Files:**
- Modify: `site/src/lib/types.ts` (append new interfaces)

- [ ] **Step 1: Add interfaces to types.ts**

Append at the end of `site/src/lib/types.ts`:

```typescript
// ── Financial data ────────────────────────────────────────────────────

export interface CotizacionCambio {
  moneda: string;
  valor: number;
  variacion_pct: number;
}

export interface CotizacionMineral {
  nombre: string;
  simbolo: string;
  precio: number;
  unidad: string;
  variacion_pct: number;
}

export interface DatosFinancieros {
  fecha: string;
  usd_pen: CotizacionCambio;
  minerales: CotizacionMineral[];
}

// ── Press news ────────────────────────────────────────────────────────

export interface PrensaResumida {
  id: string;
  titulo: string;
  fuente: string;
  fuente_display: string;
  url: string;
  fecha: string;
  contenido: string;
  resumen: string | null;
  categoria: string;
  tags: string[];
  prompt_version: string;
}

export interface DiaPrensa {
  fecha: string;
  noticias: PrensaResumida[];
  total: number;
  fuentes_activas: string[];
  prompt_version: string;
}
```

- [ ] **Step 2: Verify types compile**

Run: `cd /home/alduere/notirelevanteperu/site && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No new errors from these additions.

- [ ] **Step 3: Commit**

```bash
git add site/src/lib/types.ts
git commit -m "feat: add TypeScript interfaces for financial + press news data"
```

---

### Task 8: Add data loaders for noticias + financiero

**Files:**
- Modify: `site/src/lib/data.ts` (append new loaders)

- [ ] **Step 1: Add import of new types at the top of data.ts**

At line 5 of `site/src/lib/data.ts`, add `DiaPrensa, DatosFinancieros` to the import:

```typescript
import type { DiaProcesado, IndexEntry, NormaResumida, HubDay, DiaAlertasProcesado, DiaNoticiasProcesado, DiaGacetaProcesado, DiaTFProcesado, DiaPrensa, DatosFinancieros } from "./types";
```

- [ ] **Step 2: Append data loaders at the end of data.ts**

```typescript
// ── Press news data ───────────────────────────────────────────────────
const prensaModules = import.meta.glob<{ default: DiaPrensa }>(
  "/src/data/noticias/2*-*-*.json",
  { eager: true, import: "default" },
);
export const prensaDays: Record<string, DiaPrensa> = Object.fromEntries(
  Object.entries(prensaModules).map(([path, mod]) => {
    const date = path.split("/").pop()!.replace(".json", "");
    return [date, mod];
  }),
);
export const prensaSortedDates: string[] = Object.keys(prensaDays).sort().reverse();
export function getPrensa(date: string): DiaPrensa | null {
  return prensaDays[date] ?? null;
}
export function latestPrensaDate(): string | null {
  return prensaSortedDates[0] ?? null;
}

// ── Financial data ────────────────────────────────────────────────────
const financieroModules = import.meta.glob<{ default: DatosFinancieros }>(
  "/src/data/financiero/2*-*-*.json",
  { eager: true, import: "default" },
);
export const financieroDays: Record<string, DatosFinancieros> = Object.fromEntries(
  Object.entries(financieroModules).map(([path, mod]) => {
    const date = path.split("/").pop()!.replace(".json", "");
    return [date, mod];
  }),
);
export const financieroSortedDates: string[] = Object.keys(financieroDays).sort().reverse();
export function getFinanciero(date: string): DatosFinancieros | null {
  return financieroDays[date] ?? null;
}
export function latestFinancieroDate(): string | null {
  return financieroSortedDates[0] ?? null;
}
```

- [ ] **Step 3: Commit**

```bash
git add site/src/lib/data.ts
git commit -m "feat: add Astro data loaders for press news + financial data"
```

---

### Task 9: Create TickerBar component

**Files:**
- Create: `site/src/components/TickerBar.astro`
- Modify: `site/src/styles/global.css` (add ticker styles)

- [ ] **Step 1: Create TickerBar.astro**

```astro
---
import { latestFinancieroDate, getFinanciero } from "../lib/data";
import type { DatosFinancieros } from "../lib/types";

const date = latestFinancieroDate();
const data: DatosFinancieros | null = date ? getFinanciero(date) : null;
---

{data && (
  <div class="ticker-bar">
    <div class="max-w-5xl mx-auto px-4 sm:px-6 flex items-center gap-3 sm:gap-4 overflow-x-auto">
      {/* USD/PEN */}
      <span class="ticker-label">USD/PEN</span>
      <span class="ticker-value">
        S/ {data.usd_pen.valor.toFixed(2)}
        <span class={data.usd_pen.variacion_pct >= 0 ? "ticker-up" : "ticker-down"}>
          {data.usd_pen.variacion_pct >= 0 ? "▲" : "▼"} {Math.abs(data.usd_pen.variacion_pct).toFixed(1)}%
        </span>
      </span>
      <span class="ticker-sep">|</span>
      {/* Minerals */}
      {data.minerales.map((m, i) => (
        <>
          <span class="ticker-label">{m.simbolo}</span>
          <span class="ticker-value">
            ${m.precio.toFixed(2)}/{m.unidad.split("/")[1]}
            {m.precio > 0 && (
              <span class={m.variacion_pct >= 0 ? "ticker-up" : "ticker-down"}>
                {m.variacion_pct >= 0 ? "▲" : "▼"} {Math.abs(m.variacion_pct).toFixed(1)}%
              </span>
            )}
          </span>
          {i < data.minerales.length - 1 && <span class="ticker-sep">|</span>}
        </>
      ))}
    </div>
  </div>
)}
```

- [ ] **Step 2: Add ticker styles to global.css**

Append inside the `@layer components` block in `site/src/styles/global.css`:

```css
  /* ═══ FINANCIAL TICKER BAR ═══ */
  .ticker-bar {
    @apply py-1.5;
    background: #e8e0d0;
    border-bottom: 1px solid theme("colors.ink.rule");
    font-family: theme("fontFamily.mono");
    font-size: 11px;
    white-space: nowrap;
  }
  .ticker-label {
    font-weight: 700;
    color: theme("colors.ink.DEFAULT");
  }
  .ticker-value {
    color: theme("colors.ink.light");
  }
  .ticker-sep {
    color: theme("colors.ink.rule");
  }
  .ticker-up {
    color: theme("colors.impact.bajo");
    font-size: 9px;
    margin-left: 2px;
  }
  .ticker-down {
    color: theme("colors.impact.alto");
    font-size: 9px;
    margin-left: 2px;
  }
```

- [ ] **Step 3: Commit**

```bash
git add site/src/components/TickerBar.astro site/src/styles/global.css
git commit -m "feat: add TickerBar component with financial data"
```

---

### Task 10: Create TabBar component

**Files:**
- Create: `site/src/components/TabBar.astro`

- [ ] **Step 1: Create TabBar.astro**

```astro
---
interface Props {
  active: string;
}

const { active } = Astro.props;
const base = import.meta.env.BASE_URL.replace(/\/$/, "");

const tabs = [
  { label: "Noticias", href: `${base}/`, slug: "noticias" },
  { label: "El Peruano", href: `${base}/elperuano/`, slug: "elperuano" },
  { label: "INDECOPI", href: `${base}/indecopi/`, slug: "indecopi" },
  { label: "Tribunal Fiscal", href: `${base}/tribunal-fiscal/`, slug: "tribunal-fiscal" },
];
---

<nav class="border-b border-ink-rule bg-parchment">
  <div class="max-w-5xl mx-auto px-4 sm:px-6 flex gap-0 overflow-x-auto">
    {tabs.map((tab) => (
      <a
        href={tab.href}
        class:list={["source-tab", { active: active === tab.slug }]}
      >
        {tab.label}
      </a>
    ))}
  </div>
</nav>
```

- [ ] **Step 2: Commit**

```bash
git add site/src/components/TabBar.astro
git commit -m "feat: add TabBar navigation component"
```

---

### Task 11: Create NoticiaItem and FuenteFilter components

**Files:**
- Create: `site/src/components/NoticiaItem.astro`
- Create: `site/src/components/FuenteFilter.astro`

- [ ] **Step 1: Create NoticiaItem.astro**

```astro
---
import type { PrensaResumida } from "../lib/types";

interface Props {
  noticia: PrensaResumida;
}

const { noticia } = Astro.props;

const categoriaColors: Record<string, string> = {
  "Economía": "bg-amber-600",
  "Finanzas": "bg-green-700",
  "Política": "bg-red-700",
};
const bgClass = categoriaColors[noticia.categoria] || "bg-gray-500";

function formatFechaCorta(isoDate: string): string {
  try {
    const d = new Date(isoDate);
    const meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
    const h = d.getHours().toString().padStart(2, "0");
    const m = d.getMinutes().toString().padStart(2, "0");
    return `${d.getDate()} ${meses[d.getMonth()]} ${d.getFullYear()}, ${h}:${m}`;
  } catch {
    return isoDate;
  }
}
---

<a
  href={noticia.url}
  target="_blank"
  rel="noopener noreferrer"
  class="ruled-item block"
  data-fuente={noticia.fuente}
>
  <div class="flex items-center gap-2 mb-1">
    <span class={`inline-block px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white rounded-sm ${bgClass}`}>
      {noticia.categoria}
    </span>
    <span class="text-[11px] text-ink-sepia font-sans">
      {noticia.fuente_display} &middot; {formatFechaCorta(noticia.fecha)}
    </span>
  </div>
  <div class="font-display font-bold text-ink leading-snug text-[17px] mb-1">
    {noticia.titulo}
  </div>
  {noticia.resumen && (
    <p class="text-sm text-ink-light leading-relaxed line-clamp-2">
      {noticia.resumen}
    </p>
  )}
</a>
```

- [ ] **Step 2: Create FuenteFilter.astro**

```astro
---
interface Props {
  fuentes: string[];
  fuenteDisplayMap: Record<string, string>;
}

const { fuentes, fuenteDisplayMap } = Astro.props;
---

<div class="flex gap-2 flex-wrap py-3 border-b border-ink-rule-light" id="fuente-filter">
  <button
    class="fuente-chip active"
    data-fuente="all"
  >
    Todas
  </button>
  {fuentes.map((f) => (
    <button
      class="fuente-chip"
      data-fuente={f}
    >
      {fuenteDisplayMap[f] || f}
    </button>
  ))}
</div>

<style>
  .fuente-chip {
    @apply px-3 py-1 text-xs font-semibold border rounded-sm cursor-pointer transition-all;
    color: theme("colors.ink.sepia");
    border-color: theme("colors.ink.rule");
    background: transparent;
  }
  .fuente-chip:hover {
    color: theme("colors.ink.DEFAULT");
    border-color: theme("colors.ink.light");
  }
  .fuente-chip.active {
    color: theme("colors.parchment.light");
    background: theme("colors.ink.DEFAULT");
    border-color: theme("colors.ink.DEFAULT");
  }
</style>

<script>
  document.addEventListener("DOMContentLoaded", () => {
    const chips = document.querySelectorAll<HTMLButtonElement>(".fuente-chip");
    const items = document.querySelectorAll<HTMLElement>(".ruled-item[data-fuente]");

    chips.forEach((chip) => {
      chip.addEventListener("click", () => {
        const fuente = chip.dataset.fuente;
        chips.forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");

        items.forEach((item) => {
          if (fuente === "all" || item.dataset.fuente === fuente) {
            item.style.display = "";
            item.style.animation = "fadeUp 0.3s cubic-bezier(0.22, 1, 0.36, 1) both";
          } else {
            item.style.display = "none";
          }
        });
      });
    });
  });
</script>
```

- [ ] **Step 3: Commit**

```bash
git add site/src/components/NoticiaItem.astro site/src/components/FuenteFilter.astro
git commit -m "feat: add NoticiaItem and FuenteFilter components"
```

---

### Task 12: Rebrand masthead in Base.astro

**Files:**
- Modify: `site/src/layouts/Base.astro`

This task replaces the masthead with the heraldic Pomeranian SVG logo + "Loki-ciero" text (no subtitle), adds the TickerBar above the masthead, and replaces the existing tab bars with the new TabBar component.

- [ ] **Step 1: Add TickerBar and TabBar imports**

At the top of Base.astro frontmatter (after the existing import), add:

```astro
import TickerBar from "../components/TickerBar.astro";
import TabBar from "../components/TabBar.astro";
```

- [ ] **Step 2: Add TickerBar above the header**

Insert `<TickerBar />` immediately before the `<header>` tag (before line 41).

- [ ] **Step 3: Replace the masthead logo block**

Replace the existing masthead inner content (the `<a>` tag with the LK square + "Loki-ciero Perú" text, lines 50-58) with:

```astro
          <a href={`${base}/`} class="flex items-center gap-3 group">
            <svg viewBox="0 0 48 48" class="w-10 h-10 flex-shrink-0" aria-label="Loki-ciero logo">
              <!-- Heraldic Pomeranian in engraving style -->
              <circle cx="24" cy="24" r="22" fill="none" stroke="#2c1810" stroke-width="1.5"/>
              <circle cx="24" cy="24" r="20" fill="none" stroke="#2c1810" stroke-width="0.5"/>
              <!-- Head -->
              <ellipse cx="24" cy="17" rx="7" ry="6.5" fill="none" stroke="#2c1810" stroke-width="1.2"/>
              <!-- Ears -->
              <path d="M17.5 14 L14 8 L19 12.5" fill="none" stroke="#2c1810" stroke-width="1" stroke-linejoin="round"/>
              <path d="M30.5 14 L34 8 L29 12.5" fill="none" stroke="#2c1810" stroke-width="1" stroke-linejoin="round"/>
              <!-- Eyes -->
              <circle cx="21" cy="15.5" r="1" fill="#2c1810"/>
              <circle cx="27" cy="15.5" r="1" fill="#2c1810"/>
              <!-- Nose -->
              <ellipse cx="24" cy="18.5" rx="1.2" ry="0.8" fill="#2c1810"/>
              <!-- Muzzle smile -->
              <path d="M22 19.5 Q24 21.5 26 19.5" fill="none" stroke="#2c1810" stroke-width="0.7"/>
              <!-- Fluffy collar/mane -->
              <path d="M16 20 Q14 24 16 28" fill="none" stroke="#2c1810" stroke-width="0.8"/>
              <path d="M32 20 Q34 24 32 28" fill="none" stroke="#2c1810" stroke-width="0.8"/>
              <path d="M17 21 Q15 24.5 17 27.5" fill="none" stroke="#2c1810" stroke-width="0.5"/>
              <path d="M31 21 Q33 24.5 31 27.5" fill="none" stroke="#2c1810" stroke-width="0.5"/>
              <!-- Body -->
              <ellipse cx="24" cy="30" rx="8" ry="6" fill="none" stroke="#2c1810" stroke-width="1.2"/>
              <!-- Legs -->
              <path d="M19 34 L18 39" stroke="#2c1810" stroke-width="1" stroke-linecap="round"/>
              <path d="M29 34 L30 39" stroke="#2c1810" stroke-width="1" stroke-linecap="round"/>
              <!-- Tail (fluffy curl) -->
              <path d="M31 27 Q36 24 34 20 Q33 18 31 19" fill="none" stroke="#2c1810" stroke-width="1" stroke-linecap="round"/>
              <!-- Cross-hatching on body for engraving effect -->
              <line x1="20" y1="28" x2="22" y2="32" stroke="#2c1810" stroke-width="0.3" opacity="0.5"/>
              <line x1="23" y1="27" x2="25" y2="33" stroke="#2c1810" stroke-width="0.3" opacity="0.5"/>
              <line x1="26" y1="28" x2="28" y2="32" stroke="#2c1810" stroke-width="0.3" opacity="0.5"/>
            </svg>
            <div class="masthead-title">Loki-ciero</div>
          </a>
```

- [ ] **Step 4: Replace the existing tab bars**

Remove the existing `isHub` tabs block (lines 81-90) and replace all the conditional tab bars (lines 81-120) with a single TabBar component. Determine which tab is active based on the `sourceSlug` prop:

```astro
  <TabBar active={sourceSlug === "elperuano" ? "elperuano" : sourceSlug === "indecopi" ? "indecopi" : sourceSlug === "tribunal-fiscal" ? "tribunal-fiscal" : "noticias"} />
```

Keep the sub-navigation bars for INDECOPI, Tribunal Fiscal, and El Peruano as they are (they appear below the main TabBar when you're inside a source).

- [ ] **Step 5: Update the footer brand text and README**

Replace `Loki-ciero Perú` with `Loki-ciero` in the footer (line 133) and remove the subtitle from masthead CSS (line 56 reference is gone since we removed it in step 3). Also update `README.md` at the repo root to reflect the new name.

- [ ] **Step 6: Remove the old tab filtering script**

Remove the `isHub` script block (lines 169-191) — the homepage no longer uses client-side tab filtering (it's replaced by real page navigation).

- [ ] **Step 7: Verify the site builds**

Run: `cd /home/alduere/notirelevanteperu/site && npx astro build 2>&1 | tail -20`
Expected: Build succeeds (there may be warnings about missing data files — that's expected since we haven't run the scrapers yet).

- [ ] **Step 8: Commit**

```bash
git add site/src/layouts/Base.astro
git commit -m "feat: rebrand masthead to Loki-ciero with heraldic Pomeranian SVG"
```

---

### Task 13: Rewrite homepage as news tab

**Files:**
- Modify: `site/src/pages/index.astro` (full rewrite)

- [ ] **Step 1: Rewrite index.astro**

Replace the entire contents of `site/src/pages/index.astro` with:

```astro
---
import Base from "../layouts/Base.astro";
import NoticiaItem from "../components/NoticiaItem.astro";
import FuenteFilter from "../components/FuenteFilter.astro";
import { latestPrensaDate, getPrensa, formatFechaEs } from "../lib/data";
import type { PrensaResumida } from "../lib/types";

const FUENTE_DISPLAY: Record<string, string> = {
  gestion: "Gestión",
  elcomercio: "El Comercio",
  rpp: "RPP",
  andina: "Andina",
  semanaeconomica: "Semana Econ.",
  bcrp: "BCRP",
};

const date = latestPrensaDate();
const prensa = date ? getPrensa(date) : null;
const noticias = prensa ? prensa.noticias : [];
const base = import.meta.env.BASE_URL.replace(/\/$/, "");
---

<Base title={prensa ? `Loki-ciero · Noticias ${prensa.fecha}` : "Loki-ciero"}>
  {prensa && noticias.length > 0 ? (
    <>
      {/* Date heading */}
      <div class="text-center py-6 animate-entrance">
        <div class="text-[10px] uppercase tracking-[0.3em] text-ink-sepia font-sans mb-2 font-semibold">
          Noticias del día
        </div>
        <h1 class="font-display font-black text-3xl sm:text-4xl tracking-tightest leading-[0.9]">
          {formatFechaEs(prensa.fecha)}
        </h1>
        <div class="mt-3 text-sm text-ink-sepia">
          {prensa.total} noticias de {prensa.fuentes_activas.length} fuentes
        </div>
      </div>

      {/* Source filter chips */}
      <FuenteFilter
        fuentes={prensa.fuentes_activas}
        fuenteDisplayMap={FUENTE_DISPLAY}
      />

      {/* News list */}
      <div class="animate-entrance delay-2">
        {noticias.map((noticia) => (
          <NoticiaItem noticia={noticia} />
        ))}
      </div>
    </>
  ) : (
    <section class="text-center py-16">
      <h1 class="font-display font-black text-3xl mb-3">Sin noticias todavía</h1>
      <p class="text-ink-sepia font-sans">
        El scraping de noticias aún no se ha ejecutado. Vuelve mañana después de las 7:00 AM Lima.
      </p>
    </section>
  )}
</Base>
```

- [ ] **Step 2: Verify the site builds**

Run: `cd /home/alduere/notirelevanteperu/site && npx astro build 2>&1 | tail -20`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add site/src/pages/index.astro
git commit -m "feat: rewrite homepage as news tab landing page"
```

---

## Phase 3: CI/CD

### Task 14: Update GitHub Actions workflow

**Files:**
- Modify: `.github/workflows/daily.yml`

- [ ] **Step 1: Add scrape steps for noticias and financiero**

After the "Scrape Tribunal Fiscal" step (line 93), add:

```yaml
      - name: Scrape Noticias
        run: uv run python -m scripts.scrape --date "${{ steps.target.outputs.value }}" --source noticias
        continue-on-error: true

      - name: Scrape Financiero
        run: uv run python -m scripts.scrape --date "${{ steps.target.outputs.value }}" --source financiero
        continue-on-error: true
```

- [ ] **Step 2: Add summarize step for noticias**

After the "Summarize Tribunal Fiscal" step (line 113), add:

```yaml
      - name: Summarize Noticias
        run: uv run python -m scripts.summarize --date "${{ steps.target.outputs.value }}" --source noticias
        continue-on-error: true
```

Note: No summarize step for financiero — it's numeric data that goes directly through.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/daily.yml
git commit -m "ci: add noticias + financiero scrape/summarize to daily pipeline"
```

---

## Phase 4: Integration Test

### Task 15: Local integration test

- [ ] **Step 1: Run the financial scraper locally**

Run: `cd /home/alduere/notirelevanteperu && uv run python -m scripts.scrape --date $(date +%Y-%m-%d) --source financiero`
Expected: Creates `data/raw/financiero/<today>/parsed.json` with exchange rate and mineral prices.

- [ ] **Step 2: Verify the financial data output**

Run: `cat data/raw/financiero/$(date +%Y-%m-%d)/parsed.json | python -m json.tool | head -20`
Expected: JSON with `fecha`, `usd_pen` (with `valor` > 0), and `minerales` array.

- [ ] **Step 3: Run the news scraper locally**

Run: `cd /home/alduere/notirelevanteperu && uv run python -m scripts.scrape --date $(date +%Y-%m-%d) --source noticias`
Expected: Creates `data/raw/noticias/<today>/parsed.json` with news items.

- [ ] **Step 4: Verify the news data output**

Run: `cat data/raw/noticias/$(date +%Y-%m-%d)/parsed.json | python -m json.tool | head -30`
Expected: JSON with `fecha` and `items` array containing news articles with titulo, fuente, url, fecha, contenido.

- [ ] **Step 5: Run the news summarizer locally (requires GEMINI_API_KEY)**

Run: `cd /home/alduere/notirelevanteperu && uv run python -m scripts.summarize --date $(date +%Y-%m-%d) --source noticias`
Expected: Creates `data/processed/noticias/<today>.json` with summarized news.

- [ ] **Step 6: Run the full build**

Run: `cd /home/alduere/notirelevanteperu && uv run python -m scripts.build --skip-pdfs`
Expected: Copies data to `site/src/data/`, generates hub summaries, builds Astro site. Check that `site/src/data/financiero/` and `site/src/data/noticias/` directories exist.

- [ ] **Step 7: Start dev server and verify in browser**

Run: `cd /home/alduere/notirelevanteperu/site && npx astro dev --port 4321`
Open `http://localhost:4321/lokicieroperu/` and verify:
- Ticker bar shows at the top with financial data
- Masthead shows "Loki-ciero" with Pomeranian SVG logo
- Tab bar shows: Noticias (active), El Peruano, INDECOPI, Tribunal Fiscal
- News items display with category badges, source labels, and summaries
- Source filter chips work (clicking a source filters the list)
- Other tabs still navigate correctly to their pages

- [ ] **Step 8: Run all tests**

Run: `cd /home/alduere/notirelevanteperu && uv run pytest tests/ -v`
Expected: All tests PASS.

- [ ] **Step 9: Commit any data files generated during testing**

```bash
git add data/
git commit -m "data: integration test data for noticias + financiero"
```
