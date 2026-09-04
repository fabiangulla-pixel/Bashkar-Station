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
import re
import sys
import threading
import time
from pathlib import Path

__all__ = [
    "MODELO_ID",
    "disponible",
    "esta_descargado",
    "motivo_no_disponible",
    "estimar_tiempo",
    "estimar_tiempo_zonas",
    "ocr_pagina",
    "ocr_pagina_con_zonas",
    "ocr_lote",
    "descargar_modelo",
    "liberar",
]

MODELO_ID = "stanford-oval/churro-3B"

# `model-00002-of-00002.safetensors` → fragmento 2 de 2. El nombre es la única
# pista fiable cuando el índice del modelo no se llegó a descargar.
_RE_FRAGMENTO = re.compile(r"^model-(\d+)-of-(\d+)\.safetensors$")

# Remedido el 2026-08-12 en el mismo Ryzen 5 5500U (6 núcleos, sin GPU), sobre
# la página 2 del número del 18-mar-1939 a 300 dpi nativos, ya con el techo de
# `max_pixels` y con los pesos en bfloat16: **1 121 s (18,7 min)**, 534 palabras,
# 8,41 GB de RSS en el pico de generación.
#
# El 2026-08-04, sin capar los tokens visuales, la misma tarea tardaba 3 060 s
# (51,1 min). La mejora real es de **2,7×** — menos de lo que hacía esperar la
# reducción de 16 384 a 1 280 tokens, señal de que buena parte del tiempo no se
# va en los tokens de imagen sino en generar los de salida, uno a uno.
SEGUNDOS_POR_PAGINA_CPU = 1121.0

# Medido el 2026-08-04 sobre `rev_estampa_mar_1939/p0001-02`, una página real
# etiquetada con 13 zonas (9 con texto, 4 fotografías saltadas): **37,8 minutos
# en total, entre 2,8 y 3,7 minutos por zona**. La página completa había tardado
# 51,1 min, así que trabajar por zonas ahorra ~26 % además de no arriesgar que
# el modelo describa las fotografías.
#
# ⚠️ Este número es de ANTES de capar `max_pixels`, a diferencia del de página
# completa, que ya se remidió. Está pendiente rehacerlo: recortar una zona reduce
# los tokens visuales, así que el techo le afecta menos, y no se puede deducir
# aplicándole el mismo 2,7× sin medirlo.
SEGUNDOS_POR_ZONA_CPU = 210.0

# Techo de resolución que se le entrega al modelo, en píxeles totales.
#
# Qwen2.5-VL trocea la imagen en parches de 28×28 y fusiona de a 2×2, así que el
# número de tokens visuales es ≈ píxeles / 3136. El procesador trae por defecto
# `max_pixels = 12 845 056` (16 384 tokens): una zona recortada a 200 dpi entra
# entera y el modelo pasa la mayor parte de los 210 s midiendo blanco de página.
# El tiempo de generación crece con esos tokens, y era la causa real de los
# 51 min por página medidos en la sesión 50 — no el tamaño del modelo.
#
# 1 003 520 px = 1 280 tokens visuales. Para un recorte de zona (una columna de
# texto) sigue habiendo resolución de sobra; para una página completa implica
# remuestrear hacia abajo, y ahí sí puede perderse cuerpo pequeño.
#
# Ajustable sin tocar código con BASHKAR_CHURRO_MAX_PIXELS, para poder barrer
# el compromiso velocidad/CER con `core/benchmark_ocr.py` sobre el estándar de oro.
MAX_PIXELS_POR_DEFECTO = 1_003_520
MIN_PIXELS_POR_DEFECTO = 200_704  # 256 tokens: piso para que un pie de foto no se diluya

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
    # En el .exe compilado PyTorch está EXCLUIDO a propósito (bashkar_station.spec):
    # empaquetarlo llevaría el ejecutable de ~1 GB a más de 3 GB. Decirle al
    # usuario «pip install torch» dentro de un .exe congelado sería un consejo
    # imposible de seguir: no hay pip ahí dentro y auto-instalar está prohibido
    # en este proyecto desde el incidente de la bomba de fork.
    congelado = _esta_congelado()
    if not _hay_modulo("torch"):
        if congelado:
            return (
                "CHURRO-3B no está disponible en la versión compilada: "
                "PyTorch se excluye del .exe a propósito (pesaría más de "
                "3 GB).\n\nPara usar esta ruta, ejecuta Bashkar Station "
                "desde el código fuente:  python app.py"
            )
        return "Falta PyTorch. Instala:  pip install torch"
    if not _hay_modulo("transformers"):
        if congelado:
            return (
                "CHURRO-3B no está disponible en la versión compilada. "
                "Ejecuta Bashkar Station desde el código fuente para usarlo."
            )
        return "Faltan los transformers. Instala:  pip install transformers accelerate"
    soporta, error = _soporta_qwen()
    if error:
        return f"No se pudo inspeccionar transformers: {error}"
    if not soporta:
        return (
            "Tu versión de transformers no soporta Qwen2.5-VL. "
            "Actualiza:  pip install -U transformers"
        )
    return None


