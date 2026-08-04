"""core/ocr_churro.py — Ruta 6: CHURRO-3B, modelo de visión-lenguaje para texto histórico.

CHURRO (Stanford OVAL, EMNLP 2025) es un modelo de **pesos abiertos** de 3.000
millones de parámetros, construido sobre Qwen2.5-VL y afinado con CHURRO-DS:
99.491 páginas de 155 colecciones históricas, 22 siglos y 46 grupos
lingüísticos, español incluido. En el conjunto de prueba del paper alcanza
**82,3 % de similitud Levenshtein normalizada en impreso**, por encima de
Gemini 2.5 Pro y con un costo 15,5 veces menor.

Por qué importa en este proyecto: la auditoría de la sesión 36 concluyó que los
microfilms de la BNC no los rescata ningún preproceso clásico (NLMeans, Otsu,
adaptativo, CLAHE, upscale 3×) y que **hacen falta modelos de visión**. Hasta
ahora la única vía era la IA en la nube, que cuesta dinero por página y saca el
corpus del equipo. CHURRO da esa capacidad **en local y gratis**.

**Requisitos reales.** El modelo pesa ~6-7 GB y hay que descargarlo una vez.
Corre en CPU: en un Ryzen 5 de 6 núcleos son varios minutos por página. Es
lento para procesar un corpus completo, pero perfectamente viable para
**construir un estándar de oro** y para evaluar rutas — que es su uso previsto
aquí (ver `core/benchmark_ocr.py`).

No hay versión GGUF publicada, así que no puede correr por Ollama ni LM Studio:
se ejecuta con `transformers` directamente.

Referencias:
  · https://huggingface.co/stanford-oval/churro-3B
  · https://aclanthology.org/2025.emnlp-main.1763/
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

__all__ = [
    "MODELO_ID",
    "disponible",
    "esta_descargado",
    "motivo_no_disponible",
    "estimar_tiempo",
    "ocr_pagina",
    "ocr_lote",
    "liberar",
]

MODELO_ID = "stanford-oval/churro-3B"

# Segundos por página observados en CPU de 6 núcleos. Es una estimación para
# avisar al investigador ANTES de lanzar un lote, no una promesa.
SEGUNDOS_POR_PAGINA_CPU = 180.0

PROMPT_POR_DEFECTO = (
    "Transcribe all the text in this historical document image. "
    "Preserve the original spelling, line breaks and reading order. "
    "Do not translate, modernize or summarize."
)

# El modelo se carga una sola vez y se reutiliza. El lock evita que dos hilos
# de la GUI disparen dos cargas simultáneas de 6 GB.
_modelo = None
_procesador = None
_lock = threading.Lock()


def disponible() -> bool:
    """¿Están las dependencias para correr CHURRO?"""
    return motivo_no_disponible() is None


def motivo_no_disponible() -> str | None:
    """Devuelve el motivo por el que no se puede usar, o None si sí se puede.

    Se prefiere un mensaje accionable a un booleano: el investigador necesita
    saber qué instalar, no solo que algo falta.
    """
    if not _hay_modulo("torch"):
        return "Falta PyTorch. Instala:  pip install torch"
    if not _hay_modulo("transformers"):
        return "Faltan los transformers. Instala:  pip install transformers accelerate"
    try:
        import transformers
        if not hasattr(transformers, "Qwen2_5_VLForConditionalGeneration"):
            return ("Tu versión de transformers no soporta Qwen2.5-VL. "
                    "Actualiza:  pip install -U transformers")
    except Exception as e:                      # noqa: BLE001
        return f"No se pudo inspeccionar transformers: {e}"
    return None


def _hay_modulo(nombre: str) -> bool:
    """¿Está el módulo disponible? Tolera los casos raros de `find_spec`.

    `find_spec` lanza ValueError si el módulo ya está en `sys.modules` pero con
    `__spec__` a None — pasa con módulos inyectados y dentro de un .exe
    congelado. En ese caso el módulo SÍ está: se resuelve mirando sys.modules.
    """
    import importlib.util
    import sys
    try:
        return importlib.util.find_spec(nombre) is not None
    except (ImportError, ValueError):
        return nombre in sys.modules


def _dir_cache() -> Path:
    """Carpeta de la caché de HuggingFace, en disco local."""
    env = os.environ.get("HF_HOME") or os.environ.get("HUGGINGFACE_HUB_CACHE")
    if env:
        return Path(env)
    return Path.home() / ".cache" / "huggingface"


def esta_descargado() -> bool:
    """¿El modelo ya está en la caché local? (para no exigir red al arrancar)"""
    raiz = _dir_cache()
    for base in (raiz / "hub", raiz):
        carpeta = base / ("models--" + MODELO_ID.replace("/", "--"))
        if carpeta.exists() and any(carpeta.rglob("*.safetensors")):
            return True
    return False


def estimar_tiempo(n_paginas: int) -> dict:
    """Estimación previa del costo en TIEMPO (en dinero cuesta 0: es local).

    Sigue el estándar del proyecto de avisar antes de lanzar un lote caro.
    """
    segundos = n_paginas * SEGUNDOS_POR_PAGINA_CPU
    return {
        "paginas": n_paginas,
        "segundos": segundos,
        "minutos": round(segundos / 60, 1),
        "texto": (f"{n_paginas} página(s) · ~{round(segundos / 60, 1)} min "
                  f"en CPU (~{int(SEGUNDOS_POR_PAGINA_CPU)} s por página)"),
        "costo_usd": 0.0,
        "descarga_pendiente_gb": 0.0 if esta_descargado() else 7.0,
    }


def _cargar():
    """Carga perezosa del modelo. Devuelve (modelo, procesador)."""
    global _modelo, _procesador
    if _modelo is not None:
        return _modelo, _procesador

    with _lock:
        if _modelo is not None:            # otro hilo lo cargó mientras esperábamos
            return _modelo, _procesador

        motivo = motivo_no_disponible()
        if motivo:
            raise RuntimeError(motivo)

        import torch
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

        # Si ya está en caché, forzar modo offline: evita que el arranque se
        # cuelgue consultando el Hub sin conexión (lección de otros proyectos).
        if esta_descargado():
            os.environ.setdefault("HF_HUB_OFFLINE", "1")

        modelo = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            MODELO_ID,
            dtype=torch.float32,   # CPU: float16 va más lento y da NaN
            device_map="cpu",
            low_cpu_mem_usage=True,
        )
        modelo.eval()
        _procesador = AutoProcessor.from_pretrained(MODELO_ID)
        _modelo = modelo
        return _modelo, _procesador


def liberar() -> None:
    """Suelta el modelo de memoria (son ~6 GB de RAM)."""
    global _modelo, _procesador
    with _lock:
        _modelo = None
        _procesador = None
    import gc
    gc.collect()


def ocr_pagina(imagen, prompt: str = PROMPT_POR_DEFECTO,
               max_tokens: int = 2048) -> str:
    """Transcribe UNA imagen. `imagen` es una ruta o un objeto PIL.Image."""
    from PIL import Image

    modelo, procesador = _cargar()
    img = Image.open(imagen).convert("RGB") if isinstance(imagen, (str, Path)) else imagen.convert("RGB")

    mensajes = [{
        "role": "user",
        "content": [{"type": "image"}, {"type": "text", "text": prompt}],
    }]
    texto_plantilla = procesador.apply_chat_template(
        mensajes, tokenize=False, add_generation_prompt=True)
    entradas = procesador(text=[texto_plantilla], images=[img], return_tensors="pt")

    import torch
    with torch.inference_mode():
        generado = modelo.generate(**entradas, max_new_tokens=max_tokens,
                                   do_sample=False)

    # Recortar el eco del prompt: solo interesan los tokens nuevos
    recortado = [salida[len(entrada):]
                 for entrada, salida in zip(entradas.input_ids, generado)]
    salida = procesador.batch_decode(recortado, skip_special_tokens=True,
                                     clean_up_tokenization_spaces=False)
    return salida[0].strip() if salida else ""


def ocr_lote(rutas_imagenes, prompt: str = PROMPT_POR_DEFECTO,
             callback=None, max_tokens: int = 2048) -> dict:
    """Transcribe varias imágenes. Devuelve {nombre_pagina: texto}.

    `callback(indice, total, nombre, segundos)` se llama tras cada página para
    que la interfaz muestre avance: en CPU esto tarda minutos por página y
    dejar la barra quieta sería inaceptable.

    Un fallo en una página no aborta el lote: se registra como texto vacío,
    que es lo que `benchmark_ocr` interpreta como error total (correcto: no
    reconocer nada ES un fallo, no un dato ausente).
    """
    resultados: dict[str, str] = {}
    rutas = list(rutas_imagenes)
    for i, ruta in enumerate(rutas):
        nombre = Path(ruta).stem
        t0 = time.perf_counter()
        try:
            resultados[nombre] = ocr_pagina(ruta, prompt=prompt,
                                            max_tokens=max_tokens)
        except Exception as e:                  # noqa: BLE001
            resultados[nombre] = ""
            if callback:
                callback(i + 1, len(rutas), f"{nombre} — ERROR: {e}",
                         time.perf_counter() - t0)
            continue
        if callback:
            callback(i + 1, len(rutas), nombre, time.perf_counter() - t0)
    return resultados
