"""paneles — Las pestañas de BashkarApp, fuera del monolito.

Cada módulo define una clase mixin con los métodos de una pestaña, copiados
literalmente de app.py (paso 7 de las recomendaciones: app.py como punto de
composición). BashkarApp hereda de todas.

Los métodos usan nombres globales de app.py (``ST``, ``tk``, los colores…)
sin prefijo. ``sincronizar(globals())`` los refleja en cada módulo de panel:
app.py la llama al terminar de cargarse y cada vez que cambia la paleta,
porque el tema oscuro/claro REESCRIBE los colores en caliente y una copia
tomada solo al importar se quedaría con los viejos.
"""

from __future__ import annotations

import importlib
import pkgutil
import sys


def modulos() -> list:
    paquete = sys.modules[__name__]
    return [importlib.import_module(f"{__name__}.{m.name}")
            for m in pkgutil.iter_modules(paquete.__path__)]


def sincronizar(globales: dict) -> None:
    """Copia los nombres globales de app.py en cada módulo de panel."""
    visibles = {k: v for k, v in globales.items()
                if not (k.startswith("__") and k.endswith("__"))}
    for mod in modulos():
        mod.__dict__.update(visibles)
