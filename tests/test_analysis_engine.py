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

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.analysis_engine import (
    CAMPOS_SEM,
    SECCIONES,
    construir_red,
    leer_numero,
    run_lda,
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


# ══════════════════════════════════════════════════════════════════════════════
# Filtro de firmas / word-boundary de secciones — regresión hallazgo s.59/60
# (firmas.csv mezclaba autores reales con empresas/cargos/basura OCR porque el
# NER y la regex de mayúsculas no filtraban por forma de nombre de persona;
# SECCIONES repetía el mismo bug de subcadena sin \b ya corregido en
# article_segmenter). Ver [[project_bashkar_station]].
# ══════════════════════════════════════════════════════════════════════════════

class TestFirmasFiltradasYSeccionesConLimiteDePalabra:
    def _nlp_mock(self):
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

    def _entidad_mock(self, texto, label="PER"):
        ent = MagicMock()
        ent.text = texto
        ent.label_ = label
        return ent

    def _nlp_mock_con_entidades(self, entidades):
        token_mock = MagicMock()
        token_mock.is_stop = True
        token_mock.is_punct = False
        token_mock.lemma_ = "palabra"

        doc_mock = MagicMock()
        doc_mock.ents = entidades
        doc_mock.__iter__ = MagicMock(return_value=iter([token_mock]))

        nlp = MagicMock()
        nlp.return_value = doc_mock
        return nlp

    def test_firmas_excluye_entidad_ner_institucional(self):
        """Una entidad PER de spaCy que en realidad es una empresa/cargo
        ("Filmadora Kodak", "Secretario de Estado") no debe colarse como
        firma de autor."""
        from core.analysis_engine import analizar_numero_texto
        nlp = self._nlp_mock_con_entidades([
            self._entidad_mock("Filmadora Kodak"),
            self._entidad_mock("Secretario de Estado"),
        ])
        firmas, _, _, _ = analizar_numero_texto(
            "n", "texto de prueba " * 20, [], nlp, set()
        )
        assert "Filmadora Kodak" not in firmas
        assert "Secretario de Estado" not in firmas

    def test_firmas_conserva_entidad_ner_nombre_real(self):
        from core.analysis_engine import analizar_numero_texto
        nlp = self._nlp_mock_con_entidades([
            self._entidad_mock("Juan Gómez Salazar"),
        ])
        firmas, _, _, _ = analizar_numero_texto(
            "n", "texto de prueba " * 20, [], nlp, set()
        )
        assert "Juan Gómez Salazar" in firmas

    def test_firmas_excluye_mayusculas_cargo_institucional(self):
        """La regex de línea ALL-CAPS (firma final tipográfica) también debe
        pasar por el filtro de nombre de persona, no solo el NER."""
        from core.analysis_engine import analizar_numero_texto
        nlp = self._nlp_mock()
        texto = "Cuerpo del artículo.\nSECRETARIO DE ESTADO\nMás texto de relleno " * 5
        firmas, _, _, _ = analizar_numero_texto("n", texto, [], nlp, set())
        assert "Secretario De Estado" not in firmas

    def test_firmas_conserva_mayusculas_nombre_real(self):
        from core.analysis_engine import analizar_numero_texto
        nlp = self._nlp_mock()
        texto = "Cuerpo del artículo.\nJUAN PEREZ GOMEZ\nMás texto de relleno " * 5
        firmas, _, _, _ = analizar_numero_texto("n", texto, [], nlp, set())
        assert "Juan Perez Gomez" in firmas

    def test_secciones_no_matchea_subcadena_sin_limite_de_palabra(self):
        """'verso' (Poema/Verso) no debe dispararse dentro de 'diversas' /
        'conversación' — mismo bug corregido en article_segmenter s.59,
        replicado aquí porque analysis_engine tiene su propio SECCIONES."""
        from core.analysis_engine import analizar_numero_texto
        nlp = self._nlp_mock()
        texto = "Se presentaron diversas prendas en la conversación social. " * 10
        _, secciones, _, _ = analizar_numero_texto("n", texto, [], nlp, set())
        assert "Poema/Verso" not in secciones

    def test_secciones_conserva_verso_real(self):
        from core.analysis_engine import analizar_numero_texto
        nlp = self._nlp_mock()
        texto = "El poeta escribió un hermoso poema con versos a la primavera. " * 10
        _, secciones, _, _ = analizar_numero_texto("n", texto, [], nlp, set())
        assert secciones.get("Poema/Verso", 0) > 0

    def test_secciones_extendidas_tambien_usa_limite_de_palabra(self):
        """analizar_numero_con_campos_expandidos comparte el mismo bug de
        SECCIONES sin \\b — verificado por separado porque es una función
        distinta con su propia copia del bucle de conteo."""
        from core.analysis_engine import analizar_numero_con_campos_expandidos
        nlp = self._nlp_mock()
        texto = "Se presentaron diversas prendas en la conversación social. " * 10
        _, secciones, _, _ = analizar_numero_con_campos_expandidos(
            "n", texto, [], nlp, set()
        )
        assert "Poema/Verso" not in secciones
