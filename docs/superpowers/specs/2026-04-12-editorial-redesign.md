# Loki-ciero Perú — Editorial Redesign Spec

## Problem

The current site uses a generic glass-card dashboard aesthetic with the default Slate gray Tailwind palette. It looks like any template. For a regulatory intelligence product, the visual identity should convey credibility, tradition, and authority — like a quality newspaper.

## Decisions Made

| Decision | Choice |
|----------|--------|
| Style direction | Editorial / Newspaper (prensa clásica) |
| Color palette | Pergamino — parchment bg, sepia inks, dark brown text |
| Typography | Playfair Display (titles) + Source Sans 3 (body) |
| Component style | Ruled lines / no cards — items separated by horizontal rules |
| Source navigation | Horizontal tabs fixed below header |

## Color Palette

### Core

| Token | Hex | Usage |
|-------|-----|-------|
| `parchment` | `#f5f0e6` | Page background |
| `paper` | `#faf5eb` | Elevated surfaces (if needed) |
| `ink` | `#2c1810` | Primary text, headings, header rules |
| `ink-light` | `#4a3f30` | Body text, secondary content |
| `sepia` | `#7a6b55` | Muted text, labels, metadata |
| `rule` | `#c4b69c` | Horizontal dividers, borders |
| `rule-light` | `#d8ccb8` | Lighter dividers between items |

### Impact (semantic — unchanged purpose, adjusted for warmth)

| Token | Hex | Usage |
|-------|-----|-------|
| `alto` | `#8b2020` | High impact — deeper red, not neon |
| `medio` | `#9a6b1a` | Medium impact — warm amber |
| `bajo` | `#3a6b3a` | Low impact — forest green |

Impact pills use 10% opacity background of their color with full-color text (same pattern as current `.impact-pill` but with the new hex values).

## Typography

### Fonts

| Role | Font | Weights | Source |
|------|------|---------|--------|
| Display / headings | Playfair Display | 700, 800, 900 | Google Fonts |
| Body / UI | Source Sans 3 | 400, 600, 700 | Google Fonts |
| Monospace (data) | JetBrains Mono | 400 | Existing (keep) |

### Scale

- Masthead title: Playfair 900, 18px
- Hero date: Playfair 900, 36px (desktop), 26px (mobile)
- Source section heading: Playfair 900, 22px
- Item title: Playfair 700, 14px
- Body text: Source Sans 400, 13px, line-height 1.6
- Labels/meta: Source Sans 600, 9-11px, uppercase, letter-spacing 0.15em
- Impact pills: Source Sans 700, 9-10px, uppercase

## Layout Structure

### Header

Double rule at top (3px solid + 1px solid, 2px gap — classic press style). Sticky. Background matches parchment.

Contents:
- Left: LK logo (square, dark brown bg, paper text) + "Loki-ciero Perú" in Playfair 900 + "Inteligencia regulatoria" label
- Right: Nav links in Source Sans 600 (Buscar todo, Repo)

### Source Tabs Bar

Fixed bar directly below header, with light background tint (`rgba(44,24,16,0.03)`), separated by a bottom rule.

Tabs:
- "Todas" — shows all sources (default)
- "El Peruano (55)" — filters to El Peruano only
- "INDECOPI (1)" — filters to INDECOPI only

Active tab: bold text + 2px bottom border in ink color. Inactive: sepia text, no border.

Counts shown as inline badge or parenthetical. Tabs use client-side filtering (toggle visibility via data attributes, same pattern as existing FilterBar). No page reload.

When inside a source page (`/elperuano/`, `/indecopi-alertas/`), the tabs bar is replaced by source-specific nav: "Hoy | Buscar | Archivo".

### Hero Section

Centered composition:
- "Resumen del día" label (uppercase, spaced, sepia)
- Full date in Playfair 900, 36px
- Stats row: 3 numbers centered (Publicaciones, Alto impacto, Fuentes activas)
- Bottom rule separator

### Source Blocks

