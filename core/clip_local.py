"""
core/clip_local.py — Punto único de carga del modelo CLIP.

Cinco sitios del proyecto usaban **el mismo** checkpoint
(`openai/clip-vit-base-patch32`) y cada uno lo cargaba por su cuenta con
`from_pretrained`: `visual_search`, `visual_classifier` (dos veces) y
`deepfont` (dos veces). Como `from_pretrained` no comparte instancias, clasificar
tipografías después de una búsqueda visual dejaba dos copias de ~600 MB en
memoria; y `clasificar_imagen()`, que llamaba a `from_pretrained` en cada
invocación, releía los pesos del disco **por imagen**. Sobre un lote de cien
recortes eso es un minuto largo de lectura pura y un vaivén de memoria que
arrastra a todo el equipo.

Aquí se carga una sola vez por sesión y se reparte. Un modelo de inferencia en
`eval()` no tiene estado mutable entre llamadas, así que compartirlo es seguro
—incluso entre los hilos de la GUI, que es como lo usa Bashkar.

Reglas de la casa:
  · `transformers` y `torch` se importan dentro de la función, nunca al importar
    el módulo: son opcionales y en el .exe compilado no existen.
  · Los errores se propagan con un mensaje accionable; quien llama decide si
    degrada a OpenCV (lo hacen `visual_classifier` y `deepfont`) o avisa.
"""

from __future__ import annotations

from functools import lru_cache

__all__ = ["MODELO_CLIP", "cargar", "disponible", "liberar"]

MODELO_CLIP = "openai/clip-vit-base-patch32"


def disponible() -> bool:
    """¿Se puede usar CLIP en este entorno? No carga nada."""
    try:
        import torch          # noqa: F401
        import transformers   # noqa: F401
        return True
    except ImportError:
        return False


@lru_cache(maxsize=1)
def cargar():
    """Devuelve (modelo, procesador) de CLIP, cargándolo la primera vez.

    El resultado se cachea durante toda la sesión. El modelo vuelve ya en
    `eval()`: ninguna ruta del proyecto lo entrena, y dejarlo en modo
    entrenamiento activaría dropout y daría embeddings distintos en cada
    llamada para la misma imagen.

    Lanza ImportError con instrucciones si faltan las dependencias.
    """
    try:
        from transformers import CLIPModel, CLIPProcessor
    except ImportError as e:
        raise ImportError(
            "CLIP necesita transformers y torch.\n"
            "Instala:  pip install transformers torch\n"
            "El modelo ocupa ~600 MB la primera vez."
        ) from e

    modelo = CLIPModel.from_pretrained(MODELO_CLIP)
    proc = CLIPProcessor.from_pretrained(MODELO_CLIP)
    modelo.eval()
    return modelo, proc


def liberar() -> None:
    """Suelta el modelo de memoria (~600 MB).

    Para lotes largos que ya terminaron con la parte visual y siguen con OCR o
    con un modelo de lenguaje, que es cuando cada gigabyte cuenta.
    """
    cargar.cache_clear()
    import gc
    gc.collect()
