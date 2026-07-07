"""
tests/test_linguistica.py — Tests para el módulo de Lingüística Computacional v11.4.

Cubre:
  - sintaxis_engine: concordancias sintácticas, extracción relaciones, agrupación
  - coref_engine: correferencia heurística, cadenas, densidad referencial
  - morfologia_historica: normalización, lematización, densidad histórica, glosario
  - sentiment_engine: emociones, subjetividad, intensidad, análisis completo
"""

import pytest

# ── Corpus de prueba ──────────────────────────────────────────────────────────

CORPUS_HISTORICO = [
    "Francisco Franco visitó Bogotá en enero de 1939. El presidente habló en el Capitolio.",
    "La revista Estampa publicó fotografías de la exposición artística en Medellín.",
    "El señor habla con gran entusiasmo. Él pronunció un discurso memorable en el teatro.",
    "El Ministerio de Educación anunció nuevas becas para estudiantes colombianos.",
    "No se puede negar que la situación política era grave en aquel momento histórico.",
    "Luis Carlos López presentó su libro con alegría y júbilo en la Biblioteca Nacional.",
    "La compañía Casa Muñoz Hermanos inauguró su sede en La Candelaria.",
    "El poeta habia llegado á Bogotá en fué el año 1939. Señor presidente.",
]

TEXTO_COREF = (
    "El general Alfonso López visitó el Congreso. "
    "Él pronunció un discurso sobre la reforma agraria. "
    "Lo aplaudieron con entusiasmo. "
    "El presidente insistió en la necesidad de cambios."
)

TEXTO_HISTORICO = (
    "El señor habia llegado á Bogotá. Fué recibido con grandes honores. "
    "La republica atravesaba momentos difíciles. "
    "Hubiera sido posible evitar el conflicto."
)

TEXTO_EMOCIONAL = (
    "Con gran alegría y júbilo celebramos el triunfo de la patria. "
    "El glorioso ejército nacional venció con honor y patriotismo. "
    "Lamentablemente, algunos ciudadanos padecen miseria y sufrimiento."
)

TEXTO_FACTUAL = (
    "Según datos oficiales, el número de estudiantes ascendió a 1500. "
    "El informe señala que la fecha límite es el 30 de enero. "
    "Los reportes indican que el total de afectados fue de 200 personas."
)


