"""tests/test_identidad_articulo.py — Contrato A1: identidad de artículo.

El bug que motiva el módulo: `articulos.id` es TEXT PRIMARY KEY y
`guardar_articulo` inserta con ON CONFLICT DO UPDATE. Con el título como id, dos
artículos homónimos se pisaban en silencio. Medido sobre el corpus real de
Proyecto_04: 138 filas, 117 títulos distintos, 21 artículos perdidos.
"""
import sqlite3

import pytest

from core.identidad_articulo import (
    SIN_NUMERO,
    asignar_ids,
    id_articulo,
    primera_pagina,
    slug_numero,
)


# ── Forma del id ─────────────────────────────────────────────────────────────

def test_forma_del_id():
    assert id_articulo("rev_estampa_mar_1939", "[17]", 2) == \
        "rev_estampa_mar_1939_p0017_02"


def test_id_es_seguro_como_identificador():
    """Se usa como xml:id en TEI y como nombre en rutas: solo [a-z0-9_]."""
    generado = id_articulo("Páginas desde/rev Estampa (marzo 1939)", "[3, 4]", 1)
    assert generado.replace("_", "").isalnum()
    assert generado.islower()


def test_numero_vacio_no_produce_id_vacio():
    assert id_articulo("", "[1]", 1).startswith(SIN_NUMERO)
    assert id_articulo(None, "[1]", 1).startswith(SIN_NUMERO)


def test_orden_invalido_se_acota_a_uno():
    assert id_articulo("num", "[1]", 0).endswith("_01")
    assert id_articulo("num", "[1]", -5).endswith("_01")


# ── Normalización del número ─────────────────────────────────────────────────

def test_tildes_se_quitan_no_se_convierten_en_separador():
    """El campo `numero` real trae basura de OCR con tildes; una tilde no debe
    partir el id ni hacer que la misma cadena acentuada de dos formas difiera."""
    assert slug_numero("Páginas desde") == "paginas_desde"
    assert slug_numero("Paginas desde") == "paginas_desde"


def test_numero_solo_de_simbolos_cae_al_valor_declarado():
    assert slug_numero("///---") == SIN_NUMERO


# ── Lectura de la página ─────────────────────────────────────────────────────

@pytest.mark.parametrize("entrada,esperado", [
    ("[1]", 1),
    ("[3, 4, 5, 6]", 3),
    ("17", 17),
    (17, 17),
    ([9, 10], 9),
    ("pagina 42", 42),
])
def test_primera_pagina_de_las_formas_reales(entrada, esperado):
    """La columna `paginas` llega como repr de lista porque la escribe pandas."""
    assert primera_pagina(entrada) == esperado


@pytest.mark.parametrize("entrada", ["", None, "sin numero", [], "[]"])
def test_pagina_ilegible_da_cero_detectable(entrada):
    """0 es una página imposible: el fallo queda visible, no disfrazado."""
    assert primera_pagina(entrada) == 0


def test_booleano_no_se_cuela_como_pagina():
    """True es int en Python; sería la página 1 sin querer."""
    assert primera_pagina(True) == 0


# ── Lo que motiva el contrato: colisiones ────────────────────────────────────

def _corpus_con_titulos_repetidos():
    """Reproduce el patrón real: cabeceras fijas que se repiten en la revista."""
    return [
        {"numero": "rev_estampa_mar_1939", "paginas": "[1]",
         "titulo": "Especial para ESTAMPA"},
        {"numero": "rev_estampa_mar_1939", "paginas": "[1]",
         "titulo": "Especial para ESTAMPA"},
        {"numero": "rev_estampa_mar_1939", "paginas": "[1]",
         "titulo": "Especial para ESTAMPA"},
        {"numero": "rev_estampa_mar_1939", "paginas": "[7]",
         "titulo": "A cargo de COLETTE."},
        {"numero": "rev_estampa_mar_1939", "paginas": "[7]",
         "titulo": "A cargo de COLETTE."},
    ]


def test_articulos_homonimos_en_la_misma_pagina_reciben_ids_distintos():
    ids = asignar_ids(_corpus_con_titulos_repetidos())
    assert len(set(ids)) == len(ids) == 5


def test_el_titulo_no_participa_en_el_id():
    """Si el título entrara en el id, cambiar el OCR del título rompería el
    enlace de todas las entidades ya anotadas de ese artículo."""
    a = id_articulo("num", "[5]", 1)
    b = id_articulo("num", "[5]", 1)
    assert a == b


def test_ningun_articulo_se_pierde_al_guardarlos_con_estos_ids(tmp_path):
    """Prueba del daño real: con el título como id se perdían filas por
    ON CONFLICT DO UPDATE. Con el contrato, entran los 5."""
    db = tmp_path / "p.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE articulos (id TEXT PRIMARY KEY, titulo TEXT)")
    filas = _corpus_con_titulos_repetidos()

    for fila, art_id in zip(filas, asignar_ids(filas)):
        con.execute(
            "INSERT INTO articulos (id, titulo) VALUES (?,?) "
            "ON CONFLICT(id) DO UPDATE SET titulo=excluded.titulo",
            (art_id, fila["titulo"]))
    con.commit()

    assert con.execute("SELECT COUNT(*) FROM articulos").fetchone()[0] == 5


def test_el_esquema_viejo_si_perdia_articulos(tmp_path):
    """Contraprueba: el mismo corpus con el título como id pierde 3 de 5.
    Sin esto, el test de arriba no demuestra que hubiera un problema."""
    db = tmp_path / "viejo.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE articulos (id TEXT PRIMARY KEY, titulo TEXT)")

    for fila in _corpus_con_titulos_repetidos():
        con.execute(
            "INSERT INTO articulos (id, titulo) VALUES (?,?) "
            "ON CONFLICT(id) DO UPDATE SET titulo=excluded.titulo",
            (fila["titulo"], fila["titulo"]))
    con.commit()

    assert con.execute("SELECT COUNT(*) FROM articulos").fetchone()[0] == 2


# ── Estabilidad entre corridas ───────────────────────────────────────────────

def test_reprocesar_el_mismo_corpus_da_los_mismos_ids():
    """Es la propiedad que permite reprocesar sin perder anotaciones."""
    filas = _corpus_con_titulos_repetidos()
    assert asignar_ids(filas) == asignar_ids(list(filas))


def test_el_id_no_depende_de_la_posicion_global():
    """Un artículo insertado antes no debe renumerar a los de otras páginas —
    con un contador global (art_0000, art_0001...) sí pasaba."""
    filas = _corpus_con_titulos_repetidos()
    nuevo = [{"numero": "rev_estampa_mar_1939", "paginas": "[3]",
              "titulo": "Nuevo"}] + filas

    ids_antes = asignar_ids(filas)
    ids_despues = asignar_ids(nuevo)[1:]

    assert ids_antes == ids_despues
