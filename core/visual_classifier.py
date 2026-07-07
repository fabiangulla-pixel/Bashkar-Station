"""core/visual_classifier.py — Clasificación visual fina (estilo Newspaper Navigator).

Clasifica regiones de página en categorías visuales propias de la prensa histórica:
  fotografía | ilustración | mapa | cómic | caricatura | anuncio | titular | texto

Dos estrategias según disponibilidad:
  1. CLIP zero-shot (si transformers instalado) — sin entrenamiento, usa descripciones
  2. OpenCV heurístico (siempre disponible) — por características visuales básicas

El clasificador CLIP no requiere fine-tuning: usa prompts en español calibrados
para prensa latinoamericana de los años 30.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Callable
import numpy as np


CATEGORIAS = [
    "fotografía",
    "ilustración",
    "mapa",
    "cómic o historieta",
    "caricatura editorial",
    "anuncio publicitario",
    "titular tipográfico",
    "texto de artículo",
]

# Prompts en español para CLIP zero-shot
_PROMPTS_CLIP = [
    "una fotografía en blanco y negro de una persona o evento de los años 1930",
    "una ilustración o grabado artístico decorativo",
    "un mapa geográfico de Colombia o América Latina",
    "una historieta o tira cómica con viñetas",
    "una caricatura editorial política con figuras exageradas",
    "un anuncio publicitario o aviso comercial con texto y dibujo",
    "un titular de periódico con tipografía grande y llamativa",
    "texto de artículo periodístico en columnas con letra pequeña",
]

COLORES_CATEGORIA = {
    "fotografía":          "#3B82F6",
    "ilustración":         "#8B5CF6",
    "mapa":                "#0EA5E9",
    "cómic o historieta":  "#F59E0B",
    "caricatura editorial":"#EF4444",
    "anuncio publicitario":"#EC4899",
    "titular tipográfico": "#22C55E",
    "texto de artículo":   "#6B7280",
}


def _clasificar_clip(ruta: str, modelo, proc) -> dict:
    """Clasificación CLIP zero-shot. Retorna {categoria, confianza, scores}."""
    import torch
    from PIL import Image

    img    = Image.open(ruta).convert("RGB")
    inputs = proc(
        text=_PROMPTS_CLIP, images=img,
        return_tensors="pt", padding=True, truncation=True
    )
    with torch.no_grad():
        out    = modelo(**inputs)
        logits = out.logits_per_image[0]
        probs  = torch.softmax(logits, dim=0).numpy()

    idx_mejor = int(np.argmax(probs))
    return {
        "categoria": CATEGORIAS[idx_mejor],
        "confianza": float(probs[idx_mejor]),
        "scores":    {c: float(p) for c, p in zip(CATEGORIAS, probs)},
        "metodo":    "clip",
    }


def _clasificar_opencv(ruta: str) -> dict:
    """
    Clasificación heurística con OpenCV.
    Usa: ratio de bordes, varianza de píxeles, densidad de contornos.
    Menos preciso que CLIP pero sin dependencias de ML.
    """
    try:
        import cv2
    except ImportError:
        return {"categoria": "texto de artículo", "confianza": 0.3,
                "scores": {}, "metodo": "fallback"}

    img = cv2.imread(ruta, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return {"categoria": "texto de artículo", "confianza": 0.2,
                "scores": {}, "metodo": "fallback"}

    alto, ancho = img.shape
    total_px    = alto * ancho or 1

    # Bordes (Canny)
    bordes     = cv2.Canny(img, 50, 150)
    ratio_borde = bordes.sum() / (total_px * 255)

    # Varianza de intensidad
    varianza = float(img.var())

    # Contornos
    contornos, _ = cv2.findContours(bordes, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    n_contornos  = len(contornos)

    # Proporción blanco/negro (texto tiene muchos píxeles blancos)
    _, binarizada = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
    prop_blanco   = (binarizada == 255).sum() / total_px

    # Heurísticas simples
    if varianza > 2000 and ratio_borde > 0.05:
        cat = "fotografía"; conf = 0.55
    elif n_contornos > 200 and varianza < 1500:
        cat = "ilustración"; conf = 0.50
    elif prop_blanco < 0.5 and varianza > 1000:
        cat = "anuncio publicitario"; conf = 0.45
    elif prop_blanco > 0.85:
        cat = "texto de artículo"; conf = 0.60
    elif ratio_borde > 0.08 and n_contornos > 100:
        cat = "caricatura editorial"; conf = 0.40
    else:
        cat = "texto de artículo"; conf = 0.35

    return {"categoria": cat, "confianza": conf, "scores": {}, "metodo": "opencv"}


def clasificar_imagen(ruta: str) -> dict:
    """
    Clasifica una imagen en una de las categorías visuales de prensa histórica.
    Usa CLIP si está disponible, OpenCV como fallback.
    """
    try:
        from transformers import CLIPProcessor, CLIPModel
        modelo = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        proc   = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        modelo.eval()
        return _clasificar_clip(ruta, modelo, proc)
    except (ImportError, Exception):
        return _clasificar_opencv(ruta)


def clasificar_lote(
    rutas: list[str],
    callback: Optional[Callable[[int, int, str], None]] = None,
    usar_clip: bool = True,
) -> list[dict]:
    """
    Clasifica un lote de imágenes. Carga CLIP una sola vez para eficiencia.

    Retorna lista de {ruta, categoria, confianza, scores, metodo}.
    """
    total = len(rutas)

    # Intentar cargar CLIP una vez
    modelo_clip = proc_clip = None
    if usar_clip:
        try:
            from transformers import CLIPProcessor, CLIPModel
            modelo_clip = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            proc_clip   = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            modelo_clip.eval()
        except (ImportError, Exception):
            pass

    resultados = []
    for i, ruta in enumerate(rutas):
        if callback:
            callback(i + 1, total, ruta)
        try:
            if modelo_clip and proc_clip:
                res = _clasificar_clip(ruta, modelo_clip, proc_clip)
            else:
                res = _clasificar_opencv(ruta)
        except Exception as e:
            res = {"categoria": "texto de artículo", "confianza": 0.0,
                   "scores": {}, "metodo": "error", "error": str(e)}
        res["ruta"] = ruta
        resultados.append(res)

    return resultados


def estadisticas_clasificacion(resultados: list[dict]) -> dict:
    """
    Estadísticas sobre una clasificación de lote.
    Retorna distribución de categorías y confianza media.
    """
    from collections import Counter
    conteo    = Counter(r["categoria"] for r in resultados)
    total     = len(resultados) or 1
    conf_media = sum(r["confianza"] for r in resultados) / total

    return {
        "total": len(resultados),
        "distribucion": {
            cat: {"n": n, "pct": round(100 * n / total, 1)}
            for cat, n in conteo.most_common()
        },
        "confianza_media": round(conf_media, 3),
        "por_metodo": dict(Counter(r.get("metodo", "?") for r in resultados)),
    }


def clip_disponible() -> bool:
    try:
        import transformers
        import torch
        return True
    except ImportError:
        return False
