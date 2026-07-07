"""
core/metadata_extractor.py — Extracción de metadatos desde URLs de bibliotecas digitales.

Estrategia por capas:
  1. OAI-PMH (Dublin Core XML) — estándar de interoperabilidad de bibliotecas.
  2. JSON-LD / Schema.org (metadatos semánticos embebidos en HTML).
  3. OpenGraph / meta etiquetas HTML clásicas.
  4. Scraping de campos estructurados (catálogos SirsiDynix, BDH, Hemeroteca, etc.).
  5. Parseo de URL (parámetros de identificador).

Plataformas con soporte específico:
  · SirsiDynix Enterprise (BNCO, BiblioRed, etc.)
  · Biblioteca Digital Hispánica (BDH)
  · Hemeroteca Digital BNE
  · Europeana
  · Internet Archive (archive.org)
  · Memoria Chilena
  · WorldCat
"""

import re
import json
import urllib.request
import urllib.parse
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import Optional

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0.0.0 Safari/537.36")

DC_NS    = "http://purl.org/dc/elements/1.1/"
OAI_NS   = "http://www.openarchives.org/OAI/2.0/"
OAI_DC   = "http://www.openarchives.org/OAI/2.0/oai_dc/"


def _get(url: str, timeout: int = 12) -> str:
    """Descarga una URL y retorna el contenido como texto."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            charset = r.headers.get_content_charset() or "utf-8"
            return r.read().decode(charset, errors="replace")
    except Exception as e:
        raise ConnectionError(f"No se pudo acceder a {url}: {e}")


def _text_elem(elem, tag: str, ns: str = "") -> str:
    ns_uri = f"{{{ns}}}" if ns else ""
    e = elem.find(f".//{ns_uri}{tag}")
    return (e.text or "").strip() if e is not None else ""


# ══════════════════════════════════════════════════════════════════════════════
# 1. OAI-PMH
# ══════════════════════════════════════════════════════════════════════════════

def _oai_endpoint_from_url(url: str) -> Optional[str]:
    """Infiere el endpoint OAI-PMH a partir de la URL del recurso."""
    p = urllib.parse.urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    # Patrones conocidos
    candidatos = [
        f"{base}/oai",
        f"{base}/oai2",
        f"{base}/OAI/request",
        f"{base}/cgi-bin/oai.pl",
        f"{base}/oai-pmh",
        f"{base}/catalog/oai",
        f"{base}/api/oai",
    ]
    # Sirsi/Enterprise
    if "sirsi" in p.netloc or "ent.sirsi" in p.netloc:
        candidatos.insert(0, f"{base}/custom/oai")
    return candidatos


def _oai_get_record(endpoint: str, identifier: str) -> dict:
    """Obtiene un registro OAI-PMH por identificador."""
    url = f"{endpoint}?verb=GetRecord&metadataPrefix=oai_dc&identifier={urllib.parse.quote(identifier)}"
    xml_txt = _get(url)
    return _parse_oai_xml(xml_txt)


def _parse_oai_xml(xml_txt: str) -> dict:
    """Parsea XML OAI-PMH Dublin Core y retorna dict de metadatos."""
    meta = {}
    try:
        root = ET.fromstring(xml_txt)
        # Buscar el bloque <oai_dc:dc>
        dc = root.find(f".//{{{OAI_DC}}}dc")
        if dc is None:
            # Intentar sin namespace
            dc = root.find(".//dc")
        if dc is None:
            return meta
        campos = {
            "titulo":      "title",
            "creador":     "creator",
            "tema":        "subject",
            "descripcion": "description",
            "editorial":   "publisher",
            "fecha":       "date",
            "tipo":        "type",
            "formato":     "format",
            "identificador": "identifier",
            "idioma":      "language",
            "relacion":    "relation",
            "cobertura":   "coverage",
            "derechos":    "rights",
        }
        for campo, etiqueta in campos.items():
            elems = dc.findall(f"{{{DC_NS}}}{etiqueta}")
            if not elems:
                elems = dc.findall(etiqueta)
            valores = [e.text.strip() for e in elems if e.text]
            if valores:
                meta[campo] = valores[0] if len(valores) == 1 else valores
    except Exception:
        pass
    return meta


def intentar_oai(url: str) -> dict:
    """Intenta obtener metadatos OAI-PMH probando endpoints comunes."""
    # Extraer identificador de la URL
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    posibles_ids = [
        params.get("idFichero"),
        params.get("id"),
        params.get("identifier"),
        params.get("record"),
        urllib.parse.urlparse(url).path.split("/")[-1],
    ]
    endpoints = _oai_endpoint_from_url(url)
    for ep in endpoints[:4]:
        for ident in posibles_ids:
            if not ident:
                continue
            try:
                meta = _oai_get_record(ep, ident)
                if meta:
                    meta["fuente_metadata"] = "OAI-PMH"
                    return meta
            except Exception:
                pass
    return {}


# ══════════════════════════════════════════════════════════════════════════════
# 2. JSON-LD / Schema.org
# ══════════════════════════════════════════════════════════════════════════════

def _extraer_jsonld(html: str) -> dict:
    """Extrae metadatos de bloques <script type="application/ld+json">."""
    meta = {}
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>',
                          html, re.S | re.I):
        try:
            data = json.loads(m.group(1))
            if isinstance(data, list):
                data = data[0]
            meta["titulo"]      = meta.get("titulo")      or data.get("name") or data.get("headline", "")
            meta["creador"]     = meta.get("creador")      or _autor_str(data.get("author"))
            meta["fecha"]       = meta.get("fecha")        or data.get("datePublished", "")
            meta["descripcion"] = meta.get("descripcion")  or data.get("description", "")
            meta["editorial"]   = meta.get("editorial")    or _autor_str(data.get("publisher"))
            meta["idioma"]      = meta.get("idioma")       or data.get("inLanguage", "")
        except Exception:
            pass
    return {k: v for k, v in meta.items() if v}


def _autor_str(val) -> str:
    if not val:
        return ""
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        return val.get("name", "")
    if isinstance(val, list):
        return "; ".join(_autor_str(v) for v in val)
    return ""


# ══════════════════════════════════════════════════════════════════════════════
# 3. Meta etiquetas HTML
# ══════════════════════════════════════════════════════════════════════════════

def _extraer_meta_html(html: str) -> dict:
    """Extrae <meta name="..." content="..."> y <title>."""
    meta = {}

    # Título
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if m:
        meta["titulo"] = re.sub(r"\s+", " ", m.group(1)).strip()[:200]

    # Meta estándar / Dublin Core / OpenGraph
    pat = re.compile(
        r'<meta\s+(?:name|property)=["\']([^"\']+)["\']\s+content=["\']([^"\']*)["\']',
        re.I)
    mapa = {
        # Dublin Core
        "dc.title":         "titulo",
        "dc.creator":       "creador",
        "dc.date":          "fecha",
        "dc.description":   "descripcion",
        "dc.publisher":     "editorial",
        "dc.subject":       "tema",
        "dc.language":      "idioma",
        "dc.identifier":    "identificador",
        "dc.type":          "tipo",
        "dc.format":        "formato",
        "dc.coverage":      "cobertura",
        "dc.rights":        "derechos",
        # OpenGraph
        "og:title":         "titulo",
        "og:description":   "descripcion",
        "og:site_name":     "editorial",
        # Twitter Card
        "twitter:title":    "titulo",
        "twitter:description": "descripcion",
        # Otros
        "citation_title":   "titulo",
        "citation_author":  "creador",
        "citation_date":    "fecha",
        "citation_publisher": "editorial",
    }
    for m2 in pat.finditer(html):
        clave = m2.group(1).lower()
        valor = m2.group(2).strip()
        campo = mapa.get(clave)
        if campo and valor and not meta.get(campo):
            meta[campo] = valor

    return {k: v for k, v in meta.items() if v}


# ══════════════════════════════════════════════════════════════════════════════
# 4. Scraping específico por plataforma
# ══════════════════════════════════════════════════════════════════════════════

def _sirsi_metadata(html: str, url: str) -> dict:
    """Extrae metadatos del visor SirsiDynix Enterprise."""
    meta = {}
    # El visor de SirsiDynix suele tener tablas con etiquetas como "Autor:", "Título:", etc.
    pares = re.findall(
        r'<(?:th|td)[^>]*>([^<]{2,40})</(?:th|td)>\s*'
        r'<(?:th|td)[^>]*>(.*?)</(?:th|td)>',
        html, re.S | re.I)
    mapa_labels = {
        "título":         "titulo",
        "title":          "titulo",
        "autor":          "creador",
        "author":         "creador",
        "fecha":          "fecha",
        "date":           "fecha",
        "año":            "fecha",
        "publicación":    "editorial",
        "publisher":      "editorial",
        "descripción":    "descripcion",
        "description":    "descripcion",
        "idioma":         "idioma",
        "language":       "idioma",
        "tema":           "tema",
        "subject":        "tema",
        "tipo":           "tipo",
        "type":           "tipo",
        "colección":      "coleccion",
        "collection":     "coleccion",
        "signatura":      "signatura",
        "call number":    "signatura",
        "issn":           "issn",
        "isbn":           "isbn",
        "volumen":        "volumen",
        "número":         "numero",
    }
    for label, valor in pares:
        label_clean = re.sub(r"<[^>]+>", "", label).strip().lower().rstrip(":")
        valor_clean  = re.sub(r"<[^>]+>", "", valor).strip()[:300]
        campo = mapa_labels.get(label_clean)
        if campo and valor_clean and not meta.get(campo):
            meta[campo] = valor_clean

    # idFichero del parámetro de URL
    m = re.search(r"idFichero=(\d+)", url)
    if m and not meta.get("identificador"):
        meta["identificador"] = f"BNCO:fichero:{m.group(1)}"

    return {k: v for k, v in meta.items() if v}


def _archive_org_metadata(url: str) -> dict:
    """Consulta la API de metadata de Archive.org."""
    m = re.search(r"archive\.org/(?:details|stream)/([^/?#]+)", url)
    if not m:
        return {}
    item_id = m.group(1)
    api_url = f"https://archive.org/metadata/{item_id}"
    try:
        data = json.loads(_get(api_url))
        md = data.get("metadata", {})
        return {
            "titulo":      md.get("title", [""])[0] if isinstance(md.get("title"), list) else md.get("title", ""),
            "creador":     md.get("creator", [""])[0] if isinstance(md.get("creator"), list) else md.get("creator", ""),
            "fecha":       md.get("date", ""),
            "descripcion": md.get("description", [""])[0] if isinstance(md.get("description"), list) else md.get("description", ""),
            "editorial":   md.get("publisher", ""),
            "idioma":      md.get("language", ""),
            "identificador": f"archive.org:{item_id}",
            "url_acceso":  f"https://archive.org/details/{item_id}",
            "fuente_metadata": "Archive.org API",
        }
    except Exception:
        return {}


def _europeana_metadata(url: str) -> dict:
    """Consulta la API de Europeana si se puede extraer el identificador."""
    m = re.search(r"europeana\.eu/(?:item|portal)/([^/?#]+/[^/?#]+)", url)
    if not m:
        return {}
    item_id = m.group(1).replace("/", "%2F")
    # API pública sin clave (limitada pero funcional para metadatos básicos)
    api_url = f"https://api.europeana.eu/record/v2/{m.group(1)}.json"
    try:
        data = json.loads(_get(api_url))
        obj = data.get("object", {})
        title = obj.get("title", [""])[0] if obj.get("title") else ""
        return {
            "titulo":      title,
            "fecha":       str(obj.get("year", [""])[0]) if obj.get("year") else "",
            "editorial":   obj.get("dataProvider", [""])[0] if obj.get("dataProvider") else "",
            "idioma":      obj.get("language", [""])[0] if obj.get("language") else "",
            "url_acceso":  url,
            "fuente_metadata": "Europeana API",
        }
    except Exception:
        return {}


# ══════════════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def extraer_metadata_url(url: str) -> dict:
    """
    Extrae metadatos bibliográficos desde cualquier URL de biblioteca digital.
    Retorna dict con campos Dublin Core + campos adicionales de la plataforma.
    Los campos pueden estar vacíos si no se encontraron.
    """
    url = url.strip()
    meta = {
        "url":              url,
        "titulo":           "",
        "creador":          "",
        "fecha":            "",
        "descripcion":      "",
        "editorial":        "",
        "idioma":           "",
        "identificador":    "",
        "tema":             "",
        "tipo":             "",
        "formato":          "",
        "cobertura":        "",
        "derechos":         "",
        "fuente_metadata":  "—",
        "error":            "",
    }

    # ── Plataformas con API propia ────────────────────────────────────────────
    if "archive.org" in url:
        result = _archive_org_metadata(url)
        if result:
            meta.update(result)
            return _limpiar(meta)

    if "europeana.eu" in url:
        result = _europeana_metadata(url)
        if result:
            meta.update(result)
            return _limpiar(meta)

    # ── Intentar OAI-PMH ─────────────────────────────────────────────────────
    oai = intentar_oai(url)
    if oai:
        meta.update(oai)
        meta["fuente_metadata"] = "OAI-PMH"

    # ── Descargar HTML ───────────────────────────────────────────────────────
    html = ""
    try:
        html = _get(url, timeout=15)
    except ConnectionError as e:
        meta["error"] = str(e)
        # Aun sin HTML, si OAI tuvo datos, retornar
        if oai:
            return _limpiar(meta)
        # Intentar con URL alternativas (versión móvil, caché, etc.)
        for alt in _url_alternativas(url):
            try:
                html = _get(alt, timeout=10)
                meta["url_acceso_real"] = alt
                break
            except Exception:
                pass

    if html:
        # JSON-LD (mayor prioridad que meta tags)
        jld = _extraer_jsonld(html)
        for k, v in jld.items():
            if v and not meta.get(k):
                meta[k] = v
        if jld:
            meta["fuente_metadata"] = "JSON-LD"

        # Meta etiquetas
        htm = _extraer_meta_html(html)
        for k, v in htm.items():
            if v and not meta.get(k):
                meta[k] = v
        if htm and meta["fuente_metadata"] == "—":
            meta["fuente_metadata"] = "Meta etiquetas HTML"

        # Scraping específico SirsiDynix
        if "sirsi" in url or "ent." in url or any(
                pat in html for pat in ["SirsiDynix", "Enterprise", "sirsi"]):
            sir = _sirsi_metadata(html, url)
            for k, v in sir.items():
                if v and not meta.get(k):
                    meta[k] = v
            if sir and meta["fuente_metadata"] == "—":
                meta["fuente_metadata"] = "Catálogo SirsiDynix"

    return _limpiar(meta)


def _url_alternativas(url: str) -> list[str]:
    """Genera variantes de URL que pueden ser accesibles."""
    p = urllib.parse.urlparse(url)
    alts = []
    # Versión HTTP vs HTTPS
    if p.scheme == "https":
        alts.append(url.replace("https://", "http://", 1))
    # Caché de Google
    alts.append(f"https://webcache.googleusercontent.com/search?q=cache:{urllib.parse.quote(url)}")
    return alts


def _limpiar(meta: dict) -> dict:
    """Limpia y normaliza los valores del diccionario de metadatos."""
    for k, v in meta.items():
        if isinstance(v, str):
            # Quitar etiquetas HTML residuales
            v = re.sub(r"<[^>]+>", " ", v)
            v = re.sub(r"\s+", " ", v).strip()
            meta[k] = v[:500]
    return meta


CAMPOS_DISPLAY = {
    "titulo":           "Título",
    "creador":          "Autor / Creador",
    "fecha":            "Fecha de publicación",
    "editorial":        "Editor / Institución",
    "descripcion":      "Descripción",
    "idioma":           "Idioma",
    "tema":             "Tema / Materia",
    "tipo":             "Tipo de documento",
    "formato":          "Formato",
    "cobertura":        "Cobertura geográfica/temporal",
    "identificador":    "Identificador",
    "derechos":         "Derechos de uso",
    "fuente_metadata":  "Fuente de metadatos",
    "fuentes_web":      "Búsqueda web",
    "query_usada":      "Query utilizada",
    "campos_inferidos": "Campos inferidos por búsqueda",
    "contexto_web":     "Contexto web",
    "url":              "URL original",
}



# ══════════════════════════════════════════════════════════════════════════════
# ENRIQUECIMIENTO WEB — búsqueda en DuckDuckGo / SearXNG para rellenar huecos
# ══════════════════════════════════════════════════════════════════════════════

def _buscar_duckduckgo(query: str, timeout: int = 10) -> list[dict]:
    """
    Usa la API lite de DuckDuckGo (sin clave) para obtener snippets.
    Devuelve lista de {title, snippet, url}.
    """
    q = urllib.parse.quote_plus(query)
    url = f"https://api.duckduckgo.com/?q={q}&format=json&no_redirect=1&no_html=1&skip_disambig=1"
    try:
        html = _get(url, timeout=timeout)
        data = json.loads(html)
    except Exception:
        return []

    resultados = []
    # Resultado principal
    if data.get("AbstractText"):
        resultados.append({
            "title":   data.get("Heading", ""),
            "snippet": data["AbstractText"],
            "url":     data.get("AbstractURL", ""),
        })
    # Resultados relacionados
    for r in data.get("RelatedTopics", [])[:5]:
        if isinstance(r, dict) and r.get("Text"):
            resultados.append({
                "title":   r.get("Text", "")[:80],
                "snippet": r.get("Text", ""),
                "url":     r.get("FirstURL", ""),
            })
    return resultados


def _scrape_snippets(query: str, timeout: int = 12) -> list[dict]:
    """
    Scraping ligero de resultados de búsqueda en HTML de DuckDuckGo
    para obtener snippets adicionales cuando la API no da resultados.
    """
    q = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={q}"
    try:
        html = _get(url, timeout=timeout)
    except Exception:
        return []

    resultados = []
    # Extraer títulos y snippets de la página HTML
    titulos  = re.findall(r'class="result__title"[^>]*>.*?<a[^>]*>(.*?)</a>', html, re.S)
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</[a-z]+>', html, re.S)
    urls_raw = re.findall(r'class="result__url"[^>]*>(.*?)</a>', html, re.S)

    for i, (t, s) in enumerate(zip(titulos[:6], snippets[:6])):
        t = re.sub(r'<[^>]+>', '', t).strip()
        s = re.sub(r'<[^>]+>', '', s).strip()
        u = urls_raw[i].strip() if i < len(urls_raw) else ""
        if s:
            resultados.append({"title": t, "snippet": s, "url": u})
    return resultados


def _inferir_campo_desde_snippets(snippets: list[dict], campo: str) -> str:
    """
    Analiza snippets de búsqueda e intenta inferir el valor de un campo.
    Estrategia heurística simple orientada a prensa histórica.
    """
    texto_completo = " ".join(r.get("snippet","") + " " + r.get("title","")
                               for r in snippets)

    if campo == "fecha":
        # Buscar patrones de año/fecha
        m = re.search(r'(19[0-9]{2}|18[0-9]{2})', texto_completo)
        return m.group(1) if m else ""

    if campo == "creador":
        # Nombres propios capitalizados (heurística)
        nombres = re.findall(
            r'([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})?)',
            texto_completo)
        # Filtrar palabras comunes
        STOP = {"Esta","Este","Estos","Estas","Para","Como","Cuando","Donde"}
        nombres = [n for n in nombres if not any(p in n for p in STOP)]
        return nombres[0] if nombres else ""

    if campo == "descripcion":
        # El snippet más largo
        snippets_ord = sorted(snippets, key=lambda r: len(r.get("snippet","")), reverse=True)
        return snippets_ord[0].get("snippet","")[:400] if snippets_ord else ""

    if campo == "titulo":
        # Título del primer resultado
        return snippets[0].get("title","")[:200] if snippets else ""

    if campo == "editorial":
        patrones = [
            r'publicad[ao]\s+(?:por\s+)?([A-Z\w][^,.]{3,40})',
            r'editor(?:ial)?\s+([A-Z\w][^,.]{3,40})',
        ]
        for pat in patrones:
            m = re.search(pat, texto_completo, re.I)
            if m:
                return m.group(1).strip()[:100]

    return ""


def enriquecer_con_busqueda_web(meta: dict, url: str, timeout: int = 12) -> dict:
    """
    Complementa los metadatos existentes con información buscada en la web.

    Estrategia:
      1. Construye una query con lo que ya se sabe (título parcial, URL, dominio).
      2. Busca en DuckDuckGo API y luego en HTML si es necesario.
      3. Infiere campos faltantes a partir de los snippets obtenidos.
      4. Registra las fuentes usadas en meta["fuentes_web"].
    """
    meta = dict(meta)

    # Construir query lo más específica posible
    partes_query = []
    if meta.get("titulo"):
        partes_query.append(f'"{meta["titulo"]}"')
    elif url:
        # Extraer términos legibles de la URL
        p = urllib.parse.urlparse(url)
        slug = re.sub(r'[_\-]', ' ',
                      re.sub(r'\.(html?|php|aspx|pdf)$', '',
                             p.path.split('/')[-1]))
        if len(slug.strip()) > 4:
            partes_query.append(slug.strip())
        partes_query.append(p.netloc.split('.')[0])  # dominio base

    if meta.get("creador"):
        partes_query.append(meta["creador"])

    query = " ".join(partes_query).strip()
    if not query:
        meta["fuentes_web"] = "Sin suficiente información para buscar"
        return meta

    # Añadir contexto de tipo de documento
    if any(w in url.lower() for w in ("revista","magazine","hemeroteca","periodico","prensa")):
        query += " revista histórica"

    # Buscar
    snippets = _buscar_duckduckgo(query, timeout=timeout)
    fuente_busq = "DuckDuckGo API"
    if not snippets:
        snippets = _scrape_snippets(query, timeout=timeout)
        fuente_busq = "DuckDuckGo HTML"

    if not snippets:
        meta["fuentes_web"] = f"Búsqueda sin resultados (query: {query[:80]})"
        return meta

    # Rellenar campos vacíos
    campos_a_inferir = ["titulo", "creador", "fecha", "descripcion", "editorial"]
    enriquecidos = []
    for campo in campos_a_inferir:
        if not meta.get(campo):
            valor = _inferir_campo_desde_snippets(snippets, campo)
            if valor:
                meta[campo] = valor
                enriquecidos.append(campo)

    # Añadir snippets relevantes como "contexto_web"
    meta["contexto_web"] = (" | ".join(
        r["snippet"][:120] for r in snippets[:3] if r.get("snippet")
    ))
    meta["fuentes_web"]   = fuente_busq
    meta["query_usada"]   = query[:200]
    if enriquecidos:
        meta["campos_inferidos"] = ", ".join(enriquecidos)
        if meta.get("fuente_metadata","—") == "—":
            meta["fuente_metadata"] = f"Búsqueda web ({fuente_busq})"
        else:
            meta["fuente_metadata"] += f" + búsqueda web"

    return meta


def formatear_metadatos(meta: dict) -> str:
    """Formatea el diccionario de metadatos como texto legible."""
    lineas = []
    for campo, label in CAMPOS_DISPLAY.items():
        valor = meta.get(campo, "")
        if valor and valor != "—":
            if isinstance(valor, list):
                valor = "; ".join(valor)
            lineas.append(f"  {label:<30} {valor}")
    if meta.get("error"):
        lineas.append(f"\n  ⚠️ {meta['error']}")
    return "\n".join(lineas) if lineas else "  Sin metadatos encontrados."
