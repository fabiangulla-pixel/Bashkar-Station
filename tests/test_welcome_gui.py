"""Tests de la pantalla de inicio (_welcome_*) — se muestra según la
preferencia "mostrar_inicio" y la variable de entorno BASHKAR_NO_WELCOME;
cerrarla sin elegir nunca debe dejar la app sin proyecto."""

import pytest

tk = pytest.importorskip("tkinter")


def _instanciar_app():
    import app as appmod
    try:
        return appmod.BashkarApp(), appmod
    except tk.TclError:
        pytest.skip("Sin entorno gráfico para tkinter")


def test_con_no_welcome_env_no_muestra_pantalla_inicio(monkeypatch, tmp_path):
    monkeypatch.setenv("BASHKAR_NO_WELCOME", "1")
    monkeypatch.setattr("core.user_prefs.PREFS_PATH", tmp_path / "prefs.json")
    a, appmod = _instanciar_app()
    try:
        for _ in range(5):
            a.update()
        assert getattr(a, "_welcome_win", None) is None
    finally:
        a.destroy()


def test_con_pref_mostrar_inicio_false_no_muestra_pantalla(monkeypatch, tmp_path):
    monkeypatch.delenv("BASHKAR_NO_WELCOME", raising=False)
    prefs_path = tmp_path / "prefs.json"
    monkeypatch.setattr("core.user_prefs.PREFS_PATH", prefs_path)
    from core.user_prefs import guardar_pref
    guardar_pref("mostrar_inicio", False)

    a, appmod = _instanciar_app()
    try:
        for _ in range(5):
            a.update()
        assert getattr(a, "_welcome_win", None) is None
    finally:
        a.destroy()


def test_con_pref_default_muestra_pantalla_inicio(monkeypatch, tmp_path):
    monkeypatch.delenv("BASHKAR_NO_WELCOME", raising=False)
    monkeypatch.setattr("core.user_prefs.PREFS_PATH", tmp_path / "prefs.json")
    monkeypatch.setattr("core.project_manager.listar_proyectos", lambda: [])

    a, appmod = _instanciar_app()
    try:
        for _ in range(5):
            a.update()
        assert a._welcome_win is not None and a._welcome_win.winfo_exists()
    finally:
        a.destroy()


def test_protocolo_cierre_invoca_crear_proyecto_automatico(monkeypatch, tmp_path):
    """El handler WM_DELETE_WINDOW registrado por _welcome_mostrar debe
    llamar a _crear_proyecto_automatico (nunca dejar la app sin proyecto).
    Se invoca el comando Tcl real registrado por .protocol(), no una
    simulación de _welcome_elegir por separado."""
    monkeypatch.delenv("BASHKAR_NO_WELCOME", raising=False)
    monkeypatch.setattr("core.user_prefs.PREFS_PATH", tmp_path / "prefs.json")
    monkeypatch.setattr("core.project_manager.listar_proyectos", lambda: [])

    a, appmod = _instanciar_app()
    try:
        for _ in range(5):
            a.update()
        llamado = {"si": False}
        a._crear_proyecto_automatico = lambda: llamado.__setitem__("si", True)
        win = a._welcome_win
        cmd_name = win.protocol("WM_DELETE_WINDOW")
        assert cmd_name  # el protocolo sí quedó registrado
        win.tk.call(cmd_name)
        assert llamado["si"] is True
    finally:
        a.destroy()


def test_continuar_llama_cargar_directo(monkeypatch, tmp_path):
    monkeypatch.delenv("BASHKAR_NO_WELCOME", raising=False)
    monkeypatch.setattr("core.user_prefs.PREFS_PATH", tmp_path / "prefs.json")
    monkeypatch.setattr("core.project_manager.listar_proyectos", lambda: [
        {"nombre": "Estampa", "publicacion": "Estampa", "modificado": "hoy", "ruta": "x.bashkar"},
    ])

    a, appmod = _instanciar_app()
    try:
        for _ in range(5):
            a.update()
        llamado = {"si": False}
        a._cargar_ultimo_proyecto_directo = lambda: llamado.__setitem__("si", True)
        a._welcome_elegir(a._welcome_win, a._cargar_ultimo_proyecto_directo)
        assert llamado["si"] is True
        assert a._welcome_win is None
    finally:
        a.destroy()


def test_checkbox_no_mostrar_guarda_pref(monkeypatch, tmp_path):
    monkeypatch.delenv("BASHKAR_NO_WELCOME", raising=False)
    prefs_path = tmp_path / "prefs.json"
    monkeypatch.setattr("core.user_prefs.PREFS_PATH", prefs_path)
    monkeypatch.setattr("core.project_manager.listar_proyectos", lambda: [])

    a, appmod = _instanciar_app()
    try:
        for _ in range(5):
            a.update()
        from core.user_prefs import guardar_pref
        guardar_pref("mostrar_inicio", False)
        from core.user_prefs import obtener_pref
        assert obtener_pref("mostrar_inicio", True) is False
    finally:
        a.destroy()
