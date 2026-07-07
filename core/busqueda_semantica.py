"""
core/busqueda_semantica.py — Búsqueda semántica vectorial con FAISS.

FAISS permite buscar por significado entre miles de artículos en milisegundos.
El investigador escribe en lenguaje natural; el sistema encuentra artículos
por similitud semántica, no por palabras exactas.

Instalación:
  pip install faiss-cpu

Ejemplo de uso:
    from core.busqueda_semantica import IndiceSemantico
    from core.embeddings_local import generar_embeddings

    indice = IndiceSemantico()
    embeddings = generar_embeddings(textos)
    indice.construir(embeddings, ids_articulos)

    consulta_emb = generar_embeddings(["artículos sobre modernidad y ciudad"])
    resultados = indice.buscar(consulta_emb[0], k=10)
"""

import json
import numpy as np
from pathlib import Path
from typing import Optional


def faiss_disponible() -> bool:
    """True si faiss-cpu está instalado."""
    try:
        import faiss  # noqa
        return True
    except ImportError:
        return False


class IndiceSemantico:
    """
    Índice FAISS para búsqueda semántica sobre el corpus de artículos.

    Almacena embeddings normalizados y usa producto interno (≡ coseno)
    para ranking de similitud.
    """

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self._indice = None
        self._ids: list[str] = []
        self._construido = False

    def construir(self, embeddings: np.ndarray, ids: list[str]):
        """
        Construye el índice a partir de embeddings y sus IDs.

        Args:
            embeddings: Array (N, D) float32, normalizado L2.
            ids:        Lista de N strings identificando cada embedding.

        Raises:
            ImportError: Si faiss no está instalado.
        """
        try:
            import faiss
        except ImportError as e:
            raise ImportError(
                "faiss-cpu no está instalado. Ejecuta: pip install faiss-cpu"
            ) from e

        if len(embeddings) == 0:
            raise ValueError("No hay embeddings para indexar.")
        if len(embeddings) != len(ids):
            raise ValueError(
                f"Mismatch: {len(embeddings)} embeddings pero {len(ids)} IDs."
            )

        emb = embeddings.astype(np.float32)
        faiss.normalize_L2(emb)

        self._indice = faiss.IndexFlatIP(self.dimension)
        self._indice.add(emb)
        self._ids = list(ids)
        self._construido = True

    def buscar(self, embedding_consulta: np.ndarray, k: int = 10) -> list[dict]:
        """
        Busca los k artículos más similares al embedding de consulta.

        Args:
            embedding_consulta: Vector 1D float32 de la consulta.
            k:                  Número de resultados a retornar.

        Returns:
            Lista de dicts ordenada por similitud desc:
            [{articulo_id, similitud, rank}, ...]

        Raises:
            RuntimeError: Si el índice no ha sido construido.
        """
        if not self._construido or self._indice is None:
            raise RuntimeError(
                "El índice semántico no está construido. "
                "Llama a construir() primero."
            )

        try:
            import faiss
        except ImportError as e:
            raise ImportError("faiss-cpu no está instalado.") from e

        q = embedding_consulta.reshape(1, -1).astype(np.float32)
        faiss.normalize_L2(q)

        k_real = min(k, len(self._ids))
        distancias, indices = self._indice.search(q, k_real)

        resultados = []
        for rank, (distancia, idx) in enumerate(
            zip(distancias[0], indices[0]), start=1
        ):
            if idx < 0:
                continue
            resultados.append({
                "articulo_id": self._ids[idx],
                "similitud":   round(float(distancia), 4),
                "rank":        rank,
            })

        return resultados

    def guardar(self, ruta_base: str):
        """
        Persiste el índice en disco.
        Genera: ruta_base.faiss  y  ruta_base.ids.json
        """
        if not self._construido:
            raise RuntimeError("Índice vacío, nada que guardar.")

        try:
            import faiss
        except ImportError as e:
            raise ImportError("faiss-cpu no está instalado.") from e

        faiss.write_index(self._indice, str(ruta_base) + ".faiss")
        with open(str(ruta_base) + ".ids.json", "w", encoding="utf-8") as f:
            json.dump(self._ids, f, ensure_ascii=False)

    def cargar(self, ruta_base: str) -> bool:
        """
        Carga un índice previamente guardado.

        Returns:
            True si la carga fue exitosa, False si los archivos no existen.
        """
        try:
            import faiss
        except ImportError:
            return False

        ruta_faiss = Path(str(ruta_base) + ".faiss")
        ruta_ids   = Path(str(ruta_base) + ".ids.json")

        if not ruta_faiss.exists() or not ruta_ids.exists():
            return False

        try:
            self._indice = faiss.read_index(str(ruta_faiss))
            with open(ruta_ids, encoding="utf-8") as f:
                self._ids = json.load(f)
            self._construido = True
            return True
        except Exception:
            return False

    @property
    def n_articulos(self) -> int:
        """Número de artículos en el índice."""
        return len(self._ids)

    @property
    def construido(self) -> bool:
        return self._construido
