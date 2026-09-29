"""core/registro_errores.py — Que ningún error se pierda en silencio.

El ``.exe`` corre sin consola (``console=False`` en el .spec). Una excepción
dentro de un callback de Tk o de un hilo de trabajo se imprimía en un stderr
que no existe: el investigador veía que "no pasa nada" y el fallo quedaba
invisible. Así sobrevivió meses la bitácora, que no guardaba ninguna nota.

``instalar(app)`` engancha los tres puntos por donde escapan excepciones
(callbacks de Tk, hilos y el hilo principal), las escribe en un registro con
rutas personales anonimizadas y, si la app tiene ``toast``, avisa en pantalla.
``registrar(mensaje)`` sirve para los fallos que el código ya captura pero no
debe callar.
"""

from __future__ import annotations

import logging
import sys
import threading
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

NOMBRE = "bashkar"
_logger: logging.Logger | None = None


def ruta_registro() -> Path:
    """``BASHKAR_REGISTRO`` manda (la usan los tests para no ensuciar el
    registro real del investigador); si no, la carpeta de datos del usuario."""
    import os
    forzada = os.environ.get("BASHKAR_REGISTRO", "").strip()
    if forzada:
        return Path(forzada)
    from core.plataforma import dir_datos_usuario
    return dir_datos_usuario("BashkarStation") / "logs" / "errores.log"


def _anonimizar(texto: str) -> str:
    try:
        from core.proveniencia import anonimizar_ruta
        return anonimizar_ruta(texto)
    except Exception:
        return texto


def obtener_logger(ruta: Path | None = None) -> logging.Logger:
    """Logger con archivo rotativo (1 MB × 3). Idempotente."""
    global _logger
    if _logger is not None and ruta is None:
        return _logger
    lg = logging.getLogger(NOMBRE)
    lg.setLevel(logging.INFO)
    lg.propagate = False
    for h in list(lg.handlers):
        lg.removeHandler(h)
    destino = ruta or ruta_registro()
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        h = RotatingFileHandler(destino, maxBytes=1_000_000, backupCount=3,
                                encoding="utf-8")
    except OSError:
        h = logging.StreamHandler()  # sin disco escribible: al menos a stderr
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    lg.addHandler(h)
    if sys.stderr is not None:  # en desarrollo, también a consola
        lg.addHandler(logging.StreamHandler())
    _logger = lg
    return lg


def registrar(mensaje: str, exc: BaseException | None = None,
              nivel: int = logging.WARNING) -> None:
    """Deja constancia de un fallo capturado. Nunca lanza."""
    try:
        texto = mensaje
        if exc is not None:
            texto += "\n" + "".join(traceback.format_exception(exc))
        obtener_logger().log(nivel, _anonimizar(texto))
    except Exception:
        pass


def instalar(app=None) -> None:
    """Engancha callbacks de Tk, hilos y hilo principal al registro."""

    def _avisar(resumen: str):
        toast = getattr(app, "toast", None)
        if toast is None:
            return
        try:
            app.after(0, lambda: toast(
                f"Error inesperado: {resumen[:90]} — detalle en el registro de errores",
                "error", 6000))
        except Exception:
            pass

    def _tk(exc_type, exc, tb):
        registrar(f"Excepción en callback de Tk: {exc_type.__name__}: {exc}",
                  exc.with_traceback(tb), logging.ERROR)
        _avisar(f"{exc_type.__name__}: {exc}")

    def _hilo(args):
        if args.exc_type is SystemExit:
            return
        nombre = getattr(args.thread, "name", "?")
        registrar(f"Excepción en hilo {nombre}: {args.exc_type.__name__}: {args.exc_value}",
                  args.exc_value, logging.ERROR)
        _avisar(f"{args.exc_type.__name__}: {args.exc_value}")

    anterior = sys.excepthook

    def _principal(exc_type, exc, tb):
        registrar(f"Excepción no capturada: {exc_type.__name__}: {exc}",
                  exc.with_traceback(tb), logging.CRITICAL)
        anterior(exc_type, exc, tb)

    if app is not None:
        app.report_callback_exception = _tk
    threading.excepthook = _hilo
    sys.excepthook = _principal
