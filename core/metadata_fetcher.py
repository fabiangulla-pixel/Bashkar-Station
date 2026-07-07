"""
core/metadata_fetcher.py — Extracción de metadatos bibliográficos desde URLs.

Estrategias:
  1. HTML semántico: Dublin Core, Open Graph, Schema.org, meta tags estándar
  2. Catálogos de bibliotecas (BNCO/Sirsi, HathiTrust, Internet Archive, BNC)
  3. Extracción heurística del DOM (título, autor, fecha, descripción)

Devuelve un diccionario normalizado con los metadatos encontrados.
"""

import json
import re
import urllib.parse
import urllib.request

# ── User-agent estándar ───────────────────────────────────────────────────────
_UA = ("Mozilla/5.0 (compatible; BashkarStation/1.0; "
       "+https://github.com/bashkar-station)")

# ── Patrones generales ────────────────────────────────────────────────────────
RE_META = re.compile(
    r'<meta\s[^>]*?(?:name|property)\s*=\s*["\']([^"\']+)["\'][^>]*?'
    r'content\s*=\s*["\']([^"\']*)["\']',
    re.IGNORECASE | re.DOTALL,
)
RE_META2 = re.compile(
    r'<meta\s[^>]*?content\s*=\s*["\']([^"\']*)["\'][^>]*?'
    r'(?:name|property)\s*=\s*["\']([^"\']+)["\']',
    re.IGNORECASE | re.DOTALL,
)
RE_TITLE = re.compile(r'<title[^>]*>(.*?)</title>', re.IGNORECASE | re.DOTALL)
RE_H1    = re.compile(r'<h1[^>]*>(.*?)</h1>',    re.IGNORECASE | re.DOTALL)
RE_LINK_CANONICAL = re.compile(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', re.IGNORECASE)
RE_JSON_LD = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                         re.IGNORECASE | re.DOTALL)


def _limpiar(texto: str) -> str:
    """Quita tags HTML y normaliza espacios."""
    texto = re.sub(r'<[^>]+>', ' ', texto)
    texto = re.sub(r'&amp;', '&', texto)
    texto = re.sub(r'&lt;',  '<', texto)
    texto = re.sub(r'&gt;',  '>', texto)
    texto = re.sub(r'&quot;','"', texto)
    texto = re.sub(r'&#39;', "'", texto)
    texto = re.sub(r'&nbsp;',' ', texto)
    return re.sub(r'\s+', ' ', texto).strip()


