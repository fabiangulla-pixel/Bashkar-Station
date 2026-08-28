"""core/ocr_llm.py — Mejora de OCR con LLM Vision/texto para páginas de baja calidad.

Diseño:
  - No reemplaza el pipeline Tesseract existente.
  - Se activa SOLO para páginas con confianza < umbral (defecto: 60).
  - Dos modos:
      1. Vision:    imagen → LLM Vision → texto transcrito
      2. Corrección: texto_tesseract → LLM texto → texto corregido
  - Preserva ortografía arcaica legítima de la época.
  - Proveedores: claude (default) | openai | gemini | ollama | lmstudio
  - Se integra en app.py como botón "Mejorar con IA" en la pestaña OCR.
"""

from __future__ import annotations

import base64
import gc
import json
import re
import threading
from pathlib import Path
from typing import Callable

# ── Acumulador de `usage` real ────────────────────────────────────────────────
# Estándar de costo IA: tras un lote se mide el costo REAL leyendo el `usage` que
# devuelve el proveedor. Claude y OpenAI lo traen en la respuesta; lo recogemos
# aquí sin cambiar las firmas públicas. mejorar_lote() lo resetea al empezar y lo
# lee al terminar. Protegido con lock por si se llama desde varios hilos.
_USAGES: list = []
_USAGES_LOCK = threading.Lock()


def _registrar_usage(obj) -> None:
    """Acumula el `usage` de una respuesta de Claude/OpenAI (si lo trae)."""
    _registrar_usage_valor(getattr(obj, "usage", None))


def _registrar_usage_valor(usage) -> None:
    """Como `_registrar_usage`, pero recibe el `usage` ya extraído (p. ej.
    desde `inference_provider.ProviderResponse.usage`) en vez del objeto
    respuesta completo del SDK."""
    if usage is not None:
        with _USAGES_LOCK:
            _USAGES.append(usage)


def reset_usages() -> None:
    with _USAGES_LOCK:
        _USAGES.clear()


def usages() -> list:
    with _USAGES_LOCK:
        return list(_USAGES)


# ── Modelos ──────────────────────────────────────────────────────────────────
_MODELO_VISION  = "claude-sonnet-4-6"
_MODELO_TEXTO   = "claude-haiku-4-5-20251001"   # más barato para corrección de texto

# ── Umbrales ─────────────────────────────────────────────────────────────────
UMBRAL_CONFIANZA_DEFAULT = 60   # páginas con conf < este valor se reenvían al LLM
MAX_CHARS_CORRECCION     = 6000  # no enviar más de esto al LLM de corrección


# ── Prompts ──────────────────────────────────────────────────────────────────
_PROMPT_VISION = """\
Eres un paleógrafo especializado en prensa colombiana de los años 1930-1940.

Transcribe con exactitud el texto de esta página de la revista *Estampa*.

Reglas:
- Conserva la estructura de párrafos con saltos de línea reales
- Mantén ortografía y puntuación de época (no modernices: "habia", "fué", etc.)
- Si una palabra es ilegible, escribe [ilegible]
- Marca cambios de columna con: --- COLUMNA ---
- No agregues comentarios ni explicaciones, solo el texto transcrito
"""

_PROMPT_CORRECCION = """\
Eres un editor especializado en textos históricos colombianos de los años 1930-1940.

Este texto viene de OCR (Tesseract) sobre una página impresa de época. Puede tener:
- Caracteres rotos o confundidos (rn→m, li→h, 0→o, 1→l, etc.)
- Palabras partidas incorrectamente por salto de línea
- Espacios faltantes entre palabras pegadas
- Signos de puntuación mal interpretados

Tu tarea: corregir SOLO errores de digitalización.
NO debes:
- Modernizar ortografía arcaica legítima (habia, fuése, á, etc.)
- Cambiar puntuación de época
- Alterar nombres propios históricos
- Reordenar el texto
- Agregar información que no está en el original

Devuelve únicamente el texto corregido, sin explicaciones ni comentarios.

Texto OCR a corregir:
{texto}
"""

