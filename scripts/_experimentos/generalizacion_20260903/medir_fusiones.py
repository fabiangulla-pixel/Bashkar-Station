"""Mide fusiones de palabras por publicación, con el umbral actual y sin el piso.

Hipótesis a falsar (derivada de leer `core/alto_reconstructor.py`, no inventada):

El umbral que separa palabras es `max(0.15, 0.018 * tamaño_fuente)`. El propio
módulo documenta que el rango admisible del factor relativo es 0.007 < rel <
0.023, medido sobre pares reales de Panida. Pero el **piso absoluto de 0,15 pt**
deja de ser inocuo en fuentes pequeñas:

    size < 8.33 pt  ->  el piso manda y el umbral deja de adaptarse
    size < 6.52 pt  ->  el rel efectivo supera 0.023 y sale del rango seguro

En la muestra medida, solo *El Nuevo Tiempo* (1902, 5,27 pt) cae ahí: su rel
efectivo es 0.0285. Predicción: fusiona palabras, y bajar el piso lo corrige.
Todas las demás están entre 8,8 y 11,9 pt y no deberían cambiar nada.

Si la predicción falla —si El Nuevo Tiempo no mejora, o si las otras cambian—
la hipótesis está mal y hay que decirlo, no maquillarlo.

Cómo se cuenta, con el mismo criterio que usó la calibración original:
  · fusión  = token de más de 16 caracteres (irrecuperable para NER/frecuencias)
  · fragmento = token de 1-2 caracteres fuera de una lista de palabras cortas
    legítimas del español (errar hacia el fragmento es preferible a fusionar)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, r"I:\Mi unidad\00_Programas y macros\Bashkar Station\bashkar_station")

import fitz  # noqa: E402

from core import alto_reconstructor as ar  # noqa: E402

MUESTRA = Path(r"C:\build_rf\generalizacion\muestra")
PAGINAS = 12

# Palabras españolas legítimas de 1-2 letras: no cuentan como fragmento espurio.
CORTAS_OK = {
    "a", "y", "o", "e", "u", "de", "la", "el", "en", "un", "es", "se", "no",
    "lo", "al", "su", "si", "ya", "me", "te", "le", "mi", "tu", "ni", "os",
    "da", "va", "ha", "he", "fe", "ver", "df",
}
_RE_TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)


def contar(texto: str) -> tuple[int, int, int]:
    tokens = _RE_TOKEN.findall(texto)
    fusiones = sum(1 for t in tokens if len(t) > 16)
    frag = sum(1 for t in tokens if len(t) <= 2 and t.lower() not in CORTAS_OK)
    return len(tokens), fusiones, frag


def texto_de(pdf: Path, piso: float, n_paginas: int = PAGINAS) -> str:
    """Reconstruye por la RUTA DE PRODUCCION, con el piso que se le indique.

    Importante: se usa `reconstruir_texto_pagina` con sus valores por defecto
    (ignorar_ocr_basura=True). Medir sobre los spans crudos da conclusiones
    falsas, porque el filtrado cambia la geometria de la linea.
    """
    original = ar._UMBRAL_ESPACIO_MIN
    ar._UMBRAL_ESPACIO_MIN = piso
    try:
        doc = fitz.open(pdf)
        paso = max(1, len(doc) // n_paginas)
        indices = list(range(0, len(doc), paso))[:n_paginas]
        partes = []
        for i in indices:
            datos = ar.reconstruir_texto_pagina(doc[i])
            partes.append(datos.get("texto", "") if isinstance(datos, dict)
                          else str(datos))
        doc.close()
        return "\n".join(partes)
    finally:
        ar._UMBRAL_ESPACIO_MIN = original


def main() -> None:
    pdfs = [p for p in sorted(MUESTRA.glob("*.pdf"))
            if "El_Nuevo_Tiempo.pdf" not in p.name]  # copia corrupta

    print(f"{'PUBLICACION':26s} {'TOKENS':>7} {'FUS':>5} {'FRAG':>6} | "
          f"{'FUS':>5} {'FRAG':>6}   VEREDICTO", flush=True)
    print(f"{'':26s} {'':>7} {'piso 0.15':>12} | {'piso 0.02':>12}", flush=True)
    print("-" * 92, flush=True)

    for pdf in pdfs:
        nombre = pdf.stem[:26]
        try:
            t_actual = texto_de(pdf, 0.15)
            t_bajo = texto_de(pdf, 0.02)
        except Exception as e:
            print(f"{nombre:26s}  ERROR: {type(e).__name__}: {str(e)[:40]}", flush=True)
            continue

        n, fus_a, frag_a = contar(t_actual)
        _, fus_b, frag_b = contar(t_bajo)

        if fus_a == fus_b and frag_a == frag_b:
            veredicto = "sin cambio (el piso no actuaba)"
        elif fus_b < fus_a:
            veredicto = f"MEJORA: -{fus_a - fus_b} fusiones (+{frag_b - frag_a} frag)"
        else:
            veredicto = f"EMPEORA: +{fus_b - fus_a} fusiones"

        print(f"{nombre:26s} {n:>7} {fus_a:>5} {frag_a:>6} | "
              f"{fus_b:>5} {frag_b:>6}   {veredicto}", flush=True)


if __name__ == "__main__":
    main()
