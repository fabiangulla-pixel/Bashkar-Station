"""Procedencia del OCR: cada página dice qué motor la leyó de verdad."""

from core.ocr.procedencia import fila_meta, version_de


def test_motor_normal():
    f = fila_meta("E17", "p1", "x/p1.txt", "uno dos tres", motor="kraken",
                  version="kraken modelo=catmus", confianza=88.0)
    assert f["metodo"] == "kraken" and f["motor_version"] == "kraken modelo=catmus"
    assert f["palabras"] == 3 and f["revision"] is False


def test_respaldo_queda_registrado_y_marcado():
    f = fila_meta("E17", "p1", "x", "texto", motor="tesseract", version="tesseract 5.4",
                  confianza=91.0, respaldo_de="vision_claude")
    assert f["metodo"] == "tesseract_respaldo_de_vision_claude"
    assert f["revision"] is True          # aunque la confianza sea alta


def test_sin_confianza_medida_es_none_no_cero_ni_95():
    f = fila_meta("E17", "p1", "x", "texto", motor="vision_claude")
    assert f["confianza"] is None and f["revision"] is False


def test_baja_confianza_se_marca():
    assert fila_meta("E", "p", "x", "t", motor="tesseract", confianza=42.0)["revision"]


def test_version_de_nunca_lanza():
    assert version_de("motor_inexistente") == "desconocida"
    assert version_de("tesseract").startswith("tesseract")


def test_el_worker_no_vuelve_a_inventar_confianza():
    """Guarda estática: la ruta de visión anotaba conf = 95.0 en cada página."""
    from tests._gui_fuente import fuente_gui
    assert "conf = 95.0" not in fuente_gui()
    assert "conf  = 95.0" not in fuente_gui()


def test_procedencia_pagina_desde_metadatos():
    import pandas as pd

    from core.servicios_corpus import procedencia_pagina
    meta = pd.DataFrame({"numero": ["E17", "E17"], "pagina": ["p1", "p2"],
                         "metodo": ["kraken", "ocr"],
                         "motor_version": ["kraken modelo=catmus", None]})
    assert procedencia_pagina(meta, "E17", "p1") == ("kraken", "kraken modelo=catmus")
    assert procedencia_pagina(meta, "E17", "p2") == ("ocr", "")       # sin versión: vacío
    assert procedencia_pagina(meta, "E99", "p1") == ("", "")
    assert procedencia_pagina(None, "E17", "p1") == ("", "")
    assert procedencia_pagina({"dict": 1}, "E17", "p1") == ("", "")


def test_normalizar_guarda_motor_y_version(tmp_path, monkeypatch):
    import pandas as pd

    import app
    from datos import normalizaciones as NZ
    monkeypatch.setattr(app.ST, "corpus_meta", pd.DataFrame(
        {"numero": ["E17"], "pagina": ["p1"], "metodo": ["ocr"],
         "motor_version": ["tesseract 5.4 lang=spa"]}))
    db = tmp_path / "p.db"
    assert app.BashkarApp._norm_escribir_db(object(), db, "E17", "p1", "crudo", "rev", "")
    fila = NZ.leer(db, "E17", "p1")
    assert (fila["ocr_motor"], fila["ocr_version"]) == ("ocr", "tesseract 5.4 lang=spa")
