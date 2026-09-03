"""tests/test_comparador.py — Regresión: comparar_entidades() vs esquema real .bashkar.

Bug real: en proyectos .bashkar reales (post-migración a SQLite) el índice
NER vive anidado en resultados.indice_ner_global, nunca en la raíz del
dict. comparador.comparar_entidades() leía solo la raíz
(p.get("indice_ner_global")), así que para CUALQUIER par de proyectos
reales el índice cargado siempre era {} y la comparativa reportaba
0 entidades comunes y una frecuencia_global vacía sin importar cuántas
entidades reales compartieran los proyectos.
"""
from core.comparador import comparar_entidades


def _proyecto_real(entidades: dict) -> dict:
    """Reproduce la forma real de un .bashkar procesado."""
    return {
        "version": "12.3",
        "nombre": "Proyecto Test",
        "resultados": {"indice_ner_global": entidades},
    }


def test_comparar_entidades_lee_indice_anidado_en_resultados():
    p1 = _proyecto_real({
        "personas": {"Simón Bolívar": ["a1"], "Exclusiva Uno": ["a2"]},
    })
    p2 = _proyecto_real({
        "personas": {"Simón Bolívar": ["b1"], "Exclusiva Dos": ["b2"]},
    })

    resultado = comparar_entidades([p1, p2])

    assert resultado["comunes"] == {"personas": ["Simón Bolívar"]}
    assert resultado["total_comunes"] == 1
    assert "Simón Bolívar" in resultado["frecuencia_global"]


def test_comparar_entidades_raiz_top_level_sigue_funcionando():
    """Compatibilidad: si algún caller sí pone el índice en la raíz
    (como hacía app.py históricamente), debe seguir funcionando."""
    p1 = {"indice_ner_global": {"lugares": {"Bogotá": ["a1"]}}}
    p2 = {"indice_ner_global": {"lugares": {"Bogotá": ["b1"]}}}

    resultado = comparar_entidades([p1, p2])

    assert resultado["comunes"] == {"lugares": ["Bogotá"]}


def test_comparar_entidades_proyectos_vacios_no_crashea():
    resultado = comparar_entidades([{}, {}])
    assert resultado["total_comunes"] == 0
