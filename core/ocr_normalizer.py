"""
core/ocr_normalizer.py — Normalización post-OCR para prensa histórica
                         en español (Colombia, siglos XIX-XX).

Correcciones aplicadas en orden:
  1. Normalización Unicode NFC (compone diacríticos descompuestos)
  2. Eliminación de BOM y caracteres de control invisibles
  3. Conversión de s-larga (ſ) y otras ligaduras históricas
  4. Unión de palabras partidas por guión al final de línea
  5. Sustituciones de caracteres OCR sistemáticas
  6. Corrección de dígitos incrustados en palabras
  7. Limpieza de ruido de línea (puntos volados, guiones sueltos, etc.)
  8. Correcciones de vocabulario específicas de prensa colombiana 1930-50
  9. Normalización de espaciado y saltos de línea

No requiere diccionario externo ni conexión a internet.
Diseñado para ser rápido y determinista.

Mejoras v10.1:
  - Normalización Unicode NFC obligatoria (resuelve diacríticos descompuestos)
  - Soporte para s-larga (ſ → s) y otras grafías históricas
  - Patron de números de página más agresivo
  - Mejores patrones para prensa colombiana (Cra., No., Dpto.)
  - Estadísticas detalladas de normalización
  - Bug fix: orden incorrecto vocab → dígitos que causaba "cincc" → "cinco" parcial
"""

import re
import unicodedata
from pathlib import Path

# ── Tabla de sustituciones carácter a carácter ────────────────────────────────
# Estos son errores OCR sistemáticos del escaneado de prensa en papel amarillento

_CHAR_MAP = str.maketrans({
    # Caracteres confundidos con tilde/virgulilla
    "~": "n",    # muy frecuente: "señ~r" → "señor", "oñ~" → "oño"
    "`": "'",
    "¨": "ü",
    # Caracteres confundidos por forma
    "$": "s",    # "E$ta" → "Esta"
    "@": "a",
    "|": "l",    # solo en palabras
    # S-larga histórica y variantes tipográficas de época
    "ſ": "s",    # s-larga (muy frecuente en impresos hasta ~1850, reaparece en OCR)
    "ß": "ss",   # confusión con ß alemana en OCR de imprenta antigua
    # Ligaduras tipográficas clásicas
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬀ": "ff",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "ﬅ": "st",
    "ﬆ": "st",
    "œ": "oe",   # ligadura francesa en textos de época
    "æ": "ae",
    # Comillas tipográficas → ASCII
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": ",",   # coma baja → coma
    "\u201b": "'",
    # Guiones tipográficos
    "\u2014": "—",   # em dash → preservar como —
    "\u2013": "-",   # en dash → guión
    "\u2012": "-",
    "\u2010": "-",   # guión no-rompedor
    "\u2011": "-",   # guión no-rompedor
    # Espacios especiales → espacio normal
    "\u00a0": " ",   # espacio no-rompedor
    "\u2009": " ",   # espacio fino
    "\u200b": "",    # espacio de ancho cero
    "\u200c": "",    # no-joiner
    "\u200d": "",    # joiner
    "\ufeff": "",    # BOM
    "\u00ad": "",    # guión suave (soft hyphen) → eliminar
    # Caracteres que el OCR confunde con letras españolas
    "¡": "i",    # ¡ al inicio de palabra → probable 'i' manglada (fuera de exclamación)
    # Símbolos de párrafo y sección que el OCR malinterpreta
    "§": "S",
    "¶": "",
    # Caracteres de control
    "\x0c": "\n",    # form feed → salto de línea
    "\x0b": "\n",    # vertical tab → salto
    "\r": "",        # CR → eliminar (quedará solo LF)
})

# ── Caracteres de control que hay que eliminar ────────────────────────────────
_RE_CONTROL = re.compile(r'[\x00-\x08\x0e-\x1f\x7f]')

# ── Patrones de dígitos confundidos con letras en palabras españolas ──────────
# Se aplican SOLO cuando el dígito está rodeado de letras (contexto de palabra)
# Formato: (patrón_regex, sustitución)

