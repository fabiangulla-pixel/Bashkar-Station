"""core/pipeline_maestro.py — Orquestador del flujo completo de análisis.

Un clic → todo el análisis. El investigador no toca este módulo directamente:
lo dispara la UI con un botón y espera el paquete ZIP.

Fases:
  1. Por archivo: OCR → segmentación → NER → tono
  2. Global: índice NER → topic modeling → red co-ocurrencias → glosario
  3. Visualizaciones: red HTML, mapa, timeline, nubes, heatmap
  4. Salidas: narrativas IA → reporte HTML → Word → TEI → BibTeX → ZIP
"""

from __future__ import annotations

import json
import re
import threading
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable


class PipelineMaestro:
    """
    Orquesta el procesamiento completo de un proyecto Bashkar Station.
    Diseñado para correr en hilo separado sin bloquear la UI tkinter.
    """

    def __init__(
        self,
        bashkar_path: str,
        api_key: str,
        callback_progreso: Callable[[int, str], None] | None = None,
        callback_log: Callable[[str], None] | None = None,
        repositorio=None,
    ):
        self.bashkar_path = Path(bashkar_path)
        self.api_key = api_key
        self.cb_progreso = callback_progreso or (lambda p, m: None)
        self.cb_log = callback_log or (lambda m: None)
        self.repo = repositorio  # instancia Repositorio opcional

        if self.bashkar_path.exists():
            with open(self.bashkar_path, encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {
                "version": "12",
                "proyecto": self.bashkar_path.stem,
                "articulos": [],
                "indice_global": {},
                "topicos": {},
                "metricas_red": {},
                "glosario": {},
                "tono_corpus": {},
                "creado": datetime.now().isoformat(),
            }

        self._carpeta = self.bashkar_path.parent
        self._viz_dir = self._carpeta / "visualizaciones"
        self._viz_dir.mkdir(exist_ok=True)
        self._docs_dir = self._carpeta / "documentos"
        self._docs_dir.mkdir(exist_ok=True)
        self._datos_dir = self._carpeta / "datos"
        self._datos_dir.mkdir(exist_ok=True)

    def _nombre_proyecto(self) -> str:
        """Nombre del proyecto según el esquema que traiga el archivo.

        El pipeline creaba sus propios .bashkar con la clave "proyecto", pero
        los que abre la GUI la llaman "nombre": leyendo solo "proyecto" cada
        entregable (reporte, Word, nombre del ZIP) salía rotulado "Corpus" en
        vez del nombre real del proyecto.
        """
        return str(self.data.get("proyecto")
                   or self.data.get("nombre")
                   or self.bashkar_path.stem
                   or "Corpus")

    # ── Interfaz pública ──────────────────────────────────────────────────────

    def ejecutar_en_hilo(self, articulos_existentes: list | None = None):
        """Lanza el pipeline en hilo daemon. No bloquea la UI."""
        thread = threading.Thread(
            target=self._pipeline_completo,
            args=(articulos_existentes,),
            daemon=True,
        )
        thread.start()
        return thread

    def ejecutar_sincrono(self, articulos_existentes: list | None = None):
        """Ejecuta el pipeline en el hilo actual (para scripts batch)."""
        self._pipeline_completo(articulos_existentes)

    # ── Pipeline interno ──────────────────────────────────────────────────────

    def _pipeline_completo(self, articulos_existentes: list | None):
        try:
            self._log("=== BASHKAR STATION — Pipeline Maestro ===")
            self._log(f"Proyecto: {self._nombre_proyecto()}")
            self._log(f"Inicio: {datetime.now().strftime('%H:%M:%S')}")

            # ── FASE 1: Análisis por artículo ─────────────────────────────────
            if articulos_existentes:
                self._fase1_analisis_articulos(articulos_existentes)

            # ── FASE 2: Análisis globales ─────────────────────────────────────
            self._progreso(40, "Construyendo índice global NER…")
            self._construir_indice_global()

            self._progreso(50, "Modelando tópicos del corpus…")
            self._fase2_topicos()

            self._progreso(60, "Construyendo red de co-ocurrencias…")
            self._fase2_red()

            self._progreso(65, "Construyendo glosario léxico-histórico…")
            self._fase2_glosario()

            self._guardar_bashkar()

            # ── FASE 3: Visualizaciones ───────────────────────────────────────
            self._progreso(70, "Generando visualizaciones…")
            rutas_viz = self._fase3_visualizaciones()

            # ── FASE 4: Salidas académicas ────────────────────────────────────
            self._progreso(85, "Generando narrativas académicas con IA…")
            narrativas = self._fase4_narrativas()

            self._progreso(88, "Generando reporte HTML…")
            ruta_html = self._fase4_reporte_html(narrativas, rutas_viz)

            self._progreso(91, "Exportando secciones Word…")
            self._fase4_word(narrativas)

            self._progreso(94, "Exportando XML-TEI…")
            self._fase4_tei()

            self._progreso(96, "Exportando BibTeX…")
            self._fase4_bibtex()

            self._progreso(98, "Empaquetando ZIP…")
            ruta_zip = self._fase5_zip()

            self._guardar_bashkar()
            self._progreso(100, f"✅ ¡Paquete listo! → {ruta_zip}")
            self._log(f"\n=== Proceso completado: {datetime.now().strftime('%H:%M:%S')} ===")
            self._log(f"Paquete: {ruta_zip}")

        except Exception as e:
            import traceback
            self._log(f"\n⚠ ERROR en pipeline: {e}")
            self._log(traceback.format_exc())
            self._progreso(-1, f"Error: {e}")

    # ── Fase 1: Artículos ─────────────────────────────────────────────────────

    def _fase1_analisis_articulos(self, articulos: list):
        """Aplica NER y tono a cada artículo. Persiste en Repositorio si disponible."""
        try:
            from core.ner_engine import indice_global_vacio, pipeline_ner
        except ImportError:
            self._log("⚠ ner_engine no disponible")
            return

        try:
            import spacy
            nlp = spacy.load("es_core_news_lg")
        except Exception:
            self._log("⚠ spaCy es_core_news_lg no disponible — solo Claude NER")
            nlp = None

        try:
            from core.sentiment_engine import analizar_tono
            con_tono = True
        except ImportError:
            con_tono = False

        total = len(articulos)
        for i, art in enumerate(articulos):
            pct = int(10 + 30 * i / total)
            art_id = art.get("id", f"art_{i:04d}")
            self._progreso(pct, f"[{i+1}/{total}] NER + tono: {art_id}")

            texto = art.get("texto", "")
            if not texto or not texto.strip():
                continue

            # Persistir artículo base en Repositorio
            if self.repo:
                try:
                    self.repo.guardar_articulo({
                        "id":            art_id,
                        "archivo_origen": art.get("archivo_origen", ""),
                        "numero":        art.get("numero", ""),
                        "pagina_inicio": art.get("pagina_inicio"),
                        "pagina_fin":    art.get("pagina_fin"),
                        "tipo":          art.get("tipo", "articulo"),
                        "titulo":        art.get("titulo"),
                        "autor":         art.get("autor"),
                        "fecha_publicacion": art.get("fecha_publicacion"),
                        "seccion":       art.get("seccion"),
                        "palabras":      len(texto.split()),
                        "estado":        "procesando",
                    })
                    # Persistir OCR si hay texto
                    self.repo.guardar_ocr(
                        articulo_id=art_id,
                        texto_crudo=texto,
                        texto_limpio=texto,
                        confianza=art.get("confianza_ocr", 70.0),
                        motor=art.get("motor_ocr", "pipeline"),
                    )
                except Exception as e:
                    self._log(f"  ⚠ Repositorio guardar_articulo {art_id}: {e}")

            if not art.get("ner") and nlp:
                try:
                    art["ner"] = pipeline_ner(
                        texto, nlp, api_key=self.api_key,
                        callback=self._log,
                    )
                except Exception as e:
                    self._log(f"  ⚠ NER error {art_id}: {e}")

            # Persistir entidades NER en Repositorio
            if self.repo and art.get("ner"):
                try:
                    entidades = self._ner_dict_a_lista(art["ner"], art_id)
                    self.repo.guardar_entidades(art_id, entidades)
                except Exception as e:
                    self._log(f"  ⚠ Repositorio guardar_entidades {art_id}: {e}")

            if con_tono and not art.get("tono"):
                try:
                    art["tono"] = analizar_tono(texto, self.api_key)
                except Exception as e:
                    self._log(f"  ⚠ Tono error {art_id}: {e}")

            # Persistir tono en Repositorio
            if self.repo and art.get("tono"):
                try:
                    self.repo.guardar_tono(art_id, art["tono"])
                except Exception as e:
                    self._log(f"  ⚠ Repositorio guardar_tono {art_id}: {e}")

            # Marcar artículo completo en Repositorio
            if self.repo:
                try:
                    self.repo.actualizar_estado(art_id, "completo")
                except Exception as e:
                    self._log(f"  ⚠ Repositorio actualizar_estado {art_id}: {e}")

        self.data["articulos"] = articulos
        self._guardar_bashkar()

    # ── Fase 2: Globales ──────────────────────────────────────────────────────

    def _construir_indice_global(self):
        indice: dict[str, dict] = {
            "personas": {}, "lugares": {}, "organizaciones": {},
            "fechas": {}, "obras_publicaciones": {}, "eventos_historicos": {},
        }

        # Si hay Repositorio, construir índice desde la DB (fuente de verdad)
        if self.repo:
            try:
                rows = self.repo.buscar_entidades()
                CAT_MAP = {
                    "PER": "personas", "LOC": "lugares", "ORG": "organizaciones",
                    "EVE": "eventos_historicos", "OBRA": "obras_publicaciones",
                    "CARGO": "personas",
                }
                for row in rows:
                    cat_raw = row.get("categoria", "")
                    cat = CAT_MAP.get(cat_raw, cat_raw)
                    if cat not in indice:
                        continue
                    ent = str(row.get("texto", "")).strip()
                    art_id = row.get("articulo_id", "?")
                    if len(ent) > 2:
                        indice[cat].setdefault(ent, [])
                        if art_id not in indice[cat][ent]:
                            indice[cat][ent].append(art_id)
                n = sum(len(v) for v in indice.values())
                self._log(f"Índice global (desde DB): {n} entidades únicas")
                self.data["indice_global"] = indice
                return
            except Exception as e:
                self._log(f"  ⚠ Índice desde DB falló, usando JSON: {e}")

        # Fallback: construir desde JSON
        for art in self.data.get("articulos", []):
            art_id = art.get("id", "?")
            for cat, entidades in (art.get("ner") or {}).items():
                if cat not in indice:
                    continue
                for ent in (entidades if isinstance(entidades, list) else []):
                    ent = str(ent).strip()
                    if len(ent) > 2:
                        indice[cat].setdefault(ent, [])
                        if art_id not in indice[cat][ent]:
                            indice[cat][ent].append(art_id)
        self.data["indice_global"] = indice
        n = sum(len(v) for v in indice.values())
        self._log(f"Índice global: {n} entidades únicas")

    def _fase2_topicos(self):
        try:
            from core.topic_engine import modelar_topicos
        except ImportError:
            self._log("⚠ topic_engine no disponible")
            return
        textos = [a.get("texto", "") for a in self.data.get("articulos", [])
                  if a.get("texto", "").strip()]
        if len(textos) < 3:
            self._log("⚠ Menos de 3 textos — omitiendo topic modeling")
            return
        try:
            self.data["topicos"] = modelar_topicos(
                textos,
                n_topicos=min(10, len(textos) // 2),
                api_key=self.api_key,
                usar_bertopic=False,  # NMF por defecto (sin GPU requerido)
                callback=self._log,
            )
        except Exception as e:
            self._log(f"⚠ Topic modeling error: {e}")

    def _fase2_red(self):
        try:
            from core.network_engine import construir_grafo, grafo_a_dict, metricas_red
        except ImportError:
            self._log("⚠ network_engine no disponible")
            return
        if not self.data.get("indice_global"):
            return
        try:
            G = construir_grafo(
                self.data["indice_global"],
                peso_minimo=2,
                callback=self._log,
            )
            self.data["metricas_red"] = metricas_red(G)
            self._grafo = G
        except Exception as e:
            self._log(f"⚠ Red error: {e}")

    def _fase2_glosario(self):
        try:
            from core.lexicon_engine import construir_glosario
        except ImportError:
            self._log("⚠ lexicon_engine no disponible")
            return
        textos = {a.get("id", str(i)): a.get("texto", "")
                  for i, a in enumerate(self.data.get("articulos", []))
                  if a.get("texto", "").strip()}
        if not textos:
            return
        try:
            self.data["glosario"] = construir_glosario(
                textos, self.api_key,
                callback=lambda i, t, a: self._log(f"  Glosario {i}/{t}: {a}"),
            )
        except Exception as e:
            self._log(f"⚠ Glosario error: {e}")

    # ── Fase 3: Visualizaciones ───────────────────────────────────────────────

    def _fase3_visualizaciones(self) -> dict:
        rutas = {}

        # Red HTML
        try:
            from core.network_engine import exportar_pyvis
            if hasattr(self, "_grafo") and self._grafo:
                ruta = self._viz_dir / "red_coocurrencias.html"
                exportar_pyvis(self._grafo, ruta)
                rutas["red"] = str(ruta)
                self._log(f"  ✓ Red HTML: {ruta.name}")
        except Exception as e:
            self._log(f"  ⚠ Red HTML: {e}")

        # Mapa
        try:
            from core.viz_engine import mapa_lugares
            if self.data.get("indice_global", {}).get("lugares"):
                ruta = self._viz_dir / "mapa_corpus.html"
                mapa_lugares(self.data["indice_global"], ruta)
                rutas["mapa"] = str(ruta)
                self._log(f"  ✓ Mapa: {ruta.name}")
        except Exception as e:
            self._log(f"  ⚠ Mapa: {e}")

        # Timeline
        try:
            from core.viz_engine import eventos_desde_ner, timeline_html
            if self.data.get("indice_global"):
                eventos = eventos_desde_ner(self.data["indice_global"])
                ruta = self._viz_dir / "timeline.html"
                timeline_html(eventos, ruta)
                rutas["timeline"] = str(ruta)
                self._log(f"  ✓ Timeline: {ruta.name}")
        except Exception as e:
            self._log(f"  ⚠ Timeline: {e}")

        # Nube de palabras
        try:
            from core.viz_engine import nube_palabras
            textos = [a.get("texto", "") for a in self.data.get("articulos", [])
                      if a.get("texto", "").strip()]
            if textos:
                ruta = self._viz_dir / "nube_corpus.png"
                nube_palabras(textos, ruta, titulo=self._nombre_proyecto())
                rutas["nube"] = str(ruta)
                self._log(f"  ✓ Nube palabras: {ruta.name}")
        except Exception as e:
            self._log(f"  ⚠ Nube: {e}")

        return rutas

    # ── Fase 4: Salidas académicas ────────────────────────────────────────────

    def _fase4_narrativas(self) -> dict:
        narrativas = {}
        try:
            from core.storytelling_engine import generar_narrativa
        except ImportError:
            return narrativas

        if self.data.get("metricas_red"):
            try:
                narrativas["red"] = generar_narrativa(
                    self.data["metricas_red"], self.api_key, seccion="red")
                self._log("  ✓ Narrativa: red")
            except Exception as e:
                self._log(f"  ⚠ Narrativa red: {e}")

        stats = self._stats_corpus()
        try:
            narrativas["corpus"] = generar_narrativa(
                stats, self.api_key, seccion="corpus")
            self._log("  ✓ Narrativa: corpus")
        except Exception as e:
            self._log(f"  ⚠ Narrativa corpus: {e}")

        return narrativas

    def _fase4_reporte_html(self, narrativas: dict, rutas_viz: dict) -> Path:
        ruta = self._docs_dir / "reporte_completo.html"
        try:
            from core.sentiment_engine import estadisticas_tono
            from core.storytelling_engine import generar_reporte_html

            tono_resultados = {
                a.get("id", str(i)): a.get("tono", {})
                for i, a in enumerate(self.data.get("articulos", []))
                if a.get("tono")
            }
            stats_tono = estadisticas_tono(tono_resultados) if tono_resultados else None

            generar_reporte_html(
                proyecto_nombre=self._nombre_proyecto(),
                stats_corpus=self._stats_corpus(),
                indice_ner=self.data.get("indice_global", {}),
                stats_tono=stats_tono,
                metricas_red=self.data.get("metricas_red"),
                narrativas=narrativas,
                ruta=ruta,
                callback=self._log,
            )
            self._log(f"  ✓ Reporte HTML: {ruta.name}")
        except Exception as e:
            self._log(f"  ⚠ Reporte HTML: {e}")
        return ruta

    def _fase4_word(self, narrativas: dict):
        try:
            from core.storytelling_engine import exportar_word
            ruta = self._docs_dir / "seccion_resultados.docx"
            exportar_word(
                proyecto_nombre=self._nombre_proyecto(),
                stats_corpus=self._stats_corpus(),
                indice_ner=self.data.get("indice_global", {}),
                narrativas=narrativas,
                ruta=ruta,
            )
            self._log(f"  ✓ Word: {ruta.name}")
        except Exception as e:
            self._log(f"  ⚠ Word: {e}")

    def _fase4_tei(self):
        try:
            from core.tei_engine import exportar_corpus_tei
            arts = self.data.get("articulos", [])
            if not arts:
                return
            ruta = self._datos_dir / "corpus_anotado.xml"
            exportar_corpus_tei(
                arts,
                ruta=ruta,
                proyecto_nombre=self._nombre_proyecto(),
                callback=self._log,
            )
            self._log(f"  ✓ TEI: {ruta.name}")
        except Exception as e:
            self._log(f"  ⚠ TEI: {e}")

    def _fase4_bibtex(self):
        try:
            from core.tei_engine import exportar_bibtex
            arts = self.data.get("articulos", [])
            if not arts:
                return
            ruta = self._datos_dir / "bibliografia.bib"
            exportar_bibtex(arts, ruta)
            self._log(f"  ✓ BibTeX: {ruta.name}")
        except Exception as e:
            self._log(f"  ⚠ BibTeX: {e}")

    # ── Fase 5: ZIP ──────────────────────────────────────────────────────────

    def _fase5_zip(self) -> Path:
        proyecto = re.sub(r"[^\w\-]", "_", self._nombre_proyecto())
        fecha = datetime.now().strftime("%Y-%m")
        nombre_zip = f"{proyecto}_resultados_{fecha}.zip"
        ruta_zip = self._carpeta / nombre_zip

        directorios = [self._viz_dir, self._docs_dir, self._datos_dir]
        incluir_extra = [self.bashkar_path]

        # Generar LEAME.txt
        leame = self._generar_leame()
        ruta_leame = self._carpeta / "LEAME.txt"
        ruta_leame.write_text(leame, encoding="utf-8")
        incluir_extra.append(ruta_leame)

        with zipfile.ZipFile(ruta_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for directorio in directorios:
                if directorio.exists():
                    for f in directorio.rglob("*"):
                        if f.is_file():
                            zf.write(f, f.relative_to(self._carpeta))
            for f in incluir_extra:
                if f.exists():
                    zf.write(f, f.name)

        n = len(zipfile.ZipFile(ruta_zip).namelist())
        self._log(f"ZIP: {n} archivos → {ruta_zip.name}")
        return ruta_zip

    # ── Utilidades ────────────────────────────────────────────────────────────

    def _stats_corpus(self) -> dict:
        arts = self.data.get("articulos", [])
        textos = [a.get("texto", "") for a in arts]
        return {
            "n_articulos": len(arts),
            "n_palabras_total": sum(len(t.split()) for t in textos if t),
            "proyecto": self._nombre_proyecto(),
            "periodo": self.data.get("periodo", "1930-1940"),
        }

    def _generar_leame(self) -> str:
        proyecto = self._nombre_proyecto()
        fecha = datetime.now().strftime("%d de %B de %Y")
        n_arts = len(self.data.get("articulos", []))
        return f"""BASHKAR STATION — PAQUETE DE INVESTIGACIÓN
Proyecto: {proyecto}
Fecha de generación: {fecha}
Artículos procesados: {n_arts}
Instituto Caro y Cuervo / Gulla Editorial Tools

CONTENIDO DEL PAQUETE
=====================

documentos/
  reporte_completo.html   — Reporte interactivo scrollytelling (abrir en navegador)
  seccion_resultados.docx — Sección de resultados lista para integrar al paper

datos/
  corpus_anotado.xml      — Corpus en XML-TEI P5 (estándar humanidades digitales)
  bibliografia.bib        — Bibliografía del corpus en BibTeX

visualizaciones/
  red_coocurrencias.html  — Red de entidades interactiva (abrir en navegador)
  mapa_corpus.html        — Mapa geográfico interactivo
  timeline.html           — Línea de tiempo interactiva
  nube_corpus.png         — Nube de palabras del corpus

proyecto.bashkar          — Archivo de proyecto (abrir con Bashkar Station)
LEAME.txt                 — Este archivo

CÓMO USAR
=========
1. Abrir reporte_completo.html en cualquier navegador para ver el análisis completo
2. Copiar y pegar secciones del .docx en su manuscrito académico
3. Los archivos .html de visualizaciones funcionan sin conexión a Internet
4. El .bib puede importarse directamente en Zotero, Mendeley o LaTeX
5. El corpus_anotado.xml cumple el estándar TEI P5 para humanidades digitales

Generado con Bashkar Station — https://github.com/gulla-editorial/bashkar-station
"""

    def _guardar_bashkar(self):
        self.data["ultima_modificacion"] = datetime.now().isoformat()
        # El pipeline trabaja con su propio esquema plano ("articulos",
        # "indice_global") pero escribe sobre el .bashkar real, que la GUI lee
        # con otro: project_manager.cargar_proyecto solo mira
        # resultados.indice_ner_global. Sin este espejo, el índice NER que
        # produce el pipeline queda en una clave que nadie lee y al reabrir el
        # proyecto el investigador ve el índice anterior, no el recién
        # calculado.
        indice = self.data.get("indice_global")
        if indice and isinstance(self.data.get("resultados", {}), dict):
            self.data.setdefault("resultados", {})["indice_ner_global"] = indice
        with open(self.bashkar_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2, default=str)

    def _ner_dict_a_lista(self, ner_dict: dict, articulo_id: str) -> list[dict]:
        """Convierte el dict NER {categoria: [texto, ...]} a lista de dicts para Repositorio."""
        CAT_MAP = {
            "personas": "PER", "lugares": "LOC", "organizaciones": "ORG",
            "eventos_historicos": "EVE", "obras_publicaciones": "OBRA",
            "fechas": "CARGO",
        }
        resultado = []
        for cat, ents in ner_dict.items():
            cat_norm = CAT_MAP.get(cat, cat.upper()[:5])
            for ent in (ents if isinstance(ents, list) else []):
                texto = str(ent).strip()
                if texto and len(texto) > 1:
                    resultado.append({
                        "texto":      texto,
                        "categoria":  cat_norm,
                        "confianza":  0.75,
                        "fuente":     "pipeline",
                        "inicio":     None,
                        "fin":        None,
                        "wikidata_id":  None,
                        "wikidata_uri": None,
                    })
        return resultado

    def _log(self, msg: str):
        self.cb_log(str(msg))

    def _progreso(self, pct: int, msg: str):
        self._log(msg)
        self.cb_progreso(pct, msg)