_PROMPT_EVALUAR = """\
Evalúa brevemente la calidad de este texto OCR de prensa histórica colombiana (1930-1940).

Responde ÚNICAMENTE con JSON válido:
{
  "calidad": "buena|regular|mala",
  "problemas_detectados": ["lista", "de", "problemas"],
  "confianza_estimada": 0-100,
  "recomendacion": "usar_directo|corregir_texto|rehacer_vision"
}

Texto:
{texto}
"""


# ── Clientes por proveedor ───────────────────────────────────────────────────

def _cliente_claude(api_key: str):
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key)
    except ImportError as e:
        raise ImportError("Instala anthropic: pip install anthropic>=0.25.0") from e


def _cliente_openai(api_key: str):
    try:
        import openai
        return openai.OpenAI(api_key=api_key)
    except ImportError as e:
        raise ImportError("Instala openai: pip install openai>=1.0.0") from e


def _cliente_lmstudio(host: str = "http://localhost:1234"):
    """Cliente para LM Studio (servidor local, API compatible con OpenAI).
    Requiere Developer → Start Server en LM Studio con un modelo cargado.
    No necesita API key real (el servidor local no la valida)."""
    try:
        import openai
        return openai.OpenAI(base_url=f"{host}/v1", api_key="lm-studio")
    except ImportError as e:
        raise ImportError("Instala openai: pip install openai>=1.0.0") from e


def modelos_cargados_lmstudio(host: str = "http://localhost:1234") -> list[str]:
    """Consulta /v1/models: qué modelos tiene LM Studio cargados AHORA MISMO
    (no hay catálogo fijo que listar, depende de lo que el usuario descargó
    y cargó en su máquina). Lista vacía si el servidor no está corriendo
    (no es un error: el usuario puede no haberlo iniciado todavía)."""
    import json as _json
    import urllib.request as _urlreq
    try:
        with _urlreq.urlopen(f"{host}/v1/models", timeout=2) as resp:
            datos = _json.loads(resp.read())
        return [m["id"] for m in datos.get("data", [])]
    except Exception:
        return []


# Alias para compatibilidad interna
def _cliente(api_key: str):
    return _cliente_claude(api_key)


# ── Modo 1: Vision (imagen → texto) ──────────────────────────────────────────

def ocr_con_vision(
    img_path: Path,
    api_key: str,
    modelo: str = _MODELO_VISION,
    proveedor: str = "claude",
) -> str:
    """
    Transcribe una imagen de página usando Vision LLM.
    Proveedores: claude (default) | openai | gemini | ollama | lmstudio
    """
    img_path = Path(img_path)
    if not img_path.exists():
        raise FileNotFoundError(f"Imagen no encontrada: {img_path}")

    # Determinar media type y cargar bytes
    ext = img_path.suffix.lower()
    media_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                 ".png": "image/png",  ".tif": "image/jpeg",
                 ".tiff": "image/jpeg", ".bmp": "image/jpeg",
                 ".webp": "image/webp"}
    media_type = media_map.get(ext, "image/jpeg")

    if ext in (".tif", ".tiff", ".bmp"):
        try:
            import io

            from PIL import Image
            img = Image.open(img_path).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=92)
            img_bytes = buf.getvalue()
            media_type = "image/jpeg"
            del img
        except ImportError:
            img_bytes = img_path.read_bytes()
    else:
        img_bytes = img_path.read_bytes()

    img_b64 = base64.b64encode(img_bytes).decode()

    try:
        from core import inference_provider as _ip
        # max_tokens=8192 (default de generate_vision es 4096): con thinking
        # adaptativo, una página densa multi-columna puede agotar el
        # presupuesto pensando antes de emitir el bloque de texto
        # (stop_reason="max_tokens" sin transcripción). Visto en producción
        # con rev_estampa_feb_1939/p0057, 28-ago-2026.
        resp = _ip.generate_vision(
            proveedor, _PROMPT_VISION, img_b64, media_type,
            api_key=api_key, modelo=modelo, max_tokens=8192,
            cliente_claude=_cliente_claude, cliente_openai=_cliente_openai,
            cliente_lmstudio=_cliente_lmstudio,
            modelo_default_claude=_MODELO_VISION,
        )
        _registrar_usage_valor(resp.usage)
        return _filtrar_vision(resp.texto)

    finally:
        del img_bytes, img_b64
        gc.collect()


