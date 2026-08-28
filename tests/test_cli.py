"""tests/test_cli.py — regresión de la etapa de segmentación del CLI."""

import json
import subprocess
import sys
from pathlib import Path

from cli import _etapa_seg


def test_etapa_seg_segmenta_sin_typeerror(tmp_path: Path):
    """segmentar_numero() exige (ocr_dir, nombre); una llamada con un solo
    argumento posicional revienta con TypeError, silenciada por el except
    genérico de _etapa_seg (0 artículos sin ningún aviso claro). Ver s.59/60
    de [[project_bashkar_station]]."""
    out_dir = tmp_path / "salida"
    num_dir = out_dir / "03_ocr" / "rev_estampa_ene_1939"
    num_dir.mkdir(parents=True)
    texto = ("Un artículo de prueba con suficientes palabras para superar "
              "el umbral mínimo de quince palabras que exige el segmentador "
              "antes de descartar la página como vacía.")
    (num_dir / "p0001.txt").write_text(texto, encoding="utf-8")

    articulos = _etapa_seg({"out_dir": str(out_dir)}, verbose=False)

    assert articulos, "la segmentación debería producir al menos un artículo"
    assert (out_dir / "segmentacion.csv").exists()


def test_info_no_revienta_en_consola_cp1252(tmp_path: Path):
    """--info imprime ✅/⬜ (fuera de cp1252); en una consola real de Windows
    (no UTF-8 por defecto) esto reventaba con UnicodeEncodeError a mitad de
    la salida. Se reproduce forzando PYTHONIOENCODING=cp1252 en un subproceso
    real — monkeypatchear sys.stdout no dispara el mismo camino de encoding."""
    proyecto = tmp_path / "test.bashkar"
    proyecto.write_text(json.dumps({
        "nombre": "Test", "config": {"publicacion": "Estampa", "periodo": "1939",
                                       "out_dir": str(tmp_path), "archivos_sel": []},
        "progreso": {"ocr": True, "seg": False}, "resultados": {},
        "modificado": "2026-01-01",
    }), encoding="utf-8")

    raiz = Path(__file__).resolve().parent.parent
    r = subprocess.run(
        [sys.executable, str(raiz / "cli.py"), "--proyecto", str(proyecto), "--info"],
        capture_output=True, text=True, cwd=raiz,
        env={"PYTHONIOENCODING": "cp1252", "PATH": __import__("os").environ.get("PATH", "")},
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    assert "UnicodeEncodeError" not in r.stderr
