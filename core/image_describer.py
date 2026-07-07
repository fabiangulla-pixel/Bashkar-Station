"""
core/image_describer.py — Descripción automática de imágenes con IA.

Proveedores soportados:
  · Anthropic (Claude)        — clave empieza por "sk-ant-"
  · OpenAI   (GPT-4o)         — clave empieza por "sk-"
  · Google   (Gemini 1.5 Flash) — clave empieza por "AIza"

Sin clave API el análisis OpenCV funciona igualmente.
"""

import base64, json, gc, urllib.request, urllib.error
from pathlib import Path
from typing import Optional


# ── Prompts ───────────────────────────────────────────────────────────────────
_SYSTEM = (
    "Eres un experto en análisis de prensa histórica hispanoamericana "
    "de la primera mitad del siglo XX. Analizas imágenes recortadas de "
    "páginas de revistas y periódicos digitalizados. Respondes SIEMPRE "
    "en español y SOLO con JSON válido, sin texto adicional ni backticks."
)

_PROMPT = (
    'Analiza este elemento visual extraído de una página de revista histórica.\n\n'
    'Responde EXCLUSIVAMENTE con este JSON (sin texto fuera del JSON):\n'
    '{\n'
    '  "tipo": "fotografía" | "ilustración" | "caricatura" | "publicidad" | "viñeta" | "decorativo" | "texto" | "mixto",\n'
    '  "confianza_tipo": 0.0-1.0,\n'
    '  "descripcion": "descripción detallada del contenido visual en 1-3 oraciones",\n'
    '  "personas": {\n'
    '    "total": 0,\n'
    '    "hombres_estimados": 0,\n'
    '    "mujeres_estimadas": 0,\n'
    '    "descripcion_personas": "breve descripción si las hay, vacío si no"\n'
    '  },\n'
    '  "texto_visible": "texto legible en la imagen. Vacío si no hay.",\n'
    '  "autor_firma": "nombre del autor/ilustrador si está firmado, vacío si no",\n'
    '  "tematica": ["lista","de","keywords"],\n'
    '  "calidad_imagen": "buena",\n'
    '  "notas": "observaciones relevantes para investigación histórica"\n'
    '}'
)


# ── Detección de proveedor ────────────────────────────────────────────────────

def detectar_proveedor(api_key: str) -> str:
    k = api_key.strip()
    if k.startswith("AIza"):           return "gemini"
    if k.startswith("sk-ant-"):        return "anthropic"
    if k.startswith("sk-"):            return "openai"
    if k.lower().startswith("gemini:"): return "gemini"
    if k.lower().startswith("anthropic:"): return "anthropic"
    if k.lower().startswith("openai:"): return "openai"
    return "anthropic"


def nombre_proveedor(api_key: str) -> str:
    return {"anthropic": "Anthropic Claude",
            "openai":    "OpenAI GPT-4o",
            "gemini":    "Google Gemini 1.5 Flash"
            }.get(detectar_proveedor(api_key), "IA")


# ── Recorte ───────────────────────────────────────────────────────────────────

def _recortar_elemento(img_path: Path, x: int, y: int, w: int, h: int,
                        margen: int = 5) -> Optional[bytes]:
    try:
        import cv2
        img = cv2.imread(str(img_path))
        if img is None: return None
        ih, iw = img.shape[:2]
        recorte = img[max(0,y-margen):min(ih,y+h+margen),
                      max(0,x-margen):min(iw,x+w+margen)]
        if recorte.size == 0: return None
        _, buf = cv2.imencode(".png", recorte, [cv2.IMWRITE_PNG_COMPRESSION, 6])
        return buf.tobytes()
    except Exception:
        return None


def _limpiar_json(texto: str) -> dict:
    t = texto.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(t.strip())


def _post(url: str, payload: bytes, headers: dict, timeout: int) -> bytes:
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ── Llamadas por proveedor ────────────────────────────────────────────────────

def _llamar_anthropic(img_b64: str, api_key: str, timeout: int = 30) -> dict:
    payload = json.dumps({
        "model": "claude-sonnet-4-20250514", "max_tokens": 600,
        "system": _SYSTEM,
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64",
             "media_type": "image/png", "data": img_b64}},
            {"type": "text", "text": _PROMPT},
        ]}],
    }).encode("utf-8")
    data = json.loads(_post("https://api.anthropic.com/v1/messages", payload,
        {"Content-Type": "application/json", "x-api-key": api_key,
         "anthropic-version": "2023-06-01"}, timeout))
    return _limpiar_json(data["content"][0]["text"])