_DIGIT_IN_WORD = [
    # "m6s" → "más",  "m6s" al final
    (r'\b([a-záéíóúüñ]+)6([a-záéíóúüñ]*)\b', lambda m:
        m.group(1) + ("s" if m.group(2) == "s" else "ó") + m.group(2)),
    # "11o" → "llo", "1l" → "ll" — doble ele
    (r'\b1([lo])([a-záéíóúüñ]+)\b', lambda m: "l" + m.group(1) + m.group(2)),
    # "11egar" → "llegar"
    (r'\b11([a-záéíóúüñ]+)\b', lambda m: "ll" + m.group(1)),
    # "n0" → "no", "d0" → "do" — cero como 'o' al final
    (r'\b([a-záéíóúüñ]+)0\b', lambda m: m.group(1) + "o"),
    # "0" al inicio de palabra de letras → "O" mayúscula
    (r'\b0([a-záéíóúüñ]+)\b', lambda m: "O" + m.group(1)),
    # "1" solitario entre letras → "l" o "i"
    (r'\b([bcdfghjklmnpqrstvwxyz])1([a-záéíóúüñ]+)\b', lambda m:
        m.group(1) + "i" + m.group(2)),
    # "4e" → "de" — 4 como 'd'
    (r'\b4([aeiouáéíóúüñ][a-záéíóúüñ]*)\b', lambda m: "d" + m.group(1)),
    # "d4" → "da"
    (r'\b([a-záéíóúüñ]+)4\b', lambda m: m.group(1) + "a"),
    # "8" → "B" cuando está al inicio de palabra con letras
    (r'\b8([a-záéíóúüñ]{2,})\b', lambda m: "B" + m.group(1)),
    # "Go1e" → "Gole", "Go1" → "Gol" — 1 como 'l' entre vocales/consonantes
    (r'\b([A-ZÁÉÍÓÚÜÑa-záéíóúüñ]+)1([A-ZÁÉÍÓÚÜÑa-záéíóúüñ]*)\b', lambda m:
        m.group(1) + "l" + m.group(2)),
]

# ── Sustituciones de secuencias OCR comunes en español colonial/moderno ───────

_SEQ_REPLACEMENTS = [
    # "·" punto volado aislado (no dentro de números) → espacio
    (r'(?<!\d)\·(?!\d)', ' '),
    # Guión de continuación de párrafo suelto: línea que solo tiene "-" o "—"
    (r'^\s*[-—~·]+\s*$', '', re.MULTILINE),
    # "-~" o "~-" o "~." ruido de borde de página
    (r'[-~]{1,3}[\s]*\.\s*[-~]{0,2}', ' '),
    # Secuencia "... -" al final de línea que no es puntuación real
    (r'\s+-\s*$', '', re.MULTILINE),
    # "f0" → "fo" cuando f precede a 0 en contexto de palabra española
    (r'\bf0([a-záéíóúüñ])', lambda m: "fo" + m.group(1)),
    # "ii" → "li" en contextos específicos (posibili → posibili)
    (r'([bcdfghjklmnpqrstvwxyz])ii([a-záéíóúüñ])', lambda m:
        m.group(1) + "li" + m.group(2)),
    # Puntos dentro de palabras (no abreviaturas): "bo.quete" → "bo quete"
    # Solo si hay letras a ambos lados y NO es abreviatura de 2 chars
    (r'(?<=[a-záéíóúüñ]{3})\.(?=[a-záéíóúüñ]{2,})', ' '),
    # Números de página aislados al inicio/final de línea (1-999)
    # Deben estar solos en la línea para ser eliminados
    (r'^\s*\d{1,4}\s*$', '', re.MULTILINE),
    # Espacios múltiples → uno
    (r'  +', ' '),
    # Líneas completamente vacías múltiples → una sola línea vacía
    (r'\n{3,}', '\n\n'),
]

