"""core/servicios_ner.py — NER sobre un corpus, igual en escritorio, CLI y API.

Hasta la sesión 72 había tres bucles de NER de corpus: el del escritorio
(``paneles/entidades.py``), el de ``cli.py`` y el de ``servidor_web.py``. Los
tres llamaban a ``pipeline_ner``, pero con parámetros distintos: solo el
escritorio descartaba textos de menos de ``min_palabras`` y aplicaba el umbral
de confianza, y cada uno cargaba un modelo de spaCy distinto. El mismo corpus
daba índices distintos según desde dónde se corriera.
"""

from __future__ import annotations

from typing import Callable, Iterable

MODELOS_SPACY = ("es_core_news_lg", "es_core_news_md", "es_core_news_sm")


def cargar_spacy(motor: str = "auto"):
    """El modelo de spaCy más grande instalado, o None (RoBERTa no lo necesita)."""
    if motor == "fallback":
        return None
    try:
        import spacy
    except ImportError:
        return None
    for nombre in MODELOS_SPACY:
        try:
            return spacy.load(nombre)
        except OSError:
            continue
    return None


def textos_de_articulos(articulos: Iterable[dict], min_palabras: int = 100) -> list[tuple[str, str]]:
    """``[(id, texto)]`` con los textos que alcanzan ``min_palabras``."""
    salida = []
    for i, a in enumerate(articulos):
        txt = str(a.get("texto") or a.get("contenido") or a.get("ocr_limpio") or "")
        aid = str(a.get("id") or a.get("titulo") or f"art_{i}")
        if txt.strip() and len(txt.split()) >= min_palabras:
            salida.append((aid, txt))
    return salida


def ner_corpus(textos: list[tuple[str, str]], *, motor: str = "auto", nlp=None,
               umbral_confianza: float = 0.7, categorias: list | None = None,
               api_key: str | None = None, proveedor_llm: str = "claude",
               modelo_ollama: str = "latamgpt",
               progreso: Callable[[int, int, str], None] | None = None,
               indice: dict | None = None) -> dict:
    """Índice NER global de ``textos``. ``motor``: auto | roberta | spacy | fallback.

    Si ``motor == "spacy"`` y spaCy no está, lanza RuntimeError: pedir spaCy
    y recibir otra cosa en silencio cambiaría los resultados sin avisar.
    """
    from core.ner_engine import actualizar_indice_global, indice_global_vacio, pipeline_ner

    if nlp is None:
        nlp = cargar_spacy(motor)
        if nlp is None and motor == "spacy":
            raise RuntimeError("spaCy no está instalado: python -m spacy download es_core_news_lg")
    indice = indice if indice is not None else indice_global_vacio()
    total = len(textos)
    for i, (aid, txt) in enumerate(textos, 1):
        if progreso:
            progreso(i, total, aid)
        ner = pipeline_ner(txt, nlp, api_key=api_key, umbral_confianza=umbral_confianza,
                           categorias=categorias, proveedor_llm=proveedor_llm,
                           modelo_ollama=modelo_ollama,
                           usar_roberta=motor not in ("spacy", "fallback"))
        actualizar_indice_global(indice, aid, ner)
    return indice


def contar_entidades(indice: dict) -> int:
    return sum(len(v) for v in (indice or {}).values() if isinstance(v, dict))
