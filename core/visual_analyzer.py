"""
core/visual_analyzer.py — Análisis visual y tipográfico avanzado.

CAPACIDADES:
  · Detección y clasificación de regiones visuales (foto/ilustración/publicidad/texto)
  · Tamaño en mm de cada elemento detectado
  · Posición dentro de la página (coordenadas + zona: superior-izquierda, etc.)
  · Extracción de pie de foto / leyenda (texto adyacente)
  · Diagrama de layout por página (matplotlib)
  · Análisis tipográfico completo desde PDF digital
"""

import gc, re
import numpy as np
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch


# ── Normalización de nombres de fuente ───────────────────────────────────────
_FUENTE_MAPA = {
    "times":"Times New Roman","timesnewroman":"Times New Roman",
    "timesnewromanps":"Times New Roman","timesroman":"Times New Roman",
    "nimbusroman":"Times New Roman (Nimbus)","garamond":"Garamond",
    "palatino":"Palatino","bookman":"Bookman","centschoolbook":"Century Schoolbook",
    "centuryschoolbook":"Century Schoolbook","georgia":"Georgia",
    "caslon":"Caslon","baskerville":"Baskerville","helvetica":"Helvetica",
    "arial":"Arial","nimbussans":"Helvetica (Nimbus)","freesans":"Fuente sans-serif",
    "liberationsans":"Liberation Sans","calibri":"Calibri","futura":"Futura",
    "univers":"Univers","gill":"Gill Sans","optima":"Optima",
    "tahoma":"Tahoma","verdana":"Verdana","courier":"Courier",
    "couriernew":"Courier New","nimbusmon":"Courier (Nimbus)",
    "bodoni":"Bodoni","didot":"Didot","rockwell":"Rockwell",
    "cheltenham":"Cheltenham","clarendon":"Clarendon",
    "script":"Caligráfica","handwriting":"Caligráfica",
}
_RE_PREFIJO = re.compile(r"^[A-Z]{6}\+")

def normalizar_fuente(nombre_raw: str) -> str:
    nombre = _RE_PREFIJO.sub("", nombre_raw)
    estilo = ""
    for suf, etq in [("-BoldItalic"," · Neg.Curs."),("-BoldOblique"," · Neg.Curs."),
                     ("-Bold"," · Negrita"),("-Italic"," · Cursiva"),("-Oblique"," · Cursiva"),
                     ("-Regular",""),("-Roman",""),("MT",""),("PS",""),("PSMT","")]:
        if suf in nombre:
            nombre = nombre.replace(suf,""); estilo = etq; break
    clave = re.sub(r"[^a-z]","",nombre.lower())
    for p,n in _FUENTE_MAPA.items():
        if p in clave: return n + estilo
    limpio = re.sub(r"([a-z])([A-Z])",r"\1 \2",nombre).strip()
    return (limpio or "Desconocida") + estilo

def inferir_clasificacion_fuente(nombre: str) -> str:
    n = nombre.lower()
    if any(k in n for k in ["times","garamond","palatino","bodoni","caslon","baskerville","didot","bookman"]):
        return "Romana (serif)"
    if any(k in n for k in ["helvetica","arial","futura","gill","optima","univers","calibri","tahoma","verdana"]):
        return "Palo seco (sans-serif)"
    if any(k in n for k in ["courier","mono"]): return "Monoespaciada"
    if any(k in n for k in ["caligráf","script","handwriting"]): return "Caligráfica"
    if any(k in n for k in ["clarendon","rockwell","egyptian","slab"]): return "Egipcia (slab-serif)"
    return "Otra"


# ── Constantes de clasificación visual ───────────────────────────────────────
TIPO_FOTO        = "Fotografía"
TIPO_ILUSTRACION = "Ilustración / caricatura"
TIPO_PUBLICIDAD  = "Publicidad"
TIPO_DECORATIVO  = "Elemento decorativo"
TIPO_TEXTO       = "Bloque de texto"
TIPO_MIXTO       = "Mixto (texto + imagen)"

# Paleta de colores para el diagrama de layout
_COLORES_TIPO = {
    TIPO_FOTO:        "#4E79A7",   # azul
    TIPO_ILUSTRACION: "#F28E2B",   # naranja
    TIPO_PUBLICIDAD:  "#E15759",   # rojo
    TIPO_DECORATIVO:  "#76B7B2",   # verde agua
    TIPO_TEXTO:       "#D3D3D3",   # gris claro
    TIPO_MIXTO:       "#B07AA1",   # morado
}

