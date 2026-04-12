# Loki-ciero v2 — Design Spec

**Date:** 2026-04-12
**Status:** Approved
**Scope:** Rebrand + ticker financiero + tab de noticias

---

## 1. Rebrand: Loki-ciero + Logo heráldico

### Nombre

- El masthead muestra "Loki-ciero" en Playfair Display, sin subtítulo.
- La URL base (`/lokicieroperu`) no cambia.

### Logo

- SVG inline de un Pomeranian estilizado como grabado heráldico.
- Monocromático en tono ink/sepia (`#2c1810` / `#4a3f30`), consistente con la paleta pergamino existente.
- Estilo de líneas finas tipo grabado en cobre/acero, evocando escudos de diarios del siglo XIX.
- Tamaño: ~40-48px, posicionado a la izquierda del nombre en el masthead.
- No es una imagen externa — es SVG inline en el componente Base.astro.

### Archivos afectados

- `site/src/layouts/Base.astro` — actualizar masthead con SVG + nuevo nombre.
- `README.md` — actualizar nombre del proyecto.

---

## 2. Ticker financiero

### Ubicación

Barra horizontal en la parte superior de la página, arriba del masthead. No es sticky — scrollea con el contenido.

### Datos

| Dato | Fuente | Unidad | Símbolo yfinance |
|------|--------|--------|-------------------|
| USD/PEN | API BCRP (series estadísticas) | Soles por dólar | N/A |
| Cobre (Cu) | yfinance | USD/lb | `HG=F` |
| Plata (Ag) | yfinance | USD/oz | `SI=F` |
| Zinc (Zn) | yfinance | USD/lb | `ZNC=F` o LME |
| Plomo (Pb) | yfinance | USD/lb | `PB=F` o LME |
| Oro (Au) | yfinance | USD/oz | `GC=F` |

Cada precio muestra el valor de cierre del día anterior y una flecha (verde arriba / roja abajo) con porcentaje de variación respecto al día previo.

### Estilo visual

- Fondo: ligeramente más oscuro que parchment (`#e8e0d0`).
- Texto: tono ink, precios en JetBrains Mono.
- Flechas: verde (`#3a6b3a`) para subida, rojo (`#8b2020`) para bajada.
- Separadores `|` en tono sepia entre cada precio.
- Border-bottom `1px solid #c4b69c`.

### Pipeline

- Nuevo scraper: `scripts/scrapers/financiero.py`.
  - Obtiene tipo de cambio del BCRP vía API de series estadísticas.
  - Obtiene precios de minerales vía `yfinance` (cierre del día anterior).
  - Output: `data/processed/financiero/YYYY-MM-DD.json`.
- Schema Pydantic: `DatosFinancieros` con campos: `fecha`, `usd_pen` (valor, variacion_pct), `minerales` (lista de: nombre, simbolo, precio, unidad, variacion_pct).
- No requiere summarización con Gemini — son datos numéricos.
- Se ejecuta en el workflow diario antes del build de Astro.

### Dependencias nuevas

- `yfinance` — agregar a `pyproject.toml`.

### Frontend

- Nuevo componente: `site/src/components/TickerBar.astro`.
- Lee `data/financiero/YYYY-MM-DD.json` (el más reciente disponible).
- Se incluye en `Base.astro` arriba del masthead.

---

## 3. Tab de Noticias como landing page

### Navegación con tabs

La homepage (`/`) cambia de bento grid a un sistema de tabs:

```
[Ticker financiero]
[Logo + Loki-ciero]
[Noticias] [El Peruano] [INDECOPI] [Tribunal Fiscal]
──────────────────────────────────────────────────────
   contenido del tab activo
```

- Cada tab es un enlace a una ruta: `/` (Noticias), `/elperuano/`, `/indecopi/`, `/tribunal-fiscal/`.
- Tab activo se marca con `border-bottom: 2px solid #2c1810`.
- Estilo editorial limpio, sin pills ni botones redondeados.
- La barra de tabs se incluye en `Base.astro` para que aparezca en todas las páginas.
- La estructura es extensible para agregar más tabs en el futuro.

### Fuentes de noticias

| Fuente | Método | Secciones objetivo |
|--------|--------|--------------------|
| Gestión | RSS (`feedparser`) | Economía, Finanzas, Mercados |
| El Comercio | RSS (`feedparser`) | Economía, Política |
| RPP | RSS (`feedparser`) | Economía |
| Andina | RSS (`feedparser`) | Economía, Política |
| Semana Económica | Scraping HTML (`requests` + `beautifulsoup4`) | Todas las secciones |
| BCRP/MEF | RSS o API pública | Comunicados oficiales |

### Scraper

- Nuevo archivo: `scripts/scrapers/noticias.py`.
- Clase `NoticiasScraper` que hereda de `BaseScraper`.
- Internamente tiene sub-handlers por fuente:
  - `_fetch_rss(url)` — parser genérico RSS usando `feedparser`.
  - `_fetch_semana_economica()` — scraping HTML específico.
  - `_fetch_bcrp_comunicados()` — API/RSS del BCRP.
- Cada fuente se registra en `scripts/lib/sources.py` como una sola fuente `noticias` con slug `noticias`.
- Output: `data/raw/noticias/YYYY-MM-DD/parsed.json` con lista de noticias crudas.

### Schema Pydantic

