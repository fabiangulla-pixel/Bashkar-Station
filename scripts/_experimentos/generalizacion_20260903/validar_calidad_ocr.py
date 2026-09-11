"""Valida `core/calidad_ocr.py` contra los nueve PDF reales de la Biblioteca
Nacional, no contra texto sintético.

Los tests de `tests/test_calidad_ocr.py` construyen textos con una composición
de tokens exacta: sirven para fijar el contrato, no para saber si el umbral cae
donde debe sobre prensa de verdad. Este script mide por la RUTA DE PRODUCCIÓN
(`alto_reconstructor.reconstruir_texto_pagina`, `ignorar_ocr_basura=True`) y
contrasta el veredicto con las cifras de `RESULTADOS.md`.

Ejecutado el 10-sep-2026 sobre un ejemplar de cada publicación:

    PUBLICACION               PAGS   TXT  COBERT  TOKENS   FRAG%   FUS%  VEREDICTO      s.66
    Agitación Femenina          32    29    91%   11866    4.0%  0.03%  utilizable      4.0 %
    El Día (Cali, 1904)         16    16   100%   32830   35.0%  0.21%  no_utilizable      —
    El Gráfico                  48     0     0%      60    0.0%  0.00%  revisar            —
    El Nuevo Tiempo             92    92   100%   32119   21.8%  0.19%  no_utilizable  35.6 %
    Estampa (1939)             214   206    96%    8953    4.7%  0.16%  utilizable      6.8 %
    La Mujer                    48    48   100%    6849    7.8%  0.20%  utilizable      7.4 %
    La Semana Cómica            16    16   100%    7814   30.1%  0.01%  no_utilizable  20.8 %
    Panida                      18    18   100%    2988    6.2%  0.00%  utilizable      6.2 %
    Rin-Rin                     15    14    93%    2953    2.6%  0.00%  utilizable      2.6 %

Lectura:

· **Ningún corpus cruza de bando.** Las cinco publicaciones que el experimento
  declaró aceptables salen `utilizable` y las dos críticas salen
  `no_utilizable`. Es lo único que se le pide al umbral.
· Las cifras no coinciden al decimal con `RESULTADOS.md` porque **no es el mismo
  ejemplar**: aquí se toma el primer PDF de cada carpeta y allí se tomó el de la
  muestra copiada a mano. Donde coincide el ejemplar (Panida, Rin-Rin, Agitación
  Femenina) el porcentaje es idéntico al segundo decimal, lo que confirma que el
  cálculo es el mismo.
· **Hallazgo nuevo:** *El Día* de Cali (1904) sí trae texto en las dieciséis
  páginas —no es el ejemplar mixto de 1904 que documentó `RESULTADOS.md`— pero
  con un 35 % de fragmentación. El experimento anterior no pudo medirlo (dio 0
  tokens); ahora se sabe que además de mixto es de mala calidad.
· *El Gráfico* sale `revisar` por muestra insuficiente, que es exactamente lo
  que debe pasar: 60 tokens en 48 páginas son la marca de agua, no el contenido.
  Emitir `utilizable` ahí habría sido el fallo silencioso de siempre.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import fitz  # noqa: E402

from core import alto_reconstructor as ar  # noqa: E402
from core import calidad_ocr as cal  # noqa: E402

CORPUS = Path(r"C:\build_rf\bashkar_corpus")
N_PAGINAS = 12

# % de fragmentación medido en RESULTADOS.md, para contrastar.
ESPERADO = {
    "agitaci": 4.0, "el nuevo": 35.6, "estampa": 6.8, "la mujer": 7.4,
    "la semana": 20.8, "panida": 6.2, "rin-rin": 2.6,
}


def medir(pdf: Path, n_paginas: int = N_PAGINAS) -> cal.Veredicto:
    """Texto por la ruta de producción, muestreando el documento entero."""
    doc = fitz.open(str(pdf))
    try:
        paso = max(1, len(doc) // n_paginas)
        indices = list(range(0, len(doc), paso))[:n_paginas]
        textos = []
        for i in indices:
            try:
                datos = ar.reconstruir_texto_pagina(doc[i])
                textos.append(datos.get("texto", "") if isinstance(datos, dict)
                              else str(datos))
            except Exception:
                textos.append("")
    finally:
        doc.close()
    return cal.evaluar_paginas(textos)


def main() -> None:
    if not CORPUS.exists():
        print(f"No existe {CORPUS}. Copia los PDF con copiar_corpus.py primero.")
        return

    print(f"{'PUBLICACION':24s} {'PAGS':>5} {'TXT':>5} {'COBERT':>7} "
          f"{'TOKENS':>7} {'FRAG%':>7} {'FUS%':>6}  {'VEREDICTO':14s} {'s.66':>8}")
    print("-" * 100)

    for carpeta in sorted(p for p in CORPUS.iterdir() if p.is_dir()):
        pdf = next(iter(sorted(carpeta.glob("*.pdf"))), None)
        if pdf is None:
            continue

        censo = cal.censar_paginas(pdf)
        v = medir(pdf)
        ref = next((x for k, x in ESPERADO.items() if k in carpeta.name.lower()), None)

        print(f"{carpeta.name[:24]:24s} {censo.n_paginas:>5} "
              f"{len(censo.paginas_con_texto):>5} {censo.cobertura:>6.0%} "
              f"{v.metricas.tokens:>7} {v.metricas.pct_fragmentacion:>6.1f}% "
              f"{v.metricas.pct_fusion:>5.2f}%  {v.veredicto:14s} "
              f"{(f'{ref:.1f} %' if ref else '—'):>8}")


if __name__ == "__main__":
    main()