# ── Abreviaturas de prensa colombiana años 30-50 ──────────────────────────────
# Proteger abreviaturas antes de la normalización de puntos
_ABREVIATURAS_PROTEGIDAS = {
    # Direcciones y geografía colombiana
    r'\bCra\.': 'Carrera',
    r'\bCl\.': 'Calle',
    r'\bAv\.': 'Avenida',
    r'\bDpto\.': 'Departamento',
    r'\bDr\.': 'Dr.',
    r'\bDra\.': 'Dra.',
    r'\bSr\.': 'Sr.',
    r'\bSra\.': 'Sra.',
    r'\bSrta\.': 'Srta.',
    # Números ordinales mal escaneados
    r'\bN[oº°]\.?\s*(\d)': r'No. \1',
    r'\bn[oº°]\.?\s*(\d)': r'No. \1',
}

# ── Diccionario de correcciones específicas de vocabulario de época ───────────
# Errores muy frecuentes en digitalización de prensa colombiana años 30-40

_VOCAB_FIXES = {
    # OCR confunde caracteres similares en tipografía de época
    r'\bindustrio\b': 'industria',
    r'\bmilloees\b': 'millones',
    r'\bpocferomos\b': 'podremos',
    r'\bmercacfo\b': 'mercado',
    r'\bplonteor\b': 'plantear',
    r'\bplonteamiellta\b': 'planteamiento',
    r'\bplonteamiento\b': 'planteamiento',
    # "boston" fuera de nombre → "bastan" (error OCR muy frecuente)
    r'\bboston\b(?!\s+(?:terrier|común|bull))': 'bastan',
    r'\bcloro\b(?!\s+(?:gas|como|de))': 'claro',
    r'\bsembarga\b': 'embargo',
    r'\bpoli\.tico\b': 'político',
    # Cargos y títulos mal transcritos
    r'\bGober110dor\b': 'Gobernador',
    r'\bGober11ador\b': 'Gobernador',
    r'\b110dor\b': 'nador',
    r'\bMini~o\b': 'Ministro',
    r'\bEconomicc\b': 'Economía',
    r'\bdes4e\b': 'desde',
    r'\b4esde\b': 'desde',
    r'\bcincc\b': 'cinco',
    r'\bequiporor\b': 'equiparar',
    r'\bhoce\b': 'hace',
    r'\bembarga\b(?!\s+de)': 'embargo',
    r'\bnaeso\b': 'nació',
    r'\bogitación\b': 'agitación',
    # Artículos y preposiciones frecuentemente mal transcritos
    r'\bUlt\b': 'un',
    r'\bm6s\b': 'más',
    r'\bM6s\b': 'Más',
    r'\bS6lo\b': 'Sólo',
    r'\bs6lo\b': 'sólo',
    r'\bp6r\b': 'por',
    r'\bés\b(?=\s+[a-záéíóúüñ])': 'es',
    r'\bqu6\b': 'que',
    r'\bd6\b': 'de',
    r'\bs4\b': 'su',
    # Topónimos colombianos mal escaneados
    r'\bBogot[á4]?\b': 'Bogotá',
    r'\bMedellin\b': 'Medellín',
    r'\bBarranquil1a\b': 'Barranquilla',
    r'\bCa1i\b': 'Cali',
    r'\bManiza1es\b': 'Manizales',
    # Palabras de época específicas de Estampa/Cromos
    r'\bsema11a\b': 'semana',
    r'\bsema11al\b': 'semanal',
    r'\bco1ombia\b': 'colombia',
    r'\bco1ombiano\b': 'colombiano',
    r'\brepublica\b': 'república',
    r'\bRepublica\b': 'República',
    # ── Errores Tesseract frecuentes en Estampa 1930-40 ──────────────────────
    # Signo ! confundido con letra i/l antes de vocal → "c!e" = "de", "d!a" = "dia"
    r'\bc!e\b': 'de',
    r'\bc!el\b': 'del',
    r'\bc!a\b': 'día',
    r'\bc!as\b': 'días',
    r'\bl!o\b': 'lio',
    r'\br!o\b': 'río',
    r'\br!os\b': 'ríos',
    r'\bf!n\b': 'fin',
    r'\bf!nes\b': 'fines',
    # Tilde/acento ~ como n/ñ: "señ~r" → "señor", "Rooseve~t" → "Roosevelt"
    r'([A-Za-záéíóúüñ]+)~t\b': r'\1t',   # ~t al final → solo t (Roosevelt~t → Roosevelt)
    r'([A-Za-záéíóúüñ]+)~([A-Za-záéíóúüñ])': r'\1\2',  # letra~letra → unir sin ~
    # "1" como "i" o "l" en apellidos y nombres comunes
    r'\bUni1os\b': 'Unidos',
    r'\bUni1as\b': 'Unidas',
    r'\bposi1le\b': 'posible',
    r'\bposi1idad\b': 'posibilidad',
    r'\bposi1ilidad\b': 'posibilidad',
    r'\bpub1icó\b': 'publicó',
    r'\bpub1icación\b': 'publicación',
    r'\bpub1ico\b': 'público',
    r'\bpob1ación\b': 'población',
    r'\bpob1ado\b': 'poblado',
    r'\bco1ono\b': 'colono',
    r'\bco1onos\b': 'colonos',
    r'\bco1ega\b': 'colega',
    r'\bco1egio\b': 'colegio',
    r'\bvo1untad\b': 'voluntad',
    r'\bvo1ver\b': 'volver',
    r'\breso1ución\b': 'resolución',
    r'\bso1ución\b': 'solución',
    r'\bso1o\b': 'solo',
    r'\bso1amente\b': 'solamente',
    r'\bE1\b(?=\s+[A-Z])': 'El',   # "E1 Presidente" → "El Presidente"
    r'\bE1\s': 'El ',
    r'\bDe1\b': 'Del',
    r'\bde1\b': 'del',
    r'\ba1\b': 'al',
    r'\bA1\b(?=\s+[A-Z])': 'Al',
    # Punto dentro de palabra con letras a ambos lados (OCR fragmenta palabras)
    r'\bc\.omurtcs\b': 'comunes',
    r'\bc\.omun\b': 'común',
    r'\bc\.omo\b': 'como',
    r'\bc\.on\b': 'con',
    r'\bc\.uando\b': 'cuando',
    r'\bc\.ual\b': 'cual',
    # "paro" como "para" (error tipográfico frecuente en OCR de Estampa)
    r'\bparo\s+defender\b': 'para defender',
    r'\bparo\s+el\b': 'para el',
    r'\bparo\s+la\b': 'para la',
    r'\bparo\s+los\b': 'para los',
    r'\bparo\s+las\b': 'para las',
    r'\bparo\s+que\b': 'para que',
    r'\bparo\s+un\b': 'para un',
    r'\bparo\s+una\b': 'para una',
    # "lo" como "la" antes de sustantivo femenino (error fonético OCR)
    r'\blo\s+necesidad\b': 'la necesidad',
    r'\blo\s+semana\b': 'la semana',
    r'\blo\s+forma\b': 'la forma',
    r'\blo\s+hesto\b': 'la fiesta',
    r'\bhesto\b': 'fiesta',
    # Firma/sello de Biblioteca Nacional al final de páginas
    r'Digitalizado Biblioteca Nacional\s+de Colombia': '',
    r'Digitalizado por la Biblioteca Nacional de Colombia': '',
}