# ═══════════════════════════════════════════════════════════════════════════════
# SINTAXIS ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class TestSintaxisEngine:

    def test_importar_modulo(self):
        import core.sintaxis_engine as se
        assert hasattr(se, "analizar_dependencias")
        assert hasattr(se, "concordancias_sintaticas")
        assert hasattr(se, "extraer_relaciones")
        assert hasattr(se, "agrupar_relaciones")
        assert hasattr(se, "exportar_relaciones_csv")

    def test_patrones_disponibles(self):
        from core.sintaxis_engine import PATRONES_SINTACTICOS
        assert "verbo_sujeto" in PATRONES_SINTACTICOS
        assert "verbo_objeto" in PATRONES_SINTACTICOS
        assert "sustantivo_adj" in PATRONES_SINTACTICOS
        assert "entidad_verbo" in PATRONES_SINTACTICOS
        assert "negacion" in PATRONES_SINTACTICOS

    def test_analizar_dependencias_estructura(self):
        from core.sintaxis_engine import analizar_dependencias
        try:
            res = analizar_dependencias(CORPUS_HISTORICO[0])
            assert isinstance(res, list)
            if res:
                orac = res[0]
                assert "oracion" in orac
                assert "tokens" in orac
                assert isinstance(orac["tokens"], list)
        except ImportError:
            pytest.skip("spaCy no disponible")

    def test_analizar_dependencias_texto_vacio(self):
        from core.sintaxis_engine import analizar_dependencias
        try:
            res = analizar_dependencias("")
            assert res == []
        except ImportError:
            pytest.skip("spaCy no disponible")

    def test_resumir_arbol_con_sujeto_verbo(self):
        from core.sintaxis_engine import resumir_arbol_dep
        info = {"oracion": "Franco visitó Bogotá.",
                "sujeto": "Franco", "verbo": "visitar", "objeto": "Bogotá"}
        resumen = resumir_arbol_dep(info)
        assert "Franco" in resumen
        assert "visitar" in resumen
        assert "Bogotá" in resumen

    def test_resumir_arbol_sin_datos(self):
        from core.sintaxis_engine import resumir_arbol_dep
        info = {"oracion": "Texto de prueba.", "sujeto": None,
                "verbo": None, "objeto": None}
        resumen = resumir_arbol_dep(info)
        assert isinstance(resumen, str)
        assert len(resumen) > 0

    def test_concordancias_retorna_lista(self):
        from core.sintaxis_engine import concordancias_sintaticas
        try:
            res = concordancias_sintaticas(CORPUS_HISTORICO, patron="negacion")
            assert isinstance(res, list)
            # La oración con "No se puede negar" debe detectarse
        except ImportError:
            pytest.skip("spaCy no disponible")

    def test_concordancias_estructura_resultado(self):
        from core.sintaxis_engine import concordancias_sintaticas
        try:
            res = concordancias_sintaticas(CORPUS_HISTORICO, patron="verbo_sujeto")
            for r in res:
                assert "patron" in r
                assert "texto_completo" in r
                assert "match_principal" in r
                assert "match_secundario" in r
                assert "doc_idx" in r
        except ImportError:
            pytest.skip("spaCy no disponible")

    def test_concordancias_max_resultados(self):
        from core.sintaxis_engine import concordancias_sintaticas
        try:
            res = concordancias_sintaticas(CORPUS_HISTORICO * 20,
                                           patron="verbo_sujeto",
                                           max_resultados=5)
            assert len(res) <= 5
        except ImportError:
            pytest.skip("spaCy no disponible")

    def test_extraer_relaciones_retorna_lista(self):
        from core.sintaxis_engine import extraer_relaciones
        try:
            res = extraer_relaciones(CORPUS_HISTORICO, solo_entidades=False)
            assert isinstance(res, list)
        except ImportError:
            pytest.skip("spaCy no disponible")

    def test_extraer_relaciones_estructura(self):
        from core.sintaxis_engine import extraer_relaciones
        try:
            res = extraer_relaciones(CORPUS_HISTORICO, solo_entidades=False,
                                     min_confianza=0.3)
            for r in res:
                assert "sujeto" in r
                assert "relacion" in r
                assert "objeto" in r
                assert "confianza" in r
                assert 0.0 <= r["confianza"] <= 1.0
                assert "oracion" in r
        except ImportError:
            pytest.skip("spaCy no disponible")

    def test_agrupar_relaciones_vacio(self):
        from core.sintaxis_engine import agrupar_relaciones
        res = agrupar_relaciones([])
        assert isinstance(res, dict)
        assert len(res) == 0

    def test_agrupar_relaciones_agrupa_por_verbo(self):
        from core.sintaxis_engine import agrupar_relaciones
        rels = [
            {"sujeto": "Franco", "relacion": "visitar", "objeto": "Bogotá",
             "sujeto_tipo": "PER", "objeto_tipo": "LOC",
             "confianza": 0.8, "oracion": "...", "doc_idx": 0},
            {"sujeto": "López", "relacion": "visitar", "objeto": "Medellín",
             "sujeto_tipo": "PER", "objeto_tipo": "LOC",
             "confianza": 0.7, "oracion": "...", "doc_idx": 1},
            {"sujeto": "Estampa", "relacion": "publicar", "objeto": "foto",
             "sujeto_tipo": "ORG", "objeto_tipo": "",
             "confianza": 0.6, "oracion": "...", "doc_idx": 2},
        ]
        agrup = agrupar_relaciones(rels)
        assert "visitar" in agrup
        assert agrup["visitar"]["n"] == 2
        assert "publicar" in agrup

    def test_exportar_relaciones_csv(self, tmp_path):
        from core.sintaxis_engine import exportar_relaciones_csv
        rels = [
            {"sujeto": "Franco", "sujeto_tipo": "PER", "relacion": "visitar",
             "objeto": "Bogotá", "objeto_tipo": "LOC", "confianza": 0.8,
             "oracion": "Franco visitó Bogotá.", "doc_idx": 0},
        ]
        ruta = tmp_path / "relaciones.csv"
        exportar_relaciones_csv(rels, ruta)
        assert ruta.exists()
        contenido = ruta.read_text(encoding="utf-8-sig")
        assert "Franco" in contenido
        assert "visitar" in contenido


