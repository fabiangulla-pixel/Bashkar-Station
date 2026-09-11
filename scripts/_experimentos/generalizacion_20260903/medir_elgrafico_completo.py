"""Mide *El Gráfico* entero con Tesseract español: los 82 números, 1910-1929.

Contexto. *El Gráfico* es la única de las nueve publicaciones sin capa de texto
—44 caracteres por página, que son la marca de agua— y es el contraste
colombiano elegido en el plan de Becas Leonardo. Hasta la sesión 68 la prueba de
generalización no podía decir nada de ella: no había `spa.traineddata`
instalado. Ya lo hay, y dos números sueltos dieron 92,7 % de confianza media,
mejor que *Estampa* en fusión. Este script convierte esas dos catas en una
medición de la colección.

Qué hace, por número:
  · rasteriza una muestra de páginas repartida por el ejemplar (no las
    primeras: las portadas y los índices no representan el cuerpo);
  · pasa Tesseract en español;
  · mide confianza, fusión y fragmentación con `core.calidad_ocr`, el mismo
    módulo que usa el pipeline, para que la cifra del experimento y la del
    producto no puedan divergir;
  · emite el veredicto de abstención.

Decisiones de ejecución:

**Checkpoint incremental.** Cada número se escribe a `resultados.jsonl` en
cuanto termina. Un proceso de horas que solo guarda al final es frágil: si se
cae en el número 70 se pierde todo. Relanzar el script salta lo ya medido.

**Paralelo por procesos.** Tesseract es CPU y libera el GIL a ratos, pero
`ocr_pagina` hace también trabajo Python; procesos separados escalan de verdad.
Por defecto la mitad de los núcleos, para no dejar el equipo inservible.

Uso:
    python medir_elgrafico_completo.py [--paginas 4] [--workers 8] [--rehacer]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))

CORPUS = Path(r"C:\build_rf\bashkar_corpus\El Gráfico")
TRABAJO = Path(r"C:\build_rf\elgrafico_medicion")
SALIDA = Path(__file__).parent / "elgrafico_resultados.jsonl"

DPI = 300
N_PAGINAS = 4
# Mínimo que `calidad_ocr.evaluar_metricas` exige para emitir un veredicto.
# Por debajo se amplía la muestra en vez de declarar "muestra insuficiente".
MIN_TOKENS_OBJETIVO = 200


def _paginas_muestra(n_total: int, n: int, minimo_por_100: int = 4) -> list[int]:
    """Índices 0-based repartidos por el ejemplar, evitando la portada.

    Muestrear las primeras páginas mide portadas, índices y publicidad de
    cubierta, que no se parecen al cuerpo de la revista.

    La muestra crece con el ejemplar. La primera corrida usaba `n` páginas
    fijas y los cinco números que el sistema marcó por "muestra insuficiente"
    resultaron ser justamente los más largos —101 y 221 páginas frente a las
    ~50 habituales—, donde cuatro páginas sueltas cayeron en fotografía casi
    pura y dieron entre 5 y 40 tokens. El problema no era el corpus: era medir
    un número de 221 páginas con la misma muestra que uno de 48.
    """
    if n_total <= n:
        return list(range(n_total))
    n_efectivo = max(n, round(minimo_por_100 * n_total / 100))
    n_efectivo = min(n_efectivo, n_total)
    paso = n_total / (n_efectivo + 1)
    indices = [min(n_total - 1, int(paso * (i + 1))) for i in range(n_efectivo)]
    return sorted(set(indices))


def medir_numero(pdf_str: str, n_paginas: int, dpi: int) -> dict:
    """Mide UN número. Se ejecuta en un proceso propio."""
    import fitz

    from core.calidad_ocr import evaluar_paginas, metricas_texto
    from core.ocr_engine import ocr_pagina
    from core.ocr_normalizer import normalizar_texto_ocr

    pdf = Path(pdf_str)
    t0 = time.time()
    fila: dict = {"archivo": pdf.name}

    try:
        doc = fitz.open(str(pdf))
    except Exception as e:
        fila.update(error=f"{type(e).__name__}: {e}")
        return fila

    try:
        fila["n_paginas"] = doc.page_count
        mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
        destino = TRABAJO / pdf.stem
        destino.mkdir(parents=True, exist_ok=True)

        textos: list[str] = []
        confianzas: list[float] = []
        medidas: set[int] = set()

        def _medir_pagina(i: int) -> None:
            img = destino / f"p{i+1:04d}.png"
            try:
                if not img.exists():
                    doc[i].get_pixmap(matrix=mat).save(str(img))
                texto, conf = ocr_pagina(img)
                textos.append(normalizar_texto_ocr(texto))
                if conf is not None:
                    confianzas.append(float(conf))
            except Exception as e:
                fila.setdefault("paginas_fallidas", []).append(
                    {"pagina": i + 1, "error": f"{type(e).__name__}: {e}"}
                )
            finally:
                # Las PNG a 300 DPI de una plana de revista pesan ~25 MB. Medir
                # 82 números las dejaría todas en disco sin que nadie las use.
                img.unlink(missing_ok=True)
            medidas.add(i)

        for i in _paginas_muestra(doc.page_count, n_paginas):
            _medir_pagina(i)

        # Ampliar la muestra hasta reunir evidencia suficiente.
        #
        # La causa de que cinco números salieran "muestra insuficiente" no era
        # la longitud del ejemplar sino que *El Gráfico* es una revista
        # gráfica: hay páginas que son una fotografía a plana entera y dan
        # entre 5 y 40 tokens. Muestrear más páginas por ser el número largo
        # ayuda a los de 221 y no hace nada por los de 101, porque el problema
        # es dónde cae la muestra, no cuántas páginas tiene el ejemplar.
        #
        # Así que se mide hasta alcanzar el mínimo que `calidad_ocr` exige para
        # opinar, tomando páginas nuevas repartidas entre las ya medidas. El
        # tope evita que un número entero de fotografías rasterice las 277
        # páginas para no llegar nunca.
        objetivo = MIN_TOKENS_OBJETIVO
        tope = min(doc.page_count, max(len(medidas) * 4, 16))
        while (sum(metricas_texto(t).tokens for t in textos) < objetivo
               and len(medidas) < tope):
            candidatos = [i for i in range(doc.page_count) if i not in medidas]
            if not candidatos:
                break
            paso = max(1, len(candidatos) // 4)
            nuevos = candidatos[::paso][:4]
            if not nuevos:
                break
            for i in nuevos:
                _medir_pagina(i)

        fila["paginas_ampliada"] = len(medidas) > len(
            _paginas_muestra(doc.page_count, n_paginas))
    finally:
        doc.close()

    if not textos:
        fila.update(error="ninguna página medible", segundos=round(time.time() - t0, 1))
        return fila

    v = evaluar_paginas(textos)
    largos = [len(t) for texto in textos
              for t in __import__("re").findall(r"[^\W\d_]+", texto)]

    fila.update(
        paginas_medidas=len(textos),
        confianza=round(sum(confianzas) / len(confianzas), 2) if confianzas else None,
        tokens=v.metricas.tokens,
        pct_fusion=round(v.metricas.pct_fusion, 3),
        pct_fragmentacion=round(v.metricas.pct_fragmentacion, 2),
        largo_medio_token=round(sum(largos) / len(largos), 2) if largos else 0.0,
        veredicto=v.veredicto,
        motivos=list(v.motivos),
        segundos=round(time.time() - t0, 1),
    )
    return fila


def _ya_medidos(salida: Path) -> set[str]:
    hechos = set()
    if salida.exists():
        for linea in salida.read_text(encoding="utf-8").splitlines():
            try:
                fila = json.loads(linea)
            except Exception:
                continue
            if not fila.get("error"):
                hechos.add(fila.get("archivo", ""))
    return hechos


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--paginas", type=int, default=N_PAGINAS,
                    help="páginas muestreadas por número")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) // 2))
    ap.add_argument("--dpi", type=int, default=DPI)
    ap.add_argument("--rehacer", action="store_true",
                    help="ignora el checkpoint y vuelve a medirlo todo")
    args = ap.parse_args()

    if not CORPUS.exists():
        print(f"No existe {CORPUS}. Copia el corpus con copiar_corpus.py primero.")
        return

    pdfs = sorted(CORPUS.glob("*.pdf"))
    if args.rehacer:
        SALIDA.unlink(missing_ok=True)
    hechos = _ya_medidos(SALIDA)
    pendientes = [p for p in pdfs if p.name not in hechos]

    print(f"El Gráfico: {len(pdfs)} números · {len(hechos)} ya medidos · "
          f"{len(pendientes)} pendientes")
    print(f"Muestra: {args.paginas} páginas/número a {args.dpi} DPI · "
          f"{args.workers} procesos", flush=True)
    if not pendientes:
        return

    TRABAJO.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    hecho = 0

    with SALIDA.open("a", encoding="utf-8") as f, \
         ProcessPoolExecutor(max_workers=args.workers) as pool:
        futuros = {pool.submit(medir_numero, str(p), args.paginas, args.dpi): p
                   for p in pendientes}
        for fut in as_completed(futuros):
            pdf = futuros[fut]
            try:
                fila = fut.result()
            except Exception as e:
                fila = {"archivo": pdf.name, "error": f"{type(e).__name__}: {e}"}
            # Se escribe y se vacía el buffer AL MOMENTO: si esto muere en el
            # número 70, los 69 anteriores están en disco.
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
            f.flush()

            hecho += 1
            transcurrido = time.time() - t0
            restante = transcurrido / hecho * (len(pendientes) - hecho)
            if fila.get("error"):
                estado = f"ERROR: {fila['error'][:40]}"
            else:
                estado = (f"conf {fila['confianza']:.1f}% · "
                          f"frag {fila['pct_fragmentacion']:.1f}% · "
                          f"fus {fila['pct_fusion']:.2f}% · {fila['veredicto']}")
            print(f"[{hecho:>3}/{len(pendientes)}] {pdf.name[:42]:42s} {estado} "
                  f"· faltan ~{restante/60:.0f} min", flush=True)

    print(f"\nListo en {(time.time()-t0)/60:.1f} min → {SALIDA}")


if __name__ == "__main__":
    main()