# ── Normalización de caracteres Unicode con doble codificación ────────────────
# Algunos escáners producen caracteres compuestos en vez de precompuestos
# Ejemplo: 'a' + '\u0301' (combining accent) → 'á' (precompuesto)
# La normalización NFC resuelve esto.

def _normalizar_unicode(texto: str) -> str:
    """
    Aplica normalización NFC: compone diacríticos descompuestos.
    Elimina caracteres de control y BOM.
    Convierte s-larga y otras grafías históricas antes del NFC.
    """
    # Primero eliminar caracteres de control
    texto = _RE_CONTROL.sub('', texto)
    # Normalizar a NFC (compone diacríticos)
    texto = unicodedata.normalize('NFC', texto)
    return texto


# ══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def normalizar_texto_ocr(texto: str,
                          unir_silabas: bool = True,
                          corregir_chars: bool = True,
                          corregir_digitos: bool = True,
                          corregir_vocab: bool = True,
                          limpiar_ruido: bool = True,
                          normalizar_unicode: bool = True,
                          spell_check: bool = False) -> str:
    """
    Normaliza el texto producido por OCR en prensa histórica española.

    Parámetros
    ----------
    texto            : str   Texto OCR crudo a normalizar
    unir_silabas     : bool  Unir palabras partidas por guión al final de línea
    corregir_chars   : bool  Sustituir caracteres OCR erróneos (~, $, |, ſ, etc.)
    corregir_digitos : bool  Corregir dígitos incrustados en palabras
    corregir_vocab   : bool  Aplicar correcciones de vocabulario específicas
    limpiar_ruido    : bool  Eliminar líneas de ruido y artefactos tipográficos
    normalizar_unicode: bool Aplicar NFC y eliminar caracteres de control (recomendado)
    spell_check      : bool  Corrección Hunspell (lento, requiere spylls+diccionario es_ES)

    Retorna
    -------
    str  Texto normalizado
    """
    if not texto or not texto.strip():
        return texto

    # ── 0. Normalización Unicode (siempre primero) ────────────────────────────
    if normalizar_unicode:
        texto = _normalizar_unicode(texto)

    # ── 1. Unión de palabras partidas (antes de cambiar chars) ────────────────
    if unir_silabas:
        texto = _unir_palabras_partidas(texto)

    # ── 2. Sustituciones char a char ──────────────────────────────────────────
    if corregir_chars:
        texto = texto.translate(_CHAR_MAP)

    # ── 3. Correcciones de vocabulario específicas ────────────────────────────
    # Antes de corregir dígitos, para que "cincc" → "cinco" no interfiera
    if corregir_vocab:
        for patron, reemplazo in _VOCAB_FIXES.items():
            texto = re.sub(patron, reemplazo, texto, flags=re.IGNORECASE)

    # ── 4. Corrección de dígitos en palabras ──────────────────────────────────
    if corregir_digitos:
        for patron, reemplazo in _DIGIT_IN_WORD:
            texto = re.sub(patron, reemplazo, texto, flags=re.IGNORECASE)

    # ── 5. Limpieza de ruido y secuencias ─────────────────────────────────────
    if limpiar_ruido:
        for item in _SEQ_REPLACEMENTS:
            if len(item) == 3:
                patron, reemplazo, flags = item
                texto = re.sub(patron, reemplazo, texto, flags=flags)
            else:
                patron, reemplazo = item
                texto = re.sub(patron, reemplazo, texto)

    # ── 6. Corrección ortográfica Hunspell (opcional, conservadora) ──────────
    if spell_check:
        try:
            from core.spell_corrector import corregir_texto_ocr
            texto = corregir_texto_ocr(texto)
        except Exception:
            pass  # si spylls no está disponible, continuar sin corrección

    # ── 7. Limpieza final de espaciado ────────────────────────────────────────
    texto = _limpiar_espaciado(texto)

    return texto


