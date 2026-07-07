"""
core/ocr_ollama_local.py — OCR visual offline con Ollama + Qwen-VL.

Ollama permite ejecutar modelos de visión localmente, sin API key ni internet.
El modelo Qwen2.5-VL comprende layout de página complejo y respeta columnas.

Requisitos:
  1. Instalar Ollama: https://ollama.com/download
  2. Descargar modelo: ollama pull qwen2.5vl:7b   (8 GB RAM)
                    ó: ollama pull minicpm-v       (4 GB RAM, más ligero)
  3. pip install ollama

Velocidad aproximada: ~30-60 seg/página en CPU i7.
"""

import base64
from pathlib import Path
from typing import Optional


# Prompt calibrado para prensa histórica colombiana
PROMPT_OCR_HISTORICO = """Transcribe el texto de esta imagen.
Es una página de revista o periódico colombiano, circa 1930-1940.

Reglas:
- Conserva la ortografía original de la época (habia, fué, vió, á, etc.)
- No modernices ni corrijas formas verbales históricas
- Si un fragmento es ilegible escribe [ilegible]
- Respeta la estructura de columnas si las hay
- No añadas comentarios ni explicaciones
- Solo el texto transcrito"""

PROMPT_OCR_GENERAL = """Transcribe el texto de esta imagen de documento histórico.
Conserva la ortografía original. Si algo es ilegible escribe [ilegible].
Solo el texto, sin comentarios."""


def ollama_disponible(modelo: str = "qwen2.5vl:7b") -> bool:
    """True si Ollama está instalado y el modelo solicitado está disponible."""
    try:
        import ollama
        modelos = ollama.list()
        nombres = [m.model for m in modelos.models] if hasattr(modelos, "models") else []
        return any(modelo in n for n in nombres)
    except Exception:
        return False


def ocr_ollama(ruta_imagen: str,
               modelo: str = "qwen2.5vl:7b",
               prompt: Optional[str] = None,
               timeout: int = 120) -> tuple[str, float]:
    """
    OCR visual con Ollama (completamente offline).

    Args:
        ruta_imagen: Ruta a la imagen (PNG/JPG).
        modelo:      Nombre del modelo Ollama. Alternativa: "minicpm-v"
        prompt:      Prompt personalizado. Si None usa PROMPT_OCR_HISTORICO.
        timeout:     Segundos máximo de espera.

    Returns:
        (texto, confianza) donde confianza es estimada (0.70 por defecto).

    Raises:
        ImportError:    Si el paquete ollama no está instalado.
        ConnectionError: Si el servidor Ollama no está corriendo.
        RuntimeError:   Si el modelo no está disponible.
    """
    try:
        import ollama as _ollama
    except ImportError as e:
        raise ImportError(
            "El paquete ollama no está instalado. Ejecuta: pip install ollama\n"
            "Luego instala Ollama desde: https://ollama.com/download"
        ) from e

    if not Path(ruta_imagen).exists():
        raise FileNotFoundError(f"Imagen no encontrada: {ruta_imagen}")

    # Codificar imagen en base64
    with open(ruta_imagen, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    prompt_final = prompt or PROMPT_OCR_HISTORICO

    try:
        response = _ollama.chat(
            model=modelo,
            messages=[{
                "role":    "user",
                "content": prompt_final,
                "images":  [img_b64],
            }],
            options={"num_predict": 4096},
        )
    except Exception as e:
        error_msg = str(e)
        if "connection" in error_msg.lower() or "refused" in error_msg.lower():
            raise ConnectionError(
                "Ollama no está corriendo. Inicia el servidor con: ollama serve"
            ) from e
        if "not found" in error_msg.lower():
            raise RuntimeError(
                f"Modelo '{modelo}' no disponible. Descarga con: ollama pull {modelo}"
            ) from e
        raise RuntimeError(f"Error en Ollama: {e}") from e

    texto = response["message"]["content"].strip()

    # Confianza estimada: Ollama no expone score explícito
    # Heurística: si hay muchos [ilegible] la confianza baja
    n_ilegibles = texto.lower().count("[ilegible]")
    n_palabras = max(len(texto.split()), 1)
    confianza = max(0.40, 0.70 - (n_ilegibles / n_palabras) * 2)

    return texto, round(confianza, 4)


def ocr_ollama_lote(rutas_imagenes: list[str],
                     modelo: str = "qwen2.5vl:7b",
                     callback=None) -> list[dict]:
    """
    Procesa un lote de imágenes con Ollama.

    Args:
        rutas_imagenes: Lista de rutas a imágenes.
        modelo:         Modelo Ollama a usar.
        callback:       callable(i, total, ruta, ok) — progreso.

    Returns:
        Lista de dicts: {ruta, texto, confianza, ok, error}
    """
    resultados = []
    total = len(rutas_imagenes)

    for i, ruta in enumerate(rutas_imagenes):
        try:
            texto, confianza = ocr_ollama(ruta, modelo)
            resultados.append({
                "ruta":      ruta,
                "texto":     texto,
                "confianza": confianza,
                "ok":        True,
                "error":     None,
            })
            if callback:
                callback(i + 1, total, ruta, True)
        except Exception as e:
            resultados.append({
                "ruta":      ruta,
                "texto":     "",
                "confianza": 0.0,
                "ok":        False,
                "error":     str(e),
            })
            if callback:
                callback(i + 1, total, ruta, False)

    return resultados


def listar_modelos_vision() -> list[str]:
    """
    Lista los modelos de visión disponibles en Ollama.
    Retorna lista vacía si Ollama no está disponible.
    """
    try:
        import ollama as _ollama
        modelos = _ollama.list()
        todos = [m.model for m in modelos.models] if hasattr(modelos, "models") else []
        # Filtrar modelos de visión conocidos
        vision_keywords = ["vl", "vision", "minicpm", "llava", "bakllava", "moondream"]
        return [m for m in todos if any(k in m.lower() for k in vision_keywords)]
    except Exception:
        return []
