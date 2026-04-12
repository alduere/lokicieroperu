"""INDECOPI Alertas de Consumo scraper.

Uses the public REST API at servicio.indecopi.gob.pe/indecopialertasapi.
No authentication required.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime
from typing import Any

import requests

from scripts.lib.schemas import AlertaCruda

logger = logging.getLogger(__name__)

API_BASE = "https://servicio.indecopi.gob.pe/indecopialertasapi"
USER_AGENT = "Mozilla/5.0 LokicieroPeru/0.1 (+https://github.com/alduere/lokicieroperu)"
REQUEST_DELAY = 0.5  # politeness between requests
PAGE_SIZE = 50  # items per page (API supports pagination)


def _parse_fecha(fecha_str: str) -> date | None:
    """Parse INDECOPI date format DD/MM/YYYY to date object."""
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", fecha_str or "")
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


class IndecopiAlertasScraper:
    source_slug = "indecopi-alertas"

    def scrape_day(self, target: date) -> dict[str, Any]:
        """Fetch alerts published on the target date.

        The INDECOPI API doesn't support date filtering, so we paginate
        through recent alerts and filter by date locally.
        """
        session = requests.Session()
        session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        })

        alertas = self._fetch_alerts_for_date(session, target)
        logger.info("Found %d alerts for %s", len(alertas), target.isoformat())

        # Fetch full details for each alert
        detailed: list[AlertaCruda] = []
        for alerta_basic in alertas:
            slug = alerta_basic.get("url", "")
            if slug:
                detail = self._fetch_detail(session, slug)
                if detail:
                    detailed.append(self._parse_detail(detail, target))
                    continue
            # Fallback: use basic data
            detailed.append(self._parse_basic(alerta_basic, target))

        return {
            "fecha": target.isoformat(),
            "items": [a.model_dump(mode="json") for a in detailed],
        }

    def _fetch_alerts_for_date(
        self, session: requests.Session, target: date
    ) -> list[dict]:
        """Paginate through the API to find alerts published on target date."""
        alerts_for_date: list[dict] = []
        page = 1
        max_pages = 20  # safety limit

        while page <= max_pages:
            url = f"{API_BASE}/public/alerta"
            params = {"page": page, "limit": PAGE_SIZE}

            try:
                resp = session.get(url, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except (requests.RequestException, ValueError) as exc:
                logger.error("API request failed (page %d): %s", page, exc)
                break

            results = data.get("results", [])
            if not results:
                break

            found_older = False
            for item in results:
                pub_date = _parse_fecha(item.get("fechaPublicacion", ""))
                if pub_date == target:
                    alerts_for_date.append(item)
                elif pub_date and pub_date < target:
                    found_older = True

            # Stop paginating if we've gone past our target date
            if found_older:
                break

            total = data.get("total", 0)
            if page * PAGE_SIZE >= total:
                break

            page += 1
            time.sleep(REQUEST_DELAY)

        return alerts_for_date

    def _fetch_detail(self, session: requests.Session, slug: str) -> dict | None:
        """Fetch full alert detail by slug."""
        url = f"{API_BASE}/public/alerta/{slug}"
        try:
            time.sleep(REQUEST_DELAY)
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Failed to fetch detail for %s: %s", slug, exc)
            return None

    def _parse_detail(self, data: dict, target: date) -> AlertaCruda:
        """Parse a full detail API response into AlertaCruda."""
        pub_date = _parse_fecha(data.get("fechaPublicacion", "")) or target
        alert_id = str(data.get("id", data.get("codigoAlerta", "")))

        return AlertaCruda(
            id=alert_id,
            codigo_alerta=data.get("codigoAlerta"),
            titulo=data.get("titulo", ""),
            sumilla=data.get("sumilla"),
            fecha_publicacion=pub_date,
            categoria=data.get("categoria"),
            url_slug=data.get("url"),
            nombre_producto=data.get("nombreProducto"),
            marca=data.get("marca"),
            modelo=data.get("modelo"),
            lote=_str_or_none(data.get("lote")),
            unidades_involucradas=_str_or_none(data.get("unidadesInvolucradas")),
            periodo=data.get("periodo"),
            descripcion_riesgo=data.get("descripcionRiesgo"),
            descripcion_efectos=data.get("descripcionEfectos"),
            medidas_adoptadas=data.get("medidasAdoptadas"),
            datos_contacto=data.get("datosContacto"),
            imagen_url=_build_image_url(data),
            ficha_url=_build_ficha_url(data),
            link_oficial=f"https://alertasdeconsumo.gob.pe/alertas/{data.get('url', '')}",
        )

    def _parse_basic(self, data: dict, target: date) -> AlertaCruda:
        """Parse a basic list API response into AlertaCruda."""
        pub_date = _parse_fecha(data.get("fechaPublicacion", "")) or target
        return AlertaCruda(
            id=str(data.get("id", data.get("url", ""))),
            titulo=data.get("titulo", ""),
            sumilla=data.get("sumilla"),
            fecha_publicacion=pub_date,
            categoria=data.get("categoria"),
            url_slug=data.get("url"),
            link_oficial=f"https://alertasdeconsumo.gob.pe/alertas/{data.get('url', '')}",
        )


def _str_or_none(val: Any) -> str | None:
    """Coerce to str, since the API sometimes returns ints for string fields."""
    if val is None:
        return None
    return str(val)


def _build_image_url(data: dict) -> str | None:
    """Build full image URL from API response fields."""
    ruta = data.get("vcRutaImagen")
    nombre = data.get("nombreImagen")
    if ruta and nombre:
        return f"{ruta}{nombre}"
    return None


def _build_ficha_url(data: dict) -> str | None:
    """Build ficha técnica download URL."""
    alert_id = data.get("id")
    if alert_id:
        return f"{API_BASE}/public/alerta/descargarFichaTecnica/{alert_id}"
    return None