ZONAS_PAGINA = {
    (0,0):"superior-izquierda", (0,1):"superior-centro", (0,2):"superior-derecha",
    (1,0):"centro-izquierda",   (1,1):"centro",          (1,2):"centro-derecha",
    (2,0):"inferior-izquierda", (2,1):"inferior-centro", (2,2):"inferior-derecha",
}

def _zona_pagina(x_rel: float, y_rel: float) -> str:
    col = min(2, int(x_rel * 3))
    fila = min(2, int(y_rel * 3))
    return ZONAS_PAGINA.get((fila, col), "desconocida")


# ── Análisis tipográfico desde PDF ───────────────────────────────────────────

def analizar_tipografia_pagina(page) -> dict:
    blocks = page.get_text("dict", flags=7)["blocks"]
    font_data = {}; line_leadings = []; block_x0s = []; img_bboxes = []
    page_w = page.rect.width; page_h = page.rect.height

    for block in blocks:
        if block["type"] == 1:
            bb = block["bbox"]
            w_px,h_px = bb[2]-bb[0],bb[3]-bb[1]
            if w_px > 20 and h_px > 20:
                img_bboxes.append({"x0":bb[0],"y0":bb[1],"x1":bb[2],"y1":bb[3],
                                    "w":round(w_px,1),"h":round(h_px,1)})
            continue
        if block["type"] != 0: continue
        block_x0s.append(block["bbox"][0])
        prev_bottom = None
        for line in block["lines"]:
            if prev_bottom is not None:
                lg = line["bbox"][1] - prev_bottom
                if 0 <= lg <= 30: line_leadings.append(lg)
            prev_bottom = line["bbox"][3]
            for span in line["spans"]:
                t = span["text"].strip()
                if not t or len(t) < 2: continue
                fn = normalizar_fuente(span.get("font",""))
                sz = round(span.get("size",0),1)
                fl = span.get("flags",0)
                nc = len(t)
                if fn not in font_data:
                    font_data[fn] = {"chars":0,"sizes":[],"bold_chars":0,"italic_chars":0,"colores":set()}
                fd = font_data[fn]
                fd["chars"] += nc; fd["sizes"].append(sz)
                if fl & 16: fd["bold_chars"] += nc
                if fl & 2:  fd["italic_chars"] += nc
                fd["colores"].add(f"#{span.get('color',0):06X}")

    all_sizes = [s for fd in font_data.values() for s in fd["sizes"]]
    total_chars = max(sum(fd["chars"] for fd in font_data.values()),1)
    total_bold  = sum(fd["bold_chars"] for fd in font_data.values())
    total_italic= sum(fd["italic_chars"] for fd in font_data.values())
    size_cuerpo = float(np.median(all_sizes)) if all_sizes else 0
    size_titulo = float(np.percentile(all_sizes,90)) if all_sizes else 0
    interl_abs  = float(np.median(line_leadings)) if line_leadings else 0
    n_cols      = _estimar_columnas(block_x0s, page_w)
    fp          = max(font_data, key=lambda f:font_data[f]["chars"]) if font_data else "N/D"

    fuentes_detalle = sorted([{
        "fuente": fn, "clasificacion": inferir_clasificacion_fuente(fn),
        "chars": fd["chars"],
        "tam_mediano": round(float(np.median(fd["sizes"])),1) if fd["sizes"] else 0,
        "tam_min": round(min(fd["sizes"]),1) if fd["sizes"] else 0,
        "tam_max": round(max(fd["sizes"]),1) if fd["sizes"] else 0,
        "negrita_pct": round(fd["bold_chars"]/max(fd["chars"],1)*100,1),
        "cursiva_pct": round(fd["italic_chars"]/max(fd["chars"],1)*100,1),
        "colores": list(fd["colores"])[:3],
    } for fn,fd in font_data.items()], key=lambda x:-x["chars"])

    return {
        "fuente_principal": fp, "clasificacion_fuente": inferir_clasificacion_fuente(fp),
        "n_fuentes": len(font_data),
        "tam_cuerpo": round(size_cuerpo,1), "tam_titulo": round(size_titulo,1),
        "interlineado_abs": round(interl_abs,2),
        "interlineado_rel": round(interl_abs/size_cuerpo,2) if size_cuerpo > 0 else 0,
        "n_columnas": n_cols,
        "negrita_pct": round(total_bold/total_chars*100,1),
        "cursiva_pct": round(total_italic/total_chars*100,1),
        "n_imagenes_embebidas": len(img_bboxes),
        "imagenes_bboxes": img_bboxes[:10],
        "fuentes_detalle": fuentes_detalle[:8],
    }

