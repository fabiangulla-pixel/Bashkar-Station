"""
core/embeddings_local.py — Embeddings semánticos locales con sentence-transformers.

Modelo: paraphrase-multilingual-MiniLM-L12-v2
  - 420 MB descarga única (se cachea en HuggingFace cache)
  - Multilingüe: funciona con español histórico sin ajuste
  - 384 dimensiones, rápido en CPU
  - 100% offline después de la descarga inicial

Instalación:
  pip install sentence-transformers
"""

from functools import lru_cache

import numpy as np

MODELO_EMBEDDINGS = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIMENSIONES = 384


def sentence_transformers_disponible() -> bool:
    """True si sentence-transformers está instalado."""
    try:
        import sentence_transformers  # noqa
        return True
    except ImportError:
        return False


@lru_cache(maxsize=1)
def _modelo_embeddings():
    """Carga el modelo con caché (se carga una vez por sesión)."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise ImportError(
            "sentence-transformers no está instalado.\n"
            "Ejecuta: pip install sentence-transformers"
        ) from e

    return SentenceTransformer(MODELO_EMBEDDINGS)


def generar_embeddings(textos: list[str],
                        batch_size: int = 32,
                        mostrar_progreso: bool = False) -> np.ndarray:
    """
    Genera embeddings para una lista de textos.

    Args:
        textos:           Lista de strings a codificar.
        batch_size:       Tamaño de lote para procesamiento.
        mostrar_progreso: Mostrar barra de progreso en consola.

    Returns:
        Array numpy de shape (len(textos), DIMENSIONES), float32, normalizado L2.

    Raises:
        ImportError: Si sentence-transformers no está instalado.
    """
    modelo = _modelo_embeddings()

    embeddings = modelo.encode(
        textos,
        batch_size=batch_size,
        show_progress_bar=mostrar_progreso,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return embeddings.astype(np.float32)


def similitud_coseno(a: np.ndarray, b: np.ndarray) -> float:
    """
    Similitud coseno entre dos vectores normalizados.
    Si los vectores ya están normalizados (generar_embeddings lo hace),
    es equivalente al producto punto.
    """
    a = a.flatten()
    b = b.flatten()
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def precargar_modelo():
    """
    Precarga el modelo en memoria (descargando si es necesario).
    Útil para llamar al inicio de la app en un thread background.
    """
    try:
        _modelo_embeddings()
        return True
    except Exception:
        return False
