"""tests/test_colaboracion.py — Regresión: crear_parche() vs esquema real .bashkar.

En proyectos reales (post-migración a SQLite), el índice NER vive anidado
en resultados.indice_ner_global, no en la raíz del dict .bashkar. app.py
construye el "estado modificado" copiando ST.indice_ner_global a la raíz
(actual_mod["indice_ner_global"] = ST.indice_ner_global) pero el archivo
.bashkar original en disco NUNCA tiene esa clave en la raíz. Antes del fix,
crear_parche() comparaba raíz-vs-raíz y reportaba TODAS las entidades reales
como "agregadas" incluso sin ningún cambio del investigador.
"""
import copy

from core.colaboracion import crear_parche


def _proyecto_real_minimo():
    """Reproduce la forma real de un .bashkar procesado (ver Proyecto_04_Mar_2026)."""
    return {
        "version": "12.3",
        "nombre": "Proyecto Test",
        "resultados": {
            "indice_ner_global": {
                "personas": {"Simón Bolívar": ["art_1", "art_2"]},
                "lugares": {"Bogotá": ["art_1"]},
            }
        },
    }


def test_crear_parche_sin_cambios_reales_no_reporta_falsos_agregados():
    """Bug real: sin ningún cambio del usuario, el parche no debe mostrar
    entidades existentes como 'agregadas'."""
    original = _proyecto_real_minimo()

    # Esto es exactamente lo que hace app.py._colab_exportar_worker:
    # copiar el índice NER actual (cargado en ST desde resultados.*) a la raíz
    # del dict "modificado" antes de diffear.
    ner_actual = original["resultados"]["indice_ner_global"]
    modificado = dict(original)
    modificado["indice_ner_global"] = ner_actual

    parche = crear_parche(original, modificado, "investigador_test", "sin cambios")

    cambios_ner = parche["cambios"].get("ner", {})
    total_agregadas = sum(len(v.get("agregadas", {})) for v in cambios_ner.values())
    assert total_agregadas == 0, (
        f"Se reportaron {total_agregadas} entidades falsamente como nuevas "
        "sin que el investigador hiciera ningún cambio real."
    )


def test_crear_parche_detecta_entidad_nueva_real():
    """El fix no debe romper la detección de cambios reales."""
    original = _proyecto_real_minimo()
    modificado = copy.deepcopy(original)
    modificado["resultados"]["indice_ner_global"]["personas"]["Nueva Entidad"] = ["art_9"]
    modificado["indice_ner_global"] = modificado["resultados"]["indice_ner_global"]

    parche = crear_parche(original, modificado, "investigador_test", "un cambio real")

    agregadas = parche["cambios"]["ner"]["personas"]["agregadas"]
    assert "Nueva Entidad" in agregadas
    assert "Simón Bolívar" not in agregadas


# ── Correcciones manuales de OCR en proyectos v11 ────────────────────────────
#
# En v11 el texto NO está en el dict: las correcciones que el investigador hace
# a mano viven en la tabla `normalizaciones` del SQLite hermano. crear_parche()
# solo miraba artículos embebidos en el dict, así que un parche de un proyecto
# real salía SIEMPRE sin una sola corrección de OCR: el trabajo manual (169
# páginas corregidas en Proyecto_04) no era compartible.

import sqlite3

from core.colaboracion import aplicar_parche
from datos.schema import SCHEMA_NORMALIZACIONES


def _proyecto_v11(tmp_path, nombre, correcciones):
    """Proyecto con SQLite hermano y correcciones manuales de OCR."""
    db = tmp_path / f"{nombre}.db"
    con = sqlite3.connect(db)
    con.executescript(SCHEMA_NORMALIZACIONES)
    for numero, pagina, crudo, usuario, ts in correcciones:
        con.execute(
            "INSERT INTO normalizaciones "
            "(numero, pagina, ocr_crudo, norm_usuario, ts_usuario) "
            "VALUES (?,?,?,?,?)", (numero, pagina, crudo, usuario, ts))
    con.commit()
    con.close()
    return {"nombre": nombre, "db": str(db),
            "resultados": {"indice_ner_global": {}}}


