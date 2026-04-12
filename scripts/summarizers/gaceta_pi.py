"""INDECOPI Gaceta de Propiedad Industrial summarizer.

IP filings are already structured data — no AI summarization needed.
This summarizer passes through the scraped data, converts types, and
computes aggregate stats.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime
from typing import Any

from scripts.lib.schemas import (
    DiaGacetaProcesado,
    GacetaIndexEntry,
    SolicitudPICruda,
    SolicitudPIResumida,
    StatsGacetaDia,
)

logger = logging.getLogger(__name__)


class GacetaPISummarizer:
    """Summarizer for IP Gazette filings — pass-through with stats."""

    source_slug = "gaceta-pi"

    def summarize_day(self, parsed_data: dict[str, Any]) -> dict[str, Any]:
        """Convert raw filings to summarized format and compute stats."""
        items_raw = [SolicitudPICruda(**item) for item in parsed_data["items"]]

        if not items_raw:
            return self._empty_day(parsed_data["fecha"])

        # Pass-through: structured data needs no AI summarization
        summarized = [
            SolicitudPIResumida(**item.model_dump(), prompt_version=0)
            for item in items_raw
        ]

        tipo_counter = Counter(s.tipo_solicitud for s in summarized)
        stats = StatsGacetaDia(
            total_solicitudes=len(summarized),
            por_tipo=tipo_counter.most_common(10),
        )

        dia = DiaGacetaProcesado(
            fecha=parsed_data["fecha"],
            items=summarized,
            stats=stats,
            generated_at=datetime.utcnow().isoformat() + "Z",
        )
        return dia.model_dump(mode="json")

    def is_stale(self, existing_data: dict[str, Any]) -> bool:
        """Structured data never goes stale — no prompt versioning needed."""
        return False

    def make_index_entry(self, processed_data: dict[str, Any]) -> dict[str, Any]:
        """Build an index entry from processed data."""
        return GacetaIndexEntry(
            fecha=processed_data["fecha"],
            total_solicitudes=processed_data.get("stats", {}).get("total_solicitudes", 0),
        ).model_dump(mode="json")

    def _empty_day(self, fecha: str) -> dict[str, Any]:
        dia = DiaGacetaProcesado(
            fecha=fecha,
            items=[],
            stats=StatsGacetaDia(total_solicitudes=0),
            generated_at=datetime.utcnow().isoformat() + "Z",
        )
        return dia.model_dump(mode="json")
