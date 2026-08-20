"""
core/article_segmenter.py — Segmentación de artículos y atribución de autoría.

ESTRATEGIA v11 (reescritura completa para corpus BNC/Estampa):

El OCR de la Biblioteca Nacional de Colombia mezcla columnas de texto, produce
ruido OCR y no tiene marcadores de estructura. Intentar sub-segmentar dentro
de una página produce garbage.

NUEVA ESTRATEGIA:
  1. Cada página OCR = una unidad atómica de contenido.
  2. Detectar páginas especiales (portada, índice, colofón, publicidad, galería).
  3. Para páginas normales: limpiar texto y extraer el texto como un todo.
  4. Detectar el título de la página (primeras líneas limpias y legibles).
  5. Detectar autor (byline explícita al inicio, firma al final).
  6. Marcar páginas que continúan en otra ("Pasa a la Pág. X") para consolidarlas.
  7. Consolidar páginas consecutivas del mismo artículo en un solo registro.

Para PDFs digitales (PyMuPDF) se usa la información tipográfica real.
"""

import gc
import re
import statistics
from pathlib import Path

# ── Watermarks ────────────────────────────────────────────────────────────────
WATERMARKS = {
    "digitalizado biblioteca nacional",
    "biblioteca nacional de colombia",
    "hathitrust digital library",
    "google digitized",
    "internet archive",
    "biblioteca virtual",
    "prohibida su reproducción",
    "todos los derechos reservados",
}

# ── Caracteres basura OCR ─────────────────────────────────────────────────────
RE_CHARS_BASURA = re.compile(r'[~\[\]<>{}\\^$%@&!*|]')
RE_LINEA_BASURA = re.compile(
    r'^[\s\d\.\,\;\:\!\?\-\(\)\"\'\·\—\–\*\/\\=\+#%@&~\[\]<>{}]{1,10}$'
)

# ── Byline y firmas ───────────────────────────────────────────────────────────
RE_BYLINE = re.compile(
    r'(?:^|\n)\s*(?:[Pp][Oo][Rr]|POR)[:\s]+([A-ZÁÉÍÓÚÑ][a-záéíóúñ\-]+(?:\s+(?:de\s+la?\s+)?[A-ZÁÉÍÓÚÑ][a-záéíóúñ\-]+){1,4})',
    re.MULTILINE,
)
RE_FIRMA_CAPS = re.compile(
    r'\n[ \t]*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s\.]{8,55})\s*(?:\n|$)',
    re.MULTILINE,
)
RE_INICIAL = re.compile(
    r'\n([A-Z]\.(?:\s?[A-Z]\.)*\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{3,}(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{3,})?)\s*$',
    re.MULTILINE,
)
# Referencia a continuación en otra página
RE_CONTINUA = re.compile(
    r'[Pp]as[ao]\s+[ao]\s+la\s+[Pp][áa]g[ina\.]*\s*\.?\s*(\d+)',
    re.IGNORECASE,
)

# ── Secciones ────────────────────────────────────────────────────────────────
SECCIONES = {
    "Editorial":        ["editorial"],
    "Crónica":          ["crónica", "cronica", "crónicas"],
    "Reportaje":        ["reportaje", "gran reportaje", "reportajes"],
    "Cuento":           ["cuento", "ficción", "relato", "novela corta"],
    "Poema/Verso":      ["poema", "verso", "versos", "soneto", "oda", "rima", "poesía"],
    "Humor/Sátira":     ["humor", "caricatura", "sátira", "chiste", "humorismo"],
    "Cine":             ["cine", "película", "cinemat", "filme", "pantalla", "estreno"],
    "Teatro":           ["teatro", "escena", "drama", "obra"],
    "Libros":           ["libros", "bibliografía", "reseña", "lectura", "literatura"],
    "Sociedad":         ["sociedad", "gentes", "sociales", "vida social"],
    "Política":         ["política", "gobierno", "congreso", "partido", "ministro",
                        "presidente", "senado"],
    "Internacional":    ["europa", "guerra", "mundial", "internacional", "fascismo",
                        "alemania", "italia", "españa"],
    "Modas/Hogar":      ["modas", "hogar", "belleza", "moda", "costura", "recetas"],
    "Publicidad":       ["publicidad", "aviso", "anuncio", "propaganda"],
    "Deportes":         ["deportes", "fútbol", "atletismo", "béisbol", "boxeo", "ciclismo"],
    "Notas":            ["notas", "apuntes", "gacetilla", "brevedad", "miscelánea"],
    "Viajes":           ["viaje", "viajes", "turismo", "excursión", "itinerario"],
    "Ciencia/Salud":    ["ciencia", "medicina", "salud", "higiene", "tecnología",
                        "radio", "aviación"],
}

