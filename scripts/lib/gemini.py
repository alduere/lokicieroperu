"""Gemini 2.5 Flash client for batch-summarizing Peruvian norms.

We batch up to BATCH_SIZE norms per API call so we stay well under the
free-tier daily request quota. The model returns an array of structured
JSON objects, one per norm, in the same order.
"""

from __future__ import annotations

import json
import logging
import os
import time

from google import genai
from google.genai import types
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from scripts.lib.schemas import Impacto, NormaCruda, NormaResumida

logger = logging.getLogger(__name__)

MODEL = "gemini-2.5-flash-lite"
BATCH_SIZE = 15  # 60-80 norms/day → 4-6 batches/day. Flash Lite free tier: 1000 RPD / 15 RPM.
RATE_LIMIT_SECONDS = 4.5  # 15 RPM free tier cap → 1 call every 4.5s leaves headroom

SYSTEM_PROMPT = """Eres un analista legal peruano experto. Tu tarea es resumir
un lote de normas legales publicadas en el Diario Oficial El Peruano para una
audiencia profesional pero general (empresarios, abogados, periodistas,
ciudadanos informados).

Recibirás un array JSON de normas. Para cada una, devuelves UN objeto con:

1. **id**: el id que viene en la entrada, sin modificar.

2. **resumen_ejecutivo**: 4 a 6 oraciones en español neutro peruano. Explica:
   - QUÉ dispone la norma (lo concreto, no la frase oficial)
   - A QUIÉN afecta (sector, tipo de empresa, ciudadanía, una entidad puntual)
   - DESDE CUÁNDO entra en vigencia, si se puede inferir
   - Por qué importa (1 frase, sin opinar)
   Evita lenguaje legal vacío. Si la sumilla solo dice "designan a X", el
   resumen también es breve. No inventes datos.

3. **impacto**: clasifica como "alto", "medio" o "bajo".
   - alto: cambios regulatorios sectoriales, modificaciones a leyes/reglamentos,
     creación o eliminación de impuestos/aranceles/subsidios, decretos de urgencia,
     emergencias sanitarias, normas que afectan a >100k personas o a un sector
     económico completo.
   - medio: resoluciones operativas con efecto sectorial puntual, autorizaciones
     a entidades, modificaciones de procedimientos administrativos, calendarios.
   - bajo: designaciones, ratificaciones, autorizaciones de viaje, encargos de
     funciones, felicitaciones, asuntos puramente internos.

4. **sectores**: lista de slugs (lowercase, sin tildes, separados por guion bajo)
   que apliquen. Ejemplos válidos: economia, tributacion, salud, educacion,
   trabajo, transporte, mineria, energia, agricultura, justicia, interior,
   defensa, ambiente, vivienda, cultura, turismo, comercio_exterior, mype,
   tecnologia, exportadores, financiero, seguros, telecomunicaciones,
   aeronautica, pesqueria, gobierno_local, gobierno_regional, congreso,
   judicial, electoral. Máximo 4. Si no encaja en ninguno específico, usa
   ["administracion_publica"].

5. **tags**: 1 a 5 palabras clave libres (lowercase, español).

Devuelve estrictamente un JSON con la forma {"resultados": [...]}. El array
debe tener exactamente la misma longitud que la entrada y los ids deben
coincidir."""


_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "resultados": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "resumen_ejecutivo": {"type": "string"},
                    "impacto": {"type": "string", "enum": ["alto", "medio", "bajo"]},
                    "sectores": {"type": "array", "items": {"type": "string"}},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "resumen_ejecutivo", "impacto", "sectores", "tags"],
            },
        }
    },
    "required": ["resultados"],
}


class GeminiClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY env var not set")
        self.client = genai.Client(api_key=self.api_key)
        self._last_call = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < RATE_LIMIT_SECONDS:
            time.sleep(RATE_LIMIT_SECONDS - elapsed)
        self._last_call = time.monotonic()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=4, min=8, max=120),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _call_batch(self, prompt: str) -> dict:
        self._throttle()
        resp = self.client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=_RESPONSE_SCHEMA,
                temperature=0.3,
                max_output_tokens=8192,
            ),
        )
        text = resp.text or "{}"
        return json.loads(text)

    def summarize_batch(self, normas: list[NormaCruda]) -> list[NormaResumida]:
        """Summarize a batch of norms with one API call.

        On any error or missing item in the response, falls back to a
        minimal NormaResumida (no resumen, impacto=medio).
        """
        if not normas:
            return []

        # Build a compact JSON payload
        payload = [
            {
                "id": n.id,
                "tipo": n.tipo,
                "numero": n.numero,
                "entidad": n.entidad_emisora,
                "fecha": n.fecha_publicacion.isoformat(),
                "extraordinaria": n.edicion_extraordinaria,
                "titulo": n.titulo_oficial,
                "sumilla": n.sumilla,
            }
            for n in normas
        ]
        prompt = (
            "LOTE DE NORMAS A RESUMIR\n"
            f"Cantidad: {len(payload)}\n\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            'Devuelve {"resultados": [...]} con la misma cantidad y los mismos ids.'
        )

        try:
            data = self._call_batch(prompt)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini batch failed: %s — falling back for %d norms", exc, len(normas))
            return [self._fallback(n) for n in normas]

        resultados = {r.get("id"): r for r in (data.get("resultados") or [])}
        out: list[NormaResumida] = []
        for n in normas:
            r = resultados.get(n.id)
            if not r:
                logger.warning("Gemini batch missing id %s — fallback", n.id)
                out.append(self._fallback(n))
                continue
            try:
                out.append(
                    NormaResumida(
                        **n.model_dump(),
                        resumen_ejecutivo=r.get("resumen_ejecutivo"),
                        impacto=Impacto(r.get("impacto", "medio")),
                        sectores=[s.lower().strip() for s in (r.get("sectores") or [])][:4],
                        tags=[t.lower().strip() for t in (r.get("tags") or [])][:5],
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not build summary for %s: %s — fallback", n.id, exc)
                out.append(self._fallback(n))
        return out

    def summarize_all(self, normas: list[NormaCruda]) -> list[NormaResumida]:
        """Summarize a list of any size by chunking into BATCH_SIZE batches."""
        out: list[NormaResumida] = []
        for i in range(0, len(normas), BATCH_SIZE):
            chunk = normas[i : i + BATCH_SIZE]
            logger.info(
                "Gemini batch %d/%d — %d norms",
                i // BATCH_SIZE + 1,
                (len(normas) + BATCH_SIZE - 1) // BATCH_SIZE,
                len(chunk),
            )
            out.extend(self.summarize_batch(chunk))
        return out

    @staticmethod
    def _fallback(n: NormaCruda) -> NormaResumida:
        return NormaResumida(
            **n.model_dump(),
            resumen_ejecutivo=None,
            impacto=Impacto.MEDIO,
            sectores=["administracion_publica"],
            tags=[],
        )
