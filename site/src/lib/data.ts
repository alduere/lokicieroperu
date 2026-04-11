// Loads the processed JSON data shipped from data/processed/ into site/src/data/
// at build time. The build.py script copies the files; this module just imports
// them via Vite's glob import so Astro picks them up statically.

import type { DiaProcesado, IndexEntry, NormaResumida } from "./types";

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
