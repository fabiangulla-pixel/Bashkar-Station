"""
core/zone_labeler.py — Etiquetador manual de zonas de página.

Permite al usuario marcar zonas en imágenes de páginas escaneadas,
indicando qué áreas procesar con OCR y cuáles ignorar.
El sistema aprende el patrón de pocas páginas etiquetadas y lo aplica al resto.

Clases:
    Zona            — un rectángulo etiquetado con tipo y metadatos
    PlantillaNumero — conjunto de etiquetas para un número de revista
    DetectorZonas   — aprende patrones de páginas etiquetadas y predice en nuevas

Persistencia: JSON en <out_dir>/05_etiquetas/<numero>/p0001.json
"""

from __future__ import annotations
import json
import statistics
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional


# ── Detección automática por visión ──────────────────────────────────────────

def detectar_zonas_opencv(img_path: Path) -> list["Zona"]:
    """
    Detecta zonas en una página escaneada usando OpenCV (sin IA, offline).
    Distingue: foto (bloque oscuro/continuo), texto (líneas finas densas),
    pie de foto (texto corto inmediatamente debajo de una foto).

    Devuelve list[Zona] con confianza < 1.0.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return []

    img_bgr = cv2.imread(str(img_path))
    if img_bgr is None:
        return []

    H, W = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    zonas: list[Zona] = []

    # ── 1. Detectar fotografías ──────────────────────────────────────────────
    # Las fotos son regiones con gradiente alto y varianza de tono elevada,
    # distintas del texto (que tiene píxeles muy negros sobre fondo muy blanco).
    # Estrategia: blur + umbral adaptativo invertido, luego buscar contornos grandes.
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Mapa de "densidad local de bordes" — zonas de foto tienen bordes en
    # TODAS las direcciones (texturas); zonas de texto tienen bordes horizontales.
    edges = cv2.Canny(gray, 50, 150)
    kernel_large = np.ones((40, 40), np.uint8)
    edge_density = cv2.dilate(edges, kernel_large, iterations=1)

    # Varianza local: alta en fotos, baja en texto uniforme
    img_float = gray.astype(np.float32)
    mean_sq = cv2.blur(img_float ** 2, (60, 60))
    mean_val = cv2.blur(img_float, (60, 60))
    variance_map = mean_sq - mean_val ** 2
    # Normalizar
    v_max = variance_map.max()
    if v_max > 0:
        variance_norm = (variance_map / v_max * 255).astype(np.uint8)
    else:
        variance_norm = np.zeros_like(gray)

    # Umbral de varianza: regiones con varianza > 40% del máximo = posible foto
    _, var_mask = cv2.threshold(variance_norm, 100, 255, cv2.THRESH_BINARY)

    # Excluir zonas que son casi puro blanco (fondo de página) o puro negro
    _, bright_mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
    _, dark_mask   = cv2.threshold(gray,  10, 255, cv2.THRESH_BINARY_INV)
    pure_mask = cv2.bitwise_or(bright_mask, dark_mask)
    var_mask  = cv2.bitwise_and(var_mask, cv2.bitwise_not(pure_mask))

    # Morfología para cerrar huecos dentro de las fotos
    k2 = np.ones((20, 20), np.uint8)
    var_closed = cv2.morphologyEx(var_mask, cv2.MORPH_CLOSE, k2, iterations=3)

    contornos_foto, _ = cv2.findContours(
        var_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    foto_boxes: list[tuple[int,int,int,int]] = []  # (x,y,w,h) en px
    area_min_foto = W * H * 0.01   # mínimo 1% del área de página
    area_max_foto = W * H * 0.85   # máximo 85% (evita capturar toda la página)

    for c in contornos_foto:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        if area < area_min_foto or area > area_max_foto:
            continue
        if w < W * 0.05 or h < H * 0.03:  # demasiado estrecho/bajo
            continue
        foto_boxes.append((x, y, w, h))

    # NMS simple para fotos solapadas
    foto_boxes = _nms_boxes(foto_boxes, iou_thresh=0.4)

    for x, y, w, h in foto_boxes:
        zonas.append(Zona(
            tipo="foto",
            x0=round(x / W, 3), y0=round(y / H, 3),
            x1=round((x + w) / W, 3), y1=round((y + h) / H, 3),
            confianza=0.65,
        ))

    # ── 2. Detectar pies de foto ─────────────────────────────────────────────
    # Un pie de foto es una franja de texto corta inmediatamente debajo de una foto.
    # Criterio: banda de altura ≤ 8% de página, justo bajo una caja de foto.
    MAX_PIE_H = H * 0.08
    for (fx, fy, fw, fh) in foto_boxes:
        y_bajo = fy + fh
        # Buscar si hay texto en la franja [y_bajo, y_bajo + MAX_PIE_H]
        y1_pie = min(int(y_bajo + MAX_PIE_H), H)
        if y1_pie <= y_bajo:
            continue
        franja = gray[y_bajo:y1_pie, fx:fx + fw]
        if franja.size == 0:
            continue
        # Si la franja tiene píxeles oscuros (texto) en al menos 2% del área
        n_oscuros = np.sum(franja < 80)
        if n_oscuros / franja.size > 0.02:
            zonas.append(Zona(
                tipo="pie_foto",
                x0=round(fx / W, 3), y0=round(y_bajo / H, 3),
                x1=round((fx + fw) / W, 3), y1=round(y1_pie / H, 3),
                confianza=0.60,
            ))

    # ── 3. Región de artículo: todo lo que queda (no es foto ni pie de foto) ─
    # Crear máscara de "ya ocupado"
    ocupado = np.zeros((H, W), np.uint8)
    for z in zonas:
        x0p = int(z.x0 * W); y0p = int(z.y0 * H)
        x1p = int(z.x1 * W); y1p = int(z.y1 * H)
        ocupado[y0p:y1p, x0p:x1p] = 255

    # Texto = zona con píxeles oscuros que no esté ya ocupada
    _, text_mask = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
    text_free = cv2.bitwise_and(text_mask, cv2.bitwise_not(ocupado))

    k3 = np.ones((8, 30), np.uint8)   # kernel horizontal para líneas de texto
    text_closed = cv2.morphologyEx(text_free, cv2.MORPH_CLOSE, k3, iterations=4)

    contornos_txt, _ = cv2.findContours(
        text_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    area_min_txt = W * H * 0.015  # mínimo 1.5% del área

    txt_boxes = []
    for c in contornos_txt:
        x, y, w, h = cv2.boundingRect(c)
        if w * h >= area_min_txt and w > W * 0.05 and h > H * 0.02:
            txt_boxes.append((x, y, w, h))

    txt_boxes = _nms_boxes(txt_boxes, iou_thresh=0.3)

    for x, y, w, h in txt_boxes:
        zonas.append(Zona(
            tipo="articulo",
            x0=round(x / W, 3), y0=round(y / H, 3),
            x1=round((x + w) / W, 3), y1=round((y + h) / H, 3),
            confianza=0.60,
        ))

    # ── 4. Detectar filetes y separadores de columna ─────────────────────────
    # Filetes: líneas horizontales o verticales largas y delgadas (decorativas
    # o funcionales) que FineReader usa para delimitar columnas y secciones.
    # Estrategia: HoughLinesP sobre imagen binarizada, filtrar por longitud mínima
    # y grosor máximo (filetes ≤ 5px de ancho/alto).
    _, bw_lines = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)

    # Líneas horizontales largas (≥ 30% del ancho de página)
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (int(W * 0.30), 1))
    horiz = cv2.morphologyEx(bw_lines, cv2.MORPH_OPEN, kernel_h)
    cnts_h, _ = cv2.findContours(horiz, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cnts_h:
        x, y, w, h = cv2.boundingRect(c)
        if h <= 6 and w >= W * 0.30:
            zonas.append(Zona(
                tipo="filete",
                x0=round(x / W, 3), y0=round(y / H, 3),
                x1=round((x + w) / W, 3), y1=round((y + h) / H, 3),
                confianza=0.80,
            ))

    # Líneas verticales largas (≥ 20% del alto de página) → separadores de columna
    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, int(H * 0.20)))
    vert = cv2.morphologyEx(bw_lines, cv2.MORPH_OPEN, kernel_v)
    cnts_v, _ = cv2.findContours(vert, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cnts_v:
        x, y, w, h = cv2.boundingRect(c)
        if w <= 6 and h >= H * 0.20:
            zonas.append(Zona(
                tipo="separador_columna",
                x0=round(x / W, 3), y0=round(y / H, 3),
                x1=round((x + w) / W, 3), y1=round((y + h) / H, 3),
                confianza=0.80,
            ))

    return zonas


def _nms_boxes(
    boxes: list[tuple[int,int,int,int]],
    iou_thresh: float = 0.4,
) -> list[tuple[int,int,int,int]]:
    """Non-maximum suppression simple para (x,y,w,h)."""
    if not boxes:
        return []
    boxes = sorted(boxes, key=lambda b: b[2] * b[3], reverse=True)
    kept = []
    for box in boxes:
        x1, y1, w1, h1 = box
        merged = False
        for kb in kept:
            x2, y2, w2, h2 = kb
            ix = max(0, min(x1+w1, x2+w2) - max(x1, x2))
            iy = max(0, min(y1+h1, y2+h2) - max(y1, y2))
            inter = ix * iy
            union = w1*h1 + w2*h2 - inter
            if union > 0 and inter/union > iou_thresh:
                merged = True
                break
        if not merged:
            kept.append(box)
    return kept


PROMPT_DETECCION_DEFAULT = """Eres un experto en análisis de layout de publicaciones históricas.
Analiza esta página escaneada e identifica todas las zonas visibles.

