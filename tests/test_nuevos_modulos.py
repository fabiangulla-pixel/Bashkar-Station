"""tests/test_nuevos_modulos.py — Tests para los 7 módulos nuevos.

Cubre:
  article_segmenter_v2, collocation_engine, annotation_engine,
  visual_search (sin CLIP), visual_classifier (sin CLIP),
  novelty_engine, explainer
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ══════════════════════════════════════════════════════════════════════════════
# article_segmenter_v2
# ══════════════════════════════════════════════════════════════════════════════

class TestArticleSegmenterV2:
    from core.article_segmenter_v2 import (
        NodoPagina, _extraer_titulo, _extraer_autor, _contar_palabras,
        _similitud_coseno_simple, construir_grafo_continuidad,
        _componentes_conexas, comparar_segmentaciones,
    )

    def test_extraer_titulo_primera_linea_mayuscula(self):
        from core.article_segmenter_v2 import _extraer_titulo
        texto = "EL GRAN REPORTAJE\nEste es el cuerpo del artículo con más texto."
        t = _extraer_titulo(texto)
        assert len(t) > 0

    def test_extraer_autor_byline(self):
        from core.article_segmenter_v2 import _extraer_autor
        texto = "Por Juan García Morales\nEste es el texto del artículo."
        a = _extraer_autor(texto)
        assert "García" in a or "Juan" in a

    def test_contar_palabras(self):
        from core.article_segmenter_v2 import _contar_palabras
        assert _contar_palabras("hola mundo test") == 3
        assert _contar_palabras("") == 0
        assert _contar_palabras(None) == 0

    def test_similitud_coseno_simple_identico(self):
        from core.article_segmenter_v2 import _similitud_coseno_simple
        texto = "colombia bogotá prensa editorial artículo cultura política"
        assert _similitud_coseno_simple(texto, texto) == 1.0

    def test_similitud_coseno_simple_diferente(self):
        from core.article_segmenter_v2 import _similitud_coseno_simple
        a = "colombia bogotá cultura editorial prensa política artículo"
        b = "matemáticas física química biología laboratorio experimento resultado"
        sim = _similitud_coseno_simple(a, b)
        assert sim < 0.3

    def test_similitud_coseno_simple_vacio(self):
        from core.article_segmenter_v2 import _similitud_coseno_simple
        assert _similitud_coseno_simple("", "texto") == 0.0

    def test_componentes_conexas_sin_aristas(self):
        from core.article_segmenter_v2 import _componentes_conexas
        comps = _componentes_conexas(3, {})
        assert len(comps) == 3

    def test_componentes_conexas_cadena(self):
        from core.article_segmenter_v2 import _componentes_conexas
        grafo = {0: [1], 1: [2]}
        comps = _componentes_conexas(3, grafo)
        assert len(comps) == 1
        assert sorted(comps[0]) == [0, 1, 2]

    def test_componentes_conexas_dos_grupos(self):
        from core.article_segmenter_v2 import _componentes_conexas
        grafo = {0: [1]}
        comps = _componentes_conexas(4, grafo)
        assert len(comps) == 3  # {0,1}, {2}, {3}

    def test_construir_grafo_continua_explicita(self):
        from core.article_segmenter_v2 import NodoPagina, construir_grafo_continuidad
        p1 = NodoPagina(0, "texto artículo. Pasa a la Pág. 2", palabras=200)
        p2 = NodoPagina(1, "continuación del artículo texto más", palabras=150)
        grafo = construir_grafo_continuidad([p1, p2])
        assert 0 in grafo
        assert 1 in grafo[0]

    def test_construir_grafo_inicio_minuscula(self):
        from core.article_segmenter_v2 import NodoPagina, construir_grafo_continuidad
        p1 = NodoPagina(0, "texto final de la página anterior " * 5, palabras=50)
        p2 = NodoPagina(1, "continuando el relato de la historia anterior.", palabras=80)
        grafo = construir_grafo_continuidad([p1, p2])
        assert 0 in grafo

    def test_construir_grafo_pagina_especial_ignorada(self):
        from core.article_segmenter_v2 import NodoPagina, construir_grafo_continuidad
        p1 = NodoPagina(0, "texto normal " * 20, palabras=200, es_especial=False)
        p2 = NodoPagina(1, "publicidad", palabras=5, es_especial=True)
        p3 = NodoPagina(2, "otro artículo " * 20, palabras=200, es_especial=False)
        grafo = construir_grafo_continuidad([p1, p2, p3])
        assert 1 not in grafo

    def test_comparar_segmentaciones(self):
        from core.article_segmenter_v2 import comparar_segmentaciones, ArticuloSegmentado
        v1 = [{"titulo": f"art{i}"} for i in range(5)]
        v2 = [
            ArticuloSegmentado([0, 1], "texto", "t", "", "", "n1", 100, 0.9, "explicito"),
            ArticuloSegmentado([2], "texto", "t", "", "", "n1", 80, 0.95, "atomico"),
            ArticuloSegmentado([3, 4], "texto", "t", "", "", "n1", 120, 0.75, "semantico"),
        ]
        comp = comparar_segmentaciones(v1, v2)
        assert comp["v1_articulos"] == 5
        assert comp["v2_articulos"] == 3
        assert comp["delta"] == -2
        assert 0.0 <= comp["v2_confianza_media"] <= 1.0

    def test_segmentar_avanzado_basico(self):
        from core.article_segmenter_v2 import segmentar_avanzado
        paginas = [
            "LA GRAN CRÓNICA\nPor Juan García\nEste es el texto principal del artículo sobre Colombia en 1939. " * 5,
            "continuando la historia del artículo anterior con más detalles sobre los eventos. " * 5,
            "NUEVO ARTÍCULO\nOtro tema completamente diferente sobre política y gobierno. " * 5,
        ]
        arts = segmentar_avanzado(paginas, numero="ene1939")
        assert len(arts) >= 1
        assert all(hasattr(a, "texto") for a in arts)
        assert all(0.0 <= a.confianza <= 1.0 for a in arts)


# ══════════════════════════════════════════════════════════════════════════════
# collocation_engine
# ══════════════════════════════════════════════════════════════════════════════

CORPUS_TEST = [
    "colombia bogotá cultura editorial prensa artículo político social mujer " * 10,
    "medellín barranquilla política gobierno congreso partido liberal " * 8,
    "prensa colombia cultura artículo editorial bogotá publicación " * 12,
]


class TestCollocationEngine:
    def test_collocates_retorna_lista(self):
        from core.collocation_engine import collocates
        res = collocates(CORPUS_TEST, "colombia", top_n=10)
        assert isinstance(res, list)

    def test_collocates_campos_requeridos(self):
        from core.collocation_engine import collocates
        res = collocates(CORPUS_TEST, "colombia", top_n=5)
        if res:
            assert "palabra" in res[0]
            assert "frecuencia" in res[0]
            assert "pmi" in res[0]

    def test_collocates_palabra_ausente(self):
        from core.collocation_engine import collocates
        res = collocates(CORPUS_TEST, "xyzpalabra", top_n=10)
        assert res == []

    def test_collocates_string_simple(self):
        from core.collocation_engine import collocates
        texto = "colombia bogotá cultura prensa editorial artículo " * 20
        res = collocates(texto, "colombia", top_n=5)
        assert isinstance(res, list)

    def test_red_lexica_estructura(self):
        from core.collocation_engine import red_lexica
        red = red_lexica(CORPUS_TEST, top_n_nodos=15)
        assert "nodos" in red
        assert "aristas" in red
        assert "total_tokens" in red
        assert "vocabulario" in red

    def test_red_lexica_con_palabras_clave(self):
        from core.collocation_engine import red_lexica
        red = red_lexica(CORPUS_TEST, palabras_clave=["colombia", "cultura", "prensa"])
        assert len(red["nodos"]) <= 3

    def test_concordancias_retorna_lista(self):
        from core.collocation_engine import concordancias
        res = concordancias(CORPUS_TEST, "colombia", max_resultados=5)
        assert isinstance(res, list)
        assert len(res) <= 5

    def test_concordancias_campos(self):
        from core.collocation_engine import concordancias
        res = concordancias(CORPUS_TEST, "colombia")
        if res:
            assert "izquierda" in res[0]
            assert "kwic" in res[0]
            assert "derecha" in res[0]

    def test_frecuencias_global(self):
        from core.collocation_engine import frecuencias
        res = frecuencias(CORPUS_TEST, top_n=10)
        assert isinstance(res, list)
        assert len(res) <= 10
        if res:
            assert "palabra" in res[0]
            assert "freq" in res[0]

    def test_frecuencias_por_documento(self):
        from core.collocation_engine import frecuencias
        res = frecuencias(CORPUS_TEST, top_n=5, por_documento=True)
        assert isinstance(res, dict)
        assert 0 in res
        assert isinstance(res[0], list)

    def test_dispersion_retorna_posiciones(self):
        from core.collocation_engine import dispersion
        res = dispersion(CORPUS_TEST, ["colombia", "cultura"])
        assert "colombia" in res
        assert "cultura" in res
        assert isinstance(res["colombia"], list)
        assert all(0.0 <= p <= 1.0 for p in res["colombia"])

    def test_dispersion_palabra_ausente(self):
        from core.collocation_engine import dispersion
        res = dispersion(CORPUS_TEST, ["xyzpalabra"])
        assert res["xyzpalabra"] == []


# ══════════════════════════════════════════════════════════════════════════════
# annotation_engine
# ══════════════════════════════════════════════════════════════════════════════

class TestAnnotationEngine:
    def test_insertar_y_consultar(self, tmp_path):
        from core.annotation_engine import GestorAnotaciones, Anotacion
        db = str(tmp_path / "test.db")
        g = GestorAnotaciones(db)
        anot = Anotacion("art1", "García", "García", "PER", 10, 16, confianza=0.9)
        id_ = g.insertar(anot)
        assert id_ > 0
        rows = g.por_articulo("art1")
        assert len(rows) == 1
        assert rows[0]["texto_norm"] == "García"

    def test_actualizar_con_historial(self, tmp_path):
        from core.annotation_engine import GestorAnotaciones, Anotacion
        db = str(tmp_path / "test.db")
        g = GestorAnotaciones(db)
        id_ = g.insertar(Anotacion("art1", "García", "García", "PER"))
        ok = g.actualizar(id_, {"estado": "confirmada", "notas": "revisado"}, "corrección manual")
        assert ok
        hist = g.historial(id_)
        assert len(hist) >= 1
        assert any(h["campo"] == "estado" for h in hist)

    def test_actualizar_estado_invalido(self, tmp_path):
        from core.annotation_engine import GestorAnotaciones, Anotacion
        db = str(tmp_path / "test.db")
        g = GestorAnotaciones(db)
        id_ = g.insertar(Anotacion("art1", "x", "x", "PER"))
        with pytest.raises(ValueError):
            g.actualizar(id_, {"estado": "estado_invalido"})

    def test_insertar_lote(self, tmp_path):
        from core.annotation_engine import GestorAnotaciones, Anotacion
        db = str(tmp_path / "test.db")
        g = GestorAnotaciones(db)
        anots = [Anotacion(f"art{i}", f"ent{i}", f"ent{i}", "PER") for i in range(5)]
        n = g.insertar_lote(anots)
        assert n == 5

    def test_pendientes(self, tmp_path):
        from core.annotation_engine import GestorAnotaciones, Anotacion
        db = str(tmp_path / "test.db")
        g = GestorAnotaciones(db)
        g.insertar(Anotacion("a1", "x", "x", "PER", estado="auto"))
        g.insertar(Anotacion("a2", "y", "y", "LOC", estado="confirmada"))
        pend = g.pendientes()
        assert len(pend) == 1
        assert pend[0]["estado"] == "auto"

    def test_estadisticas(self, tmp_path):
        from core.annotation_engine import GestorAnotaciones, Anotacion
        db = str(tmp_path / "test.db")
        g = GestorAnotaciones(db)
        g.insertar(Anotacion("a1", "x", "x", "PER", estado="auto"))
        g.insertar(Anotacion("a2", "y", "y", "LOC", estado="confirmada"))
        stats = g.estadisticas()
        assert stats["total"] == 2
        assert "auto" in stats["por_estado"]
        assert "PER" in stats["por_categoria"]

    def test_exportar_json(self, tmp_path):
        from core.annotation_engine import GestorAnotaciones, Anotacion
        db = str(tmp_path / "test.db")
        g = GestorAnotaciones(db)
        g.insertar(Anotacion("a1", "García", "García", "PER", estado="confirmada"))
        dest = tmp_path / "out.json"
        n = g.exportar_json(dest, solo_confirmadas=True)
        assert n == 1
        assert dest.exists()

    def test_filtrar_por_categoria(self, tmp_path):
        from core.annotation_engine import GestorAnotaciones, Anotacion
        db = str(tmp_path / "test.db")
        g = GestorAnotaciones(db)
        g.insertar(Anotacion("a1", "García", "García", "PER"))
        g.insertar(Anotacion("a1", "Bogotá", "Bogotá", "LOC"))
        per = g.por_articulo("a1", categoria="PER")
        assert len(per) == 1
        assert per[0]["categoria"] == "PER"

    def test_importar_desde_ner(self, tmp_path):
        from core.annotation_engine import GestorAnotaciones
        db = str(tmp_path / "test.db")
        g = GestorAnotaciones(db)
        ner = {
            "art1": {
                "PER": [{"texto": "García", "inicio": 0, "fin": 6, "confianza": 0.9}],
                "LOC": [{"texto": "Bogotá", "inicio": 10, "fin": 16, "confianza": 0.8}],
            }
        }
        n = g.importar_desde_ner(ner)
        assert n == 2
        rows = g.por_articulo("art1")
        assert len(rows) == 2


# ══════════════════════════════════════════════════════════════════════════════
# visual_search (sin CLIP)
# ══════════════════════════════════════════════════════════════════════════════

class TestVisualSearch:
    def test_indice_visual_vacio(self):
        from core.visual_search import IndiceVisual
        idx = IndiceVisual()
        assert len(idx) == 0

    def test_indice_visual_agregar(self):
        from core.visual_search import IndiceVisual
        import numpy as np
        idx = IndiceVisual()
        emb = np.random.randn(512).astype("float32")
        emb /= np.linalg.norm(emb)
        idx.agregar(emb, {"ruta": "test.png", "numero": "n1"})
        assert len(idx) == 1

    def test_guardar_cargar(self, tmp_path):
        from core.visual_search import IndiceVisual
        import numpy as np
        # FAISS no soporta rutas con caracteres no-ASCII en Windows
        # Usar ruta ASCII explícita en temp
        import tempfile, os
        ruta_ascii = os.path.join(tempfile.gettempdir(), "bashkar_test_indice")
        idx = IndiceVisual()
        for i in range(3):
            emb = np.random.randn(512).astype("float32")
            emb /= np.linalg.norm(emb)
            idx.agregar(emb, {"ruta": f"img{i}.png"})
        try:
            idx.guardar(ruta_ascii)
            idx2 = IndiceVisual.cargar(ruta_ascii)
            assert len(idx2) == 3
        finally:
            for ext in (".faiss", ".meta.json", ".npy"):
                p = ruta_ascii + ext
                if os.path.exists(p):
                    os.remove(p)

    def test_clip_disponible_retorna_bool(self):
        from core.visual_search import clip_disponible
        resultado = clip_disponible()
        assert isinstance(resultado, bool)

    def test_buscar_sin_faiss_retorna_vacio(self):
        from core.visual_search import IndiceVisual
        import numpy as np
        idx = IndiceVisual()
        emb = np.random.randn(512).astype("float32")
        try:
            res = idx.buscar(emb, top_k=5)
            assert res == []
        except ImportError:
            pytest.skip("faiss-cpu no instalado")


# ══════════════════════════════════════════════════════════════════════════════
# visual_classifier (sin CLIP)
# ══════════════════════════════════════════════════════════════════════════════

class TestVisualClassifier:
    def test_categorias_definidas(self):
        from core.visual_classifier import CATEGORIAS
        assert len(CATEGORIAS) == 8
        assert "fotografía" in CATEGORIAS
        assert "anuncio publicitario" in CATEGORIAS

    def test_colores_para_todas_categorias(self):
        from core.visual_classifier import CATEGORIAS, COLORES_CATEGORIA
        for cat in CATEGORIAS:
            assert cat in COLORES_CATEGORIA

    def test_clip_disponible_retorna_bool(self):
        from core.visual_classifier import clip_disponible
        assert isinstance(clip_disponible(), bool)

    def test_estadisticas_clasificacion(self):
        from core.visual_classifier import estadisticas_clasificacion
        resultados = [
            {"categoria": "fotografía", "confianza": 0.8, "metodo": "clip"},
            {"categoria": "fotografía", "confianza": 0.7, "metodo": "clip"},
            {"categoria": "anuncio publicitario", "confianza": 0.6, "metodo": "opencv"},
        ]
        stats = estadisticas_clasificacion(resultados)
        assert stats["total"] == 3
        assert "fotografía" in stats["distribucion"]
        assert stats["distribucion"]["fotografía"]["n"] == 2
        assert stats["distribucion"]["fotografía"]["pct"] == pytest.approx(66.7, abs=0.1)

    def test_estadisticas_vacio(self):
        from core.visual_classifier import estadisticas_clasificacion
        stats = estadisticas_clasificacion([])
        assert stats["total"] == 0

    def test_clasificar_opencv_imagen_png(self, tmp_path):
        from core.visual_classifier import _clasificar_opencv
        try:
            from PIL import Image
            img_path = str(tmp_path / "test.png")
            Image.new("L", (100, 100), color=200).save(img_path)
            res = _clasificar_opencv(img_path)
            assert "categoria" in res
            assert res["categoria"] in [
                "fotografía", "ilustración", "mapa", "cómic o historieta",
                "caricatura editorial", "anuncio publicitario",
                "titular tipográfico", "texto de artículo"
            ]
        except ImportError:
            pytest.skip("PIL no disponible")


# ══════════════════════════════════════════════════════════════════════════════
# novelty_engine
# ══════════════════════════════════════════════════════════════════════════════

CORPUS_PERIODOS = {
    "ene1939": [
        "colombia bogotá cultura editorial prensa artículo político social " * 10,
        "medellín liberal partido gobierno congreso senado ministro " * 8,
    ],
    "feb1939": [
        "radio cine película teatro espectáculo entretenimiento música " * 10,
        "colombia bogotá cultura artículo editorial política gobierno " * 8,
    ],
    "mar1939": [
        "guerra europa fascismo internacional conflicto alemania " * 10,
        "radio colombia guerra fascismo internacional conflicto " * 8,
    ],
}


class TestNoveltyEngine:
    def test_palabras_nuevas_retorna_dict(self):
        from core.novelty_engine import palabras_nuevas
        res = palabras_nuevas(CORPUS_PERIODOS)
        assert isinstance(res, dict)
        assert set(res.keys()) == set(CORPUS_PERIODOS.keys())

    def test_palabras_nuevas_primer_periodo_tiene_mas(self):
        from core.novelty_engine import palabras_nuevas
        res = palabras_nuevas(CORPUS_PERIODOS, min_freq=2)
        # El primer período siempre tiene más palabras nuevas (todo es nuevo)
        assert len(res["ene1939"]) >= len(res["mar1939"])

    def test_cambio_discursivo_retorna_lista(self):
        from core.novelty_engine import cambio_discursivo
        res = cambio_discursivo(CORPUS_PERIODOS)
        assert isinstance(res, list)
        assert len(res) == len(CORPUS_PERIODOS) - 1

    def test_cambio_discursivo_campos(self):
        from core.novelty_engine import cambio_discursivo
        res = cambio_discursivo(CORPUS_PERIODOS)
        for r in res:
            assert "periodo_a" in r
            assert "periodo_b" in r
            assert "distancia" in r
            assert 0.0 <= r["distancia"] <= 2.0
            assert "palabras_ganadas" in r
            assert "palabras_perdidas" in r

    def test_cambio_discursivo_ordenado_por_distancia(self):
        from core.novelty_engine import cambio_discursivo
        res = cambio_discursivo(CORPUS_PERIODOS)
        distancias = [r["distancia"] for r in res]
        assert distancias == sorted(distancias, reverse=True)

    def test_detectar_eventos_retorna_lista(self):
        from core.novelty_engine import detectar_eventos
        articulos = [
            {"texto": "colombia editorial prensa cultura bogotá artículo " * 8,
             "titulo": f"Art {i}", "numero": f"num{i % 2 + 1}"}
            for i in range(8)
        ]
        res = detectar_eventos(articulos)
        assert isinstance(res, list)

    def test_tendencia_vocabulario(self):
        from core.novelty_engine import tendencia_vocabulario
        res = tendencia_vocabulario(CORPUS_PERIODOS, ["radio", "guerra", "colombia"])
        assert "radio" in res
        assert "guerra" in res
        assert set(res["radio"].keys()) == set(CORPUS_PERIODOS.keys())
        # "radio" debería tener frecuencia 0 en ene1939 y mayor en feb1939
        assert res["radio"]["ene1939"] == pytest.approx(0.0, abs=0.5)
        assert res["radio"]["feb1939"] > 0

    def test_tendencia_palabra_ausente(self):
        from core.novelty_engine import tendencia_vocabulario
        res = tendencia_vocabulario(CORPUS_PERIODOS, ["xyzpalabra"])
        for periodo, freq in res["xyzpalabra"].items():
            assert freq == 0.0


# ══════════════════════════════════════════════════════════════════════════════
# explainer
# ══════════════════════════════════════════════════════════════════════════════

class TestExplainer:
    def _resultado_mock(self, similitud=0.75):
        return {
            "texto": "colombia bogotá cultura editorial prensa artículo político " * 5,
            "titulo": "La cultura en Colombia",
            "similitud": similitud,
            "numero": "ene1939",
            "seccion": "cultura",
            "art_id": "art1",
        }

    def test_explicar_estructura(self):
        from core.explainer import explicar_resultado
        exp = explicar_resultado("cultura colombia", self._resultado_mock())
        assert "similitud_semantica" in exp
        assert "terminos_relevantes" in exp
        assert "fragmento_relevante" in exp
        assert "procedencia" in exp
        assert "resumen_explicacion" in exp

    def test_explicar_similitud_preservada(self):
        from core.explainer import explicar_resultado
        exp = explicar_resultado("cultura", self._resultado_mock(0.82))
        assert exp["similitud_semantica"] == pytest.approx(0.82, abs=0.01)

    def test_terminos_relevantes_contienen_query(self):
        from core.explainer import explicar_resultado
        exp = explicar_resultado("cultura colombia", self._resultado_mock())
        terminos = [t["termino"] for t in exp["terminos_relevantes"]]
        assert any(t in terminos for t in ["cultura", "colombia"])

    def test_procedencia_correcta(self):
        from core.explainer import explicar_resultado
        exp = explicar_resultado("colombia", self._resultado_mock())
        assert exp["procedencia"]["numero"] == "ene1939"
        assert exp["procedencia"]["seccion"] == "cultura"

    def test_explicar_lote(self):
        from core.explainer import explicar_lote
        resultados = [self._resultado_mock(0.8), self._resultado_mock(0.6)]
        exps = explicar_lote("cultura colombia", resultados)
        assert len(exps) == 2
        assert all("explicacion" in e for e in exps)

    def test_construir_corpus_freq(self):
        from core.explainer import construir_corpus_freq
        textos = ["colombia bogotá cultura " * 5, "prensa editorial artículo " * 5]
        freq = construir_corpus_freq(textos)
        assert "colombia" in freq
        assert freq["colombia"] >= 1

    def test_resumir_busqueda_sin_resultados(self):
        from core.explainer import resumir_busqueda
        res = resumir_busqueda("colombia", [])
        assert "No se encontraron" in res

    def test_resumir_busqueda_con_resultados(self):
        from core.explainer import resumir_busqueda, explicar_resultado
        resultados = [self._resultado_mock(0.75)]
        exps = [{"explicacion": explicar_resultado("cultura colombia", r)}
                for r in resultados]
        resumen = resumir_busqueda("cultura colombia", exps)
        assert isinstance(resumen, str)
        assert len(resumen) > 20

    def test_resumen_menciona_query(self):
        from core.explainer import resumir_busqueda, explicar_resultado
        resultados = [self._resultado_mock()]
        exps = [{"explicacion": explicar_resultado("cultura", r)} for r in resultados]
        resumen = resumir_busqueda("cultura", exps)
        assert "cultura" in resumen.lower()
