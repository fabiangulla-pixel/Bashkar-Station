"""
core/alto_reconstructor.py — Reconstrucción de texto estructurado desde PDFs
                              digitalizados con Adobe Acrobat Paper Capture.

PROBLEMA:
Acrobat Paper Capture (el plug-in de digitalización de la BNC) produce PDFs donde
cada palabra OCR se coloca como un span independiente con coordenadas (x, y).
PyMuPDF get_text() devuelve estos spans en orden de aparición en el PDF, NO en
orden de lectura. El resultado es texto fragmentado y desordenado.

SOLUCIÓN:
Agrupar spans por coordenada Y (línea) con tolerancia, luego ordenar cada línea
por coordenada X. Esto reconstruye el orden de lectura natural (columnas de izquierda
a derecha, líneas de arriba a abajo).

También detecta estructura de columnas múltiples y recupera bylines, títulos y
secciones desde las características tipográficas (tamaño de fuente).

Funciona con cualquier PDF de la Hemeroteca Nacional de Colombia (BNC).

Metodología basada en:
- Impresso Project (EPFL): reconstrucción de artículos desde coordenadas ALTO
- Newspaper Navigator (Library of Congress): análisis de layout por coordenadas
"""

import gc
from pathlib import Path

# Fuentes de OCR embebido que se deben ignorar
_FUENTES_OCR_BASURA = {"hiddenhorzocr", "hiddenvertocr", "hiddenocr"}

# Tolerancia vertical para agrupar spans en la misma línea (en puntos PDF)
_TOL_Y = 3.0

# Tolerancia horizontal para detectar separación de columnas (múltiplo del ancho medio de char)
_TOL_COL = 15.0

# Umbral de espacio entre spans consecutivos, como fracción del tamaño de fuente (em).
# Antes era un valor fijo en puntos (2.0). Se descubrió fusionando palabras en Panida
# (1915), pero al medirlo resultó que también fusionaba en Estampa (1939) —el corpus
# principal, contra el que supuestamente estaba calibrado— 126 veces en 12 páginas, sin
# que nadie lo hubiera notado. No era, por tanto, un problema de un corpus "raro": el
# umbral fijo era simplemente demasiado alto para ambos. Un umbral relativo al tamaño de
# fuente del span se adapta a la tipografía de cada digitalización en vez de necesitar un
# valor mágico distinto por corpus.
# Valor calibrado midiendo la RUTA DE PRODUCCIÓN real (reconstruir_texto_pagina con
# ignorar_ocr_basura=True, que filtra los spans de fuente OCR basura y cambia la geometría
# respecto a los spans crudos) sobre dos corpus a la vez, contando palabras fusionadas
# (>16 caracteres) y fragmentos espurios (<=2 caracteres fuera de una lista de palabras
# cortas legítimas). Barrido real, 12 páginas de cada corpus:
#
#   REL     Estampa fus/frag    Panida fus/frag
#   0.185   126 / 200           18 / 132     <- equivalente al viejo umbral fijo de 2.0 pt
#   0.100    56 / 235            3 / 149
#   0.050    19 / 269            0 / 171
#   0.018    12 / 285            0 / 179
#
# El valor NO es libre: los pares reales de Panida (fuente 9.83 pt) acotan el rango por
# ambos lados. Huecos que SÍ son separación de palabra: 0.226 ("sentir;"|"que"), 0.235
# ("un"|"ala"), 0.353 ("tiene"|"un") -> el umbral debe quedar por DEBAJO de 0.226 pt, o
# sea rel < 0.023. Hueco que NO debe recibir espacio: 0.068 ("que"|",", puntuación
# pegada) -> el umbral debe quedar por ENCIMA, o sea rel > 0.007. Rango admisible:
# 0.007 < rel < 0.023. Se elige 0.018, cerca del extremo alto del rango para no partir
# puntuación, y es además el valor con menos fusiones en la tabla de arriba para ambos
# corpus. (Un intento de subirlo a 0.05 buscando menos fragmentación en Estampa se
# descartó: cae fuera del rango y vuelve a fusionar "tieneun"/"unala" en Panida.)
# Criterio de desempate general: errar hacia el fragmento antes que hacia la fusión, ya
# que un token fusionado ("decirtequetuversosabehacer") es irrecuperable para NER y
# frecuencias, mientras que un fragmento corto es filtrable aguas abajo.
_UMBRAL_ESPACIO_REL = 0.018  # ~1.8% del tamaño de fuente (em)
_UMBRAL_ESPACIO_MIN = 0.15   # piso absoluto en puntos, para fuentes muy pequeñas


def _es_fuente_ocr_basura(nombre_fuente: str) -> bool:
    return nombre_fuente.lower().replace("-", "").replace(" ", "") in _FUENTES_OCR_BASURA


