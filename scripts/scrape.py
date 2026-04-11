"""Scrape one day from El Peruano and save raw HTML + a parsed JSON.

Usage:
    uv run python scripts/scrape.py                # scrape today
    uv run python scripts/scrape.py --date 2026-04-10
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path

from scripts.lib.elperuano import scrape_day
from scripts.lib.schemas import Seccion

logger = logging.getLogger("scrape")


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = REPO_ROOT / "data" / "raw"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scrape El Peruano for one day")
    p.add_argument("--date", help="YYYY-MM-DD; defaults to today (Lima)")
    return p.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = parse_args()

    target: date | None
    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target = None  # scrape today via Load* endpoints

    actual_date = target or date.today()
    out_dir = DATA_RAW / actual_date.isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Scraping El Peruano for %s", actual_date.isoformat())
    normas, documentos, raw = scrape_day(target)

    # Persist raw HTML for evidence
    for seccion_value, html in raw.items():
        if html:
            (out_dir / f"{seccion_value}.html").write_text(html, encoding="utf-8")

    # Persist parsed (but not yet summarized) data
    parsed = {
        "fecha": actual_date.isoformat(),
        "normas": [n.model_dump(mode="json") for n in normas],
        "documentos": [d.model_dump(mode="json") for d in documentos],
    }
    (out_dir / "parsed.json").write_text(
        json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    n_normas = len(normas)
    n_docs = len(documentos)
    logger.info("Done: %d normas legales, %d documentos otras secciones", n_normas, n_docs)

    if n_normas == 0 and n_docs == 0:
        logger.warning("No content found for %s — El Peruano may not have published yet", actual_date)
    return 0


if __name__ == "__main__":
    sys.exit(main())
