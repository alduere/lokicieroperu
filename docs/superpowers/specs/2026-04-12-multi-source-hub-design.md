# Loki-ciero Perú — Multi-Source Hub Design

## Problem

Loki-ciero Perú currently only covers El Peruano. The user wants to expand to 15+ Peruvian regulatory sources (INDECOPI, SUNAT, SBS, OSCE, SMV, SUNARP, etc.), each as an independent section with its own content, search, and archive. The current single-source site architecture doesn't support this.

## Decisions Made

| Decision | Choice |
|----------|--------|
| Navigation pattern | Hub central with dedicated pages per source |
| Return to hub | Logo click + breadcrumb |
| Hub card density | Metrics with pills (name + count + category breakdown) |
| Search | Global search in hub + per-source search with source-specific filters |
| Scale target | 15+ sources |

## Architecture

### URL Structure

```
/                           → Hub (daily summary of all sources)
/buscar                     → Global search (all sources, Pagefind)
/elperuano/                 → El Peruano — today's edition
/elperuano/[date]/          → El Peruano — specific date
/elperuano/n/[id]/          → El Peruano — individual norm detail
/elperuano/buscar/          → El Peruano — search with source-specific filters
/elperuano/archivo/         → El Peruano — archive
/indecopi/                  → INDECOPI — today's edition
/indecopi/[date]/           → INDECOPI — specific date
/indecopi/item/[id]/        → INDECOPI — individual item detail
/indecopi/buscar/           → INDECOPI — search with source-specific filters
/indecopi/archivo/          → INDECOPI — archive
/[source-slug]/             → Same pattern for each additional source
```

### Hub Page (`/`)

**Header:**
- Logo "LK" (always links to hub)
- Site name: "Loki-ciero Perú"
- Subtitle: "Inteligencia regulatoria"
- Nav: Inicio (active) | Buscar todo

**Hero section:**
- Current date (Spanish formatted)
- Title: "Resumen del día"
- Global stats: total publications, active sources, high-impact alerts

**Global search bar:**
- Pagefind-powered search across all sources
- Placeholder: "Buscar en todas las fuentes..."

**Source grid (3 columns desktop, 1 column mobile):**
- Each source is a card linking to its dedicated section
- Card content: name, subtitle, count, count label, category pills, "Actualizado" timestamp
- Source with the highest publication count gets `grid-column: span 2` (featured). Ties broken by source registry order.
- Sources with 0 publications grouped under "Sin novedades hoy", visually muted (opacity 0.45)
- Cards sorted by publication count descending, then by registry order

**Card anatomy:**
```
┌─────────────────────────────────┐
│ Name                    Count   │
│ Subtitle            count-label │
│                                 │
│ [pill] [pill] [pill]            │
│                                 │
│ Actualizado 7:00 AM             │
└─────────────────────────────────┘
```

Pills are color-coded per source category system (not a universal palette). Each source defines its own categories and pill colors.

### Source Page (`/[source-slug]/`)

**Header:**
- Same logo (links to hub)
- Nav changes to: Hoy | Buscar | Archivo (scoped to this source)

**Breadcrumb:**
- `Inicio › [Source Name]`

**Hero section:**
- Current date
- Source name as title
- Source-specific stats (varies per source)

**Category tabs (client-side filtering, no page reload):**
- Horizontal pills for filtering by category within the source
- "Todo (N)" always first, then source-specific categories
- Example for INDECOPI: Todo | Alertas | Sanciones | Marcas | Liquidación | Resoluciones
- Example for El Peruano: keeps existing FilterBar (impacto, tipo, sector)
- Filtering works by toggling visibility of content cards via data attributes (same pattern as existing FilterBar)

**Content:**
- Each source defines its own content layout
- El Peruano keeps its existing BentoGrid + SectorCard layout
- INDECOPI uses a vertical card list with type pill, title, summary, reference

**Search (`/[source-slug]/buscar/`):**
- Pagefind scoped to this source
- Filters specific to the source's category system

**Archive (`/[source-slug]/archivo/`):**
- Table of dates with per-date stats
- Same pattern as current archivo but scoped to one source

### Data Layer

**Current state:** `site/src/data/YYYY-MM-DD.json` files with `DiaProcesado` structure.

**New structure:**
```
site/src/data/
├── hub/
│   └── YYYY-MM-DD.json        # Hub summary (all sources, lightweight)
├── elperuano/
│   └── YYYY-MM-DD.json        # Full El Peruano data (existing format)
├── indecopi/
│   └── YYYY-MM-DD.json        # Full INDECOPI data
└── [source-slug]/
    └── YYYY-MM-DD.json        # Each source gets its own directory
```

**Hub summary JSON (`hub/YYYY-MM-DD.json`):**
```typescript
interface HubDay {
  fecha: string;
  sources: SourceSummary[];
  stats: {
    total_publicaciones: number;
    fuentes_activas: number;
    alertas_alto: number;
  };
  generated_at: string;
}

interface SourceSummary {
  slug: string;              // "elperuano", "indecopi", etc.
  nombre: string;            // "El Peruano"
  subtitulo: string;         // "Diario Oficial"
  total: number;             // Total items for the day
  label: string;             // "normas hoy", "resoluciones", etc.
  categorias: CategoryPill[];
  updated_at: string;        // ISO timestamp
}

interface CategoryPill {
  nombre: string;            // "alto", "alertas", "sanciones"
  count: number;
  color: string;             // Tailwind color class or hex
}
```