def _soporta_qwen() -> tuple[bool, str | None]:
    """¿Trae esta versión de transformers la clase de Qwen2.5-VL?

    Aislado en su propia función para poder probarlo sin importar transformers
    de verdad en la suite: ese import arrastra torch y desestabiliza el proceso
    de pytest (llega a provocar un access violation al crear los temporales).
    """
    try:
        import transformers

        return hasattr(transformers, "Qwen2_5_VLForConditionalGeneration"), None
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def _esta_congelado() -> bool:
    """¿Corremos dentro de un .exe de PyInstaller?

    Existe como función propia en vez de leer `sys.frozen` en línea para poder
    probarlo: parchear `sys.frozen` de verdad en un test hace que otras
    librerías cambien de comportamiento y tumba al intérprete.
    """
    return bool(getattr(sys, "frozen", False))


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
    """Carpeta de la caché de HuggingFace.

    Si junto al ejecutable existe una carpeta `modelos_ia/`, se usa esa: así el
    modelo viaja con la aplicación en una memoria USB y funciona en cualquier
    PC sin volver a descargar 7 GB. Si no, la caché normal del usuario.
    """
    env = os.environ.get("HF_HOME") or os.environ.get("HUGGINGFACE_HUB_CACHE")
    if env:
        return Path(env)
    portatil = _dir_portatil()
    if portatil is not None:
        return portatil
    return Path.home() / ".cache" / "huggingface"


def _dir_portatil() -> Path | None:
    """`modelos_ia/` junto al .exe (o al proyecto), si existe."""
    base = Path(sys.executable).parent if _esta_congelado() else Path(__file__).parent.parent
    candidata = base / "modelos_ia"
    return candidata if candidata.is_dir() else None


def _carpeta_modelo_local() -> Path | None:
    """Carpeta con el modelo desempaquetado, si la hay.

    Además de la caché de HuggingFace, se acepta una carpeta plana con los
    archivos del modelo. Dos motivos:

    1. **Portabilidad**: `modelos_ia/churro-3B/` junto al ejecutable viaja en la
       memoria USB y funciona en cualquier PC sin volver a descargar 7 GB.
    2. **Descargas por otra vía**: `huggingface_hub` se atasca con los pesos de
       varios GB en algunas redes; bajarlos con otra herramienta y dejarlos en
       una carpeta tiene que ser suficiente para que la ruta funcione.

    `BASHKAR_CHURRO_DIR` permite apuntar a una carpeta arbitraria.
    """
    candidatas = []
    env = os.environ.get("BASHKAR_CHURRO_DIR")
    if env:
        candidatas.append(Path(env))
    portatil = _dir_portatil()
    if portatil is not None:
        candidatas.append(portatil / "churro-3B")

    for c in candidatas:
        if c.is_dir() and (c / "config.json").exists() and any(c.glob("*.safetensors")):
            return c
    return None