def _agrupar_en_lineas(spans: list[dict], tol_y: float = _TOL_Y) -> list[list[dict]]:
    """
    Agrupa spans por coordenada Y0 con tolerancia.
    Retorna lista de líneas, cada línea es lista de spans ordenados por X0.
    """
    if not spans:
        return []

    # Ordenar por Y0 primero
    spans_ord = sorted(spans, key=lambda s: s["y0"])
    lineas = []
    linea_actual = [spans_ord[0]]
    y_ref = spans_ord[0]["y0"]

    for sp in spans_ord[1:]:
        if abs(sp["y0"] - y_ref) <= tol_y:
            linea_actual.append(sp)
        else:
            # Ordenar la línea completada por X0
            linea_actual.sort(key=lambda s: s["x0"])
            lineas.append(linea_actual)
            linea_actual = [sp]
            y_ref = sp["y0"]

    if linea_actual:
        linea_actual.sort(key=lambda s: s["x0"])
        lineas.append(linea_actual)

    return lineas


def _detectar_columnas(lineas: list[list[dict]], page_width: float) -> list[float]:
    """
    Detecta las columnas de texto analizando la distribución de X0 de líneas.
    Retorna lista de coordenadas X que marcan límites de columna.
    """
    if not lineas:
        return [0.0]

    # Recopilar X0 de inicio de cada línea
    x0s = [linea[0]["x0"] for linea in lineas if linea]
    if not x0s:
        return [0.0]

    # Clusterizar con tolerancia
    tol = page_width * 0.06
    grupos = []
    for x in sorted(x0s):
        if not any(abs(x - g) <= tol for g in grupos):
            grupos.append(x)

    # Filtrar grupos que son márgenes de página
    grupos = [g for g in grupos if g < page_width * 0.85]
    return sorted(grupos) if grupos else [0.0]


def _linea_a_texto(linea: list[dict]) -> str:
    """
    Convierte una línea de spans a texto, añadiendo espacios entre palabras
    según la distancia horizontal entre spans.
    """
    if not linea:
        return ""

    partes = []
    for i, sp in enumerate(linea):
        texto = sp["text"]
        if i > 0:
            anterior = linea[i-1]
            # Calcular gap entre span anterior y actual
            gap = sp["x0"] - anterior["x1"]
            # Umbral relativo al tamaño de fuente de los spans (promedio), con piso absoluto
            # para fuentes diminutas. Adaptativo por diseño: una fuente más grande necesita
            # un hueco mayor en puntos para representar el mismo espacio en blanco relativo.
            size_ref = (anterior.get("size", 0) + sp.get("size", 0)) / 2 or 8.0
            umbral = max(_UMBRAL_ESPACIO_MIN, size_ref * _UMBRAL_ESPACIO_REL)
            if gap > umbral:
                partes.append(" ")
        partes.append(texto)

    return "".join(partes).strip()


