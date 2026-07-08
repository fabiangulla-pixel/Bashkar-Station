"""core/page_quality.py — Avisos de calidad por página, estilo ABBYY
FineReader: resolución insuficiente, página en blanco, confianza OCR baja.

Umbrales de página vacía tomados de la configuración real de FineReader 16
(fineUI.CommonSettings.xml → emptyPageDetectionOptions): maxAlphabetLetters=2,
maxTextObjects=20. Función pura, sin tkinter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image

DPI_MINIMO_RECOMENDADO = 300
ALTO_PX_MINIMO_SIN_DPI = 2400  # heurística: página de periódico completa a <2400px ≈ baja resolución


@dataclass
class Aviso:
    codigo: str        # "dpi_bajo" | "pagina_vacia" | "conf_baja"
    severidad: str      # "info" | "warn"
    mensaje: str
    pagina: str
    img_path: Path


def dpi_de_imagen(img_path) -> int | None:
    """DPI horizontal declarado en los metadatos de la imagen, o None si no
    trae metadato (frecuente en microfilm BNC)."""
    from PIL import Image
    try:
        with Image.open(img_path) as im:
            dpi = im.info.get("dpi")
            return int(round(dpi[0])) if dpi else None
    except Exception:
        return None


def es_pagina_vacia(
    texto: str,
    n_tokens: int | None = None,
    max_letras: int = 2,
    max_tokens: int = 20,
) -> bool:
    """Umbrales exactos de FineReader: página vacía si tiene ≤2 letras del
    alfabeto Y (cuando se conoce) ≤20 objetos de texto detectados."""
    n_letras = len(re.findall(r"[a-záéíóúüñA-ZÁÉÍÓÚÜÑ]", texto or ""))
    if n_letras > max_letras:
        return False
    if n_tokens is not None and n_tokens > max_tokens:
        return False
    return True


def evaluar_pagina(
    img_path,
    texto_ocr: str,
    conf: float | None,
    img_size: tuple[int, int] | None = None,
    dpi: int | None = None,
    n_tokens: int | None = None,
) -> list[Aviso]:
    """Avisos para UNA página. Acepta `img_size`/`dpi` ya conocidos (el
    worker de OCR suele tener la imagen abierta) para no releerla desde
    disco/Google Drive; solo la abre si ninguno de los dos se pasa."""
    img_path = Path(img_path)
    pagina = img_path.stem
    avisos: list[Aviso] = []

    if dpi is None and img_size is None:
        dpi = dpi_de_imagen(img_path)
        if dpi is None:
            from PIL import Image
            try:
                with Image.open(img_path) as im:
                    img_size = im.size
            except Exception:
                img_size = None

    if dpi is not None:
        if dpi < DPI_MINIMO_RECOMENDADO:
            avisos.append(Aviso(
                "dpi_bajo", "warn",
                f"Resolución baja: {dpi} DPI (recomendado ≥{DPI_MINIMO_RECOMENDADO})",
                pagina, img_path,
            ))
    elif img_size is not None and img_size[1] < ALTO_PX_MINIMO_SIN_DPI:
        avisos.append(Aviso(
            "dpi_bajo", "warn",
            f"Resolución baja (estimada por tamaño: {img_size[1]}px de alto, "
            "la imagen no trae metadato DPI)",
            pagina, img_path,
        ))

    if es_pagina_vacia(texto_ocr, n_tokens):
        avisos.append(Aviso(
            "pagina_vacia", "info", "Página posiblemente en blanco o sin texto útil",
            pagina, img_path,
        ))

    if conf is not None and conf < 30:
        avisos.append(Aviso(
            "conf_baja", "warn", f"Confianza OCR muy baja: {conf:.0f}%",
            pagina, img_path,
        ))

    return avisos


def generar_miniatura(img_path, cache_dir, alto: int = 140) -> Path:
    """Miniatura JPEG en caché LOCAL (core.local_cache), nunca en la unidad
    del proyecto. Reutiliza el archivo si ya existe para esta versión exacta
    de la imagen (clave_cache incluye mtime+tamaño)."""
    from PIL import Image

    from core.local_cache import clave_cache
    img_path = Path(img_path)
    destino = Path(cache_dir) / f"{clave_cache(img_path)}.jpg"
    if destino.exists():
        return destino
    with Image.open(img_path) as im:
        im = im.convert("RGB")
        ratio = alto / max(im.height, 1)
        ancho = max(1, int(im.width * ratio))
        miniatura = im.resize((ancho, alto), Image.LANCZOS)
        miniatura.save(destino, "JPEG", quality=70)
    return destino