# ═══════════════════════════════════════════════════════════════════════════════
# COREF ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class TestCorefEngine:

    def test_importar_modulo(self):
        import core.coref_engine as ce
        assert hasattr(ce, "resolver_correferencias")
        assert hasattr(ce, "cadena_referencial")
        assert hasattr(ce, "sustituir_referencias")
        assert hasattr(ce, "estadisticas_coref")

    def test_pronombres_definidos(self):
        from core.coref_engine import _PRONOMBRES_3P
        assert "él" in _PRONOMBRES_3P
        assert "ella" in _PRONOMBRES_3P
        assert "ellos" in _PRONOMBRES_3P
        assert "su" in _PRONOMBRES_3P

    def test_resolver_texto_vacio(self):
        from core.coref_engine import resolver_correferencias
        try:
            res = resolver_correferencias("")
            assert res == []
        except ImportError:
            pytest.skip("spaCy no disponible")

    def test_resolver_retorna_lista(self):
        from core.coref_engine import resolver_correferencias
        try:
            res = resolver_correferencias(TEXTO_COREF)
            assert isinstance(res, list)
        except ImportError:
            pytest.skip("spaCy no disponible")

    def test_cadenas_tienen_estructura(self):
        from core.coref_engine import resolver_correferencias
        try:
            res = resolver_correferencias(TEXTO_COREF)
            for cadena in res:
                assert "entidad_principal" in cadena
                assert "n_menciones" in cadena
                assert "menciones" in cadena
                assert isinstance(cadena["menciones"], list)
                assert cadena["n_menciones"] >= 1
        except ImportError:
            pytest.skip("spaCy no disponible")

    def test_cadena_referencial_directa(self):
        from core.coref_engine import cadena_referencial
        try:
            res = cadena_referencial(TEXTO_COREF, "López")
            assert isinstance(res, dict)
            assert "menciones" in res
            assert "n_menciones" in res
        except ImportError:
            pytest.skip("spaCy no disponible")

    def test_estadisticas_coref_estructura(self):
        from core.coref_engine import estadisticas_coref
        try:
            stats = estadisticas_coref([TEXTO_COREF])
            assert "total_cadenas" in stats
            assert "densidad_referencial" in stats
            assert "total_pronombres" in stats
            assert "total_tokens" in stats
            assert 0.0 <= stats["densidad_referencial"] <= 1.0
        except ImportError:
            pytest.skip("spaCy no disponible")

    def test_estadisticas_corpus_vacio(self):
        from core.coref_engine import estadisticas_coref
        try:
            stats = estadisticas_coref([])
            assert stats["total_cadenas"] == 0
            assert stats["densidad_referencial"] == 0
        except ImportError:
            pytest.skip("spaCy no disponible")


# ═══════════════════════════════════════════════════════════════════════════════
# MORFOLOGÍA HISTÓRICA
# ═══════════════════════════════════════════════════════════════════════════════

