"""Los paneles extraídos de app.py siguen enganchados al monolito.

Cada panel importa lo que usa (gui_comun, tkinter…) y ruff F821 lo comprueba
en estático; estos tests lo confirman en ejecución, desde el bytecode, y
vigilan lo que ruff no ve: herencia, métodos duplicados entre paneles y que
los colores se lean de TEMA (el tema cambia en caliente).
"""

import ast
import builtins
import dis
import importlib
import pkgutil
from pathlib import Path

import pytest

import paneles

RAIZ = Path(__file__).resolve().parent.parent
MODULOS = [m.name for m in pkgutil.iter_modules(paneles.__path__)]


def _globales_de(codigo):
    """Nombres leídos con LOAD_GLOBAL en una función y sus funciones anidadas."""
    for ins in dis.get_instructions(codigo):
        if ins.opname == "LOAD_GLOBAL":
            yield ins.argval
    for c in codigo.co_consts:
        if hasattr(c, "co_code"):
            yield from _globales_de(c)


def test_hay_paneles():
    assert MODULOS


@pytest.mark.parametrize("nombre", MODULOS)
def test_todo_nombre_global_de_un_panel_se_resuelve_en_su_modulo(nombre):
    """Complementa a ruff F821 en ejecución: leído del bytecode real."""
    mod = importlib.import_module(f"paneles.{nombre}")
    faltan = set()
    for clase in (v for v in vars(mod).values() if isinstance(v, type)
                  and v.__module__ == mod.__name__):
        for atributo in vars(clase).values():
            fn = getattr(atributo, "__func__", atributo)
            if hasattr(fn, "__code__"):
                faltan |= {n for n in _globales_de(fn.__code__)
                           if n not in vars(mod) and not hasattr(builtins, n)}
    assert not faltan, f"paneles/{nombre}.py usa nombres que no importa: {sorted(faltan)}"


def test_bashkarapp_hereda_todos_los_paneles():
    import app
    clases = {c.__name__ for c in app.BashkarApp.__mro__}
    for nombre in MODULOS:
        mod = importlib.import_module(f"paneles.{nombre}")
        propias = [v.__name__ for v in vars(mod).values()
                   if isinstance(v, type) and v.__module__ == mod.__name__]
        assert set(propias) <= clases, f"{nombre}: {propias} no están en BashkarApp"


def test_ningun_metodo_definido_dos_veces():
    """Un método en dos paneles (o en un panel y en app.py) se taparía según el MRO."""
    import app
    vistos: dict[str, str] = {}
    for clase in app.BashkarApp.__mro__:
        if clase.__module__ not in ("app", "__main__") and not clase.__module__.startswith("paneles"):
            continue
        for nombre, valor in vars(clase).items():
            if callable(getattr(valor, "__func__", valor)) and not nombre.startswith("__"):
                assert nombre not in vistos, f"{nombre}: en {vistos[nombre]} y en {clase.__name__}"
                vistos[nombre] = clase.__name__


def test_el_cambio_de_tema_llega_a_los_paneles():
    """Los paneles leen TEMA.X en cada uso; _aplicar_paleta lo actualiza."""
    import app
    from gui_comun import TEMA
    original = app.CONTENT_BG
    try:
        app._aplicar_paleta({"CONTENT_BG": "#123456"})
        assert TEMA.CONTENT_BG == "#123456" == app.CONTENT_BG
    finally:
        app._aplicar_paleta({"CONTENT_BG": original})


def test_tema_coincide_con_los_colores_de_app():
    import app
    from gui_comun import TEMA
    for clave in app._PALETA_DARK:
        assert getattr(TEMA, clave) == getattr(app, clave), clave


def test_ningun_panel_usa_colores_sueltos():
    """Un color sin TEMA. delante se congelaría al importar (el tema cambia)."""
    import app
    colores = set(app._PALETA_DARK)
    for nombre in MODULOS:
        arbol = ast.parse((RAIZ / "paneles" / f"{nombre}.py").read_text(encoding="utf-8"))
        sueltos = {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name) and n.id in colores}
        assert not sueltos, f"{nombre}: {sorted(sueltos)}"


def test_ningun_panel_usa_global_ni_super():
    for nombre in MODULOS:
        arbol = ast.parse((RAIZ / "paneles" / f"{nombre}.py").read_text(encoding="utf-8"))
        assert not any(isinstance(n, (ast.Global, ast.Nonlocal)) for n in ast.walk(arbol)), nombre
        assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                       and n.func.id == "super" for n in ast.walk(arbol)), nombre
