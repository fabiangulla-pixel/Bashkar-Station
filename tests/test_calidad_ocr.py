"""tests/test_calidad_ocr.py — Métricas de calidad de OCR, abstención por
fragmentación y censo de texto página por página.

Los casos no son sintéticos al azar: reproducen las cifras reales medidas el
3-sep-2026 sobre nueve publicaciones de la Biblioteca Nacional
(`scripts/_experimentos/generalizacion_20260903/RESULTADOS.md`) y el censo real
de *El Día*, que es el documento que motivó la decisión por página.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import calidad_ocr as cal  # noqa: E402


def _texto(n_normales: int = 0, n_fragmentos: int = 0, n_fusiones: int = 0) -> str:
    """Texto sintético con una composición de tokens exacta y conocida."""
    partes = ["palabra"] * n_normales
    partes += ["x"] * n_fragmentos          # 1 letra, no está en CORTAS_OK
    partes += ["a" * 20] * n_fusiones        # 20 > LARGO_TOKEN_FUSION
    return " ".join(partes)


# ── metricas_texto ───────────────────────────────────────────────────────────

def test_cuenta_tokens_fusiones_y_fragmentos():
    m = cal.metricas_texto(_texto(n_normales=90, n_fragmentos=8, n_fusiones=2))
    assert m.tokens == 100
    assert m.fragmentos == 8
    assert m.fusiones == 2
    assert m.pct_fragmentacion == pytest.approx(8.0)
    assert m.pct_fusion == pytest.approx(2.0)


def test_palabras_cortas_legitimas_no_son_fragmentos():
    """«de la el en un» son español, no basura de OCR."""
    m = cal.metricas_texto("de la el en un y o a")
    assert m.tokens == 8
    assert m.fragmentos == 0


def test_numeros_y_puntuacion_no_entran_en_el_denominador():
    """Un número de página no debe diluir el porcentaje de fragmentación."""
    m = cal.metricas_texto("1939 -- 12, 345 ;")
    assert m.tokens == 0
    assert m.pct_fragmentacion == 0.0


def test_texto_vacio_no_revienta():
    for entrada in ("", None, "   "):
        m = cal.metricas_texto(entrada)
        assert m.tokens == 0
        assert m.pct_fragmentacion == 0.0


def test_metricas_se_suman_por_cuentas_crudas():
    a = cal.metricas_texto(_texto(n_normales=100))
    b = cal.metricas_texto(_texto(n_fragmentos=100))
    total = a + b
    assert total.tokens == 200
    assert total.pct_fragmentacion == pytest.approx(50.0)


# ── evaluar: los nueve corpus reales caen del lado correcto ─────────────────

# (publicación, % fragmentación medido, veredicto que debe emitir)
CORPUS_REALES = [
    ("Rin-Rin", 2.6, cal.UTILIZABLE),
    ("Agitación Femenina", 4.0, cal.UTILIZABLE),
    ("Panida 1915", 6.2, cal.UTILIZABLE),
    ("Estampa 1939 (línea base)", 6.8, cal.UTILIZABLE),
    ("La Mujer", 7.4, cal.UTILIZABLE),
    ("La Semana Cómica", 20.8, cal.NO_UTILIZABLE),
    ("El Nuevo Tiempo 1902", 35.6, cal.NO_UTILIZABLE),
]


@pytest.mark.parametrize("nombre,pct,esperado", CORPUS_REALES)
def test_veredicto_de_cada_publicacion_real(nombre, pct, esperado):
    n_frag = round(pct * 10)          # sobre 1.000 tokens
    m = cal.metricas_texto(_texto(n_normales=1000 - n_frag, n_fragmentos=n_frag))
    v = cal.evaluar_metricas(m)
    assert v.veredicto == esperado, f"{nombre}: {v.mensaje}"


def test_estampa_la_linea_base_nunca_se_abstiene():
    """Si el umbral llegara a abstenerse del corpus validado del proyecto,
    está mal puesto: todo el análisis publicado se hizo sobre él."""
    m = cal.metricas_texto(_texto(n_normales=932, n_fragmentos=68))
    v = cal.evaluar_metricas(m)
    assert not v.se_abstiene


def test_zona_intermedia_pide_revision_pero_no_descarta():
    m = cal.metricas_texto(_texto(n_normales=850, n_fragmentos=150))  # 15 %
    v = cal.evaluar_metricas(m)
    assert v.veredicto == cal.REVISAR
    assert v.se_abstiene
    assert "fragmentación" in v.mensaje


def test_fusion_alta_tambien_dispara_revision():
    """Fusión por encima del 1 % es regresión de alto_reconstructor, no
    propiedad del corpus: el máximo real medido es 0,26 %."""
    m = cal.metricas_texto(_texto(n_normales=970, n_fusiones=30))  # 3 %
    v = cal.evaluar_metricas(m)
    assert v.veredicto == cal.REVISAR
    assert "fusión" in v.mensaje


def test_muestra_pequena_no_se_declara_utilizable():
    """Con 30 tokens un solo fragmento son 3 puntos: callarse sería el mismo
    fallo silencioso que el módulo existe para evitar."""
    v = cal.evaluar_texto(_texto(n_normales=30))
    assert v.veredicto == cal.REVISAR
    assert "muestra insuficiente" in v.mensaje


def test_umbrales_configurables():
    m = cal.metricas_texto(_texto(n_normales=920, n_fragmentos=80))  # 8 %
    assert cal.evaluar_metricas(m).veredicto == cal.UTILIZABLE
    assert cal.evaluar_metricas(m, umbral_revisar=5.0).veredicto == cal.REVISAR


def test_evaluar_paginas_pondera_por_tamano_no_por_pagina():
    """Una página corta y basura no debe pesar lo mismo que una larga y limpia."""
    limpia = _texto(n_normales=1000)
    basura = _texto(n_fragmentos=10)
    v = cal.evaluar_paginas([limpia, basura])
    assert v.metricas.pct_fragmentacion == pytest.approx(10 / 1010 * 100)
    assert v.veredicto == cal.UTILIZABLE


# ── Censo de páginas: el caso de El Día ──────────────────────────────────────

def _pdf(tmp_path: Path, textos_por_pagina: list[str]) -> Path:
    """PDF real con el texto indicado en cada página."""
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    for txt in textos_por_pagina:
        pagina = doc.new_page()
        if txt:
            pagina.insert_textbox(fitz.Rect(20, 20, 560, 780), txt, fontsize=7)
    destino = tmp_path / "doc.pdf"
    doc.save(str(destino))
    doc.close()
    return destino


def test_censo_de_el_dia_14_paginas_vacias_y_2_con_texto(tmp_path):
    """El caso real: declara la capa oculta de Paper Capture y solo 2 de 16
    páginas están OCR-izadas. Cualquier decisión a nivel de documento se lleva
    el 87,5 % del ejemplar por delante."""
    paginas = [""] * 14 + [_texto(n_normales=400)] * 2
    censo = cal.censar_paginas(_pdf(tmp_path, paginas))

    assert censo.n_paginas == 16
    assert censo.paginas_con_texto == [14, 15]
    assert len(censo.paginas_sin_texto) == 14
    assert censo.cobertura == pytest.approx(2 / 16)
    assert censo.modo_de_pagina(0) == "escaneado"
    assert censo.modo_de_pagina(15) == "digital"
    assert "2 de 16" in censo.resumen


def test_el_texto_esta_al_final_y_el_muestreo_de_las_primeras_lo_pierde(tmp_path):
    """Regresión explícita contra el muestreo de las 5 primeras páginas."""
    paginas = [""] * 10 + [_texto(n_normales=400)]
    censo = cal.censar_paginas(_pdf(tmp_path, paginas))
    assert censo.paginas_con_texto == [10]
    assert censo.modos[:5] == ["escaneado"] * 5


def test_documento_enteramente_digital(tmp_path):
    paginas = [_texto(n_normales=300)] * 4
    censo = cal.censar_paginas(_pdf(tmp_path, paginas))
    assert censo.cobertura == 1.0
    assert censo.paginas_sin_texto == []
    assert "las 4 páginas traen texto" in censo.resumen


def test_marca_de_agua_de_la_bnc_no_cuenta_como_texto(tmp_path):
    """«Digitalizado Biblioteca Nacional de Colombia» son 5 palabras: la página
    sigue necesitando OCR."""
    paginas = ["Digitalizado Biblioteca Nacional de Colombia"] * 3
    censo = cal.censar_paginas(_pdf(tmp_path, paginas))
    assert censo.paginas_con_texto == []
    assert censo.modos == ["escaneado"] * 3


def test_censo_de_archivo_inexistente_no_revienta(tmp_path):
    censo = cal.censar_paginas(tmp_path / "no_existe.pdf")
    assert censo.n_paginas == 0
    assert censo.cobertura == 0.0
    assert censo.modo_de_pagina(0) == "escaneado"


def test_censo_reutiliza_un_doc_ya_abierto_y_no_lo_cierra(tmp_path):
    fitz = pytest.importorskip("fitz")
    ruta = _pdf(tmp_path, [_texto(n_normales=300)] * 2)
    doc = fitz.open(str(ruta))
    try:
        censo = cal.censar_paginas(ruta, doc=doc)
        assert censo.n_paginas == 2
        assert not doc.is_closed
    finally:
        doc.close()


# ── informe_documento ───────────────────────────────────────────────────────

def test_informe_documento_junta_censo_y_veredicto(tmp_path):
    paginas = [""] * 2 + [_texto(n_normales=600, n_fragmentos=200)] * 2
    inf = cal.informe_documento(_pdf(tmp_path, paginas))

    assert inf["n_paginas"] == 4
    assert inf["paginas_con_texto"] == 2
    assert inf["cobertura_texto"] == pytest.approx(0.5)
    assert inf["veredicto"] == cal.NO_UTILIZABLE
    assert inf["pct_fragmentacion"] > cal.UMBRAL_FRAGMENTACION_CRITICO
    assert inf["archivo"] == "doc.pdf"


def test_informe_documento_es_serializable(tmp_path):
    import json
    inf = cal.informe_documento(_pdf(tmp_path, [_texto(n_normales=400)]))
    assert json.loads(json.dumps(inf)) == inf