# ── Vocabulario de publicidad (para filtrar páginas publicitarias) ────────────
PALABRAS_PUBLICIDAD = {
    "almacen", "almacén", "tienda", "drogueria", "droguería", "farmacia",
    "laboratorio", "laboratorios", "clinica", "clínica",
    "tel", "telefono", "teléfono", "apartado",
    "precio", "precios", "venta", "oferta", "suscripcion", "suscripción",
    "sociedad anonima", "sociedad anónima", "ltda", "s.a.",
    "whisky", "cerveza", "ron", "aguardiente", "champagne",
    "cigarros", "cigarrillos", "tabaco",
    "solicite", "pídanos", "visitenos", "visítenos", "distribuidores",
    "exclusivo", "garantizamos", "ofrecemos", "representantes",
}

# Palabras que NO aparecen en nombres personales reales
_NO_NOMBRES = {
    "almacen", "almacén", "tienda", "casa", "drogueria", "droguería", "farmacia",
    "laboratorio", "laboratorios", "clinica", "clínica", "carrera", "calle",
    "tel", "telefono", "teléfono", "apartado", "bogota", "bogotá", "precio",
    "precios", "venta", "suscripcion", "suscripción", "oferta", "sociedad",
    "anonima", "anónima", "ltda", "cia", "compañia", "compañía",
    "whisky", "cerveza", "ron", "aguardiente", "vino", "champagne",
    "cigarros", "cigarrillos", "tabaco", "general", "coronel", "capitan",
    "capitán", "doctor", "doctora", "ingeniero", "ingeniera",
    "señor", "señora", "señorita", "don", "doña",
    "teatro", "cine", "salon", "salón", "hotel",
    "estamos", "venimos", "llegamos", "ofrecemos", "garantizamos",
}

ARTICULOS_ESP = {"el", "la", "los", "las", "un", "una", "unos", "unas", "lo"}
PREP_ESP = {"de", "del", "al", "en", "con", "por", "para", "entre", "sobre",
            "ante", "bajo", "sin", "tras", "hacia", "hasta", "desde", "según",
            "durante", "mediante"}
CONJ_ESP = {"y", "e", "o", "u", "que", "pero", "sino", "aunque", "cuando",
            "como", "si", "ni"}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _tiene_palabras_sin_vocales(texto: str) -> bool:
    for w in texto.split():
        w_alfa = re.sub(r'[^a-zA-ZáéíóúÁÉÍÓÚñÑ]', '', w)
        if len(w_alfa) >= 3 and not re.search(r'[aeiouáéíóúAEIOUÁÉÍÓÚ]', w_alfa):
            return True
    return False


def _contar_basura(texto: str) -> int:
    return len(RE_CHARS_BASURA.findall(texto))


def _es_watermark(linea: str) -> bool:
    tl = linea.lower().strip()
    return any(wm in tl for wm in WATERMARKS)


def _ratio_alfabetico(texto: str) -> float:
    if not texto:
        return 0.0
    alfa = sum(1 for c in texto if c.isalpha() or c == ' ')
    return alfa / len(texto)


def _es_nombre_personal(texto: str) -> bool:
    s = texto.strip()
    tokens = s.split()
    if not (2 <= len(tokens) <= 5):
        return False
    if not all(t[0].isupper() for t in tokens if len(t) > 1):
        return False
    if re.search(r'[\d~\[\]<>{}\\^$%@&!*|]', s):
        return False
    if _tiene_palabras_sin_vocales(s):
        return False
    tokens_lower = [t.lower() for t in tokens]
    if any(t in _NO_NOMBRES for t in tokens_lower):
        return False
    funcionales = ARTICULOS_ESP | PREP_ESP | CONJ_ESP
    if all(t in funcionales for t in tokens_lower):
        return False
    if any(len(t) > 20 for t in tokens):
        return False
    return True


