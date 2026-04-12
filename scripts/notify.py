"""Post the daily PDF + caption to Telegram."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date as Date
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from scripts.lib.schemas import DiaProcesado
from scripts.lib.telegram import TelegramClient

logger = logging.getLogger("notify")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_PROCESSED = REPO_ROOT / "data" / "processed"
PDFS_DIR = REPO_ROOT / "pdfs"

MES_ES = {
    1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
    7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--date", help="YYYY-MM-DD; defaults to most recent processed day")
    p.add_argument("--dry-run", action="store_true", help="Print caption only")
    return p.parse_args()


def _resolve_date(arg: str | None) -> Date:
    if arg:
        return datetime.strptime(arg, "%Y-%m-%d").date()
    files = sorted(p for p in DATA_PROCESSED.glob("*.json") if p.name != "index.json")
    if not files:
        raise SystemExit("No processed data found")
    return datetime.strptime(files[-1].stem, "%Y-%m-%d").date()


def _format_caption(dia: DiaProcesado, site_url: str) -> str:
    d = dia.fecha
    fecha_es = f"{d.day} {MES_ES[d.month]} {d.year}"
    s = dia.stats
    sectores_str = " · ".join(f"{name.replace('_', ' ').title()} ({n})" for name, n in s.sectores_top[:3])
    link = f"{site_url.rstrip('/')}/{d.isoformat()}"
    return (
        f"📰 <b>Loki-ciero Perú</b> · {fecha_es}\n\n"
        f"<b>{s.total_normas}</b> normas publicadas\n"
        f"🔴 {s.alto} alto · 🟡 {s.medio} medio · 🟢 {s.bajo} bajo\n"
        f"\n"
        f"Top sectores: {sectores_str if sectores_str else '—'}\n"
        f"\n"
        f"📎 PDF adjunto · <a href=\"{link}\">Ver online</a>"
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    load_dotenv()
    args = parse_args()

    target = _resolve_date(args.date)
    json_path = DATA_PROCESSED / f"{target.isoformat()}.json"
    pdf_path = PDFS_DIR / f"{target.isoformat()}.pdf"

    if not json_path.exists():
        logger.error("No processed data at %s", json_path)
        return 1

    dia = DiaProcesado(**json.loads(json_path.read_text(encoding="utf-8")))
    site_url = os.environ.get("SITE_BASE_URL", "https://alduere.github.io/lokicieroperu")
    caption = _format_caption(dia, site_url)

    if args.dry_run:
        print("--- DRY RUN ---")
        print("PDF:", pdf_path)
        print("Caption:")
        print(caption)
        return 0

    if not pdf_path.exists():
        logger.error("PDF not found at %s — run build.py first", pdf_path)
        return 2

    client = TelegramClient()
    client.send_document(pdf_path, caption)
    logger.info("Sent %s to Telegram", pdf_path.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