def _norm_usuario(proyecto, numero, pagina):
    con = sqlite3.connect(proyecto["db"])
    fila = con.execute(
        "SELECT norm_usuario FROM normalizaciones WHERE numero=? AND pagina=?",
        (numero, pagina)).fetchone()
    con.close()
    return fila[0] if fila else None


def test_parche_v11_incluye_correcciones_manuales_de_ocr(tmp_path):
    emisor = _proyecto_v11(tmp_path, "emisor", [
        ("Estampa 17", "p0001-01", "Bogota", "Bogotá", "2026-06-02T19:15:55"),
        ("Estampa 17", "p0001-04", "1a Republiea", "la República",
         "2026-06-02T19:16:10"),
    ])
    receptor = _proyecto_v11(tmp_path, "receptor", [
        ("Estampa 17", "p0001-01", "Bogota", "", ""),
        ("Estampa 17", "p0001-04", "1a Republiea", "", ""),
    ])

    parche = crear_parche(receptor, emisor, "Fabián")

    assert len(parche["cambios"]["normalizaciones"]) == 2


def test_parche_v11_solo_lleva_lo_que_el_usuario_cambio(tmp_path):
    """Una fila cuya normalización coincide con el crudo no es aporte alguno."""
    emisor = _proyecto_v11(tmp_path, "emisor", [
        ("Estampa 17", "p0001-01", "Bogotá", "Bogotá", "2026-06-02T19:15:55"),
        ("Estampa 17", "p0001-04", "Republiea", "República",
         "2026-06-02T19:16:10"),
    ])
    receptor = _proyecto_v11(tmp_path, "receptor", [])

    parche = crear_parche(receptor, emisor, "Fabián")

    assert list(parche["cambios"]["normalizaciones"]) == ["Estampa 17||p0001-04"]


def test_aplicar_parche_escribe_las_correcciones_en_el_sqlite(tmp_path):
    emisor = _proyecto_v11(tmp_path, "emisor", [
        ("Estampa 17", "p0001-04", "Republiea", "República",
         "2026-06-02T19:16:10"),
    ])
    receptor = _proyecto_v11(tmp_path, "receptor", [
        ("Estampa 17", "p0001-04", "Republiea", "", ""),
    ])

    resultado = aplicar_parche(receptor, crear_parche(receptor, emisor, "F"))

    assert _norm_usuario(receptor, "Estampa 17", "p0001-04") == "República"
    assert resultado["_contribuciones"][-1]["n_cambios_normalizacion"] == 1


def test_aplicar_parche_es_idempotente(tmp_path):
    """Reaplicar el mismo parche no vuelve a contar ni pisa nada."""
    emisor = _proyecto_v11(tmp_path, "emisor", [
        ("Estampa 17", "p0001-04", "Republiea", "República",
         "2026-06-02T19:16:10"),
    ])
    receptor = _proyecto_v11(tmp_path, "receptor", [
        ("Estampa 17", "p0001-04", "Republiea", "", ""),
    ])
    parche = crear_parche(receptor, emisor, "F")

    aplicar_parche(receptor, parche)
    segunda = aplicar_parche(receptor, parche)

    assert segunda["_contribuciones"][-1]["n_cambios_normalizacion"] == 0


def test_correccion_local_mas_reciente_no_se_pisa(tmp_path):
    """El receptor ya corrigió esa página después: su versión debe sobrevivir."""
    emisor = _proyecto_v11(tmp_path, "emisor", [
        ("Estampa 17", "p0001-04", "Republiea", "República",
         "2026-06-02T10:00:00"),
    ])
    receptor = _proyecto_v11(tmp_path, "receptor", [
        ("Estampa 17", "p0001-04", "Republiea", "la República",
         "2026-06-03T10:00:00"),
    ])

    aplicar_parche(receptor, crear_parche(receptor, emisor, "F"))

    assert _norm_usuario(receptor, "Estampa 17", "p0001-04") == "la República"


