"""Tests de la pantalla de inicio (_welcome_*).

Nota de diseño de estos tests: NO se prueba la rama de decisión de
_cargar_ultimo_proyecto (env BASHKAR_NO_WELCOME / pref "mostrar_inicio")
disparándola vía el self.after(200, ...) programado en __init__, porque
para cuando corre este archivo (tarde en orden alfabético) muchos otros
módulos de test ya sobrescribieron BashkarApp._cargar_ultimo_proyecto a
nivel de CLASE con `lambda self: None` (patrón usado en todo el resto de
la suite para evitar I/O real al instanciar) — esa sobreescritura nunca
se revierte entre archivos, así que el timer programado ya no invocaría
el método real. Por eso cada test llama directo al método real que le
interesa verificar (_welcome_mostrar, _welcome_elegir,
_cargar_ultimo_proyecto_directo), evitando depender de cuál lambda haya
quedado pisando la clase en ese momento del orden de ejecución."""

import pytest

tk = pytest.importorskip("tkinter")


@pytest.fixture
def app_sin_autocargar():
    import app as appmod
    appmod.BashkarApp._cargar_ultimo_proyecto = lambda self: None
    try:
        a = appmod.BashkarApp()
    except tk.TclError:
        pytest.skip("Sin entorno gráfico para tkinter")
    for _ in range(3):
        a.update()
    yield a, appmod
    try:
        a.destroy()
    except Exception:
        pass


def test_welcome_mostrar_construye_ventana(app_sin_autocargar, monkeypatch, tmp_path):
    a, appmod = app_sin_autocargar
    monkeypatch.setattr("core.project_manager.listar_proyectos", lambda: [])
    a._welcome_mostrar()
    a.update()
    assert a._welcome_win is not None and a._welcome_win.winfo_exists()


def test_welcome_mostrar_con_proyecto_reciente_muestra_tarjeta(app_sin_autocargar, monkeypatch):
    a, appmod = app_sin_autocargar
    monkeypatch.setattr("core.project_manager.listar_proyectos", lambda: [
        {"nombre": "Estampa", "publicacion": "Estampa", "modificado": "hoy", "ruta": "x.bashkar"},
    ])
    a._welcome_mostrar()
    a.update()
    assert a._welcome_win is not None and a._welcome_win.winfo_exists()


def test_protocolo_cierre_invoca_crear_proyecto_automatico(app_sin_autocargar, monkeypatch):
    """El handler WM_DELETE_WINDOW registrado por _welcome_mostrar debe
    llamar a _crear_proyecto_automatico (nunca dejar la app sin proyecto).
    Se invoca el comando Tcl real registrado por .protocol(), no una
    simulación de _welcome_elegir por separado."""
    a, appmod = app_sin_autocargar
    monkeypatch.setattr("core.project_manager.listar_proyectos", lambda: [])
    a._welcome_mostrar()
    a.update()

    llamado = {"si": False}
    a._crear_proyecto_automatico = lambda: llamado.__setitem__("si", True)
    win = a._welcome_win
    cmd_name = win.protocol("WM_DELETE_WINDOW")
    assert cmd_name  # el protocolo sí quedó registrado
    win.tk.call(cmd_name)
    assert llamado["si"] is True


def test_welcome_elegir_cierra_ventana_y_ejecuta_accion(app_sin_autocargar, monkeypatch):
    a, appmod = app_sin_autocargar
    monkeypatch.setattr("core.project_manager.listar_proyectos", lambda: [])
    a._welcome_mostrar()
    a.update()

    llamado = {"si": False}
    win = a._welcome_win
    a._welcome_elegir(win, lambda: llamado.__setitem__("si", True))
    assert llamado["si"] is True
    assert a._welcome_win is None
    assert not win.winfo_exists()


def test_checkbox_no_mostrar_guarda_pref(monkeypatch, tmp_path):
    prefs_path = tmp_path / "prefs.json"
    monkeypatch.setattr("core.user_prefs.PREFS_PATH", prefs_path)
    from core.user_prefs import guardar_pref, obtener_pref

    guardar_pref("mostrar_inicio", False)
    assert obtener_pref("mostrar_inicio", True) is False


def test_cargar_ultimo_proyecto_directo_sin_proyecto_crea_automatico(
        app_sin_autocargar, monkeypatch, tmp_path):
    """Cuerpo original (sin pantalla de inicio): sin proyecto previo, debe
    caer a _crear_proyecto_automatico."""
    a, appmod = app_sin_autocargar
    monkeypatch.setattr("core.project_manager.cargar_ultimo", lambda: None)

    llamado = {"si": False}
    a._crear_proyecto_automatico = lambda: llamado.__setitem__("si", True)
    a._cargar_ultimo_proyecto_directo()
    assert llamado["si"] is True
