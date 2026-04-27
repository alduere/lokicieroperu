"""Build PDFs from processed El Peruano data.

Usage:
    uv run python scripts/build.py
    uv run python scripts/build.py --date 2026-04-11   # only this day's PDF
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from scripts.lib.schemas import DiaProcesado

logger = logging.getLogger("build")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_PROCESSED = REPO_ROOT / "data" / "processed"
PDFS_DIR = REPO_ROOT / "pdfs"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--date", help="Only build PDF for this YYYY-MM-DD")
    return p.parse_args()


def _render_pdfs(only_date: str | None) -> None:
    from scripts.lib.pdf import render_pdf

    PDFS_DIR.mkdir(parents=True, exist_ok=True)

    ep_dir = DATA_PROCESSED / "elperuano"
    if not ep_dir.exists():
        ep_dir = DATA_PROCESSED

    for json_file in sorted(ep_dir.glob("*.json")):
        if json_file.name == "index.json":
            continue
        date_str = json_file.stem
        if only_date and date_str != only_date:
            continue
        out_pdf = PDFS_DIR / f"{date_str}.pdf"
        if out_pdf.exists() and not only_date:
            continue
        logger.info("Rendering PDF for %s", date_str)
        dia = DiaProcesado(**json.loads(json_file.read_text(encoding="utf-8")))
        render_pdf(dia, "", out_pdf)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    load_dotenv()
    args = parse_args()
    _render_pdfs(args.date)
    return 0


if __name__ == "__main__":
    sys.exit(main())
