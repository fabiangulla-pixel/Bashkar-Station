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


def _ner_por_articulo(ner_global) -> dict:
    """{art_id: {categoria: [entidades]}} a partir del índice global."""
    por_art: dict = {}
    for cat, ents in (ner_global or {}).items():
        if not isinstance(ents, dict):
            continue
        for ent, arts in ents.items():
            for aid in arts:
                por_art.setdefault(str(aid), {}).setdefault(cat, []).append(ent)
    return por_art


def _como_lista(articulos) -> list[dict]:
    if articulos is None:
        return []
    if hasattr(articulos, "to_dict"):          # DataFrame
        if getattr(articulos, "empty", True):
            return []
        articulos = articulos.to_dict("records")
    return [dict(a) for a in articulos]


def articulos_para_tei(corpus_txt=None, ner_global=None, *, articulos=None) -> list[dict]:
    """Artículos listos para el TEI, cada uno con SUS entidades.

    Con ``articulos`` (lista o DataFrame de la segmentación) se usa un elemento
    TEI por artículo y las entidades se cruzan por su ``id`` estable. Si a un
    artículo le falta el texto (los CSV del proyecto no lo guardan) se toma de
    ``corpus_txt`` cuando ambos están alineados. Sin segmentación, un elemento
    por página de ``corpus_txt`` (``art_0000``…).

    Antes siempre se usaba ``art_0000``… mientras el NER indexaba por título:
    el TEI no traía ninguna entidad.
    """
    from core.article_segmenter import asignar_ids_articulos
    por_art = _ner_por_articulo(ner_global)
    categorias = [c for c, v in (ner_global or {}).items() if isinstance(v, dict)]

    def ner_de(aid: str) -> dict:
        # Todas las categorías del índice, también las vacías: es el contrato
        # que ya esperaban los consumidores.
        ents = por_art.get(aid, {})
        return {c: ents.get(c, []) for c in categorias}
    textos = list(corpus_txt or [])
    arts = _como_lista(articulos)
    salida = []
    if arts:
        asignar_ids_articulos(arts)
        alineados = len(textos) == len(arts)
        for i, a in enumerate(arts):
            texto = a.get("texto")
            if not isinstance(texto, str) or not texto.strip():
                texto = textos[i] if alineados else ""
            def _str(v):
                return v if isinstance(v, str) and v.strip() and v != "nan" else None
            salida.append({
                "id": str(a["id"]), "texto": texto or "",
                "titulo": _str(a.get("titulo")), "autor": _str(a.get("autor")),
                "numero": _str(a.get("numero")),
                "ner": ner_de(str(a["id"])),
            })
        return salida
    for i, t in enumerate(textos):
        art_id = f"art_{i:04d}"
        salida.append({"id": art_id, "texto": t or "", "ner": ner_de(art_id)})
    return salida


def contar_entidades_tei(articulos_tei: list[dict]) -> int:
    """Entidades (pares artículo–entidad) que llevará el TEI."""
    return sum(len(v) for a in articulos_tei for v in (a.get("ner") or {}).values())


def exportar_tei_articulos(articulos, ruta, publicacion: str = "", periodo: str = "",
                           ner_global=None):
    """Corpus TEI de artículos segmentados; la CLI y la web llaman aquí.

    Hasta el 14-nov-2026 descartaba las entidades: el TEI de la CLI y de la web
    salía siempre sin ellas.
    """
    from core.tei_engine import exportar_corpus_tei
    arts = articulos_para_tei(ner_global=ner_global, articulos=articulos)
    fuente = f"{publicacion} ({periodo})" if periodo else publicacion
    return exportar_corpus_tei(arts, ruta, proyecto_nombre=publicacion or "Corpus",
                               fuente=fuente)
