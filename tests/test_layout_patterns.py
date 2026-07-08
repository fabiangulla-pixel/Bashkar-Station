"""tests/test_layout_patterns.py — cabeceras repetidas, capitulares, pie↔foto,
y retro-compatibilidad de Zona con JSON antiguo (sin zid/vinculo)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import layout_patterns as lp  # noqa: E402
from core.zone_labeler import PaginaEtiquetada, Zona  # noqa: E402


# ── Zona: zid autogenerado + retro-compat ────────────────────────────────────

def test_zona_autogenera_zid():
    z = Zona(tipo="articulo", x0=0, y0=0, x1=1, y1=1)
    assert z.zid and len(z.zid) == 8


def test_zonas_distintas_tienen_zid_distinto():
    a = Zona(tipo="articulo", x0=0, y0=0, x1=1, y1=1)
    b = Zona(tipo="articulo", x0=0, y0=0, x1=1, y1=1)
    assert a.zid != b.zid


def test_zona_respeta_zid_explicito():
    z = Zona(tipo="foto", x0=0, y0=0, x1=1, y1=1, zid="abc12345")
    assert z.zid == "abc12345"


def test_pagina_etiquetada_from_dict_json_antiguo_sin_zid():
    # JSON de una sesión anterior a esta feature: sin "zid" ni "vinculo".
    d = {
        "pagina": "p0001", "ancho_px": 1000, "alto_px": 1400, "manual": True,
        "zonas": [{"tipo": "articulo", "x0": 0.1, "y0": 0.1, "x1": 0.5, "y1": 0.5,
                   "confianza": 1.0, "notas": "", "orden": 1}],
    }
    pag = PaginaEtiquetada.from_dict(d)
    assert pag.zonas[0].zid  # se autogeneró al reconstruir
    assert pag.zonas[0].vinculo is None


def test_dividir_zona_produce_zids_nuevos():
    from core.zone_labeler import dividir_zona
    original = Zona(tipo="articulo", x0=0, y0=0, x1=1, y1=1)
    a, b = dividir_zona(original, eje="v", frac=0.5)
    assert a.zid != original.zid
    assert b.zid != original.zid
    assert a.zid != b.zid


# ── detectar_cabeceras_repetidas ─────────────────────────────────────────────

def _cabecera(x0=0.1, y0=0.02, x1=0.9, y1=0.08):
    return Zona(tipo="cabecera", x0=x0, y0=y0, x1=x1, y1=y1)


def test_detecta_cabecera_repetida_en_3_de_5_paginas():
    paginas = [
        [_cabecera()], [_cabecera()], [], [_cabecera()],
        [Zona(tipo="articulo", x0=0.1, y0=0.5, x1=0.9, y1=0.9)],
    ]
    grupos = lp.detectar_cabeceras_repetidas(paginas, min_repeticiones=3)
    assert len(grupos) == 1
    (paginas_del_grupo,) = grupos.values()
    assert paginas_del_grupo == [0, 1, 3]


def test_no_detecta_si_no_alcanza_el_minimo():
    paginas = [[_cabecera()], [_cabecera()], []]
    grupos = lp.detectar_cabeceras_repetidas(paginas, min_repeticiones=3)
    assert grupos == {}


def test_bbox_distinto_no_se_agrupa():
    paginas = [[_cabecera(x0=0.1)], [_cabecera(x0=0.1)], [_cabecera(x0=0.6)]]
    grupos = lp.detectar_cabeceras_repetidas(paginas, min_repeticiones=2)
    valores = list(grupos.values())
    assert [0, 1] in valores
    assert [0, 1, 2] not in valores


def test_texto_distinto_no_confirma_misma_cabecera():
    paginas = [[_cabecera()], [_cabecera()], [_cabecera()]]
    textos = [{0: "ESTAMPA"}, {0: "ESTAMPA"}, {0: "OTRA REVISTA DISTINTA"}]
    grupos = lp.detectar_cabeceras_repetidas(paginas, min_repeticiones=3, textos=textos)
    assert grupos == {}  # solo 2 con texto igual, no llega al mínimo de 3


# ── detectar_capitulares ─────────────────────────────────────────────────────

def _data_tesseract(palabras: list[tuple[str, int, int, int, int, int]]):
    """palabras: lista de (texto, alto, x, y, w, line_num)."""
    return {
        "text": [p[0] for p in palabras],
        "height": [p[1] for p in palabras],
        "left": [p[2] for p in palabras],
        "top": [p[3] for p in palabras],
        "width": [p[4] for p in palabras],
        "line_num": [p[5] for p in palabras],
    }


def test_detecta_capitular_por_altura():
    data = _data_tesseract([
        ("C", 40, 10, 10, 30, 0),       # capitular: 40 vs mediana ~20
        ("uando", 20, 45, 15, 60, 0),
        ("el", 20, 10, 40, 20, 1),
        ("lector", 20, 35, 40, 40, 1),
    ])
    capitulares = lp.detectar_capitulares(data, factor_altura=1.8)
    assert len(capitulares) == 1
    assert capitulares[0]["texto"] == "C"


def test_no_detecta_capitular_si_alturas_uniformes():
    data = _data_tesseract([
        ("el", 20, 10, 10, 20, 0),
        ("lector", 20, 35, 10, 40, 0),
        ("llega", 20, 10, 40, 30, 1),
    ])
    assert lp.detectar_capitulares(data) == []


def test_no_detecta_capitular_en_palabra_de_mas_de_una_letra():
    data = _data_tesseract([
        ("EL", 45, 10, 10, 30, 0),  # 2 letras, aunque sea alta no es "drop cap" de 1 glifo
        ("resto", 20, 10, 40, 40, 1),
    ])
    assert lp.detectar_capitulares(data) == []


def test_data_tesseract_vacio_no_lanza():
    assert lp.detectar_capitulares(_data_tesseract([])) == []


# ── asociar_pies_fotos ───────────────────────────────────────────────────────

def test_asocia_pie_con_foto_debajo():
    foto = Zona(tipo="foto", x0=0.1, y0=0.1, x1=0.5, y1=0.4)
    pie = Zona(tipo="pie_foto", x0=0.1, y0=0.41, x1=0.5, y1=0.45)
    pares = lp.asociar_pies_fotos([foto, pie])
    assert pares == [(pie.zid, foto.zid)]
    assert pie.vinculo == foto.zid


def test_no_asocia_si_no_hay_solapamiento_horizontal():
    foto = Zona(tipo="foto", x0=0.1, y0=0.1, x1=0.5, y1=0.4)
    pie = Zona(tipo="pie_foto", x0=0.6, y0=0.41, x1=0.9, y1=0.45)
    pares = lp.asociar_pies_fotos([foto, pie])
    assert pares == []
    assert pie.vinculo is None


def test_no_asocia_si_esta_muy_lejos_verticalmente():
    foto = Zona(tipo="foto", x0=0.1, y0=0.1, x1=0.5, y1=0.4)
    pie = Zona(tipo="pie_foto", x0=0.1, y0=0.6, x1=0.5, y1=0.65)
    pares = lp.asociar_pies_fotos([foto, pie])
    assert pares == []


def test_sin_fotos_no_lanza():
    pie = Zona(tipo="pie_foto", x0=0.1, y0=0.41, x1=0.5, y1=0.45)
    assert lp.asociar_pies_fotos([pie]) == []
