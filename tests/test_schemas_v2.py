"""Tests for financial data and press news schemas (Task 2)."""

from datetime import date, datetime

import pytest

from scripts.lib.schemas import (
    CotizacionCambio,
    CotizacionMineral,
    DatosFinancieros,
    DiaPrensa,
    PrensaCruda,
    PrensaResumida,
)


# ── CotizacionCambio ────────────────────────────────────────────────────


def test_cotizacion_cambio_basic_creation():
    cotizacion = CotizacionCambio(moneda="USD/PEN", valor=3.75, variacion_pct=-0.12)
    assert cotizacion.moneda == "USD/PEN"
    assert cotizacion.valor == 3.75
    assert cotizacion.variacion_pct == -0.12


def test_cotizacion_cambio_positive_variation():
    cotizacion = CotizacionCambio(moneda="EUR/PEN", valor=4.10, variacion_pct=0.05)
    assert cotizacion.moneda == "EUR/PEN"
    assert cotizacion.variacion_pct == 0.05


# ── CotizacionMineral ───────────────────────────────────────────────────


def test_cotizacion_mineral_basic_creation():
    mineral = CotizacionMineral(
        nombre="Cobre",
        simbolo="Cu",
        precio=4.25,
        unidad="USD/lb",
        variacion_pct=1.30,
    )
    assert mineral.nombre == "Cobre"
    assert mineral.simbolo == "Cu"
    assert mineral.precio == 4.25
    assert mineral.unidad == "USD/lb"
    assert mineral.variacion_pct == 1.30


def test_cotizacion_mineral_plata():
    mineral = CotizacionMineral(
        nombre="Plata",
        simbolo="Ag",
        precio=27.50,
        unidad="USD/oz",
        variacion_pct=-0.80,
    )
    assert mineral.nombre == "Plata"
    assert mineral.simbolo == "Ag"
    assert mineral.unidad == "USD/oz"


# ── DatosFinancieros ────────────────────────────────────────────────────


def test_datos_financieros_round_trip():
    usd_pen = CotizacionCambio(moneda="USD/PEN", valor=3.75, variacion_pct=-0.12)
    minerales = [
        CotizacionMineral(
            nombre="Cobre", simbolo="Cu", precio=4.25, unidad="USD/lb", variacion_pct=1.30
        ),
        CotizacionMineral(
            nombre="Plata", simbolo="Ag", precio=27.50, unidad="USD/oz", variacion_pct=-0.80
        ),
    ]
    datos = DatosFinancieros(
        fecha=date(2026, 4, 12),
        usd_pen=usd_pen,
        minerales=minerales,
    )

    dumped = datos.model_dump()
    assert dumped["fecha"] == date(2026, 4, 12)
    assert dumped["usd_pen"]["moneda"] == "USD/PEN"
    assert dumped["usd_pen"]["valor"] == 3.75
    assert len(dumped["minerales"]) == 2
    assert dumped["minerales"][0]["nombre"] == "Cobre"
    assert dumped["minerales"][1]["simbolo"] == "Ag"


def test_datos_financieros_empty_minerales():
    usd_pen = CotizacionCambio(moneda="USD/PEN", valor=3.80, variacion_pct=0.0)
    datos = DatosFinancieros(
        fecha=date(2026, 4, 12),
        usd_pen=usd_pen,
        minerales=[],
    )
    assert datos.minerales == []


# ── PrensaCruda ─────────────────────────────────────────────────────────


def test_prensa_cruda_basic_creation():
    noticia = PrensaCruda(
        id="gestion-2026-04-12-001",
        titulo="BCR mantiene tasa de interés en 6.5%",
        fuente="gestion",
        url="https://gestion.pe/economia/bcr-mantiene-tasa",
        fecha=datetime(2026, 4, 12, 9, 30, 0),
        contenido="El Banco Central de Reserva del Perú mantuvo su tasa de interés...",
    )
    assert noticia.id == "gestion-2026-04-12-001"
    assert noticia.titulo == "BCR mantiene tasa de interés en 6.5%"
    assert noticia.fuente == "gestion"
    assert noticia.url == "https://gestion.pe/economia/bcr-mantiene-tasa"
    assert isinstance(noticia.fecha, datetime)
    assert noticia.contenido.startswith("El Banco Central")


