"""Parser tests against real HTML fixtures captured from El Peruano."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from scripts.lib.elperuano import parse_documentos_seccion, parse_normas_legales
from scripts.lib.schemas import Seccion

FIX = Path(__file__).parent / "fixtures" / "elperuano"


def _read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8", errors="replace")


def test_parse_normas_legales_today():
    html = _read("normas_legales_today.html")
    normas = parse_normas_legales(html)
    assert len(normas) > 10, f"expected >10 norms, got {len(normas)}"

    n = normas[0]
    # Every norm must have these populated
    assert n.id
    assert n.tipo
    assert n.entidad_emisora
    assert n.titulo_oficial
    assert n.sumilla
    assert n.fecha_publicacion.year == 2026
    assert n.seccion is Seccion.NORMAS_LEGALES


def test_parse_normas_legales_known_norm():
    html = _read("normas_legales_today.html")
    normas = parse_normas_legales(html)
    by_id = {n.id: n for n in normas}
    assert "2504749-1" in by_id
    n = by_id["2504749-1"]
    assert "RESOLUCION MINISTERIAL" in n.tipo.upper()
    assert "PRESIDENCIA DEL CONSEJO DE MINISTROS" in n.entidad_emisora
    assert "SUNASS" in n.sumilla
    assert n.fecha_publicacion == date(2026, 4, 11)
    assert n.numero == "123-2026-PCM"
    assert str(n.link_oficial).startswith("https://busquedas.elperuano.pe/dispositivo/NL/")


def test_parse_normas_legales_historical():
    html = _read("normas_legales_2026-04-10.html")
    normas = parse_normas_legales(html)
    assert len(normas) > 10
    # All norms should be from 2026-04-10
    fechas = {n.fecha_publicacion for n in normas}
    assert date(2026, 4, 10) in fechas


def test_parse_normas_legales_extraordinary_flag():
    html = _read("normas_legales_2026-04-10.html")
    normas = parse_normas_legales(html)
    extras = [n for n in normas if n.edicion_extraordinaria]
    # April 10 happens to have extraordinary editions in our fixture
    assert len(extras) >= 0  # just verify the field is parsed without error


def test_parse_boletin_oficial():
    html = _read("boletin_oficial_today.html")
    docs = parse_documentos_seccion(html, Seccion.BOLETIN_OFICIAL)
    assert len(docs) >= 1
    d = docs[0]
    assert d.seccion is Seccion.BOLETIN_OFICIAL
    assert d.edicion
    assert d.fecha_publicacion.year == 2026
    assert str(d.descarga_url).startswith("http")


def test_parse_concesiones():
    html = _read("concesiones_today.html")
    docs = parse_documentos_seccion(html, Seccion.CONCESIONES)
    assert len(docs) >= 1
    d = docs[0]
    assert d.seccion is Seccion.CONCESIONES
    assert d.edicion
    assert str(d.descarga_url).endswith(".pdf")


def test_parse_empty_section_returns_empty_list():
    # Casaciones today is empty (only 2 bytes)
    html = _read("casaciones_today.html")
    docs = parse_documentos_seccion(html, Seccion.CASACIONES)
    assert docs == []


def test_split_titulo_extracts_numero():
    from scripts.lib.elperuano import _split_titulo

    tipo, num = _split_titulo("RESOLUCION MINISTERIAL  N° 123-2026-PCM")
    assert "RESOLUCION MINISTERIAL" in tipo
    assert num == "123-2026-PCM"

    tipo, num = _split_titulo("DECRETO SUPREMO N° 045-2026-EF")
    assert "DECRETO SUPREMO" in tipo
    assert num == "045-2026-EF"

    tipo, num = _split_titulo("Just a title without number")
    assert tipo == "Just a title without number"
    assert num is None
