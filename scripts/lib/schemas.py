"""Pydantic schemas for the Loki-ciero Perú pipeline.

These models are the contract between the scraper, the summarizer, the
website builder, the PDF builder and the Telegram notifier. Anything that
moves between scripts is validated against one of them.
"""

from __future__ import annotations

import re
from datetime import date, datetime
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


# ── INDECOPI Alertas de Consumo ─────────────────────────────────────────────

ALERTAS_PROMPT_VERSION = 1


class AlertaCruda(BaseModel):
    """A consumer alert as fetched from the INDECOPI REST API."""

    id: str
    codigo_alerta: str | None = None
    titulo: str
    sumilla: str | None = None
    fecha_publicacion: date
    categoria: str | None = None
    url_slug: str | None = None
    nombre_producto: str | None = None
    marca: str | None = None
    modelo: str | None = None
    lote: str | None = None
    unidades_involucradas: str | None = None
    periodo: str | None = None
    descripcion_riesgo: str | None = None
    descripcion_efectos: str | None = None
    medidas_adoptadas: str | None = None
    datos_contacto: str | None = None
    imagen_url: str | None = None
    ficha_url: str | None = None
    link_oficial: str | None = None


class AlertaResumida(AlertaCruda):
    """An alert after AI summarization."""

    resumen: str | None = None
    impacto: Impacto = Impacto.MEDIO
    impacto_razon: str | None = None
    tags: list[str] = Field(default_factory=list)
    prompt_version: int = 0


class StatsAlertasDia(BaseModel):
    total_alertas: int
    por_categoria: list[tuple[str, int]] = Field(default_factory=list)


class DiaAlertasProcesado(BaseModel):
    """Processed output for one day of INDECOPI alerts."""

    fecha: date
    source_slug: str = "indecopi-alertas"
    items: list[AlertaResumida]
    stats: StatsAlertasDia
    generated_at: str


class AlertasIndexEntry(BaseModel):
    fecha: date
    total_alertas: int


# ── INDECOPI Consumidor (WordPress) ─────────────────────────────────────

CONSUMIDOR_PROMPT_VERSION = 1


class NoticiaCruda(BaseModel):
    """A news post from consumidor.gob.pe WordPress API."""

    id: str
    titulo: str
    extracto: str | None = None  # HTML excerpt, stripped
    fecha_publicacion: date
    link_oficial: str | None = None
    categorias: list[int] = Field(default_factory=list)


class NoticiaResumida(NoticiaCruda):
    """A news post after AI summarization."""

    resumen: str | None = None
    impacto: Impacto = Impacto.MEDIO
    impacto_razon: str | None = None
    tags: list[str] = Field(default_factory=list)
    prompt_version: int = 0


class StatsNoticiasDia(BaseModel):
    total_noticias: int


class DiaNoticiasProcesado(BaseModel):
    fecha: date
    source_slug: str = "consumidor"
    items: list[NoticiaResumida]
    stats: StatsNoticiasDia
    generated_at: str


class NoticiasIndexEntry(BaseModel):
    fecha: date
    total_noticias: int


# ── INDECOPI Gaceta de Propiedad Industrial ─────────────────────────────

GACETA_PROMPT_VERSION = 1


class SolicitudPICruda(BaseModel):
    """A trademark/patent filing from the IP Gazette."""

    id: str  # expedition number
    tipo_solicitud: str  # "Marca de Producto", "Marca de Servicio", "Patente de Invencion", etc.
    signo_solicitado: str  # the trademark name/sign
    solicitante: str  # applicant name
    clase: str | None = None  # Nice classification
    fecha_publicacion: date
    fecha_presentacion: date | None = None
    fecha_limite_oposicion: date | None = None
    descripcion: str | None = None  # product/service description


class SolicitudPIResumida(SolicitudPICruda):
    """Not AI-summarized — filings are structured data, no AI needed."""

    prompt_version: int = 0


