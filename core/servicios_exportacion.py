"""core/servicios_exportacion.py — Datos para exportaciones y METHODS.md.

Extraído de ``app.py`` (sesión 70). El panel Resultados y el paquete de
publicación armaban cada uno, por separado, la misma configuración y las
mismas estadísticas para ``methods_reporter``, y las dos copias traían el
mismo error: ``n_paginas`` era el número de **PDF** seleccionados y
``n_palabras`` estaba fijo en 0. La sección de metodología de un artículo
salía con cifras falsas.

Aquí las cifras se calculan de lo que realmente se procesó, y lo que no se
puede calcular se devuelve como ``None`` (el reporte lo declara desconocido)
en lugar de un cero que parece un dato.
"""

from __future__ import annotations

ATRIBUTOS_CONFIG = ("publicacion", "periodo", "investigador", "institucion")


def config_methods(st, app_version: str) -> dict:
    return {
        **{k: getattr(st, k, "") for k in ATRIBUTOS_CONFIG},
        "bashkar_version": app_version,
        "dpi": getattr(st, "dpi", "150"),
        "lang": getattr(st, "lang", "spa"),
        "lematizar": getattr(st, "lematizar", True),
        "modelos_etapa": getattr(st, "modelos_etapa", {}),
        "archivos_sel": getattr(st, "archivos_sel", []),
    }


def _paginas_y_palabras(corpus_meta, corpus_txt) -> tuple[int | None, int | None, float | None]:
    """(páginas, palabras, confianza media) desde lo que haya disponible."""
    try:
        import pandas as pd
        if isinstance(corpus_meta, pd.DataFrame) and len(corpus_meta):
            palabras = (int(pd.to_numeric(corpus_meta["palabras"], errors="coerce").fillna(0).sum())
                        if "palabras" in corpus_meta else None)
            conf = None
            if "confianza" in corpus_meta:
                serie = pd.to_numeric(corpus_meta["confianza"], errors="coerce").dropna()
                conf = round(float(serie.mean()), 1) if len(serie) else None
            return len(corpus_meta), palabras, conf
    except ImportError:
        pass
    if corpus_txt:
        return len(corpus_txt), sum(len((t or "").split()) for t in corpus_txt), None
    return None, None, None


def estadisticas_methods(st) -> dict:
    """Estadísticas reales del corpus procesado para ``generar_methods_md``."""
    from datos.normalizaciones import resumen_revision

    paginas, palabras, conf = _paginas_y_palabras(
        getattr(st, "corpus_meta", None), getattr(st, "corpus_txt", None) or [])
    df_art = getattr(st, "df_articulos", None)
    ner = getattr(st, "indice_ner_global", {}) or {}
    stats = {
        "n_paginas": paginas,
        "n_palabras": palabras,
        "n_articulos": len(df_art) if df_art is not None else 0,
        "n_entidades": sum(len(v) for v in ner.values() if isinstance(v, dict)),
        "revision": resumen_revision(getattr(st, "ruta_db", "") or None),
    }
    if conf is not None:
        stats["confianza_ocr_media"] = conf
    return stats


def articulos_para_tei(corpus_txt, ner_global) -> list[dict]:
    """Un artículo TEI por página del corpus, con sus entidades."""
    ner_global = ner_global or {}
    articulos = []
    for i, t in enumerate(corpus_txt or []):
        art_id = f"art_{i:04d}"
        ner_art = {cat: [e for e, arts in ents.items() if art_id in arts]
                   for cat, ents in ner_global.items()}
        articulos.append({"id": art_id, "texto": t or "", "ner": ner_art})
    return articulos