INSTRUCCIÓN:
Devuelve las coordenadas de cada zona como fracción de la página completa.
0.0 = borde izquierdo/superior, 1.0 = borde derecho/inferior.
TODAS las coordenadas deben estar entre 0.0 y 1.0.

Tipos válidos:
{tipos_lista}

Devuelve SOLO el JSON, sin texto adicional:
{{
  "zonas": [
    {{"tipo": "cabecera", "x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 0.05}},
    {{"tipo": "foto", "x0": 0.02, "y0": 0.06, "x1": 0.55, "y1": 0.40}},
    {{"tipo": "articulo", "x0": 0.57, "y0": 0.06, "x1": 0.98, "y1": 0.70}}
  ]
}}"""

# Descripciones de los tipos base para el prompt
_DESCRIPCIONES_BASE = {
    "articulo":          "bloque de texto periodístico corrido (noticia, crónica, entrevista)",
    "titulo":            "encabezado grande de artículo (tipografía destacada)",
    "foto":              "fotografía, ilustración o grabado",
    "pie_foto":          "leyenda o caption debajo/al lado de una foto",
    "publicidad":        "aviso comercial o propaganda",
    "cabecera":          "nombre de la publicación, folio, fecha (normalmente parte superior)",
    "numero_pag":        "número de página solo",
    "colofon":           "información editorial, créditos generales",
    "indice":            "índice, sumario o tabla de contenidos",
    "filete":            "línea decorativa horizontal que separa secciones",
    "separador_columna": "línea vertical que divide columnas de texto",
}


def construir_prompt_deteccion(prompt_custom: str = "") -> str:
    """
    Construye el prompt de detección incluyendo TODOS los tipos activos:
    tipos base + tipos custom del usuario.

    Si prompt_custom está definido, lo usa directamente.
    Si no, genera el prompt con la lista completa de tipos.
    """
    if prompt_custom and prompt_custom.strip():
        return prompt_custom.strip()

    # Reunir todos los tipos activos (base + custom)
    # TIPOS_ZONA puede no estar disponible aún en el momento de importar,
    # así que lo cargamos aquí dinámicamente
    try:
        tipos_activos = dict(TIPOS_ZONA)  # copia del dict global
    except Exception:
        tipos_activos = dict(_TIPOS_ZONA_BASE)

    lineas = []
    for tipo_id, info in tipos_activos.items():
        label = info.get("label", tipo_id)
        # Usar descripción del dict base si existe, o el label del tipo como descripción
        desc = _DESCRIPCIONES_BASE.get(tipo_id, label)
        # Marcar los tipos custom para que la IA sepa que son específicos del proyecto
        es_custom = info.get("custom", False)
        sufijo = "  ★ tipo personalizado del proyecto" if es_custom else ""
        lineas.append(f'- "{tipo_id}": {desc}{sufijo}')

    tipos_lista = "\n".join(lineas)
    return PROMPT_DETECCION_DEFAULT.replace("{tipos_lista}", tipos_lista)


def detectar_zonas_claude(
    img_path: Path,
    api_key: str,
    modelo: str = "claude-opus-4-7",
    prompt_custom: str = "",
) -> list["Zona"]:
    """
    Detecta zonas en una página escaneada usando Claude Vision.
    Devuelve list[Zona] con confianza alta (0.85).
    Si prompt_custom está vacío genera el prompt dinámicamente con todos los tipos activos
    (base + custom del usuario).
    """
    import base64
    try:
        import anthropic
    except ImportError:
        return []

    # Leer y codificar imagen
    with open(img_path, "rb") as f:
        img_b64 = base64.standard_b64encode(f.read()).decode()

    # Determinar media type
    ext = img_path.suffix.lower()
    media_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                 ".png": "image/png",  ".gif": "image/gif",
                 ".webp": "image/webp"}
    media_type = media_map.get(ext, "image/png")

    prompt = construir_prompt_deteccion(prompt_custom)

    client = anthropic.Anthropic(api_key=api_key)
    try:
        resp = client.messages.create(
            model=modelo,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": img_b64,
                    }},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        raw = resp.content[0].text.strip()
        # Extraer JSON aunque haya texto extra
        import re
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if not m:
            return []
        data = json.loads(m.group())
        zonas = []
        for z in data.get("zonas", []):
            tipo = z.get("tipo", "articulo")
            if tipo not in TIPOS_ZONA:
                tipo = "articulo"
            # Clamp estricto a [0,1] — Claude a veces devuelve coords fuera de rango
            x0 = max(0.0, min(1.0, float(z.get("x0", 0))))
            y0 = max(0.0, min(1.0, float(z.get("y0", 0))))
            x1 = max(0.0, min(1.0, float(z.get("x1", 1))))
            y1 = max(0.0, min(1.0, float(z.get("y1", 1))))
            if x1 <= x0 or y1 <= y0:
                continue  # zona degenerada, ignorar
            zonas.append(Zona(
                tipo=tipo, x0=x0, y0=y0, x1=x1, y1=y1, confianza=0.85,
            ))
        return zonas
    except Exception:
        return []


# ── Proveedores de visión disponibles ────────────────────────────────────────

VISION_PROVEEDORES = {
    "claude": {
        "label":   "Claude (Anthropic)",
        "modelos": ["claude-sonnet-4-6", "claude-opus-4-8", "claude-haiku-4-5-20251001"],
        "default": "claude-sonnet-4-6",
        "help":    "El más preciso para layout histórico. Entiende contexto editorial.",
    },
    "openai": {
        "label":   "GPT-4o (OpenAI)",
        "modelos": ["gpt-4o", "gpt-4o-mini"],
        "default": "gpt-4o-mini",
        "help":    "Muy buena calidad. gpt-4o-mini es económico (~$0.003/pág).",
    },
    "gemini": {
        "label":   "Gemini (Google)",
        "modelos": ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"],
        "default": "gemini-1.5-flash",
        "help":    "Muy económico. Flash es casi gratuito en el tier libre.",
    },
    "ollama": {
        "label":   "Ollama (local, sin internet)",
        "modelos": ["llava", "llava-phi3", "llava-llama3", "minicpm-v"],
        "default": "llava",
        "help":    "Gratis, 100% local. Requiere Ollama corriendo en localhost:11434.",
    },
}


def _encode_imagen(img_path: Path) -> tuple[str, str]:
    """Devuelve (base64, media_type) de la imagen."""
    import base64
    ext = img_path.suffix.lower()
    media_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                 ".png": "image/png",  ".gif": "image/gif",
                 ".webp": "image/webp"}
    with open(img_path, "rb") as f:
        b64 = base64.standard_b64encode(f.read()).decode()
    return b64, media_map.get(ext, "image/png")


def _parsear_zonas_json(raw: str) -> list["Zona"]:
    """Extrae zonas de una respuesta JSON cruda del LLM."""
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group())
    except Exception:
        return []
    zonas = []
    for z in data.get("zonas", []):
        tipo = z.get("tipo", "articulo")
        if tipo not in TIPOS_ZONA:
            tipo = "articulo"
        x0 = max(0.0, min(1.0, float(z.get("x0", 0))))
        y0 = max(0.0, min(1.0, float(z.get("y0", 0))))
        x1 = max(0.0, min(1.0, float(z.get("x1", 1))))
        y1 = max(0.0, min(1.0, float(z.get("y1", 1))))
        if x1 <= x0 or y1 <= y0:
            continue
        zonas.append(Zona(tipo=tipo, x0=x0, y0=y0, x1=x1, y1=y1, confianza=0.85))
    return zonas


def detectar_zonas_vision(
    img_path: Path,
    proveedor: str,
    api_key: str,
    modelo: str = "",
    prompt_custom: str = "",
) -> list["Zona"]:
    """
    Detecta zonas de layout usando cualquier proveedor de visión IA.

    Args:
        img_path:     Ruta a la imagen de la página.
        proveedor:    "claude" | "openai" | "gemini" | "ollama"
        api_key:      Clave API del proveedor (vacía para ollama).
        modelo:       Modelo específico. Si vacío usa el default del proveedor.
        prompt_custom: Prompt personalizado. Si vacío genera dinámicamente con tipos activos.

    Returns:
        list[Zona]
    """
    prompt = construir_prompt_deteccion(prompt_custom)
    info   = VISION_PROVEEDORES.get(proveedor, {})
    if not modelo:
        modelo = info.get("default", "")

    if proveedor == "claude":
        return _vision_claude(img_path, api_key, modelo, prompt)
    elif proveedor == "openai":
        return _vision_openai(img_path, api_key, modelo, prompt)
    elif proveedor == "gemini":
        return _vision_gemini(img_path, api_key, modelo, prompt)
    elif proveedor == "ollama":
        return _vision_ollama(img_path, modelo, prompt)
    return []


def _vision_claude(img_path: Path, api_key: str, modelo: str, prompt: str) -> list["Zona"]:
    try:
        import anthropic
        b64, mt = _encode_imagen(img_path)
        client  = anthropic.Anthropic(api_key=api_key)
        resp    = client.messages.create(
            model=modelo, max_tokens=1024,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                                              "media_type": mt, "data": b64}},
                {"type": "text", "text": prompt},
            ]}],
        )
        return _parsear_zonas_json(resp.content[0].text)
    except Exception:
        return []


def _vision_openai(img_path: Path, api_key: str, modelo: str, prompt: str) -> list["Zona"]:
    try:
        import openai
        b64, mt = _encode_imagen(img_path)
        client  = openai.OpenAI(api_key=api_key)
        resp    = client.chat.completions.create(
            model=modelo, max_tokens=1024,
            messages=[{"role": "user", "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:{mt};base64,{b64}"}},
                {"type": "text", "text": prompt},
            ]}],
        )
        return _parsear_zonas_json(resp.choices[0].message.content)
    except Exception:
        return []


def _vision_gemini(img_path: Path, api_key: str, modelo: str, prompt: str) -> list["Zona"]:
    try:
        import google.generativeai as genai
        from PIL import Image as _Img
        genai.configure(api_key=api_key)
        gm   = genai.GenerativeModel(modelo)
        img  = _Img.open(img_path)
        resp = gm.generate_content([prompt, img])
        return _parsear_zonas_json(resp.text)
    except Exception:
        return []


def _vision_ollama(img_path: Path, modelo: str, prompt: str) -> list["Zona"]:
    try:
        import requests, base64
        b64, _ = _encode_imagen(img_path)
        resp = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": modelo, "prompt": prompt,
                  "images": [b64], "stream": False},
            timeout=120,
        )
        raw = resp.json().get("response", "")
        return _parsear_zonas_json(raw)
    except Exception:
        return []


# ── Tipos de zona base (siempre disponibles) ──────────────────────────────────
_TIPOS_ZONA_BASE = {
    "articulo":           {"label": "Artículo",          "color": "#22AA22", "ocr": True},
    "titulo":             {"label": "Título",             "color": "#0066FF", "ocr": True},
    "publicidad":         {"label": "Publicidad",         "color": "#CC2222", "ocr": False},
    "foto":               {"label": "Fotografía",         "color": "#CC2222", "ocr": False},
    "pie_foto":           {"label": "Pie de foto",        "color": "#FF8800", "ocr": True},
    "numero_pag":         {"label": "N.º de página",      "color": "#888888", "ocr": False},
    "cabecera":           {"label": "Cabecera",           "color": "#8855BB", "ocr": False},
    "indice":             {"label": "Índice",             "color": "#0099CC", "ocr": True},
    "colofon":            {"label": "Colofón",            "color": "#CC6688", "ocr": False},
    "filete":             {"label": "Filete",             "color": "#AAAAAA", "ocr": False},
    "separador_columna":  {"label": "Sep. columna",       "color": "#AAAAAA", "ocr": False},
}

TIPO_DEFAULT = "articulo"

# ── Tipos custom — se cargan desde ~/.bashkar/tipos_zona.json ─────────────────
import json as _json
from pathlib import Path as _Path

_TIPOS_CUSTOM_PATH = _Path.home() / ".bashkar" / "tipos_zona.json"


def _cargar_tipos_custom() -> dict:
    """Carga tipos de zona definidos por el usuario."""
    if not _TIPOS_CUSTOM_PATH.exists():
        return {}
    try:
        return _json.loads(_TIPOS_CUSTOM_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _guardar_tipos_custom(tipos_custom: dict):
    """Guarda tipos de zona del usuario en disco."""
    _TIPOS_CUSTOM_PATH.parent.mkdir(parents=True, exist_ok=True)
    _TIPOS_CUSTOM_PATH.write_text(
        _json.dumps(tipos_custom, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def agregar_tipo_zona(id_tipo: str, label: str, color: str, ocr: bool = True):
    """
    Agrega un tipo de zona custom global (disponible en todos los proyectos).
    id_tipo: clave interna única (ej: "titulo_arte")
    label:   etiqueta visible (ej: "Título Arte")
    color:   hex color (ej: "#FF6B35")
    ocr:     True si esta zona debe procesarse con OCR
    """
    custom = _cargar_tipos_custom()
    custom[id_tipo] = {"label": label, "color": color, "ocr": ocr, "custom": True}
    _guardar_tipos_custom(custom)
    # Actualizar TIPOS_ZONA en memoria
    TIPOS_ZONA[id_tipo] = {"label": label, "color": color, "ocr": ocr, "custom": True}


def eliminar_tipo_zona(id_tipo: str):
    """Elimina un tipo de zona custom (no puede eliminar los base)."""
    if id_tipo in _TIPOS_ZONA_BASE:
        raise ValueError(f"No se puede eliminar el tipo base '{id_tipo}'")
    custom = _cargar_tipos_custom()
    custom.pop(id_tipo, None)
    _guardar_tipos_custom(custom)
    TIPOS_ZONA.pop(id_tipo, None)


# TIPOS_ZONA = base + custom (se construye al importar)
TIPOS_ZONA: dict = {**_TIPOS_ZONA_BASE, **_cargar_tipos_custom()}


@dataclass
class Zona:
    """Rectángulo etiquetado en coordenadas normalizadas (0.0–1.0)."""
    tipo: str          # clave de TIPOS_ZONA
    x0: float          # izquierda (relativa al ancho de página)
    y0: float          # arriba (relativa al alto de página)
    x1: float          # derecha
    y1: float          # abajo
    confianza: float = 1.0   # 1.0 = manual, <1.0 = predicción
    notas: str = ""
    orden: int = 0     # orden de lectura (1..n); 0 = sin asignar

    def area(self) -> float:
        return max(0.0, (self.x1 - self.x0) * (self.y1 - self.y0))

    def solapamiento(self, otra: "Zona") -> float:
        ix0 = max(self.x0, otra.x0)
        iy0 = max(self.y0, otra.y0)
        ix1 = min(self.x1, otra.x1)
        iy1 = min(self.y1, otra.y1)
        if ix1 <= ix0 or iy1 <= iy0:
            return 0.0
        inter = (ix1 - ix0) * (iy1 - iy0)
        union = self.area() + otra.area() - inter
        return inter / union if union > 0 else 0.0

    def a_pixeles(self, ancho_px: int, alto_px: int) -> tuple[int, int, int, int]:
        return (
            int(self.x0 * ancho_px),
            int(self.y0 * alto_px),
            int(self.x1 * ancho_px),
            int(self.y1 * alto_px),
        )

    @staticmethod
    def desde_pixeles(x0: int, y0: int, x1: int, y1: int,
                      ancho_px: int, alto_px: int,
                      tipo: str = TIPO_DEFAULT) -> "Zona":
        return Zona(
            tipo=tipo,
            x0=min(x0, x1) / ancho_px,
            y0=min(y0, y1) / alto_px,
            x1=max(x0, x1) / ancho_px,
            y1=max(y0, y1) / alto_px,
        )


@dataclass
class PaginaEtiquetada:
    """Conjunto de zonas para una página."""
    pagina: str          # ej. "p0001"
    ancho_px: int        # dimensiones originales de la imagen
    alto_px: int
    zonas: list[Zona] = field(default_factory=list)
    manual: bool = True  # False si fue predicha automáticamente

    def zonas_ocr(self) -> list[Zona]:
        """Devuelve solo las zonas que deben procesarse con OCR."""
        return [z for z in self.zonas if TIPOS_ZONA.get(z.tipo, {}).get("ocr", True)]

    def zonas_ignorar(self) -> list[Zona]:
        return [z for z in self.zonas if not TIPOS_ZONA.get(z.tipo, {}).get("ocr", True)]

    def to_dict(self) -> dict:
        return {
            "pagina": self.pagina,
            "ancho_px": self.ancho_px,
            "alto_px": self.alto_px,
            "manual": self.manual,
            "zonas": [asdict(z) for z in self.zonas],
        }

    @staticmethod
    def from_dict(d: dict) -> "PaginaEtiquetada":
        zonas = [Zona(**z) for z in d.get("zonas", [])]
        return PaginaEtiquetada(
            pagina=d["pagina"],
            ancho_px=d.get("ancho_px", 1000),
            alto_px=d.get("alto_px", 1400),
            zonas=zonas,
            manual=d.get("manual", True),
        )


# ── Orden de lectura y operaciones de zona ────────────────────────────────────

def calcular_orden_lectura(zonas: list[Zona], ancho_completo: float = 0.62) -> None:
    """
    Asigna z.orden (1..n) según el orden de lectura natural de prensa:
    las zonas de ancho completo (títulos, cabeceras que cruzan la página)
    dividen la página en bandas horizontales; dentro de cada banda las
    columnas se leen de izquierda a derecha, y cada columna de arriba abajo.

    Solo numera zonas procesables por OCR; el resto queda con orden=0.
    Modifica las zonas in place.
    """
    for z in zonas:
        z.orden = 0
    legibles = [z for z in zonas
                if TIPOS_ZONA.get(z.tipo, {}).get("ocr", True)]
    if not legibles:
        return

    anchas = sorted((z for z in legibles if (z.x1 - z.x0) >= ancho_completo),
                    key=lambda z: z.y0)
    angostas = [z for z in legibles if (z.x1 - z.x0) < ancho_completo]

    # Fronteras de banda: el centro vertical de cada zona ancha
    bordes = [0.0]
    for z in anchas:
        bordes.append(max(bordes[-1], (z.y0 + z.y1) / 2))
    bordes.append(1.01)

    def banda_de(z: Zona) -> int:
        yc = (z.y0 + z.y1) / 2
        for k in range(len(bordes) - 1):
            if bordes[k] <= yc < bordes[k + 1]:
                return k
        return len(bordes) - 2

    por_banda: dict[int, list[Zona]] = {}
    for z in angostas:
        por_banda.setdefault(banda_de(z), []).append(z)

    secuencia: list[Zona] = []
    for k in range(len(bordes) - 1):
        if k > 0:
            secuencia.append(anchas[k - 1])
        zs = por_banda.get(k, [])
        # Agrupar en columnas por solapamiento de intervalos X
        columnas: list[dict] = []
        for z in sorted(zs, key=lambda z: z.x0):
            colocada = False
            for col in columnas:
                solape = min(col["x1"], z.x1) - max(col["x0"], z.x0)
                ancho_min = min(col["x1"] - col["x0"], z.x1 - z.x0)
                if ancho_min > 0 and solape / ancho_min > 0.4:
                    col["zonas"].append(z)
                    col["x0"] = min(col["x0"], z.x0)
                    col["x1"] = max(col["x1"], z.x1)
                    colocada = True
                    break
            if not colocada:
                columnas.append({"x0": z.x0, "x1": z.x1, "zonas": [z]})
        columnas.sort(key=lambda c: c["x0"])
        for col in columnas:
            secuencia.extend(sorted(col["zonas"], key=lambda z: z.y0))

    for n, z in enumerate(secuencia, start=1):
        z.orden = n


def dividir_zona(zona: Zona, eje: str = "h", frac: float = 0.5) -> tuple[Zona, Zona]:
    """
    Divide una zona en dos por el eje indicado.
    eje="h" → corte horizontal (una zona arriba, otra abajo)
    eje="v" → corte vertical (una zona a la izquierda, otra a la derecha)
    frac: posición del corte como fracción del tamaño de la zona (0.05–0.95).
    """
    frac = max(0.05, min(0.95, frac))
    if eje == "v":
        corte = zona.x0 + (zona.x1 - zona.x0) * frac
        a = Zona(tipo=zona.tipo, x0=zona.x0, y0=zona.y0, x1=corte, y1=zona.y1,
                 confianza=zona.confianza, notas=zona.notas)
        b = Zona(tipo=zona.tipo, x0=corte, y0=zona.y0, x1=zona.x1, y1=zona.y1,
                 confianza=zona.confianza, notas=zona.notas)
    else:
        corte = zona.y0 + (zona.y1 - zona.y0) * frac
        a = Zona(tipo=zona.tipo, x0=zona.x0, y0=zona.y0, x1=zona.x1, y1=corte,
                 confianza=zona.confianza, notas=zona.notas)
        b = Zona(tipo=zona.tipo, x0=zona.x0, y0=corte, x1=zona.x1, y1=zona.y1,
                 confianza=zona.confianza, notas=zona.notas)
    return a, b


def fusionar_zonas(zonas: list[Zona]) -> Zona:
    """
    Fusiona varias zonas en una sola que las engloba (bounding box).
    El tipo resultante es el de la zona de mayor área.
    """
    if not zonas:
        raise ValueError("No hay zonas para fusionar")
    mayor = max(zonas, key=lambda z: z.area())
    return Zona(
        tipo=mayor.tipo,
        x0=min(z.x0 for z in zonas),
        y0=min(z.y0 for z in zonas),
        x1=max(z.x1 for z in zonas),
        y1=max(z.y1 for z in zonas),
        confianza=min(z.confianza for z in zonas),
        notas=mayor.notas,
    )


# ── Persistencia ──────────────────────────────────────────────────────────────

def ruta_etiquetas(out_dir: Path, numero: str, pagina: str) -> Path:
    d = out_dir / "05_etiquetas" / numero
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{pagina}.json"


def guardar_pagina(out_dir: Path, numero: str, pag: PaginaEtiquetada):
    ruta = ruta_etiquetas(out_dir, numero, pag.pagina)
    ruta.write_text(json.dumps(pag.to_dict(), ensure_ascii=False, indent=2),
                    encoding="utf-8")


def cargar_pagina(out_dir: Path, numero: str, pagina: str) -> Optional[PaginaEtiquetada]:
    ruta = ruta_etiquetas(out_dir, numero, pagina)
    if not ruta.exists():
        return None
    try:
        return PaginaEtiquetada.from_dict(json.loads(ruta.read_text("utf-8")))
    except Exception:
        return None


def listar_paginas_etiquetadas(out_dir: Path, numero: str) -> list[str]:
    d = out_dir / "05_etiquetas" / numero
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.json"))


def cargar_todas_manual(out_dir: Path, numero: str) -> list[PaginaEtiquetada]:
    paginas = []
    for p in listar_paginas_etiquetadas(out_dir, numero):
        pg = cargar_pagina(out_dir, numero, p)
        if pg and pg.manual:
            paginas.append(pg)
    return paginas


# ── Detector / Entrenador ─────────────────────────────────────────────────────

class DetectorZonas:
    """
    Aprende la disposición típica de zonas a partir de páginas etiquetadas manualmente.
    Usa estadísticas simples de posición y tamaño para predecir zonas en páginas nuevas.

    Para cada tipo de zona aprende:
    - Bbox medio (x0, y0, x1, y1) normalizado
    - Desviación estándar de cada coordenada
    - Frecuencia de aparición (% de páginas donde aparece)
    """

    def __init__(self):
        self._patrones: dict[str, list[dict]] = {}   # tipo → lista de bbox dicts
        self._n_paginas = 0
        self._entrenado = False

    def entrenar(self, paginas: list[PaginaEtiquetada]) -> dict:
        """
        Entrena con las páginas etiquetadas manualmente.
        Retorna estadísticas del entrenamiento.
        """
        self._patrones = {}
        self._n_paginas = len(paginas)

        for pag in paginas:
            for z in pag.zonas:
                if z.tipo not in self._patrones:
                    self._patrones[z.tipo] = []
                self._patrones[z.tipo].append({
                    "x0": z.x0, "y0": z.y0, "x1": z.x1, "y1": z.y1
                })

        self._entrenado = bool(self._patrones)
        return self._estadisticas_entrenamiento()

    def _estadisticas_entrenamiento(self) -> dict:
        stats = {"n_paginas": self._n_paginas, "tipos": {}}
        for tipo, muestras in self._patrones.items():
            n = len(muestras)
            stats["tipos"][tipo] = {
                "n_muestras": n,
                "frecuencia": round(n / max(self._n_paginas, 1), 2),
                "bbox_medio": {
                    k: round(statistics.mean(m[k] for m in muestras), 3)
                    for k in ("x0", "y0", "x1", "y1")
                },
            }
            if n >= 2:
                stats["tipos"][tipo]["bbox_std"] = {
                    k: round(statistics.stdev(m[k] for m in muestras), 3)
                    for k in ("x0", "y0", "x1", "y1")
                }
        return stats

    def predecir(self, pagina: str, ancho_px: int, alto_px: int,
                 umbral_frecuencia: float = 0.4) -> PaginaEtiquetada:
        """
        Predice las zonas de una página nueva basándose en el entrenamiento.
        Solo incluye tipos que aparecen en ≥ umbral_frecuencia de las páginas.
        """
        zonas_pred = []

        for tipo, muestras in self._patrones.items():
            n = len(muestras)
            frecuencia = n / max(self._n_paginas, 1)
            if frecuencia < umbral_frecuencia:
                continue

            # Bbox medio
            x0_m = statistics.mean(m["x0"] for m in muestras)
            y0_m = statistics.mean(m["y0"] for m in muestras)
            x1_m = statistics.mean(m["x1"] for m in muestras)
            y1_m = statistics.mean(m["y1"] for m in muestras)

            # Confianza: más muestras y menos varianza = más confianza
            if n >= 3:
                std_total = sum(
                    statistics.stdev(m[k] for m in muestras)
                    for k in ("x0", "y0", "x1", "y1")
                ) / 4
                confianza = max(0.4, min(0.95, 1.0 - std_total * 3))
            else:
                confianza = 0.5 + (frecuencia * 0.3)

            zonas_pred.append(Zona(
                tipo=tipo,
                x0=round(x0_m, 3), y0=round(y0_m, 3),
                x1=round(x1_m, 3), y1=round(y1_m, 3),
                confianza=round(confianza, 2),
            ))

        return PaginaEtiquetada(
            pagina=pagina,
            ancho_px=ancho_px,
            alto_px=alto_px,
            zonas=zonas_pred,
            manual=False,
        )

    def aplicar_a_numero(
        self,
        out_dir: Path,
        numero: str,
        paginas_disponibles: list[str],
        paginas_ya_etiquetadas: list[str],
        ancho_px: int = 1000,
        alto_px: int = 1400,
        umbral_frecuencia: float = 0.4,
        callback=None,
    ) -> int:
        """
        Aplica la plantilla aprendida a todas las páginas no etiquetadas del número.
        Retorna cantidad de páginas predichas.
        """
        if not self._entrenado:
            return 0

        predichas = 0
        etiquetadas_set = set(paginas_ya_etiquetadas)

        for i, pagina in enumerate(paginas_disponibles):
            if pagina in etiquetadas_set:
                continue
            pred = self.predecir(pagina, ancho_px, alto_px, umbral_frecuencia)
            guardar_pagina(out_dir, numero, pred)
            predichas += 1
            if callback:
                callback(i, len(paginas_disponibles), pagina)

        return predichas

    def esta_entrenado(self) -> bool:
        return self._entrenado

    def n_paginas_entrenamiento(self) -> int:
        return self._n_paginas


# ── Extracción de texto con zonas ──────────────────────────────────────────────

def aplicar_zonas_a_texto(
    texto_pagina: str,
    zonas_ocr: list[Zona],
    zonas_ignorar: list[Zona],
) -> str:
    """
    Filtra el texto OCR de una página según las zonas etiquetadas.

    Estrategia heurística: el texto OCR de la BNC es una secuencia lineal,
    no tiene coordenadas. Las zonas se usan para:
    1. Eliminar líneas que corresponden a zonas "ignorar" (por posición vertical)
    2. Las zonas_ocr definen qué fracción vertical de la página conservar

    Si no hay zonas, devuelve el texto completo.
    """
    if not zonas_ignorar and not zonas_ocr:
        return texto_pagina

    lineas = texto_pagina.split('\n')
    n = len(lineas)
    if n == 0:
        return texto_pagina

    resultado = []
    for i, linea in enumerate(lineas):
        pos_rel = i / n   # posición relativa vertical 0.0–1.0

        # ¿Cae en zona ignorar?
        en_ignorar = any(
            z.y0 <= pos_rel <= z.y1
            for z in zonas_ignorar
        )
        if en_ignorar:
            continue

        # Si hay zonas OCR definidas, solo incluir lo que cae en ellas
        if zonas_ocr:
            en_ocr = any(
                z.y0 <= pos_rel <= z.y1
                for z in zonas_ocr
            )
            if not en_ocr:
                continue

        resultado.append(linea)

    return '\n'.join(resultado)


def filtrar_texto_con_etiquetas(
    out_dir: Path,
    numero: str,
    pagina: str,
    texto_original: str,
) -> str:
    """
    Aplica las etiquetas guardadas de una página al texto OCR.
    Si no hay etiquetas, devuelve el texto sin modificar.
    """
    pag = cargar_pagina(out_dir, numero, pagina)
    if pag is None or not pag.zonas:
        return texto_original

    zonas_ocr = pag.zonas_ocr()
    zonas_ignorar = pag.zonas_ignorar()

    return aplicar_zonas_a_texto(texto_original, zonas_ocr, zonas_ignorar)