# ── Modo 2: Corrección posOCR de texto ────────────────────────────────────────

# Frases con que los LLM inician rechazos o meta-comentarios en vez de la
# corrección pedida. Si la respuesta empieza así, NO es texto corregido y
# guardarla contaminaría el corpus (bug observado: una respuesta "No puedo
# corregir este texto porque el OCR..." quedó almacenada como artículo).
_INICIOS_RECHAZO = (
    "no puedo", "no es posible", "lo siento", "lo lamento", "disculpa",
    "i cannot", "i can't", "i'm sorry", "i am sorry", "sorry",
    "el texto proporcionado", "este texto no", "como modelo",
    "como asistente", "no hay texto", "el ocr ha producido",
)


def _filtrar_vision(texto: str) -> str:
    """
    Si la transcripción de visión es en realidad un rechazo del modelo,
    devuelve cadena vacía (página fallida) en vez de prosa contaminante.
    """
    inicio = (texto or "").strip().lower()[:60]
    if any(inicio.startswith(p) for p in _INICIOS_RECHAZO):
        return ""
    return texto


def _es_respuesta_invalida(corregido: str, original: str) -> bool:
    """
    True si la respuesta del LLM no es una corrección del texto sino un
    rechazo o comentario meta. En ese caso debe conservarse el original.
    """
    if not corregido:
        return True
    inicio = corregido.strip().lower()[:60]
    if any(inicio.startswith(p) for p in _INICIOS_RECHAZO):
        return True
    # Una "corrección" drásticamente más corta que un original largo
    # tampoco es creíble (el modelo resumió o se negó a mitad de camino).
    if len(original) > 800 and len(corregido) < len(original) * 0.25:
        return True
    return False


def corregir_texto(
    texto_ocr: str,
    api_key: str,
    modelo: str = _MODELO_TEXTO,
    proveedor: str = "claude",
) -> str:
    """
    Corrige artefactos OCR en texto ya extraído por Tesseract.
    Preserva ortografía arcaica legítima de época.
    Proveedores: claude (default) | openai | gemini | ollama | lmstudio
    """
    if not texto_ocr or not texto_ocr.strip():
        return texto_ocr

    fragmento = texto_ocr[:MAX_CHARS_CORRECCION]
    resto = texto_ocr[MAX_CHARS_CORRECCION:] if len(texto_ocr) > MAX_CHARS_CORRECCION else ""
    prompt = _PROMPT_CORRECCION.replace("{texto}", fragmento)

    from core import inference_provider as _ip
    resp = _ip.generate_text(
        proveedor, prompt,
        api_key=api_key, modelo=modelo,
        cliente_claude=_cliente_claude, cliente_openai=_cliente_openai,
        cliente_lmstudio=_cliente_lmstudio,
        modelo_default_claude=_MODELO_TEXTO,
        modelo_default_openai="gpt-4o-mini",
        timeout_ollama=120,
    )
    _registrar_usage_valor(resp.usage)
    corregido = resp.texto

    # Si el LLM respondió con un rechazo o meta-comentario en lugar de la
    # corrección, conservar el texto original intacto.
    if _es_respuesta_invalida(corregido, fragmento):
        return texto_ocr

    return corregido + ("\n" + resto if resto else "")


# ── Evaluación de calidad ──────────────────────────────────────────────────────

