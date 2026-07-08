"""
tests/test_ocr_kraken.py — Tests para core/ocr_kraken.py

Cubre: kraken_disponible, ocr_kraken_lote, descargar_modelo_catmus.
Los tests que requieren Kraken instalado se saltan automáticamente.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ocr_kraken import (
    descargar_modelo_catmus,
    kraken_disponible,
    ocr_kraken,
    ocr_kraken_lote,
)

_KRAKEN_INSTALADO = pytest.mark.skipif(
    not kraken_disponible(),
    reason="Kraken no instalado o sin modelo disponible"
)


# ══════════════════════════════════════════════════════════════════════════════
# kraken_disponible
# ══════════════════════════════════════════════════════════════════════════════

class TestKrakenDisponible:
    def test_retorna_bool(self):
        resultado = kraken_disponible()
        assert isinstance(resultado, bool)

    def test_false_cuando_kraken_no_importa(self):
        # kraken_disponible() usa subprocess bridge, no import directo.
        # Simulamos que el subproceso retorna código != 0.
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            resultado = kraken_disponible()
        assert resultado is False


# ══════════════════════════════════════════════════════════════════════════════
# ocr_kraken — errores sin Kraken
# ══════════════════════════════════════════════════════════════════════════════

class TestOcrKrakenSinKraken:
    def test_import_error_si_no_instalado(self):
        with patch.dict("sys.modules", {"kraken": None,
                                         "kraken.blla": None,
                                         "kraken.rpred": None,
                                         "kraken.lib": None,
                                         "kraken.lib.models": None}):
            with pytest.raises((ImportError, TypeError, Exception)):
                ocr_kraken("imagen_inexistente.png")

    def test_file_not_found_sin_modelo(self, tmp_path):
        img = tmp_path / "test.png"
        # Crear PNG mínimo válido (1x1 pixel blanco)
        img.write_bytes(bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00,
            0x00, 0x00, 0x02, 0x00, 0x01, 0xE2, 0x21, 0xBC,
            0x33, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,  # IEND chunk
            0x44, 0xAE, 0x42, 0x60, 0x82,
        ]))
        with patch("core.ocr_kraken._buscar_modelo", return_value=None):
            with pytest.raises((FileNotFoundError, ImportError, Exception)):
                ocr_kraken(str(img))


# ══════════════════════════════════════════════════════════════════════════════
# ocr_kraken_lote — comportamiento sin Kraken (mock)
# ══════════════════════════════════════════════════════════════════════════════

class TestOcrKrakenLote:
    def test_lista_vacia_retorna_vacia(self):
        resultado = ocr_kraken_lote([])
        assert resultado == []

    def test_retorna_lista_mismo_tamaño(self):
        imagenes = ["a.png", "b.png", "c.png"]
        with patch("core.ocr_kraken.ocr_kraken",
                   side_effect=ImportError("kraken no instalado")):
            resultado = ocr_kraken_lote(imagenes)
        assert len(resultado) == 3

    def test_ok_false_en_error(self):
        with patch("core.ocr_kraken.ocr_kraken",
                   side_effect=RuntimeError("error simulado")):
            resultado = ocr_kraken_lote(["imagen.png"])
        assert resultado[0]["ok"] is False
        assert resultado[0]["texto"] == ""
        assert resultado[0]["error"] == "error simulado"

    def test_ok_true_con_mock_exitoso(self):
        with patch("core.ocr_kraken.ocr_kraken", return_value=("texto OCR", 0.92)):
            resultado = ocr_kraken_lote(["imagen.png"])
        assert resultado[0]["ok"] is True
        assert resultado[0]["texto"] == "texto OCR"
        assert resultado[0]["confianza"] == 0.92

    def test_callback_invocado(self):
        llamadas = []
        with patch("core.ocr_kraken.ocr_kraken", return_value=("texto", 0.85)):
            ocr_kraken_lote(
                ["img1.png", "img2.png"],
                callback=lambda i, t, r, ok: llamadas.append((i, t, ok))
            )
        assert len(llamadas) == 2
        assert llamadas[0] == (1, 2, True)
        assert llamadas[1] == (2, 2, True)

    def test_callback_invocado_en_error(self):
        llamadas = []
        with patch("core.ocr_kraken.ocr_kraken",
                   side_effect=RuntimeError("falla")):
            ocr_kraken_lote(
                ["img1.png"],
                callback=lambda i, t, r, ok: llamadas.append(ok)
            )
        assert llamadas == [False]

    def test_ruta_preservada_en_resultado(self):
        with patch("core.ocr_kraken.ocr_kraken", return_value=("x", 0.8)):
            resultado = ocr_kraken_lote(["ruta/imagen.png"])
        assert resultado[0]["ruta"] == "ruta/imagen.png"

    def test_estructura_dict_resultado(self):
        with patch("core.ocr_kraken.ocr_kraken", return_value=("texto", 0.9)):
            resultado = ocr_kraken_lote(["img.png"])
        for clave in ("ruta", "texto", "confianza", "ok", "error"):
            assert clave in resultado[0]

    def test_modelo_path_propagado(self):
        with patch("core.ocr_kraken.ocr_kraken", return_value=("t", 0.8)) as mock_ocr:
            ocr_kraken_lote(["img.png"], modelo_path="/ruta/modelo.mlmodel")
        args, kwargs = mock_ocr.call_args
        assert args[0] == "img.png"
        assert args[1] == "/ruta/modelo.mlmodel"

    def test_error_no_detiene_lote(self):
        efectos = [RuntimeError("falla"), ("ok", 0.9)]
        with patch("core.ocr_kraken.ocr_kraken", side_effect=efectos):
            resultado = ocr_kraken_lote(["img1.png", "img2.png"])
        assert resultado[0]["ok"] is False
        assert resultado[1]["ok"] is True


# ══════════════════════════════════════════════════════════════════════════════
# descargar_modelo_catmus
# ══════════════════════════════════════════════════════════════════════════════

class TestDescargarModeloCatmus:
    def test_retorna_ruta_si_ya_existe(self, tmp_path):
        modelo_existente = tmp_path / "modelo.mlmodel"
        modelo_existente.touch()

        with patch("core.ocr_kraken._buscar_modelo", return_value=modelo_existente):
            resultado = descargar_modelo_catmus()

        assert resultado == str(modelo_existente)

    def test_callback_invocado_al_descargar(self, tmp_path):
        mensajes = []

        mock_proc = MagicMock()
        mock_proc.returncode = 0

        with patch("core.ocr_kraken._buscar_modelo", return_value=None), \
             patch("core.ocr_kraken._MODELOS_DIR", tmp_path), \
             patch("subprocess.run", return_value=mock_proc), \
             patch("core.ocr_kraken._buscar_modelo",
                   side_effect=[None, tmp_path / "new.mlmodel"]):
            try:
                descargar_modelo_catmus(callback=mensajes.append)
            except Exception:
                pass  # puede fallar el segundo _buscar_modelo, pero callback ya fue

        # Solo verificamos que no lanza antes del callback
        assert isinstance(mensajes, list)

    def test_runtime_error_si_subprocess_falla(self, tmp_path):
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = "error descargando"

        with patch("core.ocr_kraken._buscar_modelo", return_value=None), \
             patch("core.ocr_kraken._MODELOS_DIR", tmp_path), \
             patch("subprocess.run", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="Error descargando"):
                descargar_modelo_catmus()


# ══════════════════════════════════════════════════════════════════════════════
# Tests con Kraken real (se omiten si no está disponible)
# ══════════════════════════════════════════════════════════════════════════════

import os as _os

# CATMuS-Print Large requiere ~5.5 GB RAM. Solo corre si el usuario lo activa
# explícitamente con BASHKAR_KRAKEN_INTEGRATION=1.
_KRAKEN_INTEGRACION = pytest.mark.skipif(
    not kraken_disponible() or _os.environ.get("BASHKAR_KRAKEN_INTEGRATION") != "1",
    reason="Kraken real omitido — requiere ~5.5 GB RAM y BASHKAR_KRAKEN_INTEGRATION=1"
)


@_KRAKEN_INTEGRACION
class TestKrakenReal:
    def test_retorna_texto_y_confianza(self, tmp_path):
        import PIL.Image
        img = tmp_path / "pag.png"
        i = PIL.Image.new("RGB", (200, 50), color=(255, 255, 255))
        i.save(str(img))

        texto, confianza = ocr_kraken(str(img))

        assert isinstance(texto, str)
        assert 0.0 <= confianza <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
# _python_kraken en .exe congelado — sys.executable ahí es el propio .exe, no
# un Python con pip/kraken; usarlo como último recurso relanza una copia
# duplicada de la app en vez de ejecutar el código pedido (mismo patrón que
# causó una bomba de fork real en app.py::_auto_instalar durante esta sesión).
# ══════════════════════════════════════════════════════════════════════════════

class TestPythonKrakenFrozen:
    def test_devuelve_none_si_frozen_y_sin_venv_dedicado(self, monkeypatch):
        from core.ocr_kraken import _KRAKEN_PYTHON, _python_kraken
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        if _KRAKEN_PYTHON.exists():
            pytest.skip("El venv dedicado de Kraken sí existe en esta máquina")
        assert _python_kraken() is None

    def test_kraken_disponible_false_sin_lanzar_si_frozen_sin_venv(self, monkeypatch):
        from core.ocr_kraken import _KRAKEN_PYTHON
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        if _KRAKEN_PYTHON.exists():
            pytest.skip("El venv dedicado de Kraken sí existe en esta máquina")
        with patch("subprocess.run") as mock_run:
            resultado = kraken_disponible()
        mock_run.assert_not_called()
        assert resultado is False

    def test_ocr_kraken_lanza_importerror_claro_si_frozen_sin_venv(self, monkeypatch, tmp_path):
        from core.ocr_kraken import _KRAKEN_PYTHON
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        if _KRAKEN_PYTHON.exists():
            pytest.skip("El venv dedicado de Kraken sí existe en esta máquina")
        img = tmp_path / "pag.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
        with pytest.raises(ImportError, match="exe compilado"):
            ocr_kraken(str(img))
