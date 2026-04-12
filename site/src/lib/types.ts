export type Impacto = "alto" | "medio" | "bajo";

export interface NormaResumida {
  id: string;
  seccion: string;
  tipo: string;
  tipo_corto: string;
  numero: string | null;
  titulo_oficial: string;
  entidad_emisora: string;
  sumilla: string;
  fecha_publicacion: string;
  link_oficial: string | null;
  descarga_pdf: string | null;
  portada_img: string | null;
  edicion_extraordinaria: boolean;
  resumen_ejecutivo: string | null;
  cambios_clave: string[];
  a_quien_afecta: string | null;
  vigencia: string | null;
  impacto: Impacto;
  impacto_razon: string | null;
  sectores: string[];
  tags: string[];
  prompt_version: number;
}

export interface DocumentoSeccion {
  seccion: string;
  edicion: string;
  fecha_publicacion: string;
  descarga_url: string;
  portada_img: string | null;
}

export interface StatsDia {
  total_normas: number;
  alto: number;
  medio: number;
  bajo: number;
  sectores_top: Array<[string, number]>;
  documentos_otras_secciones: number;
}

export interface DiaProcesado {
  fecha: string;
  normas: NormaResumida[];
  documentos: DocumentoSeccion[];
  stats: StatsDia;
  generated_at: string;
}

export interface IndexEntry {
  fecha: string;
  total_normas: number;
  alto: number;
  medio: number;
  bajo: number;
}

// Hub types
export interface HubDay {
  fecha: string;
  sources: SourceSummary[];
  stats: {
    total_publicaciones: number;
    fuentes_activas: number;
    alertas_alto: number;
  };
  generated_at: string;
}

export interface SourceSummary {
  slug: string;
  nombre: string;
  subtitulo: string;
  total: number;
  label: string;
  categorias: CategoryPill[];
  updated_at: string;
}

export interface CategoryPill {
  nombre: string;
  count: number;
  color: string;
}

// INDECOPI Alertas types
export interface AlertaResumida {
  id: string;
  codigo_alerta: string | null;
  titulo: string;
  sumilla: string | null;
  fecha_publicacion: string;
  categoria: string | null;
  url_slug: string | null;
  nombre_producto: string | null;
  marca: string | null;
  modelo: string | null;
  descripcion_riesgo: string | null;
  descripcion_efectos: string | null;
  medidas_adoptadas: string | null;
  datos_contacto: string | null;
  imagen_url: string | null;
  ficha_url: string | null;
  link_oficial: string | null;
  resumen: string | null;
  impacto: Impacto;
  impacto_razon: string | null;
  tags: string[];
  prompt_version: number;
}

export interface StatsAlertasDia {
  total_alertas: number;
  por_categoria: Array<[string, number]>;
}

export interface DiaAlertasProcesado {
  fecha: string;
  source_slug: string;
  items: AlertaResumida[];
  stats: StatsAlertasDia;
  generated_at: string;
}
