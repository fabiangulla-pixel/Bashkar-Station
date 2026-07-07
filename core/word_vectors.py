"""
core/word_vectors.py — Modelos de vectores de palabras y expansión semántica.

Flujo:
  1. Entrenar Word2Vec sobre el corpus extraído.
     - Backend preferente: gensim (si está disponible).
     - Backend de respaldo: PyTorch skip-gram con negative sampling.
       Necesario en Python 3.14, donde gensim aún no compila (su código C
       usa API interna de CPython eliminada en 3.13+). Como torch ya es
       dependencia del proyecto (NER-BERT, FAISS), no añade nada nuevo.
  2. Expandir campos semánticos: dado un conjunto de semillas, encontrar
     los N vecinos más cercanos y añadirlos al campo.
  3. Calcular similaridad entre documentos usando promedio de vectores.

Ambos backends exponen la MISMA interfaz: un objeto con atributo `.wv` que
soporta `palabra in wv`, `wv[palabra] -> np.ndarray` y
`wv.most_similar(positive=[...], topn=...)`. El resto del módulo y la UI no
distinguen el backend.
"""

import gc
import re
from pathlib import Path

import numpy as np

# ── Preprocesamiento ──────────────────────────────────────────────────────────

_RE_TOKEN = re.compile(r"[a-záéíóúüñ]{3,}")

def _tokenizar(texto: str) -> list[str]:
    return _RE_TOKEN.findall(texto.lower())

def _tokenizar_oraciones(texto: str) -> list[list[str]]:
    """Divide en oraciones y tokeniza cada una (formato para Word2Vec)."""
    oraciones = re.split(r"[.!?;\n]{1,3}", texto)
    resultado = []
    for ora in oraciones:
        toks = _tokenizar(ora)
        if len(toks) >= 4:
            resultado.append(toks)
    return resultado


# ── KeyedVectors ligero (interfaz común a ambos backends) ─────────────────────

class _KeyedVectors:
    """
    Tabla de embeddings con la interfaz mínima que usa el resto del módulo
    y la UI (compatible con gensim.KeyedVectors):
      - `palabra in kv`
      - `kv[palabra] -> np.ndarray`
      - `kv.most_similar(positive=[...], topn=...) -> [(palabra, sim), ...]`

    Internamente guarda una matriz (n_palabras, dim) ya normalizada por fila,
    de modo que la similitud coseno es un simple producto punto.
    """

    def __init__(self, palabras: list[str], matriz: np.ndarray):
        self.index_to_key = list(palabras)
        self.key_to_index = {p: i for i, p in enumerate(palabras)}
        self.vectors = matriz.astype(np.float32)
        # Matriz normalizada por fila para coseno rápido
        normas = np.linalg.norm(self.vectors, axis=1, keepdims=True)
        normas[normas == 0] = 1.0
        self._unit = self.vectors / normas

    def __contains__(self, palabra: str) -> bool:
        return palabra in self.key_to_index

    def __len__(self) -> int:
        return len(self.index_to_key)

    def __getitem__(self, palabra: str) -> np.ndarray:
        return self.vectors[self.key_to_index[palabra]]

    def most_similar(self, positive=None, topn: int = 10):
        if isinstance(positive, str):
            positive = [positive]
        positive = [p for p in (positive or []) if p in self.key_to_index]
        if not positive:
            return []
        idxs = [self.key_to_index[p] for p in positive]
        centroide = self._unit[idxs].mean(axis=0)
        n = np.linalg.norm(centroide)
        if n == 0:
            return []
        centroide = centroide / n
        sims = self._unit @ centroide          # coseno contra todo el vocab
        orden = np.argsort(-sims)
        excluir = set(idxs)
        salida = []
        for i in orden:
            if i in excluir:
                continue
            salida.append((self.index_to_key[i], float(sims[i])))
            if len(salida) >= topn:
                break
        return salida

    def guardar(self, ruta: Path):
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            str(ruta),
            palabras=np.array(self.index_to_key, dtype=object),
            vectors=self.vectors,
        )

    @staticmethod
    def cargar(ruta: Path) -> "_KeyedVectors":
        data = np.load(str(ruta), allow_pickle=True)
        return _KeyedVectors(list(data["palabras"]), data["vectors"])


class _ModeloVectores:
    """Envoltorio con atributo `.wv`, igual que un modelo gensim Word2Vec."""

    def __init__(self, wv: _KeyedVectors):
        self.wv = wv


# ── Entrenamiento Word2Vec ────────────────────────────────────────────────────