def descargar_modelo(callback=None) -> Path:
    """Descarga el modelo a la caché local. Pensada para llamarse desde la GUI.

    El usuario de este programa no abre una terminal: la descarga tiene que
    poder dispararse con un botón y reportar avance. `callback(mensaje)` se
    llama con líneas de estado.

    Devuelve la carpeta donde quedó. Si ya estaba, no vuelve a bajar nada
    (huggingface_hub reutiliza lo que haya en caché).
    """
    motivo = motivo_no_disponible()
    if motivo:
        raise RuntimeError(motivo)

    from huggingface_hub import snapshot_download

    destino = _dir_cache()
    destino.mkdir(parents=True, exist_ok=True)
    if callback:
        callback(f"Descargando {MODELO_ID} (~7 GB) en {destino}…")
        callback("Es una sola vez. Después funciona sin conexión.")

    # Quitar el modo offline si estaba puesto por una sesión anterior: aquí
    # SÍ queremos ir a la red.
    os.environ.pop("HF_HUB_OFFLINE", None)

    ruta = snapshot_download(
        repo_id=MODELO_ID,
        cache_dir=str(destino / "hub") if (destino / "hub").exists() else str(destino),
        allow_patterns=["*.safetensors", "*.json", "*.txt", "*.model"],
    )
    if callback:
        callback(f"✔ Modelo listo en {ruta}")
    return Path(ruta)


def esta_descargado() -> bool:
    """¿Está el modelo COMPLETO en la caché local?

    Ojo con la versión ingenua de esto: comprobar que exista *algún* archivo
    `.safetensors` daba `True` con una descarga a medias (el modelo viene en
    dos fragmentos de 4,8 y 2,4 GB). Con eso, la aplicación creía tener el
    modelo, no volvía a descargarlo y fallaba al cargarlo. Hay que exigir que
    estén TODOS los fragmentos que declara el índice.
    """
    import json

    if _carpeta_modelo_local() is not None:
        return True

    raiz = _dir_cache()
    for base in (raiz / "hub", raiz):
        carpeta = base / ("models--" + MODELO_ID.replace("/", "--"))
        if not carpeta.exists():
            continue

        indices = list(carpeta.rglob("model.safetensors.index.json"))
        if indices:
            try:
                datos = json.loads(indices[0].read_text(encoding="utf-8"))
                requeridos = set(datos.get("weight_map", {}).values())
            except (OSError, ValueError):
                requeridos = set()
            if requeridos:
                presentes = {p.name for p in carpeta.rglob("*.safetensors") if p.stat().st_size > 0}
                return requeridos.issubset(presentes)

        # Sin índice. Ojo: que no haya índice no significa que el modelo sea de
        # un solo archivo. Aquí se llegaba con una caché que tenía el fragmento
        # 2 de 2 y nada más —ni el índice ni el fragmento 1, 5 GB— y se devolvía
        # True porque «hay un .safetensors no vacío». Con eso la aplicación
        # ofrecía la ruta, transformers intentaba mapear los pesos que faltaban
        # y el proceso moría con *segmentation fault*: no una excepción que se
        # pueda atrapar y explicar, sino la aplicación entera cerrándose de
        # golpe y llevándose por delante el trabajo sin guardar.
        #
        # El propio nombre del archivo dice si es un fragmento, así que se usa
        # eso: si hay fragmentos, tienen que estar TODOS los que anuncia el
        # sufijo `-of-N`.
        sueltos = [p for p in carpeta.rglob("*.safetensors") if p.stat().st_size > 0]
        fragmentos = {}
        for p in sueltos:
            m = _RE_FRAGMENTO.match(p.name)
            if m:
                fragmentos.setdefault(int(m.group(2)), set()).add(int(m.group(1)))
        if fragmentos:
            return any(len(vistos) == total for total, vistos in fragmentos.items())
        if sueltos:
            return True  # modelo de un solo archivo, de verdad
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
        "texto": (
            f"{n_paginas} página(s) · ~{round(segundos / 60, 1)} min "
            f"en CPU (~{int(SEGUNDOS_POR_PAGINA_CPU)} s por página)"
        ),
        "costo_usd": 0.0,
        "descarga_pendiente_gb": 0.0 if esta_descargado() else 7.0,
    }


