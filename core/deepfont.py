"""core/deepfont.py — Clasificación de estilo tipográfico para prensa histórica.

Inspirado en DeepFont (Adobe, 2015) pero adaptado a prensa latinoamericana 1930s.
Clasifica el ESTILO VISUAL de una tipografía, no su nombre.

Dos estrategias:
  1. CLIP zero-shot (si transformers disponible) — prompts calibrados para prensa
     histórica. Clasifica en categorías semánticamente ricas.
  2. OpenCV heurístico — análisis de características visuales de los trazos.
     Sin dependencias de ML. Menos preciso pero siempre disponible.

Categorías de estilo tipográfico para prensa histórica:
  "serif_romana"     — Times, Century, cuerpo de texto periodístico
  "display_titular"  — tipografía grande para títulos, alto contraste
  "art_deco"         — geométrica, ornamental, años 20-30, avisos de lujo
  "manuscrita"       — lettering dibujado a mano, firmas, avisos artesanales
  "gotica"           — blackletter, cabeceras de periódico, nombres de revista
  "sans_geometrica"  — modernista, publicidades nuevas, datos
  "caligráfica"      — script, publicidades de moda y perfumes
  "display_creative" — tipografía creativa/decorativa sin categoría clara

Referencia:
  DeepFont: Explain Your Type (ACMM 2015) — Zhangyang Wang et al.
  https://arxiv.org/abs/1507.03196
"""

from __future__ import annotations

from typing import Callable

import numpy as np

CATEGORIAS_TIPOGRAFIA = [
    "serif_romana",
    "display_titular",
    "art_deco",
    "manuscrita",
    "gotica",
    "sans_geometrica",
    "caligráfica",
    "display_creative",
]

ETIQUETAS_ES = {
    "serif_romana":     "Serif romana (cuerpo de texto)",
    "display_titular":  "Display / titular (alto contraste)",
    "art_deco":         "Art Déco (geométrica ornamental, años 30)",
    "manuscrita":       "Manuscrita / lettering a mano",
    "gotica":           "Gótica / Blackletter (cabecera de revista)",
    "sans_geometrica":  "Sans-serif geométrica (modernista)",
    "caligráfica":      "Caligráfica / script (moda, lujo)",
    "display_creative": "Display creativa (decorativa estilizada)",
}

COLORES = {
    "serif_romana":     "#6B7280",
    "display_titular":  "#3B82F6",
    "art_deco":         "#F59E0B",
    "manuscrita":       "#22C55E",
    "gotica":           "#8B5CF6",
    "sans_geometrica":  "#0EA5E9",
    "caligráfica":      "#EC4899",
    "display_creative": "#EF4444",
}

# Prompts CLIP calibrados para tipografía de prensa latinoamericana 1930s
_PROMPTS_CLIP = [
    "serif roman typeface body text newspaper 1930s Colombia small font",
    "display headline typeface high contrast thick thin strokes poster 1930s",
    "art deco geometric ornamental decorative typeface 1930s advertisement luxury",
    "handwritten lettering hand-drawn text script calligraphy artisan sign",
    "gothic blackletter old english newspaper masthead masthead title",
    "geometric sans-serif modernist bauhaus typeface 1930s advertisement data",
    "calligraphic script typeface elegant flowing fashion perfume advertisement",
    "creative decorative novelty display typeface experimental ornamental 1930s",
]


def _clasificar_clip(ruta: str) -> dict:
    """Clasificación CLIP zero-shot con prompts tipográficos."""
    try:
        import torch
        from PIL import Image
    except ImportError:
        raise ImportError("pip install transformers torch pillow")

    from core import clip_local
    modelo, proc = clip_local.cargar()   # cacheado: no relee 600 MB por imagen

    img    = Image.open(ruta).convert("RGB")
    inputs = proc(text=_PROMPTS_CLIP, images=img,
                  return_tensors="pt", padding=True, truncation=True)
    with torch.no_grad():
        out    = modelo(**inputs)
        logits = out.logits_per_image[0]
        probs  = torch.softmax(logits, dim=0).numpy()

    idx    = int(np.argmax(probs))
    cat    = CATEGORIAS_TIPOGRAFIA[idx]
    return {
        "categoria":  cat,
        "etiqueta":   ETIQUETAS_ES[cat],
        "confianza":  float(probs[idx]),
        "scores":     {c: float(p) for c, p in zip(CATEGORIAS_TIPOGRAFIA, probs)},
        "metodo":     "clip",
        "color":      COLORES[cat],
    }