def entrenar_word2vec(
    corpus_textos: list[str],
    output_path: Path,
    vector_size: int = 150,
    window: int = 6,
    min_count: int = 3,
    epochs: int = 12,
    workers: int = 4,
) -> object:
    """
    Entrena Word2Vec (skip-gram) sobre el corpus y guarda el modelo.

    Usa gensim si está disponible; si no (p.ej. Python 3.14), entrena con
    PyTorch. Devuelve un objeto con `.wv`, o None si no hay material suficiente
    ni backend disponible.
    """
    oraciones = []
    for texto in corpus_textos:
        oraciones.extend(_tokenizar_oraciones(texto))
    if len(oraciones) < 10:
        return None

    # Backend 1: gensim
    try:
        from gensim.models import Word2Vec
        model = Word2Vec(
            sentences=oraciones,
            vector_size=vector_size,
            window=window,
            min_count=min_count,
            workers=workers,
            epochs=epochs,
            sg=1,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        model.save(str(output_path))
        gc.collect()
        return model
    except ImportError:
        pass

    # Backend 2: PyTorch
    wv = _entrenar_torch(
        oraciones, vector_size=vector_size, window=window,
        min_count=min_count, epochs=epochs,
    )
    if wv is None:
        return None
    # Guardar junto al output_path con extensión .npz (formato propio)
    wv.guardar(Path(str(output_path) + ".npz"))
    gc.collect()
    return _ModeloVectores(wv)


def _entrenar_torch(
    oraciones: list[list[str]],
    vector_size: int = 150,
    window: int = 6,
    min_count: int = 3,
    epochs: int = 12,
    neg_samples: int = 5,
    lr: float = 0.025,
) -> "_KeyedVectors | None":
    """
    Skip-gram con negative sampling en PyTorch. Pensado para corpus pequeños
    (decenas de miles de oraciones) sobre CPU; entrena en segundos.
    """
    try:
        import torch
    except ImportError:
        return None

    from collections import Counter

    # Vocabulario con poda por frecuencia
    cont = Counter(tok for ora in oraciones for tok in ora)
    vocab = [w for w, c in cont.items() if c >= min_count]
    if len(vocab) < 5:
        return None
    w2i = {w: i for i, w in enumerate(vocab)}
    V = len(vocab)

    # Distribución de negative sampling ∝ freq^0.75 (como Word2Vec original)
    freqs = np.array([cont[w] for w in vocab], dtype=np.float64) ** 0.75
    neg_prob = torch.tensor(freqs / freqs.sum(), dtype=torch.float)

    # Pares (centro, contexto)
    centros, contextos = [], []
    for ora in oraciones:
        ids = [w2i[t] for t in ora if t in w2i]
        for pos, c in enumerate(ids):
            ini = max(0, pos - window)
            fin = min(len(ids), pos + window + 1)
            for j in range(ini, fin):
                if j != pos:
                    centros.append(c)
                    contextos.append(ids[j])
    if not centros:
        return None

    centros_t = torch.tensor(centros, dtype=torch.long)
    contextos_t = torch.tensor(contextos, dtype=torch.long)
    n_pares = len(centros)

    torch.manual_seed(42)
    emb_in = torch.nn.Embedding(V, vector_size)
    emb_out = torch.nn.Embedding(V, vector_size)
    torch.nn.init.uniform_(emb_in.weight, -0.5 / vector_size, 0.5 / vector_size)
    torch.nn.init.zeros_(emb_out.weight)
    opt = torch.optim.Adam(list(emb_in.parameters()) + list(emb_out.parameters()), lr=lr)

    batch = 4096
    for _ep in range(epochs):
        perm = torch.randperm(n_pares)
        for k in range(0, n_pares, batch):
            sel = perm[k:k + batch]
            ci = centros_t[sel]
            co = contextos_t[sel]
            v_c = emb_in(ci)                                  # (B, D)
            v_o = emb_out(co)                                 # (B, D)
            # positivos
            pos_score = torch.nn.functional.logsigmoid((v_c * v_o).sum(1))
            # negativos
            neg = torch.multinomial(neg_prob, len(sel) * neg_samples,
                                    replacement=True).view(len(sel), neg_samples)
            v_neg = emb_out(neg)                              # (B, K, D)
            neg_score = torch.nn.functional.logsigmoid(
                -(v_neg * v_c.unsqueeze(1)).sum(2)).sum(1)
            loss = -(pos_score + neg_score).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()

    matriz = emb_in.weight.detach().cpu().numpy()
    return _KeyedVectors(vocab, matriz)


def cargar_word2vec(model_path: Path) -> object:
    """Carga un modelo Word2Vec guardado (gensim o backend PyTorch propio)."""
    # gensim
    try:
        from gensim.models import Word2Vec
        return Word2Vec.load(str(model_path))
    except Exception:
        pass
    # backend propio (.npz junto al path)
    for cand in (Path(str(model_path) + ".npz"), Path(model_path)):
        if cand.exists() and cand.suffix == ".npz":
            try:
                return _ModeloVectores(_KeyedVectors.cargar(cand))
            except Exception:
                continue
    return None


def cargar_modelo_externo(path: Path) -> object:
    """
    Carga un modelo Word2Vec/fastText en formato binario (.bin) o texto (.vec/.txt).
    """
    try:
        from gensim.models import KeyedVectors
        binary = path.suffix.lower() == ".bin"
        return KeyedVectors.load_word2vec_format(str(path), binary=binary)
    except Exception:
        return None


# ── Expansión semántica ───────────────────────────────────────────────────────

def expandir_campo_semantico(
    semillas: list[str],
    modelo,
    topn: int = 15,
    umbral_sim: float = 0.35,
) -> dict:
    """
    Dado un campo semántico definido por 'semillas', devuelve un dict con:
      - semillas_encontradas: cuáles semillas existen en el vocabulario
      - expansiones: lista de (palabra, similaridad) ordenada por sim
      - campo_expandido: unión de semillas + expansiones (para uso en análisis)
    """
    result = {
        "semillas_encontradas": [],
        "expansiones": [],
        "campo_expandido": list(semillas),
    }

    # Obtener el objeto wv (KeyedVectors) independientemente del tipo de modelo
    try:
        wv = getattr(modelo, "wv", modelo)
    except Exception:
        return result

    semillas_ok = [s for s in semillas if s in wv]
    result["semillas_encontradas"] = semillas_ok

    if not semillas_ok:
        return result

    # Buscar similares al centroide de las semillas
    try:
        similares = wv.most_similar(positive=semillas_ok, topn=topn * 2)
    except Exception:
        return result

    expansiones = [
        (palabra, round(float(sim), 3))
        for palabra, sim in similares
        if sim >= umbral_sim and palabra not in semillas
    ][:topn]

    result["expansiones"]    = expansiones
    result["campo_expandido"] = list(set(semillas) | {p for p, _ in expansiones})
    return result


def calcular_densidad_semantica(
    texto: str,
    campo_expandido: list[str],
) -> float:
    """
    Calcula la densidad del campo semántico en el texto como
    menciones_por_1000_palabras.
    """
    tokens = _tokenizar(texto)
    n = max(len(tokens), 1)
    campo_set = set(campo_expandido)
    menciones = sum(1 for t in tokens if t in campo_set)
    return round(menciones / n * 1000, 2)


# ── Similaridad de documentos ─────────────────────────────────────────────────

def _doc_vector(texto: str, wv) -> np.ndarray | None:
    tokens = [t for t in _tokenizar(texto) if t in wv]
    if not tokens:
        return None
    vecs = np.array([wv[t] for t in tokens])
    return vecs.mean(axis=0)


def similaridad_coseno(texto_a: str, texto_b: str, modelo) -> float:
    """Retorna similitud coseno entre dos textos usando promedios de vectores."""
    try:
        wv = getattr(modelo, "wv", modelo)
        va = _doc_vector(texto_a, wv)
        vb = _doc_vector(texto_b, wv)
        if va is None or vb is None:
            return 0.0
        na = np.linalg.norm(va)
        nb = np.linalg.norm(vb)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(va, vb) / (na * nb))
    except Exception:
        return 0.0


