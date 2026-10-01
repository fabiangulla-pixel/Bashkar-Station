"""Mueve métodos de BashkarApp (app.py) a un módulo mixin en paneles/.

Uso:
    python scripts/_herramientas/extraer_panel.py <modulo> <Clase> <grupo> [<grupo>...]

Un método pertenece a un grupo según su nombre: ``_etz_x`` → "etz";
``_build_etz`` / ``_worker_etz_y`` → "etz" (el verbo inicial se ignora).
El cuerpo de cada método se copia LITERALMENTE (mismas líneas, misma
sangría): la extracción es mecánica y no cambia comportamiento.

Después de extraer: escribir ``TEMA.`` delante de los colores (el tema cambia
en caliente) y añadir los imports que pida ``ruff check paneles --select F821``
(lo compartido con app.py está en gui_comun). tests/test_paneles.py vigila
ambas cosas.

Se niega a mover métodos que usan ``global`` o ``super()``: en un mixin
cambiarían de significado.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
VERBOS = {"build", "worker", "start", "run", "export", "mostrar", "actualizar",
          "refrescar", "cargar", "guardar", "abrir"}


def grupo(nombre: str) -> str:
    partes = [p for p in nombre.strip("_").split("_") if p]
    if len(partes) > 1 and partes[0] in VERBOS:
        return partes[1]
    return partes[0] if partes else nombre


def _inicio_con_comentarios(lineas: list[str], ini: int) -> int:
    """Incluye el bloque de comentarios (banners) pegado encima del método."""
    i = ini - 1
    while i - 1 >= 0 and lineas[i - 1].strip().startswith("#"):
        i -= 1
    return i + 1


def extraer(modulo: str, clase: str, grupos: set[str]) -> int:
    app = RAIZ / "app.py"
    src = app.read_text(encoding="utf-8")
    lineas = src.splitlines(keepends=True)
    arbol = ast.parse(src)
    cls = next(n for n in arbol.body if isinstance(n, ast.ClassDef) and n.name == "BashkarApp")

    tramos = []
    for m in cls.body:
        if not isinstance(m, ast.FunctionDef) or m.name.startswith("__"):
            continue
        if grupo(m.name) not in grupos:
            continue
        prohibido = [x for x in ast.walk(m) if isinstance(x, (ast.Global, ast.Nonlocal))]
        prohibido += [x for x in ast.walk(m) if isinstance(x, ast.Call)
                      and isinstance(x.func, ast.Name) and x.func.id == "super"]
        if prohibido:
            print(f"  ✗ {m.name}: usa global/super(), se queda en app.py")
            continue
        ini = m.decorator_list[0].lineno if m.decorator_list else m.lineno
        ini = _inicio_con_comentarios(lineas, ini)
        tramos.append((ini, m.end_lineno, m.name))

    if not tramos:
        print("nada que mover")
        return 0

    destino = RAIZ / "paneles" / f"{modulo}.py"
    existente = destino.read_text(encoding="utf-8") if destino.exists() else ""
    cuerpo = []
    for ini, fin, _ in tramos:
        bloque = "".join(lineas[ini - 1:fin])
        cuerpo.append(bloque.rstrip("\n") + "\n")
    if existente:
        nuevo = existente.rstrip("\n") + "\n\n" + "\n".join(cuerpo)
    else:
        nuevo = (
            f'"""paneles/{modulo}.py — Métodos de BashkarApp extraídos de app.py.\n\n'
            f"Mixin: BashkarApp hereda de {clase}. Los cuerpos son copia literal del\n"
            "original. Importa explícitamente lo que usa; los colores del tema se\n"
            "leen de gui_comun.TEMA porque cambian en caliente.\n"
            '"""\n\nfrom __future__ import annotations\n\n\n'
            f"class {clase}:\n" + "\n".join(cuerpo)
        )
    destino.write_text(nuevo, encoding="utf-8")

    # Borrar de app.py de abajo arriba para no desplazar números de línea.
    for ini, fin, _ in sorted(tramos, reverse=True):
        del lineas[ini - 1:fin]
        # Colapsar líneas en blanco sobrantes
        while ini - 1 < len(lineas) and ini - 2 >= 0 and \
                lineas[ini - 1].strip() == "" and lineas[ini - 2].strip() == "" \
                and ini - 3 >= 0 and lineas[ini - 3].strip() == "":
            del lineas[ini - 1]
    app.write_text("".join(lineas), encoding="utf-8")
    print(f"  ✓ {len(tramos)} métodos → paneles/{modulo}.py "
          f"({sum(f - i + 1 for i, f, _ in tramos)} líneas)")
    return len(tramos)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(2)
    extraer(sys.argv[1], sys.argv[2], set(sys.argv[3:]))