def test_estrategia_manual_no_pisa_correcciones_del_receptor(tmp_path):
    emisor = _proyecto_v11(tmp_path, "emisor", [
        ("Estampa 17", "p0001-04", "Republiea", "República",
         "2026-06-09T10:00:00"),
    ])
    receptor = _proyecto_v11(tmp_path, "receptor", [
        ("Estampa 17", "p0001-04", "Republiea", "mi versión",
         "2026-06-02T10:00:00"),
    ])

    aplicar_parche(receptor, crear_parche(receptor, emisor, "F"),
                   estrategia_conflicto="manual")

    assert _norm_usuario(receptor, "Estampa 17", "p0001-04") == "mi versión"


def test_receptor_sin_tabla_normalizaciones_recibe_el_parche(tmp_path):
    """Un proyecto que nunca pasó por el panel de Normalizar no tiene la tabla."""
    emisor = _proyecto_v11(tmp_path, "emisor", [
        ("Estampa 17", "p0001-04", "Republiea", "República",
         "2026-06-02T10:00:00"),
    ])
    db = tmp_path / "virgen.db"
    sqlite3.connect(db).close()
    receptor = {"nombre": "virgen", "db": str(db), "resultados": {}}

    aplicar_parche(receptor, crear_parche(receptor, emisor, "F"))

    assert _norm_usuario(receptor, "Estampa 17", "p0001-04") == "República"


def test_sin_sqlite_localizable_no_reporta_exito_falso(tmp_path):
    """Si no se ubica la base, se avisa y se cuenta 0 — no se finge que se aplicó."""
    emisor = _proyecto_v11(tmp_path, "emisor", [
        ("Estampa 17", "p0001-04", "Republiea", "República",
         "2026-06-02T10:00:00"),
    ])
    parche = crear_parche({"nombre": "x"}, emisor, "F")
    avisos = []

    resultado = aplicar_parche({"nombre": "sin_db"}, parche,
                               callback=avisos.append)

    assert resultado["_contribuciones"][-1]["n_cambios_normalizacion"] == 0
    assert any("NO aplicadas" in a for a in avisos)


def test_db_relativa_se_resuelve_contra_la_ruta_del_bashkar(tmp_path):
    """Proyectos migrados por versiones viejas guardaron "db" como nombre pelado."""
    emisor = _proyecto_v11(tmp_path, "emisor", [
        ("Estampa 17", "p0001-04", "Republiea", "República",
         "2026-06-02T10:00:00"),
    ])
    emisor["db"] = "emisor.db"
    emisor["_ruta"] = str(tmp_path / "emisor.bashkar")

    parche = crear_parche({"nombre": "x"}, emisor, "F")

    assert len(parche["cambios"]["normalizaciones"]) == 1


# ── Truncamiento del texto OCR embebido (v10) ────────────────────────────────

def test_parche_ocr_no_trunca_el_texto_del_articulo():
    """El parche guardaba solo 200 caracteres y aplicar_parche escribía ese
    recorte como texto completo: el resto del artículo se perdía."""
    largo = "Bogotá, capital de la República. " * 40
    original = {"articulos": {"art_1": {"texto_limpio": "crudo"}}}
    modificado = {"articulos": {"art_1": {"texto_limpio": largo}}}

    resultado = aplicar_parche(original, crear_parche(original, modificado, "F"))

    assert resultado["articulos"]["art_1"]["texto_limpio"] == largo


# ── Hash de validación ───────────────────────────────────────────────────────

def test_hash_base_ignora_claves_privadas():
    """"_ruta" es contexto del equipo, no del documento: el MISMO proyecto debía
    dar el mismo hash abierto desde otra máquina."""
    base = _proyecto_real_minimo()
    desde_otro_pc = dict(base, _ruta="D:/otra/ruta/proyecto.bashkar")

    a = crear_parche(base, base, "F")["_hash_base"]
    b = crear_parche(desde_otro_pc, desde_otro_pc, "F")["_hash_base"]

    assert a == b