**Source data JSON** — each source defines its own schema extending a base interface:
```typescript
interface BaseSourceDay {
  fecha: string;
  source_slug: string;
  items: BaseItem[];
  stats: Record<string, number>;
  generated_at: string;
}

interface BaseItem {
  id: string;
  titulo: string;
  resumen: string | null;
  categoria: string;
  fecha_publicacion: string;
  link_oficial: string | null;
}
```

El Peruano's `DiaProcesado` maps to this base with its existing fields. INDECOPI extends with fields like `tipo_procedimiento`, `entidad_sancionada`, `monto_multa`, etc.

### Source Registry

A central config file defines all sources and their metadata:

```typescript
// site/src/lib/sources.ts
interface SourceConfig {
  slug: string;
  nombre: string;
  subtitulo: string;
  itemLabel: string;          // "normas", "resoluciones", "publicaciones"
  categorias: {
    key: string;
    label: string;
    pillClass: string;        // Tailwind classes for pill color
  }[];
  enabled: boolean;           // Toggle sources on/off
}
```

Adding a new source = adding an entry to this registry + a scraper + a data directory. The site generates pages dynamically from the registry.

### Astro Page Generation

Pages are generated dynamically from the source registry using `getStaticPaths()`:

- `site/src/pages/[source]/index.astro` — Source home (today)
- `site/src/pages/[source]/[date].astro` — Source by date
- `site/src/pages/[source]/item/[id].astro` — Item detail
- `site/src/pages/[source]/buscar.astro` — Source search
- `site/src/pages/[source]/archivo.astro` — Source archive

The hub pages remain at root level:
- `site/src/pages/index.astro` — Hub
- `site/src/pages/buscar.astro` — Global search

### Component Reuse

**Shared components (all sources):**
- `Base.astro` — Layout with header, footer, breadcrumb
- `HubCard.astro` — Source card for the hub grid
- `SearchBar.astro` — Pagefind integration (configurable scope)
- `ArchiveTable.astro` — Date table with stats

**Source-specific components:**
- El Peruano keeps: `StatsHero`, `FilterBar`, `BentoGrid`, `SectorCard`, `NormaItem`
- INDECOPI gets: `IndecopiHero`, `CategoryTabs`, `ItemCard`
- Future sources can reuse generic components or create custom ones

### Python Pipeline Changes

**Current:** Single pipeline (scrape → summarize → build) for El Peruano.

**New:** Modular pipeline with per-source scrapers:
```
scripts/
├── scrapers/
│   ├── elperuano.py          # Existing scraper (moved)
│   ├── indecopi.py           # New INDECOPI scraper
│   └── base.py               # Base scraper interface
├── summarizers/
│   ├── elperuano.py          # Existing summarizer (moved)
│   ├── indecopi.py           # New INDECOPI summarizer
│   └── base.py               # Base summarizer interface
├── lib/
│   ├── schemas.py            # Shared + per-source schemas
│   ├── gemini.py             # Gemini API client (shared)
│   └── brevo.py              # Email client (shared)
├── build.py                  # Orchestrates all sources → site build
├── scrape.py                 # Runs all enabled scrapers
├── summarize.py              # Runs all enabled summarizers
├── notify.py                 # Telegram notification
└── notify_email.py           # Email notification
```

**GitHub Actions workflow** runs all scrapers sequentially, then builds once.

### Notifications

Email and Telegram notifications aggregate across all sources:
- Subject: "Loki-ciero Perú — 12 abril 2026: 83 publicaciones, 6 fuentes"
- Body: source-by-source summary with counts and top items
- Link to hub page

### Migration Path

Phase 1 (this implementation):
1. Restructure site to hub + source pages
2. Move El Peruano under `/elperuano/` prefix
3. Restructure data layer
4. Restructure Python pipeline to modular scrapers
5. Add INDECOPI scraper + summarizer

Phase 2 (future):
- Add remaining sources one at a time
- Each new source = new scraper + entry in source registry
- INDECOPI data sources (exact URLs/APIs to scrape) to be determined during implementation by researching INDECOPI's public portals

### Redirects

Old URLs (`/`, `/2026-04-11/`, `/n/xxx/`, `/buscar`, `/archivo`) redirect to new paths under `/elperuano/` to avoid breaking existing links.

## Styling

- Keep existing Tailwind config with `ink.*` and `impact.*` palette
- Hub uses same design language (Inter font, glass effects, bento aesthetic)
- Source-specific pill colors defined per source in registry
- Responsive: 3-col grid on desktop, 1-col on mobile
- Featured card (most content) spans 2 columns
- Empty sources grouped and muted

## Out of Scope

- Real-time updates (stays as daily cron)
- User accounts or personalization
- API endpoints (stays static)
- RSS feed (can add later)
- Per-source PDF generation (only El Peruano has PDF currently)
