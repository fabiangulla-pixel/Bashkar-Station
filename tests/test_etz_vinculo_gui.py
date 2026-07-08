"""Tests de la GUI del etiquetador (_etz_*) para el vínculo pie_foto↔foto
(Zona.zid/vinculo) y el reporte de cabeceras repetidas."""

import pytest

tk = pytest.importorskip("tkinter")


@pytest.fixture
def app_etz():
    import app as appmod
    appmod.BashkarApp._cargar_ultimo_proyecto = lambda self: None
    try:
        a = appmod.BashkarApp()
    except tk.TclError:
        pytest.skip("Sin entorno gráfico para tkinter")

    a._mostrar_pagina("etz")
    for _ in range(3):
        a.update()

    from core.zone_labeler import Zona
    a._etz_foto = Zona(tipo="foto", x0=0.1, y0=0.1, x1=0.5, y1=0.4)
    a._etz_pie = Zona(tipo="pie_foto", x0=0.1, y0=0.41, x1=0.5, y1=0.45)
    a._etz_zonas = [a._etz_foto, a._etz_pie]

    yield a
    try:
        a.destroy()
    except Exception:
        pass


def test_vincular_foto_establece_vinculo(app_etz):
    a = app_etz
    a._etz_vincular_foto(1, a._etz_foto.zid)  # idx 1 = pie
    assert a._etz_pie.vinculo == a._etz_foto.zid


def test_vincular_foto_de_nuevo_desvincula(app_etz):
    a = app_etz
    a._etz_vincular_foto(1, a._etz_foto.zid)
    a._etz_vincular_foto(1, a._etz_foto.zid)  # toggle
    assert a._etz_pie.vinculo is None


def test_borrar_foto_vinculada_limpia_vinculo_en_pie(app_etz):
    a = app_etz
    a._etz_vincular_foto(1, a._etz_foto.zid)
    assert a._etz_pie.vinculo == a._etz_foto.zid
    a._etz_borrar_zona(0)  # borra la foto (índice 0)
    assert a._etz_pie.vinculo is None  # limpieza de huérfanos


def test_dividir_zona_vinculada_limpia_vinculo(app_etz):
    a = app_etz
    a._etz_vincular_foto(1, a._etz_foto.zid)
    a._etz_dividir_zona(0, eje="v", frac=0.5)  # divide la foto (índice 0)
    # el zid original de la foto ya no existe → el pie queda desvinculado
    assert a._etz_pie.vinculo is None


def test_redibujar_con_vinculo_no_crashea(app_etz):
    a = app_etz
    a._etz_vincular_foto(1, a._etz_foto.zid)
    a._etz_img_orig = None  # sin imagen: debe retornar temprano sin lanzar
    a._etz_redibujar_zonas()


def test_detectar_cabeceras_sin_numero_no_crashea(app_etz):
    a = app_etz
    a._etz_numero.set("")
    a._etz_detectar_cabeceras()  # solo debe mostrar un toast


def test_detectar_cabeceras_sin_etiquetas_previas(app_etz, tmp_path):
    a = app_etz
    import app as appmod
    appmod.ST.out_dir = tmp_path
    a._etz_numero.set("num_inexistente")
    a._etz_detectar_cabeceras()  # 0 páginas etiquetadas -> toast, no crash
