"""
core/image_analyzer.py — Análisis profundo de imágenes en páginas de publicaciones.

Funcionalidades:
  1. Detección y clasificación de regiones visuales (foto/ilustración/publicidad/texto).
  2. Extracción de posición (x,y,w,h) y tamaño en cm según DPI.
  3. Detección de pie de foto y autor de imagen (texto inmediatamente bajo la imagen).
  4. Diagrama de layout de página: rectángulos coloreados con etiquetas.
  5. Descripción automática con IA (Claude vision) cuando hay API key disponible.
  6. Exportación de datos por número y por página.
"""

import gc
import re
import json
import base64
from pathlib import Path
from typing import Optional
import numpy as np

# ── Tipos de elemento ────────────────────────────────────────────────────────
TIPO_FOTO        = "Fotografía"
TIPO_ILUSTRACION = "Ilustración/Caricatura"
TIPO_PUBLICIDAD  = "Publicidad/Aviso"
TIPO_TEXTO       = "Texto"
TIPO_MIXTO       = "Mixto"

COLORES_TIPO = {
    TIPO_FOTO:        "#2196F3",   # azul
    TIPO_ILUSTRACION: "#4CAF50",   # verde
    TIPO_PUBLICIDAD:  "#FF9800",   # naranja
    TIPO_TEXTO:       "#9E9E9E",   # gris
    TIPO_MIXTO:       "#9C27B0",   # morado
}

DPI_DEFAULT = 150   # resolución por defecto si no se especifica


# ══════════════════════════════════════════════════════════════════════════════
# DEDUPLICACIÓN DE CONTORNOS SOLAPADOS
# ══════════════════════════════════════════════════════════════════════════════

def _iou_ia(a: dict, b: dict) -> float:
    """IoU entre dos elementos detectados (dicts con x_px, y_px, w_px, h_px)."""
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


def _deduplicar_contornos_ia(elementos: list, umbral_iou: float = 0.45) -> list:
    """
    Elimina contornos solapados conservando el de mayor confianza.
    Evita doble conteo cuando el kernel de dilatación genera contornos
    padre e hijo para la misma región física.
    """
    if not elementos:
        return elementos
    orden = sorted(range(len(elementos)), key=lambda i: -elementos[i]["confianza"])
    keepset = set()
    suprimidos = set()
    for i in orden:
        if i in suprimidos:
            continue
        keepset.add(i)
        for j in orden:
            if j <= i or j in suprimidos:
                continue
            if _iou_ia(elementos[i], elementos[j]) > umbral_iou:
                suprimidos.add(j)
    return [elementos[k] for k in sorted(keepset)]


# ══════════════════════════════════════════════════════════════════════════════
# CLASIFICACIÓN DE REGIÓN
# ══════════════════════════════════════════════════════════════════════════════

def _clasificar_region_avanzada(roi: np.ndarray, bw_adapt: np.ndarray) -> tuple[str, float]:
    """
    Clasifica una región de imagen. Retorna (tipo, confianza 0–1).
    Usa múltiples características: varianza, gradiente, histograma, textura.
    """
    h, w = roi.shape
    if h < 20 or w < 20:
        return TIPO_TEXTO, 0.4

    area = h * w
    roi_f = roi.astype(float)

    # ── Características de textura ──────────────────────────────────────────
    varianza   = float(np.var(roi_f))
    media      = float(roi_f.mean())
    std_global = float(np.std(roi_f))
    q10        = float(np.percentile(roi_f, 10))
    q90        = float(np.percentile(roi_f, 90))
    rango_din  = q90 - q10

    # Gradiente (detecta bordes/contornos de línea de ilustración)
    gx = float(np.abs(np.diff(roi_f, axis=1)).mean())
    gy = float(np.abs(np.diff(roi_f, axis=0)).mean())
    gradiente  = (gx + gy) / 2

    # Proporción de píxeles en distintos rangos tonales
    prop_negro  = float((roi < 60).sum()  / area)
    prop_blanco = float((roi > 200).sum() / area)
    prop_medio  = 1.0 - prop_negro - prop_blanco

    # Densidad de "tinta" en la región binarizada
    if bw_adapt is not None and bw_adapt.shape == roi.shape:
        densidad_tinta = float((bw_adapt > 0).sum() / area)
    else:
        densidad_tinta = prop_negro

    # Aspecto
    aspecto = w / max(h, 1)

    # ── Reglas de clasificación ─────────────────────────────────────────────
    # Fotografía: alta varianza, rango dinámico amplio, tonos medios abundantes
    if varianza > 1200 and rango_din > 120 and prop_medio > 0.3:
        confianza = min(0.95, 0.5 + varianza / 6000 + rango_din / 400)
        return TIPO_FOTO, round(confianza, 2)

    # Ilustración/caricatura: gradiente alto, fondo blanco dominante, trazos oscuros
    if gradiente > 18 and prop_blanco > 0.45 and densidad_tinta > 0.05:
        confianza = min(0.90, 0.4 + gradiente / 80 + prop_blanco / 3)
        return TIPO_ILUSTRACION, round(confianza, 2)

    # Publicidad: fondo muy oscuro O mezcla extrema negro+blanco con poca media
    if (prop_negro > 0.35 and prop_blanco > 0.25 and prop_medio < 0.25) or \
       (varianza < 600 and densidad_tinta > 0.2 and aspecto > 0.6):
        return TIPO_PUBLICIDAD, 0.70

    # Alta varianza moderada → mixto
    if varianza > 500:
        return TIPO_MIXTO, 0.55

    return TIPO_TEXTO, 0.50


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACCIÓN DE PIE DE FOTO Y AUTOR
# ══════════════════════════════════════════════════════════════════════════════

