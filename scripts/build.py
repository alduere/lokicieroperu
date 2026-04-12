"""Build PDFs and sync processed data into the Astro site.

Steps:
  1. For every processed/elperuano/<date>.json without a matching pdf, render PDF.
  2. Copy data/processed/<source>/* into site/src/data/<source>/.
  3. Generate hub summary JSON from all sources.
  4. Run `npm install` (if needed) and `npm run build` inside site/.

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
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from scripts.lib.schemas import DiaProcesado
from scripts.lib.sources import enabled_sources

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
    """Render PDFs for El Peruano (the only source with PDF output)."""
    from scripts.lib.pdf import render_pdf

    PDFS_DIR.mkdir(parents=True, exist_ok=True)
    site_url = _site_url()

    ep_dir = DATA_PROCESSED / "elperuano"
    if not ep_dir.exists():
        # Backwards compat: check for flat structure
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
        render_pdf(dia, site_url, out_pdf)


def _sync_site_data() -> None:
    """Copy processed data into site/src/data/ per source."""
    for source in enabled_sources():
        source_dir = DATA_PROCESSED / source.slug
        if not source_dir.exists():
            continue

        target_dir = SITE_DATA / source.slug
        target_dir.mkdir(parents=True, exist_ok=True)

        for f in source_dir.glob("*.json"):
            shutil.copy2(f, target_dir / f.name)
        logger.info("Synced %s data → %s", source.nombre, target_dir)

    # Backwards compat: also copy El Peruano data to root SITE_DATA
    # so existing Astro pages still work during migration
    ep_dir = DATA_PROCESSED / "elperuano"
    if ep_dir.exists():
        SITE_DATA.mkdir(parents=True, exist_ok=True)
        for f in ep_dir.glob("*.json"):
            shutil.copy2(f, SITE_DATA / f.name)

    # Generate hub summary
    _generate_hub_summary()

    # Copy PDFs into site/public/pdfs/
    site_public_pdfs = SITE_DIR / "public" / "pdfs"
    site_public_pdfs.mkdir(parents=True, exist_ok=True)
    for f in PDFS_DIR.glob("*.pdf"):
        shutil.copy2(f, site_public_pdfs / f.name)


def _generate_hub_summary() -> None:
    """Generate hub/YYYY-MM-DD.json with stats from all sources."""
    hub_dir = SITE_DATA / "hub"
    hub_dir.mkdir(parents=True, exist_ok=True)

    # Collect all dates across all sources
    all_dates: set[str] = set()
    for source in enabled_sources():
        source_dir = DATA_PROCESSED / source.slug
        if not source_dir.exists():
            continue
        for f in source_dir.glob("*.json"):
            if f.name != "index.json":
                all_dates.add(f.stem)

    for date_str in sorted(all_dates):
        hub_path = hub_dir / f"{date_str}.json"
        source_summaries = []

        for source in enabled_sources():
            source_file = DATA_PROCESSED / source.slug / f"{date_str}.json"
            if not source_file.exists():
                continue

            data = json.loads(source_file.read_text(encoding="utf-8"))
            items = data.get("normas", data.get("items", []))
            stats = data.get("stats", {})

            # Build category pills from the data
            pills = []
            if source.slug == "elperuano":
                for key in ("alto", "medio", "bajo"):
                    count = stats.get(key, 0)
                    if count > 0:
                        color_map = {"alto": "bg-red-500", "medio": "bg-orange-400", "bajo": "bg-green-500"}
                        pills.append({"nombre": key, "count": count, "color": color_map.get(key, "")})
            else:
                # Generic: group by category field
                from collections import Counter

                cats = Counter(item.get("categoria", "otros") for item in items)
                for cat, count in cats.most_common(4):
                    pills.append({"nombre": cat, "count": count, "color": "bg-gray-400"})

            source_summaries.append({
                "slug": source.slug,
                "nombre": source.nombre,
                "subtitulo": source.subtitulo,
                "total": len(items),
                "label": source.item_label,
                "categorias": pills,
                "updated_at": data.get("generated_at", ""),
            })

        total_items = sum(s["total"] for s in source_summaries)
        hub_data = {
            "fecha": date_str,
            "sources": source_summaries,
            "stats": {
                "total_publicaciones": total_items,
                "fuentes_activas": len([s for s in source_summaries if s["total"] > 0]),
                "alertas_alto": sum(
                    p["count"] for s in source_summaries
                    for p in s["categorias"] if p["nombre"] == "alto"
                ),
            },
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }

        hub_path.write_text(
            json.dumps(hub_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if all_dates:
        logger.info("Generated hub summaries for %d dates", len(all_dates))


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
