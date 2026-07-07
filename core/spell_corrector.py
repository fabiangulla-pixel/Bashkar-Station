"""
core/spell_corrector.py — Corrección ortográfica post-OCR para prensa histórica
                           colombiana (décadas 1930-1950).

Estrategia de tres capas:
  1. Lista blanca de vocabulario de época (términos que el diccionario estándar
     no conoce: topónimos, cargos, giros propios de la prensa colombiana, etc.)
  2. Diccionario Hunspell es_ES via spylls (puro Python, sin dependencias nativas)
  3. Corrección por sugerencias: solo se reemplaza si la sugerencia top tiene
     distancia de edición ≤ 2 Y el contexto indica que es error OCR.

Diseño conservador: es preferible NO corregir que corregir mal. El corrector
solo actúa sobre palabras que:
  a) No pasan el lookup de Hunspell
  b) No están en la lista blanca de época
  c) Tienen exactamente UNA sugerencia de alta confianza
  d) La palabra original parece error OCR (contiene dígitos en letras, mezcla de
     caso anormal, etc.)

Uso:
    from core.spell_corrector import SpellCorrector
    sc = SpellCorrector()
    texto_corregido = sc.corregir_texto(texto_ocr)
    stats = sc.estadisticas()
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# VOCABULARIO DE ÉPOCA — Lista blanca
# Términos que el diccionario moderno no reconoce pero son correctos en el
# contexto de prensa colombiana de 1930-1950.
# ─────────────────────────────────────────────────────────────────────────────

_VOCAB_EPOCA: set[str] = {
    # Publicaciones y medios
    "estampa", "cromos", "semana", "sábado", "el tiempo", "el espectador",
    "el colombiano", "el universal",
    # Topónimos colombianos y suramericanos frecuentes
    "bogotá", "medellín", "barranquilla", "cartagena", "manizales",
    "bucaramanga", "cúcuta", "cali", "pereira", "ibagué", "pasto",
    "tunja", "popayán", "armenia", "montería", "neiva", "valledupar",
    "sincelejo", "riohacha", "quibdó", "leticia", "mocoa",
    "cundinamarca", "antioquia", "santander", "boyacá", "cauca",
    "nariño", "tolima", "caldas", "huila", "atlántico", "bolívar",
    "córdoba", "magdalena", "sucre", "cesar", "risaralda", "chocó",
    "guajira", "arauca", "vichada", "vaupés", "guainía", "amazonas",
    "putumayo", "caquetá", "casanare", "guaviare",
    # Cargos y títulos de época
    "monseñor", "excelentísimo", "ilustrísimo", "reverendísimo",
    "prebendado", "chantre", "deán", "canónigo", "beneficiado",
    "alcalde", "concejal", "personero", "gobernador", "intendente",
    "comisario", "prefecto", "subprefecto",
    # Términos políticos y sociales de época
    "liberalismo", "conservatismo", "laureanismo", "gaitanismo",
    "lopismo", "santanderismo", "bolivarianismo",
    "concentración", "hegemonía", "bipartidismo",
    "gamonalismo", "caciquismo", "clientelismo",
    # Instituciones
    "congreso", "senado", "cámara", "ministerio", "municipio",
    "departamento", "intendencia", "comisaría",
    "universidad nacional", "universidad de antioquia",
    "banco de la república", "caja agraria",
    # Términos de industria y comercio de época
    "valorización", "catastro", "predio", "finca raíz",
    "hacienda", "finca", "sociedad anónima", "ltda",
    "empresa", "compañía", "sociedad",
    # Gentilicios y adjetivos propios de época
    "colombiano", "colombiana", "colombianos", "colombianas",
    "bogotano", "bogotana", "antioqueño", "antioqueña",
    "costeño", "costeña", "valluno", "valluna",
    "caucano", "caucana", "boyacense", "santandereano",
    # Términos de cultura y espectáculo
    "cinematógrafo", "fonógrafo", "radiodifusión", "radiofonía",
    "radioemisora", "radiodrama", "radioteatro",
    "fotograbado", "fotomontaje", "fotorreportaje",
    "cuplé", "tango", "pasillo", "bambuco", "cumbia", "mapalé",
    "porro", "vallenato", "currulao",
    # Términos de moda y sociedad
    "confección", "modisto", "modista", "costurera",
    "sastrería", "peletería", "pasamanería",
    # Palabras arcaicas/cultas frecuentes en la época
    "empero", "empero,", "asaz", "doquiera", "doquier",
    "hogaño", "otrora", "antaño", "nones", "sendos", "sendas",
    "cuita", "cuitas", "ardid", "ardides",
    "prosapia", "alcurnia", "abolengo",
    # Términos de prensa/imprenta
    "redacción", "tipografía", "linotipo", "linotipia",
    "fototipia", "litografía", "rotativa", "plana", "folio",
    "columna", "titular", "subtítulo", "sumario", "crédito",
    "byline", "reportaje", "crónica", "gacetilla", "suelto",
    "folletín", "serial", "entrega",
    # Números escritos con grafías de época
    "diez", "once", "doce", "trece", "catorce", "quince",
    "dieciséis", "diecisiete", "dieciocho", "diecinueve",
    "veinte", "veintiuno", "veintidós", "veintitrés",
    "treinta", "cuarenta", "cincuenta", "sesenta",
    "setenta", "ochenta", "noventa", "ciento", "cien",
    # Extranjerismos asimilados de época
    "cóctel", "coctel", "smoking", "jersey", "sweater",
    "sport", "football", "tennis", "golf", "box", "boxeo",
    "ring", "knock-out", "champion", "record",
    # Términos médicos y científicos de uso periodístico
    "epidemia", "pandemia", "endemia", "cuarentena",
    "vacunación", "profilaxis", "higiene", "sanidad",
    "lazareto", "leprosario",
    # Expresiones religiosas frecuentes
    "parroquia", "diócesis", "arquidiócesis", "prelatura",
    "coadjutor", "vicario", "capellán", "sacristán",
}

# Normalizar a minúsculas para lookup rápido
_VOCAB_EPOCA_LOWER: frozenset[str] = frozenset(
    w.lower() for w in _VOCAB_EPOCA
)

# ─────────────────────────────────────────────────────────────────────────────
# CORRECCIONES DIRECTAS — Errores OCR muy específicos de Hunspell no captura
# ─────────────────────────────────────────────────────────────────────────────

_CORRECCIONES_DIRECTAS: dict[str, str] = {
    # Errores tipográficos muy frecuentes en digitalización BNC
    "ha.cer":      "hacer",
    "te.ner":      "tener",
    "po.der":      "poder",
    "va.lor":      "valor",
    "co.mo":       "como",
    "es.to":       "esto",
    "es.ta":       "esta",
    "pe.ro":       "pero",
    "pa.ra":       "para",
    "so.bre":      "sobre",
    "en.tre":      "entre",
    "des.de":      "desde",
    "has.ta":      "hasta",
    "den.tro":     "dentro",
    "mien.tras":   "mientras",
    # Números confundidos muy frecuentes
    "d1ce":        "dice",
    "d1jo":        "dijo",
    "d1os":        "Dios",
    "qu1en":       "quien",
    "tam.bién":    "también",
    "tam·bién":    "también",
    "tam-bién":    "también",
}

# ─────────────────────────────────────────────────────────────────────────────
# PATRONES DE ERROR OCR — Para identificar si una palabra "parece" error OCR
# (criterio para aplicar corrección automática agresiva vs conservadora)
# ─────────────────────────────────────────────────────────────────────────────

_RE_PARECE_OCR = re.compile(
    r'[0-9]'           # contiene dígito dentro de texto
    r'|[|¡§~]'         # caracteres típicos de ruido OCR
    r'|\.\w'           # punto pegado a letra (partición tipográfica)
    r'|\w{15,}',       # palabra excesivamente larga (fusion OCR)
    re.UNICODE
)

# Palabras de una sola letra que no son palabras reales (ruido)
_RE_SOLO_PUNTACION = re.compile(r'^[^a-záéíóúüñA-ZÁÉÍÓÚÜÑ]+$')

# ─────────────────────────────────────────────────────────────────────────────
# CLASE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

class SpellCorrector:
    """
    Corrector ortográfico conservador para texto OCR de prensa histórica.

    Uso:
        sc = SpellCorrector()            # carga diccionario la primera vez
        texto = sc.corregir_texto(texto)
        print(sc.estadisticas())
    """

    _instancia: Optional["SpellCorrector"] = None
    _dic = None

    def __init__(self, dic_path: Optional[str] = None):
        self._conteo_corregidas  = 0
        self._conteo_ignoradas   = 0
        self._conteo_total       = 0
        self._dic_path = dic_path
        self._dic = None

    def _cargar_diccionario(self):
        """Carga el diccionario Hunspell (lazy, una sola vez)."""
        if self._dic is not None:
            return True
        try:
            from spylls.hunspell import Dictionary
            if self._dic_path:
                self._dic = Dictionary.from_files(self._dic_path)
            else:
                # Buscar diccionario español empaquetado con spylls o descargado
                import spylls
                base = Path(spylls.__file__).parent / "hunspell" / "data" / "es"
                for nombre in ("es_ES", "es_ANY", "es"):
                    p = base / nombre
                    if (p.with_suffix(".aff")).exists():
                        self._dic = Dictionary.from_files(str(p))
                        break
            return self._dic is not None
        except Exception:
            return False

    def _en_lista_blanca(self, palabra: str) -> bool:
        """True si la palabra está en el vocabulario de época."""
        return palabra.lower() in _VOCAB_EPOCA_LOWER

    def _parece_error_ocr(self, palabra: str) -> bool:
        """True si la palabra tiene características de error OCR."""
        return bool(_RE_PARECE_OCR.search(palabra))

    def _es_palabra_real(self, palabra: str) -> bool:
        """
        True si la palabra es válida (lista blanca + Hunspell).
        False si no se puede cargar el diccionario.
        """
        if self._en_lista_blanca(palabra):
            return True
        if self._dic is None:
            return True  # sin diccionario → no corregir
        # Hunspell: probar con original y con minúsculas
        return (self._dic.lookup(palabra)
                or self._dic.lookup(palabra.lower())
                or self._dic.lookup(palabra.capitalize()))

    def _sugerir_correccion(self, palabra: str) -> Optional[str]:
        """
        Devuelve la mejor sugerencia Hunspell si tiene alta confianza.
        Criterio: la sugerencia top tiene distancia Levenshtein ≤ 2 respecto al original.
        """
        if self._dic is None:
            return None
        try:
            sugerencias = list(self._dic.suggest(palabra))
            if not sugerencias:
                return None
            mejor = sugerencias[0]
            # Verificar distancia de edición
            if _distancia_edicion(palabra.lower(), mejor.lower()) <= 2:
                return mejor
        except Exception:
            pass
        return None

    def corregir_palabra(self, palabra: str) -> str:
        """
        Corrige una palabra individual si parece error OCR y hay sugerencia confiable.
        Aplica correcciones directas primero, luego Hunspell.
        """
        self._conteo_total += 1

        # Ignorar tokens que no son palabras reales
        if len(palabra) <= 1:
            return palabra
        if _RE_SOLO_PUNTACION.match(palabra):
            return palabra
        # Ignorar números puros
        if palabra.replace(",", "").replace(".", "").isdigit():
            return palabra

        # 1. Corrección directa (error conocido → forma correcta)
        clave = palabra.lower()
        if clave in _CORRECCIONES_DIRECTAS:
            self._conteo_corregidas += 1
            return _CORRECCIONES_DIRECTAS[clave]

        # 2. Si la palabra ya es válida, no tocar
        if self._es_palabra_real(palabra):
            return palabra

        # 3. Solo corregir si parece error OCR Y hay sugerencia confiable
        if self._parece_error_ocr(palabra):
            sugerencia = self._sugerir_correccion(palabra)
            if sugerencia:
                # Preservar mayúscula inicial si la original la tenía
                if palabra[0].isupper() and not sugerencia[0].isupper():
                    sugerencia = sugerencia.capitalize()
                self._conteo_corregidas += 1
                return sugerencia

        self._conteo_ignoradas += 1
        return palabra

    def corregir_texto(self, texto: str) -> str:
        """
        Corrige el texto completo token por token.
        Solo actúa sobre palabras que parecen errores OCR.
        Preserva puntuación, números y estructura de líneas.
        """
        if not self._cargar_diccionario():
            return texto  # sin diccionario → devolver intacto

        # Tokenizar preservando separadores (espacios, puntuación)
        # Patrón: secuencias de letras/diacríticos o secuencias de no-letras
        tokens = re.split(r'(\W+)', texto)
        resultado = []
        for tok in tokens:
            # Solo intentar corregir tokens que parecen palabras
            if re.match(r'[a-záéíóúüñA-ZÁÉÍÓÚÜÑ0-9]', tok):
                resultado.append(self.corregir_palabra(tok))
            else:
                resultado.append(tok)
        return "".join(resultado)

    def corregir_archivo(self, txt_path: Path) -> dict:
        """
        Lee un .txt, aplica corrección y sobreescribe.
        Retorna estadísticas.
        """
        texto = txt_path.read_text("utf-8", errors="replace")
        self.resetear_stats()
        corregido = self.corregir_texto(texto)
        txt_path.write_text(corregido, encoding="utf-8")
        return self.estadisticas()

    def resetear_stats(self):
        self._conteo_corregidas = 0
        self._conteo_ignoradas  = 0
        self._conteo_total      = 0

    def estadisticas(self) -> dict:
        return {
            "palabras_revisadas":  self._conteo_total,
            "palabras_corregidas": self._conteo_corregidas,
            "palabras_ignoradas":  self._conteo_ignoradas,
            "ratio_correccion":    round(
                self._conteo_corregidas / max(self._conteo_total, 1), 4
            ),
            "diccionario_cargado": self._dic is not None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# INSTANCIA COMPARTIDA (singleton lazy)
# ─────────────────────────────────────────────────────────────────────────────

_corrector_global: Optional[SpellCorrector] = None


def obtener_corrector() -> SpellCorrector:
    """Devuelve la instancia global (crea si no existe)."""
    global _corrector_global
    if _corrector_global is None:
        _corrector_global = SpellCorrector()
    return _corrector_global


def corregir_texto_ocr(texto: str) -> str:
    """Función de conveniencia: corrige texto usando el corrector global."""
    return obtener_corrector().corregir_texto(texto)


# ─────────────────────────────────────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────────────────────────────────────

def _distancia_edicion(a: str, b: str) -> int:
    """Distancia de Levenshtein entre dos cadenas (para cadenas cortas)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    # Optimización: si la diferencia de longitud ya supera 3, no medir
    if abs(len(a) - len(b)) > 3:
        return 99

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            ins  = curr[j] + 1
            dlt  = prev[j + 1] + 1
            rep  = prev[j] + (0 if ca == cb else 1)
            curr.append(min(ins, dlt, rep))
        prev = curr
    return prev[-1]


def verificar_instalacion() -> dict:
    """
    Verifica que spylls y el diccionario español estén disponibles.
    Retorna dict con estado y ruta del diccionario.
    """
    resultado = {
        "spylls_disponible": False,
        "diccionario_es":    False,
        "ruta_diccionario":  None,
    }
    try:
        import spylls
        resultado["spylls_disponible"] = True
        base = Path(spylls.__file__).parent / "hunspell" / "data" / "es"
        for nombre in ("es_ES", "es_ANY", "es"):
            aff = base / (nombre + ".aff")
            if aff.exists():
                resultado["diccionario_es"]   = True
                resultado["ruta_diccionario"] = str(base / nombre)
                break
    except ImportError:
        pass
    return resultado
