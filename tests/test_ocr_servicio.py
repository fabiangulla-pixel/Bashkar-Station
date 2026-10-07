"""core.ocr.servicio y Bloque: la secuencia de OCR compartida por GUI y API."""

import json

import pytest

from core.ocr import Bloque, ResultadoOCR
from core.ocr.motores import bloques_de_zonas
from core.ocr.servicio import cargar_bloques, ocr_pagina, ruta_bloques


class _Motor:
    def __init__(self, nombre, texto="hola", bloques=(), falla=False, conf=88.0):
        self.nombre, self.etiqueta = nombre, nombre
        self._texto, self._bloques, self._falla, self._conf = texto, list(bloques), falla, conf
        self.llamadas = 0

    def motivo_no_disponible(self):
        return None

    def version(self):
        return f"{self.nombre} 1.0"

    def reconocer(self, imagen):
        self.llamadas += 1
        if self._falla:
            raise RuntimeError("se cayó")
        return ResultadoOCR(self._texto, self.nombre, self.version(),
                            confianza=self._conf, bloques=list(self._bloques))

    def liberar(self):
        pass


def test_bloque_ida_y_vuelta():
    b = Bloque("Título", (1, 2, 30, 40), tipo="titulo", orden=1, confianza=90.0,
               poligono=[(1, 2), (30, 2), (30, 40)], alternativas=[{"motor": "x", "texto": "T"}])
    assert Bloque.de_dict(json.loads(json.dumps(b.a_dict()))) == b


def test_bloques_de_zonas_mapea_tipos_y_omite_sin_bbox():
    zonas = [{"orden": 1, "tipo": "titulo", "texto": "A", "confianza": 80, "bbox": [0, 0, 5, 5]},
             {"orden": 2, "tipo": "pie_foto", "texto": "B", "confianza": 70, "bbox": [0, 5, 5, 9]},
             {"orden": 3, "tipo": "rarisimo", "texto": "C", "confianza": 70, "bbox": [1, 1, 2, 2]},
             {"orden": 4, "tipo": "articulo", "texto": "D", "confianza": 70}]
    bs = bloques_de_zonas(zonas)
    assert [b.tipo for b in bs] == ["titulo", "pie_imagen", "desconocido"]
    assert bs[0].bbox == (0, 0, 5, 5)


def test_escribe_texto_y_bloques(tmp_path):
    m = _Motor("surya", "texto", [Bloque("texto", (0, 0, 10, 10), orden=1)])
    tp = tmp_path / "p0001.txt"
    r, fila = ocr_pagina(m, tmp_path / "p0001.png", tp, "E1")
    assert tp.read_text("utf-8") == "texto"
    assert cargar_bloques(tp)[0].bbox == (0, 0, 10, 10)
    assert fila["metodo"] == "surya" and fila["bloques"] == 1 and fila["confianza"] == 88.0
    assert not fila["revision"]


def test_motor_sin_geometria_borra_bloques_viejos(tmp_path):
    tp = tmp_path / "p0001.txt"
    ruta_bloques(tp).write_text('{"bloques": []}', "utf-8")
    ocr_pagina(_Motor("tesseract"), tmp_path / "p0001.png", tp, "E1")
    assert not ruta_bloques(tp).exists()


def test_respaldo_queda_registrado_con_alias(tmp_path):
    tp = tmp_path / "p0001.txt"
    _, fila = ocr_pagina(_Motor("vision_llm", falla=True), tmp_path / "p0001.png", tp, "E1",
                         respaldo=_Motor("tesseract", "resp"), alias="vision_claude")
    assert fila["metodo"] == "tesseract_respaldo_de_vision_claude"
    assert fila["revision"] and tp.read_text("utf-8") == "resp"


def test_ambos_fallan_pagina_vacia_marcada(tmp_path):
    tp = tmp_path / "p0001.txt"
    r, fila = ocr_pagina(_Motor("a", falla=True), tmp_path / "p0001.png", tp, "E1",
                         respaldo=_Motor("b", falla=True))
    assert r is None and fila["revision"] and fila["metodo"].startswith("ninguno")
    assert tp.read_text("utf-8") == ""


