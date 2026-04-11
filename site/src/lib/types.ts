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
