export interface SourceConfig {
  slug: string;
  nombre: string;
  subtitulo: string;
  itemLabel: string;
  categorias: { key: string; label: string; pillClass: string }[];
  enabled: boolean;
}

export const SOURCES: Record<string, SourceConfig> = {
  elperuano: {
    slug: "elperuano",
    nombre: "El Peruano",
    subtitulo: "Diario Oficial",
    itemLabel: "normas",
    categorias: [
      { key: "alto", label: "Alto impacto", pillClass: "bg-red-500 text-white" },
      { key: "medio", label: "Medio impacto", pillClass: "bg-orange-400 text-white" },
      { key: "bajo", label: "Bajo impacto", pillClass: "bg-green-500 text-white" },
    ],
    enabled: true,
  },
  "indecopi-alertas": {
    slug: "indecopi-alertas",
    nombre: "INDECOPI Alertas",
    subtitulo: "Alertas de consumo",
    itemLabel: "alertas",
    categorias: [
      { key: "vehiculos", label: "Vehículos", pillClass: "bg-blue-500 text-white" },
      { key: "alimentos", label: "Alimentos", pillClass: "bg-amber-500 text-white" },
      { key: "electronicos", label: "Electrónicos", pillClass: "bg-purple-500 text-white" },
      { key: "otros", label: "Otros", pillClass: "bg-gray-400 text-white" },
    ],
    enabled: true,
  },
};

export function enabledSources(): SourceConfig[] {
  return Object.values(SOURCES).filter((s) => s.enabled);
}

export function getSource(slug: string): SourceConfig {
  const source = SOURCES[slug];
  if (!source) {
    throw new Error(`Unknown source: ${slug}`);
  }
  return source;
}
