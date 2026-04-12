"""INDECOPI Gaceta de Propiedad Industrial scraper.

Scrapes trademark/patent filings from the IP Gazette portal at
https://pi.indecopi.gob.pe/gaceta/. Uses RichFaces 3.3.2 A4J AJAX
multi-step flow: (1) establish session, (2) select area, (3) search by date.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date
from typing import Any

import requests
from bs4 import BeautifulSoup

from scripts.lib.schemas import SolicitudPICruda

logger = logging.getLogger(__name__)

BASE_URL = "https://pi.indecopi.gob.pe/gaceta"
PAGE_URL = f"{BASE_URL}/"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
REQUEST_DELAY = 1.0  # JSF is heavier than REST APIs


HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-PE,es;q=0.9,en;q=0.5",
}

AJAX_HEADERS = {
    **HEADERS,
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Requested-With": "XMLHttpRequest",
}


def _get_jsessionid(text: str) -> str | None:
    """Extract jsessionid from URL or HTML body."""
    m = re.search(r"jsessionid=([^\x22\x27&\s;]+)", text)
    return m.group(1) if m else None


def _parse_rf3_body(text: str) -> str:
    """Extract body from RichFaces 3.x AJAX response."""
    m = re.search(r"<body>(.*?)</body>", text, re.DOTALL)
    return m.group(1) if m else ""


def _parse_date_ddmmyyyy(val: str) -> date | None:
    """Parse dd/MM/yyyy date string to date object."""
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", (val or "").strip())
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _build_base_form(area: str, from_date: str, to_date: str) -> dict[str, str]:
    """Build the base form data for a search request."""
    from_month = from_date[3:]  # MM/YYYY
    to_month = to_date[3:]

    return {
        "FormListado": "FormListado",
        "FormListado:panBuscandoOpenedState": "",
        "FormListado:panDescargandoOpenedState": "",
        "FormListado:panAlertOpenedState": "",
        "FormListado:cboAreGacetacomboboxField": area,
        "FormListado:cboAreGaceta": area,  # KEY: must set hidden value!
        "FormListado:calendar1InputDate": from_date,
        "FormListado:calendar1InputCurrentDate": from_month,
        "FormListado:calendar2InputDate": to_date,
        "FormListado:calendar2InputCurrentDate": to_month,
        "FormListado:txtNroExpediente": "",
        "FormListado:txtDenominacion": "",
        "FormListado:suggestionDenominacion_selection": "",
        "FormListado:txtSolicitante": "",
        "FormListado:suggestionSolicitante_selection": "",
        "FormListado:txtListaClasesNiza": "Seleccione Clases de Niza ",
        "FormListado:panSelecccionClaseNizaOpenedState": "",
        "autoScroll": "",
        "FormListado:j_idcl": "",
        "FormListado:_link_hidden_": "",
        "javax.faces.ViewState": "j_id1",
    }


def _extract_records(body_html: str) -> list[dict[str, str]]:
    """Extract trademark/patent records from the A4J result table HTML.

    Each record is a rich-table-row with nested sub-tables containing
    key-value pairs like Nro. de Expediente, Fecha de Publicacion, etc.
    """
    soup = BeautifulSoup(body_html, "html.parser")
    table = soup.find("table", id="FormListado3:formDSD:LISTADSDDIN")
    if not table:
        return []

    records: list[dict[str, str]] = []
    data_rows = table.find_all("tr", class_="rich-table-row")

    for row in data_rows:
        record: dict[str, str] = {}
        text = row.get_text(separator="\n", strip=True)

        field_patterns: list[tuple[str, str]] = [
            (r"Nro\. de Expediente:\s*(.+?)(?:\n|Fecha)", "expediente"),
            (r"Fecha de Publicaci.n:\s*(.+?)(?:\n|Fecha)", "fecha_publicacion"),
            (r"Fecha L.mite para Oposici.n:\s*(.+?)(?:\n|Signo)", "fecha_limite_oposicion"),
            (r"Signo Solicitado:\s*(.+?)(?:\n|Fecha)", "signo"),
            (r"Fecha de Presentaci.n:\s*(.+?)(?:\n|Tipo)", "fecha_presentacion"),
            (r"Tipo de Solicitud:\s*(.+?)(?:\n|Solicitante|MULTICLASE)", "tipo_solicitud"),
            (r"Solicitante\(s\):\s*(.+?)(?:\n|Descripci)", "solicitante"),
            (r"Clase:\s*(\d+)", "clase"),
        ]

        for pattern, key in field_patterns:
            m = re.search(pattern, text, re.DOTALL)
            if m:
                record[key] = m.group(1).strip()

        # Fallback: extract from sub-table cells for more reliable parsing
        for td in row.find_all("td"):
            cell_text = td.get_text(strip=True)
            if cell_text.startswith("Nro. de Expediente:") and "expediente" not in record:
                record["expediente"] = cell_text.replace("Nro. de Expediente:", "").strip()

        if record and record.get("expediente"):
            records.append(record)

    return records


def _record_to_solicitud(record: dict[str, str], target: date) -> SolicitudPICruda:
    """Convert a raw parsed record dict into a SolicitudPICruda model."""
    fecha_pub = _parse_date_ddmmyyyy(record.get("fecha_publicacion", "")) or target
    fecha_pres = _parse_date_ddmmyyyy(record.get("fecha_presentacion", ""))
    fecha_lim = _parse_date_ddmmyyyy(record.get("fecha_limite_oposicion", ""))

    return SolicitudPICruda(
        id=record.get("expediente", ""),
        tipo_solicitud=record.get("tipo_solicitud", "Desconocido"),
        signo_solicitado=record.get("signo", ""),
        solicitante=record.get("solicitante", ""),
        clase=record.get("clase"),
        fecha_publicacion=fecha_pub,
        fecha_presentacion=fecha_pres,
        fecha_limite_oposicion=fecha_lim,
        descripcion=record.get("descripcion"),
    )


class GacetaPIScraper:
    """Scraper for the INDECOPI IP Gazette (Gaceta de Propiedad Industrial)."""

    source_slug = "gaceta-pi"

    def scrape_day(self, target: date) -> dict[str, Any]:
        """Scrape trademark filings published on target date.

        Multi-step JSF/A4J flow:
        1. GET page to establish session
        2. AJAX POST to select area (SIGNOS DISTINTIVOS)
        3. AJAX POST to search by date
        4. Parse result table HTML
        """
        session = requests.Session()
        session.headers.update(HEADERS)

        try:
            items = self._fetch_filings(session, target)
        except Exception as exc:
            logger.error("Gaceta PI scrape failed for %s: %s", target.isoformat(), exc)
            items = []

        logger.info("Found %d filings for %s", len(items), target.isoformat())

        return {
            "fecha": target.isoformat(),
            "items": [s.model_dump(mode="json") for s in items],
        }

    def _fetch_filings(
        self, session: requests.Session, target: date
    ) -> list[SolicitudPICruda]:
        """Execute the JSF multi-step flow and return parsed filings."""
        # Step 1: Establish session
        resp = session.get(PAGE_URL, timeout=30)
        resp.raise_for_status()

        jsid = _get_jsessionid(resp.url) or _get_jsessionid(resp.text)
        if not jsid:
            logger.error("Could not extract jsessionid from initial page")
            return []

        action_url = f"{BASE_URL}/index.seam;jsessionid={jsid}"
        logger.debug("Session established: %s", jsid[:30])

        time.sleep(REQUEST_DELAY)

        # Step 2: Select area via AJAX
        date_str = target.strftime("%d/%m/%Y")
        area = "SIGNOS DISTINTIVOS"
        form_data = _build_base_form(area, date_str, date_str)

        area_data = {
            "AJAXREQUEST": "_viewRoot",
            **form_data,
            "FormListado:j_id83": "FormListado:j_id83",
        }

        resp_area = session.post(action_url, data=area_data, headers=AJAX_HEADERS, timeout=30)
        resp_area.raise_for_status()
        logger.debug("Area selection: status=%d, len=%d", resp_area.status_code, len(resp_area.text))

        time.sleep(REQUEST_DELAY)

        # Step 3: Search by date
        search_data = {
            "AJAXREQUEST": "_viewRoot",
            **form_data,
            "FormListado:btnAceptar": "FormListado:btnAceptar",
        }

        resp_search = session.post(action_url, data=search_data, headers=AJAX_HEADERS, timeout=60)
        resp_search.raise_for_status()

        body = _parse_rf3_body(resp_search.text)
        if not body:
            logger.warning("Empty A4J response body for %s", target.isoformat())
            return []

        # Step 4: Parse records
        records = _extract_records(body)
        logger.info("Parsed %d records from result table", len(records))

        solicitudes = [_record_to_solicitud(rec, target) for rec in records]
        return solicitudes
