"""INDECOPI Alertas de Consumo summarizer.

Alerts already come with rich structured data from the API (product name,
brand, risk description, measures). We use Gemini to generate a concise
consumer-facing summary and impact classification.
"""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from datetime import datetime
from typing import Any

from scripts.lib.schemas import (
    ALERTAS_PROMPT_VERSION,
    AlertaCruda,
    AlertaResumida,
    AlertasIndexEntry,
    DiaAlertasProcesado,
    Impacto,
    StatsAlertasDia,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres un analista de protección al consumidor peruano. Tu trabajo es
clasificar alertas de consumo de INDECOPI para consumidores, abogados y periodistas.

Recibes un lote de alertas en JSON. Para cada una devuelves UN objeto con:

1. id  →  el id de la entrada, sin modificar.

2. resumen  →  2-3 oraciones. Qué producto está alertado, cuál es el riesgo
   concreto, y qué deben hacer los consumidores afectados. Sin relleno.

3. impacto  →  "alto", "medio" o "bajo".
   • alto: riesgo de lesiones graves, muerte, alimentos contaminados,
     medicamentos defectuosos, retiro masivo (>10,000 unidades), vehículos
   • medio: riesgo de lesiones menores, productos defectuosos con alcance
     limitado, productos electrónicos con falla de seguridad
   • bajo: defectos cosméticos, etiquetado incorrecto, incumplimiento menor

4. impacto_razon  →  una oración explicando el nivel de impacto.

5. tags  →  3-5 palabras clave (lowercase, español).

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
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "resumen", "impacto", "impacto_razon", "tags"],
            },
        }
    },
    "required": ["resultados"],
}


class IndecopiAlertasSummarizer:
    source_slug = "indecopi-alertas"

    def summarize_day(self, parsed_data: dict[str, Any]) -> dict[str, Any]:
        """Summarize INDECOPI alerts using Gemini."""
        items_raw = [AlertaCruda(**item) for item in parsed_data["items"]]

        if not items_raw:
            return self._empty_day(parsed_data["fecha"])

        summarized = self._summarize_with_gemini(items_raw)

        cats = Counter(a.categoria or "otros" for a in summarized)
        stats = StatsAlertasDia(
            total_alertas=len(summarized),
            por_categoria=cats.most_common(10),
        )

        dia = DiaAlertasProcesado(
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
        return not all(v >= ALERTAS_PROMPT_VERSION for v in versions)

    def make_index_entry(self, processed_data: dict[str, Any]) -> dict[str, Any]:
        """Build an index entry from processed data."""
        return AlertasIndexEntry(
            fecha=processed_data["fecha"],
            total_alertas=processed_data.get("stats", {}).get("total_alertas", 0),
        ).model_dump(mode="json")

    def _summarize_with_gemini(self, alertas: list[AlertaCruda]) -> list[AlertaResumida]:
        """Run Gemini summarization on the alerts batch."""
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not set — returning unsummarized alerts")
            return [self._fallback(a) for a in alertas]

        client = genai.Client(api_key=api_key)

        payload = [
            {
                "id": a.id,
                "titulo": a.titulo,
                "sumilla": a.sumilla or "",
                "categoria": a.categoria or "",
                "producto": a.nombre_producto or "",
                "marca": a.marca or "",
                "modelo": a.modelo or "",
                "riesgo": a.descripcion_riesgo or "",
                "efectos": a.descripcion_efectos or "",
                "medidas": a.medidas_adoptadas or "",
            }
            for a in alertas
        ]

        prompt = (
            "LOTE DE ALERTAS DE CONSUMO A CLASIFICAR\n"
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
            logger.warning("Gemini failed for alerts: %s — using fallback", exc)
            return [self._fallback(a) for a in alertas]

        resultados = {r.get("id"): r for r in (data.get("resultados") or [])}
        out: list[AlertaResumida] = []
        for a in alertas:
            r = resultados.get(a.id)
            if not r:
                out.append(self._fallback(a))
                continue
            try:
                out.append(
                    AlertaResumida(
                        **a.model_dump(),
                        resumen=r.get("resumen"),
                        impacto=Impacto(r.get("impacto", "medio")),
                        impacto_razon=r.get("impacto_razon"),
                        tags=[t.lower().strip() for t in (r.get("tags") or [])][:5],
                        prompt_version=ALERTAS_PROMPT_VERSION,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not build summary for alert %s: %s", a.id, exc)
                out.append(self._fallback(a))

        return out

    @staticmethod
    def _fallback(a: AlertaCruda) -> AlertaResumida:
        return AlertaResumida(
            **a.model_dump(),
            resumen=None,
            impacto=Impacto.MEDIO,
            impacto_razon=None,
            tags=[],
            prompt_version=0,
        )

    def _empty_day(self, fecha: str) -> dict[str, Any]:
        dia = DiaAlertasProcesado(
            fecha=fecha,
            items=[],
            stats=StatsAlertasDia(total_alertas=0),
            generated_at=datetime.utcnow().isoformat() + "Z",
        )
        return dia.model_dump(mode="json")