def _estimar_columnas(x0s, page_width):
    if not x0s or page_width <= 0: return 1
    tol = page_width * 0.07; grupos = []
    for x in sorted(x0s):
        if not any(abs(x-g) <= tol for g in grupos): grupos.append(x)
    grupos = [g for g in grupos if g < page_width * 0.87]
    return max(1, min(len(grupos), 6))

def analizar_tipografia_numero(pdf_path: Path) -> dict:
    try: import fitz
    except ImportError: return {}
    doc = fitz.open(str(pdf_path)); paginas = []
    for i,page in enumerate(doc,1):
        d = analizar_tipografia_pagina(page); d["pagina"] = i; paginas.append(d)
    doc.close(); gc.collect()
    if not paginas: return {}
    todas = {}
    for p in paginas:
        for fd in p.get("fuentes_detalle",[]):
            fn = fd["fuente"]
            if fn not in todas:
                todas[fn] = {"chars":0,"tams":[],"neg":[],"cur":[],"clasificacion":fd.get("clasificacion","")}
            todas[fn]["chars"]  += fd["chars"]
            todas[fn]["tams"].append(fd["tam_mediano"])
            todas[fn]["neg"].append(fd["negrita_pct"])
            todas[fn]["cur"].append(fd["cursiva_pct"])
    resumen = sorted([{
        "fuente": fn,"clasificacion":fd["clasificacion"],"chars_total":fd["chars"],
        "tam_mediano": round(float(np.median(fd["tams"])),1),
        "negrita_pct": round(float(np.mean(fd["neg"])),1),
        "cursiva_pct": round(float(np.mean(fd["cur"])),1),
    } for fn,fd in todas.items()], key=lambda x:-x["chars_total"])
    tams_c = [p["tam_cuerpo"] for p in paginas if p["tam_cuerpo"]>0]
    tams_t = [p["tam_titulo"] for p in paginas if p["tam_titulo"]>0]
    interls = [p["interlineado_rel"] for p in paginas if p["interlineado_rel"]>0]
    columnas = [p["n_columnas"] for p in paginas]
    return {
        "n_paginas": len(paginas), "fuentes_resumen": resumen[:12],
        "fuente_principal": resumen[0]["fuente"] if resumen else "N/D",
        "clasificacion_fuente": resumen[0]["clasificacion"] if resumen else "N/D",
        "n_fuentes": len(todas),
        "tam_cuerpo_medio": round(float(np.median(tams_c)),1) if tams_c else 0,
        "tam_titulo_medio": round(float(np.median(tams_t)),1) if tams_t else 0,
        "ratio_titulo_cuerpo": round(float(np.median(tams_t))/max(float(np.median(tams_c)),0.1),2) if tams_c and tams_t else 0,
        "interlineado_rel": round(float(np.median(interls)),2) if interls else 0,
        "columnas_prom": round(float(np.mean(columnas)),1) if columnas else 0,
        "columnas_moda": max(set(columnas),key=columnas.count) if columnas else 1,
        "negrita_pct": round(float(np.mean([p["negrita_pct"] for p in paginas])),1),
        "cursiva_pct": round(float(np.mean([p["cursiva_pct"] for p in paginas])),1),
        "imagenes_total": sum(p["n_imagenes_embebidas"] for p in paginas),
        "paginas_detalle": paginas,
    }


# ── Análisis visual desde imágenes escaneadas (OpenCV) ───────────────────────

