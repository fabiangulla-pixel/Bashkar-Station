"""tests/test_ocr_engine_duplicados.py — detectar_posibles_duplicados().

Regresión del hallazgo de auditoría s.59 de [[project_bashkar_station]]:
el usuario seleccionó el mismo número de Estampa dos veces bajo nombres de
archivo distintos (uno era un export parcial mal nombrado) y Bashkar los
procesó en silencio como dos números distintos.
"""

import fitz
import pytest

from core.ocr_engine import detectar_posibles_duplicados


def _crear_pdf(path, textos_por_pagina):
    doc = fitz.new_file() if hasattr(fitz, "new_file") else fitz.open()
    for texto in textos_por_pagina:
        pagina = doc.new_page()
        pagina.insert_text((72, 72), texto, fontsize=11)
    doc.save(str(path))
    doc.close()


TEXTO_ESTAMPA = (
    "La revista Estampa presenta en marzo de mil novecientos treinta y nueve "
    "una cronica sobre la vida social bogotana y los sucesos internacionales "
    "relacionados con la guerra civil espanola y la politica colombiana"
)
TEXTO_OTRO_NUMERO = (
    "El presente numero de enero contiene articulos sobre modas femeninas "
    "deportes nacionales cine hollywood teatro nacional y avisos comerciales "
    "de almacenes bogotanos con precios especiales de temporada"
)


class TestDetectarPosiblesDuplicados:
    def test_mismo_contenido_dos_nombres_se_detecta(self, tmp_path):
        original = tmp_path / "rev_estampa_mar_1939.pdf"
        parcial  = tmp_path / "Páginas desderev_estampa_mar_1939.pdf"
        _crear_pdf(original, [TEXTO_ESTAMPA, TEXTO_ESTAMPA])
        _crear_pdf(parcial,  [TEXTO_ESTAMPA])

        dups = detectar_posibles_duplicados([original, parcial])

        assert len(dups) == 1
        a, b, overlap = dups[0]
        assert {a, b} == {original, parcial}
        assert overlap > 0.9

    def test_numeros_distintos_no_se_marcan(self, tmp_path):
        p1 = tmp_path / "rev_estampa_ene_1939.pdf"
        p2 = tmp_path / "rev_estampa_mar_1939.pdf"
        _crear_pdf(p1, [TEXTO_OTRO_NUMERO])
        _crear_pdf(p2, [TEXTO_ESTAMPA])

        dups = detectar_posibles_duplicados([p1, p2])

        assert dups == []

    def test_un_solo_pdf_no_produce_pares(self, tmp_path):
        p1 = tmp_path / "unico.pdf"
        _crear_pdf(p1, [TEXTO_ESTAMPA])
        assert detectar_posibles_duplicados([p1]) == []

    def test_pdf_vacio_no_revienta_ni_se_compara(self, tmp_path):
        vacio = tmp_path / "vacio.pdf"
        normal = tmp_path / "normal.pdf"
        _crear_pdf(vacio, [""])
        _crear_pdf(normal, [TEXTO_ESTAMPA])
        dups = detectar_posibles_duplicados([vacio, normal])
        assert dups == []

    def test_pdf_inexistente_no_revienta(self, tmp_path):
        falso = tmp_path / "no_existe.pdf"
        real  = tmp_path / "real.pdf"
        _crear_pdf(real, [TEXTO_ESTAMPA])
        dups = detectar_posibles_duplicados([falso, real])
        assert dups == []

    def test_resultado_ordenado_de_mayor_a_menor_overlap(self, tmp_path):
        base = tmp_path / "base.pdf"
        casi_igual = tmp_path / "casi_igual.pdf"
        parcial_distinto = tmp_path / "parcial_distinto.pdf"
        _crear_pdf(base, [TEXTO_ESTAMPA])
        _crear_pdf(casi_igual, [TEXTO_ESTAMPA])
        _crear_pdf(parcial_distinto, [TEXTO_ESTAMPA[:60] + " " + TEXTO_OTRO_NUMERO])

        dups = detectar_posibles_duplicados(
            [base, casi_igual, parcial_distinto], umbral=0.2
        )

        assert dups == sorted(dups, key=lambda t: t[2], reverse=True)
