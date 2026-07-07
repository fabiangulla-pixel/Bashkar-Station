"""
core/text_postprocessor.py — Postprocesamiento de texto OCR por zonas.

Responsabilidades:
  1. ordenar_zonas_lectura()   — dado el OCR de múltiples zonas etiquetadas,
                                 las numera y ordena en flujo de lectura natural
                                 (columna izquierda ↓, columna derecha ↓, etc.).
  2. normalizar_bloque()       — normaliza un bloque de texto OCR: une palabras
                                 cortadas entre líneas y reconstruye el flujo
                                 de párrafos truncados por límites de zona.
  3. postprocesar_pagina()     — aplica 1+2 a todas las zonas OCR de una página
                                 y devuelve el texto completo rearmado.
  4. postprocesar_numero()     — aplica postprocesar_pagina() a todas las páginas
                                 de un número y exporta .txt resultante.

Diseñado para el corpus Estampa (Colombia, 1930-1940):
  - Páginas con 1-3 columnas de texto
  - Filetes y separadores detectados por zone_labeler.py
  - OCR por Tesseract (spa) o texto embebido via alto_reconstructor.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# ── Tipos de zona que producen texto de artículo ─────────────────────────────
_TIPOS_TEXTO = {"articulo", "titulo", "pie_foto", "indice"}
_TIPOS_IGNORAR = {"foto", "publicidad", "numero_pag", "cabecera",
                  "colofon", "filete", "separador_columna"}


# ─────────────────────────────────────────────────────────────────────────────
# Estructuras de datos
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BloqueTexto:
    """Un bloque de texto OCR asociado a una zona etiquetada."""
    tipo: str               # tipo de zona: articulo, titulo, pie_foto, etc.
    x0: float               # coordenadas normalizadas [0,1]
    y0: float
    x1: float
    y1: float
    texto: str              # texto OCR del bloque (crudo o normalizado)
    pagina: str = ""        # identificador de página: "p0001"
    orden_lectura: int = 0  # asignado por ordenar_zonas_lectura()
    confianza: float = 1.0


# ─────────────────────────────────────────────────────────────────────────────
# 1. Ordenar zonas en flujo de lectura
# ─────────────────────────────────────────────────────────────────────────────

def ordenar_zonas_lectura(
    bloques: list[BloqueTexto],
    n_columnas: int = 0,
    tolerancia_col: float = 0.08,
) -> list[BloqueTexto]:
    """
    Ordena bloques de texto en el flujo de lectura natural de la página.

    Algoritmo:
      1. Detecta automáticamente el número de columnas si n_columnas=0
         (agrupa los x0 de los bloques con tolerancia).
      2. Asigna cada bloque a su columna (izquierda → derecha).
      3. Dentro de cada columna, ordena por y0 (arriba → abajo).
      4. Bloques que abarcan > 60% del ancho (titulares) se colocan
         antes de todas las columnas, ordenados por y0.

    Args:
        bloques:        Lista de BloqueTexto (cualquier orden).
        n_columnas:     Número de columnas forzado. 0 = detectar automáticamente.
        tolerancia_col: Margen para agrupar x0 en la misma columna (fracción de página).

    Returns:
        Lista de BloqueTexto con orden_lectura asignado, en ese orden.
    """
    if not bloques:
        return []

    texto_bloques = [b for b in bloques if b.tipo in _TIPOS_TEXTO and b.texto.strip()]
    otros = [b for b in bloques if b not in texto_bloques]

    if not texto_bloques:
        return bloques

    # Separar bloques de ancho completo (títulos que abarcan toda la página)
    anchos_completos = [b for b in texto_bloques if (b.x1 - b.x0) > 0.60]
    columna_bloques  = [b for b in texto_bloques if b not in anchos_completos]

    # Detectar columnas por agrupación de x0
    if n_columnas == 0 and columna_bloques:
        x0s = sorted(set(round(b.x0 / tolerancia_col) * tolerancia_col
                         for b in columna_bloques))
        # Colapsar x0s cercanos
        columnas_x: list[float] = []
        for x in x0s:
            if not columnas_x or (x - columnas_x[-1]) > tolerancia_col:
                columnas_x.append(x)
        n_columnas = max(1, len(columnas_x))
    elif n_columnas == 0:
        n_columnas = 1
        columnas_x = [0.0]
    else:
        step = 1.0 / n_columnas
        columnas_x = [i * step for i in range(n_columnas)]

    def _asignar_columna(b: BloqueTexto) -> int:
        mejor = 0
        dist_min = abs(b.x0 - columnas_x[0])
        for i, cx in enumerate(columnas_x):
            d = abs(b.x0 - cx)
            if d < dist_min:
                dist_min = d
                mejor = i
        return mejor

    # Agrupar por columna y ordenar dentro de cada columna por y0
    cols: dict[int, list[BloqueTexto]] = {i: [] for i in range(n_columnas)}
    for b in columna_bloques:
        cols[_asignar_columna(b)].append(b)

    # Ordenar: anchos completos primero (por y0), luego columnas izq→der
    ordenados: list[BloqueTexto] = sorted(anchos_completos, key=lambda b: b.y0)
    for col_idx in range(n_columnas):
        ordenados.extend(sorted(cols[col_idx], key=lambda b: b.y0))

    # Asignar orden_lectura
    for i, b in enumerate(ordenados, 1):
        b.orden_lectura = i

    # Los bloques ignorados (foto, filete, etc.) van al final sin orden de lectura
    for b in otros:
        b.orden_lectura = 9999

    return ordenados + otros


# ─────────────────────────────────────────────────────────────────────────────
# 2. Normalizar un bloque de texto
# ─────────────────────────────────────────────────────────────────────────────

def normalizar_bloque(
    texto: str,
    aplicar_ocr_normalizer: bool = True,
    reconstruir_parrafos: bool = True,
) -> str:
    """
    Normaliza el texto de un bloque OCR individual.

    Pasos:
      1. ocr_normalizer.normalizar_texto_ocr() — correcciones de caracteres,
         dígitos incrustados, vocabulario de época, etc.
      2. Reconstrucción de párrafos: une líneas cortas que pertenecen a la
         misma oración (flujo truncado por límite de zona).

    Args:
        texto:                  Texto OCR crudo del bloque.
        aplicar_ocr_normalizer: Aplicar normalización completa de ocr_normalizer.
        reconstruir_parrafos:   Unir líneas fragmentadas dentro del bloque.

    Returns:
        Texto normalizado.
    """
    if not texto or not texto.strip():
        return ""

    if aplicar_ocr_normalizer:
        try:
            from core.ocr_normalizer import normalizar_texto_ocr
            texto = normalizar_texto_ocr(texto)
        except Exception:
            pass

    if reconstruir_parrafos:
        texto = _reconstruir_parrafos_bloque(texto)

    return texto.strip()


def _reconstruir_parrafos_bloque(texto: str) -> str:
    """
    Une líneas fragmentadas dentro de un bloque de texto de una sola columna.

    Regla: si una línea no termina en puntuación fuerte (. ! ? ;) y la
    siguiente empieza en minúscula → mismo párrafo, unir con espacio.
    Líneas vacías = separación de párrafo, se respetan.
    """
    RE_FIN_FUERTE = re.compile(r'[.!?;:]\s*$')

    lineas = texto.split("\n")
    resultado: list[str] = []
    buffer = ""

    for linea in lineas:
        stripped = linea.strip()
        if not stripped:
            if buffer:
                resultado.append(buffer)
                buffer = ""
            resultado.append("")
            continue

        if not buffer:
            buffer = stripped
            continue

        termina_fuerte = bool(RE_FIN_FUERTE.search(buffer))
        empieza_minus  = stripped[0].islower() if stripped else False

        if not termina_fuerte or empieza_minus:
            # Mismo párrafo: unir
            if buffer.endswith("-"):
                buffer = buffer[:-1] + stripped  # palabra cortada
            else:
                buffer = buffer + " " + stripped
        else:
            resultado.append(buffer)
            buffer = stripped

    if buffer:
        resultado.append(buffer)

    return "\n".join(r for r in resultado if r is not None)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Postprocesar una página completa
# ─────────────────────────────────────────────────────────────────────────────

def postprocesar_pagina(
    bloques: list[BloqueTexto],
    n_columnas: int = 0,
    unir_flujo_entre_bloques: bool = True,
) -> tuple[str, list[BloqueTexto]]:
    """
    Postprocesa todos los bloques de texto de una página:
      1. Normaliza el texto de cada bloque individualmente.
      2. Ordena los bloques en flujo de lectura.
      3. Opcionalmente une el texto entre bloques contiguos de la misma columna
         si el anterior no termina en puntuación fuerte (párrafo cortado por
         límite de zona).

    Args:
        bloques:                  Lista de BloqueTexto de la página.
        n_columnas:               0 = detectar automáticamente.
        unir_flujo_entre_bloques: Si True, une párrafos que cruzan límites de zona.

    Returns:
        (texto_completo, bloques_ordenados)
        texto_completo: texto de la página en orden de lectura, listo para análisis.
        bloques_ordenados: los mismos bloques con orden_lectura asignado y texto
                           normalizado.
    """
    # 1. Normalizar cada bloque
    for b in bloques:
        if b.tipo in _TIPOS_TEXTO:
            b.texto = normalizar_bloque(b.texto)

    # 2. Ordenar en flujo de lectura
    ordenados = ordenar_zonas_lectura(bloques, n_columnas=n_columnas)

    # 3. Construir texto completo
    texto_bloques = [b for b in ordenados
                     if b.tipo in _TIPOS_TEXTO and b.orden_lectura < 9999]

    partes: list[str] = []
    RE_FIN_FUERTE = re.compile(r'[.!?;]\s*$')

    for i, b in enumerate(texto_bloques):
        texto_b = b.texto.strip()
        if not texto_b:
            continue

        if unir_flujo_entre_bloques and partes:
            ultimo = partes[-1]
            termina_fuerte = bool(RE_FIN_FUERTE.search(ultimo))
            empieza_minus  = texto_b[0].islower() if texto_b else False
            if not termina_fuerte or empieza_minus:
                if ultimo.endswith("-"):
                    partes[-1] = ultimo[:-1] + texto_b
                    continue
                else:
                    partes[-1] = ultimo + " " + texto_b
                    continue

        partes.append(texto_b)

    texto_completo = "\n\n".join(partes)
    return texto_completo, ordenados


# ─────────────────────────────────────────────────────────────────────────────
# 4. Postprocesar un número completo
# ─────────────────────────────────────────────────────────────────────────────

def postprocesar_numero(
    paginas: dict[str, list[BloqueTexto]],
    out_txt: Path | None = None,
    callback=None,
    **kwargs,
) -> dict[str, str]:
    """
    Postprocesa todas las páginas de un número de revista.

    Args:
        paginas:  dict {id_pagina: [BloqueTexto, ...]}
        out_txt:  Si se indica, guarda el texto completo del número en ese archivo.
        callback: callback(n_actual, n_total, id_pagina)
        **kwargs: Se pasan a postprocesar_pagina().

    Returns:
        dict {id_pagina: texto_completo}
    """
    resultados: dict[str, str] = {}
    ids = sorted(paginas.keys())

    for i, pid in enumerate(ids, 1):
        if callback:
            callback(i, len(ids), pid)
        texto, _ = postprocesar_pagina(paginas[pid], **kwargs)
        resultados[pid] = texto

    if out_txt:
        Path(out_txt).parent.mkdir(parents=True, exist_ok=True)
        texto_numero = "\n\n--- " + " ---\n\n--- ".join(
            f"{pid}\n{t}" for pid, t in resultados.items() if t.strip()
        ) + " ---"
        Path(out_txt).write_text(texto_numero, encoding="utf-8")

    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# Utilidad: construir BloqueTexto desde zonas + archivos txt existentes
# ─────────────────────────────────────────────────────────────────────────────

def bloques_desde_etiquetas(
    zonas: list,
    txt_dir: Path,
    pagina: str,
) -> list[BloqueTexto]:
    """
    Construye una lista de BloqueTexto leyendo el texto OCR desde los .txt
    individuales generados por ocr_engine, asociándolos a las zonas etiquetadas.

    Si el txt de la página existe, se asigna su texto al primer bloque de tipo
    artículo/título. Si hay múltiples zonas, el texto se parte por número de
    líneas proporcional al alto de cada zona.

    Args:
        zonas:   list[Zona] de zone_labeler para la página.
        txt_dir: directorio que contiene los .txt OCR (ej: 03_ocr/numero/).
        pagina:  identificador de página: "p0001".

    Returns:
        list[BloqueTexto]
    """
    bloques: list[BloqueTexto] = []
    txt_path = txt_dir / f"{pagina}.txt"
    texto_pagina = ""
    if txt_path.exists():
        texto_pagina = txt_path.read_text(encoding="utf-8", errors="replace")

    lineas_total = texto_pagina.split("\n") if texto_pagina else []
    zonas_texto = [z for z in zonas if z.tipo in _TIPOS_TEXTO]
    zonas_otras = [z for z in zonas if z.tipo not in _TIPOS_TEXTO]

    # Distribuir líneas entre zonas de texto proporcionalmente a su altura
    if zonas_texto and lineas_total:
        alturas = [max(z.y1 - z.y0, 0.01) for z in zonas_texto]
        total_h = sum(alturas)
        n_lineas = len(lineas_total)
        cursor = 0
        for z, h in zip(zonas_texto, alturas):
            n = max(1, round(n_lineas * h / total_h))
            fragmento = "\n".join(lineas_total[cursor: cursor + n])
            cursor += n
            bloques.append(BloqueTexto(
                tipo=z.tipo,
                x0=z.x0, y0=z.y0, x1=z.x1, y1=z.y1,
                texto=fragmento,
                pagina=pagina,
                confianza=z.confianza,
            ))
    elif zonas_texto:
        for z in zonas_texto:
            bloques.append(BloqueTexto(
                tipo=z.tipo,
                x0=z.x0, y0=z.y0, x1=z.x1, y1=z.y1,
                texto="",
                pagina=pagina,
                confianza=z.confianza,
            ))

    for z in zonas_otras:
        bloques.append(BloqueTexto(
            tipo=z.tipo,
            x0=z.x0, y0=z.y0, x1=z.x1, y1=z.y1,
            texto="",
            pagina=pagina,
            confianza=z.confianza,
        ))

    return bloques
