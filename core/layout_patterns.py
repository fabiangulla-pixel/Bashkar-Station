"""core/layout_patterns.py — Patrones de layout entre páginas y dentro de
una página: cabeceras repetidas (misma revista, distintos números),
capitulares (drop caps, señal de inicio de artículo), y asociación
pie de foto ↔ foto por identidad estable (Zona.zid/vinculo).

Función pura, sin tkinter. Complementa core/zone_labeler.py (que solo
mira una página a la vez) con patrones que solo se ven al comparar
varias páginas entre sí.
"""

from __future__ import annotations

from difflib import SequenceMatcher

from core.zone_labeler import Zona


def _similares(a: str, b: str, umbral: float = 0.75) -> bool:
    if not a or not b:
        return False
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= umbral


def detectar_cabeceras_repetidas(
    paginas: list[list[Zona]],
    y_max: float = 0.12,
    tolerancia_bbox: float = 0.02,
    min_repeticiones: int = 3,
    textos: list[dict[int, str]] | None = None,
) -> dict[int, list[int]]:
    """Agrupa zonas altas (y0 <= y_max) con bbox parecido entre páginas.

    `paginas` es una lista de listas de Zona (una lista por página, en el
    mismo orden que `textos` si se pasa). Si `textos[i]` trae el texto OCR
    de cada zona candidata (índice de zona → texto), se exige además texto
    parecido (Levenshtein normalizado vía SequenceMatcher) para confirmar
    que es la MISMA cabecera y no solo una coincidencia geométrica.

    Devuelve {grupo_id: [índices de página donde aparece]} — solo grupos
    con al menos `min_repeticiones` páginas.
    """
    candidatas: list[tuple[int, int, Zona]] = []  # (pagina_idx, zona_idx, zona)
    for pi, zonas in enumerate(paginas):
        for zi, z in enumerate(zonas):
            if z.y0 <= y_max:
                candidatas.append((pi, zi, z))

    grupos: list[dict] = []  # cada uno: {"bbox": (x0,y0,x1,y1), "paginas": set(pi)}
    for pi, zi, z in candidatas:
        texto = textos[pi].get(zi, "") if textos else ""
        asignado = False
        for g in grupos:
            gx0, gy0, gx1, gy1 = g["bbox"]
            if (abs(z.x0 - gx0) <= tolerancia_bbox and abs(z.y0 - gy0) <= tolerancia_bbox
                    and abs(z.x1 - gx1) <= tolerancia_bbox and abs(z.y1 - gy1) <= tolerancia_bbox):
                if textos and g["texto"] and texto:
                    if not _similares(g["texto"], texto):
                        continue
                g["paginas"].add(pi)
                asignado = True
                break
        if not asignado:
            grupos.append({"bbox": (z.x0, z.y0, z.x1, z.y1), "paginas": {pi}, "texto": texto})

    resultado = {}
    for i, g in enumerate(grupos):
        if len(g["paginas"]) >= min_repeticiones:
            resultado[i] = sorted(g["paginas"])
    return resultado


def detectar_capitulares(data_tesseract: dict, factor_altura: float = 1.8) -> list[dict]:
    """Detecta capitulares (drop caps): un glifo de 1 carácter cuya altura
    es notablemente mayor que la mediana de altura de línea de la página —
    señal fuerte de inicio de artículo en prensa de los años 30.

    `data_tesseract` es el dict que devuelve pytesseract.image_to_data
    (mismas claves que usa core/word_verifier.py: text, height, line_num,
    left, top, width, conf). Devuelve una lista de dicts
    {"texto", "line_num", "x", "y", "w", "h"} — una entrada por capitular
    candidata, en orden de aparición.
    """
    textos = data_tesseract.get("text", [])
    alturas = [int(h) for t, h in zip(textos, data_tesseract.get("height", [])) if t.strip()]
    if not alturas:
        return []
    alturas_ordenadas = sorted(alturas)
    mediana = alturas_ordenadas[len(alturas_ordenadas) // 2]
    if mediana <= 0:
        return []

    resultado = []
    n = len(textos)
    for i in range(n):
        texto = textos[i].strip()
        if len(texto) != 1 or not texto.isalpha():
            continue
        alto = int(data_tesseract["height"][i])
        if alto >= mediana * factor_altura:
            resultado.append({
                "texto": texto,
                "line_num": data_tesseract.get("line_num", [0] * n)[i],
                "x": int(data_tesseract["left"][i]),
                "y": int(data_tesseract["top"][i]),
                "w": int(data_tesseract["width"][i]),
                "h": alto,
            })
    return resultado


def asociar_pies_fotos(zonas: list[Zona]) -> list[tuple[str, str]]:
    """Recalcula la asociación pie_foto↔foto sobre un conjunto de zonas
    (p.ej. tras edición manual en el etiquetador) y devuelve los pares
    (zid_pie, zid_foto) encontrados, MUTANDO `z.vinculo` en las zonas pie_foto.
    Mismo criterio geométrico que layout_tesseract.analizar_pagina_local:
    solapamiento horizontal ≥50% y borde superior del pie a ≤0.03 debajo
    del borde inferior de la foto."""
    fotos = [z for z in zonas if z.tipo == "foto"]
    pares: list[tuple[str, str]] = []
    for z in zonas:
        if z.tipo != "pie_foto":
            continue
        mejor: Zona | None = None
        for f in fotos:
            solape_x = min(z.x1, f.x1) - max(z.x0, f.x0)
            ancho_min = min(z.x1 - z.x0, f.x1 - f.x0)
            if ancho_min > 0 and solape_x / ancho_min >= 0.5 and 0 <= z.y0 - f.y1 <= 0.03:
                mejor = f
                break
        if mejor is not None:
            z.vinculo = mejor.zid
            pares.append((z.zid, mejor.zid))
    return pares
