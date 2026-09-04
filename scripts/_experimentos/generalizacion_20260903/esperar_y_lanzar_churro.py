"""Espera a que se libere la memoria y entonces lanza CHURRO. Sin supervisión.

CHURRO-3B necesita ~8,4 GB de RAM en el pico. El equipo tiene 19,35 GB, pero el
3-sep-2026 a las 18:42 Windows terminó el proceso en seco —sin mensaje, sin
stderr— porque solo quedaban 2,22 GB libres: la exportación GGUF de Aliado Libre
(PID 848) ocupaba 6,27 GB.

Este vigilante no mata nada ajeno. Espera a que ese trabajo termine por su cuenta
y a que haya margen real de memoria, y solo entonces lanza el OCR. Si el trabajo
ajeno nunca termina, este script tampoco hace nada: falla por no actuar, que es
el lado correcto en el que fallar cuando hay trabajo de otro en la máquina.
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PID_VIGILADO = 848            # aliado-libre/finetune/exportar_gguf.py
GB_NECESARIOS = 10.0          # 8,4 de pico + margen
INTERVALO_S = 60
LIMITE_HORAS = 12

BASE = Path(r"C:\build_rf\generalizacion")
SCRIPT_CHURRO = BASE / "churro_grafico.py"
SALIDA = BASE / "churro_final.txt"
ERRORES = BASE / "churro_final_err.txt"
BITACORA = BASE / "espera_churro.log"


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def gb_libres() -> float:
    est = _MEMORYSTATUSEX()
    est.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(est))
    return est.ullAvailPhys / (1024 ** 3)


def sigue_vivo(pid: int) -> bool:
    """¿Existe todavía ese PID? Vía tasklist, sin permisos especiales."""
    try:
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                           capture_output=True, text=True, timeout=30)
        return str(pid) in r.stdout
    except Exception:
        return False        # ante la duda, no bloquear para siempre


def log(msg: str) -> None:
    linea = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(linea, flush=True)
    with open(BITACORA, "a", encoding="utf-8") as f:
        f.write(linea + "\n")


def main() -> None:
    log(f"vigilando PID {PID_VIGILADO} (exportacion GGUF de Aliado Libre)")
    log(f"lanzare CHURRO cuando termine y haya >= {GB_NECESARIOS} GB libres")
    log(f"libres ahora: {gb_libres():.2f} GB")

    limite = time.time() + LIMITE_HORAS * 3600
    while time.time() < limite:
        vivo = sigue_vivo(PID_VIGILADO)
        libres = gb_libres()
        if not vivo and libres >= GB_NECESARIOS:
            log(f"via libre: proceso ajeno terminado, {libres:.2f} GB disponibles")
            break
        log(f"esperando — ajeno {'vivo' if vivo else 'terminado'}, "
            f"{libres:.2f} GB libres")
        time.sleep(INTERVALO_S)
    else:
        log(f"se agotaron las {LIMITE_HORAS} h de espera; no se lanza nada")
        return

    log("lanzando CHURRO sobre El Grafico p0006")
    with open(SALIDA, "w", encoding="utf-8") as out, \
         open(ERRORES, "w", encoding="utf-8") as err:
        proc = subprocess.run([sys.executable, "-u", str(SCRIPT_CHURRO)],
                              stdout=out, stderr=err)
    log(f"CHURRO termino con codigo {proc.returncode}")
    if proc.returncode != 0:
        log("codigo distinto de cero: revisar churro_final_err.txt")


if __name__ == "__main__":
    main()
