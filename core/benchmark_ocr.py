"""core/benchmark_ocr.py — Evaluación comparativa de rutas de OCR.

Bashkar Station ofrece varias rutas de reconocimiento (Tesseract, Kraken/CATMuS,
IA de visión multiproveedor, OCR por zonas, PERO-OCR, Churro-3B). Hasta ahora la
elección entre ellas se hacía por impresión: «esta se ve mejor». Este módulo
permite **medirlo** contra una transcripción de referencia hecha a mano.

Las métricas son las estándar en la literatura de OCR/HTR histórico:

- **CER** (*Character Error Rate*): distancia de edición entre caracteres
  dividida por la longitud de la referencia. Es la métrica principal; por
  debajo de 0,10 se considera texto explotable para análisis, por debajo de
  0,05 casi limpio.
- **WER** (*Word Error Rate*): lo mismo sobre palabras. Sube más rápido que el
  CER porque un solo carácter mal parte una palabra entera.
- **Similitud de Levenshtein normalizada**: `1 − CER` acotada a [0, 1]. Es la
  que reporta el paper de CHURRO (EMNLP 2025), y se incluye para poder
  comparar cifras directamente con la literatura.

El módulo es **puro**: no llama a ningún motor de OCR ni a la red. Recibe
transcripciones ya producidas y las compara. Eso lo hace testeable y permite
evaluar rutas que corrieron en otra máquina.

Sobre la normalización: por defecto se compara de forma **indulgente**
(minúsculas, espacios colapsados, sin tildes) porque en prensa histórica los
acentos del original son inconsistentes y penalizar por ellos mide la
ortografía de 1939, no el OCR. Con `estricta=True` se compara literal.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

__all__ = [
    "Resultado",
    "cer",
    "wer",
    "similitud_levenshtein",
    "comparar",
    "evaluar_rutas",
    "tabla_markdown",
    "exportar_csv",
    "exportar_json",
    "distancia_edicion",
]

_RE_ESPACIOS = re.compile(r"\s+")
# Guion de corte de línea: en prensa histórica una palabra partida al final de
# línea no es un error del OCR, es composición tipográfica.
_RE_GUION_CORTE = re.compile(r"[-¬]\s*\n\s*")


def _sin_tildes(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def normalizar(texto: str, estricta: bool = False) -> str:
    """Normaliza un texto para compararlo.

    Con `estricta=False` (por defecto): une palabras partidas por guion de
    corte, colapsa espacios, pasa a minúsculas y quita tildes.
    """
    if texto is None:
        return ""
    texto = _RE_GUION_CORTE.sub("", texto)
    if estricta:
        return _RE_ESPACIOS.sub(" ", texto).strip()
    texto = _RE_ESPACIOS.sub(" ", texto).strip().lower()
    return _sin_tildes(texto)


def distancia_edicion(a: str | list[str], b: str | list[str]) -> int:
    """Distancia de Levenshtein entre dos secuencias (caracteres o palabras).

    Implementación iterativa con dos filas: O(len(a)·len(b)) en tiempo y
    O(min) en memoria. Sin dependencias externas a propósito — una página de
    prensa son unos miles de caracteres, no hace falta más.
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    # Trabajar con la secuencia corta en el eje interno reduce memoria
    if len(a) < len(b):
        a, b = b, a

    anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        actual = [i]
        for j, cb in enumerate(b, start=1):
            costo = 0 if ca == cb else 1
            actual.append(min(
                anterior[j] + 1,        # borrado
                actual[j - 1] + 1,      # inserción
                anterior[j - 1] + costo,  # sustitución
            ))
        anterior = actual
    return anterior[-1]


def cer(referencia: str, hipotesis: str, estricta: bool = False) -> float:
    """Character Error Rate. 0,0 = perfecto. Puede superar 1,0 si sobra texto."""
    ref = normalizar(referencia, estricta)
    hip = normalizar(hipotesis, estricta)
    if not ref:
        return 0.0 if not hip else 1.0
    return distancia_edicion(ref, hip) / len(ref)


def wer(referencia: str, hipotesis: str, estricta: bool = False) -> float:
    """Word Error Rate. Sube más rápido que el CER: un carácter parte la palabra."""
    ref = normalizar(referencia, estricta).split()
    hip = normalizar(hipotesis, estricta).split()
    if not ref:
        return 0.0 if not hip else 1.0
    return distancia_edicion(ref, hip) / len(ref)


def similitud_levenshtein(referencia: str, hipotesis: str,
                          estricta: bool = False) -> float:
    """`1 − CER`, acotada a [0, 1]. Métrica que reporta el paper de CHURRO."""
    return max(0.0, min(1.0, 1.0 - cer(referencia, hipotesis, estricta)))


