"""Run Gemini over the parsed normas and produce data/processed/<date>.json.

Idempotent: if the processed file already exists with the same norm IDs, skip.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

from scripts.lib.gemini import GeminiClient
from scripts.lib.schemas import (
    DiaProcesado,
    DocumentoSeccion,
    Index,
    IndexEntry,
    NormaCruda,
    NormaResumida,
    StatsDia,
)

logger = logging.getLogger("summarize")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_PROCESSED = REPO_ROOT / "data" / "processed"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Summarize parsed norms with Gemini")
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.add_argument("--force", action="store_true", help="Re-summarize even if file exists")
    return p.parse_args()


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


def _update_index(dia: DiaProcesado) -> None:
    index_path = DATA_PROCESSED / "index.json"
    entries: list[IndexEntry] = []
    if index_path.exists():
        try:
            existing = Index(**json.loads(index_path.read_text(encoding="utf-8")))
            entries = [e for e in existing.fechas if e.fecha != dia.fecha]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not parse existing index.json: %s", exc)
    entries.append(
        IndexEntry(
            fecha=dia.fecha,
            total_normas=dia.stats.total_normas,
            alto=dia.stats.alto,
            medio=dia.stats.medio,
            bajo=dia.stats.bajo,
        )
    )
    entries.sort(key=lambda e: e.fecha, reverse=True)
    Index(fechas=entries).model_dump_json(indent=2)
    index_path.write_text(
        Index(fechas=entries).model_dump_json(indent=2),
        encoding="utf-8",
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    load_dotenv()
    args = parse_args()

    target = datetime.strptime(args.date, "%Y-%m-%d").date()
    raw_dir = DATA_RAW / target.isoformat()
    parsed_path = raw_dir / "parsed.json"
    if not parsed_path.exists():
        logger.error("No parsed data at %s — run scrape.py first", parsed_path)
        return 1

    parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
    normas_raw = [NormaCruda(**n) for n in parsed["normas"]]
    documentos = [DocumentoSeccion(**d) for d in parsed["documentos"]]

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED / f"{target.isoformat()}.json"
    if out_path.exists() and not args.force:
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        existing_ids = {n["id"] for n in existing.get("normas", [])}
        if existing_ids == {n.id for n in normas_raw}:
            logger.info("All %d norms already summarized, skipping", len(normas_raw))
            return 0

    if not os.environ.get("GEMINI_API_KEY"):
        logger.error("GEMINI_API_KEY not set")
        return 2

    client = GeminiClient()
    logger.info("Summarizing %d norms in batches", len(normas_raw))
    summarized = client.summarize_all(normas_raw)

    dia = DiaProcesado(
        fecha=target,
        normas=summarized,
        documentos=documentos,
        stats=_build_stats(summarized, len(documentos)),
        generated_at=datetime.utcnow().isoformat() + "Z",
    )
    out_path.write_text(dia.model_dump_json(indent=2), encoding="utf-8")
    logger.info("Wrote %s (%d normas)", out_path, len(summarized))

    _update_index(dia)
    return 0


if __name__ == "__main__":
    sys.exit(main())