def matriz_similaridad(textos: list[str], nombres: list[str], modelo) -> list[dict]:
    """
    Calcula la matriz de similaridad coseno entre todos los textos.
    Retorna lista de dicts {nombre_a, nombre_b, similaridad}.
    """
    try:
        wv = getattr(modelo, "wv", modelo)
        vecs = [(n, _doc_vector(t, wv)) for n, t in zip(nombres, textos)]
        rows = []
        for i, (na, va) in enumerate(vecs):
            for j, (nb, vb) in enumerate(vecs):
                if j <= i:
                    continue
                if va is None or vb is None:
                    sim = 0.0
                else:
                    norma = np.linalg.norm(va) * np.linalg.norm(vb)
                    sim = float(np.dot(va, vb) / norma) if norma > 0 else 0.0
                rows.append({"corpus_a": na, "corpus_b": nb,
                             "similaridad": round(sim, 3)})
        return rows
    except Exception:
        return []


# ── Nube de palabras por campo ────────────────────────────────────────────────

def frecuencias_campo(corpus: list[str], campo: list[str]) -> list[tuple[str, int]]:
    """Cuenta frecuencia de cada término del campo expandido en el corpus."""
    campo_set = set(campo)
    freq = {}
    for texto in corpus:
        for t in _tokenizar(texto):
            if t in campo_set:
                freq[t] = freq.get(t, 0) + 1
    return sorted(freq.items(), key=lambda x: -x[1])