def _dtype(torch):
    """Precisión con la que se cargan los pesos. Manda la RAM, no la velocidad.

    En `float32` el modelo ocupa **11,97 GB medidos**. Un portátil de 20 GB con
    el navegador y el editor abiertos tiene del orden de 6 GB libres, así que la
    carga terminaba en *segmentation fault* — no es que fuera lenta: no cabía.

    `bfloat16` lo deja en ~6 GB. No es lo mismo que `float16`: bfloat16 conserva
    los 8 bits de exponente de float32, así que no tiene el desbordamiento a NaN
    que hace inservible a float16 en CPU. Lo que sí pierde son bits de mantisa,
    y por eso el resultado hay que compararlo contra el estándar de oro con
    `benchmark_ocr` antes de darlo por bueno.

    `BASHKAR_CHURRO_DTYPE=float32` recupera el comportamiento anterior en una
    máquina con RAM de sobra.
    """
    nombre = os.environ.get("BASHKAR_CHURRO_DTYPE", "").strip().lower()
    if nombre in ("float32", "fp32"):
        return torch.float32
    if nombre in ("float16", "fp16"):
        return torch.float16  # a petición expresa; da NaN en CPU
    return torch.bfloat16


def _limite_pixeles(variable: str, por_defecto: int) -> int:
    """Lee un techo de píxeles de una variable de entorno, con respaldo.

    Un valor inservible (texto, cero, negativo) no debe tumbar el OCR: se ignora
    y se sigue con el valor por defecto, que es lo que espera quien solo quería
    transcribir una página.
    """
    crudo = os.environ.get(variable, "").strip()
    if not crudo:
        return por_defecto
    try:
        valor = int(crudo)
    except ValueError:
        return por_defecto
    return valor if valor > 0 else por_defecto


