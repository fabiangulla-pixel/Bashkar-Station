"""tests/test_cli.py — regresión de la etapa de segmentación del CLI."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from cli import _etapa_ner, _etapa_ocr, _etapa_seg


def test_etapa_ocr_sobre_pdf_real_sin_importerror(tmp_path: Path):
    """_etapa_ocr importaba `procesar_imagen`/`procesar_pdf` de core.ocr_engine,
    funciones que nunca existieron ahí — ImportError en cuanto se corría
    `cli.py --etapas ocr` (reproducido en auditoría de sesión). Este test usa
    un PDF real (sin mocks) para que un futuro refactor de ocr_engine.py que
    rompa el contrato que _etapa_ocr espera falle aquí, no en producción."""
    import fitz

    pdf_path = tmp_path / "numero_test.pdf"
    doc = fitz.open()
    pagina = doc.new_page()
    # Suficientes palabras para superar PALABRAS_MIN_PAGINA (40) en
    # core.ocr_engine.analizar_pdf y tomar la ruta de texto embebido
    # (reconstruir_texto_pagina), sin depender de tesseract instalado.
    for i in range(6):
        pagina.insert_text((72, 72 + i * 14), "Texto de prueba con palabras suficientes " * 3)
    doc.save(str(pdf_path))
    doc.close()

    out_dir = tmp_path / "salida"
    cfg = {
        "out_dir": str(out_dir),
        "input_tipo": "pdf",
        "archivos_sel": [str(pdf_path)],
    }

    resultados = _etapa_ocr(cfg, verbose=False)

    assert resultados.get("numero_test") == 1
    txt = out_dir / "03_ocr" / "numero_test" / "p0001.txt"
    assert txt.exists()
    assert "prueba" in txt.read_text(encoding="utf-8")


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


def test_etapa_ner_usa_roberta_por_defecto():
    """Sesión 62 forzó usar_roberta=False creyendo que el segfault de NER era
    un conflicto de threading torch/tokenizers bajo recursos.aplicar_limites_cpu().
    Sesión 63 diagnosticó la causa real (ver tests/test_ner_engine.py::
    TestOfflineForzadoAntesDeImportarTransformers y core/ner_roberta_local.py):
    era un bug de orden de imports en el forzado de HF_HUB_OFFLINE, no
    threading. Confirmado sin segfault sobre el corpus real completo de
    Estampa (792 páginas) tras el fix — _etapa_ner vuelve a usar el default
    real de pipeline_ner (usar_roberta=True)."""
    articulos = [{"id": "a1", "texto": "Texto de prueba con alguna entidad."}]

    with patch("spacy.load", return_value=MagicMock()), \
         patch("core.ner_engine.pipeline_ner") as mock_pipeline_ner, \
         patch("core.ner_engine.actualizar_indice_global"), \
         patch("core.ner_engine.indice_global_vacio", return_value={}):
        mock_pipeline_ner.return_value = {}
        _etapa_ner(articulos, verbose=False)

    assert mock_pipeline_ner.called
    _, kwargs = mock_pipeline_ner.call_args
    assert kwargs.get("usar_roberta") is not False
