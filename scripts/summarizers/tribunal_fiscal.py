"""Tribunal Fiscal summarizer.

Uses Gemini to summarize tax court resolutions (sumillas) for tax
professionals, classifying by tax topic and impact level.
"""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from datetime import datetime
from typing import Any

from scripts.lib.schemas import (
    TRIBUNAL_FISCAL_PROMPT_VERSION,
    DiaTFProcesado,
    Impacto,
    ResolucionTFCruda,
    ResolucionTFResumida,
    StatsTFDia,
    TFIndexEntry,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres un analista tributario peruano experto en jurisprudencia del Tribunal Fiscal.
Tu trabajo es clasificar resoluciones del Tribunal Fiscal para contadores, abogados
tributaristas y asesores fiscales.

Recibes un lote de resoluciones en JSON (con su sumilla). Para cada una devuelves UN objeto con:

1. id  →  el id de la entrada, sin modificar.

2. resumen  →  2-3 oraciones. Qué se resolvió, cuál es el criterio adoptado por el
   Tribunal, y qué implicancia práctica tiene para los contribuyentes. Sin relleno.

3. impacto  →  "alto", "medio" o "bajo".
   • alto: establece o modifica criterio de observancia obligatoria, cambia
     interpretación consolidada, afecta a un gran número de contribuyentes,
     resoluciones de Sala Plena
   • medio: resolución relevante para un sector específico, confirma criterio
     importante, caso con monto significativo
   • bajo: confirma criterio ya establecido, caso rutinario, procedimiento
     administrativo menor

4. impacto_razon  →  una oración explicando el nivel de impacto.

5. tema_tributario  →  uno de: "IGV", "Impuesto a la Renta", "Aduanas",
   "Municipales", "Procedimiento Tributario", "ITAN", "ITF", "ISC",
   "Contribuciones", "Otros".

6. tags  →  3-5 palabras clave (lowercase, español).

Devuelve {"resultados": [...]} con el array de la misma longitud que la entrada."""

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
                    "tema_tributario": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "id",
                    "resumen",
                    "impacto",
                    "impacto_razon",
                    "tema_tributario",
                    "tags",
                ],
            },
        }
    },
    "required": ["resultados"],
}


class TribunalFiscalSummarizer:
    source_slug = "tribunal-fiscal"

    def summarize_day(self, parsed_data: dict[str, Any]) -> dict[str, Any]:
        """Summarize Tribunal Fiscal resolutions using Gemini."""
        items_raw = [ResolucionTFCruda(**item) for item in parsed_data["items"]]

        if not items_raw:
            return self._empty_day(parsed_data["fecha"])

        summarized = self._summarize_with_gemini(items_raw)

        salas = Counter(r.sala or "desconocida" for r in summarized)
        stats = StatsTFDia(
            total_resoluciones=len(summarized),
            por_sala=salas.most_common(20),
        )

        dia = DiaTFProcesado(
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
        return not all(v >= TRIBUNAL_FISCAL_PROMPT_VERSION for v in versions)

    def make_index_entry(self, processed_data: dict[str, Any]) -> dict[str, Any]:
        """Build an index entry from processed data."""
        return TFIndexEntry(
            fecha=processed_data["fecha"],
            total_resoluciones=processed_data.get("stats", {}).get(
                "total_resoluciones", 0
            ),
        ).model_dump(mode="json")

    def _summarize_with_gemini(
        self, resoluciones: list[ResolucionTFCruda]
    ) -> list[ResolucionTFResumida]:
        """Run Gemini summarization on the resolutions batch."""
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.warning(
                "GEMINI_API_KEY not set — returning unsummarized resolutions"
            )
            return [self._fallback(r) for r in resoluciones]

        client = genai.Client(api_key=api_key)

        payload = [
            {
                "id": r.id,
                "numero_rtf": r.numero_rtf,
                "sala": r.sala or "",
                "sumilla": r.sumilla or "",
                "numero_expediente": r.numero_expediente or "",
            }
            for r in resoluciones
        ]

        prompt = (
            "LOTE DE RESOLUCIONES DEL TRIBUNAL FISCAL A CLASIFICAR\n"
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
            logger.warning(
                "Gemini failed for resolutions: %s — using fallback", exc
            )
            return [self._fallback(r) for r in resoluciones]

        resultados = {r.get("id"): r for r in (data.get("resultados") or [])}
        out: list[ResolucionTFResumida] = []
        for r in resoluciones:
            result = resultados.get(r.id)
            if not result:
                out.append(self._fallback(r))
                continue
            try:
                out.append(
                    ResolucionTFResumida(
                        **r.model_dump(),
                        resumen=result.get("resumen"),
                        impacto=Impacto(result.get("impacto", "medio")),
                        impacto_razon=result.get("impacto_razon"),
                        tema_tributario=result.get("tema_tributario"),
                        tags=[
                            t.lower().strip() for t in (result.get("tags") or [])
                        ][:5],
                        prompt_version=TRIBUNAL_FISCAL_PROMPT_VERSION,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Could not build summary for resolution %s: %s", r.id, exc
                )
                out.append(self._fallback(r))

        return out

    @staticmethod
    def _fallback(r: ResolucionTFCruda) -> ResolucionTFResumida:
        return ResolucionTFResumida(
            **r.model_dump(),
            resumen=None,
            impacto=Impacto.MEDIO,
            impacto_razon=None,
            tema_tributario=None,
            tags=[],
            prompt_version=0,
        )

    def _empty_day(self, fecha: str) -> dict[str, Any]:
        dia = DiaTFProcesado(
            fecha=fecha,
            items=[],
            stats=StatsTFDia(total_resoluciones=0),
            generated_at=datetime.utcnow().isoformat() + "Z",
        )
        return dia.model_dump(mode="json")