def _unir_palabras_partidas(texto: str) -> str:
    """
    Une palabras partidas al final de línea con guión.

    Casos manejados:
      "ex-\ntranjero"    → "extranjero"   (guión de partición tipográfica)
      "ex-\n  tranjero"  → "extranjero"   (con sangría)
      "ex—\ntranjero"    → "extranjero"   (guión largo OCR)

    NO une:
      "1939-\n1940"       (guión entre números = rango)
      "López-\nPumarejo"  (guión en nombre propio compuesto — preservar)
      "-\nPrimer punto"   (guión de lista)
    """
    lineas = texto.split('\n')
    resultado = []
    i = 0
    while i < len(lineas):
        linea_actual = lineas[i]
        # ¿Termina la línea con guión tipográfico de partición?
        m = re.search(r'([a-záéíóúüñA-ZÁÉÍÓÚÜÑ]{2,})-\s*$', linea_actual)
        if m and i + 1 < len(lineas):
            siguiente = lineas[i + 1].lstrip()
            # La siguiente línea empieza con letra minúscula → continuación
            if siguiente and siguiente[0].islower():
                m2 = re.match(r'([a-záéíóúüñ]+)(.*)', siguiente)
                if m2:
                    prefijo  = linea_actual[:m.start()]
                    palabra1 = m.group(1)
                    palabra2 = m2.group(1)
                    resto    = m2.group(2)
                    linea_unida = prefijo + palabra1 + palabra2 + resto
                    resultado.append(linea_unida)
                    i += 2
                    continue
        resultado.append(linea_actual)
        i += 1

    return '\n'.join(resultado)


