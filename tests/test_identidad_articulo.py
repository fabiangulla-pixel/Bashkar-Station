"""tests/test_identidad_articulo.py — Contrato A1: identidad de artículo.

El bug que motiva el módulo: `articulos.id` es TEXT PRIMARY KEY y
`guardar_articulo` inserta con ON CONFLICT DO UPDATE. Con el título como id, dos
artículos homónimos se pisaban en silencio. Medido sobre el corpus real de
Proyecto_04: 138 filas, 117 títulos distintos, 21 artículos perdidos.
"""
import sqlite3

import pytest

from core import identidad_articulo as ia
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


# ── rango_paginas: la deriva que dejaba pagina_inicio/pagina_fin en NULL ─────

class TestRangoPaginas:
    """`pipeline_maestro` pedía `pagina_inicio`/`pagina_fin` al artículo, y el
    segmentador nunca ha puesto esas claves: entrega `pagina` con el rango
    dentro. Medido sobre el proyecto real de Estampa, las 351 filas de
    `articulos` tienen las dos columnas en NULL. Nada falla; solo se pierde el
    dato, y con él el orden de lectura y la página en el id del contrato A1."""

    def test_rango_del_formato_que_produce_el_segmentador(self):
        # article_segmenter.py: f"{pagina_ini}-{pagina_fin}"
        assert ia.rango_paginas({"pagina": "17-18"}) == (17, 18)

    def test_rango_del_formato_con_ceros_y_guion_largo(self):
        # article_segmenter.py: f"p{curr['pi']:04d}–p{pf:04d}"
        assert ia.rango_paginas({"pagina": "p0017–p0018"}) == (17, 18)

    def test_articulo_de_una_sola_pagina(self):
        assert ia.rango_paginas({"pagina": "p0007"}) == (7, 7)

    def test_los_valores_explicitos_mandan_sobre_el_rango(self):
        art = {"pagina": "17-18", "pagina_inicio": 3, "pagina_fin": 4}
        assert ia.rango_paginas(art) == (3, 4)

    def test_pagina_inicio_explicita_y_fin_derivada(self):
        assert ia.rango_paginas({"pagina": "17-18", "pagina_inicio": 17}) == (17, 18)

    def test_sin_dato_ninguno_da_cero_no_revienta(self):
        assert ia.rango_paginas({}) == (0, 0)
        assert ia.rango_paginas({"pagina": ""}) == (0, 0)
        assert ia.rango_paginas({"pagina": None}) == (0, 0)

    def test_fin_menor_que_inicio_se_corrige(self):
        """Un rango invertido no puede producir un fin anterior al inicio."""
        assert ia.rango_paginas({"pagina_inicio": 18, "pagina_fin": 3}) == (18, 18)

    def test_lista_real_de_paginas(self):
        assert ia.rango_paginas({"pagina": [3, 4, 5]}) == (3, 5)

    def test_repr_de_lista_como_lo_escribe_pandas(self):
        assert ia.rango_paginas({"pagina": "[3, 4, 5]"}) == (3, 5)


class TestUltimaPagina:
    def test_entero(self):
        assert ia.ultima_pagina(7) == 7

    def test_rango_en_cadena(self):
        assert ia.ultima_pagina("17-18") == 18

    def test_lista(self):
        assert ia.ultima_pagina([3, 4, 5]) == 5

    def test_ilegible_da_cero_detectable(self):
        assert ia.ultima_pagina("sin página") == 0

    def test_booleano_no_cuenta_como_entero(self):
        assert ia.ultima_pagina(True) == 0
