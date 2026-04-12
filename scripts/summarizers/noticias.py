"""Press news summarizer (multi-source).

Uses Gemini to classify and summarize economic, financial, and political
news from Peruvian press sources (Gestión, El Comercio, RPP, Andina, etc.).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any

from scripts.lib.schemas import (
    FUENTE_DISPLAY,
    PRENSA_PROMPT_VERSION,
    DiaPrensa,
    PrensaCruda,
    PrensaIndexEntry,
    PrensaResumida,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres un analista económico y político peruano senior. Clasificas y resumes
noticias económicas, financieras y políticas del Perú para profesionales.

Para cada noticia devuelves: id, resumen (2-3 oraciones), categoria ("Economía"/"Finanzas"/"Política"), tags (3-5 keywords).

Devuelve {"resultados": [...]} con la misma cantidad y los mismos ids."""

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "resultados": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "resumen": {"type": "string"},
                    "categoria": {
                        "type": "string",
                        "enum": ["Economía", "Finanzas", "Política"],
                    },
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "resumen", "categoria", "tags"],
            },
        }
    },
    "required": ["resultados"],
}

_BATCH_SIZE = 20


class NoticiasSummarizer:
    source_slug = "noticias"

    def summarize_day(self, parsed_data: dict[str, Any]) -> dict[str, Any]:
        """Summarize press news articles using Gemini."""
        items_raw = [PrensaCruda(**item) for item in parsed_data["items"]]

        if not items_raw:
            return self._empty_day(parsed_data["fecha"])

        # Process in batches
        summarized: list[PrensaResumida] = []
        for i in range(0, len(items_raw), _BATCH_SIZE):
            batch = items_raw[i : i + _BATCH_SIZE]
            summarized.extend(self._summarize_with_gemini(batch))

        fuentes_activas = sorted({n.fuente for n in summarized})

        dia = DiaPrensa(
            fecha=parsed_data["fecha"],
            noticias=summarized,
            total=len(summarized),
            fuentes_activas=fuentes_activas,
            prompt_version=PRENSA_PROMPT_VERSION,
        )
        return dia.model_dump(mode="json")

    def is_stale(self, existing_data: dict[str, Any]) -> bool:
        """Check if existing data needs re-summarization."""
        versions = {
            item.get("prompt_version", "") for item in existing_data.get("noticias", [])
        }
        if not versions:
            return True
        return not all(v == PRENSA_PROMPT_VERSION for v in versions)

    def make_index_entry(self, processed_data: dict[str, Any]) -> dict[str, Any]:
        """Build an index entry from processed data."""
        from datetime import date as date_type

        fecha_val = processed_data["fecha"]
        if isinstance(fecha_val, str):
            fecha_val = date_type.fromisoformat(fecha_val)

        return PrensaIndexEntry(
            fecha=fecha_val,
            total_noticias=processed_data.get("total", 0),
            fuentes_activas=processed_data.get("fuentes_activas", []),
        ).model_dump(mode="json")

    def _summarize_with_gemini(
        self, noticias: list[PrensaCruda]
    ) -> list[PrensaResumida]:
        """Run Gemini summarization on a batch of news articles."""
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not set — returning unsummarized articles")
            return [self._fallback(n) for n in noticias]

        client = genai.Client(api_key=api_key)

        payload = [
            {
                "id": n.id,
                "titulo": n.titulo,
                "contenido": (n.contenido or "")[:500],  # truncate to save tokens
            }
            for n in noticias
        ]

        prompt = (
            "LOTE DE NOTICIAS DE PRENSA PERUANA A CLASIFICAR\n"
            f"Cantidad: {len(payload)}\n\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            'Devuelve {"resultados": [...]} con la misma cantidad y los mismos ids.'
        )

        try:
            resp = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=_RESPONSE_SCHEMA,
                    temperature=0.2,
                    max_output_tokens=16384,
                ),
            )
            data = json.loads(resp.text or "{}")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini failed for noticias batch: %s — using fallback", exc)
            return [self._fallback(n) for n in noticias]

        resultados = {r.get("id"): r for r in (data.get("resultados") or [])}
        out: list[PrensaResumida] = []
        for n in noticias:
            r = resultados.get(n.id)
            if not r:
                out.append(self._fallback(n))
                continue
            try:
                out.append(
                    PrensaResumida(
                        **n.model_dump(),
                        fuente_display=FUENTE_DISPLAY.get(n.fuente, ""),
                        resumen=r.get("resumen"),
                        categoria=r.get("categoria", "Economía"),
                        tags=[t.lower().strip() for t in (r.get("tags") or [])][:5],
                        prompt_version=PRENSA_PROMPT_VERSION,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Could not build summary for article %s: %s", n.id, exc
                )
                out.append(self._fallback(n))

        return out

    @staticmethod
    def _fallback(n: PrensaCruda) -> PrensaResumida:
        return PrensaResumida(
            **n.model_dump(),
            fuente_display=FUENTE_DISPLAY.get(n.fuente, ""),
            resumen=None,
            categoria="Economía",
            tags=[],
            prompt_version="",
        )

    def _empty_day(self, fecha: str) -> dict[str, Any]:
        dia = DiaPrensa(
            fecha=fecha,
            noticias=[],
            total=0,
            fuentes_activas=[],
            prompt_version=PRENSA_PROMPT_VERSION,
        )
        return dia.model_dump(mode="json")
