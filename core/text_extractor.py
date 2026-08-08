"""
core/text_extractor.py
──────────────────────
Extractor inteligente de texto:
  · PDFs digitales  → texto directo con PyMuPDF  (segundos, sin OCR)
  · PDFs escaneados → pdf2image + Tesseract OCR   (lento, para imágenes)
  · Carpetas de imágenes → Tesseract directo      (sin conversión)

Uso:
    from core.text_extractor import detectar_modo, extraer_archivo
"""

from __future__ import annotations

import gc
from pathlib import Path

# ── Umbral para considerar un PDF "digital" ───────────────────────────────────
# Si el promedio de caracteres por página supera esto, el PDF ya tiene texto.
UMBRAL_CHARS_PAGINA = 80
# Páginas a muestrear para la detección (para no abrir todo el PDF)
PAGINAS_MUESTRA = 5
# Ratio de caracteres "limpios" (letras y espacios) sobre total.
# Un PDF escaneado con capa OCR embebida tiene texto pero de baja calidad.
# Si menos del 50% de los chars son alfanuméricos/espacios → OCR de baja calidad.
UMBRAL_RATIO_LIMPIO = 0.50


# ─────────────────────────────────────────────────────────────────────────────
# DETECCIÓN DE MODO
# ─────────────────────────────────────────────────────────────────────────────

def detectar_modo(path: Path) -> str:
    """
    Devuelve:
      'digital'   → PDF con texto seleccionable, extracción directa
      'escaneado' → PDF sin texto (imágenes), necesita OCR
      'imagen'    → archivo de imagen (PNG/JPG/TIFF/BMP)
    """
    ext = path.suffix.lower()
    if ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"):
        return "imagen"
    if ext != ".pdf":
        return "desconocido"

    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(path))
        n   = min(PAGINAS_MUESTRA, doc.page_count)
        if n == 0:
            doc.close()
            return "escaneado"

        textos = [doc[i].get_text() for i in range(n)]
        doc.close()

        total_chars = sum(len(t.strip()) for t in textos)
        promedio = total_chars / n
        if promedio < UMBRAL_CHARS_PAGINA:
            return "escaneado"

        # Verificar calidad del texto: PDFs con capa OCR embebida tienen
        # mucho ruido (coords, basura) con bajo ratio de texto limpio
        texto_muestra = ' '.join(textos)
        chars_limpios = sum(1 for c in texto_muestra if c.isalnum() or c == ' ')
        ratio_limpio = chars_limpios / max(len(texto_muestra), 1)
        if ratio_limpio < UMBRAL_RATIO_LIMPIO:
            return "escaneado_con_ocr"   # tiene texto pero de baja calidad

        # Verificar si es Paper Capture (Acrobat OCR embebido)
        try:
            from core.alto_reconstructor import es_pdf_paper_capture
            if es_pdf_paper_capture(path):
                return "paper_capture"
        except ImportError:
            pass

        return "digital"

    except Exception:
        # Si PyMuPDF falla, asumir escaneado (usa OCR como fallback)
        return "escaneado"


# ─────────────────────────────────────────────────────────────────────────────
# EXTRACCIÓN DIRECTA  (PDFs digitales → PyMuPDF, sin OCR)
# ─────────────────────────────────────────────────────────────────────────────
# EXTRACCIÓN PAPER CAPTURE  (PDFs Acrobat OCR → reconstrucción posicional)
# ─────────────────────────────────────────────────────────────────────────────

def extraer_pdf_paper_capture(
    pdf_path: Path,
    txt_dir: Path,
    callback_pagina=None,
) -> list[dict]:
    """
    Extrae texto de PDFs creados con Adobe Acrobat Paper Capture.
    Usa alto_reconstructor para reconstruir orden de lectura desde coordenadas.
    Devuelve lista de dicts con las mismas claves que extraer_pdf_digital.
    """
    from core.alto_reconstructor import reconstruir_pdf_completo
    from core.ocr_normalizer import normalizar_texto_ocr

    txt_dir.mkdir(parents=True, exist_ok=True)

    def _cb(i, n):
        if callback_pagina:
            callback_pagina(i - 1, n)

    paginas = reconstruir_pdf_completo(pdf_path, callback=_cb)
    rows = []

    for pag in paginas:
        txt_path = txt_dir / f"{pag['pagina']}.txt"
        if txt_path.exists():
            texto = txt_path.read_text("utf-8", errors="replace")
        else:
            texto = normalizar_texto_ocr(pag["texto"])
            txt_path.write_text(texto, encoding="utf-8")

        rows.append({
            "pagina":    pag["pagina"],
            "txt_path":  str(txt_path),
            "palabras":  len(texto.split()),
            "confianza": None,
            "revision":  False,
            "n_columnas": pag.get("n_columnas", 1),
            "tiene_titulo": pag.get("tiene_titulo", False),
            # Preservar líneas con metadatos tipográficos para segmentación
            "_lineas":   pag.get("lineas", []),
        })

    return rows


