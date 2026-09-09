"""tests/test_spec_portable.py — El .spec no puede llevar rutas de una máquina.

Sesión 67: `bashkar_station.spec` empaquetaba el diccionario Hunspell desde
`C:/Users/Lenovo/AppData/Roaming/Python/Python314/site-packages/spylls/...`.
En el equipo nuevo PyInstaller aborta con "Unable to find ... when adding
binary and data files": el .exe no se podía compilar en ninguna máquina que no
fuera la del autor, y eso solo se descubre al intentar compilar. Estos tests lo
convierten en un fallo de la suite, que es mucho más barato.

Es el mismo guard que `test_plataforma.py` ya hace sobre `core/plataforma.py`.
"""
import re
from pathlib import Path

SPEC = Path(__file__).resolve().parent.parent / "bashkar_station.spec"

# C:\Users\<alguien>\... y /home/<alguien>/..., en cualquiera de las dos barras
_RE_RUTA_DE_USUARIO = re.compile(
    r"[A-Za-z]:[\/]+Users[\/]+|/home/|/Users/", re.IGNORECASE)


def test_el_spec_existe():
    assert SPEC.exists(), f"no encuentro {SPEC}"


def test_sin_rutas_absolutas_de_usuario():
    lineas = SPEC.read_text(encoding="utf-8").splitlines()
    culpables = [
        f"{n}: {linea.strip()}"
        for n, linea in enumerate(lineas, 1)
        # Los comentarios sí pueden nombrar la ruta vieja para explicar el bug.
        if not linea.strip().startswith("#") and _RE_RUTA_DE_USUARIO.search(linea)
    ]
    assert not culpables, (
        "el .spec tiene rutas de una maquina concreta y no compilara en otra:\n"
        + "\n".join(culpables))


def test_el_diccionario_se_resuelve_en_tiempo_de_build():
    fuente = SPEC.read_text(encoding="utf-8")
    assert "_datas_diccionario_es" in fuente, (
        "el diccionario Hunspell debe resolverse con una funcion en tiempo de "
        "build, no cablearse")
    assert "*_datas_dic_es" in fuente