def _fetch_html(url: str, timeout: int = 20) -> str | None:
    """Descarga el HTML de una URL. Devuelve None si falla."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA,
                                                "Accept-Language": "es,en;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = "utf-8"
            ct = resp.headers.get("Content-Type", "")
            m = re.search(r"charset=([\w-]+)", ct)
            if m: charset = m.group(1)
            raw = resp.read()
            try: return raw.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError): return raw.decode("utf-8", errors="replace")
    except Exception:
        return None


def _extraer_meta_tags(html: str) -> dict:
    """Extrae todos los meta tags relevantes."""
    resultado = {}
    for m in RE_META.finditer(html):
        resultado[m.group(1).lower()] = _limpiar(m.group(2))
    for m in RE_META2.finditer(html):
        resultado[m.group(2).lower()] = _limpiar(m.group(1))
    return resultado


def _extraer_json_ld(html: str) -> list[dict]:
    """Extrae bloques JSON-LD (Schema.org)."""
    bloques = []
    for m in RE_JSON_LD.finditer(html):
        try:
            obj = json.loads(m.group(1))
            if isinstance(obj, list): bloques.extend(obj)
            else: bloques.append(obj)
        except json.JSONDecodeError: pass
    return bloques


def _normalizar_metadatos(meta: dict, json_ld: list[dict], html: str) -> dict:
    """
    Normaliza las fuentes heterogéneas en un diccionario estándar de metadatos.
    Campos de salida: titulo, autor, fecha, institucion, descripcion,
                      idioma, temas, url_registro, tipo_documento, derechos,
                      editorial, lugar, numero, volumen, issn, fuente
    """
    resultado = {
        "titulo": "", "autor": "", "fecha": "", "institucion": "",
        "descripcion": "", "idioma": "", "temas": [],
        "url_registro": "", "tipo_documento": "", "derechos": "",
        "editorial": "", "lugar": "", "numero": "", "volumen": "", "issn": "",
        "fuente": "extracción automática",
    }

    # ── Dublin Core ─────────────────────────────────────────────────────────
    dc_map = {
        "dc.title":        "titulo",
        "dc:title":        "titulo",
        "dc.creator":      "autor",
        "dc:creator":      "autor",
        "dc.date":         "fecha",
        "dc:date":         "fecha",
        "dc.description":  "descripcion",
        "dc:description":  "descripcion",
        "dc.publisher":    "editorial",
        "dc:publisher":    "editorial",
        "dc.language":     "idioma",
        "dc:language":     "idioma",
        "dc.subject":      "temas",
        "dc:subject":      "temas",
        "dc.type":         "tipo_documento",
        "dc:type":         "tipo_documento",
        "dc.rights":       "derechos",
        "dc:rights":       "derechos",
        "dc.coverage":     "lugar",
        "dc:coverage":     "lugar",
        "dc.identifier":   "url_registro",
        "dc:identifier":   "url_registro",
    }
    for dc_key, campo in dc_map.items():
        val = meta.get(dc_key, "")
        if val:
            if campo == "temas" and isinstance(resultado[campo], list):
                resultado[campo].extend([v.strip() for v in val.split(";") if v.strip()])
            elif not resultado[campo]:
                resultado[campo] = val

    # ── Open Graph ──────────────────────────────────────────────────────────
    og_map = {
        "og:title":       "titulo",
        "og:description": "descripcion",
        "og:site_name":   "institucion",
    }
    for og,campo in og_map.items():
        if meta.get(og) and not resultado[campo]:
            resultado[campo] = meta[og]

    # ── Meta estándar ────────────────────────────────────────────────────────
    for k,campo in [("description","descripcion"),("author","autor"),
                    ("keywords","temas"),("language","idioma")]:
        if meta.get(k) and not resultado[campo]:
            if campo == "temas":
                resultado[campo].extend(
                    [v.strip() for v in meta[k].split(",") if v.strip()]
                )
            else:
                resultado[campo] = meta[k]

    # ── JSON-LD / Schema.org ─────────────────────────────────────────────────
    for bloque in json_ld:
        tipo = bloque.get("@type","")
        if tipo in ("Book","Periodical","Article","NewsArticle","ScholarlyArticle","ArchiveComponent","CreativeWork"):
            if not resultado["titulo"] and bloque.get("name"):
                resultado["titulo"] = _limpiar(str(bloque["name"]))
            if not resultado["autor"]:
                au = bloque.get("author") or bloque.get("creator")
                if isinstance(au, dict): resultado["autor"] = au.get("name","")
                elif isinstance(au, list) and au:
                    resultado["autor"] = ", ".join(
                        a.get("name",str(a)) if isinstance(a,dict) else str(a) for a in au
                    )
                elif isinstance(au, str): resultado["autor"] = au
            if not resultado["fecha"]:
                resultado["fecha"] = (bloque.get("datePublished")
                                      or bloque.get("dateCreated")
                                      or bloque.get("copyrightYear",""))
            if not resultado["descripcion"] and bloque.get("description"):
                resultado["descripcion"] = _limpiar(str(bloque["description"]))
            if not resultado["editorial"] and bloque.get("publisher"):
                p = bloque["publisher"]
                resultado["editorial"] = p.get("name",str(p)) if isinstance(p,dict) else str(p)
            if not resultado["issn"] and bloque.get("issn"):
                resultado["issn"] = str(bloque["issn"])

    # ── Fallback: título de la página ────────────────────────────────────────
    if not resultado["titulo"]:
        m = RE_TITLE.search(html)
        if m: resultado["titulo"] = _limpiar(m.group(1))
    if not resultado["titulo"]:
        m = RE_H1.search(html)
        if m: resultado["titulo"] = _limpiar(m.group(1))

    # ── Limpiar listas de temas duplicados ───────────────────────────────────
    resultado["temas"] = sorted(set(t for t in resultado["temas"] if t))

    return resultado


# ── Detectores especializados ─────────────────────────────────────────────────

def _detectar_sirsi_bnco(url: str, html: str) -> dict:
    """
    Extrae metadatos del visor de la Biblioteca Nacional de Colombia (Sirsi/Dynix).
    El visor es un iframe; intentamos obtener el registro del catálogo.
    """
    # Buscar ID del fichero en la URL
    m = re.search(r'idFichero=(\d+)', url)
    if not m: return {}
    id_fichero = m.group(1)

    # Buscar referencias a datos del catálogo en el HTML
    datos = {}

    # El visor embebe metadatos en variables JS o en atributos data-*
    patrones = [
        (r'["\']titulo["\']["\s:]+["\']([^"\']+)', "titulo"),
        (r'["\']title["\']["\s:]+["\']([^"\']+)',  "titulo"),
        (r'["\']autor["\']["\s:]+["\']([^"\']+)',  "autor"),
        (r'["\']author["\']["\s:]+["\']([^"\']+)', "autor"),
        (r'["\']fecha["\']["\s:]+["\']([^"\']+)',  "fecha"),
        (r'["\']date["\']["\s:]+["\']([^"\']+)',   "fecha"),
        (r'["\']descripcion["\']["\s:]+["\']([^"\']+)', "descripcion"),
        (r'["\']issn["\']["\s:]+["\']([^"\']+)',   "issn"),
    ]
    for patron, campo in patrones:
        mm = re.search(patron, html, re.IGNORECASE)
        if mm and not datos.get(campo):
            datos[campo] = _limpiar(mm.group(1))

    # Metadata adicional: referencia al URL del registro en el catálogo
    datos["url_catalogo_bnco"] = (
        f"https://bnco.ent.sirsi.net/custom/web/content/conservacion/"
        f"html/visorFicheros.html?idFichero={id_fichero}"
    )
    datos["id_fichero_bnco"] = id_fichero
    datos["institucion"] = "Biblioteca Nacional de Colombia"
    datos["fuente"] = "BNCO / Sirsi-Dynix"

    # Si el HTML del visor tiene poco texto, intentar API del catálogo
    # (BNCO a veces expone un endpoint de metadatos)
    api_url = (f"https://bnco.ent.sirsi.net/custom/web/content/conservacion/"
               f"html/getFichero.html?idFichero={id_fichero}")
    html_api = _fetch_html(api_url)
    if html_api:
        meta_api  = _extraer_meta_tags(html_api)
        jld_api   = _extraer_json_ld(html_api)
        extra     = _normalizar_metadatos(meta_api, jld_api, html_api)
        for k,v in extra.items():
            if v and not datos.get(k):
                datos[k] = v

    return datos


def _detectar_hathitrust(url: str, html: str) -> dict:
    m = re.search(r'/([a-z]+\.[a-z0-9]+)', url)
    datos = {"institucion": "HathiTrust Digital Library", "fuente": "HathiTrust"}
    # HathiTrust embebe metadatos en JSON en el DOM
    m2 = re.search(r'HTApp\.setMetadata\s*\(\s*(\{.*?\})\s*\)', html, re.DOTALL)
    if m2:
        try:
            obj = json.loads(m2.group(1))
            datos["titulo"]   = obj.get("title","")
            datos["autor"]    = obj.get("creator","")
            datos["fecha"]    = str(obj.get("date",""))
            datos["editorial"]= obj.get("publisher","")
        except Exception: pass
    return datos


def _detectar_archive_org(url: str, html: str) -> dict:
    """Internet Archive: metadatos en JSON embebido."""
    datos = {"institucion": "Internet Archive", "fuente": "archive.org"}
    # IA incluye __INITIAL_STATE__ con metadatos
    m = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});\s*</script>', html, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(1))
            item = obj.get("metadata",{}) or {}
            datos["titulo"]    = str(item.get("title",""))
            datos["autor"]     = str(item.get("creator",""))
            datos["fecha"]     = str(item.get("date",""))
            datos["descripcion"]= str(item.get("description",""))[:500]
            datos["editorial"] = str(item.get("publisher",""))
            datos["idioma"]    = str(item.get("language",""))
            su = item.get("subject","")
            if isinstance(su, list): datos["temas"] = su
            elif su: datos["temas"] = [su]
        except Exception: pass
    return datos


# ── Función principal ─────────────────────────────────────────────────────────

def extraer_metadatos_url(url: str) -> dict:
    """
    Extrae metadatos bibliográficos de la URL dada.

    Retorna dict con campos normalizados:
      titulo, autor, fecha, institucion, descripcion, idioma, temas,
      url_registro, tipo_documento, derechos, editorial, lugar,
      numero, volumen, issn, fuente, url_original, exito, error
    """
    resultado = {
        "url_original": url,
        "exito": False,
        "error": "",
        "titulo": "", "autor": "", "fecha": "", "institucion": "",
        "descripcion": "", "idioma": "", "temas": [],
        "url_registro": "", "tipo_documento": "", "derechos": "",
        "editorial": "", "lugar": "", "numero": "", "volumen": "", "issn": "",
        "fuente": "",
        # Campos extra según la fuente
        "metadatos_adicionales": {},
    }

    html = _fetch_html(url)
    if html is None:
        resultado["error"] = "No se pudo descargar la página. Verifica la URL y la conexión a internet."
        return resultado

    # ── Estrategia 1: detectores especializados ──────────────────────────────
    dominio = urllib.parse.urlparse(url).netloc.lower()
    extra = {}
    if "sirsi.net" in dominio or "bnco" in dominio:
        extra = _detectar_sirsi_bnco(url, html)
    elif "hathitrust.org" in dominio:
        extra = _detectar_hathitrust(url, html)
    elif "archive.org" in dominio:
        extra = _detectar_archive_org(url, html)

    # ── Estrategia 2: extracción genérica ────────────────────────────────────
    meta   = _extraer_meta_tags(html)
    jld    = _extraer_json_ld(html)
    norm   = _normalizar_metadatos(meta, jld, html)

    # Combinar: extra tiene prioridad sobre extracción genérica
    for campo in resultado.keys():
        if campo in ("url_original","exito","error","metadatos_adicionales"): continue
        if extra.get(campo): resultado[campo] = extra[campo]
        elif norm.get(campo): resultado[campo] = norm[campo]

    # Campos especiales del detector especializado
    resultado["metadatos_adicionales"] = {
        k:v for k,v in extra.items()
        if k not in resultado
    }

    # Inferir tipo de documento desde URL o título
    if not resultado["tipo_documento"]:
        u = url.lower(); t = resultado["titulo"].lower()
        if any(k in u+t for k in ["revista","magazine","periodical","journal","review"]):
            resultado["tipo_documento"] = "Revista"
        elif any(k in u+t for k in ["diario","newspaper","periódico","prensa"]):
            resultado["tipo_documento"] = "Periódico"
        elif any(k in u+t for k in ["libro","book","monograph"]):
            resultado["tipo_documento"] = "Libro"

    resultado["exito"] = bool(resultado.get("titulo") or resultado.get("descripcion"))

    return resultado