def _detectar_seccion(titulo: str, texto: str) -> str:
    tl = (titulo + " " + texto[:500]).lower()
    for sec, pats in SECCIONES.items():
        # \b (límite de palabra): sin esto, "verso" (Poema/Verso) coincidía
        # como subcadena de "diversas", "conversación", "aniversario"... y
        # clasificaba mal ~30% del corpus real (medido 2026-08-20).
        if any(re.search(rf'\b{re.escape(p)}\b', tl) for p in pats):
            return sec
    return "General"


def _es_pagina_especial(texto: str) -> str:
    """Retorna tipo especial o "" si es página normal de artículo."""
    tl = texto.lower()
    palabras = len(texto.split())
    lineas = [l.strip() for l in texto.split('\n') if l.strip()]

    if palabras < 20:
        return "Portada/Cubierta"

    # Colofón: menciona directores, redacción, imprenta con pocas palabras
    if re.search(r'director(?:es)?|redacc[ií]on|jefe\s+de\s+redacci[oó]n|imprenta|tipograf[ií]a', tl):
        if palabras < 250:
            return "Colofón/Créditos"

    # Índice: muchas líneas con "... N" o "Pág. N"
    _RE_INDICE = re.compile(
        r'p[aá]g(?:ina)?s?\.?\s+\d+|\.\.\.\s*\d+|^\s*\d+\s*\.\s*\w',
        re.IGNORECASE | re.MULTILINE
    )
    if len(_RE_INDICE.findall(texto)) >= 3:
        return "Índice"

    # Publicidad pura: alta densidad de términos publicitarios y pocas palabras reales
    n_pub = sum(1 for pw in PALABRAS_PUBLICIDAD if pw in tl)
    if n_pub >= 4 and palabras < 400:
        return "Publicidad"

    # Galería fotográfica: pies de foto
    pies_foto = re.findall(r'\b[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]{5,40}[-—][^\n]{10,120}', texto)
    palabras_pie_foto = sum(1 for w in [
        'llegada', 'llegado', 'retrato', 'aparece', 'rodeado', 'rodeada',
        'fotografiado', 'fotografiada', 'momentos', 'aspecto general',
        'a su llegad', 'en compañía', 'junto a', 'durante la', 'al ser',
        'cuando fue', 'en el acto', 'en la tribuna', 'en primer término',
    ] if w in tl)
    if len(pies_foto) >= 3 and (palabras_pie_foto >= 2 or len(pies_foto) >= 5):
        return "Galería fotográfica"

    # Portada: menciona año, número, precio, semanario
    if palabras < 80:
        portada_signals = [
            r'año\s+[ivxlcdm]+', r'n[uú]m(?:ero)?\.?\s*\d+',
            r'precio\s+\d', r'centavos\b', r'semana(?:rio|l)?\b',
        ]
        if sum(1 for p in portada_signals if re.search(p, tl)) >= 2:
            return "Portada/Cubierta"

    return ""


def _extraer_autor(texto: str) -> tuple[str, float]:
    """Extrae autor del texto. Retorna (nombre, confianza)."""
    texto_norm = re.sub(r'\s*\n\s*', ' ', texto)
    cabeza = texto_norm[:800]
    cola   = texto_norm[-600:]

    # 1. Byline explícita al inicio
    m = RE_BYLINE.search(cabeza)
    if m:
        n = m.group(1).strip()
        if _es_nombre_personal(n):
            return n.title(), 0.92

    # 2. Firma final en mayúsculas
    m = RE_FIRMA_CAPS.search(cola)
    if m:
        n = m.group(1).strip()
        if _es_nombre_personal(n):
            return n.title(), 0.80

    # 3. Inicial + apellido al final
    m = RE_INICIAL.search(cola)
    if m:
        n = m.group(1).strip()
        if _es_nombre_personal(n):
            return n.strip(), 0.65

    return "Anónimo / Sin atribuir", 0.0


