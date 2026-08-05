"""Invariantes de concurrencia con Tkinter (sesión 48).

Tcl no es thread-safe. Tocar una variable o un widget Tk desde un hilo worker
serializa la llamada contra el bucle de eventos del hilo principal, con riesgo
de bloqueo mutuo si el principal está esperando al worker. La regla del
proyecto es: **todo lo que venga de la UI se lee en el lanzador (hilo
principal) y se pasa al worker ya congelado; todo lo que vuelva a la UI pasa
por `self.after`.**

Estos tests analizan el árbol sintáctico de `app.py`, no su comportamiento en
ejecución: son una barrera para que la regla no se rompa al añadir workers.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
APP = RAIZ / "app.py"

# Nombres de atributo que delatan un widget o una variable de Tk
_RE_TK = re.compile(r"^_(var|txt|lbl|btn|cmb|ent|lst|tree|nb|canvas|prog|frm|sb)_")
_METODOS_TK = {"get", "set", "cget", "config", "configure", "insert", "delete",
               "curselection", "select", "state", "yview", "see"}


def _rango(nodo: ast.AST) -> set[int]:
    return set(range(nodo.lineno, (nodo.end_lineno or nodo.lineno) + 1))


@pytest.fixture(scope="module")
def clase_app() -> ast.ClassDef:
    arbol = ast.parse(APP.read_text(encoding="utf-8-sig"))
    for n in ast.walk(arbol):
        if isinstance(n, ast.ClassDef) and "App" in n.name:
            return n
    pytest.fail("no se encontró la clase de la aplicación en app.py")


def _workers(cls: ast.ClassDef) -> dict[str, ast.FunctionDef]:
    """Métodos que se ejecutan en un hilo, incluidos los que estos llaman.

    No basta con los `_worker_*` y los `target=` de `Thread`: un worker puede
    delegar en un método auxiliar, y ese auxiliar corre igualmente en el hilo.
    Ese punto ciego dejó pasar un acceso a Tk real (`_bench_correr_ruta`
    leyendo `self._etz_numero.get()`), así que la transitividad se sigue hasta
    punto fijo.
    """
    metodos = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    targets = set()
    for n in ast.walk(cls):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "Thread"):
            for kw in n.keywords:
                if kw.arg == "target":
                    t = kw.value
                    if isinstance(t, ast.Attribute):
                        targets.add(t.attr)
                    elif isinstance(t, ast.Name):
                        targets.add(t.id)

    nombres = {m for m in metodos if m.startswith("_worker_")} | (targets & set(metodos))

    # Cierre transitivo: todo `self.X(...)` llamado desde un método en hilo
    # también corre en hilo. Se excluye `self.after`, que es precisamente el
    # mecanismo para volver al hilo principal.
    cambio = True
    while cambio:
        cambio = False
        for nombre in list(nombres):
            for n in ast.walk(metodos[nombre]):
                if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                        and isinstance(n.func.value, ast.Name)
                        and n.func.value.id == "self"
                        and n.func.attr in metodos
                        and n.func.attr not in nombres
                        and n.lineno not in _lineas_seguras(metodos[nombre])):
                    nombres.add(n.func.attr)
                    cambio = True

    return {m: metodos[m] for m in sorted(nombres)}


def _lineas_seguras(worker: ast.FunctionDef) -> set[int]:
    """Líneas que SÍ pueden tocar Tk: las que se ejecutan vía `self.after`."""
    seguras: set[int] = set()
    nombres_diferidos: set[str] = set()

    for n in ast.walk(worker):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "after"):
            for arg in n.args:
                if isinstance(arg, ast.Name):
                    nombres_diferidos.add(arg.id)
                elif isinstance(arg, ast.Lambda):
                    seguras |= _rango(arg)

    for n in ast.walk(worker):
        # ast.walk incluye el nodo raíz: hay que excluir el propio worker o se
        # marcaría su cuerpo entero como seguro por contener un self.after.
        if isinstance(n, ast.FunctionDef) and n is not worker:
            delega = any(
                isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                and c.func.attr == "after" for c in ast.walk(n))
            if n.name in nombres_diferidos or delega:
                seguras |= _rango(n)
    return seguras


def _infracciones(worker: ast.FunctionDef) -> list[tuple[int, str]]:
    seguras = _lineas_seguras(worker)
    hallazgos = []
    for n in ast.walk(worker):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in _METODOS_TK
                and isinstance(n.func.value, ast.Attribute)
                and isinstance(n.func.value.value, ast.Name)
                and n.func.value.value.id == "self"
                and _RE_TK.match(n.func.value.attr)
                and n.lineno not in seguras):
            hallazgos.append((n.lineno, f"self.{n.func.value.attr}.{n.func.attr}()"))
    return sorted(set(hallazgos))


def test_la_auditoria_reconoce_los_workers(clase_app):
    """Guarda de la propia prueba: si deja de encontrar workers, no prueba nada."""
    assert len(_workers(clase_app)) >= 40


def test_ningun_worker_toca_tk_fuera_de_after(clase_app):
    """Ningún hilo worker lee ni escribe Tk directamente (sesión 48: eran 20)."""
    problemas = {}
    for nombre, nodo in _workers(clase_app).items():
        hallazgos = _infracciones(nodo)
        if hallazgos:
            problemas[nombre] = hallazgos

    assert not problemas, (
        "Hay accesos a Tk desde hilos worker. Léelos en el lanzador (hilo "
        "principal) y pásalos congelados, o devuélvelos con self.after:\n"
        + "\n".join(f"  {w}: {h}" for w, h in problemas.items()))


def test_la_auditoria_detecta_una_infraccion_inventada():
    """Prueba negativa: el detector tiene que fallar con código malo de verdad."""
    malo = ast.parse(
        "class App:\n"
        "    def _worker_malo(self):\n"
        "        x = self._var_dpi.get()\n"
        "        return x\n"
    )
    worker = malo.body[0].body[0]
    assert _infracciones(worker), "el detector no vio una infracción evidente"


def test_auto_instalar_no_importa_los_paquetes_para_comprobarlos():
    """`__import__` cargaba torch/spacy en cada arranque (16,8 s medidos).

    La comprobación tiene que usar find_spec, que no ejecuta el módulo.
    """
    fuente = APP.read_text(encoding="utf-8-sig")
    arbol = ast.parse(fuente)
    fn = next(n for n in ast.walk(arbol)
              if isinstance(n, ast.FunctionDef) and n.name == "_auto_instalar")
    cuerpo = ast.unparse(fn)
    assert "find_spec" in cuerpo
    assert "__import__" not in cuerpo


def test_var_congelada_conserva_la_interfaz_get():
    """El worker sigue llamando .get(); el valor ya viene leído del principal."""
    import app  # noqa: PLC0415 — importar aquí evita el costo si se filtra el test

    v = app._VarCongelada("spa")
    assert v.get() == "spa"
    assert app._VarCongelada(300).get() == 300
    # Sin estado Tk detrás: dos llamadas dan siempre lo mismo.
    congelada = app._VarCongelada(0)
    assert congelada.get() == congelada.get() == 0


def test_los_render_de_pagina_no_tocan_tk(clase_app):
    """`_norm_render_pagina` y `_etz_render_pdf` corren en hilo: deben ser puros."""
    metodos = {n.name: n for n in clase_app.body if isinstance(n, ast.FunctionDef)}
    for nombre in ("_norm_render_pagina", "_etz_render_pdf"):
        assert nombre in metodos, f"falta {nombre} (¿se revirtió el arreglo?)"
        cuerpo = ast.unparse(metodos[nombre])
        assert "ImageTk" not in cuerpo, f"{nombre} crea un objeto Tk dentro del hilo"
        assert "_canvas" not in cuerpo, f"{nombre} toca el canvas dentro del hilo"
