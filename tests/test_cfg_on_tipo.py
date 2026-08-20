"""Regresión: cambiar el tipo de archivos (PDF/Subcarpetas/Imágenes) en
Configuración, DESPUÉS de ya haber elegido la carpeta de entrada, dejaba la
lista de archivos vacía en silencio — el campo de carpeta seguía mostrando la
ruta, así que parecía configurado, y "Confirmar configuración" fallaba una y
otra vez con "Selecciona al menos un archivo" sin que el usuario entendiera
por qué (reportado por el usuario 2026-08-19)."""

import pytest

tk = pytest.importorskip("tkinter")


@pytest.fixture
def app_cfg(tmp_path):
    import app as appmod
    appmod.BashkarApp._cargar_ultimo_proyecto = lambda self: None
    try:
        a = appmod.BashkarApp()
    except tk.TclError:
        pytest.skip("Sin entorno gráfico para tkinter")

    a._mostrar_pagina("cfg")
    for _ in range(3):
        a.update()
    yield a, tmp_path
    try:
        a.destroy()
    except Exception:
        pass


def _crear_pdfs(carpeta, n=3):
    for i in range(n):
        (carpeta / f"num{i}.pdf").write_bytes(b"%PDF-1.4\n%%EOF")


def _crear_subcarpetas(carpeta, n=2):
    for i in range(n):
        sub = carpeta / f"numero_{i}"
        sub.mkdir()
        (sub / "p0001.pdf").write_bytes(b"%PDF-1.4\n%%EOF")


def test_cambiar_tipo_con_carpeta_ya_elegida_repuebla_la_lista(app_cfg):
    a, tmp_path = app_cfg
    carpeta = tmp_path / "corpus"
    carpeta.mkdir()
    _crear_pdfs(carpeta, 3)

    # Igual que _pick_ent(): fija la carpeta y escanea con el tipo actual (pdf).
    a._var_ent.set(str(carpeta))
    a._poblar_lista(carpeta)
    assert len(a._archivos_disp) == 3
    assert len(a._lb.curselection()) == 3

    # El usuario cambia de tipo (p. ej. porque en realidad son subcarpetas) —
    # antes esto dejaba _lb / _archivos_disp vacíos sin volver a escanear.
    a._var_tipo.set("carpetas")
    a._on_tipo()

    assert a._var_ent.get() == str(carpeta)  # la ruta seguía mostrándose
    # No hay subcarpetas reales en `carpeta` (son PDFs sueltos), así que la
    # nueva lista queda vacía — correcto: lo que NO debe pasar es que archivos
    # sí existentes para el tipo anterior queden fantasma en _archivos_disp
    # mientras _lb está vacío (eso descuadra los índices de curselection()).
    assert len(a._archivos_disp) == len(list(range(a._lb.size())))


def test_cambiar_tipo_a_uno_compatible_reselecciona_archivos(app_cfg):
    a, tmp_path = app_cfg
    carpeta = tmp_path / "corpus_subcarpetas"
    carpeta.mkdir()
    _crear_subcarpetas(carpeta, 2)

    # Usuario empieza en modo "pdf" (default) sobre una carpeta que en
    # realidad tiene subcarpetas: el escaneo inicial no encuentra PDFs sueltos.
    a._var_ent.set(str(carpeta))
    a._poblar_lista(carpeta)
    assert a._archivos_disp == []

    # Cambia a "carpetas" — con el fix, se re-escanea la MISMA carpeta ya
    # elegida sin que el usuario tenga que volver a pulsar "Examinar…".
    a._var_tipo.set("carpetas")
    a._on_tipo()

    assert len(a._archivos_disp) == 2
    assert len(a._lb.curselection()) == 2  # todos preseleccionados, como al examinar


def test_cambiar_tipo_sin_carpeta_elegida_no_falla(app_cfg):
    a, _tmp_path = app_cfg
    assert a._var_ent.get() == ""
    a._var_tipo.set("img")
    a._on_tipo()  # no debe lanzar excepción
    assert a._archivos_disp == []