def _cargar():
    """Carga perezosa del modelo. Devuelve (modelo, procesador)."""
    global _modelo, _procesador
    if _modelo is not None:
        return _modelo, _procesador

    with _lock:
        if _modelo is not None:  # otro hilo lo cargó mientras esperábamos
            return _modelo, _procesador

        # ── HF_HUB_OFFLINE va ANTES DE TODO, incluida la comprobación ─────
        #
        # `motivo_no_disponible()` parece una comprobación inocua, pero NO lo es:
        # usa `importlib.util.find_spec()`, que con estos paquetes ejecuta el
        # módulo. Medido el 3-sep-2026: antes de llamarla, ni torch ni
        # transformers ni huggingface_hub están en `sys.modules`; después, los
        # tres. Es decir, la comprobación de disponibilidad IMPORTA la pila
        # entera.
        local = _carpeta_modelo_local()
        origen = str(local) if local else MODELO_ID
        if local or esta_descargado():
            os.environ.setdefault("HF_HUB_OFFLINE", "1")

        motivo = motivo_no_disponible()
        if motivo:
            raise RuntimeError(motivo)

        # ── Por qué el orden de arriba no es cosmético ────────────────────
        #
        # Ponerlo después provoca un SEGFAULT (0xC0000005 en
        # Windows, sin stderr ni traza de Python). `huggingface_hub` congela el
        # valor de esta variable como constante de módulo en su propio import, y
        # `transformers` lo arrastra; escribirla más tarde deja el proceso con
        # dos verdades distintas sobre si hay red, y la carga del procesador
        # revienta en código nativo.
        #
        # Reproducido el 3-sep-2026 con el mismo script cambiando solo el orden:
        # antes del import -> código de salida 0; después -> 139 (segfault).
        # Es la MISMA causa raíz que la sesión 63 encontró en
        # `core/ner_roberta_local.py`; reapareció aquí porque la lógica está
        # copiada en dos módulos en vez de compartida.
        #
        # Se resuelve el origen antes de importar nada, porque
        # `_carpeta_modelo_local()` y `esta_descargado()` no dependen de
        # transformers.
        import torch
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

        # Un modelo de 3B en CPU satura los 12 hilos lógicos y deja a la interfaz
        # sin turno de planificación: la app se ve congelada durante los minutos
        # que dura la transcripción. Reservar núcleos apenas cuesta tiempo.
        from core import recursos

        recursos.limitar_hilos_torch()

        # `origen` y el modo offline ya quedaron resueltos arriba, antes de
        # importar transformers. Una carpeta local del modelo tiene prioridad
        # sobre la caché: es lo que hace posible el modo portátil en USB.

        modelo = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            origen,
            dtype=_dtype(torch),
            device_map="cpu",
            low_cpu_mem_usage=True,
        )
        modelo.eval()
        _procesador = AutoProcessor.from_pretrained(
            origen,
            min_pixels=_limite_pixeles("BASHKAR_CHURRO_MIN_PIXELS", MIN_PIXELS_POR_DEFECTO),
            max_pixels=_limite_pixeles("BASHKAR_CHURRO_MAX_PIXELS", MAX_PIXELS_POR_DEFECTO),
        )
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


def ocr_pagina(imagen, prompt: str = PROMPT_POR_DEFECTO, max_tokens: int = 2048) -> str:
    """Transcribe UNA imagen. `imagen` es una ruta o un objeto PIL.Image."""
    from PIL import Image

    modelo, procesador = _cargar()
    img = (
        Image.open(imagen).convert("RGB")
        if isinstance(imagen, (str, Path))
        else imagen.convert("RGB")
    )

    mensajes = [
        {
            "role": "user",
            "content": [{"type": "image"}, {"type": "text", "text": prompt}],
        }
    ]
    texto_plantilla = procesador.apply_chat_template(
        mensajes, tokenize=False, add_generation_prompt=True
    )
    entradas = procesador(text=[texto_plantilla], images=[img], return_tensors="pt")

    import torch

    with torch.inference_mode():
        generado = modelo.generate(**entradas, max_new_tokens=max_tokens, do_sample=False)

    # Recortar el eco del prompt: solo interesan los tokens nuevos
    recortado = [salida[len(entrada) :] for entrada, salida in zip(entradas.input_ids, generado)]
    salida = procesador.batch_decode(
        recortado, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )
    return salida[0].strip() if salida else ""


