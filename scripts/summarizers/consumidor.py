"""consumidor.gob.pe summarizer.

Uses Gemini to classify and summarize consumer protection news posts
from INDECOPI's WordPress portal.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any

from scripts.lib.schemas import (
    CONSUMIDOR_PROMPT_VERSION,
    DiaNoticiasProcesado,
    Impacto,
    NoticiaCruda,
    NoticiaResumida,
    NoticiasIndexEntry,
    StatsNoticiasDia,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres un analista de protección al consumidor peruano. Clasificas noticias de consumidor.gob.pe. Para cada noticia devuelves: id, resumen (2-3 oraciones), impacto (alto/medio/bajo), impacto_razon, tags (3-5)."""

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
                    "impacto": {"type": "string", "enum": ["alto", "medio", "bajo"]},
                    "impacto_razon": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "resumen", "impacto", "impacto_razon", "tags"],
            },
        }
    },
    "required": ["resultados"],
}


class ConsumidorSummarizer:
    source_slug = "consumidor"

    def summarize_day(self, parsed_data: dict[str, Any]) -> dict[str, Any]:
        """Summarize consumer news posts using Gemini."""
        items_raw = [NoticiaCruda(**item) for item in parsed_data["items"]]

        if not items_raw:
            return self._empty_day(parsed_data["fecha"])

        summarized = self._summarize_with_gemini(items_raw)

        stats = StatsNoticiasDia(total_noticias=len(summarized))

        dia = DiaNoticiasProcesado(
            fecha=parsed_data["fecha"],
            items=summarized,
            stats=stats,
            generated_at=datetime.utcnow().isoformat() + "Z",
        )
        return dia.model_dump(mode="json")

    def is_stale(self, existing_data: dict[str, Any]) -> bool:
        """Check if existing data needs re-summarization."""
        versions = {
            item.get("prompt_version", 0) for item in existing_data.get("items", [])
        }
        if not versions:
            return True
        return not all(v >= CONSUMIDOR_PROMPT_VERSION for v in versions)

    def make_index_entry(self, processed_data: dict[str, Any]) -> dict[str, Any]:
        """Build an index entry from processed data."""
        return NoticiasIndexEntry(
            fecha=processed_data["fecha"],
            total_noticias=processed_data.get("stats", {}).get("total_noticias", 0),
        ).model_dump(mode="json")

    def _summarize_with_gemini(
        self, noticias: list[NoticiaCruda]
    ) -> list[NoticiaResumida]:
        """Run Gemini summarization on the news batch."""
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not set — returning unsummarized posts")
            return [self._fallback(n) for n in noticias]

        client = genai.Client(api_key=api_key)

        payload = [
            {
                "id": n.id,
                "titulo": n.titulo,
                "extracto": n.extracto or "",
            }
            for n in noticias
        ]

        prompt = (
            "LOTE DE NOTICIAS DE CONSUMIDOR A CLASIFICAR\n"
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
                    max_output_tokens=8192,
                ),
            )
            data = json.loads(resp.text or "{}")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini failed for noticias: %s — using fallback", exc)
            return [self._fallback(n) for n in noticias]

        resultados = {r.get("id"): r for r in (data.get("resultados") or [])}
        out: list[NoticiaResumida] = []
        for n in noticias:
            r = resultados.get(n.id)
            if not r:
                out.append(self._fallback(n))
                continue
            try:
                out.append(
                    NoticiaResumida(
                        **n.model_dump(),
                        resumen=r.get("resumen"),
                        impacto=Impacto(r.get("impacto", "medio")),
                        impacto_razon=r.get("impacto_razon"),
                        tags=[t.lower().strip() for t in (r.get("tags") or [])][:5],
                        prompt_version=CONSUMIDOR_PROMPT_VERSION,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not build summary for post %s: %s", n.id, exc)
                out.append(self._fallback(n))

        return out

    @staticmethod
    def _fallback(n: NoticiaCruda) -> NoticiaResumida:
        return NoticiaResumida(
            **n.model_dump(),
            resumen=None,
            impacto=Impacto.MEDIO,
            impacto_razon=None,
            tags=[],
            prompt_version=0,
        )

    def _empty_day(self, fecha: str) -> dict[str, Any]:
        dia = DiaNoticiasProcesado(
            fecha=fecha,
            items=[],
            stats=StatsNoticiasDia(total_noticias=0),
            generated_at=datetime.utcnow().isoformat() + "Z",
        )
        return dia.model_dump(mode="json")
