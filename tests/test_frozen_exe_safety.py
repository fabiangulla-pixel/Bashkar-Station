"""tests/test_frozen_exe_safety.py — Guard contra el incidente real de esta
sesión: dentro de un .exe congelado (PyInstaller), sys.executable apunta al
propio .exe, no a un Python con pip. subprocess.check_call([sys.executable,
"-m", "pip", "install", ...]) relanza copias completas de la app en vez de
instalar algo; en app.py._auto_instalar() esto generó una bomba de fork
exponencial (~90 procesos en 12s) que tumbó una máquina real. Estos tests
verifican que ningún camino de auto-instalación pueda disparar
subprocess cuando sys.frozen es True."""

import subprocess

import pytest

pytest.importorskip("tkinter")


def test_auto_instalar_no_llama_subprocess_si_frozen(monkeypatch):
    import app as appmod
    monkeypatch.setattr(appmod.sys, "frozen", True, raising=False)
    llamado = {"si": False}
    monkeypatch.setattr(subprocess, "check_call",
                         lambda *a, **k: llamado.__setitem__("si", True))
    appmod._auto_instalar()
    assert llamado["si"] is False


def test_fijar_numpy_no_llama_subprocess_si_frozen(monkeypatch):
    import app as appmod
    monkeypatch.setattr(appmod.sys, "frozen", True, raising=False)
    llamado = {"si": False}
    monkeypatch.setattr(subprocess, "check_call",
                         lambda *a, **k: llamado.__setitem__("si", True))
    appmod._fijar_numpy()
    assert llamado["si"] is False


def test_instalar_motor_no_llama_subprocess_si_frozen(monkeypatch):
    from core.layout_neural import instalar_motor
    import sys
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    llamado = {"si": False}
    monkeypatch.setattr(subprocess, "check_call",
                         lambda *a, **k: llamado.__setitem__("si", True))
    mensajes = []
    resultado = instalar_motor("yolo", callback=mensajes.append)
    assert llamado["si"] is False
    assert resultado is False
    assert any("congelado" in m or ".exe" in m for m in mensajes)


def test_instalar_motor_funciona_normal_sin_frozen(monkeypatch):
    """Sin sys.frozen, el comportamiento original (intentar pip install) se
    conserva — este guard no debe romper el flujo de desarrollo normal."""
    from core.layout_neural import instalar_motor
    import sys
    monkeypatch.delattr(sys, "frozen", raising=False)
    llamado = {"si": False}
    monkeypatch.setattr(subprocess, "check_call",
                         lambda *a, **k: llamado.__setitem__("si", True))
    instalar_motor("yolo", callback=lambda m: None)
    assert llamado["si"] is True
