"""Tests del panel «Benchmark OCR» en la GUI (headless).

Sigue el patrón de tests/test_ling_handlers.py: instancia BashkarApp de verdad
con la auto-carga desactivada y ejercita los handlers. Si tkinter no puede abrir
display, el módulo entero se omite.

Lo que se prueba no es el OCR (eso tarda minutos por página) sino el contrato de
la interfaz: que el panel se construya, que las guardas avisen en vez de
reventar, y que la tabla se pueble a partir de resultados del motor.
"""

from __future__ import annotations

import pytest

tk = pytest.importorskip("tkinter")


@pytest.fixture
def app_bench():
    import app as appmod
    appmod.BashkarApp._cargar_ultimo_proyecto = lambda self: None
    try:
        a = appmod.BashkarApp()
    except tk.TclError:
        pytest.skip("Sin entorno gráfico para tkinter")
    a._mostrar_pagina("bench")
    for _ in range(3):
        a.update()
    yield a
    try:
        a.destroy()
    except Exception:
        pass


def test_la_pagina_esta_registrada():
    import app as appmod
    ids = [p[0] for p in appmod.BashkarApp._PAGINAS]
    assert "bench" in ids


def test_el_panel_se_construye(app_bench):
    a = app_bench
    assert hasattr(a, "_tv_bench")
    assert hasattr(a, "_txt_bench")
    assert hasattr(a, "_btn_bench")
    assert a._bench_resultados == []


def test_el_catalogo_ofrece_las_cuatro_rutas(app_bench):
    claves = {c for c, _, _ in app_bench._bench_catalogo_rutas()}
    assert claves == {"tesseract", "zonas", "churro", "pero"}


def test_el_catalogo_avisa_del_estado_real(app_bench):
    """Una ruta no instalada debe decirlo, no ofrecerse como si funcionara."""
    catalogo = {c: nota for c, _, nota in app_bench._bench_catalogo_rutas()}
    from core import ocr_pero
    if ocr_pero.motivo_no_disponible():
        assert "pip install pero-ocr" in catalogo["pero"]


def test_exportar_sin_datos_avisa_y_no_revienta(app_bench, monkeypatch):
    import app as appmod
    avisos = []
    monkeypatch.setattr(appmod.messagebox, "showinfo",
                        lambda t, m, **k: avisos.append(t))
    app_bench._bench_exportar("csv")
    app_bench._bench_copiar_md()
    assert len(avisos) == 2


def test_iniciar_sin_carpetas_avisa(app_bench, monkeypatch):
    import app as appmod
    avisos = []
    monkeypatch.setattr(appmod.messagebox, "showwarning",
                        lambda t, m, **k: avisos.append(t))
    app_bench._var_bench_oro.set("")
    app_bench._var_bench_imgs.set("")
    app_bench._bench_iniciar()
    assert avisos == ["Faltan carpetas"]


def test_iniciar_sin_rutas_marcadas_avisa(app_bench, monkeypatch, tmp_path):
    import app as appmod
    avisos = []
    monkeypatch.setattr(appmod.messagebox, "showwarning",
                        lambda t, m, **k: avisos.append(t))
    app_bench._var_bench_oro.set(str(tmp_path))
    app_bench._var_bench_imgs.set(str(tmp_path))
    for v in app_bench._bench_rutas_vars.values():
        v.set(False)
    app_bench._bench_iniciar()
    assert avisos == ["Sin rutas"]


def test_la_tabla_se_puebla_con_resultados(app_bench):
    from core.benchmark_ocr import evaluar_rutas
    resultados = evaluar_rutas(
        {"p1": "la guerra civil española"},
        {"buena": {"p1": "la guerra civil española"},
         "mala":  {"p1": ""}},
    )
    app_bench._bench_fin(resultados)
    app_bench.update()
    filas = app_bench._tv_bench.get_children()
    assert len(filas) == 2
    primera = app_bench._tv_bench.item(filas[0])["values"]
    assert primera[0] == "buena"           # ordenado de mejor a peor
    assert str(primera[1]) == "0.0000"     # CER
    assert "✅" in app_bench._lbl_bench.cget("text")


def test_bench_fin_sin_resultados_no_revienta(app_bench):
    app_bench._bench_fin([])
    app_bench.update()
    assert app_bench._tv_bench.get_children() == ()
    assert "Sin resultados" in app_bench._lbl_bench.cget("text")