def _clasificar_region_avanzado(roi: np.ndarray, aspect: float) -> tuple[str, float]:
    """
    Clasificación de región con heurísticas mejoradas.
    Devuelve (tipo, confianza 0-1).
    """
    h,w = roi.shape
    if h < 15 or w < 15: return TIPO_TEXTO, 0.3

    # Histograma: distribución de niveles de gris
    hist, _ = np.histogram(roi.flatten(), bins=32, range=(0,256))
    hist_norm = hist / max(hist.sum(), 1)

    varianza   = float(np.var(roi.astype(float)))
    media      = float(roi.mean())
    std        = float(np.std(roi.astype(float)))
    q10        = float(np.percentile(roi,10))
    q90        = float(np.percentile(roi,90))
    rango      = q90 - q10
    prop_negro = float((roi < 60).sum() / (h*w))
    prop_blanco= float((roi > 200).sum() / (h*w))
    prop_medio = 1 - prop_negro - prop_blanco

    # Gradiente (contornos)
    gx = float(np.abs(np.diff(roi.astype(float),axis=1)).mean())
    gy = float(np.abs(np.diff(roi.astype(float),axis=0)).mean())
    grad = (gx+gy)/2

    # Entropía local (mide textura)
    try:
        from scipy.stats import entropy as scipy_entropy
        entropia = float(scipy_entropy(hist_norm + 1e-10))
    except ImportError:
        # Aproximación sin scipy
        p = hist_norm + 1e-10
        entropia = float(-np.sum(p * np.log2(p)))

    # Fracción de bins con contenido (diversidad tonal)
    bins_activos = float((hist > 0).sum()) / 32

    # ── Reglas de clasificación ────────────────────────────────────────────

    # FOTOGRAFÍA: amplia gama tonal, textura alta, rango dinámico amplio
    # Bimodalidad baja (no solo B&W), entropía alta
    es_foto = (
        varianza > 1200 and rango > 130
        and prop_medio > 0.25
        and bins_activos > 0.55
        and entropia > 3.0
    )
    if es_foto: return TIPO_FOTO, min(0.95, 0.6 + varianza/8000)

    # ILUSTRACIÓN / CARICATURA: fondo blanco dominante + contornos fuertes + textura baja
    # Bimodal (B&W), líneas nítidas
    es_ilustracion = (
        prop_blanco > 0.45
        and grad > 15
        and prop_negro > 0.04
        and prop_negro < 0.5
        and bins_activos < 0.45
        and varianza < 3000
    )
    if es_ilustracion: return TIPO_ILUSTRACION, min(0.90, 0.55 + grad/80)

    # PUBLICIDAD: mezcla densa de negro/blanco, aspectos variados,
    # o fondos muy oscuros con texto inverso
    es_publicidad = (
        (prop_negro > 0.20 and prop_blanco > 0.30)     # texto denso sobre fondo claro
        or (prop_negro > 0.40 and media < 100)          # fondo oscuro
        or (varianza < 600 and prop_negro > 0.12 and rango < 90)  # tono plano con texto
    )
    if es_publicidad: return TIPO_PUBLICIDAD, 0.70

    # ELEMENTO DECORATIVO: muy pequeño en área O aspecto muy alargado (filetes, viñetas)
    if aspect > 8 or aspect < 0.12: return TIPO_DECORATIVO, 0.80

    # MIXTO: varianza moderada, mezcla
    if varianza > 400: return TIPO_MIXTO, 0.55

    return TIPO_TEXTO, 0.40


def _extraer_pie_de_foto(img_gray: np.ndarray, x: int, y: int, w: int, h: int,
                          margen_px: int = 25) -> str:
    """
    Busca texto de pie de foto en la banda justo debajo de la región (dentro del margen).
    Heurística: densidad de tinta alta en banda estrecha horizontal.
    """
    ih, iw = img_gray.shape
    y_ini = min(y + h, ih)
    y_fin = min(y + h + margen_px, ih)
    if y_fin <= y_ini or w < 20: return ""
    banda = img_gray[y_ini:y_fin, max(0,x):min(iw,x+w)]
    if banda.size == 0: return ""
    # Binarizar y medir densidad de tinta
    _, bw = __import__("cv2").threshold(banda, 0, 255,
                                        __import__("cv2").THRESH_BINARY_INV + __import__("cv2").THRESH_OTSU)
    densidad = float(bw.sum()/255) / max(banda.shape[0]*banda.shape[1], 1)
    # Densidad 0.05–0.25 sugiere líneas de texto (no imagen, no vacío)
    if 0.04 <= densidad <= 0.30:
        return "[Texto de pie detectado]"
    return ""


def _px_a_mm(px: float, dpi: float = 150.0) -> float:
    """Convierte píxeles a milímetros."""
    return round(px / dpi * 25.4, 1)


