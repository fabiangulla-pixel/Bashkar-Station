"""core/word_verifier.py — Verificador OCR palabra-por-palabra (estilo ABBYY
FineReader): recorre las palabras de baja confianza de una página, ofrece
el recorte ampliado + sugerencias, y aplica la corrección elegida al texto.

Función pura, sin tkinter. Recalcula sobre la marcha por página (no se
persiste nada aparte del texto corregido): `ocr_engine.ocr_pagina()` ya
calcula `image_to_data` para la confianza promedio y descarta el detalle
por palabra — aquí se recupera ese detalle bajo demanda.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image


@dataclass
class PalabraDudosa:
    texto: str
    conf: float
    x0: int
    y0: int
    x1: int
    y1: int
    idx_ocurrencia: int   # n-ésima aparición de `texto` en la página (0-based)
    contexto: str         # ±5 palabras alrededor, para mostrar en el diálogo


def extraer_palabras_dudosas(
    img: "Image.Image",
    lang: str = "spa",
    umbral_conf: float = 75.0,
) -> list[PalabraDudosa]:
    """Corre Tesseract sobre `img` (ya en memoria, una sola lectura de disco
    por página) y devuelve las palabras con confianza < `umbral_conf`.

    Tesseract marca "no es una palabra" (espacios, bloques vacíos) con
    conf == -1; esas se descartan siempre, sean o no el umbral.
    """
    import pytesseract

    from core.layout_tesseract import _asegurar_tessdata
    from core.ocr_engine import _get_tesseract_cmd
    pytesseract.pytesseract.tesseract_cmd = _get_tesseract_cmd()
    _asegurar_tessdata()

    config = f"--oem 3 --psm 3 -l {lang}"
    data = pytesseract.image_to_data(img, config=config, output_type=pytesseract.Output.DICT)

    palabras = [t.strip() for t in data["text"]]
    n = len(palabras)
    contador_ocurrencia: dict[str, int] = {}
    resultado: list[PalabraDudosa] = []

    for i in range(n):
        texto = palabras[i]
        conf = float(data["conf"][i])
        if not texto or conf < 0:
            continue
        idx_oc = contador_ocurrencia.get(texto, 0)
        contador_ocurrencia[texto] = idx_oc + 1
        if conf >= umbral_conf:
            continue
        ctx_ini = max(0, i - 5)
        ctx_fin = min(n, i + 6)
        contexto = " ".join(p for p in palabras[ctx_ini:ctx_fin] if p)
        resultado.append(PalabraDudosa(
            texto=texto, conf=conf,
            x0=int(data["left"][i]), y0=int(data["top"][i]),
            x1=int(data["left"][i]) + int(data["width"][i]),
            y1=int(data["top"][i]) + int(data["height"][i]),
            idx_ocurrencia=idx_oc, contexto=contexto,
        ))
    return resultado


def recortar_palabra(
    img: "Image.Image",
    p: PalabraDudosa,
    margen: int = 8,
    zoom: float = 2.0,
) -> "Image.Image":
    """Recorte ampliado de la palabra (estilo verificación de FineReader),
    con margen alrededor y zoom aplicado."""
    from PIL import Image

    ancho, alto = img.size
    x0 = max(0, p.x0 - margen)
    y0 = max(0, p.y0 - margen)
    x1 = min(ancho, p.x1 + margen)
    y1 = min(alto, p.y1 + margen)
    recorte = img.crop((x0, y0, x1, y1))
    if zoom != 1.0:
        nuevo_size = (max(1, int(recorte.width * zoom)), max(1, int(recorte.height * zoom)))
        recorte = recorte.resize(nuevo_size, Image.LANCZOS)
    return recorte


def sugerencias_para(palabra: str, corrector, dicc_corpus: dict[str, int] | None = None) -> list[str]:
    """Combina la sugerencia de `SpellCorrector` (Hunspell, distancia≤2) con
    las palabras más frecuentes del propio corpus (útil para nombres propios
    y vocabulario de época que Hunspell no conoce). Sin duplicados, sin la
    palabra original."""
    original_lower = palabra.lower()
    sugerencias: list[str] = []

    sug_dic = corrector._sugerir_correccion(palabra) if corrector is not None else None
    if sug_dic and sug_dic.lower() != original_lower:
        sugerencias.append(sug_dic)

    if dicc_corpus:
        from core.spell_corrector import _distancia_edicion
        candidatas = sorted(
            (w for w in dicc_corpus if w != original_lower
             and _distancia_edicion(original_lower, w) <= 2),
            key=lambda w: (-dicc_corpus[w], w),
        )
        for c in candidatas[:5]:
            if c not in (s.lower() for s in sugerencias):
                sugerencias.append(c)

    return sugerencias


def aplicar_reemplazo(
    texto: str,
    original: str,
    reemplazo: str,
    idx_ocurrencia: int,
) -> tuple[str, bool]:
    """Reemplaza la n-ésima ocurrencia (0-based) de `original` como palabra
    completa (\\b) en `texto`. Si el texto normalizado ya divergió del OCR
    crudo y esa ocurrencia no existe, devuelve (texto, False) sin adivinar
    una posición — la GUI debe avisar "no localizada"."""
    import re

    patron = re.compile(r"\b" + re.escape(original) + r"\b")
    contador = 0
    for m in patron.finditer(texto):
        if contador == idx_ocurrencia:
            nuevo = texto[:m.start()] + reemplazo + texto[m.end():]
            return nuevo, True
        contador += 1
    return texto, False


def reemplazar_todas(texto: str, original: str, reemplazo: str) -> tuple[str, int]:
    """Reemplaza TODAS las ocurrencias de `original` como palabra completa.
    Devuelve (texto_nuevo, n_reemplazos)."""
    import re

    patron = re.compile(r"\b" + re.escape(original) + r"\b")
    nuevo, n = patron.subn(reemplazo, texto)
    return nuevo, n