RE_FOTO_AUTOR = re.compile(
    r"(?:[Ff]oto(?:grafía)?|[Ff]ig(?:ura)?|[Ff]ot\.|[Ii]l(?:ust)?\.)[:\s]*"
    r"([A-ZÁÉÍÓÚÑ][a-záéíóúñ\-]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ\-]+){1,4})",
)
RE_PIE = re.compile(
    r"(?:[Aa]rriba|[Aa]bajo|[Aa]l\s+centro|[Ii]zquierda|[Dd]erecha|"
    r"[Ee]n\s+la\s+(?:foto|imagen)|[Cc]aptioned?|[Cc]aption)[:\s]+(.{10,120})",
)


def _detectar_pie_y_autor(texto_zona: str) -> dict:
    """Busca pie de foto y autor dentro de un bloque de texto cercano a la imagen."""
    result = {"pie_de_foto": "", "autor_imagen": ""}
    if not texto_zona:
        return result
    m = RE_FOTO_AUTOR.search(texto_zona)
    if m:
        result["autor_imagen"] = m.group(1).strip()
    m = RE_PIE.search(texto_zona)
    if m:
        result["pie_de_foto"] = m.group(1).strip()[:200]
    # Heurística: primera línea de texto corto debajo de una imagen suele ser el pie
    lineas = [l.strip() for l in texto_zona.split("\n") if 8 <= len(l.strip()) <= 160]
    if lineas and not result["pie_de_foto"]:
        result["pie_de_foto"] = lineas[0]
    return result


# ══════════════════════════════════════════════════════════════════════════════
# ANÁLISIS DE UNA PÁGINA
# ══════════════════════════════════════════════════════════════════════════════

