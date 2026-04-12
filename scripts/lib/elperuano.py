"""HTTP client and HTML parsers for El Peruano (diariooficial.elperuano.pe).

The site exposes server-rendered AJAX endpoints under /Normas, /BoletinOficial,
/Casaciones, /Concesiones and /Patentes. We hit them with the same headers a
browser would and parse the returned HTML fragments with BeautifulSoup.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date
from typing import Iterable

import requests
from bs4 import BeautifulSoup, Tag

from scripts.lib.schemas import DocumentoSeccion, NormaCruda, Seccion, compute_tipo_corto

logger = logging.getLogger(__name__)

BASE_URL = "https://diariooficial.elperuano.pe"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) LokicieroPeru/0.1 (+https://github.com/alduere/lokicieroperu)"
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "es-PE,es;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
}
REQUEST_DELAY_SECONDS = 1.0  # be polite

LOAD_TODAY = {
    Seccion.NORMAS_LEGALES: "/Normas/LoadNormasLegales?Length=0",
    Seccion.BOLETIN_OFICIAL: "/BoletinOficial/LoadBoletinOficial?Length=0",
    Seccion.CASACIONES: "/Casaciones/LoadCasacionesPortal?Length=0",
    Seccion.CONCESIONES: "/Concesiones/LoadConcesionesMinerasPortal?Length=0",
    Seccion.PATENTES: "/Patentes/LoadPatentesPortal?Length=0",
}

FILTRO = {
    Seccion.NORMAS_LEGALES: "/Normas/Filtro",
    Seccion.BOLETIN_OFICIAL: "/BoletinOficial/Filtro",
    Seccion.CASACIONES: "/Casaciones/Filtro",
    Seccion.CONCESIONES: "/Concesiones/Filtro",
    Seccion.PATENTES: "/Patentes/Filtro",
}


def _client() -> requests.Session:
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    return s


def fetch_today(seccion: Seccion, session: requests.Session | None = None) -> str:
    """Fetch the latest edition listing for a section. Returns raw HTML."""
    s = session or _client()
    url = BASE_URL + LOAD_TODAY[seccion]
    logger.info("GET %s", url)
    r = s.get(url, timeout=30)
    r.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)
    return r.text


def fetch_by_date(
    seccion: Seccion, target: date, session: requests.Session | None = None
) -> str:
    """Fetch the listing for a specific date via the Filtro endpoint."""
    s = session or _client()
    # dateparam is MM/DD/YYYY 00:00:00 (.NET en-US default)
    dateparam = target.strftime("%m/%d/%Y 00:00:00")
    # cddesde/cdhasta in body are DD/MM/YYYY (Peruvian display)
    body = {
        "cddesde": target.strftime("%d/%m/%Y"),
        "cdhasta": target.strftime("%d/%m/%Y"),
        "extraordinaria": "0",
    }
    url = BASE_URL + FILTRO[seccion]
    logger.info("POST %s dateparam=%s body=%s", url, dateparam, body)
    r = s.post(url, params={"dateparam": dateparam}, data=body, timeout=30)
    r.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)
    return r.text


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

_FECHA_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
_NUMERO_RE = re.compile(r"N[°º]\s*([A-Z0-9\-_/]+)", re.IGNORECASE)


def _parse_fecha(s: str) -> date | None:
    m = _FECHA_RE.search(s)
    if not m:
        return None
    dd, mm, yyyy = m.groups()
    try:
        return date(int(yyyy), int(mm), int(dd))
    except ValueError:
        return None


def _split_titulo(titulo_full: str) -> tuple[str, str | None]:
    """Split 'RESOLUCION MINISTERIAL N° 123-2026-PCM' into (tipo, numero)."""
    m = _NUMERO_RE.search(titulo_full)
    if not m:
        return titulo_full.strip(), None
    numero = m.group(1)
    tipo = titulo_full[: m.start()].strip()
    return tipo, numero


def parse_normas_legales(html: str) -> list[NormaCruda]:
    """Parse the HTML returned by LoadNormasLegales / Filtro for the Normas section.

    Each norm is in <article class="edicionesoficiales_articulos">.
    """
    soup = BeautifulSoup(html, "lxml")
    out: list[NormaCruda] = []
    for art in soup.select("article.edicionesoficiales_articulos"):
        h4 = art.select_one(".ediciones_texto h4")
        h5_a = art.select_one(".ediciones_texto h5 a")
        if not h4 or not h5_a:
            continue
        entidad = _clean(h4.get_text())
        titulo_full = _clean(h5_a.get_text())
        link_oficial = h5_a.get("href") or None
        tipo, numero = _split_titulo(titulo_full)

        # Date and possible "Edición Extraordinaria" badge live in the same <p><b>
        fecha_p = art.select_one(".ediciones_texto p")
        fecha = _parse_fecha(fecha_p.get_text()) if fecha_p else None
        extraordinaria = bool(fecha_p and fecha_p.select_one("strong.extraordinaria"))

        # Sumilla is the *second* <p> in .ediciones_texto
        ps = art.select(".ediciones_texto p")
        sumilla = _clean(ps[1].get_text()) if len(ps) >= 2 else ""

        # Norm ID lives on the data-id attribute of the download buttons
        btn = art.select_one("input.dataUrl[data-id]")
        norm_id = btn.get("data-id") if btn else None
        if not norm_id:
            # fallback: extract from the dispositivo URL
            m = re.search(r"/dispositivo/[A-Z]+/([\w\-]+)", link_oficial or "")
            norm_id = m.group(1) if m else titulo_full[:60]

        # Cuadernillo / individual download URLs
        descarga_pdf = None
        for inp in art.select("input.dataUrl[data-url]"):
            tipo_btn = inp.get("data-tipo") or ""
            if "Di" in tipo_btn:  # Descarga individual
                descarga_pdf = inp.get("data-url")
                break

        portada = art.select_one(".ediciones_pdf img")
        portada_url = _absolute_url(portada.get("src")) if portada else None

        if fecha is None:
            logger.warning("norm %s without parseable date, skipping", norm_id)
            continue

        tipo_str = tipo or "Norma"
        out.append(
            NormaCruda(
                id=norm_id,
                seccion=Seccion.NORMAS_LEGALES,
                tipo=tipo_str,
                tipo_corto=compute_tipo_corto(tipo_str),
                numero=numero,
                titulo_oficial=titulo_full,
                entidad_emisora=entidad,
                sumilla=sumilla,
                fecha_publicacion=fecha,
                link_oficial=link_oficial,
                descarga_pdf=descarga_pdf,
                portada_img=portada_url,
                edicion_extraordinaria=extraordinaria,
            )
        )
    return out


def parse_documentos_seccion(html: str, seccion: Seccion) -> list[DocumentoSeccion]:
    """Parse the bulletin/documents listing for the non-Normas-Legales sections.

    Those use <article class="normaslegales_articulos"> with very simple structure:
    just an edición number, a date, and a download link.
    """
    soup = BeautifulSoup(html, "lxml")
    out: list[DocumentoSeccion] = []
    for art in soup.select("article.normaslegales_articulos"):
        ps = art.find_all("p", recursive=True)
        edicion = ""
        fecha = None
        for p in ps:
            txt = _clean(p.get_text())
            if txt.startswith("Edici"):
                edicion = txt.split(":", 1)[-1].strip()
            elif txt.startswith("Fecha"):
                fecha = _parse_fecha(txt)
        a = art.select_one("a[href]")
        descarga_url = a.get("href") if a else None
        portada = art.select_one("figure img")
        portada_url = _absolute_url(portada.get("src")) if portada else None

        if fecha is None or descarga_url is None:
            continue

        out.append(
            DocumentoSeccion(
                seccion=seccion,
                edicion=edicion or "—",
                fecha_publicacion=fecha,
                descarga_url=descarga_url,
                portada_img=portada_url,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _absolute_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http"):
        return url
    if url.startswith("../"):
        return "https://diariooficial.elperuano.pe/" + url.lstrip("../")
    if url.startswith("/"):
        return BASE_URL + url
    return url


# ---------------------------------------------------------------------------
# High-level convenience used by scripts/scrape.py
# ---------------------------------------------------------------------------


def scrape_day(target: date | None = None) -> tuple[list[NormaCruda], list[DocumentoSeccion], dict[str, str]]:
    """Scrape every section for a given day (or today if None).

    Returns (normas, documentos, raw_html_per_section). The raw_html dict can be
    persisted to data/raw/<date>/ for evidence/replay.

    For Normas Legales we hit /Normas/Filtro for historical dates, since that's
    the only section with a working date filter endpoint. For the other 4
    sections we always hit the Load* endpoints (which return the most recent
    bulletins) and filter the parsed documents by date locally.
    """
    session = _client()
    raw: dict[str, str] = {}
    normas: list[NormaCruda] = []
    documentos: list[DocumentoSeccion] = []

    for seccion in Seccion:
        try:
            if seccion is Seccion.NORMAS_LEGALES and target is not None:
                html = fetch_by_date(seccion, target, session)
            else:
                html = fetch_today(seccion, session)
        except requests.RequestException as exc:
            logger.error("Failed to fetch %s: %s", seccion.value, exc)
            raw[seccion.value] = ""
            continue

        raw[seccion.value] = html

        if seccion is Seccion.NORMAS_LEGALES:
            parsed_normas = parse_normas_legales(html)
            if target is not None:
                parsed_normas = [n for n in parsed_normas if n.fecha_publicacion == target]
            normas.extend(parsed_normas)
        else:
            parsed_docs = parse_documentos_seccion(html, seccion)
            if target is not None:
                parsed_docs = [d for d in parsed_docs if d.fecha_publicacion == target]
            documentos.extend(parsed_docs)

    return normas, documentos, raw