class TestMorfologiaHistorica:

    def test_importar_modulo(self):
        import core.morfologia_historica as mh
        assert hasattr(mh, "normalizar_formas_historicas")
        assert hasattr(mh, "lematizar_historico")
        assert hasattr(mh, "analizar_morfologia_token")
        assert hasattr(mh, "analizar_densidad_historica")
        assert hasattr(mh, "glosario_arcaismos")
        assert hasattr(mh, "enriquecer_corpus_con_lemas")

    def test_excepciones_lemas_presentes(self):
        from core.morfologia_historica import EXCEPCIONES_LEMAS
        assert "habia" in EXCEPCIONES_LEMAS
        assert EXCEPCIONES_LEMAS["habia"] == "haber"
        assert "fué" not in EXCEPCIONES_LEMAS  # normalizada antes como "fue"
        assert "tenia" in EXCEPCIONES_LEMAS
        assert EXCEPCIONES_LEMAS["tenia"] == "tener"

    def test_normalizar_fué(self):
        from core.morfologia_historica import normalizar_formas_historicas
        texto = "El señor fué al mercado y vió el espectáculo."
        norm = normalizar_formas_historicas(texto)
        assert "fue" in norm
        assert "vio" in norm

    def test_normalizar_setiembre(self):
        from core.morfologia_historica import normalizar_formas_historicas
        texto = "El acto fue en setiembre de 1939."
        norm = normalizar_formas_historicas(texto)
        assert "septiembre" in norm

    def test_normalizar_texto_vacio(self):
        from core.morfologia_historica import normalizar_formas_historicas
        assert normalizar_formas_historicas("") == ""

    def test_lematizar_con_excepcion(self):
        from core.morfologia_historica import lematizar_historico
        res = lematizar_historico(["habia", "tenía", "hubiera"])
        assert any(r["fuente"] == "excepcion" for r in res)
        # habia → haber
        habia = next(r for r in res if r["token"] == "habia")
        assert habia["lema"] == "haber"
        assert habia["fuente"] == "excepcion"

    def test_lematizar_sin_excepcion(self):
        from core.morfologia_historica import lematizar_historico
        res = lematizar_historico(["casa", "perro", "azul"])
        for r in res:
            assert r["fuente"] in ("original", "spacy", "excepcion")

    def test_analizar_morfologia_token_arcaismo(self):
        from core.morfologia_historica import analizar_morfologia_token
        res = analizar_morfologia_token("habia")
        assert res["es_arcaismo"] is True
        assert res["lema"] == "haber"
        assert res["fuente_lema"] == "excepcion"

    def test_analizar_morfologia_token_normal(self):
        from core.morfologia_historica import analizar_morfologia_token
        res = analizar_morfologia_token("casa")
        assert "token" in res
        assert "lema" in res
        assert "es_arcaismo" in res

    def test_densidad_historica_texto_arcaico(self):
        from core.morfologia_historica import analizar_densidad_historica
        res = analizar_densidad_historica(TEXTO_HISTORICO)
        assert "score" in res
        assert "n_arcaismos" in res
        assert "n_tokens" in res
        assert res["n_arcaismos"] > 0
        assert res["score"] > 0.0

    def test_densidad_historica_texto_moderno(self):
        from core.morfologia_historica import analizar_densidad_historica
        texto = "El presidente habla con los ciudadanos sobre el futuro del país."
        res = analizar_densidad_historica(texto)
        assert res["score"] < 0.5  # pocas formas arcaicas

    def test_densidad_texto_vacio(self):
        from core.morfologia_historica import analizar_densidad_historica
        res = analizar_densidad_historica("")
        assert res["score"] == 0.0
        assert res["n_arcaismos"] == 0

    def test_glosario_retorna_lista(self):
        from core.morfologia_historica import glosario_arcaismos
        glos = glosario_arcaismos()
        assert isinstance(glos, list)
        assert len(glos) > 50  # al menos 50 entradas
        assert all("forma_historica" in g and "lema_moderno" in g for g in glos)

    def test_glosario_ordenado(self):
        from core.morfologia_historica import glosario_arcaismos
        glos = glosario_arcaismos()
        formas = [g["forma_historica"] for g in glos]
        assert formas == sorted(formas)

    def test_enriquecer_corpus(self):
        from core.morfologia_historica import enriquecer_corpus_con_lemas
        corpus = [TEXTO_HISTORICO, CORPUS_HISTORICO[0]]
        res = enriquecer_corpus_con_lemas(corpus)
        assert len(res) == 2
        for d in res:
            assert "doc_idx" in d
            assert "n_tokens" in d
            assert "n_arcaismos" in d
            assert "score" in d
            assert "top_arcaismos" in d


# ═══════════════════════════════════════════════════════════════════════════════
# SENTIMENT ENGINE — extensiones offline
# ═══════════════════════════════════════════════════════════════════════════════

