"""Los paneles extraídos de app.py siguen enganchados al monolito.

Los módulos de paneles/ usan los nombres globales de app.py sin importarlos
(los inyecta paneles.sincronizar) y por eso ruff no puede comprobarlos
(F821 desactivado). Estos tests hacen esa comprobación en su lugar.
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


@pytest.fixture(scope="module")
def app_globales():
    import app
    return vars(app)


def test_hay_paneles():
    assert MODULOS


@pytest.mark.parametrize("nombre", MODULOS)
def test_todo_nombre_global_de_un_panel_existe_en_app(nombre, app_globales):
    mod = importlib.import_module(f"paneles.{nombre}")
    faltan = set()
    for clase in (v for v in vars(mod).values() if isinstance(v, type)
                  and v.__module__ == mod.__name__):
        for atributo in vars(clase).values():
            fn = getattr(atributo, "__func__", atributo)
            if hasattr(fn, "__code__"):
                faltan |= {n for n in _globales_de(fn.__code__)
                           if n not in app_globales and not hasattr(builtins, n)}
    assert not faltan, f"paneles/{nombre}.py usa nombres que app.py no define: {sorted(faltan)}"


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


def test_sincronizar_refleja_cambios_de_tema():
    import app
    mod = importlib.import_module(f"paneles.{MODULOS[0]}")
    original = app.CONTENT_BG
    try:
        app._aplicar_paleta({"CONTENT_BG": "#123456"})
        assert mod.CONTENT_BG == "#123456"
    finally:
        app._aplicar_paleta({"CONTENT_BG": original})


def test_ningun_panel_usa_global_ni_super():
    for nombre in MODULOS:
        arbol = ast.parse((RAIZ / "paneles" / f"{nombre}.py").read_text(encoding="utf-8"))
        assert not any(isinstance(n, (ast.Global, ast.Nonlocal)) for n in ast.walk(arbol)), nombre
        assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                       and n.func.id == "super" for n in ast.walk(arbol)), nombre
