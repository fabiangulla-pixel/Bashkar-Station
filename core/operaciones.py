"""core/operaciones.py — Registro de paridad entre el escritorio y la API.

Desde la sesión 72 Bashkar tiene dos interfaces que deben ofrecer lo mismo: la
app de escritorio (``app.py`` + ``paneles/``) y la API (``api/``). Cada
operación de fondo del escritorio (un método ``_worker_*``) tiene que estar
aquí, con la ruta de la API que la ofrece o con ``api=None`` y el motivo.

``tests/test_paridad.py`` falla si:
- aparece un ``_worker_*`` en el escritorio que no está registrado aquí;
- una operación dice tener ruta en la API y la API no la tiene.

Así una función nueva del escritorio no puede quedar fuera de la nube sin
que se vea: o se agrega la ruta, o se declara pendiente en este archivo.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Operacion:
    clave: str
    escritorio: tuple[str, ...]      # métodos _worker_* que la implementan
    api: str | None                  # "METODO /ruta" en la API, o None
    nota: str = ""                   # por qué falta, o en qué difiere


OPERACIONES: tuple[Operacion, ...] = (
    # ── Con ruta en la API ───────────────────────────────────────────────────
    Operacion("ocr", ("_worker_ocr", "_worker_ocr_carpetas"), "POST /api/v1/ocr/iniciar"),
    Operacion("segmentar", ("_worker_seg",), "POST /api/v1/segmentar"),
    Operacion("ner", ("_worker_ner_corpus", "_worker_ner_articulo"), "POST /api/v1/ner"),
    Operacion("analisis", ("_worker_anal",), "POST /api/v1/analisis",
              "la API hace frecuencias/secciones; LDA y campos semánticos siguen solo en escritorio"),
    Operacion("benchmark_ocr", ("_worker_bench",), "POST /api/v1/benchmark"),
    Operacion("layout", ("_worker_layout",), "POST /api/v1/layout"),
    # ── Cerradas en la sesión 73 (lectura distante + publicación) ────────────
    Operacion("mejorar_ocr", ("_worker_mejorar_ocr",), "POST /api/v1/mejorar_ocr"),
    Operacion("gutter", ("_worker_gutter",), "POST /api/v1/gutter"),
    Operacion("vision", ("_worker_vis",), "POST /api/v1/vision",
              "la API no repite el detalle de tipografía por PDF (solo imágenes)"),
    Operacion("comparar", ("_worker_comp",), "POST /api/v1/comparar",
              "lee una carpeta del servidor: solo en modo local"),
    Operacion("topicos", ("_worker_top",), "POST /api/v1/topicos"),
    Operacion("nube", ("_worker_nube",), "POST /api/v1/nube"),
    Operacion("lexico", ("_worker_lexico",), "POST /api/v1/lexico"),
    Operacion("estilo", ("_worker_estilo",), "POST /api/v1/estilo"),
    Operacion("tono", ("_worker_tono",), "POST /api/v1/tono"),
    Operacion("narrativas", ("_worker_narrativas",), "POST /api/v1/narrativas"),
    Operacion("linea_tiempo", ("_worker_timeline",), "POST /api/v1/linea_tiempo"),
    Operacion("mapa", ("_worker_mapa",), "POST /api/v1/mapa"),
    Operacion("mapa_calor", ("_worker_heatmap",), "POST /api/v1/mapa_calor"),
    Operacion("red", ("_worker_red_construir",), "POST /api/v1/red"),
    Operacion("coref", ("_worker_coref_stats", "_worker_ling_coref"), "POST /api/v1/coref"),
    Operacion("linguistica", ("_worker_ling_dep", "_worker_ling_emo", "_worker_ling_frames",
                              "_worker_ling_morf", "_worker_ling_pol", "_worker_ling_sint",
                              "_worker_ling_svo"), "POST /api/v1/linguistica",
              "un solo endpoint con campo 'tipo' para las 7 sub-operaciones"),
    Operacion("canonico", ("_worker_can_fundir", "_worker_can_menciones", "_worker_can_okf"),
              "POST /api/v1/canonico",
              "un solo endpoint con campo 'accion'; requiere proyecto con base de datos (.db)"),
    Operacion("reportes", ("_worker_rep_html", "_worker_rep_word"), "POST /api/v1/reportes"),
    Operacion("paquete_publicacion", ("_worker_paquete_publicacion", "_worker_zip"),
              "POST /api/v1/paquete_publicacion",
              "no incluye bitácora (sin equivalente de sesión en el servidor)"),
)


def por_worker() -> dict[str, Operacion]:
    return {w: op for op in OPERACIONES for w in op.escritorio}


def resumen() -> dict:
    con_api = [op.clave for op in OPERACIONES if op.api]
    return {"total": len(OPERACIONES), "con_api": len(con_api),
            "pendientes": [op.clave for op in OPERACIONES if not op.api]}
