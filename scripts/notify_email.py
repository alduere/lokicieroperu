"""Send the daily HTML email + PDF attachment via Brevo."""

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
from jinja2 import Environment, FileSystemLoader, select_autoescape

from scripts.lib.brevo import BrevoClient
from scripts.lib.pdf import _format_fecha_es
from scripts.lib.schemas import DiaProcesado, Impacto

logger = logging.getLogger("notify_email")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_PROCESSED = REPO_ROOT / "data" / "processed"
PDFS_DIR = REPO_ROOT / "pdfs"
TEMPLATES_DIR = REPO_ROOT / "templates"

_IMPACTO_ORDER = {Impacto.ALTO: 0, Impacto.MEDIO: 1, Impacto.BAJO: 2}

MES_ES_SHORT = {1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
                7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--date", help="YYYY-MM-DD; defaults to most recent")
    p.add_argument("--dry-run", action="store_true", help="Render HTML and print, do not send")
    return p.parse_args()


def _resolve_date(arg: str | None) -> Date:
    if arg:
        return datetime.strptime(arg, "%Y-%m-%d").date()
    files = sorted(p for p in DATA_PROCESSED.glob("*.json") if p.name != "index.json")
    if not files:
        raise SystemExit("No processed data found")
    return datetime.strptime(files[-1].stem, "%Y-%m-%d").date()


def _top_normas(dia: DiaProcesado, n: int = 6) -> list:
    """Pick the top N most-relevant norms for the email body."""
    norms = sorted(
        dia.normas,
        key=lambda x: (_IMPACTO_ORDER[x.impacto], x.entidad_emisora),
    )
    return norms[:n]


def _render_html(dia: DiaProcesado, site_url: str) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    tpl = env.get_template("email_diario.html")
    return tpl.render(
        dia=dia,
        site_url=site_url.rstrip("/"),
        fecha_es=_format_fecha_es(dia),
        top_normas=_top_normas(dia),
    )


def _subject(dia: DiaProcesado) -> str:
    d = dia.fecha
    fecha = f"{d.day} {MES_ES_SHORT[d.month]}"
    parts = [f"📰 Loki-ciero Perú · {fecha}", f"{dia.stats.total_normas} normas"]
    if dia.stats.alto > 0:
        parts.append(f"{dia.stats.alto} alto impacto")
    return " · ".join(parts)


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
    html = _render_html(dia, site_url)
    subject = _subject(dia)

    raw_to = os.environ.get("EMAIL_TO", "")
    recipients = [e.strip() for e in raw_to.split(",") if e.strip()]
    if not recipients:
        logger.error("EMAIL_TO not set (comma-separated list)")
        return 2

    if args.dry_run:
        print("--- DRY RUN ---")
        print("Subject:", subject)
        print("To:", recipients)
        print("PDF:", pdf_path, "(exists)" if pdf_path.exists() else "(missing)")
        print("HTML preview (first 500 chars):")
        print(html[:500])
        return 0

    client = BrevoClient()
    client.send(
        to=recipients,
        subject=subject,
        html=html,
        attachment=pdf_path if pdf_path.exists() else None,
    )
    logger.info("Email sent for %s to %s", target.isoformat(), recipients)
    return 0


if __name__ == "__main__":
    sys.exit(main())