# ── PrensaResumida ──────────────────────────────────────────────────────


def test_prensa_resumida_basic_creation():
    noticia = PrensaResumida(
        id="rpp-2026-04-12-005",
        titulo="Inflación en Lima baja a 2.1%",
        fuente="rpp",
        url="https://rpp.pe/economia/inflacion-lima",
        fecha=datetime(2026, 4, 12, 10, 0, 0),
        contenido="La inflación en Lima Metropolitana...",
        fuente_display="RPP",
        resumen="La inflación en Lima bajó a 2.1% en marzo.",
        categoria="Economía",
        tags=["inflación", "Lima", "INEI"],
        prompt_version="prensa-v1",
    )
    assert noticia.fuente_display == "RPP"
    assert noticia.resumen == "La inflación en Lima bajó a 2.1% en marzo."
    assert noticia.categoria == "Economía"
    assert noticia.tags == ["inflación", "Lima", "INEI"]
    assert noticia.prompt_version == "prensa-v1"


def test_prensa_resumida_defaults():
    noticia = PrensaResumida(
        id="andina-2026-04-12-010",
        titulo="Gobierno aprueba decreto de urgencia",
        fuente="andina",
        url="https://andina.pe/noticias/gobierno",
        fecha=datetime(2026, 4, 12, 11, 0, 0),
        contenido="El Ejecutivo aprobó un decreto...",
    )
    assert noticia.fuente_display == ""
    assert noticia.resumen is None
    assert noticia.categoria == "Economía"
    assert noticia.tags == []
    assert noticia.prompt_version == ""


def test_prensa_resumida_inherits_prensa_cruda():
    """PrensaResumida should be a subclass of PrensaCruda."""
    assert issubclass(PrensaResumida, PrensaCruda)


# ── DiaPrensa ───────────────────────────────────────────────────────────


def test_dia_prensa_round_trip():
    noticias = [
        PrensaResumida(
            id="gestion-001",
            titulo="Noticia 1",
            fuente="gestion",
            url="https://gestion.pe/noticia-1",
            fecha=datetime(2026, 4, 12, 8, 0, 0),
            contenido="Contenido de la noticia 1.",
            fuente_display="Gestión",
            resumen="Resumen de noticia 1.",
            categoria="Economía",
            tags=["economía"],
            prompt_version="prensa-v1",
        ),
        PrensaResumida(
            id="rpp-002",
            titulo="Noticia 2",
            fuente="rpp",
            url="https://rpp.pe/noticia-2",
            fecha=datetime(2026, 4, 12, 9, 0, 0),
            contenido="Contenido de la noticia 2.",
            fuente_display="RPP",
            resumen="Resumen de noticia 2.",
            categoria="Política",
            tags=["política", "congreso"],
            prompt_version="prensa-v1",
        ),
    ]

    dia = DiaPrensa(
        fecha="2026-04-12",
        noticias=noticias,
        total=2,
        fuentes_activas=["gestion", "rpp"],
        prompt_version="prensa-v1",
    )

    dumped = dia.model_dump()
    assert dumped["fecha"] == "2026-04-12"
    assert dumped["total"] == 2
    assert dumped["fuentes_activas"] == ["gestion", "rpp"]
    assert dumped["prompt_version"] == "prensa-v1"
    assert len(dumped["noticias"]) == 2
    assert dumped["noticias"][0]["titulo"] == "Noticia 1"
    assert dumped["noticias"][1]["fuente_display"] == "RPP"


def test_dia_prensa_empty():
    dia = DiaPrensa(
        fecha="2026-04-12",
        noticias=[],
        total=0,
        fuentes_activas=[],
        prompt_version="prensa-v1",
    )
    assert dia.total == 0
    assert dia.noticias == []
    assert dia.fuentes_activas == []