Each source is a section with:
1. **Section divider**: horizontal rule with centered label "Fuentes"
2. **Source header**: thick 2px bottom rule, source name (Playfair 900, 22px) left, count right
3. **Source subtitle**: italic Playfair, sepia (e.g., "Diario Oficial — normas legales del día")
4. **Impact pills row**: solid-bg colored pills with counts
5. **Item list**: ruled lines (1px `rule-light`), each item has:
   - Impact tag (left, colored bg at 10% opacity)
   - Title (Playfair 700, 14px)
   - Meta line (Source Sans, 11px, sepia)
   - Summary (Source Sans, 12.5px, `ink-light`) — only for alto/medio items
6. **"+ N more →"** link at bottom in italic Playfair

### Footer

Double rule at bottom (matching header). Two columns:
- Left: Source links (underlined, sepia)
- Right: "N días publicados" in italic Playfair

### Item Detail Pages (norm / alert)

Keep the same information architecture but restyle:
- Breadcrumb in Source Sans, sepia
- Header block with thick top rule instead of glass card
- Impact tag + type/number + entity as metadata line
- Title in Playfair 800, 24px
- Sumilla in italic Playfair
- Sections separated by rules, not glass cards
- Classification tags with parchment-tinted backgrounds

### Search Page

Same Pagefind integration, restyled:
- Pagefind CSS variables updated to match pergamino palette
- Input with sepia border, parchment background
- Results with rule separators instead of card borders

### Archive Page

Table with ruled rows (no alternating colors). Playfair for date column. Source Sans mono for numbers. Sepia for muted values.

## Tailwind Config Changes

Replace the current `ink.*` and `impact.*` color tokens:

```javascript
colors: {
  parchment: { DEFAULT: '#f5f0e6', light: '#faf5eb' },
  ink: {
    DEFAULT: '#2c1810',
    light: '#4a3f30',
    sepia: '#7a6b55',
    rule: '#c4b69c',
    'rule-light': '#d8ccb8',
  },
  impact: {
    alto: '#8b2020',
    medio: '#9a6b1a',
    bajo: '#3a6b3a',
  },
}
```

Font families:
```javascript
fontFamily: {
  display: ['Playfair Display', 'Georgia', 'serif'],
  sans: ['Source Sans 3', 'system-ui', 'sans-serif'],
  mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
}
```

## Global CSS Changes

- Body: `bg-parchment text-ink`
- Remove `.glass` class — replace with ruled sections
- Update `.impact-pill` colors to new palette
- Add `.double-rule` utility for header/footer borders
- Add `.source-tab` styles for the tabs bar

## Files to Modify

| File | Change |
|------|--------|
| `tailwind.config.mjs` | New color tokens, font families |
| `src/styles/global.css` | Remove glass, add editorial utilities |
| `src/layouts/Base.astro` | New header with double rule + tabs bar, new footer |
| `src/pages/index.astro` | New hub layout with ruled source blocks + tabs |
| `src/components/HubCard.astro` | Delete — replaced by ruled source blocks |
| `src/components/StatsHero.astro` | Restyle to editorial hero |
| `src/components/BentoGrid.astro` | Restyle to ruled item list |
| `src/components/SectorCard.astro` | Restyle to ruled items |
| `src/components/FilterBar.astro` | Restyle controls + add to tabs |
| `src/components/NormaItem.astro` | Restyle to ruled line item |
| `src/pages/elperuano/*.astro` | Apply editorial styling |
| `src/pages/indecopi-alertas/*.astro` | Apply editorial styling |
| `src/pages/buscar.astro` | Pagefind CSS variable updates |
| `src/pages/elperuano/buscar.astro` | Same |
| `src/pages/elperuano/archivo.astro` | Ruled table |
| `src/pages/elperuano/n/[id].astro` | Ruled sections instead of glass |
| `src/pages/indecopi-alertas/item/[id].astro` | Ruled sections |
| `src/pages/indecopi-alertas/archivo.astro` | Ruled table |

## Font Loading

Replace the current Inter font import from rsms.me with Google Fonts in `Base.astro`:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800;900&family=Source+Sans+3:ital,wght@0,400;0,600;0,700;1,400&display=swap" rel="stylesheet">
```

## Out of Scope

- Dark mode (the pergamino identity is inherently light)
- Animations / scroll effects
- Layout structure changes (hub + source pages architecture stays the same)
- Python pipeline or data schema changes
