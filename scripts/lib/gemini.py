"""Gemini 2.5 Flash Lite client for batch-summarizing Peruvian norms.

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

from scripts.lib.schemas import PROMPT_VERSION, Impacto, NormaCruda, NormaResumida

logger = logging.getLogger(__name__)

MODEL = "gemini-2.5-flash-lite"
BATCH_SIZE = 25  # 60-80 norms/day → 2-4 batches/day. Fits comfortably in any tier.
RATE_LIMIT_SECONDS = 1.0  # Paid tier has 4000 RPM; throttle just for politeness

SYSTEM_PROMPT = """Eres un analista legal peruano senior. Tu trabajo es resumir
normas legales del Diario Oficial El Peruano para profesionales (abogados,
periodistas, empresarios, gestores públicos) que necesitan entender en 30
segundos qué dispone cada norma y si los afecta.

Recibes un lote de normas en JSON. Para cada una devuelves UN objeto con
ESTOS campos exactos:

══════════════════════════════════════════════════════════════
1. id  →  el id que viene en la entrada, sin modificar.

2. resumen_ejecutivo  →  4 a 6 oraciones en español neutro peruano.
   Estructura obligatoria:
   • Oración 1-2: QUÉ dispone concretamente la norma. No copies la sumilla:
     parafraséala explicando lo dispuesto en términos de un profesional, no
     de un funcionario.
   • Oración 3: A QUIÉN afecta directamente y cómo (sector, empresa, gremio,
     ciudadanía, una entidad puntual).
   • Oración 4-5: CONTEXTO regulatorio relevante (¿modifica algo previo?,
     ¿deroga?, ¿implementa una ley superior?, ¿es la primera vez que se
     regula esto?).
   • Oración 6 (opcional): vigencia o fecha clave si está clara.

   PROHIBIDO:
   - Empezar con "La presente norma..." o "Se dispone..." o "Mediante..."
   - Usar lenguaje legal vacío como "en el marco de", "se considera relevante"
   - Inventar datos que no estén en la sumilla
   - Frases de relleno como "es importante porque..." o "esta acción permite..."

   Si la sumilla es trivial (designación, viaje, encargo de funciones,
   ratificación), tu resumen también debe ser breve (2-3 oraciones).

3. cambios_clave  →  lista de 1 a 3 bullets cortos (máx 12 palabras cada uno)
   con los cambios concretos que introduce la norma. Ejemplos:
   ["Modifica el cálculo del IGV para servicios digitales",
    "Reduce el plazo de devolución de tributos a 15 días"]
   Si la norma no introduce cambios sustantivos (designación, viaje, etc.),
   devuelve una sola entrada describiendo qué hace.

4. a_quien_afecta  →  una sola oración (máx 20 palabras) identificando los
   destinatarios prácticos. Ejemplos:
   "Empresas exportadoras de servicios y la SUNAT."
   "Trabajadores del régimen agrario y empleadores del sector."
   "Únicamente al funcionario designado y la PCM."

5. vigencia  →  string corto sobre cuándo entra en vigencia. Ejemplos válidos:
   "Desde el 1 de mayo de 2026"
   "Desde su publicación (10/04/2026)"
   "30 días después de su publicación"
   Si no se puede inferir, usa null.

6. impacto  →  "alto", "medio" o "bajo".
   • alto: cambios regulatorios sectoriales reales, modificaciones a
     leyes/reglamentos vigentes, creación o eliminación de tributos/aranceles/
     subsidios/exoneraciones, decretos de urgencia, declaratorias de
     emergencia, normas que afectan a >100,000 personas, o que modifican el
     régimen económico/laboral/sanitario de un sector entero.
   • medio: resoluciones operativas con efecto sectorial puntual,
     autorizaciones a entidades específicas, modificaciones de procedimientos
     administrativos visibles, calendarios oficiales, aprobación de
     reglamentos internos importantes, ordenanzas regionales/municipales con
     impacto local real.
   • bajo: designaciones, ratificaciones, encargos de funciones, autorización
     de viajes, felicitaciones, asuntos puramente internos de una entidad,
     fe de erratas, ceremonias.