def _extraer_titulo_pagina(texto: str) -> str:
    """
    Extrae el título más probable de una página OCR del corpus Estampa/BNC.

    El OCR de la BNC mezcla columnas, así que los títulos tipográficos
    (en mayúsculas grandes en la revista impresa) aparecen como líneas
    ALL-CAPS en el texto OCR, muchas veces dispersas entre el cuerpo.

    Prioridades:
    1. Línea ALL-CAPS de 2-12 palabras, sin basura, ratio alfa alto → título tipográfico
    2. Byline "Por Nombre Apellido" al inicio → extraer lo que sigue
    3. Primera línea limpia de las primeras 5 que sea una frase completa
       (termina sin coma/punto, empieza en mayúscula, 3-10 palabras)
    4. Fallback: primera línea limpia
    """
    lineas = [l.strip() for l in texto.split('\n') if l.strip()]
    lineas_limpias = [l for l in lineas if
                      not _es_watermark(l) and
                      not RE_LINEA_BASURA.match(l) and
                      _contar_basura(l) == 0 and
                      not _tiene_palabras_sin_vocales(l) and
                      _ratio_alfabetico(l) >= 0.60]

    if not lineas_limpias:
        return "Sin título"

    # Prioridad 1: línea ALL-CAPS significativa
    # Buscar en TODO el texto (puede estar en medio de la página en revistas multicolumna)
    for l in lineas_limpias[:30]:
        tokens = l.split()
        if not (2 <= len(tokens) <= 12):
            continue
        palabras_largas = [t for t in tokens if len(t) >= 3]
        if not palabras_largas:
            continue
        # Al menos 60% de palabras largas en mayúsculas
        caps_ratio = sum(1 for t in palabras_largas if t.isupper()) / len(palabras_largas)
        if caps_ratio >= 0.7 and _ratio_alfabetico(l) >= 0.70:
            return l.title()

    # Prioridad 2: después de "Por X" hay que buscar el título en líneas siguientes
    for i, l in enumerate(lineas_limpias[:5]):
        if re.match(r'^[Pp]or\s+[A-ZÁÉÍÓÚÑ]', l) and i + 1 < len(lineas_limpias):
            candidato = lineas_limpias[i + 1]
            tok = candidato.split()
            if 2 <= len(tok) <= 12 and candidato[0].isupper():
                return candidato

    # Prioridad 3: primera línea limpia que sea frase de título (no fragmento)
    for l in lineas_limpias[:8]:
        tokens = l.split()
        # Evitar líneas que claramente son fragmentos de cuerpo:
        # - empieza en minúscula (continuación)
        # - termina en coma, punto, dos puntos (frase de cuerpo)
        # - empieza con artículo/preposición en minúscula
        if not l or not l[0].isupper():
            continue
        if l.endswith((',', '.', ':', ';', '...')):
            continue
        if re.match(r'^\d', l):
            continue
        if 2 <= len(tokens) <= 12:
            return l

    # Fallback: primera línea limpia
    return lineas_limpias[0] if lineas_limpias else "Sin título"


# ─────────────────────────────────────────────────────────────────────────────
# LIMPIEZA DE TEXTO OCR
# ─────────────────────────────────────────────────────────────────────────────

def limpiar_texto_ocr(texto: str) -> str:
    """Pre-procesa texto OCR: reconecta guiones, normaliza espacios, elimina basura."""
    # Reconectar palabras partidas por guión al final de línea
    texto = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', texto)
    # Normalizar espacios múltiples dentro de cada línea
    lineas = []
    for linea in texto.split('\n'):
        linea_limpia = re.sub(r' {2,}', ' ', linea)
        lineas.append(linea_limpia)
    texto = '\n'.join(lineas)
    # Eliminar números de página aislados
    texto = re.sub(r'^\s*\d{1,4}\s*$', '', texto, flags=re.MULTILINE)
    # Colapsar exceso de líneas en blanco
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    return texto.strip()


def _limpiar_lineas(texto: str) -> str:
    """Elimina líneas de watermark y basura OCR pura del texto."""
    lineas_out = []
    for linea in texto.split('\n'):
        s = linea.strip()
        if _es_watermark(s):
            continue
        if RE_LINEA_BASURA.match(s) and len(s) <= 6:
            continue
        # Líneas con >50% caracteres no alfabéticos (ruido puro)
        if s and _ratio_alfabetico(s) < 0.3 and len(s) > 5:
            continue
        lineas_out.append(linea)
    return '\n'.join(lineas_out)


# ─────────────────────────────────────────────────────────────────────────────
# SEGMENTACIÓN DE UNA PÁGINA OCR → una unidad de contenido
# ─────────────────────────────────────────────────────────────────────────────

