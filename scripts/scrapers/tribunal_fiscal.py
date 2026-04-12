"""Tribunal Fiscal (Peru Tax Court) scraper.

Scrapes resolution search results from the Tribunal Fiscal's public
HTML interface at apps4.mineco.gob.pe. No authentication required.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date
from typing import Any

import requests
from bs4 import BeautifulSoup

from scripts.lib.schemas import ResolucionTFCruda

logger = logging.getLogger(__name__)

SEARCH_URL = "https://apps4.mineco.gob.pe/ServiciosTF/nuevo_busq_rtf.htm"
SUMILLA_URL = "https://apps4.mineco.gob.pe/ServiciosTF/Sumilla.htm"
PDF_BASE = "https://www.mef.gob.pe/contenidos/tribu_fisc/Tribunal_Fiscal/PDFS"
USER_AGENT = "Mozilla/5.0 LokicieroPeru/0.1 (+https://github.com/alduere/lokicieroperu)"
REQUEST_DELAY = 1.0  # seconds between requests
PAGE_SIZE = 10  # results per page (server default)
MAX_PAGES_PER_SALA = 40  # safety limit per sala — first 400 results

# Sala codes from the search form. We search per-sala to keep result sets
# manageable (~150-350 per sala vs ~6500 for all combined).
SALA_CODES = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "20"]


def _parse_fecha(fecha_str: str) -> date | None:
    """Parse dd/mm/yyyy date string."""
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", (fecha_str or "").strip())
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _extract_sala_from_rtf(rtf_number: str) -> str | None:
    """Extract the sala from an RTF number like '2026_1_00123'."""
    parts = rtf_number.split("_")
    if len(parts) >= 2:
        return parts[1]
    return None


def _build_sumilla_valor(rtf_number: str) -> str | None:
    """Build the 'valor' param for Sumilla.htm from an RTF number.

    RTF format: year_sala_number (e.g. '2025_12_00003')
    Valor format: year(4) + number(6, zero-padded) — sala is NOT included.
    Example: '2025_12_00003' -> '2025000003'
    """
    parts = rtf_number.split("_")
    if len(parts) < 3:
        return None

    year_part = parts[0]
    number_part = parts[2]

    # Pad number to 6 digits
    number_padded = number_part.zfill(6)

    return f"{year_part}{number_padded}"


def _build_pdf_url(rtf_number: str) -> str | None:
    """Build the PDF URL from an RTF number like '2026_1_00123'."""
    parts = rtf_number.split("_")
    if len(parts) < 3:
        return None

    year = parts[0]
    sala = parts[1]
    number = parts[2]

    return f"{PDF_BASE}/{year}/{sala}/{year}_{sala}_{number}.pdf"


def _clean_rtf_number(raw: str) -> str:
    """Strip trailing 'Sumilla' text, leading slashes, and whitespace.

    The HTML table cell contains e.g. '/2025_9_00021Sumilla' — we need
    just '2025_9_00021'.
    """
    cleaned = re.sub(r"Sumilla$", "", raw, flags=re.IGNORECASE).strip()
    cleaned = cleaned.lstrip("/").strip()
    return cleaned


def _parse_total_results(soup: BeautifulSoup) -> int:
    """Extract the total result count from the results page.

    The text appears as 'La búsqueda devolvió6499resultados' (no spaces,
    accented characters).
    """
    text = soup.get_text()
    # Handle both accented and unaccented variants, with or without spaces
    m = re.search(r"b[uú]squeda\s+devolvi[oó]\s*(\d+)\s*resultado", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return 0


def _parse_result_rows(soup: BeautifulSoup) -> list[dict[str, str]]:
    """Parse the result table rows.

    Returns list of dicts with keys: rtf_number, fecha, expediente, sumilla_valor.
    Deduplicates by RTF number (nested tables may cause duplicates).
    The sumilla_valor is extracted from the onclick='openWindowSumilla(...)' attribute
    when present, for accurate sumilla fetching.
    """
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    # The results table has exactly 3-column rows: RTF number, fecha, expediente.
    # Find it by looking for a header row with "Nro. de RTF" followed by data rows.
    tables = soup.find_all("table")

    for table in tables:
        # Use direct children only to avoid nested table duplication
        trs = table.find_all("tr", recursive=False)
        if len(trs) < 2:
            continue

        # Check if any row is the header
        has_header = False
        for tr in trs:
            if "Nro. de RTF" in tr.get_text() and len(tr.find_all("td")) == 3:
                has_header = True
                break

        if not has_header:
            continue

        for tr in trs:
            tds = tr.find_all("td")
            # Only exact 3-column rows are data rows
            if len(tds) != 3:
                continue

            rtf_cell = tds[0]
            rtf_raw = rtf_cell.get_text(strip=True)
            # Must look like an RTF number (year_sala_number pattern)
            if not re.search(r"\d{4}_\d+_\d+", rtf_raw):
                continue

            rtf_text = _clean_rtf_number(rtf_raw)

            # Deduplicate
            if rtf_text in seen:
                continue
            seen.add(rtf_text)

            # Extract sumilla valor from onclick attribute
            sumilla_valor = ""
            sumilla_link = rtf_cell.find("a", onclick=re.compile(r"openWindowSumilla"))
            if sumilla_link:
                onclick = sumilla_link.get("onclick", "")
                valor_m = re.search(r"openWindowSumilla\('(\d+)'\)", onclick)
                if valor_m:
                    sumilla_valor = valor_m.group(1)

            fecha_text = tds[1].get_text(strip=True)
            expediente_text = tds[2].get_text(strip=True)

            rows.append({
                "rtf_number": rtf_text,
                "fecha": fecha_text,
                "expediente": expediente_text,
                "sumilla_valor": sumilla_valor,
            })

        # Once we found the results table, stop looking
        if rows:
            break

    return rows


class TribunalFiscalScraper:
    source_slug = "tribunal-fiscal"

    def scrape_day(self, target: date) -> dict[str, Any]:
        """Fetch resolutions published on the target date."""
        session = requests.Session()
        session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        })

        matching_rows = self._search_all_salas(session, target)
        logger.info(
            "Found %d resolutions for %s", len(matching_rows), target.isoformat()
        )

        items: list[ResolucionTFCruda] = []
        for row in matching_rows:
            rtf_number = row["rtf_number"]
            fecha = _parse_fecha(row["fecha"]) or target
            sala = _extract_sala_from_rtf(rtf_number)

            # Use valor from HTML if available, otherwise build it
            valor = row.get("sumilla_valor") or _build_sumilla_valor(rtf_number)

            # Fetch sumilla
            sumilla_text = self._fetch_sumilla(session, valor)

            pdf_url = _build_pdf_url(rtf_number)
            sumilla_link = (
                f"{SUMILLA_URL}?valor={valor}" if valor else None
            )

            item = ResolucionTFCruda(
                id=rtf_number,
                numero_rtf=rtf_number,
                fecha_rtf=fecha,
                numero_expediente=row.get("expediente") or None,
                sala=sala,
                sumilla=sumilla_text,
                link_pdf=pdf_url,
                link_sumilla=sumilla_link,
            )
            items.append(item)

        return {
            "fecha": target.isoformat(),
            "items": [item.model_dump(mode="json") for item in items],
        }

    def _search_all_salas(
        self, session: requests.Session, target: date
    ) -> list[dict[str, str]]:
        """Search across all salas and aggregate matching rows for the target date.

        Searching per-sala keeps result sets small (~150-350 per sala) vs
        ~6500+ when searching all salas at once. This avoids having to
        paginate through thousands of results.
        """
        all_matching: list[dict[str, str]] = []
        seen_rtf: set[str] = set()

        for sala_code in SALA_CODES:
            sala_matches = self._search_sala(session, target, sala_code)
            for row in sala_matches:
                if row["rtf_number"] not in seen_rtf:
                    seen_rtf.add(row["rtf_number"])
                    all_matching.append(row)

        return all_matching

    def _search_sala(
        self, session: requests.Session, target: date, sala_code: str
    ) -> list[dict[str, str]]:
        """Paginate through one sala's results and filter by target date."""
        matching: list[dict[str, str]] = []
        offset = 0
        total = 0

        for _ in range(MAX_PAGES_PER_SALA):
            params = {
                "Buscar": "navegator",
                "admin": "0",
                "anio": str(target.year),
                "sala": sala_code,
                "count": str(offset),
                "rtfexp": "1",
                "inputOpcion": "rtfexp",
                "nro": "",
                "contribuyente": "",
                "sort": "",
                "sortType": "",
            }

            try:
                resp = session.get(SEARCH_URL, params=params, timeout=30)
                resp.raise_for_status()
            except requests.RequestException as exc:
                logger.error(
                    "Search request failed (sala %s, offset %d): %s",
                    sala_code, offset, exc,
                )
                break

            soup = BeautifulSoup(resp.text, "html.parser")

            if offset == 0:
                total = _parse_total_results(soup)
                if total == 0:
                    break
                logger.debug(
                    "Sala %s: %d total results for year %d",
                    sala_code, total, target.year,
                )

            rows = _parse_result_rows(soup)
            if not rows:
                break

            for row in rows:
                row_date = _parse_fecha(row["fecha"])
                if row_date == target:
                    matching.append(row)

            offset += PAGE_SIZE
            if total > 0 and offset >= min(total, MAX_PAGES_PER_SALA * PAGE_SIZE):
                break

            time.sleep(REQUEST_DELAY)

        if matching:
            logger.info(
                "Sala %s: found %d resolutions for %s",
                sala_code, len(matching), target.isoformat(),
            )

        return matching

    def _fetch_sumilla(
        self, session: requests.Session, valor: str | None
    ) -> str | None:
        """Fetch the sumilla (summary) text for a resolution by its valor code."""
        if not valor:
            return None

        time.sleep(REQUEST_DELAY)

        try:
            resp = session.get(
                SUMILLA_URL, params={"valor": valor}, timeout=30
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Failed to fetch sumilla for valor %s: %s", valor, exc)
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # The sumilla page has a table with two rows:
        #   1. Header "Sumilla RTF:NNNNN-S-YYYY"
        #   2. The actual sumilla text
        # Look for <td> elements with substantial text content.
        best_text = None
        for td in soup.find_all("td"):
            text = td.get_text(strip=True)
            # Skip short cells (headers, labels) and the RTF number header
            if len(text) < 30:
                continue
            if text.startswith("Sumilla RTF:"):
                continue
            # Take the longest text block (the actual sumilla)
            if best_text is None or len(text) > len(best_text):
                best_text = text

        return best_text
