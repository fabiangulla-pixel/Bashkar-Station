"""tests/test_ocr_vision_lote.py — scripts/ocr_vision_lote.py sin red real."""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ocr_vision_lote.py"
_spec = importlib.util.spec_from_file_location("ocr_vision_lote", _SCRIPT_PATH)
lote = importlib.util.module_from_spec(_spec)
sys.modules["ocr_vision_lote"] = lote
_spec.loader.exec_module(lote)


class TestPaginasPendientes:
    def test_salta_paginas_ya_transcritas(self, tmp_path):
        imagenes = tmp_path / "imagenes"
        salida = tmp_path / "salida"
        imagenes.mkdir()
        salida.mkdir()
        (imagenes / "p0001.jpg").write_bytes(b"\xff\xd8\xff")
        (imagenes / "p0002.jpg").write_bytes(b"\xff\xd8\xff")
        (salida / "p0001.txt").write_text("ya transcrita", encoding="utf-8")

        pendientes = lote._paginas_pendientes(imagenes, salida, forzar=False)

        assert [p.stem for p in pendientes] == ["p0002"]

    def test_forzar_incluye_todas(self, tmp_path):
        imagenes = tmp_path / "imagenes"
        salida = tmp_path / "salida"
        imagenes.mkdir()
        salida.mkdir()
        (imagenes / "p0001.jpg").write_bytes(b"\xff\xd8\xff")
        (salida / "p0001.txt").write_text("ya transcrita", encoding="utf-8")

        pendientes = lote._paginas_pendientes(imagenes, salida, forzar=True)

        assert len(pendientes) == 1

    def test_sin_salida_previa_incluye_todas(self, tmp_path):
        imagenes = tmp_path / "imagenes"
        salida = tmp_path / "no_existe_todavia"
        imagenes.mkdir()
        (imagenes / "p0001.jpg").write_bytes(b"\xff\xd8\xff")
        (imagenes / "p0002.jpg").write_bytes(b"\xff\xd8\xff")

        pendientes = lote._paginas_pendientes(imagenes, salida, forzar=False)

        assert len(pendientes) == 2


class TestMainFlujoCompleto:
    def _preparar_imagenes(self, tmp_path, n=2):
        imagenes = tmp_path / "imagenes"
        imagenes.mkdir()
        for i in range(1, n + 1):
            (imagenes / f"p{i:04d}.jpg").write_bytes(b"\xff\xd8\xff")
        return imagenes

    def test_dry_run_no_escribe_nada(self, tmp_path, monkeypatch, capsys):
        imagenes = self._preparar_imagenes(tmp_path)
        salida = tmp_path / "salida"
        monkeypatch.setattr(sys, "argv", [
            "ocr_vision_lote.py",
            "--imagenes-dir", str(imagenes),
            "--salida-dir", str(salida),
            "--dry-run",
        ])
        codigo = lote.main()
        assert codigo == 0
        assert not salida.exists()
        assert "COSTO ESTIMADO" in capsys.readouterr().out

    def test_transcribe_y_escribe_resultados(self, tmp_path, monkeypatch):
        imagenes = self._preparar_imagenes(tmp_path, n=3)
        salida = tmp_path / "salida"
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-para-test")
        monkeypatch.setattr(sys, "argv", [
            "ocr_vision_lote.py",
            "--imagenes-dir", str(imagenes),
            "--salida-dir", str(salida),
            "--concurrencia", "2",
        ])

        from core import ocr_llm
        monkeypatch.setattr(ocr_llm, "ocr_con_vision",
                             lambda img, key, modelo, proveedor: f"texto de {img.stem}")
        monkeypatch.setattr(ocr_llm, "usages", lambda: [MagicMock(input_tokens=100, output_tokens=50)])
        monkeypatch.setattr(ocr_llm, "reset_usages", lambda: None)

        codigo = lote.main()

        assert codigo == 0
        assert (salida / "p0001.txt").read_text(encoding="utf-8") == "texto de p0001"
        assert (salida / "p0002.txt").read_text(encoding="utf-8") == "texto de p0002"
        assert (salida / "p0003.txt").read_text(encoding="utf-8") == "texto de p0003"

    def test_transcripcion_vacia_se_reporta_sin_tumbar_el_lote(self, tmp_path, monkeypatch):
        imagenes = self._preparar_imagenes(tmp_path, n=2)
        salida = tmp_path / "salida"
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-para-test")
        monkeypatch.setattr(sys, "argv", [
            "ocr_vision_lote.py",
            "--imagenes-dir", str(imagenes),
            "--salida-dir", str(salida),
            "--concurrencia", "2",
        ])

        from core import ocr_llm

        def _fake(img, key, modelo, proveedor):
            return "" if img.stem == "p0001" else "texto real"
        monkeypatch.setattr(ocr_llm, "ocr_con_vision", _fake)
        monkeypatch.setattr(ocr_llm, "usages", lambda: [])
        monkeypatch.setattr(ocr_llm, "reset_usages", lambda: None)

        codigo = lote.main()

        assert codigo == 0  # hay al menos 1 resultado real, no se cuenta como fallo total
        assert not (salida / "p0001.txt").exists()
        assert (salida / "p0002.txt").read_text(encoding="utf-8") == "texto real"

    def test_sin_api_key_falla_temprano_sin_dry_run(self, tmp_path, monkeypatch):
        imagenes = self._preparar_imagenes(tmp_path, n=1)
        salida = tmp_path / "salida"
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setattr(sys, "argv", [
            "ocr_vision_lote.py",
            "--imagenes-dir", str(imagenes),
            "--salida-dir", str(salida),
        ])
        assert lote.main() == 1
