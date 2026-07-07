"""
core/layout_analyzer.py — Análisis de layout de páginas de revista histórica.

Combina dos enfoques complementarios:
  1. LayoutParser (sin ML): detección de líneas y separadores de columna
  2. OpenCV mejorado: clasificación de regiones visuales con características robustas

El análisis de layout es el paso previo a la segmentación de artículos:
identifica qué regiones son texto, qué son imágenes, y dónde están los
separadores de columna/artículo.

Metodología basada en Impresso Project y Newspaper Navigator (LoC):
  - Agrupación de regiones por coordenadas espaciales
  - Clasificación por características de textura/gradiente/tono
  - Deduplicación NMS para evitar doble detección

No requiere torch, detectron2, GPU ni conexión a internet.
Compatible con imágenes escaneadas y páginas renderizadas desde PDF.
"""

import gc
import re
import numpy as np
from pathlib import Path
from typing import Optional

# Intentar importar LayoutParser (opcional — si no está, se usa solo OpenCV)
try:
    import layoutparser as lp
    _LP_AVAILABLE = True
except ImportError:
    _LP_AVAILABLE = False


# ── Tipos de región ──────────────────────────────────────────────────────────
REGION_FOTO        = "Fotografia"
REGION_ILUSTRACION = "Ilustracion"
REGION_PUBLICIDAD  = "Publicidad"
REGION_TEXTO       = "Texto"
REGION_DECORATIVO  = "Decorativo"
REGION_MIXTO       = "Mixto"
REGION_SEPARADOR   = "Separador"

_COLORES = {
    REGION_FOTO:        "#4E79A7",
    REGION_ILUSTRACION: "#F28E2B",
    REGION_PUBLICIDAD:  "#E15759",
    REGION_TEXTO:       "#D3D3D3",
    REGION_DECORATIVO:  "#76B7B2",
    REGION_MIXTO:       "#B07AA1",
    REGION_SEPARADOR:   "#999999",
}

DPI_DEFAULT = 150.0


# ══════════════════════════════════════════════════════════════════════════════
# CLASIFICACIÓN MEJORADA DE REGIONES
# ══════════════════════════════════════════════════════════════════════════════

def _clasificar_region(roi: np.ndarray, aspect: float) -> tuple[str, float]:
    """
    Clasifica una región de imagen usando características de textura y tono.
    Versión mejorada calibrada sobre corpus Estampa 1939:
    - Umbrales ajustados para impresión tipográfica de época (papel amarillento)
    - Mejor discriminación fotografía vs publicidad de fondo oscuro
    - Detección de filetes decorativos por aspecto extremo
    """
    h, w = roi.shape
    if h < 15 or w < 15:
        return REGION_TEXTO, 0.3

    area = h * w
    roi_f = roi.astype(float)

    # Características estadísticas
    varianza    = float(np.var(roi_f))
    media       = float(roi_f.mean())
    q10         = float(np.percentile(roi_f, 10))
    q90         = float(np.percentile(roi_f, 90))
    rango       = q90 - q10
    prop_negro  = float((roi < 50).sum() / area)
    prop_blanco = float((roi > 210).sum() / area)
    prop_medio  = 1.0 - prop_negro - prop_blanco

    # Gradiente (detecta bordes: ilustraciones tienen gradientes fuertes)
    gx = float(np.abs(np.diff(roi_f, axis=1)).mean())
    gy = float(np.abs(np.diff(roi_f, axis=0)).mean())
    gradiente = (gx + gy) / 2.0

    # Histograma con 32 bins para entropía aproximada
    hist, _ = np.histogram(roi.flatten(), bins=32, range=(0, 256))
    hist_n   = hist / max(hist.sum(), 1) + 1e-10
    entropia = float(-np.sum(hist_n * np.log2(hist_n)))
    bins_activos = float((hist > 0).sum()) / 32.0

    # Densidad de tinta (binarización Otsu simple)
    try:
        import cv2
        _, bw = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        densidad_tinta = float(bw.sum() / 255) / max(area, 1)
    except Exception:
        densidad_tinta = prop_negro

    # ── Reglas de clasificación ajustadas ────────────────────────────────────

    # FILETE / ELEMENTO DECORATIVO: aspecto extremadamente alargado
    if aspect > 10 or aspect < 0.08:
        return REGION_DECORATIVO, 0.85

    # FOTOGRAFÍA: amplia gama tonal, rango dinámico amplio, tonos medios abundantes
    # Calibrado: fotos en Estampa 1939 tienen varianza ~1500-4000, rango ~140-180
    es_foto = (
        varianza > 1000
        and rango > 110
        and prop_medio > 0.22
        and bins_activos > 0.50
        and entropia > 2.8
    )
    if es_foto:
        conf = min(0.95, 0.55 + varianza / 7000 + rango / 500)
        return REGION_FOTO, round(conf, 2)

    # ILUSTRACIÓN / CARICATURA: fondo blanco dominante + trazos oscuros + gradiente fuerte
    # Bimodal (B&W), líneas nítidas, poca varianza de tonos medios
    es_ilustracion = (
        prop_blanco > 0.42
        and gradiente > 12
        and prop_negro > 0.03
        and prop_negro < 0.55
        and bins_activos < 0.50
        and varianza < 4000
    )
    if es_ilustracion:
        conf = min(0.90, 0.50 + gradiente / 90 + prop_blanco / 4)
        return REGION_ILUSTRACION, round(conf, 2)

    # PUBLICIDAD CON FONDO OSCURO: densidad de tinta alta + fondo oscuro
    if prop_negro > 0.38 and media < 110 and densidad_tinta > 0.30:
        return REGION_PUBLICIDAD, 0.72

    # PUBLICIDAD NORMAL: mezcla texto + gráfico + varianza baja
    es_publicidad = (
        (prop_negro > 0.18 and prop_blanco > 0.28 and prop_medio < 0.35)
        or (varianza < 500 and densidad_tinta > 0.15 and rango < 85)
    )
    if es_publicidad:
        return REGION_PUBLICIDAD, 0.68

    # MIXTO: varianza moderada que no encaja en otras categorías
    if varianza > 350:
        return REGION_MIXTO, 0.52

    return REGION_TEXTO, 0.45


