"""Validación metodológica de la clasificación automática (para publicar).

El análisis de contenido automatizado debe validarse contra codificación humana
para ser defendible en un paper de humanidades digitales. Este módulo implementa
el flujo estándar de fiabilidad inter-codificador:

  1. exportar_muestra(): toma una muestra ALEATORIA (semilla fija → reproducible)
     de artículos y genera un CSV con la etiqueta AUTOMÁTICA + columnas vacías
     para que el investigador (y un segundo codificador) anoten a mano.
  2. calcular_concordancia(): tras codificar, compara manual vs. automático y
     reporta % de acuerdo y **Kappa de Cohen** (acuerdo corregido por azar),
     la métrica que piden las revistas para fiabilidad inter-codificador.

Portado de ¡Quac! y generalizado: sirve para validar CUALQUIER clasificación
del corpus (polaridad/tono, frame dominante, sección, tipología de página…),
no solo sentimiento. 100% local, sin dependencias nuevas (csv + math).
"""

from __future__ import annotations

import csv
import math  # noqa: F401  (reservado para futuras métricas; mantiene paridad con Quac)
import random
from pathlib import Path
from typing import Callable


def exportar_muestra(articulos: list[dict], ruta_csv: str | Path, *,
                     n: int = 30, semilla: int = 42,
                     campo_texto: str = "texto",
                     campo_id: str = "art_id",
                     etiqueta_auto: Callable[[dict], str] | None = None,
                     nombre_etiqueta: str = "polaridad") -> Path:
    """Exporta una muestra aleatoria de artículos para codificación manual.

    ``articulos``: lista de dicts del corpus (cada uno con un id, texto y los
    metadatos que se quieran volcar).
    ``etiqueta_auto``: función art→str que devuelve la etiqueta automática a
    validar (p. ej. la polaridad o el frame dominante). Si es None, la columna
    ``<nombre>_auto`` queda vacía y se codifica solo a mano.
    ``nombre_etiqueta``: nombre de la dimensión (genera columnas ``<n>_auto`` y
    ``<n>_manual``).

    El CSV trae columnas vacías ``<nombre>_manual`` y ``codificador`` para llenar.
    """
    ruta = Path(ruta_csv)
    ruta.parent.mkdir(parents=True, exist_ok=True)

    rng = random.Random(semilla)        # reproducible
    muestra = articulos[:] if len(articulos) <= n else rng.sample(articulos, n)

    col_auto = f"{nombre_etiqueta}_auto"
    col_manual = f"{nombre_etiqueta}_manual"
    campos = ["id", "seccion", "titulo", "fragmento", col_auto,
              col_manual, "codificador", "notas_codificacion"]
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for art in muestra:
            texto = str(art.get(campo_texto) or "").replace("\n", " ")
            auto = ""
            if etiqueta_auto is not None:
                try:
                    auto = etiqueta_auto(art) or ""
                except Exception:
                    auto = ""
            w.writerow({
                "id": art.get(campo_id, ""),
                "seccion": art.get("seccion", ""),
                "titulo": (str(art.get("titulo") or art.get("titular") or ""))[:120],
                "fragmento": texto[:300],
                col_auto: auto,
                col_manual: "",     # ← llenar a mano
                "codificador": "",
                "notas_codificacion": "",
            })
    return ruta


def _kappa_cohen(pares: list[tuple[str, str]]) -> float:
    """Kappa de Cohen entre dos series de etiquetas (manual vs. auto)."""
    if not pares:
        return 0.0
    etiquetas = sorted({x for p in pares for x in p})
    n = len(pares)
    # acuerdo observado
    po = sum(1 for a, b in pares if a == b) / n
    # acuerdo esperado por azar
    pe = 0.0
    for e in etiquetas:
        pa = sum(1 for a, _ in pares if a == e) / n
        pb = sum(1 for _, b in pares if b == e) / n
        pe += pa * pb
    if pe >= 1.0:
        return 1.0
    return round((po - pe) / (1 - pe), 3)


def _interpreta_kappa(k: float) -> str:
    if k < 0:    return "pobre (peor que el azar)"
    if k < 0.20: return "leve"
    if k < 0.40: return "aceptable"
    if k < 0.60: return "moderado"
    if k < 0.80: return "sustancial"
    return "casi perfecto"


def calcular_concordancia(ruta_csv: str | Path,
                          nombre_etiqueta: str = "polaridad",
                          col_manual: str | None = None,
                          col_auto: str | None = None) -> dict:
    """Lee el CSV ya codificado y calcula acuerdo % + Kappa de Cohen.

    Por defecto usa las columnas ``<nombre_etiqueta>_manual`` y
    ``<nombre_etiqueta>_auto``; se pueden sobrescribir con ``col_manual``/
    ``col_auto``. Solo considera filas con codificación manual no vacía.
    """
    col_manual = col_manual or f"{nombre_etiqueta}_manual"
    col_auto = col_auto or f"{nombre_etiqueta}_auto"
    ruta = Path(ruta_csv)
    pares = []
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            man = (row.get(col_manual) or "").strip().lower()
            aut = (row.get(col_auto) or "").strip().lower()
            if man and aut:
                pares.append((man, aut))
    if not pares:
        return {"error": f"No hay filas con '{col_manual}' codificada.", "n": 0}
    acuerdo = sum(1 for a, b in pares if a == b) / len(pares)
    k = _kappa_cohen(pares)
    # matriz de confusión simple (manual → auto)
    matriz: dict = {}
    for man, aut in pares:
        matriz.setdefault(man, {}).setdefault(aut, 0)
        matriz[man][aut] += 1
    return {
        "n": len(pares),
        "acuerdo": round(acuerdo, 3),
        "kappa": k,
        "interpretacion": _interpreta_kappa(k),
        "matriz_confusion": matriz,
    }
