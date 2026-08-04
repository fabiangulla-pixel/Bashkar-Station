"""Tests de core/benchmark_ocr.py — métricas de evaluación de OCR.

Se comprueban contra valores calculados a mano, no contra la propia
implementación: si el test solo repitiera la fórmula del código, no probaría
nada.
"""

from __future__ import annotations

import json

import pytest

from core.benchmark_ocr import (
    Resultado,
    cer,
    comparar,
    distancia_edicion,
    evaluar_rutas,
    exportar_csv,
    exportar_json,
    normalizar,
    similitud_levenshtein,
    tabla_markdown,
    wer,
)


class TestDistanciaEdicion:
    def test_identicas_es_cero(self):
        assert distancia_edicion("estampa", "estampa") == 0

    def test_una_sustitucion(self):
        assert distancia_edicion("estampa", "estumpa") == 1

    def test_una_insercion(self):
        assert distancia_edicion("gato", "gatos") == 1

    def test_un_borrado(self):
        assert distancia_edicion("gatos", "gato") == 1

    def test_caso_clasico_kitten_sitting(self):
        # Ejemplo canónico de la literatura: distancia 3
        assert distancia_edicion("kitten", "sitting") == 3

    def test_cadena_vacia(self):
        assert distancia_edicion("", "abc") == 3
        assert distancia_edicion("abc", "") == 3
        assert distancia_edicion("", "") == 0

    def test_funciona_sobre_listas_de_palabras(self):
        assert distancia_edicion(["la", "guerra", "civil"],
                                 ["la", "guerra", "mundial"]) == 1

    def test_es_simetrica(self):
        a, b = "Bogotá 1939", "Bogota 1930"
        assert distancia_edicion(a, b) == distancia_edicion(b, a)


class TestNormalizacion:
    def test_por_defecto_quita_tildes_y_baja_a_minusculas(self):
        assert normalizar("Bogotá ESPAÑA") == "bogota espana"

    def test_estricta_conserva_tildes_y_mayusculas(self):
        assert normalizar("Bogotá ESPAÑA", estricta=True) == "Bogotá ESPAÑA"

    def test_colapsa_espacios_y_saltos(self):
        assert normalizar("la   guerra\n\n civil") == "la guerra civil"

    def test_une_palabra_partida_por_guion_de_corte(self):
        # En prensa histórica esto es composición tipográfica, no error de OCR
        assert normalizar("revolu-\ncion") == "revolucion"
        assert normalizar("revolu¬\ncion") == "revolucion"

    def test_none_no_revienta(self):
        assert normalizar(None) == ""


class TestCERyWER:
    def test_transcripcion_perfecta_da_cero(self):
        t = "La guerra civil española llegó a su fin"
        assert cer(t, t) == 0.0
        assert wer(t, t) == 0.0
        assert similitud_levenshtein(t, t) == 1.0

    def test_cer_calculado_a_mano(self):
        # "gato" vs "gata": 1 sustitución sobre 4 caracteres = 0,25
        assert cer("gato", "gata") == pytest.approx(0.25)

    def test_wer_calculado_a_mano(self):
        # 1 palabra mal de 4 = 0,25
        assert wer("la guerra civil española",
                   "la guerra civil francesa") == pytest.approx(0.25)

    def test_wer_castiga_mas_que_cer(self):
        ref = "la guerra civil española"
        hip = "la guerrn civil espanola"     # 1 carácter mal en dos palabras
        assert wer(ref, hip) > cer(ref, hip)

    def test_hipotesis_vacia_es_error_total(self):
        assert cer("texto de referencia", "") == pytest.approx(1.0)
        assert similitud_levenshtein("texto de referencia", "") == 0.0

    def test_similitud_nunca_sale_del_rango(self):
        # Con mucho texto de más el CER supera 1, pero la similitud se acota
        s = similitud_levenshtein("hola", "hola " * 50)
        assert 0.0 <= s <= 1.0

    def test_referencia_vacia_no_divide_por_cero(self):
        assert cer("", "") == 0.0
        assert cer("", "algo") == 1.0
        assert wer("", "") == 0.0

    def test_las_tildes_no_penalizan_salvo_en_modo_estricto(self):
        assert cer("España", "Espana") == 0.0
        assert cer("España", "Espana", estricta=True) > 0.0


