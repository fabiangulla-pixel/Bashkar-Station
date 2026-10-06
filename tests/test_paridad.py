"""Paridad escritorio ↔ API (core/operaciones.py).

Si este test falla porque apareció un ``_worker_*`` nuevo en el escritorio:
regístralo en ``core/operaciones.py`` con su ruta en ``api/app.py``, o con
``api=None`` y el motivo. Lo que no vale es que exista solo en un lado sin
que se vea.
"""

import re
from pathlib import Path

import pytest

from core import operaciones

RAIZ = Path(__file__).resolve().parents[1]
_WORKER = re.compile(r"^\s+def (_worker_\w+)\(", re.MULTILINE)


def _workers_escritorio() -> set[str]:
    fuentes = [RAIZ / "app.py", *sorted((RAIZ / "paneles").glob("*.py"))]
    return {m for f in fuentes for m in _WORKER.findall(f.read_text("utf-8"))}


def _rutas_api() -> set[str]:
    from api.app import app
    return {f"{metodo} {r.path}" for r in app.routes for metodo in getattr(r, "methods", ())}


def test_todo_worker_del_escritorio_esta_registrado():
    faltan = _workers_escritorio() - set(operaciones.por_worker())
    assert not faltan, (f"Operaciones del escritorio sin registrar en core/operaciones.py: "
                        f"{sorted(faltan)}")


def test_registro_no_nombra_workers_que_ya_no_existen():
    sobran = set(operaciones.por_worker()) - _workers_escritorio()
    assert not sobran, f"core/operaciones.py nombra workers inexistentes: {sorted(sobran)}"


@pytest.mark.parametrize("op", [o for o in operaciones.OPERACIONES if o.api],
                         ids=lambda o: o.clave)
def test_ruta_declarada_existe_en_la_api(op):
    assert op.api in _rutas_api(), f"{op.clave}: la API no tiene {op.api}"


def test_pendientes_declaran_motivo():
    for op in operaciones.OPERACIONES:
        assert op.api or op.nota, f"{op.clave}: sin ruta y sin motivo"


def test_un_worker_no_esta_en_dos_operaciones():
    vistos = [w for op in operaciones.OPERACIONES for w in op.escritorio]
    assert len(vistos) == len(set(vistos))
