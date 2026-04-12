"""El Peruano summarizer — adapter wrapping the existing Gemini client."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime
from typing import Any

from scripts.lib.gemini import GeminiClient
from scripts.lib.schemas import (
    PROMPT_VERSION,
    DiaProcesado,
    DocumentoSeccion,
    IndexEntry,
    NormaCruda,
    NormaResumida,
    StatsDia,
)

logger = logging.getLogger(__name__)


class ElPeruanoSummarizer:
    source_slug = "elperuano"

    def summarize_day(self, parsed_data: dict[str, Any]) -> dict[str, Any]:
        """Summarize El Peruano parsed data using Gemini.

        Input: dict with 'normas' (list[NormaCruda dicts]) and 'documentos'.
        Output: DiaProcesado as a JSON-serializable dict.
        """
        normas_raw = [NormaCruda(**n) for n in parsed_data["normas"]]
        documentos = [DocumentoSeccion(**d) for d in parsed_data["documentos"]]

        client = GeminiClient()
        logger.info("Summarizing %d norms in batches", len(normas_raw))
        summarized = client.summarize_all(normas_raw)

        stats = _build_stats(summarized, len(documentos))
        dia = DiaProcesado(
            fecha=parsed_data["fecha"],
            normas=summarized,
            documentos=documentos,
            stats=stats,
            generated_at=datetime.utcnow().isoformat() + "Z",
        )
        return dia.model_dump(mode="json")

    def is_stale(self, existing_data: dict[str, Any]) -> bool:
        """Check if existing data needs re-summarization."""
        existing_versions = {
            n.get("prompt_version", 0) for n in existing_data.get("normas", [])
        }
        if not existing_versions:
            return True
        return not all(v >= PROMPT_VERSION for v in existing_versions)

    def make_index_entry(self, processed_data: dict[str, Any]) -> dict[str, Any]:
        """Build an index entry from processed data."""
        stats = processed_data.get("stats", {})
        return IndexEntry(
            fecha=processed_data["fecha"],
            total_normas=stats.get("total_normas", 0),
            alto=stats.get("alto", 0),
            medio=stats.get("medio", 0),
            bajo=stats.get("bajo", 0),
        ).model_dump(mode="json")


def _build_stats(normas: list[NormaResumida], n_docs: int) -> StatsDia:
    counts = Counter(n.impacto.value for n in normas)
    sectores = Counter(s for n in normas for s in n.sectores)
    return StatsDia(
        total_normas=len(normas),
        alto=counts.get("alto", 0),
        medio=counts.get("medio", 0),
        bajo=counts.get("bajo", 0),
        sectores_top=sectores.most_common(6),
        documentos_otras_secciones=n_docs,
    )
