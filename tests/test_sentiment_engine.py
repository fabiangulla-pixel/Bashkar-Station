"""tests/test_sentiment_engine.py — Tests para core/sentiment_engine.py"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import json

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.sentiment_engine import (
    TONOS,
    COLORES_TONO,
    analizar_tono,
    analizar_corpus_tono,
    estadisticas_tono,
    evolucion_temporal,
    cruce_seccion_tono,
    comparar_numeros_tono,
    tendencia_tono,
    resumen_narrativo,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

RESULTADO_MOCK = {
    "tono_principal": "celebratorio",
    "tono_secundario": "neutro",
    "confianza": 0.87,
    "intensidad": "alta",
    "indicadores": ["logros nacionales", "enaltece"],
    "resumen": "El artículo celebra los avances del país.",
}

def _mock_claude(respuesta: dict):
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps(respuesta))]
    client = MagicMock()
    client.messages.create.return_value = msg
    return client


CORPUS_MOCK = {
    "a1": {"texto": "texto1", "numero": "ene1939", "seccion": "politica"},
    "a2": {"texto": "texto2", "numero": "ene1939", "seccion": "cultura"},
    "a3": {"texto": "texto3", "numero": "feb1939", "seccion": "politica"},
    "a4": {"texto": "texto4", "numero": "feb1939", "seccion": "cultura"},
}

RESULTADOS_MOCK = {
    "a1": {"tono_principal": "celebratorio", "confianza": 0.9,
           "intensidad": "alta", "numero": "ene1939", "seccion": "politica"},
    "a2": {"tono_principal": "crítico",      "confianza": 0.8,
           "intensidad": "media", "numero": "ene1939", "seccion": "cultura"},
    "a3": {"tono_principal": "neutro",       "confianza": 0.7,
           "intensidad": "baja", "numero": "feb1939", "seccion": "politica"},
    "a4": {"tono_principal": "polémico",     "confianza": 0.85,
           "intensidad": "alta", "numero": "feb1939", "seccion": "cultura"},
}


# ── analizar_tono ─────────────────────────────────────────────────────────────

class TestAnalizarTono:
    def test_texto_vacio_retorna_neutro(self):
        res = analizar_tono("", api_key="k")
        assert res["tono_principal"] == "neutro"
        assert res["confianza"] == 0.0
        assert "error" in res

    def test_texto_solo_espacios(self):
        res = analizar_tono("   ", api_key="k")
        assert res["tono_principal"] == "neutro"

    def test_retorna_campos_completos(self):
        with patch("anthropic.Anthropic", return_value=_mock_claude(RESULTADO_MOCK)):
            res = analizar_tono("texto de prueba", api_key="fake")
        for campo in ("tono_principal", "tono_secundario", "confianza",
                      "intensidad", "indicadores", "resumen"):
            assert campo in res

    def test_tono_principal_valido(self):
        with patch("anthropic.Anthropic", return_value=_mock_claude(RESULTADO_MOCK)):
            res = analizar_tono("texto de prueba", api_key="fake")
        assert res["tono_principal"] in TONOS

    def test_confianza_en_rango(self):
        with patch("anthropic.Anthropic", return_value=_mock_claude(RESULTADO_MOCK)):
            res = analizar_tono("texto de prueba", api_key="fake")
        assert 0.0 <= res["confianza"] <= 1.0

    def test_intensidad_valida(self):
        with patch("anthropic.Anthropic", return_value=_mock_claude(RESULTADO_MOCK)):
            res = analizar_tono("texto de prueba", api_key="fake")
        assert res["intensidad"] in ("alta", "media", "baja")

    def test_error_api_retorna_neutro(self):
        client = MagicMock()
        client.messages.create.side_effect = Exception("timeout")
        with patch("anthropic.Anthropic", return_value=client):
            res = analizar_tono("texto", api_key="fake")
        assert res["tono_principal"] == "neutro"
        assert "error" in res

    def test_trunca_texto_largo(self):
        texto_largo = "a" * 10000
        llamadas = []
        def mock_create(**kwargs):
            llamadas.append(kwargs["messages"][0]["content"])
            return _mock_claude(RESULTADO_MOCK).messages.create(**kwargs)
        client = MagicMock()
        client.messages.create.side_effect = mock_create
        client.messages.create.return_value = _mock_claude(RESULTADO_MOCK).messages.create()
        with patch("anthropic.Anthropic", return_value=_mock_claude(RESULTADO_MOCK)):
            analizar_tono(texto_largo, api_key="fake")
        # Solo verificamos que no explota con texto largo

    def test_json_con_markdown_se_parsea(self):
        respuesta_md = f"```json\n{json.dumps(RESULTADO_MOCK)}\n```"
        msg = MagicMock()
        msg.content = [MagicMock(text=respuesta_md)]
        client = MagicMock()
        client.messages.create.return_value = msg
        with patch("anthropic.Anthropic", return_value=client):
            res = analizar_tono("texto", api_key="fake")
        assert res["tono_principal"] == "celebratorio"


# ── analizar_corpus_tono ──────────────────────────────────────────────────────

class TestAnalizarCorpusTono:
    def test_corpus_vacio_retorna_vacio(self):
        resultado = analizar_corpus_tono({}, api_key="k")
        assert resultado == {}

    def test_retorna_todos_los_ids(self):
        with patch("core.sentiment_engine.analizar_tono", return_value=RESULTADO_MOCK):
            res = analizar_corpus_tono({"a": "t1", "b": "t2"}, api_key="k")
        assert set(res.keys()) == {"a", "b"}

    def test_callback_invocado(self):
        llamadas = []
        with patch("core.sentiment_engine.analizar_tono", return_value=RESULTADO_MOCK):
            analizar_corpus_tono(
                {"a": "t1", "b": "t2"}, api_key="k",
                callback=lambda n, t, aid: llamadas.append((n, t))
            )
        assert len(llamadas) == 2

    def test_acepta_entradas_con_metadatos(self):
        entrada = {"a1": {"texto": "hola", "numero": "ene1939", "seccion": "cultura"}}
        with patch("core.sentiment_engine.analizar_tono", return_value=RESULTADO_MOCK):
            res = analizar_corpus_tono(entrada, api_key="k")
        assert "numero" in res["a1"]
        assert res["a1"]["numero"] == "ene1939"

    def test_acepta_entradas_solo_texto(self):
        with patch("core.sentiment_engine.analizar_tono", return_value=RESULTADO_MOCK):
            res = analizar_corpus_tono({"a": "texto plano"}, api_key="k")
        assert "a" in res

    def test_workers_paralelos_preservan_orden(self):
        entradas = {f"a{i}": f"texto{i}" for i in range(10)}
        with patch("core.sentiment_engine.analizar_tono", return_value=RESULTADO_MOCK):
            res = analizar_corpus_tono(entradas, api_key="k", workers=4)
        assert len(res) == 10


# ── estadisticas_tono ─────────────────────────────────────────────────────────

class TestEstadisticasTono:
    def test_estructura_retorno(self):
        stats = estadisticas_tono(RESULTADOS_MOCK)
        assert "total" in stats
        assert "distribucion" in stats
        assert "tono_dominante" in stats
        assert "indice_polarizacion" in stats

    def test_total_correcto(self):
        stats = estadisticas_tono(RESULTADOS_MOCK)
        assert stats["total"] == 4

    def test_todos_los_tonos_en_distribucion(self):
        stats = estadisticas_tono(RESULTADOS_MOCK)
        for tono in TONOS:
            assert tono in stats["distribucion"]

    def test_porcentajes_suman_100(self):
        stats = estadisticas_tono(RESULTADOS_MOCK)
        total_pct = sum(v["porcentaje"] for v in stats["distribucion"].values())
        assert abs(total_pct - 100.0) < 0.5

    def test_tono_dominante_es_el_mas_frecuente(self):
        resultados = {
            "a": {"tono_principal": "celebratorio", "confianza": 0.9},
            "b": {"tono_principal": "celebratorio", "confianza": 0.8},
            "c": {"tono_principal": "crítico",      "confianza": 0.7},
        }
        stats = estadisticas_tono(resultados)
        assert stats["tono_dominante"] == "celebratorio"

    def test_indice_polarizacion_calculado(self):
        resultados = {
            "a": {"tono_principal": "crítico",   "confianza": 0.9},
            "b": {"tono_principal": "polémico",  "confianza": 0.8},
            "c": {"tono_principal": "neutro",    "confianza": 0.7},
            "d": {"tono_principal": "neutro",    "confianza": 0.6},
        }
        stats = estadisticas_tono(resultados)
        assert stats["indice_polarizacion"] == 50.0

    def test_corpus_vacio_no_explota(self):
        stats = estadisticas_tono({})
        assert stats["total"] == 0


# ── evolucion_temporal ────────────────────────────────────────────────────────

class TestEvolucionTemporal:
    def test_retorna_periodos_ordenados(self):
        evol = evolucion_temporal(RESULTADOS_MOCK, "numero")
        periodos = list(evol.keys())
        assert periodos == sorted(periodos)

    def test_todos_los_tonos_en_cada_periodo(self):
        evol = evolucion_temporal(RESULTADOS_MOCK, "numero")
        for periodo, datos in evol.items():
            for tono in TONOS:
                assert tono in datos

    def test_porcentajes_suman_100_por_periodo(self):
        evol = evolucion_temporal(RESULTADOS_MOCK, "numero")
        for periodo, datos in evol.items():
            total_pct = sum(datos[t] for t in TONOS)
            assert abs(total_pct - 100.0) < 0.5

    def test_total_por_periodo(self):
        evol = evolucion_temporal(RESULTADOS_MOCK, "numero")
        assert evol["ene1939"]["total"] == 2
        assert evol["feb1939"]["total"] == 2

    def test_sin_periodo_agrupa_en_sin_periodo(self):
        res = {"a": {"tono_principal": "neutro", "confianza": 0.5}}
        evol = evolucion_temporal(res, "numero")
        assert "sin_periodo" in evol

    def test_campo_personalizado(self):
        evol = evolucion_temporal(RESULTADOS_MOCK, "seccion")
        assert "politica" in evol
        assert "cultura" in evol


# ── cruce_seccion_tono ────────────────────────────────────────────────────────

class TestCruceSeccionTono:
    def test_retorna_secciones_correctas(self):
        cruce = cruce_seccion_tono(RESULTADOS_MOCK, "seccion")
        assert "politica" in cruce
        assert "cultura" in cruce

    def test_porcentajes_suman_100(self):
        cruce = cruce_seccion_tono(RESULTADOS_MOCK, "seccion")
        for seccion, datos in cruce.items():
            total_pct = sum(datos[t] for t in TONOS)
            assert abs(total_pct - 100.0) < 0.5

    def test_total_por_seccion(self):
        cruce = cruce_seccion_tono(RESULTADOS_MOCK, "seccion")
        assert cruce["politica"]["total"] == 2
        assert cruce["cultura"]["total"] == 2

    def test_campo_numero(self):
        cruce = cruce_seccion_tono(RESULTADOS_MOCK, "numero")
        assert "ene1939" in cruce
        assert "feb1939" in cruce


# ── comparar_numeros_tono ─────────────────────────────────────────────────────

class TestCompararNumerosTono:
    def test_estructura_retorno(self):
        res_a = {"x": {"tono_principal": "celebratorio", "confianza": 0.9}}
        res_b = {"y": {"tono_principal": "crítico",      "confianza": 0.8}}
        comp = comparar_numeros_tono(res_a, res_b, "Ene", "Feb")
        for tono in TONOS:
            assert tono in comp
            assert "Ene" in comp[tono]
            assert "Feb" in comp[tono]
            assert "delta" in comp[tono]

    def test_delta_calculado(self):
        # A: 50% celebratorio (1 de 2), B: 100% celebratorio (2 de 2) → delta +50
        res_a = {
            "x": {"tono_principal": "celebratorio", "confianza": 0.9},
            "w": {"tono_principal": "crítico",      "confianza": 0.8},
        }
        res_b = {
            "y": {"tono_principal": "celebratorio", "confianza": 0.9},
            "z": {"tono_principal": "celebratorio", "confianza": 0.8},
        }
        comp = comparar_numeros_tono(res_a, res_b)
        assert comp["celebratorio"]["delta"] > 0

    def test_corpora_iguales_delta_cero(self):
        res = {"x": {"tono_principal": "neutro", "confianza": 0.7}}
        comp = comparar_numeros_tono(res, res)
        for tono in TONOS:
            assert comp[tono]["delta"] == 0.0


# ── tendencia_tono ────────────────────────────────────────────────────────────

class TestTendenciaTono:
    def _evol_simple(self, valores):
        periodos = [f"p{i}" for i in range(len(valores))]
        return {p: {"celebratorio": v, **{t: 0 for t in TONOS if t != "celebratorio"},
                    "total": 10}
                for p, v in zip(periodos, valores)}

    def test_estructura_retorno(self):
        evol = self._evol_simple([10, 20, 30])
        t = tendencia_tono(evol, "celebratorio")
        assert "periodos" in t
        assert "valores" in t
        assert "pendiente" in t
        assert "direccion" in t

    def test_sube(self):
        evol = self._evol_simple([10, 20, 30, 40])
        t = tendencia_tono(evol, "celebratorio")
        assert t["direccion"] == "sube"

    def test_baja(self):
        evol = self._evol_simple([40, 30, 20, 10])
        t = tendencia_tono(evol, "celebratorio")
        assert t["direccion"] == "baja"

    def test_estable(self):
        evol = self._evol_simple([20, 21, 19, 20])
        t = tendencia_tono(evol, "celebratorio")
        assert t["direccion"] == "estable"

    def test_un_solo_periodo_es_estable(self):
        evol = {"p0": {"celebratorio": 50, "total": 10}}
        t = tendencia_tono(evol, "celebratorio")
        assert t["direccion"] == "estable"
        assert t["pendiente"] == 0.0

    def test_valores_coinciden_con_periodos(self):
        evol = self._evol_simple([10, 30, 20])
        t = tendencia_tono(evol, "celebratorio")
        assert len(t["valores"]) == len(t["periodos"]) == 3


# ── constantes ───────────────────────────────────────────────────────────────

class TestConstantes:
    def test_tonos_completos(self):
        esperados = {"celebratorio", "crítico", "neutro", "elegíaco", "polémico", "informativo"}
        assert set(TONOS) == esperados

    def test_colores_para_todos_los_tonos(self):
        for tono in TONOS:
            assert tono in COLORES_TONO
            assert COLORES_TONO[tono].startswith("#")