def _procesar_pagina_ocr(texto_raw: str, pagina_nombre: str) -> dict | None:
    """
    Convierte el texto OCR de una página en un dict de artículo/fragmento.
    Retorna None si la página no tiene contenido útil.
    """
    tipo_especial = _es_pagina_especial(texto_raw)

    texto = limpiar_texto_ocr(texto_raw)
    texto = _limpiar_lineas(texto)

    palabras = len(texto.split())
    if palabras < 15:
        return None

    autor, conf_autor = _extraer_autor(texto)

    if tipo_especial:
        titulo = tipo_especial
        seccion = tipo_especial
    else:
        titulo = _extraer_titulo_pagina(texto)
        seccion = _detectar_seccion(titulo, texto)

    # Detectar si continúa en otra página
    m_cont = RE_CONTINUA.search(texto)
    continua_en = int(m_cont.group(1)) if m_cont else None

    return {
        "titulo":          titulo,
        "autor":           autor,
        "confianza_autor": round(conf_autor, 2),
        "seccion":         seccion,
        "texto":           texto,
        "palabras":        palabras,
        "pagina":          pagina_nombre,
        "tipo_pagina":     tipo_especial or "Artículo",
        "_continua_en":    continua_en,
        "_es_especial":    bool(tipo_especial),
    }


# ─────────────────────────────────────────────────────────────────────────────
# CONSOLIDACIÓN DE PÁGINAS CONSECUTIVAS
# ─────────────────────────────────────────────────────────────────────────────

def _consolidar_paginas(paginas: list[dict]) -> list[dict]:
    """
    Une páginas que son continuación del mismo artículo.

    Señales de continuación:
    - La página previa tiene _continua_en = N (referencia explícita)
    - La página previa tiene pocas palabras (<120) y la actual empieza en minúscula
    - Ambas tienen el mismo autor conocido
    - Ninguna es página especial

    Señales de nuevo artículo:
    - La página actual tiene tipo_pagina especial
    - La página actual tiene un título ALL-CAPS diferente y suficiente cuerpo previo
    - El autor cambió
    """
    if not paginas:
        return []

    resultado = []
    acum = paginas[0].copy()

    for pag in paginas[1:]:
        prev = acum

        # No consolidar páginas especiales
        if pag["_es_especial"] or prev["_es_especial"]:
            if prev["palabras"] >= 15:
                resultado.append(_limpiar_dict(prev))
            acum = pag.copy()
            continue

        # Señal explícita de continuación
        continua_explicita = (prev.get("_continua_en") is not None)

        # Continuación implícita: artículo corto + inicio en minúscula
        inicio_minusc = bool(
            pag["texto"].lstrip()[:1].islower() or
            pag["texto"].lstrip()[:3].startswith(("el ", "la ", "lo ", "un ",
                                                   "una", "que", "su ", "se ",
                                                   "de ", "del", "y ", "en "))
        )
        fragmento_corto = prev["palabras"] < 150

        # Autores distintos conocidos → nuevo artículo
        autores_distintos = (
            prev["autor"] != "Anónimo / Sin atribuir" and
            pag["autor"] != "Anónimo / Sin atribuir" and
            prev["autor"] != pag["autor"]
        )

        if autores_distintos:
            resultado.append(_limpiar_dict(prev))
            acum = pag.copy()
        elif continua_explicita or (fragmento_corto and inicio_minusc):
            # Consolidar: fusionar texto, conservar título del primero
            acum["texto"]    += "\n\n" + pag["texto"]
            acum["palabras"] += pag["palabras"]
            acum["pagina"]   += f"-{pag['pagina']}"
            # Si encontramos autor en continuación, actualizar
            if (acum["autor"] == "Anónimo / Sin atribuir" and
                    pag["autor"] != "Anónimo / Sin atribuir"):
                acum["autor"] = pag["autor"]
                acum["confianza_autor"] = pag["confianza_autor"]
            # Propagar continuación
            acum["_continua_en"] = pag.get("_continua_en")
        else:
            resultado.append(_limpiar_dict(prev))
            acum = pag.copy()

    if acum["palabras"] >= 15:
        resultado.append(_limpiar_dict(acum))

    return resultado


def _limpiar_dict(d: dict) -> dict:
    """Elimina campos internos del dict antes de devolver al usuario."""
    return {k: v for k, v in d.items() if not k.startswith("_")}


