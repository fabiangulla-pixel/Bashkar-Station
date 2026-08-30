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

import os
from functools import lru_cache
from pathlib import Path

# Modelo BERT fine-tuned para NER en español (acceso público)
_MODELO_NER = "mrm8488/bert-spanish-cased-finetuned-ner"


def _ruta_cache_hf(modelo_id: str) -> Path:
    """Reproduce la ruta de caché de huggingface_hub (HUGGINGFACE_HUB_CACHE >
    HF_HOME/hub > default) SIN importar la librería — ver por qué en
    `_forzar_offline_si_ya_cacheado`."""
    override = os.environ.get("HUGGINGFACE_HUB_CACHE")
    if override:
        base = Path(override)
    else:
        home = os.environ.get("HF_HOME") or str(Path.home() / ".cache" / "huggingface")
        base = Path(home) / "hub"
    carpeta = "models--" + modelo_id.replace("/", "--")
    return base / carpeta


def _forzar_offline_si_ya_cacheado(modelo_id: str) -> None:
    """Si el modelo ya está en la caché local de HuggingFace, fuerza
    HF_HUB_OFFLINE=1 antes de cargarlo.

    Sin esto, from_pretrained() consulta el Hub para revalidar el ETag en
    CADA arranque aunque el modelo ya esté descargado — eso es lo que el
    usuario percibe como "Bashkar instala algo cada vez que lo abro"
    (reportado en sesión; mismo patrón ya aplicado en ocr_churro.py para
    CHURRO). Si no está cacheado, se QUITA la variable en vez de dejarla
    intacta: si otro modelo ya cacheado la puso en "1" antes en el mismo
    proceso, este modelo necesita red para su primera descarga real.

    El chequeo de caché se hace con `pathlib` puro, sin importar
    `huggingface_hub`: esa librería lee HF_HUB_OFFLINE del entorno UNA sola
    vez, como constante de módulo, en el momento en que se importa por
    primera vez en el proceso — fijar la variable de entorno DESPUÉS de ese
    import no tiene efecto (huggingface_hub 1.9.0, verificado). Con el orden
    anterior (importar la librería para preguntar si el modelo estaba
    cacheado, y solo ENTONCES fijar la variable), `pipeline()` seguía
    saliendo a red aunque el modelo ya estuviera descargado — y esa llamada
    de red terminaba con un access violation reproducible dentro de
    `socket.getaddrinfo` en Windows (sesión 63, 29-ago-2026; el segfault que
    sesión 62 le había atribuido a un conflicto de threading torch/tokenizers
    no era eso — no había conflicto de threading que reproducir)."""
    try:
        cacheado = any(_ruta_cache_hf(modelo_id).glob("snapshots/*/config.json"))
    except Exception:
        return
    if cacheado:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
    else:
        os.environ.pop("HF_HUB_OFFLINE", None)


# Se llama aquí, a nivel de módulo, no dentro de una función: tiene que
# ejecutarse en el momento en que este módulo se importa por primera vez,
# ANTES de que `roberta_disponible()` (más abajo) o cualquier otra función de
# este archivo hagan `import transformers` — ese import es justamente el que
# arrastra `huggingface_hub` y congela su constante de offline. Moverlo a
# dentro de `_pipeline_ner()`, después del `from transformers import
# pipeline`, no sirve: para entonces la constante ya quedó en False.
_forzar_offline_si_ya_cacheado(_MODELO_NER)

