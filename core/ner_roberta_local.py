"""
core/ner_roberta_local.py — NER local con BERT-Spanish (español).

Modelo: mrm8488/bert-spanish-cased-finetuned-ner
  - Fine-tuned sobre CoNLL-2002 Spanish corpus
  - Categorías: PER, LOC, ORG, MISC
  - Primera ejecución descarga ~400 MB (se cachea en HuggingFace cache)
  - 100% offline después de la descarga inicial
  - Acceso público sin autenticación requerida

Instalación:
  pip install transformers torch

Ventajas sobre spaCy para este corpus:
  - Mejor manejo de nombres propios históricos y topónimos colombianos
  - No requiere modelo separado (se descarga automáticamente de HuggingFace)
"""

from functools import lru_cache
from typing import Optional

# Modelo BERT fine-tuned para NER en español (acceso público)
_MODELO_NER = "mrm8488/bert-spanish-cased-finetuned-ner"

# Ventana deslizante: procesar texto largo en fragmentos de 450 palabras
# con solapamiento de 50 para no perder entidades en los límites
_VENTANA = 450
_SOLAPE  = 50

# Mapeo de etiquetas del modelo a categorías de Bashkar
MAPA_CATEGORIAS = {
    "PER":  "personas",
    "LOC":  "lugares",
    "ORG":  "organizaciones",
    "MISC": "otros",
}


def roberta_disponible() -> bool:
    """True si transformers y torch están instalados."""
    try:
        import transformers  # noqa
        import torch  # noqa
        return True
    except ImportError:
        return False


@lru_cache(maxsize=1)
def _pipeline_ner():
    """Carga el pipeline NER con caché (se carga una sola vez por sesión)."""
    try:
        from transformers import pipeline
    except ImportError as e:
        raise ImportError(
            "transformers no está instalado. Ejecuta: pip install transformers torch"
        ) from e

    return pipeline(
        "ner",
        model=_MODELO_NER,
        aggregation_strategy="simple",
        device=-1,  # CPU; cambiar a 0 si hay GPU disponible
    )


def ner_roberta(texto: str,
                umbral_confianza: float = 0.60) -> list[dict]:
    """
    Extrae entidades nombradas con RoBERTa-BNE.

    Usa ventana deslizante para textos largos (>512 tokens ≈ ~400 palabras).
    Deduplica entidades repetidas manteniendo la de mayor confianza.

    Args:
        texto:             Texto a analizar.
        umbral_confianza:  Ignorar entidades con confianza menor a este valor.

    Returns:
        Lista de dicts: {texto, categoria, confianza, fuente}

    Raises:
        ImportError: Si transformers/torch no están instalados.
    """
    nlp = _pipeline_ner()
    palabras = texto.split()

    # Si el texto cabe en una ventana, procesarlo directo
    if len(palabras) <= _VENTANA:
        fragmentos = [texto]
    else:
        # Ventana deslizante con solapamiento
        fragmentos = []
        for inicio in range(0, len(palabras), _VENTANA - _SOLAPE):
            frag = " ".join(palabras[inicio:inicio + _VENTANA])
            fragmentos.append(frag)

    # Procesar todos los fragmentos y deduplicar
    vistas: dict[tuple, dict] = {}  # (texto_norm, categoria) → entidad de mayor confianza

    for frag in fragmentos:
        try:
            entidades = nlp(frag)
        except Exception:
            continue

        # Fusionar entidades consecutivas del mismo tipo cuyos tokens empiezan con ##
        # (artefacto de WordPiece cuando aggregation_strategy no fusiona completamente)
        fusionadas = []
        for ent in entidades:
            word = ent.get("word", "")
            label = ent.get("entity_group", ent.get("entity", "MISC"))
            if word.startswith("##") and fusionadas and fusionadas[-1].get("entity_group", "") == label:
                prev = fusionadas[-1]
                prev["word"] = prev["word"] + word[2:]
                prev["score"] = (prev["score"] + ent.get("score", 0.0)) / 2
                prev["end"] = ent.get("end", prev.get("end"))
            else:
                fusionadas.append(dict(ent))

        for ent in fusionadas:
            score = float(ent.get("score", 0.0))
            if score < umbral_confianza:
                continue

            label = ent.get("entity_group", ent.get("entity", "MISC"))
            categoria = MAPA_CATEGORIAS.get(label, "otros")
            texto_ent = ent.get("word", "").strip()

            # Limpiar artefactos del tokenizador (▁ de sentencepiece, ## de wordpiece)
            texto_ent = texto_ent.replace("▁", " ").replace("##", "").strip()

            if len(texto_ent) < 2:
                continue

            clave = (texto_ent.lower(), categoria)
            if clave not in vistas or score > vistas[clave]["confianza"]:
                vistas[clave] = {
                    "texto":     texto_ent,
                    "categoria": categoria,
                    "confianza": round(score, 4),
                    "fuente":    "roberta_bne",
                }

    return sorted(vistas.values(), key=lambda e: -e["confianza"])


def ner_roberta_a_indice(texto: str,
                          umbral_confianza: float = 0.60) -> dict:
    """
    Variante que retorna el mismo formato dict que spaCy pipeline_ner:
    {categoria: [lista_ordenada_de_strings]}

    Compatible con actualizar_indice_global() de ner_engine.py.
    """
    entidades = ner_roberta(texto, umbral_confianza)
    from core.ner_engine import CATEGORIAS
    indice = {cat: set() for cat in CATEGORIAS}

    for ent in entidades:
        cat = ent["categoria"]
        if cat in indice:
            indice[cat].add(ent["texto"])

    return {cat: sorted(indice[cat]) for cat in CATEGORIAS}


def precargar_modelo():
    """
    Precarga el modelo en memoria (descargando si es necesario).
    Útil para llamar al inicio de la app en un thread background.
    """
    try:
        _pipeline_ner()
        return True
    except Exception:
        return False