# ─────────────────────────────────────────────────────────────────────────────
# SEGMENTACIÓN DESDE TEXTO OCR (punto de entrada para carpeta de .txt)
# ─────────────────────────────────────────────────────────────────────────────

def segmentar_texto_ocr(texto: str, pagina_nombre: str) -> list[dict]:
    """
    API de compatibilidad: procesa el texto OCR de una sola página.
    Retorna lista de 0 o 1 artículo (la página como unidad).
    """
    resultado = _procesar_pagina_ocr(texto, pagina_nombre)
    if resultado is None:
        return []
    return [_limpiar_dict(resultado)]


# ─────────────────────────────────────────────────────────────────────────────
# SEGMENTACIÓN DESDE PDF DIGITAL (PyMuPDF)
# ─────────────────────────────────────────────────────────────────────────────

def segmentar_numero_pdf(pdf_path: Path) -> list[dict]:
    """
    Segmentación basada en bloques PyMuPDF con tamaño tipográfico.
    Para PDFs con texto digital no hay ruido OCR, la señal de fuente es fiable.
    """
    try:
        import fitz
    except ImportError:
        return []

    doc   = fitz.open(str(pdf_path))
    sizes = []
    for page in doc:
        for b in page.get_text("dict")["blocks"]:
            if b["type"] != 0:
                continue
            for l in b["lines"]:
                for s in l["spans"]:
                    t = s["text"].strip()
                    if t and len(t) >= 4:
                        sizes.append(s["size"])

    if not sizes:
        doc.close()
        return []

    size_cuerpo   = statistics.median(sizes)
    umbral_titulo = size_cuerpo * 1.35

    arts = []
    curr = {"titulo": None, "parts": [], "n_palabras": 0, "pi": 1}

    def commit(pf: int):
        texto = '\n'.join(curr["parts"]).strip()
        lineas_limpias = [l for l in texto.split('\n') if not _es_watermark(l)]
        texto = '\n'.join(lineas_limpias).strip()
        nw = len(texto.split())
        if nw < 40:
            return
        t  = curr["titulo"] or "Sin título"
        au, co = _extraer_autor(texto)
        tipo_esp = _es_pagina_especial(texto)
        seccion  = _detectar_seccion(t, texto)
        if tipo_esp and seccion == "General":
            seccion = tipo_esp
        arts.append({
            "titulo": t, "autor": au, "confianza_autor": round(co, 2),
            "seccion": seccion,
            "texto": texto, "palabras": nw,
            "pagina": f"p{curr['pi']:04d}–p{pf:04d}",
            "tipo_pagina": tipo_esp or "Artículo",
        })
        curr["titulo"] = None
        curr["parts"]  = []
        curr["n_palabras"] = 0
        curr["pi"] = pf

    for pn, page in enumerate(doc, 1):
        for b in page.get_text("dict")["blocks"]:
            if b["type"] != 0:
                continue
            for line in b["lines"]:
                spans = line["spans"]
                if not spans:
                    continue
                ms = max(s["size"] for s in spans)
                tl = ' '.join(s["text"] for s in spans).strip()
                tl = re.sub(r' {2,}', ' ', tl)
                if not tl or _es_watermark(tl):
                    continue

                fuentes_span = [s.get("font", "").lower() for s in spans]
                es_ocr_font  = any("ocr" in f or "hidden" in f for f in fuentes_span)
                es_coord_basura = bool(re.match(r'^\s*\d{1,3}[-/]\d{1,3}', tl))

                es_titulo = (
                    not es_ocr_font
                    and not es_coord_basura
                    and ms >= umbral_titulo
                    and 4 <= len(tl) <= 120
                    and 2 <= len(tl.split()) <= 12
                    and not tl.endswith(('.', ','))
                    and _contar_basura(tl) == 0
                    and not _tiene_palabras_sin_vocales(tl)
                )

                if es_titulo and curr["n_palabras"] >= 40:
                    commit(pn)
                    curr["titulo"] = tl
                    curr["pi"] = pn
                else:
                    curr["parts"].append(tl)
                    curr["n_palabras"] += len(tl.split())

    commit(doc.page_count)
    doc.close()
    gc.collect()
    return arts


# ─────────────────────────────────────────────────────────────────────────────
# SEGMENTACIÓN DESDE PDF PAPER CAPTURE (BNC/Adobe Acrobat)
# ─────────────────────────────────────────────────────────────────────────────