```python
class NoticiaCruda(BaseModel):
    titulo: str
    fuente: str          # "gestion", "elcomercio", "rpp", "andina", "semanaeconomica", "bcrp"
    url: str
    fecha: datetime
    contenido: str       # texto completo o extracto del artículo

class NoticiaResumida(BaseModel):
    titulo: str
    fuente: str
    fuente_display: str  # "Gestión", "El Comercio", etc.
    url: str
    fecha: datetime
    resumen: str         # 2-3 oraciones generadas por Gemini
    categoria: str       # "Economía", "Finanzas", "Política"
    tags: list[str]

class DiaNoticias(BaseModel):
    fecha: str           # YYYY-MM-DD
    noticias: list[NoticiaResumida]
    total: int
    fuentes_activas: list[str]
    prompt_version: str
```

### Summarizer

- Nuevo archivo: `scripts/summarizers/noticias.py`.
- Clase `NoticiasSummarizer` que hereda de `BaseSummarizer`.
- Prompt a Gemini por cada noticia (o en batch si son muchas): generar `resumen`, `categoria`, `tags`.
- Output: `data/processed/noticias/YYYY-MM-DD.json`.
- Idempotente: verifica `prompt_version` antes de re-procesar.

### Dependencias nuevas

- `feedparser` — agregar a `pyproject.toml`.

### Frontend

- `site/src/pages/index.astro` — se reescribe para mostrar el tab de Noticias.
  - Lee `data/noticias/YYYY-MM-DD.json` (el más reciente).
  - Renderiza lista de noticias ordenadas por fecha/hora (más recientes primero).
  - Filtros por fuente (chips clickeables con JavaScript client-side).
- Nuevo componente: `site/src/components/TabBar.astro` — barra de tabs reutilizable.
- Nuevo componente: `site/src/components/NoticiaItem.astro` — item de noticia individual.
- Nuevo componente: `site/src/components/FuenteFilter.astro` — chips de filtro por fuente.
- Nuevos types en `site/src/lib/types.ts`: `NoticiaResumida`, `DiaNoticias`.
- Nueva función en `site/src/lib/data.ts`: `getLatestNoticias()`.

### Las páginas existentes no cambian

- `/elperuano/`, `/elperuano/[date]`, `/elperuano/n/[id]` — sin cambios.
- `/indecopi/`, `/indecopi/alertas/`, etc. — sin cambios.
- `/tribunal-fiscal/` — sin cambios.
- `/buscar` — sin cambios (Pagefind indexará las noticias automáticamente).

---

## 4. Workflow diario actualizado

El pipeline en `.github/workflows/daily.yml` agrega dos nuevos pasos de scraping:

```
1. Scrape (paralelo):
   - elperuano, indecopi-alertas, consumidor, gaceta-pi, tribunal-fiscal
   - noticias (NUEVO)
   - financiero (NUEVO, sin summarización)

2. Summarize (paralelo):
   - elperuano, indecopi-alertas, consumidor, gaceta-pi, tribunal-fiscal
   - noticias (NUEVO)

3. Build (sin cambios en el flujo)
4. Notify (sin cambios)
5. Persist (sin cambios — git add data/ incluye los nuevos directorios)
6. Deploy (sin cambios)
```

---

## 5. Resumen de archivos nuevos y modificados

### Archivos nuevos

| Archivo | Propósito |
|---------|-----------|
| `scripts/scrapers/noticias.py` | Scraper híbrido RSS + HTML para 6 fuentes de noticias |
| `scripts/scrapers/financiero.py` | Tipo de cambio BCRP + precios minerales yfinance |
| `scripts/summarizers/noticias.py` | Summarización de noticias con Gemini |
| `site/src/components/TickerBar.astro` | Barra de precios financieros |
| `site/src/components/TabBar.astro` | Barra de tabs de navegación |
| `site/src/components/NoticiaItem.astro` | Componente de item de noticia |
| `site/src/components/FuenteFilter.astro` | Chips de filtro por fuente |

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `site/src/layouts/Base.astro` | Nuevo masthead (logo SVG + "Loki-ciero"), incluir TickerBar y TabBar |
| `site/src/pages/index.astro` | Reescribir como tab de Noticias (reemplaza bento grid hub) |
| `site/src/lib/types.ts` | Agregar `NoticiaResumida`, `DiaNoticias`, `DatosFinancieros` |
| `site/src/lib/data.ts` | Agregar `getLatestNoticias()`, `getLatestFinanciero()` |
| `site/src/lib/sources.ts` | Registrar fuente `noticias` y `financiero` |
| `scripts/lib/sources.py` | Registrar `noticias` y `financiero` |
| `scripts/lib/schemas.py` | Agregar `NoticiaCruda`, `NoticiaResumida`, `DiaNoticias`, `DatosFinancieros` |
| `pyproject.toml` | Agregar `feedparser`, `yfinance` |
| `.github/workflows/daily.yml` | Agregar pasos de scrape/summarize para noticias y financiero |
| `README.md` | Actualizar nombre y descripción |

---

## 6. Fuera de scope

- No se cambia la URL base (`/lokicieroperu`).
- No se agregan notificaciones específicas para noticias (se puede agregar después).
- No se modifica el PDF diario (solo incluye El Peruano por ahora).
- No se implementa tiempo real — todo es estático, generado en el pipeline diario.
- No se cambia el flujo de búsqueda (Pagefind indexa automáticamente el nuevo contenido).