def _limpiar_espaciado(texto: str) -> str:
    """Normaliza espacios dentro de líneas sin eliminar estructura de párrafos."""
    lineas = texto.split('\n')
    limpias = []
    for linea in lineas:
        # Espacios múltiples dentro de línea → uno
        linea = re.sub(r'  +', ' ', linea)
        # Espacio antes de puntuación final → quitar
        linea = re.sub(r'\s+([.,;:!?)\]])', r'\1', linea)
        # Espacio después de paréntesis/corchete abierto
        linea = re.sub(r'([(¡¿\[])\s+', r'\1', linea)
        limpias.append(linea)
    # Máximo 2 líneas vacías consecutivas
    texto = '\n'.join(limpias)
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    return texto.strip()


# ══════════════════════════════════════════════════════════════════════════════
# NORMALIZACIÓN DE ARCHIVO
# ══════════════════════════════════════════════════════════════════════════════

def normalizar_archivo(txt_path: "Path",
                        guardar_original: bool = True,
                        **kwargs) -> dict:
    """
    Lee un archivo .txt OCR, lo normaliza y lo sobreescribe.
    Si guardar_original=True, guarda el original como .txt.orig

    Retorna dict con estadísticas de la normalización.
    """
    from pathlib import Path
    txt_path = Path(txt_path)

    original = txt_path.read_text(encoding="utf-8", errors="replace")

    # Guardar original si se pide
    if guardar_original:
        orig_path = txt_path.with_suffix(".txt.orig")
        if not orig_path.exists():
            orig_path.write_text(original, encoding="utf-8")

    normalizado = normalizar_texto_ocr(original, **kwargs)

    txt_path.write_text(normalizado, encoding="utf-8")

    # Estadísticas detalladas
    palabras_orig = len(original.split())
    palabras_norm = len(normalizado.split())
    chars_cambiados = sum(1 for a, b in zip(original, normalizado) if a != b)
    # Detectar cuántas palabras partidas se unieron
    guiones_unidos = len(re.findall(r'\w-\s*\n', original)) - \
                     len(re.findall(r'\w-\s*\n', normalizado))

    return {
        "palabras_original":    palabras_orig,
        "palabras_normalizado": palabras_norm,
        "chars_cambiados":      chars_cambiados,
        "ratio_cambio":         round(chars_cambiados / max(len(original), 1), 4),
        "guiones_unidos":       max(0, guiones_unidos),
    }


_RE_COORDS_BNC = re.compile(
    r'^\s*-?\d{3,8}(?:\s+-?\d{3,8}){1,5}\s*$',
    re.MULTILINE,
)