def evaluar_calidad(
    texto_ocr: str,
    api_key: str,
    modelo: str = _MODELO_TEXTO,
) -> dict:
    """
    Pide a Claude que evalúe la calidad del texto OCR y recomiende acción.
    Retorna dict con: calidad, problemas_detectados, confianza_estimada, recomendacion.
    """
    from core import inference_provider as _ip

    muestra = texto_ocr[:2000]
    client = _cliente(api_key)
    try:
        msg = client.messages.create(
            model=modelo,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": _PROMPT_EVALUAR.replace("{texto}", muestra),
            }],
        )
        raw = _ip.texto_de_respuesta_claude(msg)
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception:
        return {
            "calidad": "desconocida",
            "problemas_detectados": [],
            "confianza_estimada": 0,
            "recomendacion": "corregir_texto",
        }


# ── Pipeline completo para una página ─────────────────────────────────────────

def mejorar_pagina(
    txt_path: Path,
    img_path: Path | None,
    api_key: str,
    umbral_confianza: float = UMBRAL_CONFIANZA_DEFAULT,
    confianza_tesseract: float | None = None,
    modo: str = "auto",
    proveedor: str = "claude",
    modelo_ollama: str = "latamgpt",
    callback: Callable[[str], None] | None = None,
) -> dict:
    """
    Mejora el OCR de una página usando un LLM.

    Parámetros:
        txt_path:            .txt producido por Tesseract (puede no existir)
        img_path:            imagen original (necesaria para modo vision)
        api_key:             clave del proveedor seleccionado
        umbral_confianza:    solo mejorar si confianza Tesseract < este valor
        confianza_tesseract: confianza reportada por Tesseract (None = siempre mejorar)
        modo:                "auto" | "vision" | "correccion"
                             auto → usa vision si img disponible y conf<30, sino correccion
        proveedor:           "claude" | "openai" | "gemini" | "ollama"
        callback:            función(mensaje) para logging

    Retorna dict:
        texto_mejorado, metodo_usado, confianza_tesseract, mejorado (bool)
    """
    def log(msg):
        if callback:
            callback(msg)

    txt_path = Path(txt_path) if txt_path else None
    texto_original = ""
    if txt_path and txt_path.exists():
        texto_original = txt_path.read_text("utf-8", errors="replace")

    # Decidir si procesar
    if confianza_tesseract is not None and confianza_tesseract >= umbral_confianza:
        return {
            "texto_mejorado": texto_original,
            "metodo_usado": "sin_cambios",
            "confianza_tesseract": confianza_tesseract,
            "mejorado": False,
        }

    # Determinar modo
    usar_vision = False
    if modo == "vision":
        usar_vision = True
    elif modo == "auto":
        muy_baja_conf = confianza_tesseract is not None and confianza_tesseract < 30
        texto_muy_corto = len(texto_original.split()) < 30
        # ollama con vision solo si modelo soporta imágenes (llava, etc.)
        usar_vision = bool(img_path and img_path.exists() and (muy_baja_conf or texto_muy_corto))

    # Ejecutar
    try:
        _es_local = proveedor in ("ollama", "lmstudio")
        if usar_vision and img_path and img_path.exists():
            _modelo_v = modelo_ollama if _es_local else None
            log(f"    🔭 Vision ({proveedor}): {img_path.name}")
            texto_mejorado = ocr_con_vision(img_path, api_key, modelo=_modelo_v, proveedor=proveedor)
            metodo = f"vision_{proveedor}"
        else:
            if not texto_original.strip():
                return {
                    "texto_mejorado": "",
                    "metodo_usado": "sin_texto",
                    "confianza_tesseract": confianza_tesseract,
                    "mejorado": False,
                }
            _modelo_c = modelo_ollama if _es_local else None
            log(f"    ✏️ Corrección ({proveedor}): {txt_path.name if txt_path else '?'}")
            texto_mejorado = corregir_texto(texto_original, api_key, modelo=_modelo_c, proveedor=proveedor)
            metodo = f"correccion_{proveedor}"

        # Persistir si hay ruta de destino
        if txt_path:
            orig = txt_path.with_suffix(".txt.orig")
            if not orig.exists() and texto_original:
                orig.write_text(texto_original, encoding="utf-8")
            txt_path.write_text(texto_mejorado, encoding="utf-8")

        return {
            "texto_mejorado": texto_mejorado,
            "metodo_usado": metodo,
            "confianza_tesseract": confianza_tesseract,
            "mejorado": True,
        }

    except Exception as e:
        log(f"    ⚠️ Error LLM ({proveedor}): {e}")
        return {
            "texto_mejorado": texto_original,
            "metodo_usado": "error",
            "confianza_tesseract": confianza_tesseract,
            "mejorado": False,
            "error": str(e),
        }