# ══════════════════════════════════════════════════════════════════════════════
# IoU Y DEDUPLICACIÓN NMS
# ══════════════════════════════════════════════════════════════════════════════

def _iou(a: dict, b: dict) -> float:
    ax1, ay1 = a["x_px"], a["y_px"]
    ax2, ay2 = ax1 + a["w_px"], ay1 + a["h_px"]
    bx1, by1 = b["x_px"], b["y_px"]
    bx2, by2 = bx1 + b["w_px"], by1 + b["h_px"]
    ix1 = max(ax1, bx1); iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2); iy2 = min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    union = a["w_px"] * a["h_px"] + b["w_px"] * b["h_px"] - inter
    return inter / max(union, 1)


def _nms(elementos: list[dict], umbral: float = 0.40) -> list[dict]:
    """Non-Maximum Suppression: elimina detecciones solapadas."""
    if not elementos:
        return elementos
    orden = sorted(range(len(elementos)), key=lambda i: -elementos[i]["confianza"])
    keep = set()
    suprimidos = set()
    for i in orden:
        if i in suprimidos:
            continue
        keep.add(i)
        for j in orden:
            if j <= i or j in suprimidos:
                continue
            if _iou(elementos[i], elementos[j]) > umbral:
                suprimidos.add(j)
    return [elementos[k] for k in sorted(keep)]


# ══════════════════════════════════════════════════════════════════════════════
# ANÁLISIS DE IMAGEN DE PÁGINA
# ══════════════════════════════════════════════════════════════════════════════

