"""Persistencia de entidades NER al guardar y reabrir un proyecto.

Fallo 1 del diagnóstico MVP (14-nov-2026): guardar_proyecto() llamaba a
Repositorio.guardar_entidades() —que reemplaza TODAS las entidades del
artículo— una vez por cada entidad. En SQLite sobrevivía una sola entidad por
artículo: 5 de 161 en la muestra real de Estampa (abril de 1939), y el grafo
canónico se construía sobre esas 5.

Se mide con el índice NER real de esa muestra (tests/fixtures/).
"""
import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "ner_estampa_abr1939_muestra.json"


@pytest.fixture
def dir_proyectos(tmp_path, monkeypatch):
    import core.project_manager as pm
    from core import user_prefs
    monkeypatch.setattr(pm, "_dir_proyectos", lambda: tmp_path)
    monkeypatch.setattr(user_prefs, "CREDENCIALES_PATH",
                        tmp_path / "home" / "credenciales.json")
    return tmp_path


@pytest.fixture
def muestra():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _unicas(indice: dict) -> int:
    return sum(len(ents) for ents in indice.values() if isinstance(ents, dict))


def _pares(indice: dict) -> int:
    return sum(len(arts) for ents in indice.values() if isinstance(ents, dict)
               for arts in ents.values())


def _estado_con(muestra) -> object:
    from core.estado import Estado
    st = Estado()
    st.df_articulos = pd.DataFrame(muestra["articulos"])
    st.articulos = list(muestra["articulos"])
    st.indice_ner_global = muestra["indice_ner_global"]
    return st


def _db_de(ruta_bashkar: Path) -> str:
    datos = json.loads(ruta_bashkar.read_text(encoding="utf-8"))
    return datos["db"]


def test_la_muestra_tiene_161_entidades_y_169_pares(muestra):
    # Cifras de referencia medidas en el recorrido real del 14-nov-2026.
    assert _unicas(muestra["indice_ner_global"]) == 161
    assert _pares(muestra["indice_ner_global"]) == 169


def test_guardar_y_reabrir_conserva_todas_las_entidades_en_sqlite(dir_proyectos, muestra):
    from core.project_manager import guardar_proyecto, nuevo_proyecto
    ruta = nuevo_proyecto("Persistencia NER", "Estampa", "abril 1939")
    guardar_proyecto(ruta, _estado_con(muestra))

    con = sqlite3.connect(_db_de(ruta))
    try:
        unicas = con.execute(
            "SELECT COUNT(*) FROM (SELECT DISTINCT categoria, texto FROM entidades)"
        ).fetchone()[0]
        pares = con.execute(
            "SELECT COUNT(*) FROM (SELECT DISTINCT categoria, texto, articulo_id "
            "FROM entidades)").fetchone()[0]
        filas = con.execute("SELECT COUNT(*) FROM entidades").fetchone()[0]
    finally:
        con.close()
    assert unicas == 161
    assert pares == 169
    assert filas == 169, "no debe haber filas duplicadas"


def test_guardar_dos_veces_no_duplica_ni_pierde(dir_proyectos, muestra):
    from core.project_manager import guardar_proyecto, nuevo_proyecto
    ruta = nuevo_proyecto("Persistencia NER x2", "Estampa", "abril 1939")
    st = _estado_con(muestra)
    guardar_proyecto(ruta, st)
    guardar_proyecto(ruta, st)
    con = sqlite3.connect(_db_de(ruta))
    try:
        filas = con.execute("SELECT COUNT(*) FROM entidades").fetchone()[0]
    finally:
        con.close()
    assert filas == 169


def test_reabrir_recupera_el_indice_completo(dir_proyectos, muestra):
    from core.estado import Estado
    from core.project_manager import cargar_proyecto, guardar_proyecto, nuevo_proyecto
    ruta = nuevo_proyecto("Persistencia NER reabrir", "Estampa", "abril 1939")
    guardar_proyecto(ruta, _estado_con(muestra))
    st2 = Estado()
    assert cargar_proyecto(ruta, st2)["ok"]
    assert _unicas(st2.indice_ner_global) == 161
    assert _pares(st2.indice_ner_global) == 169
