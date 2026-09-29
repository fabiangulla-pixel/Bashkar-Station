"""Cada módulo de core/, datos/ y exportadores/ se importa sin error.

Un import roto en un módulo que ningún otro test toca solo aparece cuando el
investigador abre ese panel. Aquí salta en la CI.
"""

import importlib
import pkgutil

import pytest

import core
import datos
import exportadores

MODULOS = [
    f"{paquete.__name__}.{m.name}"
    for paquete in (core, datos, exportadores)
    for m in pkgutil.iter_modules(paquete.__path__)
]


@pytest.mark.parametrize("nombre", MODULOS)
def test_modulo_importa(nombre):
    importlib.import_module(nombre)


def test_hay_modulos_que_probar():
    assert len(MODULOS) > 80