def analizar_pagina_visual(
    img_path: Path,
    txt_path: Optional[Path] = None,
    dpi: int = DPI_DEFAULT,
) -> dict:
    """
    Analiza visualmente una página escaneada.
    Retorna dict con lista de elementos detectados, métricas globales y
    datos para el diagrama de layout.
    """
    try:
        import cv2
    except ImportError:
        return {"error": "OpenCV no disponible"}

    img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return {"error": f"No se pudo leer {img_path}"}

    h_total, w_total = img.shape
    pulgadas_w = w_total / dpi
    pulgadas_h = h_total / dpi
    cm_w = pulgadas_w * 2.54
    cm_h = pulgadas_h * 2.54

    mg = int(min(h_total, w_total) * 0.025)
    content = img[mg:h_total-mg, mg:w_total-mg]
    hc, wc  = content.shape

    # Umbralización global + adaptativa
    _, bw_global = cv2.threshold(
        content, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    bw_adapt = cv2.adaptiveThreshold(
        content, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 31, 10)

    # Morfología para agrupar píxeles de imagen (kernel grande)
    k_img = cv2.getStructuringElement(cv2.MORPH_RECT,
                                       (max(3, int(wc*0.04)), max(3, int(hc*0.025))))
    dilatado = cv2.dilate(bw_global, k_img, iterations=2)
    eroded   = cv2.erode(dilatado, k_img, iterations=1)

    contours, _ = cv2.findContours(eroded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area_total  = hc * wc

    # Leer texto OCR de la página si está disponible
    texto_ocr = ""
    if txt_path and txt_path.exists():
        texto_ocr = txt_path.read_text("utf-8", errors="replace")

    elementos_raw = []
    for cnt in contours:
        x, y, bw_c, bh_c = cv2.boundingRect(cnt)
        area = bw_c * bh_c

        # Filtros de tamaño
        if area < area_total * 0.006:   # muy pequeño
            continue
        if area > area_total * 0.92:    # casi toda la página
            continue

        roi   = content[y:y+bh_c, x:x+bw_c]
        roi_b = bw_adapt[y:y+bh_c, x:x+bw_c]
        tipo, conf = _clasificar_region_avanzada(roi, roi_b)

        # Ignorar bloques clasificados como texto puro con baja confianza
        if tipo == TIPO_TEXTO and conf < 0.65:
            continue

        # Coordenadas absolutas (incluyendo margen)
        ax, ay  = int(x + mg), int(y + mg)
        w_cm    = round(bw_c / dpi * 2.54, 2)
        h_cm    = round(bh_c / dpi * 2.54, 2)
        area_cm = round(w_cm * h_cm, 2)

        # Posición relativa en la página (porcentaje)
        pos_x_pct = round(ax / w_total * 100, 1)
        pos_y_pct = round(ay / h_total * 100, 1)

        pie_info = _detectar_pie_y_autor(texto_ocr) if texto_ocr else {}

        elementos_raw.append({
            "tipo":          tipo,
            "confianza":     conf,
            "x_px":          ax, "y_px": ay,
            "w_px":          bw_c, "h_px": bh_c,
            "w_cm":          w_cm, "h_cm": h_cm,
            "area_cm2":      area_cm,
            "area_pct":      round(area / area_total * 100, 1),
            "pos_x_pct":     pos_x_pct,
            "pos_y_pct":     pos_y_pct,
            "aspecto":       round(bw_c / max(bh_c, 1), 2),
            "pie_de_foto":   pie_info.get("pie_de_foto", ""),
            "autor_imagen":  pie_info.get("autor_imagen", ""),
            "descripcion_ia": "",
            "_roi_bytes":    _roi_to_b64(roi) if tipo != TIPO_TEXTO else "",
        })

    # Deduplicar contornos solapados (NMS por IoU)
    elementos = _deduplicar_contornos_ia(elementos_raw)

    del img, content, bw_global, bw_adapt, dilatado, eroded
    gc.collect()

    # Métricas globales
    n_no_texto = [e for e in elementos if e["tipo"] != TIPO_TEXTO]
    area_visual = sum(e["area_pct"] for e in n_no_texto)

    return {
        "pagina":           img_path.stem,
        "w_px": w_total,    "h_px": h_total,
        "w_cm": round(cm_w, 1), "h_cm": round(cm_h, 1),
        "n_elementos":      len(elementos),
        "n_fotos":          sum(1 for e in elementos if e["tipo"] == TIPO_FOTO),
        "n_ilustraciones":  sum(1 for e in elementos if e["tipo"] == TIPO_ILUSTRACION),
        "n_publicidades":   sum(1 for e in elementos if e["tipo"] == TIPO_PUBLICIDAD),
        "area_visual_pct":  round(area_visual, 1),
        "elementos":        elementos,
    }


def _roi_to_b64(roi: np.ndarray) -> str:
    """Convierte una región numpy a JPEG base64 (thumbnail 256px)."""
    try:
        import cv2
        scale = min(1.0, 256 / max(roi.shape))
        if scale < 1.0:
            roi = cv2.resize(roi, None, fx=scale, fy=scale,
                             interpolation=cv2.INTER_AREA)
        _, buf = cv2.imencode(".jpg", roi, [cv2.IMWRITE_JPEG_QUALITY, 70])
        return base64.b64encode(buf).decode("ascii")
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════════════════════════
# DESCRIPCIÓN CON IA (Claude Vision)
# ══════════════════════════════════════════════════════════════════════════════

def describir_imagen_ia(
    roi_b64:    str,
    tipo:       str,
    api_key:    str,
    idioma:     str = "español",
) -> str:
    """
    Llama a la API de Anthropic (Claude) para describir una imagen.
    Retorna la descripción en texto plano.
    """
    if not roi_b64 or not api_key:
        return ""
    try:
        import urllib.request
        prompt = {
            TIPO_FOTO:        f"Describe brevemente esta fotografía de prensa histórica en {idioma}. "
                               "Indica: (1) cuántas personas aparecen y sus características visibles "
                               "(hombre/mujer/niño, edad aproximada, actividad), "
                               "(2) el escenario o contexto, (3) si hay algún elemento visual relevante. "
                               "Sé conciso (máximo 80 palabras).",
            TIPO_ILUSTRACION: f"Describe este elemento gráfico (ilustración, caricatura o dibujo) "
                               f"de una publicación histórica en {idioma}. Indica tipo de ilustración, "
                               "tema o personajes representados. Máximo 60 palabras.",
            TIPO_PUBLICIDAD:  f"Describe brevemente este aviso publicitario histórico en {idioma}. "
                               "Indica: producto o servicio anunciado, empresa si es legible, "
                               "elementos visuales destacados. Máximo 60 palabras.",
        }.get(tipo, f"Describe brevemente este elemento visual en {idioma}. Máximo 50 palabras.")

        body = json.dumps({
            "model":      "claude-opus-4-6",
            "max_tokens": 200,
            "messages":   [{
                "role": "user",
                "content": [
                    {"type": "image",
                     "source": {"type": "base64",
                                "media_type": "image/jpeg",
                                "data": roi_b64}},
                    {"type": "text", "text": prompt},
                ]
            }]
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "Content-Type":    "application/json",
                "x-api-key":       api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        return data["content"][0]["text"].strip()
    except Exception as e:
        return f"[Error IA: {e}]"


def describir_pagina_completa(
    datos_pagina: dict,
    api_key: str,
    idioma: str = "español",
    max_elementos: int = 8,
) -> dict:
    """
    Llama a la IA para describir los elementos visuales de una página.
    Modifica los datos en sitio y retorna el dict actualizado.
    """
    elementos = datos_pagina.get("elementos", [])
    n = 0
    for el in elementos:
        if el["tipo"] in (TIPO_FOTO, TIPO_ILUSTRACION, TIPO_PUBLICIDAD):
            if el.get("_roi_bytes") and n < max_elementos:
                el["descripcion_ia"] = describir_imagen_ia(
                    el["_roi_bytes"], el["tipo"], api_key, idioma)
                n += 1
        # Limpiar bytes para no inflar el JSON
        el.pop("_roi_bytes", None)
    return datos_pagina


# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAMA DE LAYOUT
# ══════════════════════════════════════════════════════════════════════════════

def generar_diagrama_layout(
    datos_pagina: dict,
    titulo: str = "",
) -> bytes:
    """
    Genera una figura matplotlib con el diagrama de layout de la página:
    rectángulos coloreados por tipo sobre el contorno de la página.
    Retorna bytes PNG.
    """
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import io

    w_cm = datos_pagina.get("w_cm", 21)
    h_cm = datos_pagina.get("h_cm", 29)
    w_px = datos_pagina.get("w_px", 1)
    h_px = datos_pagina.get("h_px", 1)
    elementos = datos_pagina.get("elementos", [])

    fig, ax = plt.subplots(figsize=(4.5, 4.5 * h_cm / w_cm))
    ax.set_xlim(0, w_cm); ax.set_ylim(0, h_cm)
    ax.set_facecolor("#FAF8F5")
    ax.set_aspect("equal")
    ax.invert_yaxis()
    ax.set_xlabel("cm", fontsize=8); ax.set_ylabel("cm", fontsize=8)
    titulo_full = f"{titulo} · {datos_pagina.get('pagina','')}" if titulo else datos_pagina.get("pagina","")
    ax.set_title(titulo_full, fontsize=9, fontweight="bold", pad=6)

    # Borde de página
    rect_page = mpatches.FancyBboxPatch((0, 0), w_cm, h_cm,
                                         boxstyle="square,pad=0",
                                         linewidth=1.5, edgecolor="#555",
                                         facecolor="none")
    ax.add_patch(rect_page)

    etiquetas_usadas = set()
    for i, el in enumerate(elementos):
        if el["tipo"] == TIPO_TEXTO:
            continue
        x_cm = el["x_px"] / w_px * w_cm
        y_cm = el["y_px"] / h_px * h_cm
        w_el = el["w_px"] / w_px * w_cm
        h_el = el["h_px"] / h_px * h_cm
        color = COLORES_TIPO.get(el["tipo"], "#999")
        rect = mpatches.FancyBboxPatch(
            (x_cm, y_cm), w_el, h_el,
            boxstyle="square,pad=0.02",
            linewidth=0.8, edgecolor=color,
            facecolor=color, alpha=0.35,
        )
        ax.add_patch(rect)
        # Etiqueta: número del elemento + tipo abreviado
        tipo_abr = {TIPO_FOTO:"F", TIPO_ILUSTRACION:"I",
                    TIPO_PUBLICIDAD:"P", TIPO_MIXTO:"M"}.get(el["tipo"],"?")
        label = f"{tipo_abr}{i+1}"
        ax.text(x_cm + w_el/2, y_cm + h_el/2, label,
                ha="center", va="center", fontsize=7,
                color=color, fontweight="bold")
        etiquetas_usadas.add(el["tipo"])

    # Leyenda
    handles = [mpatches.Patch(facecolor=COLORES_TIPO[t], alpha=0.5, label=t,
                               edgecolor=COLORES_TIPO[t])
               for t in [TIPO_FOTO, TIPO_ILUSTRACION, TIPO_PUBLICIDAD, TIPO_MIXTO]
               if t in etiquetas_usadas]
    if handles:
        ax.legend(handles=handles, loc="lower right", fontsize=7,
                  framealpha=0.85, edgecolor="#CCC")

    plt.tight_layout(pad=0.5)
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    buf.seek(0); data = buf.read()
    plt.close(fig); gc.collect()
    return data


# ══════════════════════════════════════════════════════════════════════════════
# ANÁLISIS DE UN NÚMERO COMPLETO
# ══════════════════════════════════════════════════════════════════════════════

def analizar_numero_imagenes(
    img_dir:   Path,
    ocr_dir:   Path,
    nombre:    str,
    dpi:       int = DPI_DEFAULT,
    api_key:   str = "",
    max_ia:    int = 20,
    callback   = None,
) -> dict:
    """
    Analiza todas las páginas escaneadas de un número.
    Si se provee api_key, describe las imágenes con IA.
    callback(msg:str) para reporting de progreso.
    """
    def log(m):
        if callback: callback(m)

    imgs = sorted(img_dir.glob("*.png"))
    if not imgs:
        imgs = sorted(img_dir.glob("*.jpg")) + sorted(img_dir.glob("*.tiff"))
    if not imgs:
        return {"numero": nombre, "n_paginas": 0, "paginas": []}

    paginas = []
    n_ia = 0
    total_fotos = total_ilus = total_pub = 0

    for i, img_p in enumerate(imgs):
        log(f"    🖼️ Página {i+1}/{len(imgs)}: {img_p.name}")
        txt_p = ocr_dir / nombre / (img_p.stem + ".txt")
        datos = analizar_pagina_visual(img_p, txt_p if txt_p.exists() else None, dpi)
        if "error" in datos:
            log(f"    ⚠️ {datos['error']}")
            continue

        # Descripción IA
        if api_key and n_ia < max_ia:
            n_ia_pag = sum(1 for e in datos["elementos"]
                           if e["tipo"] in (TIPO_FOTO, TIPO_ILUSTRACION, TIPO_PUBLICIDAD)
                           and e.get("_roi_bytes"))
            if n_ia_pag:
                log(f"       🤖 Describiendo {min(n_ia_pag, max_ia-n_ia)} elementos…")
                datos = describir_pagina_completa(datos, api_key, max_elementos=max_ia-n_ia)
                n_ia += n_ia_pag
        else:
            # Limpiar bytes aunque no haya IA
            for el in datos.get("elementos", []):
                el.pop("_roi_bytes", None)

        total_fotos += datos["n_fotos"]
        total_ilus  += datos["n_ilustraciones"]
        total_pub   += datos["n_publicidades"]
        paginas.append(datos)

    return {
        "numero":          nombre,
        "n_paginas":       len(paginas),
        "total_fotos":     total_fotos,
        "total_ilustraciones": total_ilus,
        "total_publicidades":  total_pub,
        "area_visual_media":   round(
            sum(p["area_visual_pct"] for p in paginas) / max(len(paginas), 1), 1),
        "paginas":         paginas,
    }
