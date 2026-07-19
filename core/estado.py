"""
core/estado.py — Estado del proyecto, compartido por todos los frontends.

Única fuente de verdad del estado en memoria de un proyecto Bashkar.
La app de escritorio (app.py, Tkinter) y el servidor web (servidor_web.py)
consumen ESTA clase; ninguno define la suya propia. Función pura, sin
tkinter ni HTTP (regla del proyecto: core/ desacoplado de la UI).
"""


class Estado:
    def __init__(self):
        self.reset()

    def reset(self):
        self.publicacion   = "Mi publicación"
        self.periodo       = ""
        self.pdf_dir       = None
        self.out_dir       = None
        self.input_tipo    = "pdf"
        self.archivos_sel  = []
        self.modos_detec   = {}
        self.etz_done      = False
        self.ocr_done      = False
        self.norm_done     = False
        self.norm_version  = "manual"  # "crudo" | "manual" | "ia"
        self.seg_done      = False
        self.anal_done     = False
        self.vis_done      = False
        self.comp_done     = False
        self.corpus_meta   = None
        self.df_articulos  = None
        self.df_firmas     = None
        self.df_secciones  = None
        self.df_campos     = None
        self.df_layout     = None
        self.df_temas      = None
        self.df_doc_temas  = None
        self.graph_path    = None
        self.xlsx_path     = None
        self.word_model    = None
        self.campos_expandidos = {}
        self.datos_visual  = {}
        self.datos_imagenes = {}
        self.datos_comparativo = {}
        self.figuras       = {}
        self.api_key         = ""   # clave activa (compatibilidad legado)
        self.api_keys        = {    # claves por proveedor
            "anthropic": "", "openai": "", "gemini": "", "ollama": "",
        }
        # Switch global: False = modo 100% offline, ninguna función llama APIs externas
        self.ia_habilitada   = False
        # Modelo elegido por etapa. Valores: "<proveedor>/<modelo>"
        self.modelos_etapa   = {
            "ocr_mejora":   "ollama/llava",
            "ner":          "ollama/mistral",
            "deteccion":    "ollama/llava",
            "tono":         "ollama/mistral",
            "narrativas":   "ollama/mistral",
            "asistente":    "ollama/mistral",
        }
        self.max_ia          = 15
        self.campos_semillas = {}
        # Resultados de análisis (inicializados explícitamente para type-safety)
        self.resumen_ocr     = None   # dict con stats de extracción
        self.temas_lda       = None   # list de dicts con palabras por tema
        self.matriz_sim      = None   # DataFrame de similitud comparativa
        self.terminos_dist   = {}     # dict {nombre: [términos distinctivos]}
        self.ner_done        = False
        self.indice_ner_global = {}  # {categoria: {entidad: [art_ids]}}
        self.stopwords_proyecto = []  # palabras extra a filtrar en análisis léxico
        self.lematizar       = True   # False = usar formas originales (corpus histórico)
        self.corpus_txt      = []    # [str] textos planos listos para módulo lingüística
        # v11 DB
        self.repo           = None  # instancia datos.repositorio.Repositorio
        self.ruta_db        = ""    # ruta al archivo .db SQLite
        self.wikidata_enlaces = {}  # {cat: {texto: {id,label,description,url,confianza}}}
        # v17 — comparador
        self.comparar_rutas    = []   # list of str paths for comparison
        self.reporte_comparativo = {} # dict result
        # v17 — intertextualidad
        self.intertex_resultado = {}
        # v18 — confianza
        self.confianza_corpus  = {}
        # v19 — colaboracion
        self.colaboracion_parche = None  # dict parche cargado
        # v20
        self.pptx_path         = None
        # Etiquetador — prompt de detección editable por proyecto
        self.prompt_deteccion  = ""     # vacío = usar prompt por defecto de zone_labeler
        # Semáforos de flujo: "pending" | "ready" | "stale"
        # "ready"   = etapa completada y datos al día
        # "stale"   = completada pero una etapa anterior cambió → re-ejecutar
        # "pending" = nunca ejecutada o reseteada
        self.estado_etapas: dict = {
            "etz":  "pending",
            "ocr":  "pending",
            "norm": "pending",
            "seg":  "pending",
            "anal": "pending",
        }

    def marcar_etapa(self, etapa: str, estado: str):
        """Marca una etapa y propaga 'stale' a todas las etapas posteriores."""
        _orden = ["etz", "ocr", "norm", "seg", "anal"]
        self.estado_etapas[etapa] = estado
        if estado in ("ready", "stale"):
            try:
                idx = _orden.index(etapa)
            except ValueError:
                return
            for posterior in _orden[idx + 1:]:
                if self.estado_etapas.get(posterior) == "ready":
                    self.estado_etapas[posterior] = "stale"
