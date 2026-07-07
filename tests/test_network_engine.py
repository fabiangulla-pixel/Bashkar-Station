"""
tests/test_network_engine.py — Tests para core/network_engine.py

Cubre: construir_grafo (nodos, aristas, peso_minimo, max_nodos, grafo vacío),
       metricas_red (estructura, grafo vacío, densidad, top_centralidad),
       grafo_a_dict / dict_a_grafo (roundtrip serialización).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.network_engine import construir_grafo, metricas_red, grafo_a_dict, dict_a_grafo


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures — índice NER de prueba
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def indice_simple():
    """Índice NER mínimo con co-ocurrencias claras."""
    return {
        "personas": {
            "Bolívar":   ["art_1", "art_2", "art_3"],
            "Santander": ["art_1", "art_2"],
            "Nariño":    ["art_3", "art_4"],
        },
        "lugares": {
            "Bogotá":    ["art_1", "art_2", "art_3", "art_4"],
            "Caracas":   ["art_1", "art_2"],
        },
    }


@pytest.fixture
def indice_vacio():
    return {"personas": {}, "lugares": {}}


@pytest.fixture
def indice_sin_coocurrencias():
    """Entidades que nunca aparecen en el mismo artículo."""
    return {
        "personas": {
            "Solo_A": ["art_1"],
            "Solo_B": ["art_2"],
        }
    }


# ══════════════════════════════════════════════════════════════════════════════
# construir_grafo
# ══════════════════════════════════════════════════════════════════════════════

class TestConstruirGrafo:
    def test_retorna_grafo_networkx(self, indice_simple):
        import networkx as nx
        G = construir_grafo(indice_simple, peso_minimo=1)
        assert isinstance(G, nx.Graph)

    def test_nodos_creados(self, indice_simple):
        G = construir_grafo(indice_simple, peso_minimo=1)
        assert G.number_of_nodes() > 0

    def test_nodos_tienen_atributo_categoria(self, indice_simple):
        G = construir_grafo(indice_simple, peso_minimo=1)
        for node, data in G.nodes(data=True):
            assert "categoria" in data

    def test_nodos_tienen_atributo_freq(self, indice_simple):
        G = construir_grafo(indice_simple, peso_minimo=1)
        for node, data in G.nodes(data=True):
            assert "freq" in data

    def test_aristas_creadas_con_peso_minimo_uno(self, indice_simple):
        G = construir_grafo(indice_simple, peso_minimo=1)
        assert G.number_of_edges() > 0

    def test_peso_minimo_dos_reduce_aristas(self, indice_simple):
        G1 = construir_grafo(indice_simple, peso_minimo=1)
        G2 = construir_grafo(indice_simple, peso_minimo=2)
        assert G2.number_of_edges() <= G1.number_of_edges()

    def test_sin_coocurrencias_grafo_vacio(self, indice_sin_coocurrencias):
        G = construir_grafo(indice_sin_coocurrencias, peso_minimo=1)
        # Solo_A y Solo_B no co-ocurren → no hay aristas → nodos aislados eliminados
        assert G.number_of_edges() == 0

    def test_indice_vacio_grafo_sin_nodos(self, indice_vacio):
        G = construir_grafo(indice_vacio, peso_minimo=1)
        assert G.number_of_nodes() == 0

    def test_max_nodos_limita_grafo(self, indice_simple):
        G = construir_grafo(indice_simple, peso_minimo=1, max_nodos=2)
        assert G.number_of_nodes() <= 2

    def test_categorias_filtrado(self, indice_simple):
        G_solo_personas = construir_grafo(
            indice_simple, categorias=["personas"], peso_minimo=1)
        for node, data in G_solo_personas.nodes(data=True):
            assert data.get("categoria") == "personas"

    def test_aristas_ponderadas(self, indice_simple):
        G = construir_grafo(indice_simple, peso_minimo=1)
        for u, v, data in G.edges(data=True):
            assert "weight" in data
            assert data["weight"] >= 1

    def test_callback_llamado(self, indice_simple):
        mensajes = []
        construir_grafo(indice_simple, peso_minimo=1, callback=mensajes.append)
        assert len(mensajes) > 0


# ══════════════════════════════════════════════════════════════════════════════
# metricas_red
# ══════════════════════════════════════════════════════════════════════════════

class TestMetricasRed:
    def test_grafo_vacio_retorna_error(self):
        import networkx as nx
        G = nx.Graph()
        result = metricas_red(G)
        assert "error" in result

    def test_metricas_basicas_presentes(self, indice_simple):
        G = construir_grafo(indice_simple, peso_minimo=1)
        if G.number_of_nodes() == 0:
            pytest.skip("Grafo vacío")
        m = metricas_red(G)
        for campo in ("nodos", "aristas", "densidad", "componentes_conexas"):
            assert campo in m

    def test_densidad_entre_cero_y_uno(self, indice_simple):
        G = construir_grafo(indice_simple, peso_minimo=1)
        if G.number_of_nodes() == 0:
            pytest.skip("Grafo vacío")
        m = metricas_red(G)
        assert 0.0 <= m["densidad"] <= 1.0

    def test_top_centralidad_es_lista(self, indice_simple):
        G = construir_grafo(indice_simple, peso_minimo=1)
        if G.number_of_nodes() == 0:
            pytest.skip("Grafo vacío")
        m = metricas_red(G)
        assert isinstance(m.get("top_centralidad", []), list)

    def test_nodos_aristas_coinciden_con_grafo(self, indice_simple):
        G = construir_grafo(indice_simple, peso_minimo=1)
        if G.number_of_nodes() == 0:
            pytest.skip("Grafo vacío")
        m = metricas_red(G)
        assert m["nodos"] == G.number_of_nodes()
        assert m["aristas"] == G.number_of_edges()


# ══════════════════════════════════════════════════════════════════════════════
# grafo_a_dict / dict_a_grafo — serialización roundtrip
# ══════════════════════════════════════════════════════════════════════════════

class TestSerializacionGrafo:
    def test_grafo_a_dict_retorna_dict(self, indice_simple):
        G = construir_grafo(indice_simple, peso_minimo=1)
        if G.number_of_nodes() == 0:
            pytest.skip("Grafo vacío")
        d = grafo_a_dict(G)
        assert isinstance(d, dict)

    def test_dict_tiene_nodos_y_aristas(self, indice_simple):
        G = construir_grafo(indice_simple, peso_minimo=1)
        if G.number_of_nodes() == 0:
            pytest.skip("Grafo vacío")
        d = grafo_a_dict(G)
        # networkx node_link_data usa "nodes" y "links" o "edges"
        assert "nodes" in d or "nodos" in d
        assert "links" in d or "edges" in d or "aristas" in d

    def test_roundtrip_preserva_n_nodos(self, indice_simple):
        G = construir_grafo(indice_simple, peso_minimo=1)
        if G.number_of_nodes() == 0:
            pytest.skip("Grafo vacío")
        d = grafo_a_dict(G)
        G2 = dict_a_grafo(d)
        assert G2.number_of_nodes() == G.number_of_nodes()

    def test_roundtrip_preserva_n_aristas(self, indice_simple):
        G = construir_grafo(indice_simple, peso_minimo=1)
        if G.number_of_nodes() == 0:
            pytest.skip("Grafo vacío")
        d = grafo_a_dict(G)
        G2 = dict_a_grafo(d)
        assert G2.number_of_edges() == G.number_of_edges()

    def test_dict_vacio_da_grafo_vacio(self):
        # node_link_graph espera el formato nativo de networkx
        import networkx as nx
        G_empty = nx.Graph()
        d = grafo_a_dict(G_empty)
        G2 = dict_a_grafo(d)
        assert G2.number_of_nodes() == 0
        assert G2.number_of_edges() == 0
