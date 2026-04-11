// Loads the processed JSON data shipped from data/processed/ into site/src/data/
// at build time. The build.py script copies the files; this module just imports
// them via Vite's glob import so Astro picks them up statically.

import type { DiaProcesado, IndexEntry } from "./types";

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
