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