def _llamar_openai(img_b64: str, api_key: str, timeout: int = 30) -> dict:
    payload = json.dumps({
        "model": "gpt-4o", "max_tokens": 600,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": [
                {"type": "image_url",
                 "image_url": {"url": "data:image/png;base64," + img_b64, "detail": "low"}},
                {"type": "text", "text": _PROMPT},
            ]},
        ],
    }).encode("utf-8")
    data = json.loads(_post("https://api.openai.com/v1/chat/completions", payload,
        {"Content-Type": "application/json", "Authorization": "Bearer " + api_key}, timeout))
    return _limpiar_json(data["choices"][0]["message"]["content"])


def _llamar_gemini(img_b64: str, api_key: str, timeout: int = 30) -> dict:
    """Google Gemini 1.5 Flash — muy económico para análisis masivo."""
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "gemini-1.5-flash:generateContent?key=" + api_key)
    payload = json.dumps({
        "contents": [{"parts": [
            {"inline_data": {"mime_type": "image/png", "data": img_b64}},
            {"text": _SYSTEM + "\n\n" + _PROMPT},
        ]}],
        "generationConfig": {"maxOutputTokens": 600, "temperature": 0.1},
    }).encode("utf-8")
    data = json.loads(_post(url, payload, {"Content-Type": "application/json"}, timeout))
    texto = data["candidates"][0]["content"]["parts"][0]["text"]
    return _limpiar_json(texto)


# ── Función principal ─────────────────────────────────────────────────────────

def describir_elemento(img_path: Path, elemento: dict,
                        api_key: str, timeout: int = 30) -> dict:
    x = elemento.get("x_px", 0); y = elemento.get("y_px", 0)
    w = elemento.get("w_px", 50); h = elemento.get("h_px", 50)
    if w < 40 or h < 40: return elemento
    if elemento.get("tipo") in ("Elemento decorativo", "Bloque de texto"):
        return elemento

    img_bytes = _recortar_elemento(img_path, x, y, w, h)
    if not img_bytes: return elemento
    img_b64 = base64.standard_b64encode(img_bytes).decode("utf-8")

    proveedor = detectar_proveedor(api_key)
    try:
        if proveedor == "gemini":
            desc = _llamar_gemini(img_b64, api_key, timeout)
        elif proveedor == "openai":
            desc = _llamar_openai(img_b64, api_key, timeout)
        else:
            desc = _llamar_anthropic(img_b64, api_key, timeout)

        elemento = dict(elemento)
        elemento["tipo_ai"]         = desc.get("tipo", "")
        elemento["descripcion_ai"]  = desc.get("descripcion", "")
        elemento["personas"]        = desc.get("personas", {})
        elemento["texto_visible"]   = desc.get("texto_visible", "")
        elemento["autor"]           = desc.get("autor_firma", "")
        elemento["tematica_ai"]     = desc.get("tematica", [])
        elemento["calidad_imagen"]  = desc.get("calidad_imagen", "")
        elemento["notas_ai"]        = desc.get("notas", "")
        elemento["descrito_por_ai"] = True
        elemento["proveedor_ai"]    = proveedor
    except Exception as e:
        elemento["error_ai"] = f"{proveedor}: {e}"

    del img_bytes; gc.collect()
    return elemento


def describir_pagina(img_path: Path, datos_pagina: dict, api_key: str,
                      solo_tipos=None, max_elementos: int = 12,
                      callback_progreso=None) -> dict:
    if solo_tipos is None:
        solo_tipos = ["Fotografía", "Ilustración / caricatura", "Publicidad"]
    elementos  = datos_pagina.get("elementos", [])
    candidatos = [e for e in elementos
                  if e.get("tipo") in solo_tipos
                  and e.get("w_px", 0) >= 40 and e.get("h_px", 0) >= 40
                  ][:max_elementos]
    nuevos = list(elementos)
    for i, el in enumerate(candidatos):
        if callback_progreso: callback_progreso(i + 1, len(candidatos))
        idx = elementos.index(el)
        nuevos[idx] = describir_elemento(img_path, el, api_key)
    datos_pagina = dict(datos_pagina)
    datos_pagina["elementos"] = nuevos
    return datos_pagina


def describir_numero(img_dir: Path, datos_paginas: list, api_key: str,
                      callback_progreso=None, max_por_pagina: int = 8) -> list:
    resultados = []
    for i, pag in enumerate(datos_paginas):
        pid      = pag.get("pagina", f"p{i+1:04d}")
        img_path = img_dir / f"{pid}.png"
        if not img_path.exists():
            resultados.append(pag); continue
        if callback_progreso: callback_progreso(i + 1, len(datos_paginas), pid)
        resultados.append(describir_pagina(img_path, pag, api_key,
                                            max_elementos=max_por_pagina))
    return resultados
