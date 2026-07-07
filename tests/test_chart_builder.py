"""tests/test_chart_builder.py — Tests para core/chart_builder.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from core.chart_builder import (
    CATALOGO,
    comparativo_divergente,
    corpus_longitud_articulos,
    corpus_palabras_por_numero,
    corpus_zipf,
    ner_categorias,
    ner_frecuencia,
    ocr_boxplot,
    ocr_histograma,
    ocr_scatter,
    tono_area_apilada,
    tono_barras,
    tono_heatmap,
    tono_pie,
    tono_radar,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

TONOS_TODOS = ["celebratorio", "crítico", "neutro", "elegíaco", "polémico", "informativo"]

def _res_tono(n=10):
    import itertools
    ciclo = itertools.cycle(TONOS_TODOS)
    return {
        str(i): {
            "tono_principal": next(ciclo),
            "confianza": 0.8,
            "numero": f"num{i % 3 + 1}",
            "seccion": "cultura" if i % 2 == 0 else "política",
        }
        for i in range(n)
    }

def _confianza(n=20):
    return {
        str(i): {
            "confianza": 0.5 + (i % 5) * 0.1,
            "palabras": 100 + i * 10,
            "numero": f"num{i % 3 + 1}",
        }
        for i in range(n)
    }

def _ner():
    return {
        "PER": {"García": ["a1", "a2", "a3"], "López": ["a1"], "Martínez": ["a2", "a3"]},
        "LOC": {"Bogotá": ["a1", "a2"], "Medellín": ["a3"]},
        "ORG": {"El Tiempo": ["a1", "a2", "a3", "a4"]},
    }

def _articulos(n=15):
    return [
        {
            "texto": f"Este es el texto del artículo número {i} con varias palabras " * 5,
            "titulo": f"Artículo {i}",
            "tipo": "cultura" if i % 3 == 0 else ("política" if i % 3 == 1 else "crónica"),
            "numero": f"num{i % 3 + 1}",
        }
        for i in range(n)
    ]

def _corpus_txt(n=10):
    return [
        "colombia bogotá cultura prensa editorial artículo texto información " * 20
        for _ in range(n)
    ]


def _es_figura(obj):
    return isinstance(obj, plt.Figure)


# ── CATÁLOGO ──────────────────────────────────────────────────────────────────

class TestCatalogo:
    def test_fuentes_esperadas(self):
        esperadas = {"Tono editorial", "Calidad OCR", "Entidades (NER)",
                     "Corpus general", "Estilometría", "Comparativo"}
        assert esperadas.issubset(set(CATALOGO.keys()))

    def test_cada_opcion_tiene_campos_requeridos(self):
        for fuente, opciones in CATALOGO.items():
            for op in opciones:
                assert "id"    in op, f"{fuente}: falta 'id'"
                assert "label" in op, f"{fuente}: falta 'label'"
                assert "desc"  in op, f"{fuente}: falta 'desc'"
                assert "fn"    in op, f"{fuente}: falta 'fn'"
                assert "param" in op, f"{fuente}: falta 'param'"

    def test_funciones_son_callable(self):
        for fuente, opciones in CATALOGO.items():
            for op in opciones:
                assert callable(op["fn"]), f"{fuente}/{op['id']}: 'fn' no es callable"

    def test_ids_unicos(self):
        ids = [op["id"] for ops in CATALOGO.values() for op in ops]
        assert len(ids) == len(set(ids)), "IDs duplicados en el catálogo"

    def test_descripciones_no_vacias(self):
        for fuente, opciones in CATALOGO.items():
            for op in opciones:
                assert op["desc"].strip(), f"{fuente}/{op['id']}: descripción vacía"


# ── TONO ─────────────────────────────────────────────────────────────────────

class TestTonoBarras:
    def test_retorna_figura(self):
        assert _es_figura(tono_barras(_res_tono()))

    def test_titulo_personalizado(self):
        fig = tono_barras(_res_tono(), titulo="Mi título")
        assert fig.axes[0].get_title() == "Mi título"

    def test_corpus_vacio(self):
        fig = tono_barras({})
        assert _es_figura(fig)

    def teardown_method(self):
        plt.close("all")


class TestTonoPie:
    def test_retorna_figura(self):
        assert _es_figura(tono_pie(_res_tono()))

    def test_titulo_personalizado(self):
        fig = tono_pie(_res_tono(), titulo="Torta")
        assert _es_figura(fig)

    def teardown_method(self):
        plt.close("all")


class TestTonoHeatmap:
    def test_retorna_figura(self):
        assert _es_figura(tono_heatmap(_res_tono(20)))

    def test_un_solo_numero(self):
        res = {"a": {"tono_principal": "neutro", "confianza": 0.7, "numero": "n1"}}
        assert _es_figura(tono_heatmap(res))

    def teardown_method(self):
        plt.close("all")


class TestTonoAreaApilada:
    def test_retorna_figura_con_varios_numeros(self):
        assert _es_figura(tono_area_apilada(_res_tono(20)))

    def test_un_solo_numero_cae_a_barras(self):
        res = {"a": {"tono_principal": "neutro", "numero": "n1", "confianza": 0.7}}
        fig = tono_area_apilada(res)
        assert _es_figura(fig)

    def teardown_method(self):
        plt.close("all")


class TestTonoRadar:
    def test_retorna_figura(self):
        assert _es_figura(tono_radar(_res_tono()))

    def test_corpus_vacio(self):
        assert _es_figura(tono_radar({}))

    def teardown_method(self):
        plt.close("all")


# ── OCR ───────────────────────────────────────────────────────────────────────

class TestOcrBoxplot:
    def test_retorna_figura(self):
        assert _es_figura(ocr_boxplot(_confianza()))

    def test_un_solo_numero(self):
        datos = {"p1": {"confianza": 0.8, "palabras": 200, "numero": "n1"}}
        assert _es_figura(ocr_boxplot(datos))

    def teardown_method(self):
        plt.close("all")


class TestOcrScatter:
    def test_retorna_figura(self):
        assert _es_figura(ocr_scatter(_confianza()))

    def test_corpus_vacio(self):
        assert _es_figura(ocr_scatter({}))

    def teardown_method(self):
        plt.close("all")


class TestOcrHistograma:
    def test_retorna_figura(self):
        assert _es_figura(ocr_histograma(_confianza()))

    def test_un_dato(self):
        datos = {"p1": {"confianza": 0.75, "numero": "n1"}}
        assert _es_figura(ocr_histograma(datos))

    def teardown_method(self):
        plt.close("all")


# ── NER ───────────────────────────────────────────────────────────────────────

class TestNerFrecuencia:
    def test_retorna_figura(self):
        assert _es_figura(ner_frecuencia(_ner(), "PER"))

    def test_categoria_vacia(self):
        fig = ner_frecuencia({}, "PER")
        assert _es_figura(fig)

    def test_categoria_inexistente(self):
        fig = ner_frecuencia(_ner(), "EVE")
        assert _es_figura(fig)

    def test_top_n(self):
        ner = {"PER": {f"persona{i}": [f"a{i}"] for i in range(30)}}
        fig = ner_frecuencia(ner, "PER", top_n=5)
        assert _es_figura(fig)

    def teardown_method(self):
        plt.close("all")


class TestNerCategorias:
    def test_retorna_figura(self):
        assert _es_figura(ner_categorias(_ner()))

    def test_vacio(self):
        assert _es_figura(ner_categorias({}))

    def teardown_method(self):
        plt.close("all")


# ── CORPUS ────────────────────────────────────────────────────────────────────

class TestCorpusPalabrasPorNumero:
    def test_retorna_figura(self):
        assert _es_figura(corpus_palabras_por_numero(_articulos()))

    def test_lista_vacia(self):
        assert _es_figura(corpus_palabras_por_numero([]))

    def teardown_method(self):
        plt.close("all")


class TestCorpusZipf:
    def test_retorna_figura(self):
        assert _es_figura(corpus_zipf(_corpus_txt()))

    def test_corpus_vacio(self):
        assert _es_figura(corpus_zipf([]))

    def teardown_method(self):
        plt.close("all")


class TestCorpusLongitud:
    def test_retorna_figura(self):
        assert _es_figura(corpus_longitud_articulos(_articulos()))

    def test_sin_texto(self):
        arts = [{"texto": None, "tipo": "x", "numero": "n1"}]
        assert _es_figura(corpus_longitud_articulos(arts))

    def teardown_method(self):
        plt.close("all")


# ── COMPARATIVO ───────────────────────────────────────────────────────────────

class TestComparativoDivergente:
    def _delta_mock(self):
        tonos = ["celebratorio", "crítico", "neutro", "elegíaco", "polémico", "informativo"]
        return {t: {"delta": (i - 3) * 5.0, "A": 15.0, "B": 15.0 + (i - 3) * 5.0}
                for i, t in enumerate(tonos)}

    def test_retorna_figura(self):
        assert _es_figura(comparativo_divergente(self._delta_mock()))

    def test_con_etiquetas(self):
        fig = comparativo_divergente(self._delta_mock(), "Ene 1939", "Feb 1939")
        assert _es_figura(fig)

    def test_delta_ceros(self):
        tonos = ["celebratorio", "crítico", "neutro", "elegíaco", "polémico", "informativo"]
        delta = {t: {"delta": 0.0, "A": 20.0, "B": 20.0} for t in tonos}
        assert _es_figura(comparativo_divergente(delta))

    def teardown_method(self):
        plt.close("all")


# ── Guardado ──────────────────────────────────────────────────────────────────

class TestGuardado:
    def test_guardar_png(self, tmp_path):
        fig = tono_barras(_res_tono())
        dest = tmp_path / "test.png"
        fig.savefig(str(dest), dpi=72)
        assert dest.exists()
        assert dest.stat().st_size > 1000

    def test_guardar_svg(self, tmp_path):
        fig = tono_pie(_res_tono())
        dest = tmp_path / "test.svg"
        fig.savefig(str(dest))
        assert dest.exists()

    def teardown_method(self):
        plt.close("all")