class StatsGacetaDia(BaseModel):
    total_solicitudes: int
    por_tipo: list[tuple[str, int]] = Field(default_factory=list)


class DiaGacetaProcesado(BaseModel):
    fecha: date
    source_slug: str = "gaceta-pi"
    items: list[SolicitudPIResumida]
    stats: StatsGacetaDia
    generated_at: str


class GacetaIndexEntry(BaseModel):
    fecha: date
    total_solicitudes: int


# ── Tribunal Fiscal ─────────────────────────────────────────────────────

TRIBUNAL_FISCAL_PROMPT_VERSION = 1


class ResolucionTFCruda(BaseModel):
    """A resolution from the Tribunal Fiscal."""

    id: str  # RTF number e.g. "2026_1_00123"
    numero_rtf: str
    fecha_rtf: date
    numero_expediente: str | None = None
    sala: str | None = None  # "1", "2", ..., "A", "Q"
    sumilla: str | None = None  # fetched from Sumilla.htm
    administracion: str | None = None  # SUNAT, Municipal, etc.
    link_pdf: str | None = None
    link_sumilla: str | None = None


class ResolucionTFResumida(ResolucionTFCruda):
    """A resolution after AI summarization."""

    resumen: str | None = None
    impacto: Impacto = Impacto.MEDIO
    impacto_razon: str | None = None
    tema_tributario: str | None = None  # e.g. "IGV", "Impuesto a la Renta", "Aduanas"
    tags: list[str] = Field(default_factory=list)
    prompt_version: int = 0


class StatsTFDia(BaseModel):
    total_resoluciones: int
    por_sala: list[tuple[str, int]] = Field(default_factory=list)


class DiaTFProcesado(BaseModel):
    fecha: date
    source_slug: str = "tribunal-fiscal"
    items: list[ResolucionTFResumida]
    stats: StatsTFDia
    generated_at: str


class TFIndexEntry(BaseModel):
    fecha: date
    total_resoluciones: int


# ── Datos Financieros (tipo de cambio + minerales) ─────────────────────

class CotizacionCambio(BaseModel):
    """Exchange rate quote (e.g. USD/PEN)."""
    moneda: str  # "USD/PEN"
    valor: float
    variacion_pct: float  # % change vs previous day

class CotizacionMineral(BaseModel):
    """Commodity/mineral price quote."""
    nombre: str  # "Cobre", "Plata", etc.
    simbolo: str  # "Cu", "Ag", etc.
    precio: float
    unidad: str  # "USD/lb", "USD/oz"
    variacion_pct: float

class DatosFinancieros(BaseModel):
    """Daily financial data: exchange rate + mineral prices."""
    fecha: date
    usd_pen: CotizacionCambio
    minerales: list[CotizacionMineral]


# ── Noticias de Prensa (multi-source news) ─────────────────────────────

PRENSA_PROMPT_VERSION = "prensa-v1"

FUENTE_DISPLAY: dict[str, str] = {
    "gestion": "Gestión",
    "elcomercio": "El Comercio",
    "rpp": "RPP",
    "andina": "Andina",
    "semanaeconomica": "Semana Económica",
    "bcrp": "BCRP",
}

class PrensaCruda(BaseModel):
    """A news article as fetched from RSS or HTML scraping."""
    id: str
    titulo: str
    fuente: str
    url: str
    fecha: datetime
    contenido: str

class PrensaResumida(PrensaCruda):
    """A news article after Gemini summarization."""
    fuente_display: str = ""
    resumen: str | None = None
    categoria: str = "Economía"
    tags: list[str] = Field(default_factory=list)
    prompt_version: str = ""

class DiaPrensa(BaseModel):
    """Processed output for one day of press news."""
    fecha: str
    noticias: list[PrensaResumida]
    total: int
    fuentes_activas: list[str]
    prompt_version: str

class PrensaIndexEntry(BaseModel):
    fecha: date
    total_noticias: int
    fuentes_activas: list[str]