def segmentar_numero_paper_capture(pdf_path: Path) -> list[dict]:
    """
    Segmentación para PDFs Adobe Paper Capture (BNC).
    Usa alto_reconstructor para reconstrucción posicional.
    """
    try:
        from core.alto_reconstructor import reconstruir_pdf_completo
    except ImportError:
        return []

    paginas = reconstruir_pdf_completo(pdf_path)
    if not paginas:
        return []

    arts = []
    titulo_actual = None
    cuerpo_partes = []
    pagina_ini = "p0001"
    n_palabras = 0

    def _commit(pagina_fin: str):
        nonlocal titulo_actual, cuerpo_partes, n_palabras
        cuerpo = "\n".join(cuerpo_partes).strip()
        nw = len(cuerpo.split())
        if nw < 40:
            return
        t = titulo_actual or "Sin titulo"
        au, co = _extraer_autor(cuerpo)
        tipo_esp = _es_pagina_especial(cuerpo)
        seccion  = _detectar_seccion(t, cuerpo)
        if tipo_esp and seccion == "General":
            seccion = tipo_esp
        arts.append({
            "titulo":          t,
            "autor":           au,
            "confianza_autor": round(co, 2),
            "seccion":         seccion,
            "texto":           cuerpo,
            "palabras":        nw,
            "pagina":          f"{pagina_ini}-{pagina_fin}",
            "tipo_pagina":     tipo_esp or "Articulo",
        })
        titulo_actual = None
        cuerpo_partes = []
        n_palabras = 0

    for pag in paginas:
        pagina_id = pag["pagina"]
        for linea in pag.get("lineas", []):
            texto_l = linea["texto"].strip()
            if not texto_l or _es_watermark(texto_l):
                continue
            if linea.get("es_titulo") and len(texto_l.split()) >= 2:
                if n_palabras >= 50:
                    _commit(pagina_id)
                    pagina_ini = pagina_id
                titulo_actual = texto_l
            else:
                cuerpo_partes.append(texto_l)
                n_palabras += len(texto_l.split())

    _commit(paginas[-1]["pagina"] if paginas else "p0001")
    return arts


# ─────────────────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def segmentar_numero(
    ocr_dir:  Path,
    nombre:   str,
    pdf_path: Path | None = None,
) -> list[dict]:
    """
    Segmenta un número de revista. Prioridad:
    1. PDF Paper Capture → reconstrucción posicional
    2. PDF digital nativo → segmentación por tamaño de fuente
    3. Textos OCR en disco → una unidad por página + consolidación
    """
    if pdf_path and pdf_path.exists():
        # Paper Capture
        try:
            from core.alto_reconstructor import es_pdf_paper_capture
            if es_pdf_paper_capture(pdf_path):
                arts = segmentar_numero_paper_capture(pdf_path)
                if arts:
                    for a in arts:
                        a["numero"] = nombre
                    return arts
        except Exception:
            pass

        # PDF digital nativo
        try:
            import fitz
            doc    = fitz.open(str(pdf_path))
            muestra = ''.join(doc[i].get_text() for i in range(min(3, doc.page_count)))
            doc.close()
            if len(muestra.split()) > 100:
                arts = segmentar_numero_pdf(pdf_path)
                if arts:
                    for a in arts:
                        a["numero"] = nombre
                    return arts
        except Exception:
            pass

    # Fallback: textos OCR en carpeta
    carpeta = ocr_dir / nombre
    if not carpeta.exists():
        return []

    # Procesar cada página como unidad atómica
    paginas_raw = []
    for tf in sorted(carpeta.glob("*.txt")):
        texto = tf.read_text("utf-8", errors="replace")
        pag = _procesar_pagina_ocr(texto, tf.stem)
        if pag is not None:
            pag["numero"] = nombre
            paginas_raw.append(pag)

    # Consolidar páginas consecutivas del mismo artículo
    articulos = _consolidar_paginas(paginas_raw)
    for a in articulos:
        a["numero"] = nombre

    gc.collect()
    return articulos


def _consolidar_cortes(arts: list[dict]) -> list[dict]:
    """Alias para compatibilidad con código que llama a esta función."""
    return _consolidar_paginas(arts) if arts and "_continua_en" in arts[0] else arts
