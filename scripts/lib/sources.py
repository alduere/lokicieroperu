"""Source registry for Loki-ciero Perú.

Each source defines its slug, display name, scraper, and summarizer.
Adding a new source = adding an entry here + implementing scraper/summarizer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scripts.scrapers.base import BaseScraper
    from scripts.summarizers.base import BaseSummarizer


@dataclass(frozen=True)
class SourceConfig:
    slug: str
    nombre: str
    subtitulo: str
    item_label: str  # "normas", "alertas", "resoluciones"
    enabled: bool = True
    scraper_cls: str = ""  # dotted import path
    summarizer_cls: str = ""  # dotted import path
    categorias: list[dict[str, str]] = field(default_factory=list)


# ── Registry ────────────────────────────────────────────────────────────────

SOURCES: dict[str, SourceConfig] = {
    "elperuano": SourceConfig(
        slug="elperuano",
        nombre="El Peruano",
        subtitulo="Diario Oficial",
        item_label="normas",
        scraper_cls="scripts.scrapers.elperuano.ElPeruanoScraper",
        summarizer_cls="scripts.summarizers.elperuano.ElPeruanoSummarizer",
        categorias=[
            {"key": "alto", "label": "Alto impacto", "color": "bg-red-500"},
            {"key": "medio", "label": "Medio impacto", "color": "bg-orange-400"},
            {"key": "bajo", "label": "Bajo impacto", "color": "bg-green-500"},
        ],
    ),
    "consumidor": SourceConfig(
        slug="consumidor",
        nombre="Consumidor",
        subtitulo="Protección al consumidor",
        item_label="noticias",
        scraper_cls="scripts.scrapers.consumidor.ConsumidorScraper",
        summarizer_cls="scripts.summarizers.consumidor.ConsumidorSummarizer",
        categorias=[],
    ),
    "indecopi-alertas": SourceConfig(
        slug="indecopi-alertas",
        nombre="INDECOPI Alertas",
        subtitulo="Alertas de consumo",
        item_label="alertas",
        scraper_cls="scripts.scrapers.indecopi_alertas.IndecopiAlertasScraper",
        summarizer_cls="scripts.summarizers.indecopi_alertas.IndecopiAlertasSummarizer",
        categorias=[
            {"key": "vehiculos", "label": "Vehículos", "color": "bg-blue-500"},
            {"key": "alimentos", "label": "Alimentos", "color": "bg-amber-500"},
            {"key": "electronicos", "label": "Electrónicos", "color": "bg-purple-500"},
            {"key": "otros", "label": "Otros", "color": "bg-gray-400"},
        ],
    ),
    "gaceta-pi": SourceConfig(
        slug="gaceta-pi",
        nombre="Gaceta PI",
        subtitulo="Propiedad Industrial",
        item_label="solicitudes",
        scraper_cls="scripts.scrapers.gaceta_pi.GacetaPIScraper",
        summarizer_cls="scripts.summarizers.gaceta_pi.GacetaPISummarizer",
        categorias=[
            {"key": "marca", "label": "Marcas", "color": "bg-blue-500"},
            {"key": "patente", "label": "Patentes", "color": "bg-purple-500"},
        ],
    ),
    "tribunal-fiscal": SourceConfig(
        slug="tribunal-fiscal",
        nombre="Tribunal Fiscal",
        subtitulo="Jurisprudencia tributaria",
        item_label="resoluciones",
        scraper_cls="scripts.scrapers.tribunal_fiscal.TribunalFiscalScraper",
        summarizer_cls="scripts.summarizers.tribunal_fiscal.TribunalFiscalSummarizer",
        categorias=[
            {"key": "igv", "label": "IGV", "color": "bg-blue-500"},
            {"key": "renta", "label": "Renta", "color": "bg-amber-500"},
            {"key": "aduanas", "label": "Aduanas", "color": "bg-purple-500"},
        ],
    ),
    "noticias": SourceConfig(
        slug="noticias",
        nombre="Noticias",
        subtitulo="Economía, finanzas y política",
        item_label="noticias",
        enabled=False,
        scraper_cls="scripts.scrapers.noticias.NoticiasScraper",
        summarizer_cls="scripts.summarizers.noticias.NoticiasSummarizer",
        categorias=[
            {"key": "economia", "label": "Economía", "color": "bg-amber-500"},
            {"key": "finanzas", "label": "Finanzas", "color": "bg-green-500"},
            {"key": "politica", "label": "Política", "color": "bg-red-500"},
        ],
    ),
    "financiero": SourceConfig(
        slug="financiero",
        nombre="Datos Financieros",
        subtitulo="Tipo de cambio y minerales",
        item_label="cotizaciones",
        enabled=False,  # no summarizer — only invoked via explicit --source
        scraper_cls="scripts.scrapers.financiero.FinancieroScraper",
        summarizer_cls="",  # no summarizer needed
        categorias=[],
    ),
}


def enabled_sources() -> list[SourceConfig]:
    """Return all enabled sources in registry order."""
    return [s for s in SOURCES.values() if s.enabled]


def get_source(slug: str) -> SourceConfig:
    """Get a source by slug. Raises KeyError if not found."""
    return SOURCES[slug]


def load_scraper(source: SourceConfig) -> BaseScraper:
    """Dynamically import and instantiate the scraper for a source."""
    module_path, class_name = source.scraper_cls.rsplit(".", 1)
    import importlib

    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls()


def load_summarizer(source: SourceConfig) -> BaseSummarizer:
    """Dynamically import and instantiate the summarizer for a source."""
    module_path, class_name = source.summarizer_cls.rsplit(".", 1)
    import importlib

    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls()
