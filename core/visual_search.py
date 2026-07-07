"""core/visual_search.py — Búsqueda visual por similitud (estilo Newspaper Navigator).

Usa CLIP (openai/clip-vit-base-patch32) via HuggingFace para generar embeddings
de imagen, y FAISS para búsqueda eficiente por similitud coseno.

100% offline una vez descargado el modelo (~600 MB).
No envía datos a ningún servidor externo.

Funciones principales:
  indexar_imagenes()    — procesa carpeta/lista de imágenes → índice FAISS
  buscar_similares()    — dada una imagen query, retorna las N más similares
  buscar_por_texto()    — búsqueda CLIP text→image ("fotografía de mujer 1930s")
  guardar_indice()      — persiste índice + metadatos
  cargar_indice()       — carga índice existente
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Callable
import numpy as np


_MODELO_CLIP = "openai/clip-vit-base-patch32"
_DIM_CLIP = 512


def _cargar_clip():
    """Carga el modelo CLIP. Descarga ~600 MB la primera vez."""
    try:
        from transformers import CLIPProcessor, CLIPModel
        import torch
    except ImportError:
        raise ImportError(
            "Instala: pip install transformers torch\n"
            "El modelo CLIP requiere ~600 MB la primera vez."
        )
    modelo = CLIPModel.from_pretrained(_MODELO_CLIP)
    proc   = CLIPProcessor.from_pretrained(_MODELO_CLIP)
    modelo.eval()
    return modelo, proc


def _embedding_imagen(ruta: str, modelo, proc) -> Optional[np.ndarray]:
    """Genera embedding CLIP de una imagen. Retorna None si falla."""
    try:
        from PIL import Image
        import torch
        img    = Image.open(ruta).convert("RGB")
        inputs = proc(images=img, return_tensors="pt")
        with torch.no_grad():
            feats = modelo.get_image_features(**inputs)
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats[0].numpy()
    except Exception:
        return None


def _embedding_texto(texto: str, modelo, proc) -> np.ndarray:
    """Genera embedding CLIP de un texto para búsqueda cross-modal."""
    import torch
    inputs = proc(text=[texto], return_tensors="pt", padding=True, truncation=True)
    with torch.no_grad():
        feats = modelo.get_text_features(**inputs)
        feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats[0].numpy()


class IndiceVisual:
    """Índice FAISS de embeddings de imagen con metadatos."""

    def __init__(self):
        self.embeddings: list[np.ndarray] = []
        self.metadatos:  list[dict] = []
        self._index = None

    def _construir_faiss(self):
        try:
            import faiss
        except ImportError:
            raise ImportError("Instala faiss-cpu: pip install faiss-cpu")
        if not self.embeddings:
            return
        matriz = np.vstack(self.embeddings).astype("float32")
        idx = faiss.IndexFlatIP(_DIM_CLIP)
        idx.add(matriz)
        self._index = idx

    def agregar(self, embedding: np.ndarray, meta: dict):
        self.embeddings.append(embedding.astype("float32"))
        self.metadatos.append(meta)
        self._index = None  # invalidar índice

    def buscar(self, query_emb: np.ndarray, top_k: int = 10) -> list[dict]:
        """Retorna los top_k más similares al query_emb."""
        if self._index is None:
            self._construir_faiss()
        if self._index is None or self._index.ntotal == 0:
            return []
        import faiss
        q = query_emb.astype("float32").reshape(1, -1)
        faiss.normalize_L2(q)
        D, I = self._index.search(q, min(top_k, self._index.ntotal))
        resultados = []
        for dist, idx in zip(D[0], I[0]):
            if idx < 0:
                continue
            r = dict(self.metadatos[idx])
            r["similitud"] = float(dist)
            resultados.append(r)
        return resultados

    def guardar(self, ruta_base: str | Path):
        """Guarda índice FAISS + metadatos en disco."""
        ruta_base = Path(ruta_base)
        ruta_base.parent.mkdir(parents=True, exist_ok=True)
        if self._index is None:
            self._construir_faiss()
        if self._index is not None:
            import faiss
            faiss.write_index(self._index, str(ruta_base) + ".faiss")
        with open(str(ruta_base) + ".meta.json", "w", encoding="utf-8") as f:
            json.dump(self.metadatos, f, ensure_ascii=False)
        np.save(str(ruta_base) + ".npy", np.vstack(self.embeddings))

    @classmethod
    def cargar(cls, ruta_base: str | Path) -> "IndiceVisual":
        ruta_base = Path(ruta_base)
        inst = cls()
        emb_path = str(ruta_base) + ".npy"
        meta_path = str(ruta_base) + ".meta.json"
        faiss_path = str(ruta_base) + ".faiss"
        if not Path(meta_path).exists():
            raise FileNotFoundError(f"No se encontró el índice en {ruta_base}")
        with open(meta_path, encoding="utf-8") as f:
            inst.metadatos = json.load(f)
        if Path(emb_path).exists():
            inst.embeddings = list(np.load(emb_path))
        if Path(faiss_path).exists():
            import faiss
            inst._index = faiss.read_index(faiss_path)
        return inst

    def __len__(self):
        return len(self.metadatos)


def indexar_imagenes(
    rutas: list[str],
    metadatos_extra: Optional[list[dict]] = None,
    callback: Optional[Callable[[int, int, str], None]] = None,
) -> IndiceVisual:
    """
    Genera embeddings CLIP para una lista de imágenes y construye un IndiceVisual.

    metadatos_extra: lista paralela a rutas con dicts de metadatos adicionales
                     (número, página, tipo_zona, etc.)
    """
    modelo, proc = _cargar_clip()
    indice = IndiceVisual()
    total  = len(rutas)

    for i, ruta in enumerate(rutas):
        if callback:
            callback(i + 1, total, ruta)
        emb = _embedding_imagen(ruta, modelo, proc)
        if emb is None:
            continue
        meta = {"ruta": ruta, "idx": i}
        if metadatos_extra and i < len(metadatos_extra):
            meta.update(metadatos_extra[i])
        indice.agregar(emb, meta)

    indice._construir_faiss()
    return indice


def buscar_similares(
    ruta_query: str,
    indice: IndiceVisual,
    top_k: int = 10,
) -> list[dict]:
    """
    Dada una imagen query, retorna las top_k imágenes más similares del índice.
    """
    modelo, proc = _cargar_clip()
    emb = _embedding_imagen(ruta_query, modelo, proc)
    if emb is None:
        return []
    return indice.buscar(emb, top_k)


def buscar_por_texto(
    texto: str,
    indice: IndiceVisual,
    top_k: int = 10,
) -> list[dict]:
    """
    Búsqueda cross-modal: texto → imágenes similares.
    Ej: "fotografía de mujer elegante años 30" → devuelve imágenes del corpus.
    """
    modelo, proc = _cargar_clip()
    emb = _embedding_texto(texto, modelo, proc)
    return indice.buscar(emb, top_k)


def clip_disponible() -> bool:
    """True si transformers y torch están instalados."""
    try:
        import transformers
        import torch
        return True
    except ImportError:
        return False
