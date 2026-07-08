"""Tests del diálogo «Guardar como…» (_exp_*) — PDF buscable, resolución
de imagen de página, y export a texto plano."""

import pytest

tk = pytest.importorskip("tkinter")


@pytest.fixture
def app_res():
    import app as appmod
    appmod.BashkarApp._cargar_ultimo_proyecto = lambda self: None
    try:
        a = appmod.BashkarApp()
    except tk.TclError:
        pytest.skip("Sin entorno gráfico para tkinter")
    a._mostrar_pagina("res")
    for _ in range(3):
        a.update()
    yield a, appmod
    try:
        a.destroy()
    except Exception:
        pass


def _png(path, size=(200, 100)):
    from PIL import Image
    Image.new("RGB", size, "white").save(path)


def test_exp_resolver_imagen_encuentra_por_glob(app_res, tmp_path):
    a, appmod = app_res
    appmod.ST.out_dir = tmp_path
    img_dir = tmp_path / "02_imagenes" / "num1"
    img_dir.mkdir(parents=True)
    _png(img_dir / "p0001.png")

    encontrada = a._exp_resolver_imagen("num1", "p0001")
    assert encontrada is not None
    assert encontrada.name == "p0001.png"


def test_exp_resolver_imagen_sin_carpeta_devuelve_none(app_res, tmp_path):
    a, appmod = app_res
    appmod.ST.out_dir = tmp_path
    assert a._exp_resolver_imagen("no_existe", "p0001") is None


def test_exp_pdf_buscable_sin_corpus_meta_avisa_no_crashea(app_res):
    a, appmod = app_res
    appmod.ST.corpus_meta = None
    a._exp_pdf_buscable()  # debe mostrar warning y retornar, no lanzar


def test_exp_pdf_worker_genera_pdf_real(app_res, tmp_path, monkeypatch):
    a, appmod = app_res
    img_dir = tmp_path / "02_imagenes" / "num1"
    img_dir.mkdir(parents=True)
    _png(img_dir / "p0001.png")
    txt = tmp_path / "p0001.txt"
    txt.write_text("texto de prueba de la pagina uno", encoding="utf-8")

    appmod.ST.out_dir = tmp_path
    import pandas as pd
    appmod.ST.corpus_meta = pd.DataFrame([
        {"numero": "num1", "pagina": "p0001", "txt_path": str(txt), "confianza": 90},
    ])

    dest = tmp_path / "salida.pdf"
    monkeypatch.setattr("os.startfile", lambda *_a, **_k: None, raising=False)
    a._exp_pdf_worker(str(dest), abrir_al_terminar=False)

    assert dest.exists()
    import fitz
    doc = fitz.open(str(dest))
    assert doc.page_count == 1
    assert "prueba" in doc[0].get_text()
    doc.close()


def test_exp_texto_plano_sin_corpus_avisa(app_res):
    a, appmod = app_res
    appmod.ST.corpus_txt = []
    a._exp_texto_plano()  # solo debe mostrar warning, no lanzar


def test_exp_abrir_dialogo_construye_ventana(app_res):
    a, _ = app_res
    a._exp_abrir_dialogo()
    a.update()
    # el diálogo abrió un Toplevel adicional (no se guarda referencia con
    # nombre propio, pero no debe lanzar excepción al construirse)
