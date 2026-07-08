"""core/pdf_export.py — Exporta un PDF buscable (texto invisible sobre la
imagen), estilo «Copia exacta» de ABBYY FineReader. Usa PyMuPDF (fitz),
ya dependencia del proyecto (app.py la importa en varios puntos).

Decisión de consistencia: cuando el texto viene NORMALIZADO/corregido (no
del OCR crudo), los bboxes de Tesseract ya no corresponden palabra por
palabra al texto real — resaltar la palabra equivocada al buscar sería
peor que no resaltar nada. Por eso el texto normalizado se inserta como
UNA sola caja invisible por página completa; el posicionamiento por
palabra (`palabras`) solo tiene sentido si se exporta el OCR crudo, cuyos
bboxes sí siguen siendo válidos.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Callable


def exportar_pdf_buscable(
    paginas: list[dict],
    out_pdf,
    max_lado_px: int = 2500,
    jpeg_q: int = 75,
    callback: Callable[[int, int], None] | None = None,
) -> Path:
    """Genera `out_pdf`: una página por cada entrada de `paginas`, con la
    imagen (recomprimida a JPEG, lado máximo `max_lado_px`) y una capa de
    texto invisible buscable/copiable encima.

    Cada entrada de `paginas`: {"img_path": Path|str, "texto": str,
    "palabras": list[dict] | None}. Si "palabras" trae una lista de
    {"texto","x0","y0","x1","y1"} (en píxeles de la imagen YA recomprimida
    a max_lado_px), el texto se posiciona por palabra; si es None o falta,
    se usa una caja única cubriendo la página completa con "texto".

    Páginas sin imagen legible se omiten (no detienen el lote); se cuentan
    en el valor de retorno vía callback pero no aparecen en el PDF final.
    """
    import fitz
    from PIL import Image

    out_pdf = Path(out_pdf)
    doc = fitz.open()
    total = len(paginas)

    for i, item in enumerate(paginas):
        img_path = Path(item["img_path"])
        texto = (item.get("texto") or "").strip()
        palabras = item.get("palabras")

        try:
            with Image.open(img_path) as im:
                im = im.convert("RGB")
                escala = 1.0
                if max(im.size) > max_lado_px:
                    escala = max_lado_px / max(im.size)
                    nuevo = (max(1, int(im.width * escala)), max(1, int(im.height * escala)))
                    im = im.resize(nuevo, Image.LANCZOS)
                ancho_px, alto_px = im.size
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=jpeg_q)
                img_bytes = buf.getvalue()
        except Exception:
            if callback:
                callback(i + 1, total)
            continue

        page = doc.new_page(width=ancho_px, height=alto_px)
        page.insert_image(fitz.Rect(0, 0, ancho_px, alto_px), stream=img_bytes)

        if palabras:
            for p in palabras:
                rect = fitz.Rect(p["x0"], p["y0"], p["x1"], p["y1"])
                if rect.is_empty or not p.get("texto"):
                    continue
                page.insert_textbox(rect, p["texto"], fontsize=8, render_mode=3)
        elif texto:
            rect = fitz.Rect(0, 0, ancho_px, alto_px)
            page.insert_textbox(rect, texto, fontsize=8, render_mode=3)

        if callback:
            callback(i + 1, total)

    if doc.page_count == 0:
        doc.close()
        raise ValueError("Ninguna página tenía una imagen legible; no se generó PDF.")

    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_pdf))
    doc.close()
    return out_pdf