class TestSentimentExtensiones:

    def test_importar_funciones_nuevas(self):
        from core.sentiment_engine import (
            analisis_completo_emocion,
            analizar_emociones,
            analizar_intensidad,
            analizar_subjetividad,
        )
        assert callable(analizar_emociones)
        assert callable(analizar_subjetividad)
        assert callable(analizar_intensidad)
        assert callable(analisis_completo_emocion)

    def test_lexicon_emociones_no_vacio(self):
        from core.sentiment_engine import _LEXICON_EMOCIONES
        assert len(_LEXICON_EMOCIONES) == 8
        assert "alegria" in _LEXICON_EMOCIONES
        assert "tristeza" in _LEXICON_EMOCIONES
        assert "miedo" in _LEXICON_EMOCIONES

    def test_emociones_texto_vacio(self):
        from core.sentiment_engine import analizar_emociones
        res = analizar_emociones("")
        assert res["emocion_dominante"] is None
        assert res["subjetividad"] == 0.0
        assert res["tipo_discurso"] == "factual"

    def test_emociones_detecta_alegria(self):
        from core.sentiment_engine import analizar_emociones
        res = analizar_emociones(TEXTO_EMOCIONAL)
        assert res["emocion_dominante"] is not None
        # El texto tiene muchas palabras de alegría/confianza
        conteo_alg = res["emociones"].get("alegria", {}).get("n", 0)
        conteo_con = res["emociones"].get("confianza", {}).get("n", 0)
        assert conteo_alg + conteo_con > 0

    def test_emociones_estructura(self):
        from core.sentiment_engine import analizar_emociones
        res = analizar_emociones(TEXTO_EMOCIONAL)
        assert "emociones" in res
        assert "emocion_dominante" in res
        assert "palabras_detectadas" in res
        assert "subjetividad" in res
        assert "tipo_discurso" in res
        assert 0.0 <= res["subjetividad"] <= 1.0
        assert res["tipo_discurso"] in ("subjetivo", "factual", "mixto")

    def test_emociones_distribucion_suma(self):
        from core.sentiment_engine import analizar_emociones
        res = analizar_emociones(TEXTO_EMOCIONAL)
        total_pct = sum(e["porcentaje"] for e in res["emociones"].values())
        # Suma debe ser ~100% (tolerancia por redondeo)
        assert abs(total_pct - 100.0) < 1.0

    def test_subjetividad_texto_factual(self):
        from core.sentiment_engine import analizar_subjetividad
        res = analizar_subjetividad(TEXTO_FACTUAL)
        assert "score_subjetividad" in res
        assert "tipo_discurso" in res
        assert "marcadores_factuales" in res
        assert "marcadores_subjetivos" in res
        assert len(res["marcadores_factuales"]) > 0

    def test_subjetividad_texto_vacio(self):
        from core.sentiment_engine import analizar_subjetividad
        res = analizar_subjetividad("")
        assert res["score_subjetividad"] == 0.0
        assert res["tipo_discurso"] == "factual"

    def test_intensidad_superlativos(self):
        from core.sentiment_engine import analizar_intensidad
        texto = "El grandísimo ejército venció. El poderísimo líder habló."
        res = analizar_intensidad(texto)
        assert "score_intensidad" in res
        assert "marcadores" in res
        assert res["score_intensidad"] > 0.0
        tipos = [m["tipo"] for m in res["marcadores"]]
        assert "superlativo" in tipos

    def test_intensidad_exclamaciones(self):
        from core.sentiment_engine import analizar_intensidad
        texto = "¡Viva Colombia! ¡Viva la República! ¡Gloria al pueblo!"
        res = analizar_intensidad(texto)
        assert res["score_intensidad"] > 0.0

    def test_intensidad_texto_vacio(self):
        from core.sentiment_engine import analizar_intensidad
        res = analizar_intensidad("")
        assert res["score_intensidad"] == 0.0
        assert res["marcadores"] == []

    def test_analisis_completo_estructura(self):
        from core.sentiment_engine import analisis_completo_emocion
        res = analisis_completo_emocion(TEXTO_EMOCIONAL)
        assert "emociones" in res
        assert "subjetividad" in res
        assert "intensidad" in res
        # Cada sub-dict tiene sus campos
        assert "emocion_dominante" in res["emociones"]
        assert "score_subjetividad" in res["subjetividad"]
        assert "score_intensidad" in res["intensidad"]

    def test_analisis_completo_texto_vacio(self):
        from core.sentiment_engine import analisis_completo_emocion
        res = analisis_completo_emocion("")
        assert res["emociones"]["emocion_dominante"] is None
        assert res["subjetividad"]["score_subjetividad"] == 0.0
        assert res["intensidad"]["score_intensidad"] == 0.0