@dataclass
class Resultado:
    """Resultado de una ruta de OCR sobre un conjunto de páginas."""

    ruta: str
    paginas: int = 0
    cer: float = 0.0
    wer: float = 0.0
    similitud: float = 0.0
    segundos: float = 0.0
    palabras_ref: int = 0
    palabras_hip: int = 0
    por_pagina: list[dict] = field(default_factory=list)

    @property
    def segundos_por_pagina(self) -> float:
        return self.segundos / self.paginas if self.paginas else 0.0

    @property
    def calidad(self) -> str:
        """Lectura cualitativa del CER, con los umbrales de uso habituales."""
        if self.cer <= 0.05:
            return "casi limpio"
        if self.cer <= 0.10:
            return "explotable"
        if self.cer <= 0.25:
            return "requiere corrección"
        return "inservible"

    def como_dict(self) -> dict:
        d = asdict(self)
        d["segundos_por_pagina"] = round(self.segundos_por_pagina, 3)
        d["calidad"] = self.calidad
        return d


def comparar(referencias: dict[str, str], hipotesis: dict[str, str],
             ruta: str = "sin_nombre", segundos: float = 0.0,
             estricta: bool = False) -> Resultado:
    """Compara las transcripciones de UNA ruta contra el estándar de oro.

    `referencias` e `hipotesis` son `{id_pagina: texto}`. Solo se evalúan las
    páginas presentes en `referencias`; una página que la ruta no produjo
    cuenta como texto vacío (error total), que es el comportamiento correcto:
    no reconocer nada es un fallo, no un dato ausente.
    """
    res = Resultado(ruta=ruta, segundos=segundos)
    if not referencias:
        return res

    total_ref_chars = 0
    total_dist_chars = 0
    total_ref_words = 0
    total_dist_words = 0

    for pagina in sorted(referencias):
        ref = normalizar(referencias[pagina], estricta)
        hip = normalizar(hipotesis.get(pagina, ""), estricta)

        d_char = distancia_edicion(ref, hip)
        ref_w, hip_w = ref.split(), hip.split()
        d_word = distancia_edicion(ref_w, hip_w)

        total_ref_chars += len(ref)
        total_dist_chars += d_char
        total_ref_words += len(ref_w)
        total_dist_words += d_word

        res.por_pagina.append({
            "pagina": pagina,
            "cer": round(d_char / len(ref), 4) if ref else 0.0,
            "wer": round(d_word / len(ref_w), 4) if ref_w else 0.0,
            "palabras_ref": len(ref_w),
            "palabras_hip": len(hip_w),
        })

    res.paginas = len(referencias)
    res.palabras_ref = total_ref_words
    res.palabras_hip = sum(p["palabras_hip"] for p in res.por_pagina)
    # Micro-promedio (agregando distancias, no promediando CER por página):
    # es lo correcto, si no una página corta pesa igual que una larga.
    res.cer = total_dist_chars / total_ref_chars if total_ref_chars else 0.0
    res.wer = total_dist_words / total_ref_words if total_ref_words else 0.0
    res.similitud = max(0.0, min(1.0, 1.0 - res.cer))
    return res


def evaluar_rutas(referencias: dict[str, str],
                  resultados_por_ruta: dict[str, dict[str, str]],
                  tiempos: dict[str, float] | None = None,
                  estricta: bool = False) -> list[Resultado]:
    """Evalúa varias rutas de una vez y las devuelve ordenadas por CER."""
    tiempos = tiempos or {}
    salida = [
        comparar(referencias, hip, ruta=nombre,
                 segundos=tiempos.get(nombre, 0.0), estricta=estricta)
        for nombre, hip in resultados_por_ruta.items()
    ]
    return sorted(salida, key=lambda r: r.cer)


def tabla_markdown(resultados: list[Resultado]) -> str:
    """Tabla lista para pegar en el artículo o la memoria de la tesis."""
    if not resultados:
        return "_Sin resultados._"
    lineas = [
        "| Ruta | CER ↓ | WER ↓ | Similitud ↑ | s/página | Calidad |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for r in resultados:
        lineas.append(
            f"| {r.ruta} | {r.cer:.4f} | {r.wer:.4f} | {r.similitud:.4f} "
            f"| {r.segundos_por_pagina:.1f} | {r.calidad} |")
    mejor = resultados[0]
    lineas.append("")
    lineas.append(
        f"Mejor ruta por CER: **{mejor.ruta}** ({mejor.cer:.4f} sobre "
        f"{mejor.paginas} página(s), {mejor.palabras_ref} palabras de referencia).")
    return "\n".join(lineas)


def exportar_csv(resultados: list[Resultado], destino: Path) -> Path:
    """Escribe el resumen por ruta. utf-8-sig para que Excel lo abra bien."""
    destino = Path(destino)
    campos = ["ruta", "paginas", "cer", "wer", "similitud",
              "segundos", "segundos_por_pagina", "palabras_ref",
              "palabras_hip", "calidad"]
    with open(destino, "w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        for r in resultados:
            fila = r.como_dict()
            escritor.writerow({c: fila[c] for c in campos})
    return destino


def exportar_json(resultados: list[Resultado], destino: Path) -> Path:
    """Vuelca todo, incluido el detalle por página, para reanalizar después."""
    destino = Path(destino)
    destino.write_text(
        json.dumps([r.como_dict() for r in resultados], ensure_ascii=False, indent=2),
        encoding="utf-8")
    return destino
