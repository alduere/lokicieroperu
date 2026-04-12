// Loads the processed JSON data shipped from data/processed/ into site/src/data/
// at build time. The build.py script copies the files; this module just imports
// them via Vite's glob import so Astro picks them up statically.

import type { DiaProcesado, IndexEntry, NormaResumida, HubDay, DiaAlertasProcesado } from "./types";

const dayModules = import.meta.glob<{ default: DiaProcesado }>(
  "/src/data/2*-*-*.json",
  { eager: true, import: "default" },
);

let _indexFile: { fechas: IndexEntry[] } | null = null;
try {
  _indexFile = (
    await import("../data/index.json", { with: { type: "json" } })
  ).default as { fechas: IndexEntry[] };
} catch {
  _indexFile = { fechas: [] };
}

export const days: Record<string, DiaProcesado> = Object.fromEntries(
  Object.entries(dayModules).map(([path, mod]) => {
    const date = path.split("/").pop()!.replace(".json", "");
    return [date, mod];
  }),
);

export const sortedDates: string[] = Object.keys(days).sort().reverse();

export const indexFile = _indexFile;

export function getDay(date: string): DiaProcesado | null {
  return days[date] ?? null;
}

export function latestDate(): string | null {
  return sortedDates[0] ?? null;
}

export function formatFechaEs(date: string): string {
  const d = new Date(date + "T12:00:00-05:00");
  const dias = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
  const meses = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
  ];
  return `${dias[d.getDay()]} ${d.getDate()} de ${meses[d.getMonth()]} de ${d.getFullYear()}`;
}

/** Flatten every norm across every day with a back-reference to its date. */
export function allNorms(): Array<NormaResumida & { _fecha: string }> {
  const out: Array<NormaResumida & { _fecha: string }> = [];
  for (const date of sortedDates) {
    const dia = days[date];
    for (const n of dia.normas) {
      out.push({ ...n, _fecha: date });
    }
  }
  return out;
}

/** Look up a single norm by id, returning the norm and its date. */
export function findNorm(id: string): { norma: NormaResumida; fecha: string } | null {
  for (const date of sortedDates) {
    const dia = days[date];
    const n = dia.normas.find((x) => x.id === id);
    if (n) return { norma: n, fecha: date };
  }
  return null;
}

/** Distinct sorted set of all tipo_corto values for filter UIs. */
export function distinctTipos(): string[] {
  const s = new Set<string>();
  for (const date of sortedDates) {
    for (const n of days[date].normas) s.add(n.tipo_corto || "OTRO");
  }
  return [...s].sort();
}

export function distinctSectores(): string[] {
  const s = new Set<string>();
  for (const date of sortedDates) {
    for (const n of days[date].normas) {
      for (const sector of n.sectores) s.add(sector);
    }
  }
  return [...s].sort();
}

// NEW: Hub data loading
const hubModules = import.meta.glob<{ default: HubDay }>(
  "/src/data/hub/2*-*-*.json",
  { eager: true, import: "default" },
);

export const hubDays: Record<string, HubDay> = Object.fromEntries(
  Object.entries(hubModules).map(([path, mod]) => {
    const date = path.split("/").pop()!.replace(".json", "");
    return [date, mod];
  }),
);

export const hubSortedDates: string[] = Object.keys(hubDays).sort().reverse();

export function getHubDay(date: string): HubDay | null {
  return hubDays[date] ?? null;
}

export function latestHubDate(): string | null {
  return hubSortedDates[0] ?? null;
}

// NEW: El Peruano source-specific data (same data, loaded from elperuano/ subdirectory)
const epModules = import.meta.glob<{ default: DiaProcesado }>(
  "/src/data/elperuano/2*-*-*.json",
  { eager: true, import: "default" },
);

export const epDays: Record<string, DiaProcesado> = Object.fromEntries(
  Object.entries(epModules).map(([path, mod]) => {
    const date = path.split("/").pop()!.replace(".json", "");
    return [date, mod];
  }),
);

export const epSortedDates: string[] = Object.keys(epDays).sort().reverse();

export function getEpDay(date: string): DiaProcesado | null {
  return epDays[date] ?? null;
}

export function latestEpDate(): string | null {
  return epSortedDates[0] ?? null;
}

// Keep existing El Peruano helpers working with ep prefix too
export function epAllNorms(): Array<NormaResumida & { _fecha: string }> {
  const out: Array<NormaResumida & { _fecha: string }> = [];
  for (const date of epSortedDates) {
    const dia = epDays[date];
    if (dia) for (const n of dia.normas) out.push({ ...n, _fecha: date });
  }
  return out;
}

export function epFindNorm(id: string): { norma: NormaResumida; fecha: string } | null {
  for (const date of epSortedDates) {
    const dia = epDays[date];
    if (!dia) continue;
    const n = dia.normas.find((x) => x.id === id);
    if (n) return { norma: n, fecha: date };
  }
  return null;
}

// NEW: INDECOPI Alertas data
const indecopiModules = import.meta.glob<{ default: DiaAlertasProcesado }>(
  "/src/data/indecopi-alertas/2*-*-*.json",
  { eager: true, import: "default" },
);

export const indecopiDays: Record<string, DiaAlertasProcesado> = Object.fromEntries(
  Object.entries(indecopiModules).map(([path, mod]) => {
    const date = path.split("/").pop()!.replace(".json", "");
    return [date, mod];
  }),
);

export const indecopiSortedDates: string[] = Object.keys(indecopiDays).sort().reverse();

export function getIndecopiDay(date: string): DiaAlertasProcesado | null {
  return indecopiDays[date] ?? null;
}

export function latestIndecopiDate(): string | null {
  return indecopiSortedDates[0] ?? null;
}
