"""Cifras de METHODS.md: salen de lo procesado, no de la lista de PDF."""

from types import SimpleNamespace

import pandas as pd

from core import servicios_exportacion as SE
from core.methods_reporter import generar_methods_md
from datos import normalizaciones as NZ


def _st(**kw):
    base = dict(publicacion="Estampa", periodo="1939", investigador="F", institucion="U",
                archivos_sel=["a.pdf"], corpus_meta=None, corpus_txt=[],
                df_articulos=None, indice_ner_global={}, ruta_db="")
    base.update(kw)
    return SimpleNamespace(**base)


def test_paginas_y_palabras_salen_del_corpus_no_de_los_pdf():
    meta = pd.DataFrame({"palabras": [100, 50, 25], "confianza": [90.0, None, 80.0]})
    st = _st(corpus_meta=meta)  # 1 PDF, 3 páginas
    e = SE.estadisticas_methods(st)
    assert e["n_paginas"] == 3 and e["n_palabras"] == 175
    assert e["confianza_ocr_media"] == 85.0


def test_sin_meta_usa_corpus_txt_y_sin_nada_es_desconocido():
    assert SE.estadisticas_methods(_st(corpus_txt=["uno dos", "tres"]))["n_palabras"] == 3
    e = SE.estadisticas_methods(_st(corpus_meta={}))
    assert e["n_paginas"] is None and e["n_palabras"] is None


def test_resumen_revision(tmp_path):
    db = tmp_path / "p.db"
    NZ.guardar(db, "E", "p1", ocr_crudo="a", norm_usuario="A", norm_ia="")
    NZ.guardar(db, "E", "p2", ocr_crudo="b", norm_usuario="", norm_ia="B")
    NZ.guardar(db, "E", "p3", ocr_crudo="c", norm_usuario="", norm_ia="")
    NZ.guardar(db, "E", "p4", ocr_crudo="d", norm_usuario="D", norm_ia="")
    r = NZ.resumen_revision(db)
    assert (r["revisado"], r["corregido_ia"], r["ocr"], r["total"]) == (2, 1, 1, 4)
    assert r["pct_revision_humana"] == 50.0
    assert NZ.resumen_revision(tmp_path / "no.db") is None


def test_methods_declara_desconocido_revision_y_limitaciones(tmp_path):
    db = tmp_path / "p.db"
    NZ.guardar(db, "E", "p1", ocr_crudo="a", norm_usuario="A", norm_ia="")
    NZ.guardar(db, "E", "p2", ocr_crudo="b", norm_usuario="", norm_ia="")
    st = _st(ruta_db=str(db))
    ruta = generar_methods_md(SE.config_methods(st, "12.3"), SE.estadisticas_methods(st),
                              tmp_path / "METHODS.md")
    md = ruta.read_text(encoding="utf-8")
    assert "Páginas analizadas:** desconocido" in md
    assert "Revisado por el investigador | 1" in md
    assert "**50.0%**" in md
    assert "## Limitaciones conocidas" in md
    assert "50.0% de las páginas registradas no tuvo revisión humana" in md


def test_articulos_para_tei_reparte_entidades():
    arts = SE.articulos_para_tei(["a", None], {"PER": {"Gaitán": ["art_0001"]}})
    assert arts[0]["ner"] == {"PER": []} and arts[1]["ner"] == {"PER": ["Gaitán"]}
    assert arts[1]["texto"] == ""


def test_paquete_publicacion_puede_exportar_tei(tmp_path):
    """Regresión: el paquete llamaba exportar_corpus_tei con titulo=/fecha=."""
    from core.tei_engine import exportar_corpus_tei
    arts = SE.articulos_para_tei(["texto de prueba"], {})
    exportar_corpus_tei(arts, tmp_path / "corpus.xml", proyecto_nombre="Estampa",
                        investigador="F", institucion="")
    assert (tmp_path / "corpus.xml").stat().st_size > 0
