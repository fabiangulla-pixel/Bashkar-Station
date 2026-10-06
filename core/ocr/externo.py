"""core/ocr/externo.py — Motores que viven en otro venv, como trabajador persistente.

Surya y PaddleOCR no caben en el venv de Bashkar: Surya baja Pillow e instala
otro OpenCV; Paddle y torch chocan por las DLL de CUDA en Windows. Cada uno
tiene su venv (``C:\\dev\\venv-surya``, ``C:\\dev\\venv-paddle``; o lo que digan
``BASHKAR_VENV_SURYA`` / ``BASHKAR_VENV_PADDLE``).

Kraken arranca un proceso por página y recarga el modelo cada vez. En GPU eso
es casi todo el tiempo, así que aquí el proceso arranca UNA vez, carga el
modelo y atiende páginas por un protocolo de líneas JSON:

    → {"imagen": "C:/.../p0001.jpg"}
    ← {"ok": true, "texto": "...", "confianza": 91.2, "bloques": [...], "version": "..."}
    ← {"ok": false, "error": "..."}

La primera línea que escribe el trabajador al arrancar es
``{"listo": true, "version": "..."}``. Todo lo demás que imprima (barras de
progreso, avisos) debe ir a stderr: stdout es solo el protocolo.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from core.ocr.interfaces import Bloque, ResultadoOCR

DIR_TRABAJADORES = Path(__file__).parent / "trabajadores"


def python_de_venv(variable: str, por_defecto: Path) -> Path:
    venv = Path(os.environ.get(variable) or por_defecto)
    return venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


class TrabajadorExterno:
    """Proceso hijo con el modelo cargado. Seguro entre hilos (un pedido a la vez)."""

    def __init__(self, python: Path, script: Path, args: list[str] | None = None,
                 timeout_arranque: float = 600):
        self.python, self.script, self.args = Path(python), Path(script), args or []
        self.timeout_arranque = timeout_arranque
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self.version = ""
        self._stderr_cola: list[str] = []

    def _leer_stderr(self, flujo):
        for linea in flujo:
            self._stderr_cola.append(linea.rstrip())
            del self._stderr_cola[:-40]

    def _arrancar(self):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        # Las variables de hilos de Bashkar no deben limitar al trabajador GPU.
        for v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS"):
            env.pop(v, None)
        self._proc = subprocess.Popen(
            [str(self.python), str(self.script), *self.args],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        threading.Thread(target=self._leer_stderr, args=(self._proc.stderr,),
                         daemon=True).start()
        saludo = self._leer_linea(self.timeout_arranque)
        if not saludo.get("listo"):
            raise RuntimeError(f"el trabajador no arrancó: {saludo}")
        self.version = saludo.get("version", "")

    def _leer_linea(self, timeout: float) -> dict:
        resultado: dict = {}

        def leer():
            linea = self._proc.stdout.readline()
            resultado["linea"] = linea

        t = threading.Thread(target=leer, daemon=True)
        t.start()
        t.join(timeout)
        linea = resultado.get("linea")
        if not linea:
            cola = "\n".join(self._stderr_cola[-10:])
            self.cerrar()
            raise RuntimeError(f"el trabajador {self.script.name} no respondió"
                               f"{' (tiempo agotado)' if t.is_alive() else ''}.\n{cola}")
        return json.loads(linea)

    def pedir(self, pedido: dict, timeout: float = 900) -> dict:
        with self._lock:
            if self._proc is None or self._proc.poll() is not None:
                self._arrancar()
            self._proc.stdin.write(json.dumps(pedido, ensure_ascii=False) + "\n")
            self._proc.stdin.flush()
            r = self._leer_linea(timeout)
        if not r.get("ok"):
            raise RuntimeError(r.get("error", "error desconocido del trabajador"))
        return r

    def cerrar(self):
        p, self._proc = self._proc, None
        if p and p.poll() is None:
            try:
                p.stdin.close()
                p.wait(timeout=10)
            except Exception:
                p.kill()


class MotorExterno:
    """Base de los adaptadores de motores en otro venv."""

    nombre = etiqueta = ""
    variable_venv = ""
    venv_por_defecto = Path()
    script = ""
    paquete = ""          # lo que se importa para comprobar la instalación

    def __init__(self):
        self._trabajador: TrabajadorExterno | None = None

    def _python(self) -> Path:
        return python_de_venv(self.variable_venv, self.venv_por_defecto)

    def _args(self) -> list[str]:
        return []

    def motivo_no_disponible(self) -> str | None:
        # Se mira el disco, no se importa: importar paddle en un subproceso
        # tarda decenas de segundos y el catálogo de la GUI lo pregunta por
        # cada motor (sesión 72: el panel de benchmark tardaba 96 s en abrir).
        py = self._python()
        if not py.exists():
            return f"falta el venv de {self.etiqueta} ({py.parent.parent}); ver INSTALACION.md"
        venv = py.parent.parent
        sitios = [venv / "Lib" / "site-packages", *venv.glob("lib/python3*/site-packages")]
        if not any((s / self.paquete).is_dir() for s in sitios):
            return f"{self.paquete} no está instalado en {venv}"
        return None

    def version(self) -> str:
        if self._trabajador and self._trabajador.version:
            return self._trabajador.version
        return f"{self.nombre} (sin arrancar)"

    def reconocer(self, imagen: Path) -> ResultadoOCR:
        import time
        t0 = time.perf_counter()
        if self._trabajador is None:
            self._trabajador = TrabajadorExterno(
                self._python(), DIR_TRABAJADORES / self.script, self._args())
        r = self._trabajador.pedir({"imagen": str(Path(imagen).resolve())})
        bloques = [Bloque.de_dict(b) for b in r.get("bloques", [])]
        return ResultadoOCR(r.get("texto", ""), self.nombre, r.get("version") or self.version(),
                            confianza=r.get("confianza"), bloques=bloques,
                            segundos=round(time.perf_counter() - t0, 3),
                            detalles=r.get("detalles", {}))

    def liberar(self) -> None:
        if self._trabajador:
            self._trabajador.cerrar()
            self._trabajador = None
