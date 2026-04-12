"""Pydantic schemas for the Loki-ciero Perú pipeline.

These models are the contract between the scraper, the summarizer, the
website builder, the PDF builder and the Telegram notifier. Anything that
moves between scripts is validated against one of them.
"""

from __future__ import annotations

import re
from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl

# Bump this whenever the Gemini prompt or output schema changes meaningfully.
# summarize.py uses it to decide whether existing processed files are stale.
PROMPT_VERSION = 2


class Impacto(str, Enum):
    ALTO = "alto"
    MEDIO = "medio"
    BAJO = "bajo"


# Mapping from regex pattern → short type code. Order matters: more specific
# patterns first. Used by parse_normas_legales to compute tipo_corto.
TIPO_CORTO_PATTERNS: list[tuple[str, str]] = [
    (r"DECRETO\s+SUPREMO", "DS"),
    (r"DECRETO\s+DE\s+URGENCIA", "DU"),
    (r"DECRETO\s+LEGISLATIVO", "DL"),
    (r"\bLEY\b", "LEY"),
    (r"RESOLUCI[OÓ]N\s+MINISTERIAL", "RM"),
    (r"RESOLUCI[OÓ]N\s+VICEMINISTERIAL", "RVM"),
    (r"RESOLUCI[OÓ]N\s+DIRECTORAL", "RD"),
    (r"RESOLUCI[OÓ]N\s+DE\s+SUPERINTENDENCIA", "RS"),
    (r"RESOLUCI[OÓ]N\s+JEFATURAL", "RJ"),
    (r"RESOLUCI[OÓ]N\s+ADMINISTRATIVA", "RA"),
    (r"RESOLUCI[OÓ]N\s+DE\s+PRESIDENCIA", "RPRE"),
    (r"RESOLUCI[OÓ]N\s+DE\s+CONSEJO\s+DIRECTIVO", "RCD"),
    (r"RESOLUCI[OÓ]N\s+SUPREMA", "RSU"),
    (r"RESOLUCI[OÓ]N\b", "RES"),
    (r"ORDENANZA\s+REGIONAL", "OR"),
    (r"ORDENANZA\s+MUNICIPAL", "OM"),
    (r"\bORDENANZA\b", "ORD"),
    (r"ACUERDO\s+DE\s+CONSEJO", "AC"),
    (r"\bACUERDO\b", "ACU"),
    (r"CIRCULAR", "CIRC"),
    (r"DIRECTIVA", "DIR"),
    (r"FE\s+DE\s+ERRATAS", "FE"),
    (r"REGLAMENTO", "REG"),
    (r"PROTOCOLO", "PROT"),
]


def compute_tipo_corto(tipo: str) -> str:
    """Map a free-text tipo string to a short uppercase code."""
    upper = tipo.upper()
    for pattern, code in TIPO_CORTO_PATTERNS:
        if re.search(pattern, upper):
            return code
    return "OTRO"


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
    tipo_corto: str = "OTRO"  # "RM", "DS", "LEY", etc. — used for filtering
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
    cambios_clave: list[str] = Field(default_factory=list)  # 1-3 bullet points
    a_quien_afecta: str | None = None  # one-line audience description
    vigencia: str | None = None  # one-line "from when" — or null if unknown
    impacto: Impacto = Impacto.MEDIO
    impacto_razon: str | None = None  # one-line "why this impact level"
    sectores: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    prompt_version: int = 0  # set by summarizer to PROMPT_VERSION


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