def _caracteristicas_opencv(img_gray) -> dict:
    """
    Extrae características visuales del trazo tipográfico con OpenCV.
    Retorna métricas útiles para clasificación heurística.
    """
    import cv2

    alto, ancho = img_gray.shape
    total_px = alto * ancho or 1

    # Binarizar
    _, bw = cv2.threshold(img_gray, 0, 255,
                          cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Proporción de tinta (trazos oscuros)
    prop_tinta = (bw > 0).sum() / total_px

    # Esqueleto para ancho de trazo
    try:
        from skimage.morphology import skeletonize
        skel = skeletonize(bw > 0)
        longitud_skel = skel.sum()
        ancho_trazo_medio = (bw > 0).sum() / (longitud_skel + 1)
    except ImportError:
        longitud_skel = 0
        ancho_trazo_medio = 5.0

    # Contraste de trazo (ratio max/min width) — alto en serif display
    # Usamos desviación estándar de ancho de contornos como proxy
    contornos, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL,
                                     cv2.CHAIN_APPROX_SIMPLE)
    anchos_contornos = []
    for cnt in contornos:
        x, y, w, h = cv2.boundingRect(cnt)
        if w > 3 and h > 3:
            anchos_contornos.append(w)

    contraste_trazo = (np.std(anchos_contornos) / (np.mean(anchos_contornos) + 1)
                       if anchos_contornos else 0)

    # Bordes curvos vs rectos (Canny)
    bordes = cv2.Canny(img_gray, 30, 100)
    ratio_borde = bordes.sum() / (total_px * 255)

    # Orientación de trazos (Hough lines)
    lineas = cv2.HoughLinesP(bordes, 1, np.pi/180, threshold=20,
                              minLineLength=10, maxLineGap=5)
    n_lineas_rectas = len(lineas) if lineas is not None else 0

    # Simetría horizontal (indicador de sans-serif geométrica)
    mitad = ancho // 2
    izq = bw[:, :mitad].astype(float)
    der = np.fliplr(bw[:, mitad:]).astype(float)
    min_w = min(izq.shape[1], der.shape[1])
    simetria = 1.0 - np.mean(np.abs(izq[:, :min_w] - der[:, :min_w])) / 255

    return {
        "prop_tinta":       prop_tinta,
        "ancho_trazo":      ancho_trazo_medio,
        "contraste_trazo":  contraste_trazo,
        "ratio_borde":      ratio_borde,
        "n_lineas_rectas":  n_lineas_rectas,
        "simetria":         simetria,
        "n_contornos":      len(anchos_contornos),
    }


