"""tests/test_stylometry_engine.py — Regresión de cluster_tematico().

Auditoría de sesión (frente 1, 2026-09-02): con menos de 2 textos,
cluster_tematico() ejecutaba KMeans(n_clusters=max(2, len(textos))), lo que
para len(textos)==1 pedía 2 clusters con 1 sola muestra y sklearn lanzaba
ValueError("n_samples=1 should be >= n_clusters=2"). Reproducido en vivo
llamando la función con un solo texto real del corpus Estampa. Escenario
plausible: el usuario filtra la selección de artículos a 0 o 1 elemento
antes de pedir clustering temático desde la GUI.
"""
from core.stylometry_engine import cluster_tematico


def test_un_solo_texto_no_lanza_y_va_a_cluster_unico():
    r = cluster_tematico({"a1": "un texto cualquiera sobre bogota y la guerra en europa"})
    assert r == {"a1": 0}


def test_cero_textos_no_lanza():
    assert cluster_tematico({}) == {}


def test_dos_textos_clusteriza_normalmente():
    r = cluster_tematico({
        "a1": "texto uno sobre bogota y la politica nacional",
        "a2": "texto dos sobre medellin y la economia regional",
    })
    assert set(r.keys()) == {"a1", "a2"}


def test_menos_textos_que_n_clusters_pedidos_no_lanza():
    r = cluster_tematico(
        {"a1": "texto sobre bogota", "a2": "texto sobre medellin", "a3": "texto sobre cali"},
        n_clusters=5,
    )
    assert set(r.keys()) == {"a1", "a2", "a3"}
