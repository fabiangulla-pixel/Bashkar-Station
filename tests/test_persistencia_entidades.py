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


# ── Fallo 4: el grafo canónico en un proyecto recién creado ───────────────────
# guardar_proyecto() nunca asignaba st.ruta_db (solo cargar_proyecto lo hacía):
# el panel del grafo respondía «Abre o guarda un proyecto con base de datos»
# aunque el usuario acabara de guardar, hasta cerrar y reabrir.

def test_guardar_un_proyecto_nuevo_deja_lista_la_base_para_el_grafo(dir_proyectos, muestra):
    from core.project_manager import guardar_proyecto, nuevo_proyecto
    from datos.repositorio import Repositorio
    ruta = nuevo_proyecto("Grafo sin reabrir", "Estampa", "abril 1939")
    st = _estado_con(muestra)
    assert not getattr(st, "ruta_db", "")      # como un proyecto recién creado
    guardar_proyecto(ruta, st)
    assert st.ruta_db == _db_de(ruta)
    repo = Repositorio(st.ruta_db)              # lo mismo que hace _can_repo()
    repo.fundir_menciones_en_canonicas(fuente="ner")
    assert len(repo.listar_entidades_canonicas()) >= 150


def test_un_fallo_al_sincronizar_sqlite_queda_registrado(dir_proyectos, muestra, monkeypatch):
    from core import registro_errores
    from core.project_manager import guardar_proyecto, nuevo_proyecto
    from datos.repositorio import Repositorio
    registrados = []
    monkeypatch.setattr(registro_errores, "registrar",
                        lambda msg, exc=None, **k: registrados.append((msg, exc)))

    def _falla(self, *a, **k):
        raise RuntimeError("disco lleno (simulado)")
    monkeypatch.setattr(Repositorio, "reemplazar_entidades_de_fuente", _falla)
    ruta = nuevo_proyecto("Falla SQLite", "Estampa", "abril 1939")
    res = guardar_proyecto(ruta, _estado_con(muestra))
    assert registrados and "disco lleno" in str(registrados[0][1])
    assert res.get("error_sqlite")


# ── A5: una sola fuente para las entidades (la base) ──────────────────────────

def _proyecto_antiguo(dir_proyectos, muestra, nombre):
    """Simula un .bashkar de v13: índice por título en el JSON, base recortada."""
    import sqlite3

    from core.project_manager import nuevo_proyecto
    from datos.repositorio import Repositorio
    ruta = nuevo_proyecto(nombre, "Estampa", "abril 1939")
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    datos.setdefault("resultados", {})["indice_ner_global"] = muestra["indice_ner_global"]
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    carpeta = ruta.with_suffix("")
    carpeta.mkdir(exist_ok=True)
    pd.DataFrame(muestra["articulos"]).to_csv(carpeta / "articulos.csv", index=False)
    repo = Repositorio(datos["db"])
    for a in muestra["articulos"]:                 # como lo dejaba el fallo 1
        repo.guardar_articulo({"id": a["titulo"], "titulo": a["titulo"]})
        repo.guardar_entidades(a["titulo"], [{"texto": "X", "categoria": "personas",
                                              "fuente": "ner_engine"}])
    con = sqlite3.connect(datos["db"])
    assert con.execute("SELECT COUNT(*) FROM entidades").fetchone()[0] == 5
    con.close()
    return ruta


def test_al_reabrir_el_indice_sale_de_la_base(dir_proyectos, muestra):
    from core.estado import Estado
    from core.project_manager import cargar_proyecto, guardar_proyecto, nuevo_proyecto
    from datos.repositorio import Repositorio
    ruta = nuevo_proyecto("Fuente unica", "Estampa", "abril 1939")
    guardar_proyecto(ruta, _estado_con(muestra))
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["resultados"]["entidades_fuente"] == "sqlite"
    # Si alguien toca la base (p. ej. una corrección), al reabrir manda la base.
    Repositorio(datos["db"]).reemplazar_entidades_de_fuente(
        "ner_engine", [{"articulo_id": "a", "texto": "Bogotá", "categoria": "lugares"}])
    st = Estado()
    cargar_proyecto(ruta, st)
    assert st.indice_ner_global["lugares"] == {"Bogotá": ["a"]}


def test_proyecto_antiguo_se_migra_desde_el_json_con_respaldo(dir_proyectos, muestra):
    from core.estado import Estado
    from core.project_manager import cargar_proyecto
    ruta = _proyecto_antiguo(dir_proyectos, muestra, "Antiguo")
    st = Estado()
    res = cargar_proyecto(ruta, st)
    assert res["entidades_migradas"]
    assert _unicas(st.indice_ner_global) == 161 and _pares(st.indice_ner_global) == 169
    ids = set(st.df_articulos["id"])
    assert all(a in ids for ents in st.indice_ner_global.values()
               for arts in ents.values() for a in arts)
    assert list(dir_proyectos.glob("Antiguo.db.respaldo-*")), "falta la copia de la base"


def test_panel_grafo_y_tei_cuentan_lo_mismo(dir_proyectos, muestra, tmp_path):
    from core.estado import Estado
    from core.project_manager import cargar_proyecto
    from core.servicios_exportacion import articulos_para_tei
    from core.tei_engine import contar_entidades_en_tei, exportar_corpus_tei
    from datos.repositorio import Repositorio
    ruta = _proyecto_antiguo(dir_proyectos, muestra, "Cuentas")
    st = Estado()
    cargar_proyecto(ruta, st)
    repo = Repositorio(st.ruta_db)
    repo.fundir_menciones_en_canonicas(fuente="ner")
    panel = _unicas(st.indice_ner_global)
    grafo = len(repo.listar_entidades_canonicas())
    xml = tmp_path / "c.xml"
    arts = articulos_para_tei([""] * 5, st.indice_ner_global, articulos=st.df_articulos)
    exportar_corpus_tei(arts, xml)
    en_tei = contar_entidades_en_tei(xml)
    pares_exportables = sum(len(arts) for ents in st.indice_ner_global.values()
                            for e, arts in ents.items() if len(e.strip()) > 2)
    assert panel == 161
    assert grafo == 161          # antes del arreglo: 5
    assert en_tei == pares_exportables
