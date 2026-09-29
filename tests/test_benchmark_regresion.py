"""Benchmark OCR formal: referencia humana obligatoria, estratos, regresiones."""

import json

import pytest

from core import benchmark_regresion as BR


def _bench(tmp_path, referencia=None, casos=None, salidas=None):
    man = {
        "corpus_id": "prueba",
        "referencia": referencia or {"tipo": "humana", "transcriptor": "F. G."},
        "casos": casos or [
            {"page_id": "p1", "revista": "Estampa", "anio": 1939},
            {"page_id": "p2", "revista": "Cromos", "anio": 1938},
        ],
    }
    (tmp_path / BR.MANIFIESTO).write_text(json.dumps(man), encoding="utf-8")
    (tmp_path / "referencia").mkdir()
    (tmp_path / "referencia" / "p1.txt").write_text("el gobierno de los liberales",
                                                    encoding="utf-8")
    (tmp_path / "referencia" / "p2.txt").write_text("la revista ilustrada",
                                                    encoding="utf-8")
    for ruta, textos in (salidas or {}).items():
        d = tmp_path / "salidas" / ruta
        d.mkdir(parents=True)
        for pid, t in textos.items():
            (d / f"{pid}.txt").write_text(t, encoding="utf-8")
    return tmp_path


def test_rechaza_referencia_de_ia(tmp_path):
    _bench(tmp_path, referencia={"tipo": "juez_ia", "transcriptor": "claude"})
    with pytest.raises(BR.ReferenciaNoHumana):
        BR.evaluar(tmp_path)


def test_rechaza_referencia_sin_transcriptor(tmp_path):
    _bench(tmp_path, referencia={"tipo": "humana"})
    with pytest.raises(BR.ReferenciaNoHumana):
        BR.evaluar(tmp_path)


def test_salida_perfecta_da_cer_cero_y_estratos(tmp_path):
    _bench(tmp_path, salidas={"t": {"p1": "el gobierno de los liberales",
                                    "p2": "la revista ilustrada"}})
    res = BR.evaluar(tmp_path)
    g = res["rutas"][0]["global"]
    assert g["cer"] == 0 and g["cobertura"] == 1
    assert set(res["rutas"][0]["por_estrato"]["revista"]) == {"Estampa", "Cromos"}
    assert any("ruido" in a for a in res["advertencias"])  # muestra chica


def test_pagina_ausente_cuenta_como_error_y_baja_cobertura(tmp_path):
    _bench(tmp_path, salidas={"t": {"p1": "el gobierno de los liberales"}})
    g = BR.evaluar(tmp_path)["rutas"][0]["global"]
    assert g["cobertura"] == 0.5 and g["cer"] > 0


def test_tasas_de_fusion_y_fragmentacion():
    t = BR.tasas_segmentacion("el gobierno de los liberales",
                              "el gob ierno delos liberales")
    assert t["fusion"] == pytest.approx(1 / 5)
    assert t["fragmentacion"] == pytest.approx(1 / 5)
    assert BR.tasas_segmentacion("", "x") == {"fusion": 0.0, "fragmentacion": 0.0}


def test_ruta_prellenada_se_excluye(tmp_path):
    _bench(tmp_path, referencia={"tipo": "humana", "transcriptor": "F",
                                 "prellenado_con": "tesseract"},
           salidas={"tesseract": {"p1": "x"}, "kraken": {"p1": "x"}})
    res = BR.evaluar(tmp_path)
    assert [r["ruta"] for r in res["rutas"]] == ["kraken"]
    assert any("prellenó" in a for a in res["advertencias"])


def test_linea_base_detecta_regresion_y_ruta_perdida(tmp_path, monkeypatch):
    from core import proveniencia
    monkeypatch.setattr(proveniencia, "componentes_externos", lambda: {})
    _bench(tmp_path, salidas={"t": {"p1": "el gobierno de los liberales",
                                    "p2": "la revista ilustrada"},
                              "k": {"p1": "el gobierno", "p2": "la revista"}})
    ruta = BR.guardar_linea_base(tmp_path)
    base = json.loads(ruta.read_text(encoding="utf-8"))
    assert base["entorno"]["commit"] and base["corpus"]["version"] != "desconocido"
    assert BR.comparar_con_base(BR.evaluar(tmp_path), base) == []

    (tmp_path / "salidas" / "t" / "p1.txt").write_text("el gobiemo de l0s liberale",
                                                      encoding="utf-8")
    import shutil
    shutil.rmtree(tmp_path / "salidas" / "k")
    problemas = BR.comparar_con_base(BR.evaluar(tmp_path), base)
    assert any(p.startswith("t: cer") for p in problemas)
    assert any("k:" in p and "ya no produce" in p for p in problemas)


def test_cli_verificar_devuelve_1_ante_regresion(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path

    from core import proveniencia
    monkeypatch.setattr(proveniencia, "componentes_externos", lambda: {})
    spec = importlib.util.spec_from_file_location(
        "cli_bench", Path(__file__).parent.parent / "scripts" / "benchmark_ocr_regresion.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    _bench(tmp_path, salidas={"t": {"p1": "el gobierno de los liberales",
                                    "p2": "la revista ilustrada"}})
    assert cli.main(["verificar", str(tmp_path)]) == 2  # sin base
    assert cli.main(["base", str(tmp_path)]) == 0
    assert cli.main(["verificar", str(tmp_path)]) == 0
    (tmp_path / "salidas" / "t" / "p2.txt").write_text("xx", encoding="utf-8")
    assert cli.main(["verificar", str(tmp_path)]) == 1
