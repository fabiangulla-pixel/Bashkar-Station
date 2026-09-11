"""core/calidad_ocr.py — Calidad del texto reconocido y ruta de OCR por página.

Dos preguntas que el pipeline no se hacía y que la prueba de generalización del
3 de septiembre de 2026 dejó sobre la mesa
(`scripts/_experimentos/generalizacion_20260903/RESULTADOS.md`):

1. **¿Este texto sirve?** La fragmentación —tokens partidos en trozos de una o
   dos letras— varía de 2,6 % a 35,6 % entre publicaciones de la misma
   biblioteca, y nada en Bashkar la medía ni la reportaba. Un documento al 36 %
   entra al NER y a las frecuencias como si fuera texto limpio.

2. **¿Por dónde hay que leer cada página?** *El Día* declara la capa oculta de
   Adobe Paper Capture igual que *Estampa* —el conjunto de fuentes es
   idéntico— y solo 2 de sus 16 páginas tienen texto. Cualquier comprobación a
   nivel de documento responde "sí, tiene texto" y encamina el ejemplar entero
   por la ruta rápida, extrayendo el 12,5 % del contenido y reportando éxito.

Módulo puro: sin tkinter, sin estado global. `fitz` se importa dentro de las
funciones que lo necesitan para no cargar PyMuPDF al importar el módulo.

Los umbrales son EMPÍRICOS, medidos sobre nueve publicaciones de la Biblioteca
Nacional de Colombia; están documentados en `UMBRAL_*` con la evidencia que los
sostiene, y se pueden pasar por parámetro. No son universales: valen para prensa
histórica en español por la ruta de producción de Bashkar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# ── Umbrales, con la evidencia que los justifica ─────────────────────────────
#
# Fragmentación medida sobre 12 páginas de un ejemplar de cada publicación:
#
#   Rin-Rin              2,6 %  ┐
#   Agitación Femenina   4,0 %  │ aceptable
#   Panida (1915)        6,2 %  │
#   Estampa 1939         6,8 %  ├─ línea base: el corpus validado del proyecto
#   La Mujer             7,4 %  ┘
#   ----------------------------- UMBRAL_FRAGMENTACION_REVISAR = 10 %
#   La Semana Cómica    20,8 %  ┐ crítico: NER y frecuencias inservibles
#   El Nuevo Tiempo     35,6 %  ┘
#
# El corte en 10 % deja fuera a las cinco aceptables con margen (la peor, 7,4 %,
# queda a 2,6 puntos) y no roza a las dos críticas (la mejor, 20,8 %, queda al
# doble). No hay ninguna publicación entre 7,4 % y 20,8 %, así que el umbral no
# está calibrado contra un caso frontera: cae en un hueco vacío de la evidencia.
UMBRAL_FRAGMENTACION_REVISAR = 10.0

# Por encima de este valor el documento no es material de análisis en absoluto:
# uno de cada cinco tokens es basura. Queda entre las dos críticas medidas.
UMBRAL_FRAGMENTACION_CRITICO = 20.0

# Fusión: token de más de 16 caracteres, irrecuperable para NER y frecuencias.
# Tras el arreglo del umbral relativo de la sesión 65 el máximo medido es la
# propia Estampa con 0,26 %; cualquier cosa por encima del 1 % es una regresión
# de `alto_reconstructor`, no una propiedad del corpus.
UMBRAL_FUSION_REVISAR = 1.0

LARGO_TOKEN_FUSION = 16
LARGO_TOKEN_FRAGMENTO = 2

# Palabras españolas legítimas de 1-2 letras: no cuentan como fragmento espurio.
# Misma lista que usó la medición original (`medir_fusiones.py`), para que las
# cifras de producción sean comparables con las del experimento.
CORTAS_OK = frozenset({
    "a", "y", "o", "e", "u", "de", "la", "el", "en", "un", "es", "se", "no",
    "lo", "al", "su", "si", "ya", "me", "te", "le", "mi", "tu", "ni", "os",
    "da", "va", "ha", "he", "fe", "ver", "df",
})

_RE_TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)

# Veredictos
UTILIZABLE = "utilizable"
REVISAR = "revisar"
NO_UTILIZABLE = "no_utilizable"

# Mínimo de palabras para considerar que una página TIENE texto de verdad.
# Una página de prensa OCR-izada trae cientos; las que solo llevan la marca de
# agua de digitalización de la BNC traen ~6 ("Digitalizado Biblioteca Nacional
# de Colombia"). El corte en 20 separa las dos poblaciones sin ambigüedad: en el
# censo de *El Día* las páginas sin OCR dan 0 y las dos que sí lo tienen dan
# más de 1.800.
PALABRAS_MIN_PAGINA_CON_TEXTO = 20


@dataclass
class MetricasTexto:
    """Cuentas crudas y porcentajes de una muestra de texto."""

    tokens: int = 0
    fusiones: int = 0
    fragmentos: int = 0

    @property
    def pct_fusion(self) -> float:
        return 100.0 * self.fusiones / self.tokens if self.tokens else 0.0

    @property
    def pct_fragmentacion(self) -> float:
        return 100.0 * self.fragmentos / self.tokens if self.tokens else 0.0

    def __add__(self, otra: "MetricasTexto") -> "MetricasTexto":
        return MetricasTexto(
            tokens=self.tokens + otra.tokens,
            fusiones=self.fusiones + otra.fusiones,
            fragmentos=self.fragmentos + otra.fragmentos,
        )


@dataclass
class Veredicto:
    """Resultado de evaluar un texto: métricas + decisión + por qué."""

    veredicto: str
    metricas: MetricasTexto
    motivos: list[str] = field(default_factory=list)

    @property
    def se_abstiene(self) -> bool:
        """True si el documento NO debe analizarse sin revisión humana."""
        return self.veredicto != UTILIZABLE

    @property
    def mensaje(self) -> str:
        m = self.metricas
        if not m.tokens:
            return "Sin texto que evaluar"
        cabeza = {
            UTILIZABLE: "Texto utilizable",
            REVISAR: "⚠ Texto degradado, revisar antes de analizar",
            NO_UTILIZABLE: "✖ Texto no utilizable sin nueva transcripción",
        }[self.veredicto]
        cifras = (f"fragmentación {m.pct_fragmentacion:.1f} % · "
                  f"fusión {m.pct_fusion:.2f} % · {m.tokens:,} tokens")
        if self.motivos:
            return f"{cabeza} ({cifras}): {'; '.join(self.motivos)}"
        return f"{cabeza} ({cifras})"


def metricas_texto(texto: str) -> MetricasTexto:
    """Cuenta tokens, fusiones y fragmentos de una muestra de texto.

    · fusión    = token de más de 16 caracteres (irrecuperable aguas abajo)
    · fragmento = token de 1-2 letras que no es palabra corta legítima

    Solo mira tokens alfabéticos: números de página, coordenadas y puntuación
    no entran en el denominador.
    """
    tokens = _RE_TOKEN.findall(texto or "")
    return MetricasTexto(
        tokens=len(tokens),
        fusiones=sum(1 for t in tokens if len(t) > LARGO_TOKEN_FUSION),
        fragmentos=sum(
            1 for t in tokens
            if len(t) <= LARGO_TOKEN_FRAGMENTO and t.lower() not in CORTAS_OK
        ),
    )


def evaluar_metricas(
    m: MetricasTexto,
    umbral_revisar: float = UMBRAL_FRAGMENTACION_REVISAR,
    umbral_critico: float = UMBRAL_FRAGMENTACION_CRITICO,
    umbral_fusion: float = UMBRAL_FUSION_REVISAR,
    min_tokens: int = 200,
) -> Veredicto:
    """Traduce métricas a una decisión de abstención.

    `min_tokens` evita opinar sobre muestras minúsculas: con 30 tokens, un solo
    fragmento son 3 puntos porcentuales. Por debajo del mínimo el veredicto es
    REVISAR con el motivo explícito, nunca UTILIZABLE por defecto — callarse
    ante una muestra insuficiente es el fallo silencioso que este módulo existe
    para evitar.
    """
    motivos: list[str] = []

    if m.tokens < min_tokens:
        motivos.append(
            f"muestra insuficiente para juzgar ({m.tokens} tokens, "
            f"mínimo {min_tokens})"
        )
        return Veredicto(REVISAR, m, motivos)

    veredicto = UTILIZABLE
    if m.pct_fragmentacion >= umbral_critico:
        veredicto = NO_UTILIZABLE
        motivos.append(
            f"fragmentación {m.pct_fragmentacion:.1f} % ≥ {umbral_critico:.0f} %"
        )
    elif m.pct_fragmentacion >= umbral_revisar:
        veredicto = REVISAR
        motivos.append(
            f"fragmentación {m.pct_fragmentacion:.1f} % ≥ {umbral_revisar:.0f} %"
        )

    if m.pct_fusion >= umbral_fusion:
        motivos.append(
            f"fusión {m.pct_fusion:.2f} % ≥ {umbral_fusion:.1f} % "
            "(posible regresión del umbral de separación de palabras)"
        )
        if veredicto == UTILIZABLE:
            veredicto = REVISAR

    return Veredicto(veredicto, m, motivos)


def evaluar_texto(texto: str, **kwargs) -> Veredicto:
    """Atajo: mide y juzga una muestra de texto de una sola vez."""
    return evaluar_metricas(metricas_texto(texto), **kwargs)


def evaluar_paginas(textos, **kwargs) -> Veredicto:
    """Evalúa un documento a partir del texto de sus páginas.

    Suma las cuentas crudas antes de calcular porcentajes: promediar los
    porcentajes por página daría el mismo peso a una página de 20 tokens que a
    una de 2.000.
    """
    total = MetricasTexto()
    for t in textos:
        total = total + metricas_texto(t)
    return evaluar_metricas(total, **kwargs)


# ── Ruta de OCR por página ───────────────────────────────────────────────────

@dataclass
class CensoPaginas:
    """Qué páginas de un PDF traen texto real y cuáles hay que OCR-izar."""

    palabras_por_pagina: list[int] = field(default_factory=list)

    @property
    def n_paginas(self) -> int:
        return len(self.palabras_por_pagina)

    @property
    def paginas_con_texto(self) -> list[int]:
        """Índices 0-based de las páginas que traen texto real."""
        return [i for i, n in enumerate(self.palabras_por_pagina)
                if n >= PALABRAS_MIN_PAGINA_CON_TEXTO]

    @property
    def paginas_sin_texto(self) -> list[int]:
        return [i for i, n in enumerate(self.palabras_por_pagina)
                if n < PALABRAS_MIN_PAGINA_CON_TEXTO]

    @property
    def cobertura(self) -> float:
        """Fracción 0-1 de páginas con texto real."""
        if not self.n_paginas:
            return 0.0
        return len(self.paginas_con_texto) / self.n_paginas

    def modo_de_pagina(self, i: int) -> str:
        """"digital" si la página i trae texto real, "escaneado" si no."""
        if 0 <= i < self.n_paginas:
            if self.palabras_por_pagina[i] >= PALABRAS_MIN_PAGINA_CON_TEXTO:
                return "digital"
        return "escaneado"

    @property
    def modos(self) -> list[str]:
        return [self.modo_de_pagina(i) for i in range(self.n_paginas)]

    @property
    def resumen(self) -> str:
        n_dig = len(self.paginas_con_texto)
        if not self.n_paginas:
            return "documento sin páginas legibles"
        if n_dig == self.n_paginas:
            return f"las {self.n_paginas} páginas traen texto"
        if n_dig == 0:
            return f"ninguna de las {self.n_paginas} páginas trae texto (OCR completo)"
        return (f"{n_dig} de {self.n_paginas} páginas traen texto "
                f"({self.cobertura:.0%}); las otras {self.n_paginas - n_dig} "
                "necesitan OCR")


def censar_paginas(pdf_path, doc=None) -> CensoPaginas:
    """Cuenta las palabras de texto embebido de CADA página del PDF.

    Recorre el documento entero, no una muestra: el caso que motiva esta
    función (*El Día*) tiene el texto en las dos últimas páginas de dieciséis, y
    cualquier muestreo de las primeras lo declara escaneado. `get_text("text")`
    no rasteriza nada, así que el censo completo cuesta poco incluso en los
    ejemplares grandes.

    Acepta un `doc` de fitz ya abierto para no reabrir el archivo; en ese caso
    no lo cierra (lo cierra quien lo abrió).
    """
    propio = doc is None
    try:
        if propio:
            import fitz
            doc = fitz.open(str(pdf_path))
    except Exception:
        return CensoPaginas([])

    try:
        palabras = [len(pagina.get_text("text").split()) for pagina in doc]
    except Exception:
        palabras = []
    finally:
        if propio:
            try:
                doc.close()
            except Exception:
                pass

    return CensoPaginas(palabras)


def informe_documento(pdf_path, textos=None, **kwargs) -> dict:
    """Ficha de calidad de un documento: censo de páginas + veredicto de texto.

    Si no se pasan `textos`, se evalúa el texto embebido de las páginas que lo
    tienen. Devuelve un dict serializable para guardar junto al proyecto.
    """
    pdf_path = Path(pdf_path)
    censo = censar_paginas(pdf_path)

    if textos is None:
        textos = []
        try:
            import fitz
            doc = fitz.open(str(pdf_path))
            try:
                for i in censo.paginas_con_texto:
                    textos.append(doc[i].get_text("text"))
            finally:
                doc.close()
        except Exception:
            textos = []

    v = evaluar_paginas(textos, **kwargs)
    return {
        "archivo": pdf_path.name,
        "n_paginas": censo.n_paginas,
        "paginas_con_texto": len(censo.paginas_con_texto),
        "cobertura_texto": round(censo.cobertura, 4),
        "resumen_censo": censo.resumen,
        "tokens": v.metricas.tokens,
        "pct_fragmentacion": round(v.metricas.pct_fragmentacion, 2),
        "pct_fusion": round(v.metricas.pct_fusion, 2),
        "veredicto": v.veredicto,
        "motivos": list(v.motivos),
        "mensaje": v.mensaje,
    }
