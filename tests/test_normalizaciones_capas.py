"""Capas de normalización: el OCR original nunca se pierde.

Reproduce el ciclo real del panel Normalizar: guardar escribe el texto final
en el .txt de la página, y la sesión siguiente relee ese .txt como "OCR crudo".
"""

import sqlite3

from datos import normalizaciones as NZ


def _db(tmp_path):
    return tmp_path / "proyecto.db"


def test_segunda_sesion_no_pisa_el_ocr_original(tmp_path):
    db = _db(tmp_path)
    NZ.guardar(db, "E17", "p0001", ocr_crudo="gobiemo presidenle",
               norm_usuario="gobierno presidente", norm_ia="")
    # Sesión 2: el .txt ya tiene el texto corregido y el panel lo manda como crudo.
    NZ.guardar(db, "E17", "p0001", ocr_crudo="gobierno presidente",
               norm_usuario="gobierno presidente.", norm_ia="")
    fila = NZ.leer(db, "E17", "p0001")
    assert fila["ocr_crudo"] == "gobiemo presidenle"
    assert fila["norm_usuario"] == "gobierno presidente."


def test_crudo_vacio_se_completa_la_primera_vez_que_llega(tmp_path):
    db = _db(tmp_path)
    NZ.guardar(db, "E", "p1", ocr_crudo="", norm_usuario="", norm_ia="x")
    NZ.guardar(db, "E", "p1", ocr_crudo="texto motor", norm_usuario="", norm_ia="x")
    assert NZ.leer(db, "E", "p1")["ocr_crudo"] == "texto motor"


def test_cada_capa_tiene_su_propia_marca_de_tiempo(tmp_path, monkeypatch):
    db = _db(tmp_path)
    horas = iter(["2026-01-01T10:00:00", "2026-01-02T10:00:00", "2026-01-03T10:00:00"])
    monkeypatch.setattr(NZ, "_ahora", lambda: next(horas))
    NZ.guardar(db, "E", "p1", ocr_crudo="a", norm_usuario="", norm_ia="ia1")
    NZ.guardar(db, "E", "p1", ocr_crudo="a", norm_usuario="humano", norm_ia="ia1")
    fila = NZ.leer(db, "E", "p1")
    assert fila["ts_ia"] == "2026-01-01T10:00:00"
    assert fila["ts_usuario"] == "2026-01-02T10:00:00"
    # Guardar sin cambios no mueve ninguna marca.
    assert NZ.guardar(db, "E", "p1", ocr_crudo="a", norm_usuario="humano",
                      norm_ia="ia1") == []
    assert NZ.leer(db, "E", "p1")["ts_usuario"] == "2026-01-02T10:00:00"


def test_historial_registra_solo_cambios_con_autor_y_commit(tmp_path):
    db = _db(tmp_path)
    NZ.guardar(db, "E", "p1", ocr_crudo="a", norm_usuario="", norm_ia="b",
               autor_ia="modelo-x", ocr_motor="tesseract", commit_software="abc")
    NZ.guardar(db, "E", "p1", ocr_crudo="a", norm_usuario="c", norm_ia="b",
               autor_usuario="fabian", commit_software="abc")
    h = NZ.historial(db, "E", "p1")
    assert [(r["capa"], r["autor"]) for r in h] == [
        ("ocr_crudo", "tesseract"), ("norm_ia", "modelo-x"), ("norm_usuario", "fabian")]
    assert all(r["commit_software"] == "abc" for r in h)
    fila = NZ.leer(db, "E", "p1")
    assert fila["autor_ia"] == "modelo-x" and fila["autor_usuario"] == "fabian"


def test_migra_tabla_de_un_proyecto_existente_sin_perder_filas(tmp_path):
    db = _db(tmp_path)
    con = sqlite3.connect(db)
    con.executescript("""CREATE TABLE normalizaciones (
        numero TEXT NOT NULL, pagina TEXT NOT NULL, ocr_crudo TEXT,
        norm_usuario TEXT, norm_ia TEXT, ts_usuario TEXT, ts_ia TEXT,
        PRIMARY KEY (numero, pagina));
        INSERT INTO normalizaciones VALUES ('E','p1','viejo','rev','', 't','t');""")
    con.commit()
    con.close()
    fila = NZ.leer(db, "E", "p1")
    assert fila["ocr_crudo"] == "viejo" and "commit_software" in fila
    NZ.guardar(db, "E", "p1", ocr_crudo="rev", norm_usuario="rev2", norm_ia="")
    assert NZ.leer(db, "E", "p1")["ocr_crudo"] == "viejo"


def test_error_de_escritura_se_propaga(tmp_path):
    carpeta = tmp_path / "no_es_un_archivo"
    carpeta.mkdir()
    try:
        NZ.guardar(carpeta, "E", "p1", ocr_crudo="a", norm_usuario="", norm_ia="")
    except sqlite3.Error:
        return
    raise AssertionError("un fallo de SQLite no debe pasar en silencio")


def test_estado_epistemico():
    assert NZ.estado_epistemico(None) == "sin_datos"
    assert NZ.estado_epistemico({"ocr_crudo": "x"}) == "ocr"
    assert NZ.estado_epistemico({"ocr_crudo": "x", "norm_ia": "y"}) == "corregido_ia"
    assert NZ.estado_epistemico({"ocr_crudo": "x", "norm_ia": "y",
                                 "norm_usuario": "z"}) == "revisado"
    assert NZ.estado_epistemico({"norm_usuario": "  "}) == "sin_datos"