# ── Proceso por lote ───────────────────────────────────────────────────────────

def mejorar_lote(
    corpus_meta,    # DataFrame de ST.corpus_meta
    api_key: str,
    umbral_confianza: float = UMBRAL_CONFIANZA_DEFAULT,
    img_dir_raiz: Path | None = None,
    modo: str = "auto",
    proveedor: str = "claude",
    modelo_ollama: str = "latamgpt",
    callback: Callable[[int, int, str], None] | None = None,
) -> dict:
    """
    Mejora todas las páginas con baja confianza en el corpus.

    corpus_meta: DataFrame con columnas: txt_path, confianza, pagina, numero
    callback(n_actual, n_total, descripcion)

    Retorna dict con estadísticas: mejoradas, omitidas, errores, tokens_aprox
    """
    import pandas as pd

    bajas = corpus_meta[
        corpus_meta["confianza"].notna() &
        (corpus_meta["confianza"] < umbral_confianza)
    ].copy()

    total = len(bajas)
    if total == 0:
        return {"mejoradas": 0, "omitidas": len(corpus_meta), "errores": 0,
                "total_candidatas": 0}

    stats = {"mejoradas": 0, "omitidas": 0, "errores": 0, "total_candidatas": total}

    # Estándar de costo IA: medir el costo REAL del lote desde el usage del
    # proveedor. Reseteamos el acumulador al empezar este lote.
    reset_usages()

    for i, (_, row) in enumerate(bajas.iterrows(), 1):
        txt_path = Path(row["txt_path"]) if pd.notna(row.get("txt_path", "")) else None
        conf = row.get("confianza")
        nombre = f"{row.get('numero','?')} · {row.get('pagina','?')}"

        # Buscar imagen correspondiente
        img_path = None
        if img_dir_raiz:
            numero = row.get("numero", "")
            pagina = row.get("pagina", "")
            for ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
                candidata = img_dir_raiz / numero / (pagina + ext)
                if candidata.exists():
                    img_path = candidata
                    break

        if callback:
            callback(i, total, nombre)

        def _log(msg):
            if callback:
                callback(i, total, msg)

        resultado = mejorar_pagina(
            txt_path=txt_path,
            img_path=img_path,
            api_key=api_key,
            umbral_confianza=umbral_confianza,
            confianza_tesseract=float(conf) if conf is not None else None,
            modo=modo,
            proveedor=proveedor,
            modelo_ollama=modelo_ollama,
            callback=_log,
        )

        if resultado["mejorado"]:
            stats["mejoradas"] += 1
        elif resultado.get("metodo_usado") == "error":
            stats["errores"] += 1
        else:
            stats["omitidas"] += 1

    # Costo REAL del lote, leído del usage acumulado (Claude/OpenAI; ollama = 0).
    try:
        from core.costos import costo_real_desde_usages

        # Modelo de referencia: el de visión si hubo imágenes, si no el de texto.
        modelo_ref = _MODELO_VISION if proveedor == "claude" else (
            "gpt-4o" if proveedor == "openai" else modelo_ollama
        )
        real = costo_real_desde_usages(proveedor, modelo_ref, usages())
        if real.tokens_totales > 0 or real.costo_usd == 0.0:
            stats["costo_real_usd"] = round(real.costo_usd, 4)
            stats["tokens_reales"] = real.tokens_totales
    except Exception:
        pass

    return stats
