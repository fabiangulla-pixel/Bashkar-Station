"""
tests/test_comparative_analyzer.py — Tests para core/comparative_analyzer.py

Cubre: _tokenizar, perfil_tfidf, palabras_distintivas, similaridad_coseno_tfidf,
       comparar_campos_semanticos, generar_reporte_comparativo, cargar_corpora.
"""

import sys
import tempfile
from pathlib import Path

import pytest
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.comparative_analyzer import (
    _tokenizar,
    perfil_tfidf,
    palabras_distintivas,
    similaridad_coseno_tfidf,
    comparar_campos_semanticos,
    generar_reporte_comparativo,
    cargar_corpora,
)


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def corpora_basico():
    return {
        "Estampa": (
            "bogotá colombia política modernidad ciudad calle barrio "
            "teatro cine espectáculo artista poeta escritor "
        ) * 40,
        "Cromos": (
            "moda belleza sociedad elegante fotografía retrato mujer "
            "familia hogar costura receta festividad "
        ) * 40,
        "SemanaRef": (
            "economía industria comercio empresa gerente presidente "
            "banco dinero mercado producción fábrica obrero "
        ) * 40,
    }


@pytest.fixture
def campos_basicos():
    return {
        "Cultura": ["teatro", "cine", "artista", "poeta", "libro"],
        "Moda":    ["moda", "belleza", "costura", "elegante"],
        "Economía": ["industria", "comercio", "banco", "mercado"],
    }


# ══════════════════════════════════════════════════════════════════════════════
# _tokenizar
# ══════════════════════════════════════════════════════════════════════════════

class TestTokenizar:
    def test_retorna_lista(self):
        assert isinstance(_tokenizar("hola mundo"), list)

    def test_filtra_stopwords(self):
        # "que", "con", "para" son stopwords
        tokens = _tokenizar("que con para bogotá colombia")
        assert "que" not in tokens
        assert "con" not in tokens

    def test_filtra_palabras_cortas(self):
        # menos de 4 caracteres ignoradas
        tokens = _tokenizar("el la de colombia")
        assert "el" not in tokens
        assert "la" not in tokens

    def test_convierte_a_minusculas(self):
        tokens = _tokenizar("Bogotá Colombia")
        assert all(t == t.lower() for t in tokens)

    def test_texto_vacio_retorna_vacio(self):
        assert _tokenizar("") == []

    def test_solo_numeros_retorna_vacio(self):
        assert _tokenizar("123 456 789") == []

    def test_palabras_largas_incluidas(self):
        tokens = _tokenizar("internacionalización modernización")
        assert len(tokens) > 0


# ══════════════════════════════════════════════════════════════════════════════
# perfil_tfidf
# ══════════════════════════════════════════════════════════════════════════════

class TestPerfilTfidf:
    def test_retorna_dataframe(self, corpora_basico):
        df = perfil_tfidf(corpora_basico)
        assert isinstance(df, pd.DataFrame)

    def test_columnas_son_nombres_publicaciones(self, corpora_basico):
        df = perfil_tfidf(corpora_basico)
        assert set(df.columns) == set(corpora_basico.keys())

    def test_valores_no_negativos(self, corpora_basico):
        df = perfil_tfidf(corpora_basico)
        assert (df >= 0).all().all()

    def test_corpus_unico_retorna_dataframe(self):
        # Con un solo corpus, IDF es 0 para todos los términos → df vacío o válido
        df = perfil_tfidf({"Unico": "texto largo " * 30})
        assert isinstance(df, pd.DataFrame)

    def test_corpus_vacio_retorna_dataframe(self):
        df = perfil_tfidf({})
        assert isinstance(df, pd.DataFrame)


# ══════════════════════════════════════════════════════════════════════════════
# palabras_distintivas
# ══════════════════════════════════════════════════════════════════════════════

class TestPalabrasDistintivas:
    def test_retorna_dict(self, corpora_basico):
        result = palabras_distintivas("Estampa", corpora_basico)
        assert isinstance(result, dict)

    def test_llaves_son_otras_publicaciones(self, corpora_basico):
        result = palabras_distintivas("Estampa", corpora_basico)
        assert "Estampa" not in result
        assert "Cromos" in result
        assert "SemanaRef" in result

    def test_cada_entrada_es_lista_de_tuplas(self, corpora_basico):
        result = palabras_distintivas("Estampa", corpora_basico)
        for nombre, lista in result.items():
            assert isinstance(lista, list)
            for item in lista[:3]:
                assert isinstance(item, tuple)
                assert len(item) == 2

    def test_scores_son_floats(self, corpora_basico):
        result = palabras_distintivas("Estampa", corpora_basico)
        for nombre, lista in result.items():
            for palabra, score in lista[:5]:
                assert isinstance(score, float)

    def test_top_n_limita_resultados(self, corpora_basico):
        result = palabras_distintivas("Estampa", corpora_basico, top_n=5)
        for lista in result.values():
            assert len(lista) <= 5

    def test_foco_inexistente_no_crashea(self, corpora_basico):
        result = palabras_distintivas("NoExiste", corpora_basico)
        assert isinstance(result, dict)


# ══════════════════════════════════════════════════════════════════════════════
# similaridad_coseno_tfidf
# ══════════════════════════════════════════════════════════════════════════════

