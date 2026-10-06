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
    # ── Pendientes en la API (declarados, no olvidados) ──────────────────────
    Operacion("mejorar_ocr", ("_worker_mejorar_ocr",), None, "pendiente"),
    Operacion("gutter", ("_worker_gutter",), None, "pendiente"),
    Operacion("vision", ("_worker_vis",), None, "pendiente"),
    Operacion("comparar", ("_worker_comp",), None, "pendiente"),
    Operacion("topicos", ("_worker_top",), None, "pendiente"),
    Operacion("nube", ("_worker_nube",), None, "pendiente"),
    Operacion("lexico", ("_worker_lexico",), None, "pendiente"),
    Operacion("estilo", ("_worker_estilo",), None, "pendiente"),
    Operacion("tono", ("_worker_tono",), None, "pendiente"),
    Operacion("narrativas", ("_worker_narrativas",), None, "pendiente"),
    Operacion("linea_tiempo", ("_worker_timeline",), None, "pendiente"),
    Operacion("mapa", ("_worker_mapa",), None, "pendiente"),
    Operacion("mapa_calor", ("_worker_heatmap",), None, "pendiente"),
    Operacion("red", ("_worker_red_construir",), None, "pendiente"),
    Operacion("coref", ("_worker_coref_stats", "_worker_ling_coref"), None, "pendiente"),
    Operacion("linguistica", ("_worker_ling_dep", "_worker_ling_emo", "_worker_ling_frames",
                              "_worker_ling_morf", "_worker_ling_pol", "_worker_ling_sint",
                              "_worker_ling_svo"), None, "pendiente"),
    Operacion("canonico", ("_worker_can_fundir", "_worker_can_menciones", "_worker_can_okf"),
              None, "pendiente"),
    Operacion("reportes", ("_worker_rep_html", "_worker_rep_word"), None, "pendiente"),
    Operacion("paquete_publicacion", ("_worker_paquete_publicacion", "_worker_zip"), None,
              "pendiente"),
)


def por_worker() -> dict[str, Operacion]:
    return {w: op for op in OPERACIONES for w in op.escritorio}


def resumen() -> dict:
    con_api = [op.clave for op in OPERACIONES if op.api]
    return {"total": len(OPERACIONES), "con_api": len(con_api),
            "pendientes": [op.clave for op in OPERACIONES if not op.api]}
