"""Contrato de las operaciones de corpus extraídas de app.py."""

import pandas as pd

from core import servicios_corpus as SC


def _carpeta(tmp_path):
    img = tmp_path / "02_imagenes" / "E17"
    ocr = tmp_path / "03_ocr" / "E17"
    img.mkdir(parents=True)
    ocr.mkdir(parents=True)
    for p in ("p1", "p2", "p3"):
        (img / f"{p}.png").write_bytes(b"x")
    (ocr / "p1.txt").write_text("uno dos tres", encoding="utf-8")
    return tmp_path


def test_cuenta_solo_paginas_sin_txt(tmp_path):
    out = _carpeta(tmp_path)
    assert SC.contar_paginas_pendientes(out, [tmp_path / "E17.pdf"]) == 2


def test_pdf_sin_rasterizar_se_estima_por_tamano(tmp_path):
    pdf = tmp_path / "E18.pdf"
    pdf.write_bytes(b"0" * 450_000)
    assert SC.contar_paginas_pendientes(tmp_path, [pdf]) == 3
    assert SC.contar_paginas_pendientes(tmp_path, [tmp_path / "no.pdf"]) == 100


def test_sin_carpeta_o_sin_archivos_es_cero(tmp_path):
    assert SC.contar_paginas_pendientes(None, [tmp_path / "x.pdf"]) == 0
    assert SC.contar_paginas_pendientes(tmp_path, []) == 0


def test_reconstruir_meta_escribe_csv(tmp_path):
    out = _carpeta(tmp_path)
    df = SC.reconstruir_meta_corpus(out)
    assert list(df["pagina"]) == ["p1"] and df.loc[0, "palabras"] == 3
    csv = pd.read_csv(out / "04_analisis" / "ocr_metadatos.csv")
    assert csv.loc[0, "numero"] == "E17"


def test_reconstruir_sin_txt_es_none(tmp_path):
    assert SC.reconstruir_meta_corpus(tmp_path) is None
    assert SC.reconstruir_meta_corpus(None) is None


def test_agrupar_prefiere_articulos_y_omite_vacios():
    arts = [{"numero": "E17", "texto": "a"}, {"numero": "E17", "texto": " "},
            {"numero": 18, "texto": "b"}]
    assert SC.agrupar_por_numero(arts, ["ignorado"]) == {"E17": ["a"], "18": ["b"]}
    assert SC.agrupar_por_numero([], ["x", None]) == {"pag_0000": ["x"], "pag_0001": [""]}
    assert SC.agrupar_por_numero() == {}
