"""
core/entity_linker.py — Entity linking a Wikidata para entidades NER.

Estrategia:
  1. Búsqueda via API pública de Wikidata (wbsearchentities) — sin autenticación.
  2. Caché local SQLite para no repetir llamadas entre sesiones.
  3. Filtrado por tipo de entidad (humano, lugar, org) para reducir falsos positivos.
  4. Desambiguación por contexto: favorece candidatos con descripción que coincida
     con el tipo de entidad NER y con el período histórico 1930-1940.
  5. Funciona 100% offline si las entidades ya están en caché.

Dependencias: solo stdlib (urllib, sqlite3, json) — sin pip adicional.
"""

import json
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

# Palabras (con tildes/ñ) para el solapamiento descripción↔contexto del artículo
_RE_PALABRA = re.compile(r"[a-zá-úñü]+", re.IGNORECASE)


# --- Constantes ---------------------------------------------------------------

_API_WIKIDATA = "https://www.wikidata.org/w/api.php"
_API_WIKIPEDIA_ES = "https://es.wikipedia.org/w/api.php"

# Tiempo máximo de espera por petición HTTP (segundos)
_TIMEOUT_HTTP = 10

# Pausa entre llamadas a la API para respetar los rate limits de Wikidata
_PAUSA_ENTRE_LLAMADAS = 0.5

# Versión del algoritmo de desambiguación. Se guarda junto a cada resultado en
# caché; cuando subimos esta versión (porque mejoramos el scoring), las entradas
# viejas se IGNORAN y se vuelven a enlazar. Así una mejora del algoritmo no queda
# enmascarada por resultados malos cacheados de antes. (Mejora #4)
#   v1 → desambiguación previa a sesión 35
#   v2 → fix sesión 35 (uselang=es, rango, P31, descarte homónimos)
#   v3 → sesión 42: contexto LLM, ventana histórica 1930-40, filtro basura OCR
_ALGO_VERSION = 3

# Período histórico del corpus (revista Estampa, Colombia). Una entidad cuya
# fecha de nacimiento/fundación sea MUY posterior no puede ser la que cita la
# prensa de los años 30: se penaliza al desambiguar homónimos modernos. (#3)
_ANIO_CORPUS_FIN = 1945    # margen sobre 1940 para no excluir contemporáneos
_ANIO_CORPUS_INI = 1700    # cota inferior holgada (personajes ya nacidos)

# Longitud mínima de una entidad para intentar enlazarla. Fragmentos OCR muy
# cortos ("Bogo", "Cal") generan enlaces espurios; se descartan. (#2)
_MIN_LEN_ENTIDAD = 4

# Confianza mínima para CONSERVAR un enlace. Por debajo de este umbral el enlace
# es demasiado dudoso y se trata como "no encontrado" (evita ruido en el corpus). (#2)
_CONF_MINIMA = 0.45

# Tipos Wikidata por categoría NER
# P31 = "instancia de", Q5 = humano, Q515 = ciudad, Q6256 = país, etc.
_TIPOS_WIKIDATA = {
    "personas":       ["Q5"],                        # humano
    "lugares":        ["Q515", "Q6256", "Q35657",    # ciudad, país, estado
                       "Q3957", "Q532", "Q486972",   # pueblo, aldea, asentamiento
                       "Q82794"],                    # región geográfica
    "organizaciones": ["Q43229", "Q7210356",         # organización, organización política
                       "Q31855", "Q2385804",         # institución educativa, institución
                       "Q1114461", "Q1093829"],      # cámara, municipio
    "obras_publicaciones": ["Q571", "Q11032",        # libro, periódico
                            "Q732577", "Q13442814"], # publicación, artículo académico
}

# Ruta por defecto para la caché (en el mismo directorio que el módulo)
_CACHE_DEFAULT = Path(__file__).parent.parent / "datos" / "entity_cache.db"


