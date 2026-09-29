"""core/servicios_corpus.py — Operaciones sobre la carpeta de trabajo del corpus.

Extraídas de ``app.py`` (sesión 70). Allí eran métodos de ``BashkarApp`` que
no usaban ``self`` sino el estado global ``ST``: imposibles de probar sin
levantar la GUI. Aquí reciben lo que necesitan como argumentos y devuelven
datos; ``app.py`` conserva métodos delgados que les pasan ``ST``.

Estructura de la carpeta de trabajo (``out_dir``)::

    02_imagenes/<numero>/*.png
    03_ocr/<numero>/*.txt
    04_analisis/ocr_metadatos.csv
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

# Estimación cuando todavía no hay imágenes: 1 página ≈ 150 KB de PDF.
BYTES_POR_PAGINA_PDF = 150_000
PAGINAS_SI_NO_SE_PUEDE_LEER = 100


def contar_paginas_pendientes(out_dir, archivos_pdf) -> int:
    """Páginas que aún no tienen .txt de OCR en ``03_ocr``.

    Si un PDF todavía no se rasterizó, se estima por su tamaño.
    """
    if not out_dir or not archivos_pdf:
        return 0
    out_dir = Path(out_dir)
    total = 0
    for pdf in archivos_pdf:
        pdf = Path(pdf)
        img_dir = out_dir / "02_imagenes" / pdf.stem
        ocr_dir = out_dir / "03_ocr" / pdf.stem
        if img_dir.exists():
            imgs = list(img_dir.glob("*.png"))
            if ocr_dir.exists():
                hechas = {p.stem for p in ocr_dir.glob("*.txt")}
                total += sum(1 for i in imgs if i.stem not in hechas)
            else:
                total += len(imgs)
        else:
            try:
                total += max(1, pdf.stat().st_size // BYTES_POR_PAGINA_PDF)
            except OSError:
                total += PAGINAS_SI_NO_SE_PUEDE_LEER
    return total


def filas_meta_desde_txt(out_dir) -> list[dict]:
    """Una fila de metadatos por cada .txt de ``03_ocr/<numero>/``."""
    if not out_dir:
        return []
    base = Path(out_dir) / "03_ocr"
    if not base.exists():
        return []
    filas = []
    for num_dir in sorted(base.iterdir()):
        if not num_dir.is_dir():
            continue
        for txt in sorted(num_dir.glob("*.txt")):
            try:
                palabras = len(txt.read_text(encoding="utf-8", errors="replace").split())
            except OSError:
                palabras = 0
            filas.append({
                "numero": num_dir.name,
                "pagina": txt.stem,
                "txt_path": str(txt),
                "palabras": palabras,
                "confianza": None,
                "revision": False,
                "metodo": "conversor",
            })
    return filas


def reconstruir_meta_corpus(out_dir):
    """DataFrame de metadatos desde los .txt y su CSV en ``04_analisis``.

    Devuelve None si no hay ningún .txt.
    """
    import pandas as pd
    filas = filas_meta_desde_txt(out_dir)
    if not filas:
        return None
    df = pd.DataFrame(filas)
    df["palabras"] = pd.to_numeric(df["palabras"], errors="coerce").fillna(0).astype(int)
    ad = Path(out_dir) / "04_analisis"
    ad.mkdir(exist_ok=True)
    df.to_csv(ad / "ocr_metadatos.csv", index=False)
    return df


def agrupar_por_numero(articulos=None, corpus_txt=None) -> dict[str, list[str]]:
    """Textos agrupados por número de revista.

    Con artículos segmentados agrupa por ``numero`` (omite los vacíos). Sin
    ellos, cae al corpus por página con claves ``pag_0000``.
    """
    por_num: dict[str, list[str]] = defaultdict(list)
    if articulos:
        for art in articulos:
            txt = art.get("texto", "") or ""
            if txt.strip():
                por_num[str(art.get("numero", "sin_número"))].append(txt)
    elif corpus_txt:
        for i, txt in enumerate(corpus_txt):
            por_num[f"pag_{i:04d}"].append(txt or "")
    return dict(por_num)