def limpiar_coordenadas_bnc(texto: str) -> str:
    """Elimina líneas de coordenadas XY que Adobe Paper Capture embebe junto al texto.

    En los PDF de la BNC cada bloque OCR va precedido por números de posición del
    tipo '207509 -149211 6249691 -277354' que PyMuPDF extrae como texto plano.
    Son 2-6 enteros (positivos o negativos, 3-8 dígitos) solos en su línea."""
    return _RE_COORDS_BNC.sub('', texto)


def reconstruir_lineas_rotas(texto: str) -> str:
    """
    Reconstruye líneas fragmentadas por la mezcla de columnas del OCR de la BNC.

    El OCR de la BNC intercala líneas de columnas distintas en el mismo stream,
    lo que produce secuencias de líneas muy cortas (1-4 palabras) que pertenecen
    a la misma oración. Esta función une esas líneas respetando los límites reales
    de párrafo (línea vacía, línea que empieza con mayúscula después de punto,
    títulos en mayúsculas, indicadores de sección).

    Heurística:
    - Si una línea termina sin puntuación fuerte (.,;:!?) y la siguiente empieza
      en minúscula → misma oración, unir con espacio.
    - Si la línea tiene ≤4 palabras y la siguiente también → probable fragmento
      de columna, unir si no hay señal de párrafo nuevo.
    - Respetar líneas completamente vacías (separación de párrafos).
    - Respetar líneas ALL-CAPS (probables títulos).
    - Respetar líneas que empiezan con mayúscula tras punto (párrafo nuevo).
    """
    if not texto or not texto.strip():
        return texto

    RE_FIN_ORACION   = re.compile(r'[.!?;]\s*$')
    RE_INICIO_PARRAF = re.compile(r'^[A-ZÁÉÍÓÚÜÑ]{2,}')  # título o párrafo
    RE_SOLO_MAYUS    = re.compile(r'^[A-ZÁÉÍÓÚÜÑ\s\d\-\.,:]{4,}$')

    lineas   = texto.split('\n')
    resultado = []
    buffer   = ""

    def _vaciar():
        nonlocal buffer
        if buffer.strip():
            resultado.append(buffer.rstrip())
        buffer = ""

    for i, linea in enumerate(lineas):
        stripped = linea.strip()

        # Línea vacía: cierra párrafo
        if not stripped:
            _vaciar()
            resultado.append("")
            continue

        palabras = [w for w in stripped.split() if w]
        n_palabras = len(palabras)

        # Título ALL-CAPS largo (≥3 palabras): párrafo propio
        if RE_SOLO_MAYUS.match(stripped) and n_palabras >= 3:
            _vaciar()
            resultado.append(stripped)
            continue

        if not buffer:
            buffer = stripped
            continue

        buf_palabras = len([w for w in buffer.split() if w])
        termina_fuerte = bool(RE_FIN_ORACION.search(buffer))
        empieza_mayus  = bool(stripped[0].isupper()) if stripped else False
        es_continuacion = (
            stripped[0].islower()                     # empieza en minúscula → mismo párrafo
            or (not termina_fuerte and buf_palabras <= 6)  # línea corta sin punto
            or (not termina_fuerte and n_palabras <= 4)    # siguiente también corta
        )
        # No unir si la línea anterior terminó fuerte Y la siguiente empieza mayúscula
        es_nuevo_parrafo = termina_fuerte and empieza_mayus and buf_palabras > 4

        if es_nuevo_parrafo:
            _vaciar()
            buffer = stripped
        elif es_continuacion:
            # Unir: si la anterior terminó en guión de palabra partida, sin espacio
            if buffer.endswith('-'):
                buffer = buffer[:-1] + stripped
            else:
                buffer = buffer + " " + stripped
        else:
            _vaciar()
            buffer = stripped

    _vaciar()

    # Colapsar espacios múltiples dentro de líneas
    resultado_final = []
    for ln in resultado:
        resultado_final.append(re.sub(r' {2,}', ' ', ln))

    return '\n'.join(resultado_final)


# ══════════════════════════════════════════════════════════════════════════════
# DICCIONARIO DE CORPUS
# ══════════════════════════════════════════════════════════════════════════════

