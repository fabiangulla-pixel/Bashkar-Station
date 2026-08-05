"""Tests de la ruta CHURRO por zonas, sin cargar el modelo.

Lo que importa aqui es el CONTRATO: que se salten las zonas sin texto, que se
respete el orden de lectura y que la salida tenga la misma forma que
layout_tesseract.ocr_por_zonas. La inferencia se simula.
"""
import pytest

from core import ocr_churro
from core.zone_labeler import Zona


@pytest.fixture
def pagina_mixta():
    """Pagina tipica de Estampa: articulo, titulo, foto, publicidad, filete."""
    return [
        Zona(tipo="titulo", x0=0.1, y0=0.05, x1=0.9, y1=0.12, orden=1),
        Zona(tipo="foto", x0=0.1, y0=0.15, x1=0.5, y1=0.45, orden=2),
        Zona(tipo="pie_foto", x0=0.1, y0=0.46, x1=0.5, y1=0.49, orden=3),
        Zona(tipo="articulo", x0=0.55, y0=0.15, x1=0.9, y1=0.6, orden=4),
        Zona(tipo="publicidad", x0=0.1, y0=0.65, x1=0.9, y1=0.9, orden=5),
        Zona(tipo="filete", x0=0.1, y0=0.62, x1=0.9, y1=0.63, orden=6),
    ]


@pytest.fixture
def imagen(tmp_path):
    from PIL import Image
    p = tmp_path / "p0001.png"
    Image.new("RGB", (1200, 1600), "white").save(p)
    return p


def test_solo_procesa_las_zonas_con_texto(monkeypatch, pagina_mixta, imagen):
    """foto, publicidad y filete NO deben gastar tokens del modelo."""
    procesadas = []

    def falso_ocr(recorte, **kw):
        procesadas.append(recorte.size)
        return "texto reconocido"

    monkeypatch.setattr(ocr_churro, "ocr_pagina", falso_ocr)
    r = ocr_churro.ocr_pagina_con_zonas(imagen, pagina_mixta)

    # 3 con texto: titulo, pie_foto, articulo
    assert len(procesadas) == 3
    assert [z["tipo"] for z in r["zonas"]] == ["titulo", "pie_foto", "articulo"]
    assert "foto" not in [z["tipo"] for z in r["zonas"]]
    assert "publicidad" not in [z["tipo"] for z in r["zonas"]]


def test_respeta_el_orden_de_lectura(monkeypatch, imagen):
    zonas = [
        Zona(tipo="articulo", x0=0.1, y0=0.5, x1=0.4, y1=0.9, orden=3),
        Zona(tipo="titulo", x0=0.1, y0=0.05, x1=0.9, y1=0.1, orden=1),
        Zona(tipo="articulo", x0=0.5, y0=0.2, x1=0.9, y1=0.4, orden=2),
    ]
    textos = iter(["PRIMERO", "SEGUNDO", "TERCERO"])
    monkeypatch.setattr(ocr_churro, "ocr_pagina", lambda *a, **k: next(textos))
    r = ocr_churro.ocr_pagina_con_zonas(imagen, zonas)
    assert r["texto"] == "PRIMERO\n\nSEGUNDO\n\nTERCERO"
    assert [z["orden"] for z in r["zonas"]] == [1, 2, 3]


def test_pagina_sin_zonas_de_texto(monkeypatch, imagen):
    zonas = [Zona(tipo="foto", x0=0, y0=0, x1=1, y1=1, orden=1)]
    monkeypatch.setattr(ocr_churro, "ocr_pagina",
                        lambda *a, **k: pytest.fail("no debio llamarse"))
    r = ocr_churro.ocr_pagina_con_zonas(imagen, zonas)
    assert r["texto"] == ""
    assert r["zonas"] == []


def test_una_zona_que_falla_no_aborta_la_pagina(monkeypatch, pagina_mixta, imagen):
    def a_veces_falla(recorte, **kw):
        if recorte.size[0] > 400:
            raise RuntimeError("sin memoria")
        return "ok"

    monkeypatch.setattr(ocr_churro, "ocr_pagina", a_veces_falla)
    r = ocr_churro.ocr_pagina_con_zonas(imagen, pagina_mixta)
    assert len(r["zonas"]) == 3
    assert r["confianza"] < 100.0        # cobertura parcial, reportada


def test_misma_forma_que_la_ruta_de_tesseract(monkeypatch, pagina_mixta, imagen):
    """Las dos rutas deben ser intercambiables aguas arriba."""
    monkeypatch.setattr(ocr_churro, "ocr_pagina", lambda *a, **k: "x")
    r = ocr_churro.ocr_pagina_con_zonas(imagen, pagina_mixta)
    assert set(r) == {"texto", "zonas", "confianza"}
    assert set(r["zonas"][0]) >= {"orden", "tipo", "texto"}


def test_estimacion_cuenta_solo_las_zonas_con_texto(pagina_mixta):
    e = ocr_churro.estimar_tiempo_zonas(pagina_mixta)
    assert e["zonas_con_texto"] == 3
    assert e["zonas_saltadas"] == 3
    assert e["costo_usd"] == 0.0
    # Por zonas tiene que salir mas barato que la pagina entera
    assert e["segundos"] < ocr_churro.estimar_tiempo(1)["segundos"]
