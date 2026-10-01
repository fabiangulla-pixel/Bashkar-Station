"""Fuente de la GUI para los tests estáticos: app.py + paneles/*.py.

Desde la sesión 71 los métodos de BashkarApp viven repartidos entre app.py y
los mixins de paneles/. Los tests que analizan el código de la GUI (que ningún
hilo toque Tk, que no se duplique el OCR de visión…) deben mirar las dos
partes: leer solo app.py los haría pasar en falso sobre lo que se movió.
"""

from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
APP = RAIZ / "app.py"
PANELES = RAIZ / "paneles"


def archivos_gui() -> list[Path]:
    return [APP, *sorted(p for p in PANELES.glob("*.py") if p.stem != "__init__")]


@lru_cache(maxsize=1)
def fuente_gui() -> str:
    """Todo el texto de la GUI, para búsquedas de cadenas."""
    return "\n".join(p.read_text(encoding="utf-8-sig") for p in archivos_gui())


def _metodos_de(ruta: Path, nombre_clase: str | None) -> list[str]:
    texto = ruta.read_text(encoding="utf-8-sig")
    lineas = texto.splitlines(keepends=True)
    arbol = ast.parse(texto)
    trozos = []
    for cls in (n for n in arbol.body if isinstance(n, ast.ClassDef)):
        if nombre_clase and cls.name != nombre_clase:
            continue
        for m in cls.body:
            ini = m.decorator_list[0].lineno if getattr(m, "decorator_list", None) else m.lineno
            trozos.append("".join(lineas[ini - 1:m.end_lineno]).rstrip("\n") + "\n")
    return trozos


@lru_cache(maxsize=1)
def fuente_clase_app() -> str:
    """BashkarApp con los métodos de todos sus paneles, como una sola clase."""
    trozos = _metodos_de(APP, "BashkarApp")
    for ruta in archivos_gui()[1:]:
        trozos += _metodos_de(ruta, None)
    return "class BashkarApp:\n" + "\n".join(trozos)


def clase_app() -> ast.ClassDef:
    """Árbol de la clase compuesta (números de línea propios y únicos)."""
    return ast.parse(fuente_clase_app()).body[0]
