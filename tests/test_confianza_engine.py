"""
tests/test_confianza_engine.py — Tests para core/confianza_engine.py

Cubre: nivel_confianza, color_semaforo, color_fondo_semaforo, etiqueta_semaforo,
       score_ocr, score_ner_entidad, score_tono, EntidadValidacion, ColaPendiente,
       confianza_global_corpus.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.confianza_engine import (
    AMARILLO,
    COLOR_AMARILLO,
    COLOR_BG_AMARILLO,
    COLOR_BG_ROJO,
    COLOR_BG_VERDE,
    COLOR_ROJO,
    COLOR_VERDE,
    ROJO,
    VERDE,
    ColaPendiente,
    EntidadValidacion,
    color_fondo_semaforo,
    color_semaforo,
    confianza_global_corpus,
    etiqueta_semaforo,
    nivel_confianza,
    score_ner_entidad,
    score_ocr,
    score_tono,
)

# ══════════════════════════════════════════════════════════════════════════════
# nivel_confianza
# ══════════════════════════════════════════════════════════════════════════════

class TestNivelConfianza:
    def test_verde_exacto(self):
        assert nivel_confianza(0.75) == VERDE

    def test_verde_alto(self):
        assert nivel_confianza(1.0) == VERDE

    def test_amarillo_exacto(self):
        assert nivel_confianza(0.45) == AMARILLO

    def test_amarillo_en_rango(self):
        assert nivel_confianza(0.60) == AMARILLO

    def test_amarillo_justo_bajo_verde(self):
        assert nivel_confianza(0.749) == AMARILLO

    def test_rojo_justo_bajo_amarillo(self):
        assert nivel_confianza(0.449) == ROJO

    def test_rojo_cero(self):
        assert nivel_confianza(0.0) == ROJO

    def test_rojo_negativo_tratado_como_rojo(self):
        assert nivel_confianza(-0.1) == ROJO


# ══════════════════════════════════════════════════════════════════════════════
# color_semaforo / color_fondo_semaforo / etiqueta_semaforo
# ══════════════════════════════════════════════════════════════════════════════

class TestColoresEtiquetas:
    def test_color_verde(self):
        assert color_semaforo(0.9) == COLOR_VERDE

    def test_color_amarillo(self):
        assert color_semaforo(0.6) == COLOR_AMARILLO

    def test_color_rojo(self):
        assert color_semaforo(0.1) == COLOR_ROJO

    def test_fondo_verde(self):
        assert color_fondo_semaforo(0.9) == COLOR_BG_VERDE

    def test_fondo_amarillo(self):
        assert color_fondo_semaforo(0.6) == COLOR_BG_AMARILLO

    def test_fondo_rojo(self):
        assert color_fondo_semaforo(0.1) == COLOR_BG_ROJO

    def test_etiqueta_verde(self):
        assert "CONFIABLE" in etiqueta_semaforo(0.9)

    def test_etiqueta_amarillo(self):
        assert "REVISAR" in etiqueta_semaforo(0.6)

    def test_etiqueta_rojo(self):
        assert "VALIDAR" in etiqueta_semaforo(0.1)


# ══════════════════════════════════════════════════════════════════════════════
# score_ocr
# ══════════════════════════════════════════════════════════════════════════════

class TestScoreOcr:
    def test_cien_da_uno(self):
        assert score_ocr(100.0) == 1.0

    def test_cero_da_cero(self):
        assert score_ocr(0.0) == 0.0

    def test_cincuenta_da_cero_cinco(self):
        assert abs(score_ocr(50.0) - 0.5) < 0.01

    def test_mejorado_llm_sube_score(self):
        base = score_ocr(60.0, mejorado_con_llm=False)
        mejorado = score_ocr(60.0, mejorado_con_llm=True)
        assert mejorado > base

    def test_mejorado_llm_no_supera_uno(self):
        assert score_ocr(100.0, mejorado_con_llm=True) == 1.0

    def test_negativo_clampea_a_cero(self):
        assert score_ocr(-10.0) == 0.0

    def test_mayor_de_cien_clampea_a_uno(self):
        assert score_ocr(150.0) == 1.0


# ══════════════════════════════════════════════════════════════════════════════
# score_ner_entidad
# ══════════════════════════════════════════════════════════════════════════════

class TestScoreNerEntidad:
    def test_verificada_siempre_uno(self):
        assert score_ner_entidad(en_kb=False, verificada=True,
                                  spacy_conf=0.0, llm_conf=0.0) == 1.0

    def test_en_kb_sube_score(self):
        sin_kb = score_ner_entidad(en_kb=False, verificada=False,
                                    spacy_conf=0.7, llm_conf=0.8)
        con_kb = score_ner_entidad(en_kb=True, verificada=False,
                                    spacy_conf=0.7, llm_conf=0.8)
        assert con_kb > sin_kb

    def test_score_maximo_sin_verificar(self):
        sc = score_ner_entidad(en_kb=True, verificada=False,
                                spacy_conf=1.0, llm_conf=1.0)
        assert sc == 1.0

    def test_score_minimo(self):
        sc = score_ner_entidad(en_kb=False, verificada=False,
                                spacy_conf=0.0, llm_conf=0.0)
        assert sc == 0.0

    def test_pesos_suman_correctamente(self):
        # kb=0.3, spacy=0.25*1, llm=0.45*1 → 1.0
        sc = score_ner_entidad(en_kb=True, verificada=False,
                                spacy_conf=1.0, llm_conf=1.0)
        assert abs(sc - 1.0) < 0.001

    def test_retorna_float_redondeado(self):
        sc = score_ner_entidad(en_kb=True, verificada=False,
                                spacy_conf=0.7, llm_conf=0.8)
        # Verificar que tiene como máximo 3 decimales
        assert sc == round(sc, 3)


# ══════════════════════════════════════════════════════════════════════════════
# score_tono
# ══════════════════════════════════════════════════════════════════════════════

class TestScoreTono:
    def test_neutro_sube_score(self):
        base = score_tono(0.7, es_neutral=False)
        neutro = score_tono(0.7, es_neutral=True)
        assert neutro > base

    def test_neutro_no_supera_uno(self):
        assert score_tono(1.0, es_neutral=True) == 1.0

    def test_sin_neutro_retorna_igual(self):
        assert score_tono(0.65) == 0.65


# ══════════════════════════════════════════════════════════════════════════════
# EntidadValidacion
# ══════════════════════════════════════════════════════════════════════════════

class TestEntidadValidacion:
    def test_nivel_se_calcula_automaticamente(self):
        e = EntidadValidacion(nombre="Bolívar", categoria="personas", score=0.9)
        assert e.nivel == VERDE

    def test_nivel_rojo_para_score_bajo(self):
        e = EntidadValidacion(nombre="X", categoria="otros", score=0.2)
        assert e.nivel == ROJO

    def test_verificada_false_por_defecto(self):
        e = EntidadValidacion(nombre="A", categoria="b", score=0.5)
        assert e.verificada is False

    def test_editado_por_vacio_por_defecto(self):
        e = EntidadValidacion(nombre="A", categoria="b", score=0.5)
        assert e.editado_por == ""


# ══════════════════════════════════════════════════════════════════════════════
# ColaPendiente
# ══════════════════════════════════════════════════════════════════════════════

class TestColaPendiente:
    def _cola_con_items(self):
        cola = ColaPendiente()
        cola.agregar(EntidadValidacion("Bogotá", "lugares", 0.9))    # verde → no entra
        cola.agregar(EntidadValidacion("García", "personas", 0.6))   # amarillo → entra
        cola.agregar(EntidadValidacion("X123", "otros", 0.2))        # rojo → entra
        return cola

    def test_verde_no_entra_en_cola(self):
        cola = self._cola_con_items()
        assert len(cola._items) == 2

    def test_pendientes_inicialmente_todos(self):
        cola = self._cola_con_items()
        assert len(cola.pendientes()) == 2

    def test_verificar_reduce_pendientes(self):
        cola = self._cola_con_items()
        cola.verificar("García", "personas", editado_por="investigadora")
        assert len(cola.pendientes()) == 1

    def test_verificar_inexistente_retorna_false(self):
        cola = self._cola_con_items()
        assert cola.verificar("NoExiste", "personas") is False

    def test_verificar_existente_retorna_true(self):
        cola = self._cola_con_items()
        assert cola.verificar("García", "personas") is True

    def test_estadisticas_estructura(self):
        cola = self._cola_con_items()
        stats = cola.estadisticas()
        assert "total" in stats
        assert "verificadas" in stats
        assert "pendientes" in stats
        assert "por_nivel" in stats

    def test_estadisticas_totales_correctas(self):
        cola = self._cola_con_items()
        stats = cola.estadisticas()
        assert stats["total"] == 2
        assert stats["verificadas"] == 0
        assert stats["pendientes"] == 2

    def test_estadisticas_tras_verificacion(self):
        cola = self._cola_con_items()
        cola.verificar("García", "personas")
        stats = cola.estadisticas()
        assert stats["verificadas"] == 1
        assert stats["pendientes"] == 1


# ══════════════════════════════════════════════════════════════════════════════
# confianza_global_corpus
# ══════════════════════════════════════════════════════════════════════════════

class TestConfianzaGlobalCorpus:
    def test_corpus_vacio_retorna_rojo(self):
        resultado = confianza_global_corpus({})
        assert resultado["nivel"] == ROJO

    def test_corpus_con_ocr_alto(self):
        corpus = {
            "art1": {"conf_ocr": 90},
            "art2": {"conf_ocr": 85},
            "art3": {"conf_ocr": 88},
        }
        resultado = confianza_global_corpus(corpus)
        assert resultado["nivel"] == VERDE
        assert resultado["promedio_ocr"] > 0.75

    def test_corpus_con_ocr_bajo(self):
        corpus = {
            "art1": {"conf_ocr": 20},
            "art2": {"conf_ocr": 15},
        }
        resultado = confianza_global_corpus(corpus)
        assert resultado["nivel"] in (ROJO, AMARILLO)

    def test_mejorado_llm_sube_nivel(self):
        corpus_sin = {"art1": {"conf_ocr": 60}}
        corpus_con = {"art1": {"conf_ocr": 60, "mejorado_llm": True}}
        sin_mejora = confianza_global_corpus(corpus_sin)["promedio_ocr"]
        con_mejora = confianza_global_corpus(corpus_con)["promedio_ocr"]
        assert con_mejora >= sin_mejora

    def test_distribucion_presente(self):
        corpus = {"art1": {"conf_ocr": 80}, "art2": {"conf_ocr": 30}}
        resultado = confianza_global_corpus(corpus)
        assert VERDE in resultado["distribucion"]
        assert ROJO in resultado["distribucion"]

    def test_total_articulos_correcto(self):
        corpus = {f"art{i}": {"conf_ocr": 70} for i in range(5)}
        resultado = confianza_global_corpus(corpus)
        assert resultado["total_articulos"] == 5

    def test_confianza_alternativa_key(self):
        # También acepta "confianza_ocr" como clave
        corpus = {"art1": {"confianza_ocr": 80}}
        resultado = confianza_global_corpus(corpus)
        assert resultado["promedio_ocr"] > 0
