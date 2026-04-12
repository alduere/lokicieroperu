"""Base summarizer protocol for Loki-ciero Perú sources.

Every source summarizer implements this interface. The pipeline (summarize.py)
calls summarize_day() with the parsed data and gets back the processed output.
"""

from __future__ import annotations

from typing import Any, Protocol


class BaseSummarizer(Protocol):
    """Protocol that every source summarizer must implement."""

    source_slug: str

    def summarize_day(self, parsed_data: dict[str, Any]) -> dict[str, Any]:
        """Summarize one day's parsed data and return processed output.

        Input: the dict produced by the source's scraper (scrape_day output).
        Output: a dict ready for JSON serialization, containing at least:
          - "fecha": ISO date string
          - "items": list of dicts (summarized items)
          - "stats": dict with aggregate stats for the day
          - "generated_at": ISO timestamp

        The output format is source-specific — each source defines its own
        schema for items and stats.
        """
        ...

    def is_stale(self, existing_data: dict[str, Any]) -> bool:
        """Check if existing processed data needs re-summarization.

        Returns True if the data should be re-processed (e.g., prompt version
        changed, items changed).
        """
        ...
