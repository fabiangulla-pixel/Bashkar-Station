"""Verifica que requirements.txt y requirements.lock.txt no se hayan separado.

Hay dos rutas de instalación (ver INSTALACION.md):
  · requirements.lock.txt — versiones exactas verificadas en verde (investigación,
    publicación, .exe, CI);
  · requirements.txt — rangos, para quien necesita versiones recientes.

Si se agrega un paquete a requirements.txt y no al lock, la ruta reproducible
deja de instalarlo sin que nadie lo note (ya pasó con spylls: 11 tests
desaparecieron del conteo). Sale con 1 si hay discrepancias.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

RAIZ = Path(__file__).resolve().parent.parent


def _lineas(ruta: Path):
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.split("#", 1)[0].strip()
        if linea and not linea.startswith("-"):
            yield linea


def leer_lock(ruta: Path) -> dict[str, str]:
    fijados = {}
    for linea in _lineas(ruta):
        m = re.match(r"^([A-Za-z0-9_.\-]+)==([^\s;]+)", linea)
        if m:
            fijados[canonicalize_name(m.group(1))] = m.group(2)
        elif " @ " in linea:
            fijados[canonicalize_name(linea.split(" @ ", 1)[0])] = "url"
    return fijados


def verificar(req: Path, lock: Path) -> list[str]:
    fijados = leer_lock(lock)
    problemas = []
    for linea in _lineas(req):
        r = Requirement(linea)
        nombre = canonicalize_name(r.name)
        if nombre not in fijados:
            problemas.append(f"{r.name}: está en {req.name} pero no en {lock.name}")
            continue
        version = fijados[nombre]
        if version != "url" and r.specifier and not r.specifier.contains(
                Version(version), prereleases=True):
            problemas.append(f"{r.name}: el lock fija {version}, fuera de '{r.specifier}'")
    return problemas


def main() -> int:
    problemas = verificar(RAIZ / "requirements.txt", RAIZ / "requirements.lock.txt")
    for p in problemas:
        print(f"✗ {p}")
    if not problemas:
        print("✓ requirements.txt y requirements.lock.txt son coherentes")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