class TestSimilaridadCosenoTfidf:
    def test_retorna_dataframe_cuadrado(self, corpora_basico):
        df_tfidf = perfil_tfidf(corpora_basico)
        if df_tfidf.empty:
            pytest.skip("perfil_tfidf vacío")
        sim = similaridad_coseno_tfidf(df_tfidf)
        assert sim.shape[0] == sim.shape[1]
        assert sim.shape[0] == len(corpora_basico)

    def test_diagonal_es_uno(self, corpora_basico):
        df_tfidf = perfil_tfidf(corpora_basico)
        if df_tfidf.empty:
            pytest.skip("perfil_tfidf vacío")
        sim = similaridad_coseno_tfidf(df_tfidf)
        import numpy as np
        diag = [sim.iloc[i, i] for i in range(len(sim))]
        for v in diag:
            assert abs(v - 1.0) < 0.01

    def test_simetrica(self, corpora_basico):
        df_tfidf = perfil_tfidf(corpora_basico)
        if df_tfidf.empty:
            pytest.skip("perfil_tfidf vacío")
        sim = similaridad_coseno_tfidf(df_tfidf)
        for i in range(len(sim)):
            for j in range(len(sim)):
                assert abs(sim.iloc[i, j] - sim.iloc[j, i]) < 1e-6

    def test_valores_entre_cero_y_uno(self, corpora_basico):
        df_tfidf = perfil_tfidf(corpora_basico)
        if df_tfidf.empty:
            pytest.skip("perfil_tfidf vacío")
        sim = similaridad_coseno_tfidf(df_tfidf)
        assert (sim >= -0.01).all().all()
        assert (sim <= 1.01).all().all()


# ══════════════════════════════════════════════════════════════════════════════
# comparar_campos_semanticos
# ══════════════════════════════════════════════════════════════════════════════

class TestCompararCamposSemanticos:
    def test_retorna_dataframe(self, corpora_basico, campos_basicos):
        df = comparar_campos_semanticos(corpora_basico, campos_basicos)
        assert isinstance(df, pd.DataFrame)

    def test_filas_son_publicaciones(self, corpora_basico, campos_basicos):
        df = comparar_campos_semanticos(corpora_basico, campos_basicos)
        assert set(df.index) == set(corpora_basico.keys())

    def test_columnas_son_campos(self, corpora_basico, campos_basicos):
        df = comparar_campos_semanticos(corpora_basico, campos_basicos)
        assert set(df.columns) == set(campos_basicos.keys())

    def test_valores_no_negativos(self, corpora_basico, campos_basicos):
        df = comparar_campos_semanticos(corpora_basico, campos_basicos)
        assert (df >= 0).all().all()

    def test_corpus_especializado_tiene_campo_alto(self, campos_basicos):
        # Estampa con mucho vocabulario cultural
        corpora = {
            "Cultural": "teatro cine artista poeta libro " * 50,
            "Neutro": "texto generico palabras varias " * 50,
        }
        df = comparar_campos_semanticos(corpora, campos_basicos)
        assert df.loc["Cultural", "Cultura"] > df.loc["Neutro", "Cultura"]


# ══════════════════════════════════════════════════════════════════════════════
# generar_reporte_comparativo
# ══════════════════════════════════════════════════════════════════════════════

class TestGenerarReporteComparativo:
    def test_retorna_dict(self, corpora_basico, campos_basicos):
        rep = generar_reporte_comparativo("Estampa", corpora_basico, campos_basicos)
        assert isinstance(rep, dict)

    def test_campos_presentes(self, corpora_basico, campos_basicos):
        rep = generar_reporte_comparativo("Estampa", corpora_basico, campos_basicos)
        assert "similaridad" in rep
        assert "palabras_distintivas" in rep
        assert "perfil_campos" in rep

    def test_corpora_vacio_retorna_vacio(self, campos_basicos):
        rep = generar_reporte_comparativo("NoExiste", {}, campos_basicos)
        assert rep == {}

    def test_similaridad_es_dataframe(self, corpora_basico, campos_basicos):
        rep = generar_reporte_comparativo("Estampa", corpora_basico, campos_basicos)
        if rep.get("similaridad") is not None:
            assert isinstance(rep["similaridad"], pd.DataFrame)


# ══════════════════════════════════════════════════════════════════════════════
# cargar_corpora
# ══════════════════════════════════════════════════════════════════════════════

class TestCargarCorpora:
    def test_directorio_inexistente_retorna_vacio(self, tmp_path):
        resultado = cargar_corpora(tmp_path / "no_existe")
        assert resultado == {}

    def test_carga_subcarpetas(self, tmp_path):
        pub = tmp_path / "Publicacion_A"
        pub.mkdir()
        (pub / "p001.txt").write_text("texto de prueba largo " * 20, encoding="utf-8")
        resultado = cargar_corpora(tmp_path)
        assert "Publicacion_A" in resultado

    def test_incluye_corpus_principal(self, tmp_path):
        resultado = cargar_corpora(tmp_path, corpus_principal={"MiCorpus": "texto"})
        assert "MiCorpus" in resultado

    def test_corpus_principal_no_sobreescrito_por_directorio(self, tmp_path):
        (tmp_path / "MiCorpus").mkdir()
        (tmp_path / "MiCorpus" / "f.txt").write_text("otro texto", encoding="utf-8")
        resultado = cargar_corpora(tmp_path, corpus_principal={"MiCorpus": "original"})
        # corpus_principal tiene prioridad (update al final)
        assert resultado["MiCorpus"] == "original"

    def test_ignora_subcarpeta_vacia(self, tmp_path):
        vacia = tmp_path / "Vacia"
        vacia.mkdir()
        resultado = cargar_corpora(tmp_path)
        assert "Vacia" not in resultado
