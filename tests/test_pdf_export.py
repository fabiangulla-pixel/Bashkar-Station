"""tests/test_pdf_export.py — PDF buscable estilo «Copia exacta» de FineReader."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.pdf_export import exportar_pdf_buscable  # noqa: E402


def _png(path: Path, size=(300, 200), color=(255, 255, 255)):
    from PIL import Image
    Image.new("RGB", size, color).save(path)


def test_exporta_una_pagina_con_texto_completo(tmp_path):
    img = tmp_path / "p0001.png"
    _png(img)
    out = tmp_path / "salida.pdf"

    exportar_pdf_buscable(
        [{"img_path": img, "texto": "Bogotá capital de Colombia"}], out)

    import fitz
    doc = fitz.open(str(out))
    assert doc.page_count == 1
    assert "Bogotá" in doc[0].get_text()
    doc.close()


def test_exporta_varias_paginas_en_orden(tmp_path):
    imgs = []
    for i in range(3):
        p = tmp_path / f"p{i:04d}.png"
        _png(p)
        imgs.append({"img_path": p, "texto": f"texto de la pagina {i}"})
    out = tmp_path / "lote.pdf"

    exportar_pdf_buscable(imgs, out)

    import fitz
    doc = fitz.open(str(out))
    assert doc.page_count == 3
    for i in range(3):
        assert f"pagina {i}" in doc[i].get_text()
    doc.close()


def test_progreso_via_callback(tmp_path):
    imgs = []
    for i in range(2):
        p = tmp_path / f"p{i:04d}.png"
        _png(p)
        imgs.append({"img_path": p, "texto": "x"})
    out = tmp_path / "cb.pdf"

    llamadas = []
    exportar_pdf_buscable(imgs, out, callback=lambda n, total: llamadas.append((n, total)))
    assert llamadas == [(1, 2), (2, 2)]


def test_texto_por_palabra_cuando_se_pasan_bboxes(tmp_path):
    img = tmp_path / "p0001.png"
    _png(img, size=(400, 100))
    out = tmp_path / "palabra.pdf"

    exportar_pdf_buscable([{
        "img_path": img, "texto": "",
        "palabras": [{"texto": "Bogota", "x0": 10, "y0": 10, "x1": 100, "y1": 30}],
    }], out)

    import fitz
    doc = fitz.open(str(out))
    assert "Bogota" in doc[0].get_text()
    doc.close()


def test_pagina_sin_imagen_legible_se_omite_no_detiene_lote(tmp_path):
    bueno = tmp_path / "p0001.png"
    _png(bueno)
    malo = tmp_path / "no_existe.png"
    out = tmp_path / "parcial.pdf"

    exportar_pdf_buscable(
        [{"img_path": malo, "texto": "no debería aparecer"},
         {"img_path": bueno, "texto": "esta si aparece"}], out)

    import fitz
    doc = fitz.open(str(out))
    assert doc.page_count == 1  # solo la buena
    assert "esta si aparece" in doc[0].get_text()
    doc.close()


def test_todas_las_paginas_invalidas_lanza(tmp_path):
    import pytest
    out = tmp_path / "vacio.pdf"
    with pytest.raises(ValueError):
        exportar_pdf_buscable([{"img_path": tmp_path / "no_existe.png", "texto": "x"}], out)


def test_recomprime_a_max_lado_px(tmp_path):
    img = tmp_path / "grande.png"
    _png(img, size=(4000, 3000))
    out = tmp_path / "recomprimido.pdf"

    exportar_pdf_buscable([{"img_path": img, "texto": "x"}], out, max_lado_px=1000)

    import fitz
    doc = fitz.open(str(out))
    assert max(doc[0].rect.width, doc[0].rect.height) <= 1000
    doc.close()


def test_crea_carpeta_destino_si_no_existe(tmp_path):
    img = tmp_path / "p0001.png"
    _png(img)
    out = tmp_path / "subcarpeta" / "nueva" / "salida.pdf"

    exportar_pdf_buscable([{"img_path": img, "texto": "x"}], out)
    assert out.exists()
