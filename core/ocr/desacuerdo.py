"""core/ocr/desacuerdo.py — Cuánto discrepan dos lecturas de la misma página.

Cuando dos motores leen la misma página y no coinciden, Bashkar no elige en
silencio cuál tiene razón: mide la discrepancia y, si supera el umbral, marca
la página (o el bloque) para revisión humana con las dos lecturas a la vista.

La discrepancia NO es un CER: sin referencia humana no se sabe cuál de los dos
acierta. Solo dice "aquí hay duda".
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass

from core.ocr.interfaces import Bloque, ResultadoOCR

_ESPACIOS = re.compile(r"\s+")


def _normalizar(texto: str) -> str:
    """Comparar contenido, no maquetación: espacios y saltos de línea no cuentan."""
    t = unicodedata.normalize("NFC", texto or "")
    return _ESPACIOS.sub(" ", t).strip()


def discrepancia_caracteres(a: str, b: str) -> float:
    """0 = idénticos, 1 = nada en común (1 − ratio de difflib, a nivel carácter)."""
    a, b = _normalizar(a), _normalizar(b)
    if not a and not b:
        return 0.0
    return 1.0 - difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def discrepancia_palabras(a: str, b: str) -> float:
    a, b = _normalizar(a).split(), _normalizar(b).split()
    if not a and not b:
        return 0.0
    return 1.0 - difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def palabras_en_disputa(a: str, b: str, maximo: int = 30) -> list[tuple[str, str]]:
    """Pares (lectura A, lectura B) donde los motores difieren, para mostrar."""
    pa, pb = _normalizar(a).split(), _normalizar(b).split()
    salida = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, pa, pb, autojunk=False).get_opcodes():
        if op != "equal":
            salida.append((" ".join(pa[i1:i2]), " ".join(pb[j1:j2])))
            if len(salida) >= maximo:
                break
    return salida


def _iou(a, b) -> float:
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    area = lambda r: max(0, r[2] - r[0]) * max(0, r[3] - r[1])  # noqa: E731
    return inter / float(area(a) + area(b) - inter)


@dataclass
class Comparacion:
    caracteres: float
    palabras: float
    disputas: list[tuple[str, str]]
    bloques_en_duda: int = 0

    def a_dict(self) -> dict:
        return {"discrepancia_caracteres": round(self.caracteres, 4),
                "discrepancia_palabras": round(self.palabras, 4),
                "disputas": self.disputas, "bloques_en_duda": self.bloques_en_duda}


def comparar(principal: ResultadoOCR, segundo: ResultadoOCR, *,
             umbral_bloque: float = 0.15, iou_min: float = 0.5) -> Comparacion:
    """Compara dos lecturas. Si ambas traen bloques, empareja por solapamiento
    y anota en cada bloque de ``principal`` la lectura alternativa; los que
    discrepan más de ``umbral_bloque`` quedan con ``revisar=True``.

    Modifica los bloques de ``principal`` (alternativas y revisar).
    """
    c = Comparacion(discrepancia_caracteres(principal.texto, segundo.texto),
                    discrepancia_palabras(principal.texto, segundo.texto),
                    palabras_en_disputa(principal.texto, segundo.texto))
    if principal.bloques and segundo.bloques:
        for b in principal.bloques:
            par = _mejor_par(b, segundo.bloques, iou_min)
            if par is None or not (b.texto or par.texto):
                continue
            d = discrepancia_caracteres(b.texto, par.texto)
            b.alternativas.append({"motor": segundo.motor, "texto": par.texto,
                                   "confianza": par.confianza, "discrepancia": round(d, 4)})
            if d > umbral_bloque:
                b.revisar = True
                c.bloques_en_duda += 1
    return c


def _mejor_par(b: Bloque, otros: list[Bloque], iou_min: float) -> Bloque | None:
    mejor, valor = None, iou_min
    for o in otros:
        v = _iou(b.bbox, o.bbox)
        if v >= valor:
            mejor, valor = o, v
    return mejor
