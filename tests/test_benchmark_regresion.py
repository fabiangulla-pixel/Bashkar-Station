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


def test_catalogo_rutas_siempre_ofrece_tesseract_y_declara_estado():
    from core.benchmark_ocr import catalogo_rutas
    cat = catalogo_rutas()
    claves = [c[0] for c in cat]
    assert claves[:2] == ["tesseract", "zonas"]
    assert {"churro", "pero"} <= set(claves)
    assert all(len(c) == 3 for c in cat)


def test_correr_ruta_tesseract_mide_tiempo_y_usa_stem(tmp_path, monkeypatch):
    from core import benchmark_ocr, ocr_engine
    monkeypatch.setattr(ocr_engine, "ocr_pagina", lambda p, lang="spa": (f"txt {p.stem}", 90.0))
    log = []
    out = benchmark_ocr.correr_ruta("tesseract", [tmp_path / "p1.jpg"], log.append)
    assert out == {"p1": "txt p1"}
    assert log and log[0].strip().startswith("1/1  p1")


def test_correr_ruta_desconocida_falla():
    from core import benchmark_ocr
    with pytest.raises(ValueError):
        benchmark_ocr.correr_ruta("magia", [], print)


def test_churro_se_libera_aunque_falle_el_lote(tmp_path, monkeypatch):
    from core import benchmark_ocr, ocr_churro
    liberado = []
    monkeypatch.setattr(ocr_churro, "ocr_pagina", lambda p: 1 / 0)
    monkeypatch.setattr(ocr_churro, "liberar", lambda: liberado.append(True))
    with pytest.raises(ZeroDivisionError):
        benchmark_ocr.correr_ruta("churro", [tmp_path / "p1.jpg"], lambda m: None)
    assert liberado == [True]


def test_generar_salidas_escribe_por_page_id(tmp_path, monkeypatch):
    from core import benchmark_ocr
    _bench(tmp_path)
    (tmp_path / "imagenes").mkdir()
    (tmp_path / "imagenes" / "p1.jpg").write_bytes(b"x")
    monkeypatch.setattr(benchmark_ocr, "correr_ruta",
                        lambda ruta, imgs, log: {i.stem: f"{ruta}:{i.stem}" for i in imgs})
    assert BR.generar_salidas(tmp_path, "zonas") == 1
    assert (tmp_path / "salidas" / "zonas" / "p1.txt").read_text(encoding="utf-8") == "zonas:p1"


def test_ruta_zonas_no_modifica_la_imagen_original(tmp_path, monkeypatch):
    """El deskew de analizar_pagina_local guarda encima del archivo: la ruta
    debe trabajar sobre una copia para no alterar imágenes de referencia."""
    from core import benchmark_ocr, layout_tesseract

    def analizar_que_escribe(ruta, **kw):
        ruta.write_bytes(b"ENDEREZADA")
        return ["zona"]
    monkeypatch.setattr(layout_tesseract, "analizar_pagina_local", analizar_que_escribe)
    monkeypatch.setattr(layout_tesseract, "ocr_por_zonas",
                        lambda ruta, zonas: {"texto": "texto por zonas"})
    img = tmp_path / "p1.jpg"
    img.write_bytes(b"ORIGINAL")
    assert benchmark_ocr.correr_ruta("zonas", [img], lambda m: None) == {"p1": "texto por zonas"}
    assert img.read_bytes() == b"ORIGINAL"
