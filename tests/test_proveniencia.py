"""Manifiestos de ejecución y exportación."""

import json
from pathlib import Path

import pytest

from core import proveniencia as P


def test_hash_archivos_cambia_con_una_sola_pagina(tmp_path):
    (tmp_path / "a.txt").write_text("uno", encoding="utf-8")
    (tmp_path / "b.txt").write_text("dos", encoding="utf-8")
    rutas = list(tmp_path.glob("*.txt"))
    h1 = P.hash_archivos(rutas)
    assert h1 == P.hash_archivos(reversed(rutas))  # orden no importa
    (tmp_path / "b.txt").write_text("dos.", encoding="utf-8")
    assert P.hash_archivos(rutas) != h1


def test_hash_vacio_es_desconocido_no_inventado():
    assert P.hash_archivos([]) == P.DESCONOCIDO
    assert P.hash_texto({}) == P.DESCONOCIDO


def test_commit_respeta_variable_de_entorno(monkeypatch):
    P.commit_software.cache_clear()
    monkeypatch.setenv("BASHKAR_COMMIT", "deadbeef")
    try:
        assert P.commit_software() == "deadbeef"
    finally:
        P.commit_software.cache_clear()


def test_manifiesto_ejecucion_exige_id_de_corpus():
    with pytest.raises(ValueError):
        P.manifiesto_ejecucion(tipo="x", corpus={})


def test_manifiesto_ejecucion_campos(monkeypatch):
    monkeypatch.setattr(P, "componentes_externos", lambda: {"tesseract": {"instalado": True}})
    m = P.manifiesto_ejecucion(tipo="benchmark_ocr", corpus={"id": "estampa-1939"},
                               metricas={"cer": 0.1}, advertencias=["sin Kraken"])
    for clave in ("fecha", "corpus", "entorno", "metricas", "advertencias", "etapas_omitidas"):
        assert clave in m
    assert m["corpus"]["version"] == P.DESCONOCIDO
    assert m["entorno"]["python"]
    assert "commit" in m["entorno"]


def test_manifiesto_exportacion_junto_al_producto(tmp_path):
    prod = tmp_path / "corpus.tei.xml"
    prod.write_text("<TEI/>", encoding="utf-8")
    ruta = P.escribir_manifiesto_exportacion(prod, formato="TEI",
                                             corpus={"id": "estampa"})
    assert ruta == tmp_path / "corpus.tei.xml.proveniencia.json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["formato"] == "TEI" and datos["corpus"]["id"] == "estampa"
    # Sin fuentes declaradas, el manifiesto lo dice en vez de callarlo.
    assert any("fuentes" in a for a in datos["advertencias"])
    assert "NO" in datos["licencias"]


def test_rutas_personales_no_salen_en_el_manifiesto():
    home = str(Path.home())
    assert home not in P.anonimizar_ruta(home + "\\x\\y")
    assert P.anonimizar_ruta("") == ""
