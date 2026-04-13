"""Scraper de visitas a entidades del Estado peruano.

Fuente: Plataforma de Registro de Visitas en Linea
https://visitas.servicios.gob.pe/consultas/

Requiere Playwright (pip install playwright && playwright install chromium).
El portal usa reCAPTCHA v3, por lo que necesitamos un navegador real.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PORTAL_URL = "https://visitas.servicios.gob.pe/consultas/"
SEARCH_ENDPOINT = "https://visitas.servicios.gob.pe/consultas/dataBusqueda.php"

# Key institutions with their RUC numbers
INSTITUCIONES: dict[str, str] = {
    "PCM": "20168999926",
    "MEF": "20131370645",
    "MINJUS": "20131371617",
    "CONGRESO": "20161749126",
    "SUNAT": "20131312955",
    "PRODUCE": "20504774288",
    "MTC": "20131379944",
    "MINEDU": "20131370998",
    "MINSA": "20131023414",
    "MINEM": "20131368845",
    "MINDEF": "20131370301",
    "MININTER": "20131367938",
    "MVCS": "20504743307",
    "MIDAGRI": "20131368829",
    "MINAM": "20532904237",
    "MIDIS": "20543568417",
    "MINCETUR": "20504794637",
    "OSCE": "20419026809",
    "SERVIR": "20504743048",
    "SUNARP": "20168999926",
}


def _format_date_dmy(d: date) -> str:
    return d.strftime("%d/%m/%Y")


class VisitantesScraper:
    """Scraper for the Peruvian government visitor registry.

    This scraper uses Playwright to handle the reCAPTCHA v3 protection
    on the government portal. It can search by:
    - Free text (name, apellidos) with a date range (max 90 days)
    - DNI number with a date range
    - Institution RUC with a date range
    """

    source_slug = "visitantes"

    def __init__(self) -> None:
        self._browser = None
        self._page = None

    def _ensure_browser(self) -> Any:
        """Lazy-init Playwright browser."""
        if self._page is not None:
            return self._page

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError(
                "Playwright is required: pip install playwright && playwright install chromium"
            )

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )
        self._page = context.new_page()
        return self._page

    def close(self) -> None:
        if self._browser:
            self._browser.close()
        if hasattr(self, "_pw") and self._pw:
            self._pw.stop()
        self._browser = None
        self._page = None

    def search(
        self,
        query: str,
        date_from: date,
        date_to: date,
        ruc: str = "",
    ) -> list[dict[str, Any]]:
        """Search the government portal for visitor records.

        Args:
            query: Search text (name, DNI, etc.) — min 3 chars unless ruc is set.
            date_from: Start date.
            date_to: End date (max 90 days from date_from).
            ruc: Optional institution RUC to filter by.

        Returns:
            List of visitor record dicts.
        """
        page = self._ensure_browser()

        # Navigate to portal
        logger.info("Navigating to portal: %s", PORTAL_URL)
        page.goto(PORTAL_URL, wait_until="networkidle", timeout=30000)
        time.sleep(2)  # Let reCAPTCHA initialize

        # Fill search form
        fecha_range = f"{_format_date_dmy(date_from)} - {_format_date_dmy(date_to)}"

        page.evaluate(f"""() => {{
            document.getElementById('txtbuscar').value = '{query}';
            document.getElementById('fechabus').value = '{fecha_range}';
            document.getElementById('ruc').value = '{ruc}';
        }}""")

        # Intercept the API response
        all_results: list[dict[str, Any]] = []

        def handle_response(response: Any) -> None:
            if "dataBusqueda.php" in response.url:
                try:
                    data = response.json()
                    if isinstance(data, dict) and isinstance(data.get("data"), list):
                        all_results.extend(data["data"])
                except Exception:
                    pass

        page.on("response", handle_response)

        # Trigger search via the page's own JavaScript
        page.evaluate("""() => {
            if (typeof consulta === 'function') {
                consulta();
            }
        }""")

        # Wait for results
        time.sleep(5)

        page.remove_listener("response", handle_response)

        logger.info("Found %d results for query '%s'", len(all_results), query)
        return all_results

    def scrape_day(self, target: date) -> dict[str, Any]:
        """Scrape visitor records for a single day across key institutions.

        This follows the BaseScraper protocol for integration with the
        Loki-ciero pipeline.
        """
        all_items: list[dict[str, Any]] = []

        for nombre, ruc in INSTITUCIONES.items():
            logger.info("Scraping %s (RUC: %s) for %s", nombre, ruc, target)
            try:
                results = self.search(
                    query="",
                    date_from=target,
                    date_to=target,
                    ruc=ruc,
                )
                for r in results:
                    r["institucion_nombre"] = nombre
                all_items.extend(results)
                time.sleep(3)  # Rate limiting between institutions
            except Exception as e:
                logger.error("Error scraping %s: %s", nombre, e)

        return {
            "fecha": target.isoformat(),
            "source_slug": self.source_slug,
            "items": all_items,
            "stats": {
                "total_visitas": len(all_items),
                "instituciones_scrapeadas": len(INSTITUCIONES),
            },
            "generated_at": date.today().isoformat(),
        }


def search_cli(query: str, days_back: int = 30) -> list[dict[str, Any]]:
    """CLI helper to search for visitors.

    Usage:
        python -m scrapers.visitantes "Garcia Lopez" --days 30
        python -m scrapers.visitantes "12345678" --days 90
    """
    scraper = VisitantesScraper()
    try:
        today = date.today()
        from_date = today - timedelta(days=days_back)
        results = scraper.search(query, from_date, today)
        return results
    finally:
        scraper.close()


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Buscar visitas a entidades del Estado")
    parser.add_argument("query", help="Texto de busqueda (apellidos, DNI, etc.)")
    parser.add_argument("--days", type=int, default=30, help="Dias hacia atras (max 90)")
    parser.add_argument("--output", "-o", help="Archivo de salida JSON")
    args = parser.parse_args()

    results = search_cli(args.query, min(args.days, 90))

    if args.output:
        Path(args.output).write_text(json.dumps(results, ensure_ascii=False, indent=2))
        print(f"Guardados {len(results)} resultados en {args.output}")
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        print(f"\nTotal: {len(results)} resultados")
