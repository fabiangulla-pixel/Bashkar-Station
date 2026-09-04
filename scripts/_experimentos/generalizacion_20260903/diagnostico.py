"""Diagnóstico de generalización: por qué ruta de OCR entra cada publicación.

Responde con evidencia medida la pregunta de evaluación n.º 1 del plan de Becas
Leonardo — si Bashkar generaliza "sin reglas fijas de una sola publicación".

Qué mira y por qué importa cada cosa:

- **Capa oculta de Adobe Paper Capture.** `core/alto_reconstructor.py` explota la
  fuente `HiddenHorzOCR` que traen los PDF digitalizados por la BNC. Es la ruta
  buena: texto ya reconocido, con coordenadas, sin rehacer OCR. Un PDF de otro
  archivo no la tiene y cae a OCR desde cero.
- **Texto por página, no por documento.** La validación previa encontró que en
  *El Día* la última página tiene 12.318 caracteres y la del medio tiene 0.
  Dentro de un mismo ejemplar conviven páginas con y sin texto, así que decidir
  la ruta una vez por documento se equivoca en la mitad.
- **Tamaño de fuente.** El umbral que separa palabras en `alto_reconstructor` es
  relativo (0,018 × tamaño de fuente) y se calibró contra *Estampa*. Con otra
  tipografía puede fusionar o partir palabras — lo que ya pasó con *Panida*.

Cada PDF se analiza en un subproceso propio con límite de tiempo: un archivo con
la tabla de referencias cruzadas rota cuelga a MuPDF indefinidamente, y en un
piloto que acepta cargas de usuarios eso no puede tumbar el lote.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

MUESTRA = Path(r"C:\build_rf\generalizacion\muestra")
LIMITE_S = 120
PAGINAS_A_MIRAR = 8

SONDA = r'''
import json, statistics, sys, fitz

ruta = sys.argv[1]
doc = fitz.open(ruta)
n_pag = len(doc)
# Muestreo repartido por todo el ejemplar, no las primeras N: las primeras
# paginas suelen ser portada y no representan el cuerpo del documento.
paso = max(1, n_pag // 8)
indices = list(range(0, n_pag, paso))[:8]

con_texto = 0
chars_por_pagina = []
tamanos = []
fuentes = set()
imagenes = 0

for i in indices:
    pag = doc[i]
    t = pag.get_text().strip()
    chars_por_pagina.append(len(t))
    if len(t) > 200:          # 200 ch = umbral de "hay cuerpo de texto", no una marca de agua
        con_texto += 1
    for f in pag.get_fonts(full=True):
        fuentes.add(str(f[3]))
    imagenes += len(pag.get_images())
    for bloque in pag.get_text("dict").get("blocks", []):
        for linea in bloque.get("lines", []):
            for span in linea.get("spans", []):
                if span.get("text", "").strip():
                    tamanos.append(span.get("size", 0.0))

doc.close()
print(json.dumps({
    "paginas": n_pag,
    "muestreadas": len(indices),
    "con_texto": con_texto,
    "chars_min": min(chars_por_pagina) if chars_por_pagina else 0,
    "chars_max": max(chars_por_pagina) if chars_por_pagina else 0,
    "chars_medio": int(statistics.median(chars_por_pagina)) if chars_por_pagina else 0,
    "imagenes": imagenes,
    "fuentes": sorted(fuentes)[:12],
    "tam_fuente": round(statistics.median(tamanos), 2) if tamanos else 0.0,
}))
'''


def ruta_ocr(d: dict) -> str:
    # Un PDF ilegible devuelve 0 paginas; sin esta guarda, 0 == 0 hacia que
    # cayera en "texto embebido en todas las paginas" y un archivo danado se
    # reportaba como el mejor caso posible.
    if not d["muestreadas"]:
        return "ILEGIBLE (0 paginas legibles)"
    oculta = any("HiddenHorz" in f or "OCR" in f.upper() for f in d["fuentes"])
    if oculta:
        return "CAPA OCULTA Paper Capture -> alto_reconstructor (ruta buena)"
    if d["con_texto"] == d["muestreadas"]:
        return "texto embebido en todas las paginas"
    if d["con_texto"] == 0:
        return "SOLO IMAGEN -> OCR desde cero (Tesseract/Kraken/CHURRO)"
    return (f"MIXTO: solo {d['con_texto']}/{d['muestreadas']} paginas con texto "
            f"-> hay que decidir por pagina")


def main() -> None:
    pdfs = sorted(MUESTRA.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"No hay PDFs en {MUESTRA}")

    resultados = []
    print(f"{'PUBLICACION':32s} {'PAGS':>5} {'CH/PAG':>7} {'FUENTE':>7}  RUTA", flush=True)
    print("-" * 110, flush=True)

    for pdf in pdfs:
        nombre = pdf.stem[:32]
        try:
            r = subprocess.run([sys.executable, "-c", SONDA, str(pdf)],
                               capture_output=True, text=True, timeout=LIMITE_S)
            if r.returncode != 0:
                print(f"{nombre:32s} {'-':>5} {'-':>7} {'-':>7}  ILEGIBLE (PDF danado)",
                      flush=True)
                continue
            d = json.loads(r.stdout)
            d["nombre"] = nombre
            d["ruta"] = ruta_ocr(d)
            resultados.append(d)
            print(f"{nombre:32s} {d['paginas']:>5} {d['chars_medio']:>7} "
                  f"{d['tam_fuente']:>7}  {d['ruta']}", flush=True)
        except subprocess.TimeoutExpired:
            print(f"{nombre:32s} {'-':>5} {'-':>7} {'-':>7}  COLGADO >{LIMITE_S}s "
                  f"(xref roto)", flush=True)

    if not resultados:
        return

    print(flush=True)
    con_oculta = [d for d in resultados if "CAPA OCULTA" in d["ruta"]]
    print(f"Con capa oculta Paper Capture: {len(con_oculta)} de {len(resultados)}",
          flush=True)
    for d in resultados:
        marca = "+" if "CAPA OCULTA" in d["ruta"] else "-"
        print(f"  {marca} {d['nombre']:32s} {d['ruta']}", flush=True)

    print(flush=True)
    tam = [d["tam_fuente"] for d in resultados if d["tam_fuente"]]
    if len(tam) > 1:
        print(f"Tamano de fuente: min {min(tam)} / max {max(tam)} "
              f"(razon {max(tam)/min(tam):.1f}x)", flush=True)
        print("El umbral de separacion de palabras es 0,018 x tamano de fuente,",
              flush=True)
        print("calibrado contra Estampa. Cuanto mayor la dispersion, mayor el",
              flush=True)
        print("riesgo de fusionar o partir palabras en las demas publicaciones.",
              flush=True)

    salida = Path(r"C:\build_rf\generalizacion\diagnostico.json")
    salida.write_text(json.dumps(resultados, indent=2, ensure_ascii=False),
                      encoding="utf-8")
    print(f"\nDetalle guardado en {salida}", flush=True)


if __name__ == "__main__":
    main()
