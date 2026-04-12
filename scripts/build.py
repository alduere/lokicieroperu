"""Build the daily PDF and copy processed data into the Astro site.

Steps:
  1. For every processed/<date>.json without a matching pdfs/<date>.pdf, render the PDF.
  2. Copy data/processed/* into site/src/data/ so Astro can import it at build time.
  3. Run `npm install` (if needed) and `npm run build` inside site/ to produce public/.

Usage:
    uv run python scripts/build.py
    uv run python scripts/build.py --date 2026-04-11   # only this day's PDF
    uv run python scripts/build.py --skip-site         # only PDFs, no Astro build
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from scripts.lib.pdf import render_pdf
from scripts.lib.schemas import DiaProcesado

logger = logging.getLogger("build")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_PROCESSED = REPO_ROOT / "data" / "processed"
PDFS_DIR = REPO_ROOT / "pdfs"
SITE_DIR = REPO_ROOT / "site"
SITE_DATA = SITE_DIR / "src" / "data"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--date", help="Only build PDF for this YYYY-MM-DD")
    p.add_argument("--skip-site", action="store_true", help="Skip Astro build")
    p.add_argument("--skip-pdfs", action="store_true", help="Skip PDF rendering")
    return p.parse_args()


def _site_url() -> str:
    import os

    return os.environ.get("SITE_BASE_URL", "https://alduere.github.io/lokicieroperu")


def _render_pdfs(only_date: str | None) -> None:
    PDFS_DIR.mkdir(parents=True, exist_ok=True)
    site_url = _site_url()
    for json_file in sorted(DATA_PROCESSED.glob("*.json")):
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
        render_pdf(dia, site_url, out_pdf)


def _sync_site_data() -> None:
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    # Copy every processed/<date>.json + index.json into site/src/data/
    for f in DATA_PROCESSED.glob("*.json"):
        shutil.copy2(f, SITE_DATA / f.name)
    # Also copy PDFs into site/public/pdfs/ so Astro picks them up
    site_public_pdfs = SITE_DIR / "public" / "pdfs"
    site_public_pdfs.mkdir(parents=True, exist_ok=True)
    for f in PDFS_DIR.glob("*.pdf"):
        shutil.copy2(f, site_public_pdfs / f.name)


def _astro_build() -> None:
    if not (SITE_DIR / "package.json").exists():
        logger.warning("site/package.json missing — skipping Astro build")
        return
    if not (SITE_DIR / "node_modules").exists():
        logger.info("Running npm install...")
        subprocess.run(["npm", "install", "--silent"], cwd=SITE_DIR, check=True)
    logger.info("Running npm run build...")
    subprocess.run(["npm", "run", "build"], cwd=SITE_DIR, check=True)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    load_dotenv()
    args = parse_args()

    if not args.skip_pdfs:
        _render_pdfs(args.date)

    if not args.skip_site:
        _sync_site_data()
        _astro_build()

    return 0


if __name__ == "__main__":
    sys.exit(main())