def _clasificar_opencv(ruta: str) -> dict:
    """Clasificación heurística con OpenCV. Siempre disponible."""
    try:
        import cv2
    except ImportError:
        return {
            "categoria": "display_creative", "etiqueta": ETIQUETAS_ES["display_creative"],
            "confianza": 0.2, "scores": {}, "metodo": "fallback", "color": COLORES["display_creative"],
        }

    img = cv2.imread(ruta, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return {
            "categoria": "serif_romana", "etiqueta": ETIQUETAS_ES["serif_romana"],
            "confianza": 0.1, "scores": {}, "metodo": "fallback", "color": COLORES["serif_romana"],
        }

    feat = _caracteristicas_opencv(img)

    # Árbol de decisión calibrado para prensa histórica
    cat = "serif_romana"
    conf = 0.4

    if feat["simetria"] > 0.75 and feat["contraste_trazo"] < 0.5:
        cat = "sans_geometrica"; conf = 0.55
    elif feat["contraste_trazo"] > 1.5 and feat["prop_tinta"] < 0.15:
        cat = "display_titular"; conf = 0.60
    elif feat["n_lineas_rectas"] > 30 and feat["simetria"] > 0.65:
        cat = "art_deco"; conf = 0.50
    elif feat["ratio_borde"] > 0.12 and feat["contraste_trazo"] > 0.8:
        cat = "caligráfica"; conf = 0.45
    elif feat["prop_tinta"] > 0.35:
        cat = "gotica"; conf = 0.50
    elif feat["n_contornos"] < 5 and feat["ratio_borde"] > 0.08:
        cat = "manuscrita"; conf = 0.45
    elif feat["contraste_trazo"] > 0.7:
        cat = "display_creative"; conf = 0.45
    else:
        cat = "serif_romana"; conf = 0.40

    return {
        "categoria":  cat,
        "etiqueta":   ETIQUETAS_ES[cat],
        "confianza":  conf,
        "scores":     feat,
        "metodo":     "opencv",
        "color":      COLORES[cat],
    }


def clasificar_tipografia(ruta: str, usar_clip: bool = True) -> dict:
    """
    Clasifica el estilo tipográfico de una imagen.
    Usa CLIP si está disponible (más preciso), OpenCV como fallback.

    Args:
        ruta:       Ruta a la imagen (recorte de zona etiquetada).
        usar_clip:  True para intentar CLIP primero.

    Returns:
        {categoria, etiqueta, confianza, scores, metodo, color}
    """
    if usar_clip:
        try:
            return _clasificar_clip(ruta)
        except Exception:
            pass
    return _clasificar_opencv(ruta)


def clasificar_lote_tipografia(
    rutas: list[str],
    usar_clip: bool = True,
    callback: Callable[[int, int, str], None] | None = None,
) -> list[dict]:
    """
    Clasifica un lote de imágenes. Con CLIP, carga el modelo una sola vez.

    Retorna lista de {ruta, categoria, etiqueta, confianza, scores, metodo, color}.
    """
    total = len(rutas)

    # Cargar CLIP una vez si está disponible
    modelo_clip = proc_clip = None
    if usar_clip:
        try:
            from core import clip_local
            modelo_clip, proc_clip = clip_local.cargar()
        except Exception:
            pass

    resultados = []
    for i, ruta in enumerate(rutas):
        if callback:
            callback(i + 1, total, ruta)
        try:
            if modelo_clip and proc_clip:
                import torch
                from PIL import Image
                img = Image.open(ruta).convert("RGB")
                inputs = proc_clip(text=_PROMPTS_CLIP, images=img,
                                   return_tensors="pt", padding=True, truncation=True)
                with torch.no_grad():
                    out   = modelo_clip(**inputs)
                    probs = torch.softmax(out.logits_per_image[0], dim=0).numpy()
                idx = int(np.argmax(probs))
                cat = CATEGORIAS_TIPOGRAFIA[idx]
                res = {
                    "categoria": cat, "etiqueta": ETIQUETAS_ES[cat],
                    "confianza": float(probs[idx]),
                    "scores": {c: float(p) for c, p in zip(CATEGORIAS_TIPOGRAFIA, probs)},
                    "metodo": "clip", "color": COLORES[cat],
                }
            else:
                res = _clasificar_opencv(ruta)
        except Exception as e:
            res = {
                "categoria": "display_creative",
                "etiqueta":  ETIQUETAS_ES["display_creative"],
                "confianza": 0.0, "scores": {}, "metodo": "error",
                "color": COLORES["display_creative"], "error": str(e),
            }
        res["ruta"] = ruta
        resultados.append(res)

    return resultados


def estadisticas_tipografia(resultados: list[dict]) -> dict:
    """Estadísticas sobre una clasificación de lote."""
    from collections import Counter
    conteo = Counter(r["categoria"] for r in resultados)
    total  = len(resultados) or 1
    conf_m = sum(r["confianza"] for r in resultados) / total

    return {
        "total": len(resultados),
        "distribucion": {
            cat: {
                "n": n,
                "pct": round(100 * n / total, 1),
                "etiqueta": ETIQUETAS_ES.get(cat, cat),
                "color": COLORES.get(cat, "#888"),
            }
            for cat, n in conteo.most_common()
        },
        "confianza_media": round(conf_m, 3),
        "metodos": dict(Counter(r.get("metodo", "?") for r in resultados)),
    }


def clip_disponible() -> bool:
    try:
        import torch
        import transformers
        return True
    except ImportError:
        return False
