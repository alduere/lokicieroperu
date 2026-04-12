"""consumidor.gob.pe scraper (WordPress REST API).

Fetches news posts from INDECOPI's consumer protection portal.
Very low volume (~2-4 posts/month).
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime
from typing import Any

import requests

from scripts.lib.schemas import NoticiaCruda

logger = logging.getLogger(__name__)

API_BASE = "https://consumidor.gob.pe/wp-json/wp/v2"
USER_AGENT = "LokicieroPeru/0.1 (+https://github.com/alduere/lokicieroperu)"
REQUEST_DELAY = 0.5  # politeness between requests
PAGE_SIZE = 50


def _strip_html(text: str | None) -> str | None:
    """Remove HTML tags from a string."""
    if not text:
        return None
    cleaned = re.sub(r"<[^>]+>", "", text)
    return cleaned.strip() or None


def _parse_wp_date(date_str: str) -> date | None:
    """Parse WordPress date format (ISO 8601 without tz) to date object."""
    try:
        return datetime.fromisoformat(date_str).date()
    except (ValueError, TypeError):
        return None


class ConsumidorScraper:
    source_slug = "consumidor"

    def scrape_day(self, target: date) -> dict[str, Any]:
        """Fetch posts published on the target date.

        The WordPress API supports orderby=date, so we paginate through
        recent posts and filter by date locally.
        """
        session = requests.Session()
        session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        })

        noticias = self._fetch_posts_for_date(session, target)
        logger.info("Found %d posts for %s", len(noticias), target.isoformat())

        return {
            "fecha": target.isoformat(),
            "items": [n.model_dump(mode="json") for n in noticias],
        }

    def _fetch_posts_for_date(
        self, session: requests.Session, target: date
    ) -> list[NoticiaCruda]:
        """Paginate through the WordPress API to find posts on target date."""
        posts_for_date: list[NoticiaCruda] = []
        page = 1
        max_pages = 10  # safety limit

        while page <= max_pages:
            params = {
                "per_page": PAGE_SIZE,
                "_fields": "id,title,date,link,excerpt,categories",
                "orderby": "date",
                "order": "desc",
                "page": page,
            }

            try:
                resp = session.get(
                    f"{API_BASE}/posts", params=params, timeout=30
                )
                resp.raise_for_status()
                results = resp.json()
            except (requests.RequestException, ValueError) as exc:
                logger.error("API request failed (page %d): %s", page, exc)
                break

            if not results:
                break

            found_older = False
            for item in results:
                pub_date = _parse_wp_date(item.get("date", ""))
                if pub_date == target:
                    posts_for_date.append(self._parse_post(item, target))
                elif pub_date and pub_date < target:
                    found_older = True

            # Stop paginating if we've gone past our target date
            if found_older:
                break

            # WordPress returns total pages in header
            total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
            if page >= total_pages:
                break

            page += 1
            time.sleep(REQUEST_DELAY)

        return posts_for_date

    @staticmethod
    def _parse_post(data: dict, target: date) -> NoticiaCruda:
        """Parse a WordPress post JSON into NoticiaCruda."""
        pub_date = _parse_wp_date(data.get("date", "")) or target

        title_obj = data.get("title", {})
        titulo = title_obj.get("rendered", "") if isinstance(title_obj, dict) else str(title_obj)

        excerpt_obj = data.get("excerpt", {})
        excerpt_html = excerpt_obj.get("rendered", "") if isinstance(excerpt_obj, dict) else str(excerpt_obj)

        return NoticiaCruda(
            id=str(data.get("id", "")),
            titulo=titulo.strip(),
            extracto=_strip_html(excerpt_html),
            fecha_publicacion=pub_date,
            link_oficial=data.get("link"),
            categorias=data.get("categories", []),
        )
