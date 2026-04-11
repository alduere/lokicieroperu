# NotiRelevantePerú

> Resumen diario con IA de las normas legales publicadas en el Diario Oficial El Peruano.

Cada día a las **7:00 AM hora Lima** (12:00 UTC), un workflow de GitHub Actions:

1. **Scrapea** El Peruano (Normas Legales, Boletín Oficial, Casaciones, Concesiones Mineras, Patentes)
2. **Resume** cada norma con Gemini 2.5 Flash (resumen ejecutivo + clasificación de impacto + sectores)
3. **Genera** un PDF tipo "diario digital" del día completo
4. **Publica** un dashboard bento navegable en GitHub Pages
5. **Envía** el PDF a Telegram con link al dashboard

Sitio: https://alduere.github.io/notirelevanteperu

## Stack

- **Python 3.11+** con [`uv`](https://docs.astral.sh/uv/)
- **`requests` + `beautifulsoup4`** para scrapear (El Peruano usa endpoints AJAX server-rendered, sin JS)
- **`google-genai`** para resumir con Gemini 2.5 Flash (free tier: 1500 req/día)
- **WeasyPrint** para el PDF (HTML+CSS → PDF)
- **Astro + TailwindCSS** para el dashboard estático
- **GitHub Actions** para el cron diario y el deploy de Pages
- **Telegram Bot API** para notificación

## Setup local

```bash
# 1. Instalar dependencias Python
uv sync

# 2. Instalar dependencias del sitio Astro
cd site && npm install && cd ..

# 3. Crear .env con tus credenciales (basado en .env.example)
cp .env.example .env
$EDITOR .env

# 4. Tests
uv run pytest

# 5. Pipeline manual (un día)
uv run python -m scripts.scrape --date 2026-04-10
uv run python -m scripts.summarize --date 2026-04-10
uv run python -m scripts.build --date 2026-04-10
uv run python -m scripts.notify --date 2026-04-10 --dry-run
```

## Pipeline

```
scrape.py    → data/raw/<date>/{normas_legales,boletin_oficial,...}.html + parsed.json
summarize.py → data/processed/<date>.json (con resumen ejecutivo + impacto + sectores)
build.py     → pdfs/<date>.pdf  +  site/dist/ (Astro build estático)
notify.py    → POST PDF + caption a Telegram
```

Cada script es **idempotente**: re-ejecutarlo con el mismo `--date` no gasta cuota de Gemini ni envía duplicados.

## GitHub Actions

- **`.github/workflows/daily.yml`** — cron `0 12 * * *` (12:00 UTC = 7:00 Lima). También botón manual.
- **`.github/workflows/backfill.yml`** — `workflow_dispatch` con inputs `start_date` / `end_date`. Para procesar días pasados.
- **`.github/workflows/deploy.yml`** — deploy de GitHub Pages cuando `daily.yml` termina.

### Secrets necesarios

En `Settings → Secrets and variables → Actions`:

| Secret | De dónde sale |
|---|---|
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey (free) |
| `TELEGRAM_BOT_TOKEN` | Conversación con [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | [@userinfobot](https://t.me/userinfobot) o id del grupo/canal |

## Estructura del repo

```
scripts/
  scrape.py          # entry: scrape one day
  summarize.py       # entry: summarize parsed → processed
  build.py           # entry: PDFs + Astro build
  notify.py          # entry: post to Telegram
  lib/
    elperuano.py     # HTTP client + parsers
    gemini.py        # Gemini client + prompts
    schemas.py       # pydantic models
    pdf.py           # WeasyPrint helper
    telegram.py      # TG bot client
data/
  raw/<date>/        # HTML crudo capturado de El Peruano
  processed/<date>.json
  processed/index.json
pdfs/<date>.pdf
site/                # Astro project (bento dashboard)
templates/pdf_diario.html  # WeasyPrint template
tests/
  fixtures/elperuano/      # HTML real para tests
.github/workflows/
```

## Por qué esta arquitectura

- **Sin servidor propio**: GitHub Actions hace de cron, GitHub Pages aloja la web, todo gratis.
- **Sin base de datos**: cada día queda como un JSON commiteado al repo. La historia es git history.
- **Sin Claude API**: usa Gemini 2.5 Flash que tiene tier gratuito muy generoso (1500 req/día).
- **Sin Playwright**: El Peruano expone endpoints `Load*` y `Filtro` que devuelven HTML server-rendered. Solo `requests` + `beautifulsoup4`.
- **Reproducible**: cualquiera puede correr el pipeline localmente con su propia clave de Gemini.

## Licencia

MIT. El contenido scrapeado de El Peruano es de dominio público (Decreto Legislativo 822).
