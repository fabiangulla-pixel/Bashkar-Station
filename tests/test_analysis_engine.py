"""
tests/test_analysis_engine.py — Tests para core/analysis_engine.py

Cubre: leer_numero (filesystem), construir_red (networkx),
       run_lda (sklearn), analizar_numero_texto (con nlp mock),
       SECCIONES / CAMPOS_SEM constantes.
       analizar_layout_pagina requiere cv2/scipy y se omite si no están.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.analysis_engine import (
    leer_numero,
    construir_red,
    run_lda,
    SECCIONES,
    CAMPOS_SEM,
)


# ══════════════════════════════════════════════════════════════════════════════
# Constantes
# ══════════════════════════════════════════════════════════════════════════════

class TestConstantes:
    def test_secciones_es_dict(self):
        assert isinstance(SECCIONES, dict)

    def test_secciones_no_vacio(self):
        assert len(SECCIONES) > 0

    def test_campos_sem_es_dict(self):
        assert isinstance(CAMPOS_SEM, dict)

    def test_campos_sem_tiene_modernidad(self):
        assert "Modernidad" in CAMPOS_SEM

    def test_campos_sem_valores_son_listas(self):
        for campo, terminos in CAMPOS_SEM.items():
            assert isinstance(terminos, list), f"Campo {campo} no es lista"

    def test_secciones_valores_son_listas(self):
        for sec, pats in SECCIONES.items():
            assert isinstance(pats, list), f"Sección {sec} no es lista"


# ══════════════════════════════════════════════════════════════════════════════
# leer_numero
# ══════════════════════════════════════════════════════════════════════════════

class TestLeerNumero:
    def test_directorio_inexistente_retorna_vacio(self, tmp_path):
        resultado = leer_numero(tmp_path, "no_existe")
        assert resultado == ""

    def test_carga_un_txt(self, tmp_path):
        carpeta = tmp_path / "enero_1939"
        carpeta.mkdir()
        (carpeta / "p001.txt").write_text("texto de prueba", encoding="utf-8")
        resultado = leer_numero(tmp_path, "enero_1939")
        assert "texto de prueba" in resultado

    def test_carga_multiples_txt(self, tmp_path):
        carpeta = tmp_path / "febrero_1939"
        carpeta.mkdir()
        (carpeta / "p001.txt").write_text("primero", encoding="utf-8")
        (carpeta / "p002.txt").write_text("segundo", encoding="utf-8")
        resultado = leer_numero(tmp_path, "febrero_1939")
        assert "primero" in resultado
        assert "segundo" in resultado

    def test_retorna_string(self, tmp_path):
        resultado = leer_numero(tmp_path, "no_existe")
        assert isinstance(resultado, str)

    def test_orden_alfabetico_de_paginas(self, tmp_path):
        carpeta = tmp_path / "num"
        carpeta.mkdir()
        (carpeta / "p001.txt").write_text("AAA", encoding="utf-8")
        (carpeta / "p002.txt").write_text("BBB", encoding="utf-8")
        resultado = leer_numero(tmp_path, "num")
        assert resultado.index("AAA") < resultado.index("BBB")

    def test_carpeta_vacia_retorna_vacio(self, tmp_path):
        carpeta = tmp_path / "vacia"
        carpeta.mkdir()
        resultado = leer_numero(tmp_path, "vacia")
        assert resultado == ""


# ══════════════════════════════════════════════════════════════════════════════
# construir_red
# ══════════════════════════════════════════════════════════════════════════════

class TestConstruirRed:
    def _df(self, filas):
        return pd.DataFrame(filas, columns=["numero", "firma"])

    def test_retorna_grafo_networkx(self):
        import networkx as nx
        df = self._df([
            ("n1", "García"), ("n1", "López"),
            ("n2", "García"), ("n2", "López"),
        ])
        G = construir_red(df, min_apariciones=1)
        assert isinstance(G, nx.Graph)

    def test_arista_por_coautoria(self):
        df = self._df([
            ("n1", "García"), ("n1", "López"),
        ])
        G = construir_red(df, min_apariciones=1)
        assert G.has_edge("García", "López")

    def test_sin_coautoria_sin_aristas(self):
        df = self._df([
            ("n1", "Solo_A"),
            ("n2", "Solo_B"),
        ])
        G = construir_red(df, min_apariciones=1)
        assert G.number_of_edges() == 0

    def test_min_apariciones_filtra(self):
        df = self._df([
            ("n1", "García"), ("n1", "López"),
            ("n2", "García"), ("n2", "López"),
            ("n3", "Raro"),   ("n3", "García"),
        ])
        G_1 = construir_red(df, min_apariciones=1)
        G_2 = construir_red(df, min_apariciones=3)
        assert G_2.number_of_nodes() <= G_1.number_of_nodes()

    def test_nodo_tiene_atributo_apariciones(self):
        df = self._df([("n1", "García"), ("n1", "López"), ("n2", "García")])
        G = construir_red(df, min_apariciones=1)
        for nodo in G.nodes():
            assert "apariciones" in G.nodes[nodo]

    def test_arista_tiene_peso(self):
        df = self._df([
            ("n1", "A"), ("n1", "B"),
            ("n2", "A"), ("n2", "B"),
        ])
        G = construir_red(df, min_apariciones=1)
        assert G["A"]["B"]["weight"] == 2

    def test_df_vacio_retorna_grafo_vacio(self):
        import networkx as nx
        df = self._df([])
        G = construir_red(df, min_apariciones=1)
        assert isinstance(G, nx.Graph)
        assert G.number_of_nodes() == 0


# ══════════════════════════════════════════════════════════════════════════════
# run_lda
# ══════════════════════════════════════════════════════════════════════════════

class TestRunLda:
    def _docs(self):
        # run_lda usa min_df=2, max_df=0.9 → término debe aparecer en ≥2 y ≤90% de docs
        # Con 10 docs, un término debe estar en 2-9 de ellos
        politica  = "política colombia bogotá gobierno república estado congreso presidente"
        cultura   = "literatura arte poesía novela música teatro escritor artista libro"
        economia  = "economía industria comercio empresa banco dinero mercado producción"
        guerra    = "guerra europa conflicto exilio refugiado nazismo mundial fascismo"
        comun     = "moderno progreso sociedad nacional ciudad"  # palabras comunes

        return [
            f"{politica} {comun}",
            f"{politica} {comun}",
            f"{politica} {comun}",
            f"{cultura}  {comun}",
            f"{cultura}  {comun}",
            f"{economia} {comun}",
            f"{economia} {comun}",
            f"{guerra}   {comun}",
            f"{guerra}   {comun}",
            f"{cultura}  {economia} {comun}",
        ]

    def test_retorna_dos_dataframes(self):
        docs = self._docs()
        df_temas, df_doc = run_lda(docs, [f"d{i}" for i in range(len(docs))], n_temas=2)
        assert isinstance(df_temas, pd.DataFrame)
        assert isinstance(df_doc, pd.DataFrame)

    def test_n_temas_correcto(self):
        docs = self._docs()
        df_temas, _ = run_lda(docs, [f"d{i}" for i in range(len(docs))], n_temas=3)
        assert len(df_temas) == 3

    def test_df_temas_tiene_palabras_clave(self):
        docs = self._docs()
        df_temas, _ = run_lda(docs, [f"d{i}" for i in range(len(docs))], n_temas=2)
        assert "palabras_clave" in df_temas.columns

    def test_df_doc_indice_son_nombres(self):
        docs = self._docs()
        nombres = [f"num_{i}" for i in range(len(docs))]
        _, df_doc = run_lda(docs, nombres, n_temas=2)
        for nombre in nombres:
            assert nombre in df_doc.index

    def test_df_doc_tiene_tema_dominante(self):
        docs = self._docs()
        _, df_doc = run_lda(docs, [f"d{i}" for i in range(len(docs))], n_temas=2)
        assert "tema_dominante" in df_doc.columns

    def test_distribuciones_suman_uno(self):
        import numpy as np
        docs = self._docs()
        _, df_doc = run_lda(docs, [f"d{i}" for i in range(len(docs))], n_temas=2)
        cols_tema = [c for c in df_doc.columns if c.startswith("tema_") and c != "tema_dominante"]
        sumas = df_doc[cols_tema].sum(axis=1)
        assert all(abs(s - 1.0) < 0.01 for s in sumas)

    def test_tema_dominante_entero(self):
        docs = self._docs()
        _, df_doc = run_lda(docs, [f"d{i}" for i in range(len(docs))], n_temas=2)
        for v in df_doc["tema_dominante"]:
            assert isinstance(int(v), int)
            assert 1 <= int(v) <= 2


# ══════════════════════════════════════════════════════════════════════════════
# analizar_numero_texto — con nlp mock (sin spaCy real)
# ══════════════════════════════════════════════════════════════════════════════

class TestAnalizarNumeroTexto:
    def _nlp_mock(self):
        """Mock de spaCy nlp que retorna doc vacío de entidades."""
        token_mock = MagicMock()
        token_mock.is_stop = True
        token_mock.is_punct = False
        token_mock.lemma_ = "palabra"

        doc_mock = MagicMock()
        doc_mock.ents = []
        doc_mock.__iter__ = MagicMock(return_value=iter([token_mock]))

        nlp = MagicMock()
        nlp.return_value = doc_mock
        return nlp

    def test_retorna_cuatro_elementos(self):
        from core.analysis_engine import analizar_numero_texto
        nlp = self._nlp_mock()
        resultado = analizar_numero_texto(
            "num_01",
            "texto de prueba moderado " * 20,
            colaboradores=["García"],
            nlp=nlp,
            stopwords=set(),
        )
        assert len(resultado) == 4

    def test_firmas_es_lista(self):
        from core.analysis_engine import analizar_numero_texto
        nlp = self._nlp_mock()
        firmas, _, _, _ = analizar_numero_texto(
            "n", "texto de prueba " * 20, [], nlp, set()
        )
        assert isinstance(firmas, list)

    def test_secciones_es_dict(self):
        from core.analysis_engine import analizar_numero_texto
        nlp = self._nlp_mock()
        _, secciones, _, _ = analizar_numero_texto(
            "n", "editorial crónica teatro cine " * 20, [], nlp, set()
        )
        assert isinstance(secciones, dict)

    def test_campos_es_dict(self):
        from core.analysis_engine import analizar_numero_texto
        nlp = self._nlp_mock()
        _, _, campos, _ = analizar_numero_texto(
            "n", "colombia bogotá gobierno " * 20, [], nlp, set()
        )
        assert isinstance(campos, dict)

    def test_lema_es_string(self):
        from core.analysis_engine import analizar_numero_texto
        nlp = self._nlp_mock()
        _, _, _, lema = analizar_numero_texto(
            "n", "texto prueba " * 20, [], nlp, set()
        )
        assert isinstance(lema, str)

    def test_colaborador_presente_detectado(self):
        from core.analysis_engine import analizar_numero_texto
        nlp = self._nlp_mock()
        texto = "En este artículo, García explica los hechos. " * 10
        firmas, _, _, _ = analizar_numero_texto(
            "n", texto, ["García"], nlp, set()
        )
        assert "García" in firmas

    def test_secciones_cuentan_patrones(self):
        from core.analysis_engine import analizar_numero_texto
        nlp = self._nlp_mock()
        texto = ("teatro teatro teatro " * 20)
        _, secciones, _, _ = analizar_numero_texto(
            "n", texto, [], nlp, set()
        )
        assert secciones.get("Teatro", 0) > 0

    def test_campos_sem_nacion_detectado(self):
        from core.analysis_engine import analizar_numero_texto
        nlp = self._nlp_mock()
        texto = "colombia bogotá república colombia colombia " * 20
        _, _, campos, _ = analizar_numero_texto(
            "n", texto, [], nlp, set()
        )
        assert campos.get("Nación", 0) > 0
