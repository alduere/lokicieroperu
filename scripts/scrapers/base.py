"""Base scraper protocol for Loki-ciero Perú sources.

Every source scraper implements this interface. The pipeline (scrape.py) calls
scrape_day() and persists the returned dict as JSON.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol


class BaseScraper(Protocol):
    """Protocol that every source scraper must implement."""

    source_slug: str

    def scrape_day(self, target: date) -> dict[str, Any]:
        """Scrape one day and return a dict ready for JSON serialization.

        The dict MUST contain at least:
          - "fecha": ISO date string
          - "items": list of dicts (source-specific item schema)

        It MAY also contain:
          - "raw_html": dict of section → raw HTML (for evidence)
          - Any other source-specific keys

        Returns the parsed data dict (not yet summarized).
        """
        ...
