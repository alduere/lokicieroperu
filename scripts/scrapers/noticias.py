"""Multi-source news scraper — RSS + HTML hybrid for Loki-ciero Perú.

Sources:
- Gestión, El Comercio, RPP, Andina: RSS feeds via feedparser
- BCRP: RSS (comunicados / notas informativas)
- Semana Económica: HTML scraping via requests + BeautifulSoup
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

logger = logging.getLogger(__name__)

USER_AGENT = "LokicieroPeru/0.1 (+https://github.com/alduere/lokicieroperu)"

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
        "https://andina.pe/agencia/rss/3",
        "https://andina.pe/agencia/rss/6",
    ],
}

BCRP_RSS_URL = "https://www.bcrp.gob.pe/rss/notas-informativas.xml"

SEMANA_ECONOMICA_URL = "https://semanaeconomica.com/"

# CSS selectors to locate article cards on Semana Económica homepage
_SE_SELECTORS = [
    "article",
    ".article-card",
    ".post-card",
    ".story-card",
]

_REQUEST_DELAY = 0.5  # seconds between requests


def _make_id(fuente: str, url: str) -> str:
    """Return a deterministic ID: '{fuente}-{12 hex chars of MD5(url)}'.

    Args:
        fuente: Source slug (e.g. "gestion", "rpp").
        url: Article URL used as the hash input.

    Returns:
        A stable string ID that uniquely identifies this article.
    """
    hash12 = hashlib.md5(url.encode()).hexdigest()[:12]
    return f"{fuente}-{hash12}"


def _parse_rss_date(entry: dict) -> datetime | None:
    """Extract a timezone-aware datetime from a feedparser entry.

    Tries ``published_parsed`` first, then ``updated_parsed``.  Both are
    ``time.struct_time`` values in UTC when present.

    Args:
        entry: A feedparser entry dict.

    Returns:
        A timezone-aware ``datetime`` in UTC, or ``None`` if unavailable.
    """
    for attr in ("published_parsed", "updated_parsed"):
        parsed = entry.get(attr)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return None


def _strip_html(html: str) -> str:
    """Strip HTML tags from a string using BeautifulSoup."""
    if not html:
        return ""
    return BeautifulSoup(html, "lxml").get_text(separator=" ").strip()


def _parse_rss_entry(entry: dict, fuente: str) -> dict | None:
    """Parse a single feedparser entry into the canonical item dict.

    Args:
        entry: A feedparser entry dict.
        fuente: Source slug.

    Returns:
        A dict with keys: id, titulo, fuente, url, fecha, contenido — or
        ``None`` if required fields are missing.
    """
    url = entry.get("link") or entry.get("id") or ""
    if not url:
        logger.debug("%s: skipping entry with no URL", fuente)
        return None

    titulo = entry.get("title", "").strip()
    if not titulo:
        logger.debug("%s: skipping entry with no title", fuente)
        return None

    fecha = _parse_rss_date(entry)
    if fecha is None:
        logger.debug("%s: skipping entry with no parseable date: %s", fuente, url)
        return None

    raw_summary = entry.get("summary") or entry.get("description") or ""
    contenido = _strip_html(raw_summary)

    return {
        "id": _make_id(fuente, url),
        "titulo": titulo,
        "fuente": fuente,
        "url": url,
        "fecha": fecha.isoformat(),
        "contenido": contenido,
    }


class NoticiasScraper:
    """Scraper for multi-source Peruvian news (RSS + HTML hybrid)."""

    source_slug = "noticias"

    def scrape_day(self, target: date) -> dict[str, Any]:
        """Scrape all news sources for *target* date.

        Failures in individual sources are caught and logged — they never
        propagate to the caller.

        Args:
            target: The date to scrape.

        Returns:
            A dict with:
            - ``"fecha"``: ISO date string.
            - ``"items"``: List of article dicts, deduplicated and sorted by
              ``fecha`` descending.
        """
        all_items: list[dict] = []

        # --- RSS sources ---
        for fuente, urls in RSS_SOURCES.items():
            try:
                items = self._fetch_rss_source(fuente, urls, target)
                all_items.extend(items)
            except Exception:
                logger.exception("RSS fetch failed for source '%s'", fuente)

        # --- BCRP RSS ---
        try:
            bcrp_items = self._fetch_bcrp_rss(target)
            all_items.extend(bcrp_items)
        except Exception:
            logger.exception("BCRP RSS fetch failed")

        # --- Semana Económica HTML ---
        try:
            se_items = self._fetch_semana_economica(target)
            all_items.extend(se_items)
        except Exception:
            logger.exception("Semana Económica HTML scrape failed")

        # Deduplicate by id (keep first occurrence)
        seen: set[str] = set()
        unique_items: list[dict] = []
        for item in all_items:
            item_id = item.get("id", "")
            if item_id and item_id not in seen:
                seen.add(item_id)
                unique_items.append(item)

        # Sort by fecha descending
        unique_items.sort(key=lambda x: x.get("fecha", ""), reverse=True)

        return {
            "fecha": target.isoformat(),
            "items": unique_items,
        }

    def _fetch_rss_source(
        self, fuente: str, urls: list[str], target: date
    ) -> list[dict]:
        """Fetch RSS feeds for one source and filter entries to *target* date.

        Args:
            fuente: Source slug (e.g. "gestion").
            urls: List of RSS feed URLs to fetch.
            target: The date to filter articles by.

        Returns:
            List of article dicts matching the target date.
        """
        items: list[dict] = []

        for url in urls:
            try:
                feed = feedparser.parse(
                    url,
                    agent=USER_AGENT,
                    request_headers={"User-Agent": USER_AGENT},
                )
                for entry in feed.entries:
                    parsed = _parse_rss_entry(entry, fuente)
                    if parsed is None:
                        continue
                    # Filter to target date
                    try:
                        entry_date = datetime.fromisoformat(parsed["fecha"]).date()
                    except (ValueError, KeyError):
                        continue
                    if entry_date == target:
                        items.append(parsed)
            except Exception:
                logger.exception("Failed fetching RSS feed %s for %s", url, fuente)

            time.sleep(_REQUEST_DELAY)

        return items

    def _fetch_bcrp_rss(self, target: date) -> list[dict]:
        """Fetch BCRP RSS feed and filter entries to *target* date.

        Args:
            target: The date to filter articles by.

        Returns:
            List of article dicts matching the target date.
        """
        fuente = "bcrp"
        items: list[dict] = []

        try:
            feed = feedparser.parse(
                BCRP_RSS_URL,
                agent=USER_AGENT,
                request_headers={"User-Agent": USER_AGENT},
            )
            for entry in feed.entries:
                parsed = _parse_rss_entry(entry, fuente)
                if parsed is None:
                    continue
                try:
                    entry_date = datetime.fromisoformat(parsed["fecha"]).date()
                except (ValueError, KeyError):
                    continue
                if entry_date == target:
                    items.append(parsed)
        except Exception:
            logger.exception("Failed fetching BCRP RSS feed %s", BCRP_RSS_URL)

        time.sleep(_REQUEST_DELAY)
        return items

    def _fetch_semana_economica(self, target: date) -> list[dict]:
        """Scrape Semana Económica homepage for article cards.

        Uses CSS selectors to locate article elements. Since SE does not
        expose RSS with dates, all found articles are included regardless of
        date (the caller may post-filter if needed). No date filtering is
        applied here as SE does not reliably expose publish dates in HTML.

        Args:
            target: The target date (used only to generate IDs, not for
                filtering since SE HTML rarely includes parseable dates).

        Returns:
            List of article dicts (fecha defaults to target date at noon UTC).
        """
        fuente = "semanaeconomica"
        items: list[dict] = []

        try:
            resp = requests.get(
                SEMANA_ECONOMICA_URL,
                headers={"User-Agent": USER_AGENT},
                timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException:
            logger.exception("Failed fetching Semana Económica homepage")
            return items

        time.sleep(_REQUEST_DELAY)

        soup = BeautifulSoup(resp.text, "lxml")

        # Try each selector in order; collect all matching elements
        article_elements: list = []
        for selector in _SE_SELECTORS:
            found = soup.select(selector)
            if found:
                article_elements.extend(found)
                break  # stop at first selector that yields results

        # Use a set to deduplicate by URL within SE results
        seen_urls: set[str] = set()
        default_fecha = datetime(
            target.year, target.month, target.day, 12, 0, tzinfo=timezone.utc
        ).isoformat()

        for elem in article_elements:
            # Extract link
            a_tag = elem.find("a", href=True)
            if not a_tag:
                continue
            url = a_tag.get("href", "").strip()
            if not url:
                continue
            # Make absolute if relative
            if url.startswith("/"):
                url = f"https://semanaeconomica.com{url}"
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Extract title: prefer heading tags, fall back to link text
            title_tag = elem.find(["h1", "h2", "h3", "h4", "h5", "h6"])
            titulo = (title_tag.get_text(strip=True) if title_tag else "").strip()
            if not titulo:
                titulo = a_tag.get_text(strip=True).strip()
            if not titulo:
                continue

            # Extract excerpt from <p> tags
            p_tag = elem.find("p")
            contenido = p_tag.get_text(strip=True) if p_tag else ""

            items.append(
                {
                    "id": _make_id(fuente, url),
                    "titulo": titulo,
                    "fuente": fuente,
                    "url": url,
                    "fecha": default_fecha,
                    "contenido": contenido,
                }
            )

        return items
