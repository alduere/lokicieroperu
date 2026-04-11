"""Pydantic schemas for the NotiRelevantePerú pipeline.

These models are the contract between the scraper, the summarizer, the
website builder, the PDF builder and the Telegram notifier. Anything that
moves between scripts is validated against one of them.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class Impacto(str, Enum):
    ALTO = "alto"
    MEDIO = "medio"
    BAJO = "bajo"


class Seccion(str, Enum):
    NORMAS_LEGALES = "normas_legales"
    BOLETIN_OFICIAL = "boletin_oficial"
    CASACIONES = "casaciones"
    CONCESIONES = "concesiones_mineras"
    PATENTES = "patentes_signos"


class NormaCruda(BaseModel):
    """A norm as scraped from El Peruano (no AI fields yet)."""

    id: str
    seccion: Seccion = Seccion.NORMAS_LEGALES
    tipo: str  # "RESOLUCION MINISTERIAL", "DECRETO SUPREMO", etc.
    numero: str | None = None  # "123-2026-PCM"
    titulo_oficial: str  # full h5 text
    entidad_emisora: str  # h4
    sumilla: str  # the <p> after the date
    fecha_publicacion: date
    link_oficial: HttpUrl | None = None
    descarga_pdf: HttpUrl | None = None
    portada_img: HttpUrl | None = None
    edicion_extraordinaria: bool = False


class NormaResumida(NormaCruda):
    """A norm after Gemini has produced an executive summary + classification."""

    resumen_ejecutivo: str | None = None
    impacto: Impacto = Impacto.MEDIO
    sectores: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class DocumentoSeccion(BaseModel):
    """A daily PDF/document from the non-Normas-Legales sections.

    These sections (Boletín Oficial, Casaciones, Concesiones, Patentes) only
    publish bulletin PDFs without per-document metadata that we can summarize.
    We surface them as downloadable links on the site.
    """

    seccion: Seccion
    edicion: str
    fecha_publicacion: date
    descarga_url: HttpUrl
    portada_img: HttpUrl | None = None


class StatsDia(BaseModel):
    total_normas: int
    alto: int
    medio: int
    bajo: int
    sectores_top: list[tuple[str, int]] = Field(default_factory=list)
    documentos_otras_secciones: int = 0


class DiaProcesado(BaseModel):
    """The full processed output of one day, ready to feed the site builder."""

    fecha: date
    normas: list[NormaResumida]
    documentos: list[DocumentoSeccion] = Field(default_factory=list)
    stats: StatsDia
    generated_at: str  # ISO timestamp


class IndexEntry(BaseModel):
    fecha: date
    total_normas: int
    alto: int
    medio: int
    bajo: int


class Index(BaseModel):
    fechas: list[IndexEntry]
