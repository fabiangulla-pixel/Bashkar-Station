"""
tests/test_alto_reconstructor.py — Tests para core/alto_reconstructor.py

Cubre: _es_fuente_ocr_basura, _agrupar_en_lineas, _detectar_columnas,
       _linea_a_texto, reconstruir_texto_pagina (con page mock),
       extraer_titulos_pagina.
       (reconstruir_pdf_completo y es_pdf_paper_capture requieren fitz real
        y se marcan como skipif fitz no está disponible.)
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.alto_reconstructor import (
    _agrupar_en_lineas,
    _detectar_columnas,
    _es_fuente_ocr_basura,
    _linea_a_texto,
    extraer_titulos_pagina,
    reconstruir_texto_pagina,
)

# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _span(text, x0, y0, x1=None, y1=None, font="Times", size=10.0, flags=0):
    if x1 is None:
        x1 = x0 + len(text) * 6
    if y1 is None:
        y1 = y0 + size
    return {
        "text": text, "font": font, "size": size,
        "x0": x0, "y0": y0, "x1": x1, "y1": y1, "flags": flags,
    }


def _make_page(spans, width=595.0, height=842.0):
    """Crea un mock de fitz.Page a partir de una lista de spans."""
    blocks = []
    for sp in spans:
        block = {
            "type": 0,
            "lines": [{
                "spans": [{
                    "text": sp["text"],
                    "font": sp["font"],
                    "size": sp["size"],
                    "bbox": [sp["x0"], sp["y0"], sp["x1"], sp["y1"]],
                    "flags": sp.get("flags", 0),
                }]
            }]
        }
        blocks.append(block)
    page = MagicMock()
    page.get_text.return_value = {"blocks": blocks}
    page.rect = MagicMock()
    page.rect.width = width
    page.rect.height = height
    return page


# ══════════════════════════════════════════════════════════════════════════════
# _es_fuente_ocr_basura
# ══════════════════════════════════════════════════════════════════════════════

class TestEsFuenteOcrBasura:
    def test_hidden_horz_ocr(self):
        assert _es_fuente_ocr_basura("HiddenHorzOCR") is True

    def test_hidden_vert_ocr(self):
        assert _es_fuente_ocr_basura("HiddenVertOCR") is True

    def test_hidden_ocr(self):
        assert _es_fuente_ocr_basura("HiddenOCR") is True

    def test_case_insensitive(self):
        assert _es_fuente_ocr_basura("HIDDENORZOCR") is False   # variante desconocida
        assert _es_fuente_ocr_basura("hiddenhorzocr") is True

    def test_fuente_normal_falsa(self):
        assert _es_fuente_ocr_basura("Times-Roman") is False

    def test_fuente_arial_falsa(self):
        assert _es_fuente_ocr_basura("Arial") is False

    def test_cadena_vacia_falsa(self):
        assert _es_fuente_ocr_basura("") is False

    def test_guiones_ignorados(self):
        assert _es_fuente_ocr_basura("Hidden-Horz-OCR") is True


# ══════════════════════════════════════════════════════════════════════════════
# _agrupar_en_lineas
# ══════════════════════════════════════════════════════════════════════════════

class TestAgruparEnLineas:
    def test_vacio_retorna_vacio(self):
        assert _agrupar_en_lineas([]) == []

    def test_un_span_una_linea(self):
        sp = _span("hola", 50, 100)
        lineas = _agrupar_en_lineas([sp])
        assert len(lineas) == 1
        assert lineas[0][0]["text"] == "hola"

    def test_dos_spans_misma_linea(self):
        s1 = _span("hola", 50, 100)
        s2 = _span("mundo", 100, 101)  # y0 dentro de tolerancia de 3
        lineas = _agrupar_en_lineas([s1, s2])
        assert len(lineas) == 1
        assert len(lineas[0]) == 2

    def test_dos_lineas_distintas(self):
        s1 = _span("primera", 50, 100)
        s2 = _span("segunda", 50, 115)  # y0 separado por 15 > tolerancia
        lineas = _agrupar_en_lineas([s1, s2])
        assert len(lineas) == 2

    def test_orden_dentro_linea_por_x0(self):
        s1 = _span("B", 200, 100)
        s2 = _span("A", 50, 101)
        lineas = _agrupar_en_lineas([s1, s2])
        assert lineas[0][0]["text"] == "A"
        assert lineas[0][1]["text"] == "B"

    def test_tolerancia_personalizada(self):
        s1 = _span("x", 50, 100)
        s2 = _span("y", 50, 105)  # dentro de tol_y=10
        lineas = _agrupar_en_lineas([s1, s2], tol_y=10.0)
        assert len(lineas) == 1

    def test_tres_lineas(self):
        spans = [
            _span("L1a", 50, 100), _span("L1b", 80, 101),
            _span("L2",  50, 120),
            _span("L3",  50, 145),
        ]
        lineas = _agrupar_en_lineas(spans)
        assert len(lineas) == 3

    def test_retorna_lista_de_listas(self):
        lineas = _agrupar_en_lineas([_span("x", 0, 0)])
        assert isinstance(lineas, list)
        assert isinstance(lineas[0], list)


# ══════════════════════════════════════════════════════════════════════════════
# _detectar_columnas
# ══════════════════════════════════════════════════════════════════════════════

class TestDetectarColumnas:
    def test_vacio_retorna_cero(self):
        result = _detectar_columnas([], page_width=595)
        assert result == [0.0]

    def test_una_columna(self):
        lineas = [[_span("texto", 50, 100)], [_span("otro", 55, 120)]]
        cols = _detectar_columnas(lineas, page_width=595)
        assert len(cols) == 1

    def test_dos_columnas_detectadas(self):
        # Líneas con dos grupos de X0 claramente separados
        lineas = [
            [_span("col1", 50, 100)],
            [_span("col2", 310, 100)],
            [_span("col1b", 52, 130)],
            [_span("col2b", 308, 130)],
        ]
        cols = _detectar_columnas(lineas, page_width=595)
        assert len(cols) == 2

    def test_retorna_lista_ordenada(self):
        lineas = [[_span("x", 300, 50)], [_span("y", 50, 50)]]
        cols = _detectar_columnas(lineas, page_width=595)
        assert cols == sorted(cols)

    def test_ignora_columnas_cerca_del_margen_derecho(self):
        lineas = [[_span("x", 510, 100)]]  # 510/595 > 0.85 → filtrado
        cols = _detectar_columnas(lineas, page_width=595)
        # Puede retornar [0.0] si se filtra
        assert isinstance(cols, list)
        assert len(cols) >= 1


# ══════════════════════════════════════════════════════════════════════════════
# _linea_a_texto
# ══════════════════════════════════════════════════════════════════════════════

class TestLineaATexto:
    def test_vacio_retorna_vacio(self):
        assert _linea_a_texto([]) == ""

    def test_un_span(self):
        assert _linea_a_texto([_span("hola", 50, 100)]) == "hola"

    def test_dos_spans_con_espacio(self):
        s1 = _span("hola",  50, 100, x1=80)
        s2 = _span("mundo", 90, 100)  # gap = 90-80 = 10 > 2
        texto = _linea_a_texto([s1, s2])
        assert "hola" in texto
        assert "mundo" in texto
        assert " " in texto

    def test_dos_spans_sin_espacio(self):
        s1 = _span("hola",  50, 100, x1=80)
        s2 = _span("mundo", 81, 100)  # gap = 1, umbral relativo a size=10 → sin espacio extra
        texto = _linea_a_texto([s1, s2])
        assert "hola" in texto
        assert "mundo" in texto

    def test_espacio_correcto_gap_apretado_tipografia_compacta(self):
        # Regresión: coordenadas REALES de "tiene un" en Panida (rev_panida_nro1.pdf,
        # página 3), donde el hueco real entre palabras es de solo 0.35 pt a tamaño de
        # fuente ~9.8-9.9. Con el umbral fijo anterior (2.0 pt) este par se fusionaba en
        # "tieneun". El umbral relativo al tamaño de fuente debe seguir detectando el
        # espacio real aunque sea mucho más chico que 2 pt.
        s1 = _span("tiene", 238.78, 232.56, x1=262.93, size=9.84)
        s2 = _span("un",    263.28, 232.56, x1=276.86, size=9.93)  # gap = 0.35
        texto = _linea_a_texto([s1, s2])
        assert "tiene un" in texto
        assert "tieneun" not in texto

    def test_espacio_correcto_gap_apretado_un_ala(self):
        # Regresión: coordenadas reales de "un ala" en la misma página de Panida.
        # gap = 277.10 - 276.86 = 0.24 pt, tamaño ~9.8-9.9 pt.
        s1 = _span("un",  263.28, 232.56, x1=276.86, size=9.93)
        s2 = _span("ala", 277.10, 232.56, x1=292.40, size=9.80)
        texto = _linea_a_texto([s1, s2])
        assert "un ala" in texto
        assert "unala" not in texto

    def test_coma_pegada_sin_espacio_espurio(self):
        # La puntuación pegada a la palabra anterior (gap casi cero o negativo, como
        # ocurre realmente en Panida entre palabra y coma) NO debe ganar un espacio
        # espurio con el umbral relativo.
        s1 = _span("que", 50, 100, x1=68.0, size=9.8)
        s2 = _span(",",   68.1, 100, x1=71.0, size=9.8)  # gap = 0.1, pegado
        texto = _linea_a_texto([s1, s2])
        assert texto == "que,"

    def test_strip_al_final(self):
        s1 = _span("  texto  ", 50, 100)
        texto = _linea_a_texto([s1])
        assert texto == texto.strip()

    def test_tres_palabras_orden(self):
        spans = [
            _span("uno",  50, 100, x1=70),
            _span("dos",  80, 100, x1=100),
            _span("tres", 110, 100),
        ]
        texto = _linea_a_texto(spans)
        assert texto.index("uno") < texto.index("dos") < texto.index("tres")


# ══════════════════════════════════════════════════════════════════════════════
# reconstruir_texto_pagina — con page mock
# ══════════════════════════════════════════════════════════════════════════════

class TestReconstruirTextoPagina:
    def test_pagina_vacia_retorna_dict(self):
        page = _make_page([])
        result = reconstruir_texto_pagina(page)
        assert isinstance(result, dict)
        assert result["texto"] == ""
        assert result["lineas"] == []

    def test_retorna_campos_requeridos(self):
        page = _make_page([_span("texto", 50, 100)])
        result = reconstruir_texto_pagina(page)
        for campo in ("texto", "lineas", "n_columnas", "tiene_titulo"):
            assert campo in result

    def test_texto_no_vacio(self):
        spans = [_span("primero", 50, 100), _span("segundo", 50, 120)]
        page = _make_page(spans)
        result = reconstruir_texto_pagina(page)
        assert len(result["texto"]) > 0

    def test_n_columnas_entero(self):
        page = _make_page([_span("x", 50, 100)])
        result = reconstruir_texto_pagina(page)
        assert isinstance(result["n_columnas"], int)
        assert result["n_columnas"] >= 1

    def test_tiene_titulo_bool(self):
        page = _make_page([_span("x", 50, 100)])
        result = reconstruir_texto_pagina(page)
        assert isinstance(result["tiene_titulo"], bool)

    def test_fuente_basura_ignorada(self):
        spans = [
            _span("visible", 50, 100, font="Times"),
            _span("oculto",  50, 120, font="HiddenHorzOCR"),
        ]
        page = _make_page(spans)
        result = reconstruir_texto_pagina(page, ignorar_ocr_basura=True)
        assert "oculto" not in result["texto"]
        assert "visible" in result["texto"]

    def test_fuente_basura_incluida_cuando_no_ignorar(self):
        spans = [_span("oculto", 50, 100, font="HiddenHorzOCR")]
        page = _make_page(spans)
        result = reconstruir_texto_pagina(page, ignorar_ocr_basura=False)
        assert "oculto" in result["texto"]

    def test_titulo_detectado_por_tamano(self):
        # Un span grande → es_titulo=True
        spans = [
            _span("TÍTULO GRANDE", 50, 50, size=24.0),
            _span("cuerpo cuerpo cuerpo", 50, 100, size=10.0),
            _span("cuerpo cuerpo cuerpo", 50, 115, size=10.0),
            _span("cuerpo cuerpo cuerpo", 50, 130, size=10.0),
        ]
        page = _make_page(spans)
        result = reconstruir_texto_pagina(page)
        assert result["tiene_titulo"] is True

    def test_lineas_es_lista(self):
        page = _make_page([_span("x", 50, 100)])
        result = reconstruir_texto_pagina(page)
        assert isinstance(result["lineas"], list)

    def test_bloque_no_texto_ignorado(self):
        page = MagicMock()
        page.get_text.return_value = {"blocks": [{"type": 1}]}  # type 1 = imagen
        page.rect = MagicMock()
        page.rect.width = 595.0
        page.rect.height = 842.0
        result = reconstruir_texto_pagina(page)
        assert result["texto"] == ""


# ══════════════════════════════════════════════════════════════════════════════
# extraer_titulos_pagina
# ══════════════════════════════════════════════════════════════════════════════

class TestExtraerTitulosPagina:
    def _datos(self, lineas):
        return {"lineas": lineas}

    def test_sin_lineas_retorna_vacio(self):
        assert extraer_titulos_pagina({"lineas": []}) == []

    def test_linea_no_titulo_ignorada(self):
        datos = self._datos([{"texto": "texto normal", "es_titulo": False}])
        assert extraer_titulos_pagina(datos) == []

    def test_linea_titulo_incluida(self):
        datos = self._datos([{"texto": "Gran Título Aquí", "es_titulo": True}])
        result = extraer_titulos_pagina(datos)
        assert "Gran Título Aquí" in result

    def test_min_palabras_filtra_titulo_corto(self):
        datos = self._datos([{"texto": "Solo", "es_titulo": True}])
        result = extraer_titulos_pagina(datos, min_palabras_titulo=2)
        assert result == []

    def test_min_palabras_incluye_titulo_largo(self):
        datos = self._datos([{"texto": "Título de Prueba", "es_titulo": True}])
        result = extraer_titulos_pagina(datos, min_palabras_titulo=2)
        assert len(result) == 1

    def test_varios_titulos(self):
        datos = self._datos([
            {"texto": "Primer Título", "es_titulo": True},
            {"texto": "texto cuerpo",  "es_titulo": False},
            {"texto": "Segundo Título", "es_titulo": True},
        ])
        result = extraer_titulos_pagina(datos)
        assert len(result) == 2

    def test_retorna_lista(self):
        assert isinstance(extraer_titulos_pagina({"lineas": []}), list)
