"""Tests de los handlers de la GUI para las 4 pestañas nuevas de Lingüística
(encuadre, polaridad, revisión NER, validación).

Instancia BashkarApp headless con la auto-carga del último proyecto desactivada
(para que no pise el corpus de prueba), ejercita los workers en el hilo principal
y verifica que los treeviews/labels se pueblan. Si tkinter no puede abrir display
(CI sin entorno gráfico), el módulo se omite entero.
"""

import os
import sqlite3

import pytest

tk = pytest.importorskip("tkinter")


@pytest.fixture
def app_ling():
    import app as appmod
    # Desactivar auto-carga del último proyecto: no debe pisar el corpus de prueba.
    appmod.BashkarApp._cargar_ultimo_proyecto = lambda self: None
    try:
        a = appmod.BashkarApp()
    except tk.TclError:
        pytest.skip("Sin entorno gráfico para tkinter")
    a._mostrar_pagina("ling")
    for _ in range(3):
        a.update()
    yield a, appmod.ST
    try:
        a.destroy()
    except Exception:
        pass


def _drena(a, n=6):
    for _ in range(n):
        a.update()


CORPUS = [
    "El frente republicano resistio la ofensiva del ejercito nacionalista. "
    "Tragedia, muerte y destruccion. Franco impuso terror.",
    "La vida moderna trae el automovil, la aviacion y la electricidad. "
    "Adelanto glorioso, esplendor y progreso de la civilizacion.",
    "La dama luce un vestido de elegancia en el salon. Moda femenina y belleza.",
    "El poeta publico una novela admirable. La literatura alcanza esplendor.",
    "Mussolini y Hitler amenazan a Europa. Guerra, ataques, miedo y horror.",
    "ilegible xxx zzz nnn",
]


def test_encuadre_puebla_todo_el_corpus(app_ling):
    a, ST = app_ling
    ST.corpus_txt = CORPUS
    a._worker_ling_frames(CORPUS)
    _drena(a)
    # 6 artículos → 6 filas
    assert len(a._tv_ling_frame.get_children()) == 6
    assert a._ling_frame_corpus.get("n_articulos") == 6
    assert a._ling_frame_corpus.get("dominante_corpus") == "guerra"


def test_polaridad_puebla_y_resume(app_ling):
    a, ST = app_ling
    ST.corpus_txt = CORPUS
    a._worker_ling_pol(CORPUS)
    _drena(a)
    assert len(a._tv_ling_pol.get_children()) == 6
    assert len(a._ling_pol_datos) == 6
    # debe haber al menos un negativo y un positivo en este corpus
    pols = {r["polaridad"] for r in a._ling_pol_datos}
    assert "negativo" in pols
    assert "positivo" in pols


def test_polaridad_hacia_entidad_en_app(app_ling):
    a, ST = app_ling
    ST.corpus_txt = CORPUS
    a._ent_pol_entidad.delete(0, "end")
    a._ent_pol_entidad.insert(0, "Franco")
    a._ling_pol_hacia()
    _drena(a)
    txt = a._lbl_pol_hacia.cget("text")
    assert "menciones" in txt
    assert "negativo" in txt  # a Franco se le cubre negativamente


def test_revision_ner_flujo_completo(app_ling, tmp_path):
    a, ST = app_ling
    ST.indice_ner_global = {
        "personas": {"Franco": ["d1"], "Mussolini": ["d5"], "RuidoX": ["d6"]},
        "lugares": {"Valencia": ["d1"], "Bgta": ["d2"]},
    }
    ST.ruta_db = str(tmp_path / "proyecto.db")
    a._ling_rev_construir()
    _drena(a)
    # todas tienen 1 artículo → 5 dudosas (rojo)
    assert len(a._tv_ling_rev.get_children()) == 5

    # descartar RuidoX
    for iid in a._tv_ling_rev.get_children():
        if a._tv_ling_rev.item(iid, "values")[0] == "RuidoX":
            a._tv_ling_rev.selection_set(iid)
            break
    a._ling_rev_decidir("descartada")
    _drena(a)
    assert len(a._tv_ling_rev.get_children()) == 4

    # persistencia: la decisión quedó en la BD
    con = sqlite3.connect(ST.ruta_db)
    con.row_factory = sqlite3.Row
    from core import revision_engine
    stats = revision_engine.estadisticas(con)
    con.close()
    assert stats["descartadas"] == 1

    # descartar también limpia el índice NER en memoria
    assert "RuidoX" not in ST.indice_ner_global["personas"]


def test_validacion_exporta_muestra_completa(app_ling, tmp_path):
    a, ST = app_ling
    ST.corpus_txt = CORPUS
    arts = a._ling_val_articulos()
    assert len(arts) == 6

    import csv
    from core import validacion_engine
    ruta = tmp_path / "muestra.csv"
    et = a._ling_val_etiquetador("polaridad")
    validacion_engine.exportar_muestra(arts, ruta, n=6, semilla=1,
                                       etiqueta_auto=et, nombre_etiqueta="polaridad")
    rows = list(csv.DictReader(open(ruta, encoding="utf-8-sig")))
    assert len(rows) == 6
    # la columna automática se rellenó con etiquetas válidas
    autos = {r["polaridad_auto"] for r in rows}
    assert autos <= {"positivo", "negativo", "neutro"}
    assert "polaridad_manual" in rows[0]


def test_validacion_dimension_emocion(app_ling, tmp_path):
    a, ST = app_ling
    ST.corpus_txt = CORPUS
    import csv
    from core import validacion_engine
    et = a._ling_val_etiquetador("emocion")
    assert et is not None
    ruta = tmp_path / "muestra_emo.csv"
    arts = a._ling_val_articulos()
    validacion_engine.exportar_muestra(arts, ruta, n=5, semilla=3,
                                       etiqueta_auto=et, nombre_etiqueta="emocion")
    rows = list(csv.DictReader(open(ruta, encoding="utf-8-sig")))
    assert "emocion_auto" in rows[0]
    assert "emocion_manual" in rows[0]


def test_ir_a_ling_pestania(app_ling):
    a, _ = app_ling
    a._ir_a_ling_pestania(6)   # Encuadre
    a.update()
    assert a._nb_ling.index(a._nb_ling.select()) == 6
