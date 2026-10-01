"""Ningún `self.x = ...` puede llamarse igual que un método de su clase.

Pasó con la bitácora: `__init__` hacía `self._bitacora_engine = None` y el
método `_bitacora_engine()` quedaba tapado; cada nota fallaba con
"'NoneType' object is not callable" dentro de un callback de Tk, donde nadie
lo veía. Este test lo detecta en todo el código por análisis estático.
"""

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EXCLUIR = {"build", "dist", "_prueba5", "tests", ".venv", "venv", "scripts"}


def _colisiones(ruta: Path):
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    for cls in (n for n in ast.walk(arbol) if isinstance(n, ast.ClassDef)):
        metodos = {m.name for m in cls.body
                   if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for nodo in ast.walk(cls):
            if isinstance(nodo, ast.Assign):
                objetivos = nodo.targets
            elif isinstance(nodo, ast.AnnAssign):
                objetivos = [nodo.target]
            else:
                continue
            for o in objetivos:
                for x in ast.walk(o):
                    if (isinstance(x, ast.Attribute) and isinstance(x.value, ast.Name)
                            and x.value.id == "self" and x.attr in metodos):
                        yield f"{ruta.relative_to(RAIZ)}:{x.lineno} {cls.name}.{x.attr}"


def test_ningun_atributo_tapa_un_metodo():
    archivos = [p for p in RAIZ.rglob("*.py")
                if not EXCLUIR & set(p.relative_to(RAIZ).parts)]
    assert len(archivos) > 100
    problemas = [c for f in archivos for c in _colisiones(f)]
    assert problemas == []


def test_ningun_atributo_tapa_un_metodo_de_otro_panel():
    """Con los paneles como mixins, un `self.x = ...` en app.py puede tapar un
    método definido en paneles/*.py (otra clase del mismo objeto)."""
    fuentes = [RAIZ / "app.py", *sorted((RAIZ / "paneles").glob("*.py"))]
    metodos, asignaciones = set(), []
    for ruta in fuentes:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        for cls in (n for n in ast.walk(arbol) if isinstance(n, ast.ClassDef)):
            if cls.name != "BashkarApp" and ruta.parent.name != "paneles":
                continue
            metodos |= {m.name for m in cls.body
                        if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))}
            for nodo in ast.walk(cls):
                objetivos = (nodo.targets if isinstance(nodo, ast.Assign)
                             else [nodo.target] if isinstance(nodo, ast.AnnAssign) else [])
                for o in objetivos:
                    for x in ast.walk(o):
                        if (isinstance(x, ast.Attribute) and isinstance(x.value, ast.Name)
                                and x.value.id == "self"):
                            asignaciones.append((ruta.name, x.lineno, x.attr))
    problemas = [f"{f}:{ln} self.{a}" for f, ln, a in asignaciones if a in metodos]
    assert problemas == []