7. impacto_razon  →  una oración explicando POR QUÉ ese nivel de impacto.
   Ejemplos:
   "Modifica el reglamento del IGV; afecta a todas las empresas exportadoras."
   "Designación interna sin efectos hacia terceros."
   "Autoriza viaje individual de un funcionario."

8. sectores  →  lista de 1 a 4 slugs (lowercase, sin tildes, separados por
   guion bajo) ordenados de más a menos relevante. Catálogo válido:
   economia, tributacion, financiero, banca, seguros, mercado_valores,
   trabajo, pensiones, salud, sanidad, educacion, ciencia, transporte,
   aeronautica, maritimo, mineria, hidrocarburos, energia, electricidad,
   agricultura, ganaderia, pesqueria, ambiente, agua, vivienda, construccion,
   urbanismo, cultura, turismo, comercio_exterior, aduanas, mype, comercio,
   tecnologia, telecomunicaciones, justicia, judicial, defensa, fuerzas_armadas,
   policia, interior, migraciones, relaciones_exteriores, electoral,
   gobierno_local, gobierno_regional, congreso, organismos_constitucionales,
   contraloria, defensoria, derechos_humanos, mujer, familia, niñez,
   discapacidad, pueblos_indigenas, medioambiente_urbano, residuos_solidos,
   transparencia, contrataciones_publicas, presupuesto_publico, tesoro_publico,
   modernizacion_estado, administracion_publica.

   El primero debe ser el sector PRINCIPAL (no general). Solo usa
   "administracion_publica" si genuinamente no encaja en ningún sector
   específico (designaciones internas, viajes, etc.).

9. tags  →  3 a 5 palabras clave libres (lowercase, español, sin numerales).
   Buenos tags: "iva", "exportadores", "viaje oficial", "reglamento",
   "designacion", "tarifa". Malos tags (NO USES): "norma", "perú", "ley",
   "publicado", "ministerio".

══════════════════════════════════════════════════════════════
Devuelve estrictamente {"resultados": [...]} con el array EXACTO de la misma
longitud que la entrada y los ids coincidentes."""


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
                    "cambios_clave": {"type": "array", "items": {"type": "string"}},
                    "a_quien_afecta": {"type": "string"},
                    "vigencia": {"type": "string"},
                    "impacto": {"type": "string", "enum": ["alto", "medio", "bajo"]},
                    "impacto_razon": {"type": "string"},
                    "sectores": {"type": "array", "items": {"type": "string"}},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "id",
                    "resumen_ejecutivo",
                    "cambios_clave",
                    "a_quien_afecta",
                    "impacto",
                    "impacto_razon",
                    "sectores",
                    "tags",
                ],
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
                temperature=0.25,
                max_output_tokens=32768,  # 25 norms × ~600 tokens output ≈ 15k. Safe margin.
            ),
        )
        text = resp.text or "{}"
        return json.loads(text)

    def summarize_batch(self, normas: list[NormaCruda]) -> list[NormaResumida]:
        if not normas:
            return []

        payload = [
            {
                "id": n.id,
                "tipo": n.tipo,
                "tipo_corto": n.tipo_corto,
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
                        resumen_ejecutivo=r.get("resumen_ejecutivo") or None,
                        cambios_clave=[
                            s.strip() for s in (r.get("cambios_clave") or []) if s and s.strip()
                        ][:3],
                        a_quien_afecta=(r.get("a_quien_afecta") or "").strip() or None,
                        vigencia=(r.get("vigencia") or "").strip() or None,
                        impacto=Impacto(r.get("impacto", "medio")),
                        impacto_razon=(r.get("impacto_razon") or "").strip() or None,
                        sectores=[s.lower().strip() for s in (r.get("sectores") or [])][:4]
                        or ["administracion_publica"],
                        tags=[t.lower().strip() for t in (r.get("tags") or [])][:5],
                        prompt_version=PROMPT_VERSION,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not build summary for %s: %s — fallback", n.id, exc)
                out.append(self._fallback(n))
        return out

    def summarize_all(self, normas: list[NormaCruda]) -> list[NormaResumida]:
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
            cambios_clave=[],
            a_quien_afecta=None,
            vigencia=None,
            impacto=Impacto.MEDIO,
            impacto_razon=None,
            sectores=["administracion_publica"],
            tags=[],
            prompt_version=0,
        )