def _iou(a: tuple, b: tuple) -> float:
    """Calcula Intersection over Union entre dos bounding boxes (x,y,w,h)."""
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    ix1 = max(ax1, bx1); iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2); iy2 = min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    union = aw * ah + bw * bh - inter
    return inter / max(union, 1)


def _deduplicar_contornos(elementos: list[dict], umbral_iou: float = 0.45) -> list[dict]:
    """
    Elimina contornos solapados (IoU > umbral) conservando el de mayor confianza.
    Resuelve el doble-conteo que ocurre cuando el kernel de dilatación crea
    contornos padre e hijo para la misma región.
    """
    if not elementos:
        return elementos
    # Ordenar por confianza descendente
    orden = sorted(range(len(elementos)), key=lambda i: -elementos[i]["confianza"])
    keepset = set()
    suprimidos = set()
    for i in orden:
        if i in suprimidos:
            continue
        keepset.add(i)
        bi = (elementos[i]["x_px"], elementos[i]["y_px"],
              elementos[i]["w_px"], elementos[i]["h_px"])
        for j in orden:
            if j <= i or j in suprimidos:
                continue
            bj = (elementos[j]["x_px"], elementos[j]["y_px"],
                  elementos[j]["w_px"], elementos[j]["h_px"])
            if _iou(bi, bj) > umbral_iou:
                suprimidos.add(j)
    return [elementos[i] for i in sorted(keepset)]


