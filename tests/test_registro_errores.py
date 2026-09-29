"""Registro de errores: lo que escapa de Tk o de un hilo queda escrito."""

import sys
import threading
from pathlib import Path

import pytest

from core import registro_errores as RE


@pytest.fixture
def log(tmp_path, monkeypatch):
    ruta = tmp_path / "errores.log"
    monkeypatch.setattr(RE, "_logger", None)
    RE.obtener_logger(ruta)
    hook_hilo, hook_sys = threading.excepthook, sys.excepthook
    yield ruta
    threading.excepthook, sys.excepthook = hook_hilo, hook_sys
    for h in list(RE._logger.handlers):
        h.close()
        RE._logger.removeHandler(h)
    monkeypatch.setattr(RE, "_logger", None)


class AppFalsa:
    def __init__(self):
        self.avisos = []

    def after(self, ms, fn):
        fn()

    def toast(self, msg, tipo, dur):
        self.avisos.append((msg, tipo))


def test_excepcion_en_callback_tk_se_registra_y_avisa(log):
    app = AppFalsa()
    RE.instalar(app)
    try:
        None()
    except TypeError as e:
        app.report_callback_exception(type(e), e, e.__traceback__)
    texto = log.read_text(encoding="utf-8")
    assert "callback de Tk" in texto and "NoneType" in texto
    assert app.avisos and app.avisos[0][1] == "error"


def test_excepcion_en_hilo_se_registra(log):
    RE.instalar(None)
    t = threading.Thread(target=lambda: 1 / 0, name="worker-prueba")
    t.start()
    t.join()
    texto = log.read_text(encoding="utf-8")
    assert "worker-prueba" in texto and "ZeroDivisionError" in texto


def test_registrar_anonimiza_rutas(log):
    RE.registrar(f"fallo en {Path.home()}\\proyecto.db")
    texto = log.read_text(encoding="utf-8")
    assert str(Path.home()) not in texto and "~" in texto
