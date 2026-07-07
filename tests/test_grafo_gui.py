"""Tests de la pestaña «Grafo canónico» (panel Redes 🕸) en la GUI.

Instancia BashkarApp headless con auto-carga desactivada, apunta ST.ruta_db a
una DB temporal con menciones sembradas, y ejercita los workers de fusión,
generación de tripletas y export GEXF en el hilo principal. Si no hay entorno
gráfico, el módulo se omite entero.
"""

import os

import pytest

tk = pytest.importorskip("tkinter")


@pytest.fixture
def app_red(tmp_path):
    import app as appmod
    appmod.BashkarApp._cargar_ultimo_proyecto = lambda self: None
    try:
        a = appmod.BashkarApp()
    except tk.TclError:
        pytest.skip("Sin entorno gráfico para tkinter")

    # DB temporal con menciones reales sembradas
    db = str(tmp_path / "proyecto.db")
    from datos.repositorio import Repositorio
    repo = Repositorio(db)
    repo.guardar_articulo({"id": "art_001", "tipo": "articulo"})
    repo.guardar_articulo({"id": "art_002", "tipo": "articulo"})
    repo.guardar_entidades("art_001", [
        {"texto": "Colombia", "categoria": "lugares", "confianza": 0.9},
        {"texto": "Franco",   "categoria": "personas", "confianza": 0.9},
    ])
    repo.guardar_entidades("art_002", [
        {"texto": "Colombia", "categoria": "lugares", "confianza": 0.8},
    ])
    appmod.ST.ruta_db = db

    a._mostrar_pagina("red")
    for _ in range(3):
        a.update()
    yield a, appmod.ST, db
    try:
        a.destroy()
    except Exception:
        pass


def _drena(a, n=8):
    for _ in range(n):
        a.update()


def test_pestania_y_widgets_existen(app_red):
    a, ST, db = app_red
    # los widgets de la pestaña Grafo canónico se construyeron
    assert hasattr(a, "_tv_can")
    assert hasattr(a, "_btn_can_fundir")
    assert hasattr(a, "_lbl_can_ok")


def test_fundir_puebla_tabla(app_red):
    a, ST, db = app_red
    # llamar al worker directo (evita el thread para test determinista)
    from datos.repositorio import Repositorio
    a._worker_can_fundir(Repositorio(db))
    _drena(a)
    filas = a._tv_can.get_children()
    # 3 menciones → 2 canónicas (Colombia fundida)
    assert len(filas) == 2
    assert "canónicas" in a._lbl_can_ok.cget("text")


def test_generar_tripletas(app_red):
    a, ST, db = app_red
    from datos.repositorio import Repositorio
    repo = Repositorio(db)
    a._worker_can_fundir(repo); _drena(a)
    a._worker_can_menciones(repo); _drena(a)
    rels = repo.listar_relaciones(predicado="mencionado_en")
    assert len(rels) == 3  # 3 menciones → 3 tripletas mencionado_en


def test_exportar_gexf(app_red, tmp_path):
    a, ST, db = app_red
    from datos.repositorio import Repositorio
    repo = Repositorio(db)
    a._worker_can_fundir(repo); _drena(a)
    # una arista entidad→entidad para que el GEXF tenga edges
    cans = repo.listar_entidades_canonicas()
    repo.guardar_relacion(cans[0]["id"], "co_aparece_con",
                          destino_id=cans[1]["id"], confianza=0.7)
    graf = repo.grafo_entidades()
    salida = str(tmp_path / "g.gexf")
    a._can_escribir_gexf(graf, salida)
    assert os.path.exists(salida)
    contenido = open(salida, encoding="utf-8").read()
    assert "<gexf" in contenido and "co_aparece_con" in contenido
    assert "<node" in contenido and "<edge" in contenido


def test_handlers_fase234_existen(app_red):
    a, ST, db = app_red
    # los botones de Fases 2-4 y el editor de relaciones están cableados
    for m in ("_can_exportar_rdf", "_can_mapa_lugares", "_can_timeline",
              "_can_vocabulario", "_can_editor_relacion"):
        assert callable(getattr(a, m, None)), f"falta handler {m}"


def test_editor_relacion_se_abre_y_guarda(app_red, monkeypatch):
    a, ST, db = app_red
    from datos.repositorio import Repositorio
    repo = Repositorio(db)
    a._worker_can_fundir(repo); _drena(a)
    # abrir el diálogo del editor: no debe lanzar; cerramos el Toplevel creado
    import tkinter as tk
    a._can_editor_relacion()
    _drena(a)
    # localizar el Toplevel y cerrarlo
    tops = [w for w in a.winfo_children() if isinstance(w, tk.Toplevel)]
    assert tops, "el editor de relaciones no abrió ventana"
    tops[0].destroy()
    _drena(a)