def analizar_elementos_visuales(img_path: Path, dpi: float = 150.0) -> dict:
    """
    Detecta, clasifica y mide elementos visuales en una imagen de página escaneada.
    Incluye: tipo, tamaño (mm), posición relativa, zona en la página.
    Aplica deduplicación de contornos solapados (IoU-based NMS).

    Mejoras v10.1:
    - Deduplicación NMS para evitar doble conteo de regiones solapadas
    - Detección mejorada de filetes/viñetas decorativas (aspecto muy alargado)
    - Área proporcional respecto a la página en porcentaje
    - Conteo separado por categoría con área total por tipo
    """
    try:
        import cv2
    except ImportError:
        return {}

    img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return {}
    ih, iw = img.shape
    mg = int(min(ih, iw) * 0.025)
    content = img[mg:ih-mg, mg:iw-mg]
    hc, wc = content.shape
    area_total = hc * wc

    # Umbral adaptativo
    _, bw_global = cv2.threshold(content, 0, 255,
                                  cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    bw_adapt = cv2.adaptiveThreshold(content, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 8)

    # Agrupar regiones de imagen con cierre morfológico moderado.
    # Un kernel demasiado grande (o varias iteraciones de dilatación) fusiona
    # columnas y fotos en un único contorno que cubre toda la página y luego
    # se descarta por superar el área máxima → 0 elementos. Se usa un kernel
    # pequeño y MORPH_CLOSE (cierra huecos internos de las fotos sin invadir
    # las calles entre columnas).
    k_img = cv2.getStructuringElement(
        cv2.MORPH_RECT, (max(3, int(wc * 0.012)), max(3, int(hc * 0.012))))
    closed = cv2.morphologyEx(bw_global, cv2.MORPH_CLOSE, k_img, iterations=2)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Si aun así un solo contorno cubre casi toda la página (escaneo muy denso),
    # reintentar con apertura previa para romper puentes finos entre regiones.
    grandes = [c for c in contours
               if cv2.boundingRect(c)[2] * cv2.boundingRect(c)[3] > area_total * 0.85]
    if len(contours) <= 2 and grandes:
        k_open = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        abierto = cv2.morphologyEx(bw_global, cv2.MORPH_OPEN, k_open, iterations=1)
        cerrado2 = cv2.morphologyEx(abierto, cv2.MORPH_CLOSE, k_img, iterations=1)
        contours, _ = cv2.findContours(cerrado2, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)

    elementos_raw = []
    for cnt in contours:
        x, y, bw_c, bh_c = cv2.boundingRect(cnt)
        area = bw_c * bh_c
        if area < area_total * 0.006:
            continue
        if area > area_total * 0.92:
            continue

        roi    = content[y:y+bh_c, x:x+bw_c]
        aspect = round(bw_c / max(bh_c, 1), 2)
        tipo, conf = _clasificar_region_avanzado(roi, aspect)

        # Filtrar bloques de texto puro muy pequeños
        if tipo == TIPO_TEXTO and area < area_total * 0.03:
            continue

        # Densidad de tinta mínima
        roi_bw   = bw_adapt[y:y+bh_c, x:x+bw_c]
        densidad = float(roi_bw.sum() / 255) / max(bw_c * bh_c, 1)
        if densidad < 0.02 and area > area_total * 0.04:
            continue

        # Coordenadas absolutas
        xa, ya = x + mg, y + mg
        cx_rel = (xa + bw_c / 2) / iw
        cy_rel = (ya + bh_c / 2) / ih
        zona   = _zona_pagina(cx_rel, cy_rel)

        ancho_mm = _px_a_mm(bw_c, dpi)
        alto_mm  = _px_a_mm(bh_c, dpi)
        area_cm2 = round((ancho_mm * alto_mm) / 100, 1)
        area_pct = round(area / area_total * 100, 1)

        pie = _extraer_pie_de_foto(content, x, y, bw_c, bh_c)

        elementos_raw.append({
            "tipo":           tipo,
            "confianza":      round(conf, 2),
            "x_px": xa,       "y_px": ya,
            "w_px": int(bw_c),"h_px": int(bh_c),
            "x_rel": round(xa/iw, 3),   "y_rel": round(ya/ih, 3),
            "w_rel": round(bw_c/iw, 3), "h_rel": round(bh_c/ih, 3),
            "ancho_mm":       ancho_mm,
            "alto_mm":        alto_mm,
            "area_cm2":       area_cm2,
            "area_pct":       area_pct,
            "zona_pagina":    zona,
            "aspecto":        aspect,
            "densidad_tinta": round(densidad, 3),
            "pie_de_foto":    pie,
            "autor":          "",
            "descripcion_ai": "",
        })

    # Deduplicar contornos solapados
    elementos = _deduplicar_contornos(elementos_raw)

    # Métricas globales
    conteo = {t: 0 for t in [TIPO_FOTO, TIPO_ILUSTRACION, TIPO_PUBLICIDAD,
                               TIPO_DECORATIVO, TIPO_TEXTO, TIPO_MIXTO]}
    for el in elementos:
        conteo[el["tipo"]] = conteo.get(el["tipo"], 0) + 1

    area_fotos = sum(el["area_cm2"] for el in elementos if el["tipo"] == TIPO_FOTO)
    area_ilus  = sum(el["area_cm2"] for el in elementos if el["tipo"] == TIPO_ILUSTRACION)
    area_pub   = sum(el["area_cm2"] for el in elementos if el["tipo"] == TIPO_PUBLICIDAD)
    area_dec   = sum(el["area_cm2"] for el in elementos if el["tipo"] == TIPO_DECORATIVO)

    # Área visual como porcentaje de la página (fotos + ilustraciones)
    area_pag_cm2 = round((iw / dpi * 25.4) * (ih / dpi * 25.4) / 100, 1)
    area_visual_pct = round(
        (area_fotos + area_ilus) / max(area_pag_cm2, 1) * 100, 1)

    prop_negro    = float((content < 60).sum() / area_total)
    varianza_glob = float(np.var(content.astype(float)))

    del img, content, bw_global, bw_adapt, closed
    gc.collect()

    return {
        "n_elementos":      len(elementos),
        "n_fotos":          conteo[TIPO_FOTO],
        "n_ilustraciones":  conteo[TIPO_ILUSTRACION],
        "n_publicidades":   conteo[TIPO_PUBLICIDAD],
        "n_decorativos":    conteo[TIPO_DECORATIVO],
        "n_bloques_texto":  conteo[TIPO_TEXTO] + conteo[TIPO_MIXTO],
        "area_fotos_cm2":   round(area_fotos, 1),
        "area_ilus_cm2":    round(area_ilus, 1),
        "area_pub_cm2":     round(area_pub, 1),
        "area_dec_cm2":     round(area_dec, 1),
        "area_visual_pct":  area_visual_pct,
        "area_pag_cm2":     area_pag_cm2,
        "prop_negro":       round(prop_negro, 3),
        "varianza_global":  round(varianza_glob, 1),
        "elementos":        elementos[:50],
        "img_w_px":         iw,
        "img_h_px":         ih,
    }


# ── Diagrama de layout de página ─────────────────────────────────────────────

def generar_diagrama_layout(datos_pagina: dict, titulo: str = "",
                             out_path: Path | None = None) -> plt.Figure:
    """
    Genera un diagrama de la página con rectángulos coloreados por tipo de elemento.
    Muestra tamaño en mm y zona. Guardable como PNG.
    """
    iw = datos_pagina.get("img_w_px", 1000)
    ih = datos_pagina.get("img_h_px", 1400)
    elementos = datos_pagina.get("elementos", [])

    # Aspecto de la página
    aspecto_pag = ih / max(iw, 1)
    fig_w = 5.0; fig_h = fig_w * aspecto_pag
    fig, ax = plt.subplots(figsize=(fig_w, min(fig_h, 9)))
    ax.set_xlim(0, iw); ax.set_ylim(ih, 0)   # Y invertida (0 arriba)
    ax.set_facecolor("#F5F0E8")               # color papel envejecido

    # Dibujar rectángulo de página
    ax.add_patch(mpatches.Rectangle((0,0), iw, ih,
                                     linewidth=1.5, edgecolor="#333", facecolor="none"))

    for i, el in enumerate(elementos):
        x,y,w,h = el["x_px"],el["y_px"],el["w_px"],el["h_px"]
        tipo    = el["tipo"]
        color   = _COLORES_TIPO.get(tipo, "#999")
        conf    = el.get("confianza", 0)

        patch = FancyBboxPatch((x,y), w, h, boxstyle="round,pad=2",
                                linewidth=1.2, edgecolor=color,
                                facecolor=color, alpha=0.30)
        ax.add_patch(patch)

        # Etiqueta con tipo abreviado y tamaño
        tipo_corto = tipo.split("/")[0].strip()[:10]
        etiqueta = f"{tipo_corto}\n{el['ancho_mm']}×{el['alto_mm']}mm"
        ax.text(x + w/2, y + h/2, etiqueta,
                ha="center", va="center", fontsize=6.5,
                color="#222", fontweight="bold", clip_on=True,
                bbox=dict(boxstyle="round,pad=1", fc="white", alpha=0.6, ec="none"))

        # Numeración
        ax.text(x+3, y+10, str(i+1), fontsize=5.5, color=color, fontweight="bold")

    # Leyenda
    patches = [mpatches.Patch(color=c, label=t, alpha=0.7)
               for t,c in _COLORES_TIPO.items()
               if any(el["tipo"]==t for el in elementos)]
    if patches:
        ax.legend(handles=patches, fontsize=6, loc="lower right",
                  framealpha=0.85, borderpad=0.6)

    ax.set_title(titulo or "Distribución de elementos", fontsize=9,
                 fontweight="bold", pad=6)
    ax.axis("off")
    fig.tight_layout(pad=0.4)

    if out_path:
        fig.savefig(str(out_path), dpi=120, bbox_inches="tight")
        plt.close(fig)

    return fig


def generar_diagramas_numero(datos_paginas: list[dict], nombre: str,
                              out_dir: Path) -> list[Path]:
    """Genera un diagrama PNG de layout por cada página con elementos visuales."""
    rutas = []
    for pag in datos_paginas:
        if pag.get("n_elementos", 0) == 0: continue
        pagina_id = pag.get("pagina","pXXXX")
        ruta = out_dir / f"layout_{nombre}_{pagina_id}.png"
        try:
            generar_diagrama_layout(pag,
                titulo=f"{nombre} · {pagina_id}",
                out_path=ruta)
            rutas.append(ruta)
        except Exception:
            pass
    return rutas


# ── Punto de entrada unificado ───────────────────────────────────────────────

def analizar_numero_visual(
    pdf_path: Path | None,
    img_dir:  Path | None,
    nombre:   str,
    modo:     str = "digital",
) -> dict:
    resultado = {"nombre": nombre, "tipografia": {}, "visual_elementos": []}
    if modo in ("digital","ambos") and pdf_path and pdf_path.exists():
        try:
            resultado["tipografia"] = analizar_tipografia_numero(pdf_path)
        except Exception as e:
            resultado["tipografia"] = {"error": str(e)}
    if modo in ("escaneado","ambos") and img_dir and img_dir.exists():
        imgs = sorted(img_dir.glob("*.png"))[:60]
        pags = []
        for ip in imgs:
            el = analizar_elementos_visuales(ip)
            if el: el["pagina"] = ip.stem; pags.append(el)
        resultado["visual_elementos"] = pags
    return resultado