def reconstruir_texto_pagina(page, ignorar_ocr_basura: bool = True) -> dict:
    """
    Reconstruye el texto de una página PDF con layout posicional (Acrobat Paper Capture).

    Retorna dict con:
        texto      : str   Texto reconstruido en orden de lectura
        lineas     : list  Lista de dicts por línea {texto, y0, x0, size, font, es_titulo}
        n_columnas : int   Número de columnas detectado
        tiene_titulo: bool Si se detectó al menos un título tipográfico
    """
    bloques = page.get_text("dict")["blocks"]
    page_width = page.rect.width
    page_height = page.rect.height

    # Recopilar todos los spans de texto
    spans = []
    sizes_cuerpo = []

    for bloque in bloques:
        if bloque.get("type") != 0:
            continue
        for line in bloque.get("lines", []):
            for sp in line.get("spans", []):
                texto = sp.get("text", "").strip()
                if not texto:
                    continue
                font = sp.get("font", "")
                if ignorar_ocr_basura and _es_fuente_ocr_basura(font):
                    continue
                bb = sp.get("bbox", [0, 0, 0, 0])
                size = sp.get("size", 0)
                spans.append({
                    "text": texto,
                    "font": font,
                    "size": size,
                    "x0": bb[0], "y0": bb[1],
                    "x1": bb[2], "y1": bb[3],
                    "flags": sp.get("flags", 0),
                })
                if size > 0:
                    sizes_cuerpo.append(size)

    if not spans:
        return {"texto": "", "lineas": [], "n_columnas": 1, "tiene_titulo": False}

    # Calcular tamaño de cuerpo (mediana)
    import statistics
    size_mediana = statistics.median(sizes_cuerpo) if sizes_cuerpo else 8.0
    umbral_titulo = size_mediana * 1.4

    # Agrupar en líneas
    lineas_spans = _agrupar_en_lineas(spans)

    # Detectar columnas
    columnas_x = _detectar_columnas(lineas_spans, page_width)
    n_columnas = len(columnas_x)

    # Asignar cada span a su columna
    def _col_de_span(sp):
        for i in range(len(columnas_x) - 1, -1, -1):
            if sp["x0"] >= columnas_x[i] - _TOL_COL:
                return i
        return 0

    # Construir líneas de texto por columna
    # Para multi-columna: ordenar columnas de izquierda a derecha,
    # dentro de cada columna de arriba a abajo
    lineas_por_col: dict[int, list] = {i: [] for i in range(n_columnas)}

    for linea_sp in lineas_spans:
        texto_linea = _linea_a_texto(linea_sp)
        if not texto_linea.strip():
            continue
        size_max = max(sp["size"] for sp in linea_sp)
        font_dom = max(linea_sp, key=lambda s: s["size"])["font"]
        # Una línea que abarca más de la mitad de la página → cabecera/titular de ancho completo
        x_min = min(sp["x0"] for sp in linea_sp)
        x_max = max(sp["x1"] for sp in linea_sp)
        ancho_linea = x_max - x_min
        es_ancho_completo = ancho_linea > page_width * 0.55
        col_idx = 0 if es_ancho_completo else _col_de_span(linea_sp[0])
        es_titulo = size_max >= umbral_titulo and not _es_fuente_ocr_basura(font_dom)

        # flags de PyMuPDF: bit 4 = bold, bit 1 = italic (OR sobre todos los spans)
        flags_union = 0
        for sp in linea_sp:
            flags_union |= sp.get("flags", 0)
        es_bold   = bool(flags_union & (1 << 4))
        es_italic = bool(flags_union & (1 << 1))

        entrada = {
            "texto":          texto_linea,
            "y0":             linea_sp[0]["y0"],
            "x0":             linea_sp[0]["x0"],
            "size":           round(size_max, 1),
            "font":           font_dom,
            "es_titulo":      es_titulo,
            "ancho_completo": es_ancho_completo,
            "bold":           es_bold,
            "italic":         es_italic,
        }
        lineas_por_col[col_idx].append(entrada)

    # Unir: primero cabeceras (ancho completo, col 0 con y0 pequeño),
    # luego columnas de izquierda a derecha
    lineas_texto = []
    tiene_titulo = False

    for col_idx in range(n_columnas):
        for entrada in sorted(lineas_por_col[col_idx], key=lambda l: l["y0"]):
            lineas_texto.append(entrada)
            if entrada["es_titulo"]:
                tiene_titulo = True

    # Texto completo: columnas en orden izquierda→derecha, dentro de columna arriba→abajo
    texto_completo = "\n".join(l["texto"] for l in lineas_texto)

    return {
        "texto":       texto_completo,
        "lineas":      lineas_texto,
        "n_columnas":  n_columnas,
        "tiene_titulo": tiene_titulo,
        "size_cuerpo": round(size_mediana, 1),
    }


def reconstruir_pdf_completo(
    pdf_path: Path,
    callback=None,
) -> list[dict]:
    """
    Reconstruye el texto de todas las páginas de un PDF Paper Capture.
    callback(n_pag, total) para reporting de progreso.

    Retorna lista de dicts por página:
        pagina      : str  "p0001"
        texto       : str  Texto reconstruido
        lineas      : list
        n_columnas  : int
        tiene_titulo: bool
        palabras    : int
    """
    try:
        import fitz
    except ImportError:
        return []

    doc = fitz.open(str(pdf_path))
    paginas = []

    for i, page in enumerate(doc):
        if callback:
            callback(i + 1, doc.page_count)
        datos = reconstruir_texto_pagina(page)
        datos["pagina"] = f"p{i+1:04d}"
        datos["palabras"] = len(datos["texto"].split())
        paginas.append(datos)

    doc.close()
    gc.collect()
    return paginas


def es_pdf_paper_capture(pdf_path: Path) -> bool:
    """
    Detecta si un PDF fue creado con Adobe Acrobat Paper Capture.
    Criterios: producer contiene 'Paper Capture' O hay fuentes HiddenHorzOCR.
    """
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        producer = doc.metadata.get("producer", "").lower()
        es_capture = "paper capture" in producer

        if not es_capture:
            # Verificar en las primeras 3 páginas
            for i in range(min(3, doc.page_count)):
                page = doc[i]
                for b in page.get_text("dict")["blocks"]:
                    if b.get("type") != 0:
                        continue
                    for line in b.get("lines", []):
                        for sp in line.get("spans", []):
                            if _es_fuente_ocr_basura(sp.get("font", "")):
                                es_capture = True
                                break
                        if es_capture:
                            break
                if es_capture:
                    break

        doc.close()
        return es_capture
    except Exception:
        return False


def extraer_titulos_pagina(datos_pagina: dict, min_palabras_titulo: int = 2) -> list[str]:
    """
    Extrae los títulos detectados en una página reconstruida.
    Útil para la segmentación de artículos.
    """
    titulos = []
    for linea in datos_pagina.get("lineas", []):
        if linea.get("es_titulo") and len(linea["texto"].split()) >= min_palabras_titulo:
            titulos.append(linea["texto"])
    return titulos
