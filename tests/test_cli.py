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
    # ≥100 palabras: desde la sesión 72 la CLI filtra como el escritorio.
    articulos = [{"id": "a1", "texto": "Texto de prueba con alguna entidad. " * 20}]

    with patch("spacy.load", return_value=MagicMock()), \
         patch("core.ner_engine.pipeline_ner") as mock_pipeline_ner, \
         patch("core.ner_engine.actualizar_indice_global"), \
         patch("core.ner_engine.indice_global_vacio", return_value={}):
        mock_pipeline_ner.return_value = {}
        _etapa_ner(articulos, verbose=False)

    assert mock_pipeline_ner.called
    _, kwargs = mock_pipeline_ner.call_args
    assert kwargs.get("usar_roberta") is not False


def test_etapa_ocr_documento_mixto_no_deja_paginas_vacias(tmp_path: Path):
    """El caso de *El Día*: el PDF declara la capa oculta de Paper Capture y
    solo algunas páginas la tienen de verdad. Con la decisión tomada a nivel de
    documento, las páginas sin texto se escribían vacías y el CLI reportaba
    éxito. Ahora cada página sin texto embebido tiene que ir a Tesseract.

    Tesseract se sustituye por un doble: lo que se comprueba es el ENRUTADO,
    no el reconocimiento (que ya tiene sus propios tests)."""
    import fitz

    pdf_path = tmp_path / "el_dia_mixto.pdf"
    doc = fitz.open()
    for i in range(4):
        pagina = doc.new_page()
        if i >= 2:      # solo las dos últimas traen texto, como el ejemplar real
            for k in range(6):
                pagina.insert_text(
                    (72, 72 + k * 14),
                    "Texto embebido con palabras suficientes " * 3,
                )
    doc.save(str(pdf_path))
    doc.close()

    out_dir = tmp_path / "salida"
    cfg = {"out_dir": str(out_dir), "input_tipo": "pdf",
           "archivos_sel": [str(pdf_path)]}

    imgs = []
    for i in range(1, 5):
        img = tmp_path / f"pag{i}.png"
        img.write_bytes(b"")
        imgs.append(img)

    with patch("core.ocr_engine.pdf_a_imagenes", return_value=imgs) as m_img, \
         patch("core.ocr_engine.ocr_pagina",
               return_value=("Texto reconocido por Tesseract en la pagina", 88.0)) as m_ocr:
        _etapa_ocr(cfg, verbose=False)

    txt_dir = out_dir / "03_ocr" / "el_dia_mixto"
    escritos = sorted(p.name for p in txt_dir.glob("p*.txt"))
    assert escritos == ["p0001.txt", "p0002.txt", "p0003.txt", "p0004.txt"]

    # Las dos primeras NO pueden quedar vacías: tuvieron que pasar por OCR.
    for nombre in ("p0001.txt", "p0002.txt"):
        contenido = (txt_dir / nombre).read_text(encoding="utf-8").strip()
        assert contenido, f"{nombre} quedó vacía: la página se dio por perdida"
        assert "Tesseract" in contenido

    # Las dos últimas vienen del texto embebido, sin pasar por Tesseract.
    assert "embebido" in (txt_dir / "p0003.txt").read_text(encoding="utf-8")

    assert m_img.called, "no se rasterizó nada pese a haber páginas sin texto"
    assert m_ocr.call_count == 2, "se OCR-izaron páginas que ya traían texto"


def test_etapa_ocr_reporta_documento_no_utilizable(tmp_path: Path, capsys):
    """Un documento con un tercio de sus tokens partidos tiene que decirlo,
    no entrar al pipeline como si fuera texto limpio."""
    import fitz

    # 40 % de tokens de una sola letra: por encima del umbral crítico.
    basura = " ".join(["palabra"] * 6 + ["x"] * 4) + " "
    pdf_path = tmp_path / "fragmentado.pdf"
    doc = fitz.open()
    pagina = doc.new_page()
    for k in range(40):
        pagina.insert_text((40, 40 + k * 16), basura * 3, fontsize=8)
    doc.save(str(pdf_path))
    doc.close()

    out_dir = tmp_path / "salida"
    _etapa_ocr({"out_dir": str(out_dir), "input_tipo": "pdf",
                "archivos_sel": [str(pdf_path)]}, verbose=True)

    salida = capsys.readouterr().out
    assert "no utilizable" in salida.lower()
    assert "fragmentado" in salida
