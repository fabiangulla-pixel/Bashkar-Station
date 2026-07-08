"""Test del indicador ⚠ en la lista de bloques de Normalizar cuando
_avisos_ocr (calculado en _worker_ocr, ver core/page_quality.py) marca
una página con avisos de calidad."""

import pytest

tk = pytest.importorskip("tkinter")


@pytest.fixture
def app_norm():
    import app as appmod
    appmod.BashkarApp._cargar_ultimo_proyecto = lambda self: None
    try:
        a = appmod.BashkarApp()
    except tk.TclError:
        pytest.skip("Sin entorno gráfico para tkinter")

    a._mostrar_pagina("norm")
    for _ in range(3):
        a.update()

    a._norm_bloques = [
        {"numero": "num1", "pagina": "p0001", "ocr_crudo": "texto", "norm_usuario": "",
         "norm_ia": "", "txt_path": None},
        {"numero": "num1", "pagina": "p0002", "ocr_crudo": "otro texto", "norm_usuario": "",
         "norm_ia": "", "txt_path": None},
    ]
    a._norm_idx_actual = 0
    yield a
    try:
        a.destroy()
    except Exception:
        pass


def test_refrescar_lista_muestra_alerta_para_pagina_con_avisos(app_norm):
    a = app_norm
    a._avisos_ocr = {("num1", "p0002"): ["Confianza OCR muy baja: 15%"]}
    a._norm_lb.insert("end", "· p0001")
    a._norm_lb.insert("end", "· p0002")
    a._norm_refrescar_lista()

    textos = [a._norm_lb.get(i) for i in range(a._norm_lb.size())]
    assert "⚠" not in textos[0]
    assert "⚠" in textos[1]


def test_refrescar_lista_sin_avisos_no_marca_nada(app_norm):
    a = app_norm
    a._avisos_ocr = {}
    a._norm_lb.insert("end", "· p0001")
    a._norm_lb.insert("end", "· p0002")
    a._norm_refrescar_lista()

    textos = [a._norm_lb.get(i) for i in range(a._norm_lb.size())]
    assert all("⚠" not in t for t in textos)