# ─────────────────────────────────────────────────────────────────────────────

def extraer_pdf_digital(
    pdf_path: Path,
    txt_dir: Path,
    callback_pagina=None,
) -> list[dict]:
    """
    Extrae texto página a página de un PDF digital con PyMuPDF.
    Devuelve lista de dicts con claves: pagina, txt_path, palabras, confianza.
    callback_pagina(pag_idx, total_pags) se llama después de cada página.
    """
    import fitz

    txt_dir.mkdir(parents=True, exist_ok=True)
    doc  = fitz.open(str(pdf_path))
    rows = []

    from core.ocr_normalizer import normalizar_texto_ocr
    for i in range(doc.page_count):
        txt_path = txt_dir / f"p{i+1:04d}.txt"
        if txt_path.exists():
            texto = txt_path.read_text("utf-8", errors="replace")
            # Re-normalizar siempre: puede venir de OCR externo sin normalizar
            texto_norm = normalizar_texto_ocr(texto)
            if texto_norm != texto:
                txt_path.write_text(texto_norm, encoding="utf-8")
            texto = texto_norm
        else:
            texto = doc[i].get_text()
            texto = normalizar_texto_ocr(texto)
            txt_path.write_text(texto, encoding="utf-8")

        rows.append({
            "pagina":    f"p{i+1:04d}",
            "txt_path":  str(txt_path),
            "palabras":  len(texto.split()),
            "confianza": None,    # extracción directa, sin score OCR
            "revision":  False,
        })
        if callback_pagina:
            callback_pagina(i, doc.page_count)

    doc.close()
    gc.collect()
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# EXTRACCIÓN POR OCR  (PDFs escaneados o imágenes)
# ─────────────────────────────────────────────────────────────────────────────

def _get_poppler_path() -> str | None:
    """Carpeta bin de poppler para pdf2image, o None si basta con el PATH.

    Delega en core.ocr_engine en vez de repetir la búsqueda: eran dos copias
    con el mismo propósito y órdenes de prioridad distintos, y ese tipo de
    divergencia es la que hace que el OCR funcione en una pestaña y no en otra.
    """
    from core.ocr_engine import _get_poppler_path as _buscar
    return _buscar()


def extraer_pdf_ocr(
    pdf_path: Path,
    img_dir:  Path,
    txt_dir:  Path,
    dpi:      int  = 150,
    lang:     str  = "spa",
    callback_pagina=None,
) -> list[dict]:
    """
    Convierte PDF a imágenes y aplica Tesseract OCR.
    Devuelve lista de dicts igual que extraer_pdf_digital.
    """
    from core.ocr_engine import ocr_pagina, pdf_a_imagenes

    img_dir.mkdir(parents=True, exist_ok=True)
    txt_dir.mkdir(parents=True, exist_ok=True)

    img_paths = pdf_a_imagenes(pdf_path, img_dir, dpi)
    rows      = []

    from core.ocr_normalizer import normalizar_texto_ocr
    for i, img_path in enumerate(img_paths):
        txt_path = txt_dir / (img_path.stem + ".txt")
        if txt_path.exists():
            texto = txt_path.read_text("utf-8", errors="replace")
            texto_norm = normalizar_texto_ocr(texto)
            if texto_norm != texto:
                txt_path.write_text(texto_norm, encoding="utf-8")
            texto = texto_norm
            conf  = None
        else:
            texto, conf = ocr_pagina(img_path, lang=lang)
            txt_path.write_text(texto, encoding="utf-8")

        rows.append({
            "pagina":    img_path.stem,
            "txt_path":  str(txt_path),
            "palabras":  len(texto.split()),
            "confianza": conf,
            "revision":  bool(conf is not None and conf < 60),
        })
        if callback_pagina:
            callback_pagina(i, len(img_paths))

    gc.collect()
    return rows


def extraer_imagenes_ocr(
    img_paths: list[Path],
    txt_dir:   Path,
    lang:      str = "spa",
    callback_pagina=None,
) -> list[dict]:
    """
    OCR directo sobre una lista de imágenes (sin conversión PDF).
    """
    from core.ocr_engine import ocr_pagina

    txt_dir.mkdir(parents=True, exist_ok=True)
    rows = []

    for i, img_path in enumerate(sorted(img_paths)):
        txt_path = txt_dir / (img_path.stem + ".txt")
        if txt_path.exists():
            texto = txt_path.read_text("utf-8", errors="replace")
            conf  = None
        else:
            texto, conf = ocr_pagina(img_path, lang=lang)
            txt_path.write_text(texto, encoding="utf-8")

        rows.append({
            "pagina":    img_path.stem,
            "txt_path":  str(txt_path),
            "palabras":  len(texto.split()),
            "confianza": conf,
            "revision":  bool(conf is not None and conf < 60),
        })
        if callback_pagina:
            callback_pagina(i, len(img_paths))

    gc.collect()
    return rows