class TestComparar:
    def test_promedio_es_micro_no_macro(self):
        """Una página larga debe pesar más que una corta.

        Con macro-promedio ambas pesarían igual y el resultado seria 0,25;
        el micro-promedio agrega distancias sobre longitudes.
        """
        referencias = {"p1": "a" * 100, "p2": "bbbb"}
        hipotesis = {"p1": "a" * 100, "p2": "cccc"}   # solo falla la corta
        r = comparar(referencias, hipotesis, ruta="prueba")
        assert r.cer == pytest.approx(4 / 104, abs=1e-6)
        assert r.cer < 0.25

    def test_pagina_ausente_cuenta_como_error_total(self):
        r = comparar({"p1": "texto largo aqui", "p2": "otro texto"},
                     {"p1": "texto largo aqui"}, ruta="incompleta")
        assert r.paginas == 2
        assert r.cer > 0
        assert r.por_pagina[1]["palabras_hip"] == 0

    def test_detalle_por_pagina(self):
        r = comparar({"p1": "gato", "p2": "perro"},
                     {"p1": "gata", "p2": "perro"}, ruta="x")
        assert len(r.por_pagina) == 2
        assert r.por_pagina[0]["cer"] == pytest.approx(0.25)
        assert r.por_pagina[1]["cer"] == 0.0

    def test_referencias_vacias_devuelve_resultado_vacio(self):
        r = comparar({}, {}, ruta="nada")
        assert r.paginas == 0
        assert r.cer == 0.0

    def test_segundos_por_pagina(self):
        r = comparar({"p1": "hola", "p2": "adios"}, {"p1": "hola", "p2": "adios"},
                     ruta="x", segundos=30.0)
        assert r.segundos_por_pagina == pytest.approx(15.0)

    def test_segundos_por_pagina_sin_paginas_no_revienta(self):
        assert Resultado(ruta="x", segundos=10).segundos_por_pagina == 0.0


class TestCalidad:
    @pytest.mark.parametrize("valor_cer,esperado", [
        (0.01, "casi limpio"),
        (0.05, "casi limpio"),
        (0.08, "explotable"),
        (0.10, "explotable"),
        (0.20, "requiere corrección"),
        (0.60, "inservible"),
    ])
    def test_umbrales(self, valor_cer, esperado):
        assert Resultado(ruta="x", cer=valor_cer).calidad == esperado


class TestEvaluarRutas:
    @pytest.fixture
    def escenario(self):
        referencias = {"p1": "la guerra civil española", "p2": "bogota mil novecientos"}
        rutas = {
            "tesseract": {"p1": "la guerrn civil espanola", "p2": "bogota mil novecientos"},
            "churro":    {"p1": "la guerra civil española", "p2": "bogota mil novecientos"},
            "vacio":     {"p1": "", "p2": ""},
        }
        return referencias, rutas

    def test_ordena_de_mejor_a_peor(self, escenario):
        referencias, rutas = escenario
        res = evaluar_rutas(referencias, rutas)
        assert [r.ruta for r in res][0] == "churro"
        assert [r.ruta for r in res][-1] == "vacio"
        assert res[0].cer <= res[1].cer <= res[2].cer

    def test_la_ruta_perfecta_da_cer_cero(self, escenario):
        referencias, rutas = escenario
        res = evaluar_rutas(referencias, rutas)
        assert res[0].cer == 0.0
        assert res[0].similitud == 1.0

    def test_propaga_los_tiempos(self, escenario):
        referencias, rutas = escenario
        res = evaluar_rutas(referencias, rutas, tiempos={"churro": 360.0})
        churro = next(r for r in res if r.ruta == "churro")
        assert churro.segundos == 360.0
        assert churro.segundos_por_pagina == pytest.approx(180.0)


class TestExportacion:
    @pytest.fixture
    def resultados(self):
        return evaluar_rutas(
            {"p1": "la guerra civil"},
            {"a": {"p1": "la guerra civil"}, "b": {"p1": "la guerra"}},
        )

    def test_tabla_markdown_lista_todas_las_rutas(self, resultados):
        md = tabla_markdown(resultados)
        assert "| Ruta |" in md
        assert "| a |" in md
        assert "| b |" in md
        assert "Mejor ruta por CER: **a**" in md

    def test_tabla_markdown_sin_resultados(self):
        assert "Sin resultados" in tabla_markdown([])

    def test_csv_se_abre_con_excel(self, resultados, tmp_path):
        destino = exportar_csv(resultados, tmp_path / "bench.csv")
        contenido = destino.read_bytes()
        assert contenido.startswith(b"\xef\xbb\xbf")     # BOM utf-8-sig
        texto = contenido.decode("utf-8-sig")
        assert "ruta,paginas,cer,wer" in texto
        assert "calidad" in texto

    def test_json_conserva_el_detalle_por_pagina(self, resultados, tmp_path):
        destino = exportar_json(resultados, tmp_path / "bench.json")
        datos = json.loads(destino.read_text(encoding="utf-8"))
        assert len(datos) == 2
        assert "por_pagina" in datos[0]
        assert datos[0]["por_pagina"][0]["pagina"] == "p1"
        assert "calidad" in datos[0]