def test_sin_respaldo_falla_marcada(tmp_path):
    tp = tmp_path / "p0001.txt"
    r, fila = ocr_pagina(_Motor("a", falla=True), tmp_path / "p0001.png", tp, "E1")
    assert r is None and fila["revision"]


def test_reusar_no_llama_al_motor(tmp_path):
    tp = tmp_path / "p0001.txt"
    tp.write_text("previo", "utf-8")
    m = _Motor("x")
    _, fila = ocr_pagina(m, tmp_path / "p0001.png", tp, "E1", reusar=True)
    assert m.llamadas == 0 and fila["confianza"] is None and fila["reusado"]


def test_bloque_a_revisar_marca_la_pagina(tmp_path):
    m = _Motor("x", bloques=[Bloque("t", (0, 0, 1, 1), revisar=True)])
    _, fila = ocr_pagina(m, tmp_path / "p.png", tmp_path / "p.txt", "E1")
    assert fila["revision"]


@pytest.mark.parametrize("campo", ["texto", "bbox", "tipo", "orden", "confianza", "revisar"])
def test_a_dict_tiene_campos(campo):
    assert campo in Bloque("t", (0, 0, 1, 1)).a_dict()


def test_metadatos_conservan_marca_previa_de_revision(tmp_path):
    """_worker_ocr_carpetas recalculaba 'revision' solo con la confianza y borraba
    la marca de las páginas que salieron de un respaldo (sesión 72)."""
    import pandas as pd

    from core.ocr.servicio import guardar_metadatos
    filas = [{"numero": "E", "pagina": "p1", "txt_path": "x", "palabras": 10, "confianza": 95.0,
              "revision": True, "metodo": "tesseract_respaldo_de_kraken"},
             {"numero": "E", "pagina": "p2", "txt_path": "y", "palabras": 10, "confianza": 40.0,
              "revision": False},
             {"numero": "E", "pagina": "p3", "txt_path": "z", "palabras": 10, "confianza": None,
              "revision": False}]
    df = pd.read_csv(guardar_metadatos(filas, tmp_path))
    assert df["revision"].tolist() == [True, True, False]


def test_metadatos_vacios_no_revientan(tmp_path):
    from core.ocr.servicio import tabla_metadatos
    assert tabla_metadatos([]).empty


def _pdf_digital(ruta):
    import pymupdf
    doc = pymupdf.open()
    pg = doc.new_page()
    pg.insert_text((72, 72), "La revista publicó una crónica sobre el embajador. " * 3)
    doc.save(ruta)


def _pdf_escaneado(ruta, tmp_path):
    """Como los de la BNC: una imagen que cubre la página + texto invisible encima."""
    import pymupdf
    from PIL import Image
    png = tmp_path / "scan.png"
    Image.new("RGB", (600, 800), "white").save(png)
    doc = pymupdf.open()
    pg = doc.new_page()
    pg.insert_image(pg.rect, filename=str(png))
    pg.insert_text((72, 72), "LO QUE HA PASAPO lo patria Mortínez " * 3, render_mode=3)
    doc.save(ruta)


def test_texto_nativo_solo_en_paginas_digitales(tmp_path):
    """Sesión 72: el enrutador tomaba la capa OCR de la BNC por texto nativo."""
    from core.ocr.servicio import textos_nativos_utiles
    dig, esc = tmp_path / "dig.pdf", tmp_path / "esc.pdf"
    _pdf_digital(dig)
    _pdf_escaneado(esc, tmp_path)
    assert "embajador" in textos_nativos_utiles(dig)[0]
    assert textos_nativos_utiles(esc) == [None]


def test_cobertura_imagen(tmp_path):
    import pymupdf

    from core.ocr.servicio import cobertura_imagen
    esc = tmp_path / "esc.pdf"
    _pdf_escaneado(esc, tmp_path)
    with pymupdf.open(esc) as d:
        assert cobertura_imagen(d[0]) > 0.9   # la imagen conserva su proporción
