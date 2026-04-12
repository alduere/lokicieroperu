"""Scrape one or all sources for one day and save raw data.

Usage:
    uv run python scripts/scrape.py --date 2026-04-10                   # all sources
    uv run python scripts/scrape.py --date 2026-04-10 --source elperuano  # one source
    uv run python scripts/scrape.py                                       # today, all
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path

from scripts.lib.sources import enabled_sources, get_source, load_scraper

logger = logging.getLogger("scrape")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = REPO_ROOT / "data" / "raw"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scrape sources for one day")
    p.add_argument("--date", help="YYYY-MM-DD; defaults to today (Lima)")
    p.add_argument("--source", help="Source slug (e.g., elperuano); defaults to all enabled")
    return p.parse_args()


def scrape_source(source_slug: str, target: date) -> int:
    """Scrape a single source for a given date. Returns 0 on success."""
    source = get_source(source_slug)
    scraper = load_scraper(source)

    out_dir = DATA_RAW / source_slug / target.isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Scraping %s for %s", source.nombre, target.isoformat())
    data = scraper.scrape_day(target)

    # Persist raw HTML if provided
    raw_html = data.pop("raw_html", {})
    for section_name, html in raw_html.items():
        if html:
            (out_dir / f"{section_name}.html").write_text(html, encoding="utf-8")

    # Persist parsed (but not yet summarized) data
    (out_dir / "parsed.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    n_items = len(data.get("normas", data.get("items", [])))
    logger.info("Done %s: %d items", source.nombre, n_items)

    if n_items == 0:
        logger.warning("No content from %s for %s", source.nombre, target)
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = parse_args()

    target: date
    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target = date.today()

    if args.source:
        sources = [get_source(args.source)]
    else:
        sources = enabled_sources()

    errors = 0
    for source in sources:
        try:
            scrape_source(source.slug, target)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to scrape %s: %s", source.nombre, exc)
            errors += 1

    return 1 if errors == len(sources) else 0


if __name__ == "__main__":
    sys.exit(main())
