"""Tests de la ventana de Verificación OCR (_verif_*) en el panel Normalizar.

Instancia BashkarApp headless con auto-carga desactivada. El worker de
análisis se llama DIRECTO (sin thread) para que el test sea determinista,
siguiendo el mismo patrón que tests/test_grafo_gui.py."""

import pytest

tk = pytest.importorskip("tkinter")


def _pagina_sintetica():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (500, 100), "white")
    d = ImageDraw.Draw(img)
    d.text((10, 35), "Bogota capital", fill="black")
    return img


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

    a._norm_bloques = [{
        "numero": "num1", "pagina": "p0001",
        "ocr_crudo": "texto original del ocr", "norm_usuario": "",
        "norm_ia": "", "txt_path": None,
    }]
    a._norm_idx_actual = 0
    a._norm_img_orig_full = _pagina_sintetica()

    yield a, appmod
    try:
        a.destroy()
    except Exception:
        pass


def _drena(a, n=5):
    for _ in range(n):
        a.update()


def test_verif_abrir_sin_bloque_seleccionado_no_crashea(app_norm):
    a, _ = app_norm
    a._norm_idx_actual = -1
    a._verif_abrir()  # solo debe mostrar un toast, no lanzar
    assert getattr(a, "_verif_win", None) is None


def test_verif_abrir_construye_ventana_y_puebla_tras_worker(app_norm):
    a, _ = app_norm
    a._verif_abrir()
    _drena(a)
    assert a._verif_win is not None and a._verif_win.winfo_exists()

    # Llamar el worker DIRECTO (determinista, sin depender del thread)
    a._verif_worker_analizar(a._norm_img_orig_full)
    a._verif_poll()
    _drena(a)

    assert isinstance(a._verif_palabras, list)
    if a._verif_palabras:
        assert a._verif_var_texto.get() == a._verif_palabras[0].texto


def test_verif_reemplazar_y_cerrar_persiste_en_bloque(app_norm):
    a, _ = app_norm
    a._norm_txt_usuario.insert("1.0", "el texto ocr original con un eror aqui")
    a._verif_abrir()
    a._verif_worker_analizar(a._norm_img_orig_full)
    a._verif_poll()
    _drena(a)

    # Fuerza una palabra dudosa conocida en vez de depender del OCR real
    from core.word_verifier import PalabraDudosa
    a._verif_palabras = [PalabraDudosa(
        texto="eror", conf=40.0, x0=0, y0=0, x1=10, y1=10,
        idx_ocurrencia=0, contexto="con un eror aqui")]
    a._verif_pos = 0
    a._verif_var_texto.set("error")

    a._verif_reemplazar()
    a._verif_cerrar()

    assert "error" in a._norm_bloques[0]["norm_usuario"]
    assert "eror" not in a._norm_bloques[0]["norm_usuario"]


def test_verif_agregar_diccionario_registra_en_vocab_usuario(app_norm, monkeypatch, tmp_path):
    a, _ = app_norm
    ruta = tmp_path / ".bashkar" / "vocab_usuario.json"
    monkeypatch.setattr("core.spell_corrector._VOCAB_USUARIO_PATH", ruta)

    from core.word_verifier import PalabraDudosa
    a._verif_abrir()
    a._verif_palabras = [PalabraDudosa(
        texto="piquillopio", conf=30.0, x0=0, y0=0, x1=10, y1=10,
        idx_ocurrencia=0, contexto="")]
    a._verif_pos = 0
    a._verif_agregar_diccionario()

    from core.spell_corrector import _cargar_vocab_usuario
    assert "piquillopio" in _cargar_vocab_usuario()