def construir_diccionario_corpus(
    txt_dir: "Path",
    freq_min: int = 5,
    cache_path: "Path | None" = None,
    callback=None,
) -> dict[str, int]:
    """
    Construye un diccionario de frecuencias a partir de todos los .txt del corpus.
    Palabras con frecuencia >= freq_min se consideran válidas para el corpus.

    Args:
        txt_dir:    Directorio con archivos .txt del OCR.
        freq_min:   Frecuencia mínima para considerar una palabra como válida.
        cache_path: Si se indica, guarda/carga el diccionario en formato JSON.
        callback:   callback(n_actual, n_total, nombre) para reporte de progreso.

    Returns:
        dict {palabra_normalizada: frecuencia}
    """
    import json
    from collections import Counter
    from pathlib import Path

    txt_dir = Path(txt_dir)

    if cache_path and Path(cache_path).exists():
        return json.loads(Path(cache_path).read_text(encoding="utf-8"))

    RE_PALABRA = re.compile(r"\b[a-záéíóúüñA-ZÁÉÍÓÚÜÑ]{3,}\b")
    contador: Counter = Counter()

    archivos = sorted(txt_dir.rglob("*.txt"))
    for i, p in enumerate(archivos, 1):
        if callback:
            callback(i, len(archivos), p.name)
        try:
            texto = p.read_text(encoding="utf-8", errors="replace")
            palabras = RE_PALABRA.findall(texto.lower())
            contador.update(palabras)
        except Exception:
            continue

    diccionario = {p: f for p, f in contador.items() if f >= freq_min}

    if cache_path:
        Path(cache_path).write_text(
            json.dumps(diccionario, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return diccionario


def detectar_palabras_sospechosas(
    texto: str,
    diccionario: dict[str, int],
    umbral_freq: int = 5,
) -> list[dict]:
    """
    Detecta palabras en el texto que NO están en el diccionario de corpus.
    Estas son candidatas a errores OCR no corregidos.

    Args:
        texto:       Texto OCR ya normalizado.
        diccionario: Dict {palabra: frecuencia} construido con construir_diccionario_corpus().
        umbral_freq: Frecuencia mínima para considerar una palabra como conocida.

    Returns:
        Lista de dicts: [{palabra, posicion_char, contexto}]
    """
    RE_PALABRA = re.compile(r"\b[a-záéíóúüñA-ZÁÉÍÓÚÜÑ]{4,}\b")
    sospechosas = []
    for m in RE_PALABRA.finditer(texto):
        pal = m.group(0).lower()
        freq = diccionario.get(pal, 0)
        if freq < umbral_freq:
            inicio = max(0, m.start() - 30)
            fin    = min(len(texto), m.end() + 30)
            sospechosas.append({
                "palabra":      m.group(0),
                "frecuencia":   freq,
                "posicion":     m.start(),
                "contexto":     texto[inicio:fin].replace("\n", " "),
            })
    return sospechosas


def normalizar_directorio(txt_dir: "Path",
                           callback=None,
                           guardar_original: bool = True,
                           **kwargs) -> dict:
    """
    Normaliza todos los .txt de un directorio.
    callback(n_actual, n_total, nombre_archivo)
    """
    from pathlib import Path
    txt_dir = Path(txt_dir)
    archivos = sorted(txt_dir.glob("*.txt"))

    totales = {"archivos": 0, "palabras_cambiadas": 0, "errores": 0,
               "guiones_unidos": 0}
    for i, p in enumerate(archivos, 1):
        if callback:
            callback(i, len(archivos), p.name)
        try:
            stats = normalizar_archivo(p, guardar_original=guardar_original, **kwargs)
            totales["archivos"] += 1
            totales["palabras_cambiadas"] += abs(
                stats["palabras_normalizado"] - stats["palabras_original"])
            totales["guiones_unidos"] += stats.get("guiones_unidos", 0)
        except Exception:
            totales["errores"] += 1
    return totales
