"""Tests for the press news summarizer (Task 5).

Tests do NOT mock Gemini — only the non-API parts are tested.
"""

from datetime import datetime

import pytest

from scripts.lib.schemas import (
    FUENTE_DISPLAY,
    PRENSA_PROMPT_VERSION,
    PrensaCruda,
)
from scripts.summarizers.noticias import NoticiasSummarizer


# ── Fixture ─────────────────────────────────────────────────────────────────


def _make_prensa_cruda(
    id: str = "gestion-2026-04-12-001",
    fuente: str = "gestion",
    titulo: str = "BCR mantiene tasa de interés en 6.5%",
) -> PrensaCruda:
    return PrensaCruda(
        id=id,
        titulo=titulo,
        fuente=fuente,
        url=f"https://gestion.pe/{id}",
        fecha=datetime(2026, 4, 12, 9, 30, 0),
        contenido="El Banco Central de Reserva del Perú mantuvo su tasa de interés referencial.",
    )


# ── Tests ────────────────────────────────────────────────────────────────────


def test_summarizer_has_correct_slug():
    summarizer = NoticiasSummarizer()
    assert summarizer.source_slug == "noticias"


def test_empty_day_returns_valid_structure():
    """summarize_day with empty items should return a valid DiaPrensa dict."""
    summarizer = NoticiasSummarizer()
    result = summarizer.summarize_day({"fecha": "2026-04-12", "items": []})

    assert result["fecha"] == "2026-04-12"
    assert result["noticias"] == []
    assert result["total"] == 0
    assert isinstance(result["fuentes_activas"], list)
    assert result["prompt_version"] == PRENSA_PROMPT_VERSION


def test_is_stale_returns_true_for_old_version():
    """is_stale should return True when prompt_version doesn't match."""
    summarizer = NoticiasSummarizer()
    existing = {
        "noticias": [
            {"prompt_version": "old-version"},
            {"prompt_version": "another-old"},
        ]
    }
    assert summarizer.is_stale(existing) is True


def test_is_stale_returns_false_for_current_version():
    """is_stale should return False when all items have the current prompt_version."""
    summarizer = NoticiasSummarizer()
    existing = {
        "noticias": [
            {"prompt_version": PRENSA_PROMPT_VERSION},
            {"prompt_version": PRENSA_PROMPT_VERSION},
        ]
    }
    assert summarizer.is_stale(existing) is False


def test_fallback_returns_unsummarized_item():
    """_fallback should return a PrensaResumida with fuente_display populated and prompt_version=''."""
    summarizer = NoticiasSummarizer()

    noticia = _make_prensa_cruda(fuente="gestion")
    result = summarizer._fallback(noticia)

    assert result.id == noticia.id
    assert result.titulo == noticia.titulo
    assert result.fuente == "gestion"
    assert result.fuente_display == FUENTE_DISPLAY.get("gestion", "")
    assert result.resumen is None
    assert result.tags == []
    assert result.prompt_version == ""


def test_fallback_fuente_display_for_rpp():
    """_fallback should map 'rpp' to 'RPP' via FUENTE_DISPLAY."""
    summarizer = NoticiasSummarizer()
    noticia = _make_prensa_cruda(id="rpp-001", fuente="rpp")
    result = summarizer._fallback(noticia)
    assert result.fuente_display == FUENTE_DISPLAY.get("rpp", "")


def test_fallback_fuente_display_for_unknown_source():
    """_fallback should handle unknown fuente gracefully (empty string)."""
    summarizer = NoticiasSummarizer()
    noticia = _make_prensa_cruda(id="unknown-001", fuente="desconocido")
    result = summarizer._fallback(noticia)
    assert result.fuente_display == ""


def test_make_index_entry_returns_valid_structure():
    """make_index_entry should return a PrensaIndexEntry-compatible dict."""
    summarizer = NoticiasSummarizer()
    processed = {
        "fecha": "2026-04-12",
        "noticias": [],
        "total": 3,
        "fuentes_activas": ["gestion", "rpp"],
        "prompt_version": PRENSA_PROMPT_VERSION,
    }
    entry = summarizer.make_index_entry(processed)

    assert str(entry["fecha"]) == "2026-04-12"
    assert entry["total_noticias"] == 3
    assert entry["fuentes_activas"] == ["gestion", "rpp"]
