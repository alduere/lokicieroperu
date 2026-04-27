"""Extract mining concession records from El Peruano PDF bulletins using Gemini."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

import requests
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

MODEL = "gemini-2.5-flash-lite"

PROMPT = """Eres un analista minero peruano. El siguiente PDF es un boletín de
concesiones mineras del Diario Oficial El Peruano publicado por INGEMMET.

Extrae TODOS los registros de concesiones que aparecen en el documento.
Para cada concesión devuelve un objeto JSON con estos campos:
- titular: nombre completo del titular (persona natural o empresa)
- mineral: tipo de mineral principal (ej: "Oro", "Cobre", "Plata", "Zinc", "No metálico", etc.)
- hectareas: área en hectáreas como número (solo el número, sin unidad)
- departamento: departamento donde se ubica
- provincia: provincia donde se ubica (si aparece)
- codigo: código o número de expediente de la concesión (si aparece)

Si el documento no contiene registros de concesiones individuales (es solo
una portada o índice), devuelve una lista vacía.

Devuelve estrictamente: {"concesiones": [...]}"""


@dataclass
class Concesion:
    titular: str
    mineral: str
    hectareas: float | None
    departamento: str
    provincia: str | None
    codigo: str | None


def _download_pdf(url: str, timeout: int = 30) -> bytes | None:
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        return resp.content
    except Exception as exc:
        logger.warning("Failed to download %s: %s", url, exc)
        return None


def _extract_from_pdf(client: genai.Client, pdf_bytes: bytes) -> list[Concesion]:
    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                    types.Part.from_text(text=PROMPT),
                ],
            ),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
                max_output_tokens=8192,
            ),
        )
        import json
        data = json.loads(resp.text or "{}")
        records = []
        for item in data.get("concesiones", []):
            try:
                records.append(Concesion(
                    titular=item.get("titular", "").strip(),
                    mineral=item.get("mineral", "").strip(),
                    hectareas=float(item["hectareas"]) if item.get("hectareas") else None,
                    departamento=item.get("departamento", "").strip(),
                    provincia=item.get("provincia", "").strip() or None,
                    codigo=item.get("codigo", "").strip() or None,
                ))
            except Exception as exc:
                logger.debug("Skipping malformed record: %s", exc)
        return records
    except Exception as exc:
        logger.warning("Gemini extraction failed: %s", exc)
        return []


def extract_concesiones(documentos: list[dict]) -> list[Concesion]:
    """Download and extract concession records from all PDF bulletins."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not set — skipping concesiones extraction")
        return []

    client = genai.Client(api_key=api_key)
    all_concesiones: list[Concesion] = []

    pdf_docs = [d for d in documentos if d.get("seccion") == "concesiones_mineras"]
    logger.info("Extracting concesiones from %d PDFs", len(pdf_docs))

    for i, doc in enumerate(pdf_docs):
        url = doc.get("descarga_url", "")
        if not url:
            continue
        pdf_bytes = _download_pdf(url)
        if not pdf_bytes:
            continue
        records = _extract_from_pdf(client, pdf_bytes)
        logger.info("PDF %d/%d → %d concesiones", i + 1, len(pdf_docs), len(records))
        all_concesiones.extend(records)
        if i < len(pdf_docs) - 1:
            time.sleep(1.0)

    return all_concesiones


def format_concesiones_section(concesiones: list[Concesion], n_pdfs: int) -> str | None:
    """Format the concesiones block for the Telegram caption."""
    if not concesiones:
        if n_pdfs > 0:
            return f"⛏️ <b>Concesiones Mineras</b> — {n_pdfs} boletín{'es' if n_pdfs != 1 else ''} (sin registros extraíbles)"
        return None

    # Group by mineral
    from collections import Counter
    minerales = Counter(c.mineral for c in concesiones if c.mineral)
    total = len(concesiones)

    mineral_str = "  ·  ".join(f"{m}: {n}" for m, n in minerales.most_common(4))
    lines = [f"⛏️ <b>Concesiones Mineras</b> — {total} otorgada{'s' if total != 1 else ''}  ({mineral_str})"]

    # Show up to 4 records, preferring gold/copper/silver
    priority = {"Oro", "Cobre", "Plata", "Zinc"}
    sorted_c = sorted(concesiones, key=lambda c: (c.mineral not in priority, c.mineral))
    for c in sorted_c[:4]:
        ha = f" — {c.hectareas:.0f} ha" if c.hectareas else ""
        if c.departamento and c.provincia:
            loc = f" — {c.departamento} / {c.provincia}"
        elif c.departamento:
            loc = f" — {c.departamento}"
        else:
            loc = ""
        lines.append(f"• {c.titular[:45]} ({c.mineral}{ha}{loc})")

    if total > 4:
        lines.append(f"  <i>...y {total - 4} más</i>")

    return "\n".join(lines)
