# Telegram Delivery Redesign

**Date:** 2026-04-26
**Status:** Approved

## Context

Loki-ciero Perú delivers a daily digest of Peruvian legal/regulatory information to a single personal Telegram account. The pipeline runs at 6:30 AM Lima time. Currently two messages are sent: a PDF with a dense caption and a separate text message for other sources.

## Goal

Restructure delivery into 3 focused messages that separate concerns: raw stats (with PDF), highlighted content (norms + concessions), and other sources.

## Design

### Message 1 — PDF + minimal caption

Sent always. Attaches the El Peruano PDF.

Caption contains only:
- Date header
- Norm counts by impact level (alto/medio/bajo)
- Top 3 sectors

```
📋 El Peruano · 25 abr 2026
67 normas · 🔴 3 alto  🟡 22 medio  🟢 42 bajo
Sectores: Minería · Salud · Economía
```

### Message 2 — Normas destacadas + Concesiones mineras

Sent only if there is at least one high-impact norm OR at least one mining concession.

**Normas destacadas section** (if any norms with `impacto == "alto"`):
- Shows up to 3 norms
- Each entry: `tipo_corto + número — resumen_ejecutivo` (2-3 lines)

**Concesiones mineras section** (if any concessions extracted from PDFs):
- Header: `⛏️ Concesiones — N otorgadas`
- Up to 4 individual records: `• Titular (Mineral — Xha — Departamento / Provincia)`
  - Omit provincia if not available
- Overflow line: `...y N más` if total > 4

```
🔴 Normas destacadas

DS 021-2026-EM — Modifica reglamento ambiental minero.
Eleva estándares de EIA para concesiones >500ha. Afecta a
titulares mineros y consultoras ambientales.

LEY 32041 — Nueva ley de recursos hídricos. Crea autoridad
única de cuencas. Deroga arts. 45-60 de Ley 29338.

⛏️ Concesiones — 5 otorgadas
• Minera Atacocha SAC (Oro — 500 ha — Pasco / Cerro de Pasco)
• Buenaventura SAA (Cobre — 300 ha — Junín / Yauli)
• + 3 más
```

### Message 3 — Otras fuentes

Sent only if at least one of the following sources has items that day:
- INDECOPI Alertas
- Consumidor
- Tribunal Fiscal
- Gaceta PI

Format unchanged from current implementation, one section per source, sources with 0 items omitted.

## Implementation changes

### `scripts/notify.py`

- Split `_build_elperuano_caption()` into two functions:
  - `_build_pdf_caption()` — stats only (Message 1)
  - `_build_destacadas_message()` — normas alto + concesiones (Message 2)
- Update `main()` to send 3 messages in order, skipping Message 2 if empty

### `scripts/lib/concesiones.py`

- Update `format_concesiones_section()` to include `provincia` in location display:
  - Format: `Departamento / Provincia` when provincia is available
  - Format: `Departamento` when provincia is None or empty

## Behaviour when sources are empty

| Condition | Result |
|-----------|--------|
| No normas alto AND no concesiones | Message 2 skipped |
| No other sources with data | Message 3 skipped |
| Normal day | All 3 messages sent |
