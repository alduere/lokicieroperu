"""WeasyPrint helper that renders the daily PDF from a Jinja2 template."""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from scripts.lib.schemas import DiaProcesado, Impacto, NormaResumida

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"

MES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}

DIA_ES = {0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves", 4: "viernes", 5: "sábado", 6: "domingo"}

_IMPACTO_ORDER = {Impacto.ALTO: 0, Impacto.MEDIO: 1, Impacto.BAJO: 2}


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _format_fecha_es(dia: DiaProcesado) -> str:
    d = dia.fecha
    return f"{DIA_ES[d.weekday()]} {d.day} de {MES_ES[d.month]} de {d.year}"


def _group_by_sector(normas: list[NormaResumida]) -> list[tuple[str, list[NormaResumida]]]:
    """Group norms by their primary sector, sort sectors by total count desc,
    sort norms within a sector by impact (alto first)."""
    bucket: dict[str, list[NormaResumida]] = defaultdict(list)
    for n in normas:
        primary = n.sectores[0] if n.sectores else "administracion_publica"
        bucket[primary].append(n)
    out = []
    for sector, items in sorted(bucket.items(), key=lambda kv: -len(kv[1])):
        items.sort(key=lambda n: (_IMPACTO_ORDER[n.impacto], n.entidad_emisora))
        out.append((sector, items))
    return out


def render_html(dia: DiaProcesado, site_url: str) -> str:
    env = _env()
    tpl = env.get_template("pdf_diario.html")
    return tpl.render(
        dia=dia,
        site_url=site_url,
        fecha_es=_format_fecha_es(dia),
        normas_por_sector=_group_by_sector(dia.normas),
    )


def render_pdf(dia: DiaProcesado, site_url: str, output: Path) -> Path:
    """Render the day to a PDF on disk. Returns the output path."""
    # Import lazily — WeasyPrint pulls in cairo/pango which is heavy and only
    # required at PDF time, not for parser tests.
    from weasyprint import HTML

    html = render_html(dia, site_url)
    output.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html, base_url=str(TEMPLATES_DIR)).write_pdf(target=str(output))
    logger.info("PDF written to %s", output)
    return output
