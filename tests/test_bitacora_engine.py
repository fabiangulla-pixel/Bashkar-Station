"""tests/test_bitacora_engine.py — Tests de BitacoraEngine.

Incluye regresión de un bug real: exportar_markdown() usaba
datetime.strftime("%d de %B de %Y"), cuyo nombre de mes depende del
locale del sistema. En Windows sin locale español configurado (el caso
real de la máquina de desarrollo), esto produce fechas mixtas como
"02 de September de 2026" en un documento en español destinado a
apéndice de paper académico.
"""
import sqlite3

import pytest

from core.bitacora_engine import BitacoraEngine, _fecha_es
from datetime import datetime


@pytest.fixture
def engine(tmp_path):
    db = tmp_path / "proyecto.db"
    return BitacoraEngine(str(db))


def test_fecha_es_no_depende_del_locale():
    """Regresión: los meses deben salir siempre en español, sin importar
    el locale del sistema operativo."""
    dt = datetime(2026, 9, 2)
    assert _fecha_es(dt) == "02 de septiembre de 2026"
    assert "September" not in _fecha_es(dt)


def test_exportar_markdown_fecha_en_espanol(engine, tmp_path):
    engine.insertar({"tipo": "libre", "texto": "nota de prueba"})
    ruta = engine.exportar_markdown(tmp_path / "bitacora.md", "Estampa 1939")
    contenido = ruta.read_text(encoding="utf-8")
    assert "September" not in contenido
    assert "**Exportado:**" in contenido


def test_insertar_listar_contar(engine):
    engine.insertar({
        "tipo": "hipotesis", "estado": "abierta",
        "texto": "Las noticias de deportes aumentan en verano",
        "etiquetas": ["deportes", "temporalidad"],
        "ref_numero": "enero_1939", "ref_pagina": "p0042",
        "modulo_origen": "anal",
    })
    engine.insertar({"tipo": "cita", "texto": "cita textual", "ref_numero": "febrero_1939"})
    engine.insertar({"tipo": "libre", "texto": "nota libre"})

    conteo = engine.contar()
    assert conteo["total"] == 3
    assert conteo["por_tipo"] == {"hipotesis": 1, "cita": 1, "libre": 1}
    assert conteo["por_estado"] == {"abierta": 1}

    hipotesis = engine.listar(tipo="hipotesis")
    assert len(hipotesis) == 1
    assert hipotesis[0]["etiquetas"] == ["deportes", "temporalidad"]


def test_exportar_markdown_agrupa_por_seccion(engine, tmp_path):
    engine.insertar({"tipo": "hipotesis", "estado": "abierta", "texto": "H1"})
    engine.insertar({"tipo": "hipotesis", "estado": "confirmada", "texto": "H2"})
    engine.insertar({"tipo": "cita", "texto": "C1"})
    engine.insertar({"tipo": "libre", "texto": "L1"})

    ruta = engine.exportar_markdown(tmp_path / "bitacora.md", "Estampa 1939")
    contenido = ruta.read_text(encoding="utf-8")

    assert "## \U0001F4A1 Hipótesis de investigación" in contenido
    assert "## \U0001F4CC Citas del corpus" in contenido
    assert "## \U0001F4DD Notas libres" in contenido
    assert contenido.index("Abierta") < contenido.index("Confirmada")
