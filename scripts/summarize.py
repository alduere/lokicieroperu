"""Run AI summarization over parsed data for one or all sources.

Idempotent: skips if processed file exists with current data + prompt version.

Usage:
    uv run python scripts/summarize.py --date 2026-04-10
    uv run python scripts/summarize.py --date 2026-04-10 --source elperuano
    uv run python scripts/summarize.py --date 2026-04-10 --force
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from scripts.lib.sources import enabled_sources, get_source, load_summarizer

logger = logging.getLogger("summarize")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_PROCESSED = REPO_ROOT / "data" / "processed"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Summarize parsed data with AI")
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.add_argument("--source", help="Source slug; defaults to all enabled")
    p.add_argument("--force", action="store_true", help="Re-summarize even if file exists")
    return p.parse_args()


def _update_source_index(source_slug: str, processed_data: dict, summarizer: object) -> None:
    """Update the per-source index.json with the new day's entry."""
    index_path = DATA_PROCESSED / source_slug / "index.json"

    entries: list[dict] = []
    if index_path.exists():
        try:
            existing = json.loads(index_path.read_text(encoding="utf-8"))
            fecha = processed_data["fecha"]
            entries = [e for e in existing.get("fechas", []) if e.get("fecha") != fecha]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not parse %s: %s", index_path, exc)

    # Let the summarizer build its source-specific index entry
    if hasattr(summarizer, "make_index_entry"):
        entry = summarizer.make_index_entry(processed_data)
    else:
        # Generic fallback
        entry = {
            "fecha": processed_data["fecha"],
            "total_items": len(processed_data.get("items", [])),
        }
    entries.append(entry)
    entries.sort(key=lambda e: e.get("fecha", ""), reverse=True)
    index_path.write_text(
        json.dumps({"fechas": entries}, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def summarize_source(source_slug: str, target_date: str, force: bool) -> int:
    """Summarize one source for a given date. Returns 0 on success."""
    source = get_source(source_slug)
    summarizer = load_summarizer(source)

    raw_dir = DATA_RAW / source_slug / target_date
    parsed_path = raw_dir / "parsed.json"
    if not parsed_path.exists():
        logger.warning("No parsed data at %s — skipping %s", parsed_path, source.nombre)
        return 0

    parsed_data = json.loads(parsed_path.read_text(encoding="utf-8"))

    out_dir = DATA_PROCESSED / source_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{target_date}.json"

    # Idempotency check
    if out_path.exists() and not force:
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        existing_ids = {
            n.get("id") for n in existing.get("normas", existing.get("items", []))
        }
        new_ids = {
            n.get("id") for n in parsed_data.get("normas", parsed_data.get("items", []))
        }
        ids_match = existing_ids == new_ids
        stale = summarizer.is_stale(existing)

        if ids_match and not stale:
            logger.info("Skipping %s %s — already up to date", source.nombre, target_date)
            return 0
        if ids_match and stale:
            logger.info("Re-summarizing %s %s — data is stale", source.nombre, target_date)

    if not os.environ.get("GEMINI_API_KEY"):
        logger.error("GEMINI_API_KEY not set")
        return 2

    logger.info("Summarizing %s for %s", source.nombre, target_date)
    processed = summarizer.summarize_day(parsed_data)

    out_path.write_text(
        json.dumps(processed, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("Wrote %s", out_path)

    _update_source_index(source_slug, processed, summarizer)
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    load_dotenv()
    args = parse_args()

    target_date = datetime.strptime(args.date, "%Y-%m-%d").date().isoformat()

    if args.source:
        sources = [get_source(args.source)]
    else:
        sources = enabled_sources()

    errors = 0
    for source in sources:
        try:
            result = summarize_source(source.slug, target_date, args.force)
            if result != 0:
                errors += 1
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to summarize %s: %s", source.nombre, exc)
            errors += 1

    return 1 if errors == len(sources) else 0


if __name__ == "__main__":
    sys.exit(main())