# --- Caché local --------------------------------------------------------------

class _CacheEntidades:
    """Caché SQLite para resultados de Wikidata."""

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS cache_wikidata (
        texto       TEXT NOT NULL,
        categoria   TEXT NOT NULL,
        resultado   TEXT,          -- JSON con el resultado o NULL si no se encontró
        consultado  REAL NOT NULL,
        algo_version INTEGER DEFAULT 0,  -- versión del algoritmo que produjo el dato
        PRIMARY KEY (texto, categoria)
    );
    """

    def __init__(self, ruta: str):
        self._ruta = ruta
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(ruta, check_same_thread=False)
        self._con.execute(self._SCHEMA)
        # Migración suave: añadir algo_version si la caché es de una versión
        # anterior del módulo (tablas creadas sin esa columna).
        cols = {r[1] for r in self._con.execute("PRAGMA table_info(cache_wikidata)")}
        if "algo_version" not in cols:
            self._con.execute(
                "ALTER TABLE cache_wikidata ADD COLUMN algo_version INTEGER DEFAULT 0"
            )
        self._con.commit()

    def obtener(self, texto: str, categoria: str) -> Optional[dict]:
        """None = no está en caché (o cacheado por un algoritmo viejo, hay que
        re-enlazar); dict vacío {} = consultado con el algoritmo actual y no
        encontrado."""
        cur = self._con.execute(
            "SELECT resultado, algo_version FROM cache_wikidata "
            "WHERE texto=? AND categoria=?",
            (texto, categoria),
        )
        fila = cur.fetchone()
        if fila is None:
            return None  # no está en caché
        # Si fue producido por una versión anterior del algoritmo, lo tratamos
        # como ausente para forzar el re-enlace con la lógica mejorada. (#4)
        if (fila[1] or 0) < _ALGO_VERSION:
            return None
        return json.loads(fila[0]) if fila[0] else {}

    def guardar(self, texto: str, categoria: str, resultado: Optional[dict]):
        val = json.dumps(resultado, ensure_ascii=False) if resultado else None
        self._con.execute(
            "INSERT OR REPLACE INTO cache_wikidata"
            "(texto, categoria, resultado, consultado, algo_version)"
            " VALUES (?,?,?,?,?)",
            (texto, categoria, val, time.time(), _ALGO_VERSION),
        )
        self._con.commit()

    def estadisticas(self) -> dict:
        cur = self._con.execute(
            "SELECT COUNT(*), SUM(resultado IS NOT NULL AND resultado != 'null') "
            "FROM cache_wikidata"
        )
        total, encontrados = cur.fetchone()
        return {"total": total or 0, "encontrados": encontrados or 0}

    def limpiar(self, dias: int = 90):
        """Elimina entradas con más de `dias` días de antigüedad."""
        limite = time.time() - dias * 86400
        self._con.execute(
            "DELETE FROM cache_wikidata WHERE consultado < ?", (limite,)
        )
        self._con.commit()


# Instancia global de caché (se inicializa con la ruta por defecto)
_cache: Optional[_CacheEntidades] = None


def _obtener_cache(ruta: Optional[str] = None) -> _CacheEntidades:
    global _cache
    if _cache is None or (ruta and ruta != str(_CACHE_DEFAULT)):
        _cache = _CacheEntidades(ruta or str(_CACHE_DEFAULT))
    return _cache


# --- Lógica de linking --------------------------------------------------------

def _llamar_wikidata(texto: str, tipo_entidad: str, lang: str = "es") -> list[dict]:
    """
    Llama a wbsearchentities de Wikidata.
    Retorna lista de candidatos [{id, label, description, url, rango}].

    `rango` = posición en el ranking de Wikidata (0 = el más relevante).
    Wikidata ordena por número de enlaces/sitelinks, así que el orden es una
    señal fuerte de cuál es la acepción más conocida.
    """
    params = {
        "action":   "wbsearchentities",
        "format":   "json",
        "search":   texto,
        "language": lang,
        "uselang":  lang,    # ← descripciones en el idioma pedido (no inglés)
        "limit":    "8",
        "type":     "item",
    }
    url = _API_WIKIDATA + "?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": "BashkarStation/1.0 (contact: bashkar@icc.gov.co)"}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=_TIMEOUT_HTTP) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return []

    candidatos = []
    for rango, item in enumerate(data.get("search", [])):
        candidatos.append({
            "id":          item.get("id", ""),
            "label":       item.get("label", texto),
            "description": item.get("description", ""),
            "url":         item.get("concepturi", ""),
            "rango":       rango,
        })
    return candidatos


def _obtener_p31(qid: str) -> list[str]:
    """
    Devuelve los QIDs de 'instancia de' (P31) de una entidad — su(s) tipo(s).
    Permite descartar candidatos del tipo equivocado (un apellido, una pintura,
    un barco) cuando el NER esperaba una persona/lugar/organización.
    Vacío si falla la consulta (degradación sin red).
    """
    params = {
        "action":   "wbgetclaims",
        "format":   "json",
        "entity":   qid,
        "property": "P31",
    }
    url = _API_WIKIDATA + "?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": "BashkarStation/1.0 (contact: bashkar@icc.gov.co)"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=_TIMEOUT_HTTP) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return []
    tipos = []
    for claim in data.get("claims", {}).get("P31", []):
        try:
            tipos.append(claim["mainsnak"]["datavalue"]["value"]["id"])
        except (KeyError, TypeError):
            pass
    return tipos


def _anio_de_claim(claims: dict, prop: str) -> Optional[int]:
    """Extrae el AÑO de una propiedad de fecha de Wikidata (P569 nacimiento,
    P571 fundación, P580 inicio). Devuelve None si no está o no se parsea."""
    for claim in claims.get(prop, []):
        try:
            t = claim["mainsnak"]["datavalue"]["value"]["time"]  # ej '+1934-08-07T..'
            # Formato: +YYYY-MM-DD...  (el año puede llevar signo y ceros)
            anio = int(t.lstrip("+").split("-")[0])
            return anio
        except (KeyError, TypeError, ValueError, IndexError):
            continue
    return None


def _obtener_fecha_relevante(qid: str) -> Optional[int]:
    """Año relevante de la entidad para ubicarla en el tiempo: nacimiento (P569)
    para personas, fundación/inicio (P571/P580) para lugares/organizaciones.
    Permite descartar homónimos MODERNOS que no existían en la época del corpus.
    Devuelve None si no se puede obtener (degradación sin red, sin penalizar). (#3)
    """
    params = {
        "action": "wbgetclaims", "format": "json", "entity": qid,
    }
    url = _API_WIKIDATA + "?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": "BashkarStation/1.0 (contact: bashkar@icc.gov.co)"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=_TIMEOUT_HTTP) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return None
    claims = data.get("claims", {})
    for prop in ("P569", "P571", "P580"):   # nacimiento, fundación, inicio
        anio = _anio_de_claim(claims, prop)
        if anio is not None:
            return anio
    return None


# Descripciones que delatan que un candidato NO es la entidad buscada sino
# un homónimo de otro tipo (apellido, nombre de pila, barco, pintura, calle…).
_DESC_DESCARTE = (
    "apellido", "family name", "surname", "nombre de pila", "given name",
    "pintura", "painting", "escultura", "sculpture", "monumento", "monument",
    "buque", "barco", "battleship", "acorazado", "ship",
    "película", "film", "álbum", "album", "canción", "song",
    "estación de metro", "metro station", "calle", "street",
    "equipo ciclista", "cycling team", "personaje", "ficticio", "fictional",
)

# Tipos P31 aceptables por categoría NER. Si el candidato top tiene P31 y
# ninguno cae aquí, se rechaza (era un homónimo del tipo equivocado).
_P31_VALIDOS = {
    "personas":       {"Q5"},                                  # humano
    "lugares":        {"Q515", "Q6256", "Q35657", "Q3957",     # ciudad, país, estado, pueblo
                       "Q532", "Q486972", "Q82794", "Q15284",  # aldea, asentamiento, región, municipio
                       "Q1549591", "Q1637706"},                # gran ciudad, millón-hab
    "organizaciones": {"Q43229", "Q7210356", "Q31855",         # organización, org. política, inst.
                       "Q2385804", "Q1114461", "Q1093829",
                       "Q3918", "Q875538", "Q207320",          # universidad, univ. pública, partido
                       "Q4830453", "Q163740"},                 # empresa, sin ánimo de lucro
    "obras_publicaciones": {"Q571", "Q11032", "Q732577",       # libro, periódico, publicación
                            "Q13442814", "Q5633421"},          # artículo, revista
}


def _puntuar_candidato(candidato: dict, texto: str, categoria: str,
                       contexto: str = "") -> float:
    """
    Puntúa un candidato de Wikidata. El criterio dominante es el RANGO de
    Wikidata (orden por relevancia/enlaces): la primera acepción es casi
    siempre la más conocida, que es la que cita la prensa de 1939.

    Criterios:
      base 2.0 - rango*0.6   → premia fuertemente las primeras acepciones
      +1.0  label coincide exactamente (case-insensitive)
      +0.6  descripción coincide con el tipo de entidad esperado
      +0.4  descripción menciona Colombia / período (desempate, no dominante)
      +0.8  palabras de la descripción aparecen en el CONTEXTO del artículo
             (desambiguación contextual: distingue "Alfonso López" presidente
              colombiano de su homónimo deportista según de qué habla la nota) (#1)
      -3.0  descripción delata homónimo de otro tipo (apellido, barco, pintura…)
    """
    score = 0.0
    label = candidato.get("label", "").lower()
    desc  = candidato.get("description", "").lower()
    texto_l = texto.lower()
    rango = candidato.get("rango", 0)

    # Señal principal: posición en el ranking de Wikidata
    score += 2.0 - rango * 0.6

    if label == texto_l:
        score += 1.0
    elif texto_l in label or label in texto_l:
        score += 0.3

    # Desambiguación contextual (#1): solapamiento entre las palabras de
    # contenido de la descripción del candidato y el texto del artículo donde
    # aparece la entidad. Si la nota habla de "presidente", "Colombia",
    # "gobierno" y la descripción del candidato también, es el correcto.
    if contexto and desc:
        ctx = contexto.lower()
        palabras_desc = {w for w in _RE_PALABRA.findall(desc) if len(w) > 3}
        coincidencias = sum(1 for w in palabras_desc if w in ctx)
        if coincidencias:
            score += min(0.8, 0.25 * coincidencias)

    # Descarte fuerte de homónimos de otro tipo
    if any(t in desc for t in _DESC_DESCARTE):
        score -= 3.0

    # Coincidencia con el tipo de entidad esperado (en español, ya que uselang=es)
    tipo_desc = {
        "personas":       ["político", "escritor", "periodista", "poeta", "historiador",
                           "abogado", "militar", "dictador", "general", "presidente",
                           "diplomático", "pintor", "artista", "filósofo", "compositor"],
        "lugares":        ["ciudad", "municipio", "departamento", "país", "región",
                           "capital", "provincia", "comunidad autónoma", "estado"],
        "organizaciones": ["organización", "institución", "universidad", "partido",
                           "periódico", "revista", "empresa", "club"],
    }
    for palabra in tipo_desc.get(categoria, []):
        if palabra in desc:
            score += 0.6
            break

    # Desempate suave por relación con el corpus (NO debe dominar al rango)
    if "colombia" in desc or "colombiano" in desc or "colombiana" in desc:
        score += 0.4

    return score


def enlazar_entidad(
    texto: str,
    categoria: str,
    ruta_cache: Optional[str] = None,
    sin_red: bool = False,
    contexto: str = "",
) -> Optional[dict]:
    """
    Enlaza una entidad nombrada con su entrada en Wikidata.

    Args:
        texto:       Texto de la entidad (ej: "German Arciniegas")
        categoria:   Categoría NER (personas, lugares, organizaciones, etc.)
        ruta_cache:  Ruta al archivo SQLite de caché (usa la por defecto si None)
        sin_red:     Si True, solo consulta caché local (modo offline)
        contexto:    Texto del artículo donde aparece la entidad. Se usa para
                     desambiguar homónimos por contexto (ej. "Alfonso López"
                     presidente vs. deportista). Opcional. (#1)

    Returns:
        dict con {id, label, description, url, confianza} o None si no se encontró.
        - id:          QID de Wikidata (ej: "Q1234567")
        - label:       Nombre canónico en español
        - description: Descripción corta de Wikidata
        - url:         URL completa de la entidad en Wikidata
        - confianza:   Float 0.0-1.0 basado en coincidencia con el corpus
    """
    if not texto or not texto.strip():
        return None

    texto = texto.strip()

    # Filtro de basura OCR (#2): fragmentos demasiado cortos ("Bogo", "Cal") o
    # sin ninguna letra generan enlaces espurios. No se intentan enlazar.
    if len(texto) < _MIN_LEN_ENTIDAD or not any(c.isalpha() for c in texto):
        return None

    cache = _obtener_cache(ruta_cache)

    # Consultar caché primero (sólo entradas del algoritmo actual; #4)
    cached = cache.obtener(texto, categoria)
    if cached is not None:
        return cached if cached else None  # {} → None (no encontrado)

    if sin_red:
        return None  # Modo offline: no hacer llamadas HTTP

    # Llamada a la API
    time.sleep(_PAUSA_ENTRE_LLAMADAS)
    candidatos = _llamar_wikidata(texto, categoria, lang="es")

    # Si no hay resultados en español, intentar en inglés
    if not candidatos:
        time.sleep(_PAUSA_ENTRE_LLAMADAS)
        candidatos = _llamar_wikidata(texto, categoria, lang="en")

    if not candidatos:
        cache.guardar(texto, categoria, None)
        return None

    # Puntuar y ordenar (con contexto del artículo si lo hay; #1)
    puntuados = [
        (c, _puntuar_candidato(c, texto, categoria, contexto))
        for c in candidatos
    ]
    puntuados.sort(key=lambda x: -x[1])

    # Filtro por tipo P31 + ventana histórica: recorrer en orden de score y
    # quedarse con el primer candidato cuyo tipo Wikidata sea compatible con la
    # categoría NER y que existiera en la época del corpus. Así se descartan
    # homónimos (apellido, barco, pintura) y homónimos MODERNOS (#3).
    tipos_validos = _P31_VALIDOS.get(categoria)
    mejor, mejor_score = None, 0.0
    for cand, sc in puntuados:
        if sc < 0.3:
            continue
        if not sin_red and tipos_validos:
            time.sleep(_PAUSA_ENTRE_LLAMADAS)
            p31 = _obtener_p31(cand["id"])
            # Si tiene P31 conocido y NINGUNO es válido, descartar.
            # Si no se pudo obtener P31 (lista vacía), no penalizar (fallback).
            if p31 and not (set(p31) & tipos_validos):
                continue
        if not sin_red:
            # Descartar homónimos modernos (nacidos/fundados tras el corpus). (#3)
            time.sleep(_PAUSA_ENTRE_LLAMADAS)
            anio = _obtener_fecha_relevante(cand["id"])
            if anio is not None and not (_ANIO_CORPUS_INI <= anio <= _ANIO_CORPUS_FIN):
                continue
        mejor, mejor_score = cand, sc
        break

    if mejor is None:
        cache.guardar(texto, categoria, None)
        return None

    # Normalizar confianza a [0, 1]. El score máximo ronda ~4.8 (rango 0 + label
    # exacto + tipo + Colombia + contexto).
    confianza = max(0.0, min(1.0, mejor_score / 4.0))

    # Umbral de confianza (#2): por debajo, el enlace es demasiado dudoso y se
    # trata como "no encontrado" para no contaminar el corpus con enlaces malos.
    if confianza < _CONF_MINIMA:
        cache.guardar(texto, categoria, None)
        return None

    resultado = {
        "id":          mejor["id"],
        "label":       mejor["label"],
        "description": mejor["description"],
        "url":         mejor["url"],
        "confianza":   round(confianza, 3),
    }
    cache.guardar(texto, categoria, resultado)
    return resultado


def enlazar_indice_ner(
    indice_ner: dict,
    ruta_cache: Optional[str] = None,
    sin_red: bool = False,
    callback=None,
    textos_articulos: Optional[dict] = None,
) -> dict:
    """
    Enlaza todas las entidades de un índice NER completo.

    Args:
        indice_ner:  Dict {categoria: {texto: [articulo_ids]}} (formato del repositorio)
        ruta_cache:  Ruta al archivo SQLite de caché
        sin_red:     Si True, solo consulta caché local
        callback:    Función callback(n_procesadas, total) para progreso
        textos_articulos: Dict opcional {articulo_id: texto}. Si se pasa, se
                     construye el CONTEXTO de cada entidad concatenando los
                     artículos donde aparece, para desambiguación contextual. (#1)

    Returns:
        Dict {categoria: {texto: resultado_wikidata_o_None}}
    """
    resultado = {}
    total = sum(len(entidades) for entidades in indice_ner.values())
    n = 0

    for categoria, entidades in indice_ner.items():
        resultado[categoria] = {}
        for texto, art_ids in entidades.items():
            contexto = ""
            if textos_articulos:
                # Une los textos de los artículos donde aparece la entidad
                # (cota de tamaño para no inflar el solapamiento).
                trozos = [textos_articulos.get(a, "") for a in (art_ids or [])]
                contexto = " ".join(t for t in trozos if t)[:4000]
            enlace = enlazar_entidad(texto, categoria, ruta_cache, sin_red, contexto)
            resultado[categoria][texto] = enlace
            n += 1
            if callback:
                try:
                    callback(n, total)
                except Exception:
                    pass

    return resultado


def enlazar_lista_entidades(
    entidades: list[dict],
    ruta_cache: Optional[str] = None,
    sin_red: bool = False,
) -> list[dict]:
    """
    Enlaza una lista de entidades NER (formato de ner_roberta / pipeline_ner).

    Args:
        entidades:  Lista de dicts {texto, categoria, confianza, fuente}
        ruta_cache: Ruta al archivo SQLite de caché
        sin_red:    Si True, solo consulta caché local

    Returns:
        La misma lista con un campo "wikidata" añadido a cada elemento.
        Si no se encontró enlace, "wikidata" es None.
    """
    enriquecidas = []
    for ent in entidades:
        ent_copia = dict(ent)
        enlace = enlazar_entidad(
            ent.get("texto", ""),
            ent.get("categoria", ""),
            ruta_cache,
            sin_red,
        )
        ent_copia["wikidata"] = enlace
        enriquecidas.append(ent_copia)
    return enriquecidas


def estadisticas_cache(ruta_cache: Optional[str] = None) -> dict:
    """Retorna estadísticas de la caché local."""
    return _obtener_cache(ruta_cache).estadisticas()


def limpiar_cache(dias: int = 90, ruta_cache: Optional[str] = None):
    """Elimina entradas con más de `dias` días de antigüedad de la caché."""
    _obtener_cache(ruta_cache).limpiar(dias)
