"""Post the daily digest to Telegram.

Three messages per day:
  1. El Peruano PDF with minimal caption (stats only)
  2. Normas de alto impacto + concesiones mineras (skipped if both empty)
  3. Other sources: INDECOPI, Consumidor, Tribunal Fiscal, Gaceta PI (skipped if all empty)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date as Date
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger("notify")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_PROCESSED = REPO_ROOT / "data" / "processed"
PDFS_DIR = REPO_ROOT / "pdfs"

MES_ES = {
    1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
    7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic",
}

SECTOR_DISPLAY: dict[str, str] = {
    "administracion_publica": "Administración Pública",
    "vivienda": "Vivienda",
    "gobierno_local": "Gobierno Local",
    "urbanismo": "Urbanismo",
    "relaciones_exteriores": "RR.EE.",
    "educacion": "Educación",
    "salud": "Salud",
    "economia": "Economía",
    "justicia": "Justicia",
    "trabajo": "Trabajo",
    "agricultura": "Agricultura",
    "medio_ambiente": "Medio Ambiente",
    "energia": "Energía",
    "transporte": "Transporte",
    "defensa": "Defensa",
    "interior": "Interior",
    "mineria": "Minería",
    "tributacion": "Tributación",
    "comercio": "Comercio",
    "tecnologia": "Tecnología",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--date", help="YYYY-MM-DD; defaults to most recent processed day")
    p.add_argument("--dry-run", action="store_true", help="Print messages only, do not send")
    return p.parse_args()


def _resolve_date(arg: str | None) -> Date:
    if arg:
        return datetime.strptime(arg, "%Y-%m-%d").date()
    ep_dir = DATA_PROCESSED / "elperuano"
    search_dir = ep_dir if ep_dir.exists() else DATA_PROCESSED
    files = sorted(p for p in search_dir.glob("*.json") if p.name != "index.json")
    if not files:
        raise SystemExit("No processed data found")
    return datetime.strptime(files[-1].stem, "%Y-%m-%d").date()


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _fecha_es(d: Date) -> str:
    return f"{d.day} {MES_ES[d.month]} {d.year}"


# ── Message 1: PDF caption (stats only) ─────────────────────────────────────

def _build_pdf_caption(data: dict, fecha: str) -> str:
    stats = data.get("stats", {})
    total = stats.get("total_normas", 0)
    alto = stats.get("alto", 0)
    medio = stats.get("medio", 0)
    bajo = stats.get("bajo", 0)

    sectores_top = stats.get("sectores_top", [])[:3]
    sectores_str = " · ".join(
        SECTOR_DISPLAY.get(s, s.replace("_", " ").title())
        for s, _ in sectores_top
    )

    lines = [
        f"📋 <b>El Peruano</b> · {fecha}",
        f"{total} normas · 🔴 {alto} alto  🟡 {medio} medio  🟢 {bajo} bajo",
    ]
    if sectores_str:
        lines.append(f"Sectores: {sectores_str}")

    return "\n".join(lines)


# ── Message 2: Normas destacadas + Concesiones ──────────────────────────────

def _build_destacadas_message(data: dict, fecha: str) -> str | None:
    from scripts.lib.concesiones import extract_concesiones, format_concesiones_section

    normas_alto = [n for n in data.get("normas", []) if n.get("impacto") == "alto"]
    documentos = data.get("documentos", [])
    n_pdfs = sum(1 for d in documentos if d.get("seccion") == "concesiones_mineras")
    concesiones = extract_concesiones(documentos) if n_pdfs > 0 else []
    concesiones_section = format_concesiones_section(concesiones, n_pdfs)

    if not normas_alto and not concesiones_section:
        return None

    lines = []

    if normas_alto:
        lines.append("🔴 <b>Normas destacadas</b>")
        for n in normas_alto[:3]:
            tipo = n.get("tipo_corto", "")
            numero = n.get("numero", "")
            ref = f"{tipo} {numero}".strip() if tipo or numero else n.get("titulo_oficial", "")[:40]
            resumen = n.get("resumen_ejecutivo") or n.get("sumilla") or ""
            resumen = resumen[:200].rstrip()
            if resumen and not resumen.endswith((".", "…")):
                resumen += "…"
            lines.append(f"\n<b>{ref}</b> — {resumen}")

    if concesiones_section:
        if lines:
            lines.append("")
        lines.append(concesiones_section)

    return "\n".join(lines)


# ── Message 3: Other sources ─────────────────────────────────────────────────

def _section_indecopi(data: dict) -> str | None:
    items = data.get("items", [])
    if not items:
        return None
    total = data.get("stats", {}).get("total_alertas", len(items))
    lines = [f"⚠️ <b>INDECOPI Alertas</b> — {total} alerta{'s' if total != 1 else ''}"]
    for item in items[:3]:
        titulo = item.get("titulo", "")[:100]
        lines.append(f"• {titulo}")
    return "\n".join(lines)


def _section_consumidor(data: dict) -> str | None:
    items = data.get("items", [])
    if not items:
        return None
    total = data.get("stats", {}).get("total_noticias", len(items))
    lines = [f"👤 <b>Consumidor</b> — {total} noticia{'s' if total != 1 else ''}"]
    for item in items[:3]:
        resumen = item.get("resumen", "")
        text = resumen[:90] if resumen else item.get("titulo", "")[:90]
        lines.append(f"• {text}")
    return "\n".join(lines)


def _section_tribunal(data: dict) -> str | None:
    items = data.get("items", [])
    if not items:
        return None
    total = data.get("stats", {}).get("total_resoluciones", len(items))
    lines = [f"⚖️ <b>Tribunal Fiscal</b> — {total} resolución{'es' if total != 1 else ''}"]
    for item in items[:3]:
        tema = item.get("tema_tributario", "")
        resumen = item.get("resumen", "")[:90]
        prefix = f"{tema}: " if tema else ""
        lines.append(f"• {prefix}{resumen}" if resumen else f"• RTF {item.get('numero_rtf', '')}")
    return "\n".join(lines)


def _section_gaceta(data: dict) -> str | None:
    items = data.get("items", [])
    if not items:
        return None
    stats = data.get("stats", {})
    total = stats.get("total_solicitudes", len(items))
    por_tipo = stats.get("por_tipo", [])
    tipo_str = "  ·  ".join(f"{t}: {n}" for t, n in por_tipo[:4]) if por_tipo else f"{total} solicitudes"
    lines = [f"™️ <b>Gaceta PI</b> — {tipo_str}"]
    for item in items[:2]:
        signo = item.get("signo_solicitado", "")[:50]
        solicitante = item.get("solicitante", "")[:40]
        tipo = item.get("tipo_solicitud", "")
        lines.append(f"• {signo} ({tipo}) — {solicitante}")
    return "\n".join(lines)


def _build_otras_fuentes_message(date: Date, fecha: str) -> str | None:
    date_str = date.isoformat()
    sections = []

    loaders = [
        (DATA_PROCESSED / "indecopi-alertas" / f"{date_str}.json", _section_indecopi),
        (DATA_PROCESSED / "consumidor" / f"{date_str}.json", _section_consumidor),
        (DATA_PROCESSED / "tribunal-fiscal" / f"{date_str}.json", _section_tribunal),
        (DATA_PROCESSED / "gaceta-pi" / f"{date_str}.json", _section_gaceta),
    ]

    for path, builder in loaders:
        data = _load_json(path)
        if data:
            section = builder(data)
            if section:
                sections.append(section)

    if not sections:
        return None

    header = f"📊 <b>Otras fuentes</b> · {fecha}\n"
    return header + "\n\n".join(sections)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    load_dotenv()
    args = parse_args()

    target = _resolve_date(args.date)
    fecha = _fecha_es(target)
    date_str = target.isoformat()

    ep_path = DATA_PROCESSED / "elperuano" / f"{date_str}.json"
    if not ep_path.exists():
        ep_path = DATA_PROCESSED / f"{date_str}.json"
    if not ep_path.exists():
        logger.error("No El Peruano data at %s", ep_path)
        return 1

    ep_data = _load_json(ep_path)
    pdf_path = PDFS_DIR / f"{date_str}.pdf"

    msg1_caption = _build_pdf_caption(ep_data, fecha)
    msg2 = _build_destacadas_message(ep_data, fecha)
    msg3 = _build_otras_fuentes_message(target, fecha)

    if args.dry_run:
        sep = "=" * 60
        print(f"{sep}\nMENSAJE 1 — PDF caption:\n{sep}")
        print(f"PDF: {pdf_path}")
        print(msg1_caption)
        if msg2:
            print(f"\n{sep}\nMENSAJE 2 — Normas destacadas + Concesiones:\n{sep}")
            print(msg2)
        else:
            print("\n[Mensaje 2 omitido — sin normas alto ni concesiones]")
        if msg3:
            print(f"\n{sep}\nMENSAJE 3 — Otras fuentes:\n{sep}")
            print(msg3)
        else:
            print("\n[Mensaje 3 omitido — sin contenido en otras fuentes]")
        return 0

    if not pdf_path.exists():
        logger.error("PDF not found at %s — run build.py first", pdf_path)
        return 2

    from scripts.lib.telegram import TelegramClient
    client = TelegramClient()

    client.send_document(pdf_path, msg1_caption)
    logger.info("Sent PDF (msg 1)")

    if msg2:
        client.send_message(msg2)
        logger.info("Sent normas destacadas + concesiones (msg 2)")

    if msg3:
        client.send_message(msg3)
        logger.info("Sent otras fuentes (msg 3)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