def ocr_pagina_con_zonas(
    img_path,
    zonas,
    prompt: str = PROMPT_POR_DEFECTO,
    margen_px: int = 6,
    max_tokens: int = 1024,
    callback=None,
) -> dict:
    """Transcribe SOLO las zonas etiquetadas como texto, en orden de lectura.

    Es la forma correcta de usar este modelo dentro del flujo de Bashkar: el
    investigador etiqueta primero la tipología de cada zona, y el OCR trabaja
    sobre esa marca. Pasarle la página entera a un modelo de visión gasta miles
    de tokens en fotografías, filetes y publicidad —que no llevan texto que
    interese— y encima invita a que el modelo alucine describiendo imágenes.

    Se respeta el flag `ocr` de `TIPOS_ZONA`: fotografía, publicidad, filete,
    cabecera, colofón y número de página se saltan; artículo, título, pie de
    foto e índice se transcriben.

    Devuelve la misma forma que `layout_tesseract.ocr_por_zonas` para que las
    dos rutas sean intercambiables aguas arriba:
        {"texto": str, "zonas": [{orden, tipo, texto}], "confianza": float}
    """
    from PIL import Image

    from core.zone_labeler import TIPOS_ZONA, calcular_orden_lectura

    def log(m):
        if callback:
            callback(m)

    procesables = [z for z in zonas if TIPOS_ZONA.get(z.tipo, {}).get("ocr", True)]
    if not procesables:
        log("Ninguna zona de esta página lleva texto a transcribir.")
        return {"texto": "", "zonas": [], "confianza": 0.0}

    if all(getattr(z, "orden", 0) == 0 for z in procesables):
        calcular_orden_lectura(zonas)
    procesables.sort(key=lambda z: (z.orden if z.orden > 0 else 9999, z.y0, z.x0))

    img = Image.open(img_path).convert("RGB")
    W, H = img.size
    saltadas = len(zonas) - len(procesables)
    log(f"{len(procesables)} zona(s) con texto · {saltadas} saltada(s) (foto/publicidad/filete)")

    salida, partes = [], []
    for i, z in enumerate(procesables):
        x0, y0, x1, y1 = z.a_pixeles(W, H)
        x0 = max(0, x0 - margen_px)
        y0 = max(0, y0 - margen_px)
        x1 = min(W, x1 + margen_px)
        y1 = min(H, y1 + margen_px)
        if x1 - x0 < 8 or y1 - y0 < 8:
            continue

        t0 = time.perf_counter()
        try:
            texto = ocr_pagina(img.crop((x0, y0, x1, y1)), prompt=prompt, max_tokens=max_tokens)
        except Exception as e:  # noqa: BLE001
            texto = ""
            log(f"  zona {i + 1}/{len(procesables)} ({z.tipo}) — ERROR: {e}")
        seg = time.perf_counter() - t0

        salida.append(
            {"orden": z.orden, "tipo": z.tipo, "texto": texto, "zid": getattr(z, "zid", "")}
        )
        if texto:
            partes.append(texto)
        log(
            f"  zona {i + 1}/{len(procesables)} ({z.tipo}): "
            f"{len(texto.split())} palabras en {seg / 60:.1f} min"
        )

    return {
        "texto": "\n\n".join(partes),
        "zonas": salida,
        # CHURRO no reporta confianza por token; se informa cobertura: qué
        # proporción de las zonas con texto devolvió algo.
        "confianza": round(100 * sum(1 for z in salida if z["texto"]) / max(len(salida), 1), 1),
    }


def estimar_tiempo_zonas(zonas) -> dict:
    """Estimación previa contando SOLO las zonas que llevan texto."""
    from core.zone_labeler import TIPOS_ZONA

    n = sum(1 for z in zonas if TIPOS_ZONA.get(z.tipo, {}).get("ocr", True))
    segundos = n * SEGUNDOS_POR_ZONA_CPU
    return {
        "zonas_con_texto": n,
        "zonas_saltadas": len(zonas) - n,
        "segundos": segundos,
        "minutos": round(segundos / 60, 1),
        "texto": (f"{n} zona(s) con texto de {len(zonas)} · ~{round(segundos / 60, 1)} min en CPU"),
        "costo_usd": 0.0,
    }


def ocr_lote(
    rutas_imagenes, prompt: str = PROMPT_POR_DEFECTO, callback=None, max_tokens: int = 2048
) -> dict:
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
            resultados[nombre] = ocr_pagina(ruta, prompt=prompt, max_tokens=max_tokens)
        except Exception as e:  # noqa: BLE001
            resultados[nombre] = ""
            if callback:
                callback(i + 1, len(rutas), f"{nombre} — ERROR: {e}", time.perf_counter() - t0)
            continue
        if callback:
            callback(i + 1, len(rutas), nombre, time.perf_counter() - t0)
    return resultados
