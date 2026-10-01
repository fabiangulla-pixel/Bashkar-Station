"""Contrato de los motores de OCR (core/ocr): el mismo para todos.

Los motores reales (Tesseract, CHURRO de 7 GB, PERO, Kraken en otro venv, IA
de pago) se sustituyen por dobles en el punto donde el adaptador los llama;
lo que se prueba es el adaptador: que cumpla el contrato y no altere nada.
"""

from pathlib import Path

import pytest

from core import ocr_churro, ocr_engine, ocr_kraken, ocr_llm, ocr_pero
from core.ocr import MotorOCR, ResultadoOCR, crear, nombres, reconocer_lote
from core.ocr import motores as M


@pytest.fixture
def dobles(monkeypatch):
    """Cada motor devuelve un texto que identifica quién lo produjo."""
    monkeypatch.setattr(ocr_engine, "ocr_pagina", lambda p, lang="spa": (f"tess {Path(p).stem}", 88.0))
    import core.layout_tesseract as LT
    monkeypatch.setattr(LT, "analizar_pagina_local", lambda p, **k: [])
    monkeypatch.setattr(ocr_churro, "ocr_pagina", lambda p: f"churro {Path(p).stem}")
    monkeypatch.setattr(ocr_churro, "liberar", lambda: None)
    monkeypatch.setattr(ocr_pero, "_cargar_motor", lambda cfg: object())
    monkeypatch.setattr(ocr_pero, "ocr_pagina", lambda p, cfg, motor=None: f"pero {Path(p).stem}")
    monkeypatch.setattr(ocr_kraken, "ocr_kraken", lambda p, *a, **k: (f"kraken {Path(p).stem}", 0.9))
    monkeypatch.setattr(ocr_llm, "ocr_con_vision", lambda p, key, modelo=None, proveedor=None:
                        f"ia {Path(p).stem}")


def _crear(nombre, tmp_path):
    opciones = {"config_ini": tmp_path / "config.ini", "api_key": "k"}
    return crear(nombre, **opciones)


@pytest.mark.parametrize("nombre", nombres())
def test_cumple_el_contrato(nombre, dobles, tmp_path):
    motor = _crear(nombre, tmp_path)
    assert isinstance(motor, MotorOCR)
    assert motor.nombre == nombre and motor.etiqueta
    assert isinstance(motor.version(), str) and motor.version()
    motivo = motor.motivo_no_disponible()
    assert motivo is None or (isinstance(motivo, str) and motivo)
    img = tmp_path / "p0007.png"
    img.write_bytes(b"x")
    r = motor.reconocer(img)
    assert isinstance(r, ResultadoOCR)
    assert r.motor == nombre and r.version == motor.version()
    assert r.texto.endswith("p0007")
    assert r.confianza is None or 0 <= r.confianza <= 100
    assert r.segundos >= 0
    motor.liberar()


def test_confianza_de_kraken_se_lleva_a_escala_0_100(dobles, tmp_path):
    img = tmp_path / "p.png"
    img.write_bytes(b"x")
    assert crear("kraken").reconocer(img).confianza == 90.0


def test_motor_desconocido():
    with pytest.raises(ValueError, match="desconocido"):
        crear("magia")


def test_opciones_que_no_aplican_se_ignoran():
    assert crear("tesseract", lang="lat", api_key="x", out_dir="y").lang == "lat"


def test_lote_libera_aunque_falle_una_pagina(tmp_path):
    class Fragil:
        nombre, etiqueta = "fragil", "x"
        liberado = False

        def reconocer(self, img):
            if img.stem == "p2":
                raise RuntimeError("página dañada")
            return ResultadoOCR("ok", "fragil", "1")

        def liberar(self):
            Fragil.liberado = True

    with pytest.raises(RuntimeError):
        reconocer_lote(Fragil(), [tmp_path / "p1.png", tmp_path / "p2.png"], lambda m: None)
    assert Fragil.liberado


def test_registro_y_benchmark_coinciden():
    from core.benchmark_ocr import catalogo_rutas
    assert [c[0] for c in catalogo_rutas()] == list(M.RUTAS_BENCHMARK)
    assert set(M.RUTAS_BENCHMARK) <= set(nombres())