# Ventana deslizante: procesar texto largo en fragmentos de hasta
# _VENTANA_TOKENS subtokens (el límite real del modelo son 512 posiciones;
# se deja margen para [CLS]/[SEP] y algo de holgura), con solapamiento de
# _SOLAPE_TOKENS para no perder entidades en los límites.
#
# ANTES esta ventana se medía en PALABRAS (450 palabras, asumiendo ~1
# subtoken por palabra). Con texto OCR histórico real (números, mayúsculas
# sostenidas, guiones, ruido) el tokenizador WordPiece parte mucho más de lo
# esperado — medido sobre el corpus real de Estampa: ~1.4 subtokens por
# palabra, no ~1. El resultado: CADA fragmento de 450 "palabras" superaba
# los 512 subtokens y pipeline() reventaba con RuntimeError (tensor de N
# posiciones contra 512), silenciado por el `except Exception: continue` de
# más abajo — 171 de 171 fragmentos fallando en silencio sobre un número
# completo real (89 páginas), 0 entidades encontradas donde debería haber
# decenas (sesión 63, 29-ago-2026). Medir en subtokens reales, con el
# tokenizador del propio modelo, es la única forma de que esto no dependa de
# cuánto se fragmenta un texto en particular.
_VENTANA_TOKENS = 480
_SOLAPE_TOKENS  = 50

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

    # HF_HUB_OFFLINE ya se fijó a nivel de módulo, antes del import de arriba
    # — ver el comentario junto a la llamada de _forzar_offline_si_ya_cacheado
    # más abajo en este archivo.
    return pipeline(
        "ner",
        model=_MODELO_NER,
        aggregation_strategy="simple",
        device=-1,  # CPU; cambiar a 0 si hay GPU disponible
    )


def _fragmentar_por_tokens(texto: str, tokenizador) -> list[str]:
    """Parte `texto` en fragmentos que caben en _VENTANA_TOKENS subtokens del
    tokenizador REAL del modelo (no una cuenta de palabras — ver por qué en
    el comentario junto a _VENTANA_TOKENS). Decodifica cada trozo de vuelta a
    texto para poder seguir usando el pipeline de alto nivel de transformers,
    que espera texto de entrada."""
    ids = tokenizador(texto, add_special_tokens=False)["input_ids"]
    if len(ids) <= _VENTANA_TOKENS:
        return [texto]
    paso = _VENTANA_TOKENS - _SOLAPE_TOKENS
    return [
        tokenizador.decode(ids[inicio:inicio + _VENTANA_TOKENS], skip_special_tokens=True)
        for inicio in range(0, len(ids), paso)
    ]


def ner_roberta(texto: str,
                umbral_confianza: float = 0.60) -> list[dict]:
    """
    Extrae entidades nombradas con RoBERTa-BNE.

    Usa ventana deslizante (medida en subtokens reales del propio
    tokenizador, no en palabras) para textos largos. Deduplica entidades
    repetidas manteniendo la de mayor confianza.

    Args:
        texto:             Texto a analizar.
        umbral_confianza:  Ignorar entidades con confianza menor a este valor.

    Returns:
        Lista de dicts: {texto, categoria, confianza, fuente}

    Raises:
        ImportError: Si transformers/torch no están instalados.
    """
    nlp = _pipeline_ner()
    fragmentos = _fragmentar_por_tokens(texto, nlp.tokenizer)

    # Procesar todos los fragmentos y deduplicar
    vistas: dict[tuple, dict] = {}  # (texto_norm, categoria) → entidad de mayor confianza
    fallos = 0

    for frag in fragmentos:
        try:
            entidades = nlp(frag)
        except Exception:
            fallos += 1
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

    if fallos:
        # No debería pasar con la fragmentación por tokens de arriba, pero si
        # pasa NO puede quedar en silencio otra vez: eso fue exactamente lo
        # que dejó 171/171 fragmentos fallando sin que nadie se enterara
        # (sesión 63). Un RuntimeWarning aparece en consola/logs sin
        # necesitar tocar la firma de esta función para agregar un callback.
        import warnings
        warnings.warn(
            f"ner_roberta: {fallos}/{len(fragmentos)} fragmentos fallaron y se "
            "descartaron sin procesar (ver stacktrace con -W error si hace falta "
            "diagnosticar)",
            RuntimeWarning,
            stacklevel=2,
        )

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