def analizar_layout_pagina(
    img_path: Path,
    dpi: float = DPI_DEFAULT,
    txt_path: Optional[Path] = None,
) -> dict:
    """
    Detecta y clasifica regiones visuales en una página escaneada.
    Combina OpenCV (detección de contornos) con LayoutParser (si disponible).

    Retorna dict compatible con visual_analyzer.analizar_elementos_visuales().
    """
    try:
        import cv2
    except ImportError:
        return {}

    img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return {}

    ih, iw = img.shape
    mg = int(min(ih, iw) * 0.020)
    content = img[mg:ih-mg, mg:iw-mg]
    hc, wc = content.shape
    area_total = hc * wc

    # Umbralización doble: global (Otsu) + adaptativa
    _, bw_global = cv2.threshold(
        content, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    bw_adapt = cv2.adaptiveThreshold(
        content, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 31, 12)

    # Morfología con kernel ajustado para agrupar regiones visuales
    # (más grande que texto pero menor que el tamaño de página)
    k_w = max(5, int(wc * 0.035))
    k_h = max(5, int(hc * 0.022))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_w, k_h))
    dilated = cv2.dilate(bw_global, kernel, iterations=2)
    eroded  = cv2.erode(dilated, kernel, iterations=1)

    contours, _ = cv2.findContours(
        eroded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    elementos_raw = []
    for cnt in contours:
        x, y, bw_c, bh_c = cv2.boundingRect(cnt)
        area = bw_c * bh_c

        # Filtros de tamaño: 0.5% mínimo, 92% máximo de la página
        if area < area_total * 0.005:
            continue
        if area > area_total * 0.92:
            continue

        roi    = content[y:y+bh_c, x:x+bw_c]
        aspect = round(bw_c / max(bh_c, 1), 2)
        tipo, conf = _clasificar_region(roi, aspect)

        # Texto puro de tamaño pequeño → ignorar (son columnas de texto normales)
        if tipo == REGION_TEXTO and area < area_total * 0.025:
            continue

        # Densidad de tinta mínima (evitar regiones vacías)
        roi_bw   = bw_adapt[y:y+bh_c, x:x+bw_c]
        densidad = float(roi_bw.sum() / 255) / max(bw_c * bh_c, 1)
        if densidad < 0.015 and area > area_total * 0.03:
            continue

        xa, ya = x + mg, y + mg
        ancho_mm = round(bw_c / dpi * 25.4, 1)
        alto_mm  = round(bh_c / dpi * 25.4, 1)
        area_cm2 = round((ancho_mm * alto_mm) / 100, 1)
        area_pct = round(area / area_total * 100, 1)

        cx_rel = (xa + bw_c / 2) / iw
        cy_rel = (ya + bh_c / 2) / ih
        col = min(2, int(cx_rel * 3))
        fil = min(2, int(cy_rel * 3))
        zonas = {
            (0,0):"sup-izq", (0,1):"sup-cen", (0,2):"sup-der",
            (1,0):"cen-izq", (1,1):"centro",  (1,2):"cen-der",
            (2,0):"inf-izq", (2,1):"inf-cen", (2,2):"inf-der",
        }
        zona = zonas.get((fil, col), "?")

        elementos_raw.append({
            "tipo":           tipo,
            "confianza":      round(conf, 2),
            "x_px": xa,       "y_px": ya,
            "w_px": int(bw_c),"h_px": int(bh_c),
            "x_rel": round(xa/iw, 3), "y_rel": round(ya/ih, 3),
            "w_rel": round(bw_c/iw, 3), "h_rel": round(bh_c/ih, 3),
            "ancho_mm":  ancho_mm,  "alto_mm":  alto_mm,
            "area_cm2":  area_cm2,  "area_pct": area_pct,
            "zona_pagina": zona,
            "aspecto":     aspect,
            "densidad_tinta": round(densidad, 3),
            "pie_de_foto": "",
            "autor": "",
            "descripcion_ai": "",
        })

    # Detectar separadores de columna con LayoutParser (si disponible)
    separadores = []
    if _LP_AVAILABLE:
        try:
            separadores = _detectar_separadores_lp(img_path, iw, ih, mg)
            elementos_raw.extend(separadores)
        except Exception:
            pass

    # Aplicar NMS
    elementos = _nms(elementos_raw)

    # Métricas por tipo
    conteo = {}
    for el in elementos:
        conteo[el["tipo"]] = conteo.get(el["tipo"], 0) + 1

    area_fotos = sum(e["area_cm2"] for e in elementos if e["tipo"] == REGION_FOTO)
    area_ilus  = sum(e["area_cm2"] for e in elementos if e["tipo"] == REGION_ILUSTRACION)
    area_pub   = sum(e["area_cm2"] for e in elementos if e["tipo"] == REGION_PUBLICIDAD)
    area_dec   = sum(e["area_cm2"] for e in elementos if e["tipo"] == REGION_DECORATIVO)

    area_pag_cm2 = round((iw / dpi * 2.54) * (ih / dpi * 2.54), 1)
    area_visual_pct = round((area_fotos + area_ilus) / max(area_pag_cm2, 1) * 100, 1)

    del img, content, bw_global, bw_adapt, dilated, eroded
    gc.collect()

    return {
        "pagina":           img_path.stem,
        "img_w_px": iw,     "img_h_px": ih,
        "area_pag_cm2":     area_pag_cm2,
        "n_elementos":      len(elementos),
        "n_fotos":          conteo.get(REGION_FOTO, 0),
        "n_ilustraciones":  conteo.get(REGION_ILUSTRACION, 0),
        "n_publicidades":   conteo.get(REGION_PUBLICIDAD, 0),
        "n_decorativos":    conteo.get(REGION_DECORATIVO, 0),
        "n_separadores":    conteo.get(REGION_SEPARADOR, 0),
        "n_bloques_texto":  conteo.get(REGION_TEXTO, 0) + conteo.get(REGION_MIXTO, 0),
        "area_fotos_cm2":   round(area_fotos, 1),
        "area_ilus_cm2":    round(area_ilus, 1),
        "area_pub_cm2":     round(area_pub, 1),
        "area_dec_cm2":     round(area_dec, 1),
        "area_visual_pct":  area_visual_pct,
        "elementos":        elementos[:60],
        # Compatibilidad con visual_analyzer
        "ancho_mm": round(iw / dpi * 25.4, 1),
        "alto_mm":  round(ih / dpi * 25.4, 1),
    }


def _detectar_separadores_lp(
    img_path: Path, iw: int, ih: int, mg: int
) -> list[dict]:
    """
    Usa LayoutParser simple_line_detection para encontrar filetes y separadores
    de columna/artículo en la página.
    """
    separadores = []
    try:
        import cv2
        img = cv2.imread(str(img_path))
        if img is None:
            return []
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        # LayoutParser simple line detection
        lineas = lp.simple_line_detection(gray, rho=1, theta=3.14159/180,
                                           threshold=80, minLineLength=int(iw*0.3),
                                           maxLineGap=20)
        if lineas is not None:
            for linea in lineas:
                x1, y1, x2, y2 = linea[0]
                # Solo líneas casi horizontales o verticales
                ang = abs(np.arctan2(y2-y1, x2-x1) * 180 / np.pi)
                if ang < 5 or ang > 175:  # horizontal
                    separadores.append({
                        "tipo": REGION_SEPARADOR, "confianza": 0.80,
                        "x_px": min(x1,x2), "y_px": min(y1,y2),
                        "w_px": abs(x2-x1)+1, "h_px": max(abs(y2-y1), 3),
                        "x_rel": 0, "y_rel": round(min(y1,y2)/ih, 3),
                        "w_rel": round(abs(x2-x1)/iw, 3), "h_rel": 0,
                        "ancho_mm": 0, "alto_mm": 0,
                        "area_cm2": 0, "area_pct": 0,
                        "zona_pagina": "separador", "aspecto": 999,
                        "densidad_tinta": 0, "pie_de_foto": "",
                        "autor": "", "descripcion_ai": "",
                    })
    except Exception:
        pass
    return separadores


# ══════════════════════════════════════════════════════════════════════════════
# ANÁLISIS DESDE PDF (renderizado sin imágenes externas)
# ══════════════════════════════════════════════════════════════════════════════

def analizar_layout_desde_pdf(
    pdf_path: Path,
    dpi: float = 100.0,
    max_paginas: int = 50,
    callback=None,
) -> list[dict]:
    """
    Renderiza páginas del PDF a imagen (en memoria) y analiza su layout.
    No requiere archivos de imagen externos.
    dpi=100 para velocidad; 150 para mayor precisión.
    """
    try:
        import fitz
    except ImportError:
        return []

    doc = fitz.open(str(pdf_path))
    n   = min(doc.page_count, max_paginas)
    resultados = []

    for i in range(n):
        if callback:
            callback(i + 1, n)
        page = doc[i]
        # Renderizar a imagen numpy
        mat  = fitz.Matrix(dpi / 72, dpi / 72)
        pix  = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
        img  = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)

        resultado = _analizar_layout_imagen_np(img, dpi)
        resultado["pagina"] = f"p{i+1:04d}"
        resultados.append(resultado)

    doc.close()
    gc.collect()
    return resultados


