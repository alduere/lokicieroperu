"""El Peruano scraper — adapter wrapping the existing lib/elperuano.py."""

from __future__ import annotations

from datetime import date
from typing import Any

from scripts.lib.elperuano import scrape_day as _scrape_day


class ElPeruanoScraper:
    source_slug = "elperuano"

    def scrape_day(self, target: date) -> dict[str, Any]:
        """Scrape El Peruano for one day.

        Returns a dict with:
          - fecha: ISO date string
          - normas: list of NormaCruda dicts
          - documentos: list of DocumentoSeccion dicts
          - raw_html: dict of section → raw HTML
        """
        normas, documentos, raw_html = _scrape_day(target)
        return {
            "fecha": target.isoformat(),
            "normas": [n.model_dump(mode="json") for n in normas],
            "documentos": [d.model_dump(mode="json") for d in documentos],
            "raw_html": raw_html,
        }