def _analizar_layout_imagen_np(img: np.ndarray, dpi: float) -> dict:
    """
    Versión de analizar_layout_pagina que trabaja directamente con array numpy
    (sin necesidad de guardar a disco).
    """
    try:
        import cv2
    except ImportError:
        return {}

    ih, iw = img.shape
    mg = int(min(ih, iw) * 0.020)
    content = img[mg:ih-mg, mg:iw-mg]
    hc, wc = content.shape
    area_total = hc * wc

    _, bw_global = cv2.threshold(
        content, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    bw_adapt = cv2.adaptiveThreshold(
        content, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 31, 12)

    k_w = max(5, int(wc * 0.035))
    k_h = max(5, int(hc * 0.022))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_w, k_h))
    dilated = cv2.dilate(bw_global, kernel, iterations=2)
    eroded  = cv2.erode(dilated, kernel, iterations=1)

    contours, _ = cv2.findContours(
        eroded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    elementos_raw = []
    for cnt in contours:
        x, y, bw_c, bh_c = cv2.boundingRect(cnt)
        area = bw_c * bh_c
        if area < area_total * 0.005 or area > area_total * 0.92:
            continue
        roi    = content[y:y+bh_c, x:x+bw_c]
        aspect = round(bw_c / max(bh_c, 1), 2)
        tipo, conf = _clasificar_region(roi, aspect)
        if tipo == REGION_TEXTO and area < area_total * 0.025:
            continue
        roi_bw   = bw_adapt[y:y+bh_c, x:x+bw_c]
        densidad = float(roi_bw.sum() / 255) / max(bw_c * bh_c, 1)
        if densidad < 0.015 and area > area_total * 0.03:
            continue

        xa, ya   = x + mg, y + mg
        ancho_mm = round(bw_c / dpi * 25.4, 1)
        alto_mm  = round(bh_c / dpi * 25.4, 1)
        area_cm2 = round((ancho_mm * alto_mm) / 100, 1)
        area_pct = round(area / area_total * 100, 1)

        elementos_raw.append({
            "tipo": tipo, "confianza": round(conf, 2),
            "x_px": xa, "y_px": ya, "w_px": int(bw_c), "h_px": int(bh_c),
            "x_rel": round(xa/iw,3), "y_rel": round(ya/ih,3),
            "w_rel": round(bw_c/iw,3), "h_rel": round(bh_c/ih,3),
            "ancho_mm": ancho_mm, "alto_mm": alto_mm,
            "area_cm2": area_cm2, "area_pct": area_pct,
            "zona_pagina": "?", "aspecto": aspect,
            "densidad_tinta": round(densidad, 3),
            "pie_de_foto": "", "autor": "", "descripcion_ai": "",
        })

    elementos = _nms(elementos_raw)
    conteo = {}
    for el in elementos:
        conteo[el["tipo"]] = conteo.get(el["tipo"], 0) + 1

    area_fotos = sum(e["area_cm2"] for e in elementos if e["tipo"] == REGION_FOTO)
    area_ilus  = sum(e["area_cm2"] for e in elementos if e["tipo"] == REGION_ILUSTRACION)
    area_pub   = sum(e["area_cm2"] for e in elementos if e["tipo"] == REGION_PUBLICIDAD)

    del content, bw_global, bw_adapt, dilated, eroded
    gc.collect()

    return {
        "img_w_px": iw, "img_h_px": ih,
        "n_elementos":      len(elementos),
        "n_fotos":          conteo.get(REGION_FOTO, 0),
        "n_ilustraciones":  conteo.get(REGION_ILUSTRACION, 0),
        "n_publicidades":   conteo.get(REGION_PUBLICIDAD, 0),
        "n_decorativos":    conteo.get(REGION_DECORATIVO, 0),
        "n_separadores":    conteo.get(REGION_SEPARADOR, 0),
        "n_bloques_texto":  conteo.get(REGION_TEXTO, 0) + conteo.get(REGION_MIXTO, 0),
        "area_fotos_cm2":   round(area_fotos, 1),
        "area_ilus_cm2":    round(area_ilus, 1),
        "area_pub_cm2":     round(area_pub, 1),
        "area_visual_pct":  round((area_fotos + area_ilus) / max((iw/dpi*2.54)*(ih/dpi*2.54), 1) * 100, 1),
        "elementos":        elementos[:60],
    }


# ══════════════════════════════════════════════════════════════════════════════
# ESTADÍSTICAS AGREGADAS
# ══════════════════════════════════════════════════════════════════════════════

def agregar_estadisticas_numero(paginas: list[dict]) -> dict:
    """
    Agrega estadísticas visuales de todas las páginas de un número.
    Retorna resumen compatible con lo que espera app.py en ST.datos_imagenes.
    """
    if not paginas:
        return {}

    total_fotos    = sum(p.get("n_fotos", 0) for p in paginas)
    total_ilus     = sum(p.get("n_ilustraciones", 0) for p in paginas)
    total_pub      = sum(p.get("n_publicidades", 0) for p in paginas)
    total_dec      = sum(p.get("n_decorativos", 0) for p in paginas)
    total_sep      = sum(p.get("n_separadores", 0) for p in paginas)
    area_visual    = [p.get("area_visual_pct", 0) for p in paginas if p.get("area_visual_pct", 0) > 0]

    return {
        "n_paginas":              len(paginas),
        "total_fotos":            total_fotos,
        "total_ilustraciones":    total_ilus,
        "total_publicidades":     total_pub,
        "total_decorativos":      total_dec,
        "total_separadores":      total_sep,
        "total_elementos_visuales": total_fotos + total_ilus + total_pub + total_dec,
        "area_visual_media_pct":  round(sum(area_visual) / max(len(area_visual), 1), 1),
        "paginas":                paginas,
        "lp_disponible":          _LP_AVAILABLE,
    }
