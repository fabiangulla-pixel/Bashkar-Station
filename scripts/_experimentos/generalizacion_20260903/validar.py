"""Valida la integridad de cada PDF de la muestra, uno por uno y aislado.

Por qué aislado: dos copias desde Google Drive fallaron con "Invalid request
code" y aun así dejaron un archivo de tamaño plausible en disco. Un PDF truncado
abre sin protestar —el encabezado está intacto— y solo falla al llegar al final,
o peor, hace que MuPDF se ponga a reconstruir la tabla de referencias cruzadas y
tarde muchísimo. Con un límite de tiempo por archivo, uno dañado no bloquea el
diagnóstico de los demás.

Cada archivo se procesa en un subproceso propio: si se cuelga, se mata solo ese.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

MUESTRA = Path(r"C:\build_rf\generalizacion\muestra")
LIMITE_S = 90

# Lo que corre dentro del subproceso, por archivo.
SONDA = r"""
import sys, fitz
ruta = sys.argv[1]
d = fitz.open(ruta)
n = len(d)
# La ULTIMA pagina es la prueba real: un archivo truncado revienta aqui,
# no al abrir.
chars = len(d[n - 1].get_text())
# Y una pagina del medio, por si el dano esta en el cuerpo.
medio = len(d[n // 2].get_text())
d.close()
print(f"{n}|{chars}|{medio}")
"""


def main() -> None:
    pdfs = sorted(MUESTRA.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"No hay PDFs en {MUESTRA}")

    print(f"{'ARCHIVO':34s} {'MB':>7} {'PAGS':>5}  ESTADO", flush=True)
    print("-" * 78, flush=True)

    buenos, malos = [], []
    for pdf in pdfs:
        mb = pdf.stat().st_size / 1e6
        try:
            r = subprocess.run(
                [sys.executable, "-c", SONDA, str(pdf)],
                capture_output=True, text=True, timeout=LIMITE_S,
            )
            if r.returncode != 0:
                err = (r.stderr or "").strip().splitlines()
                motivo = err[-1][:52] if err else f"codigo {r.returncode}"
                print(f"{pdf.name:34s} {mb:7.1f} {'-':>5}  DANADO: {motivo}", flush=True)
                malos.append(pdf.name)
                continue
            n, chars, medio = r.stdout.strip().split("|")
            print(f"{pdf.name:34s} {mb:7.1f} {n:>5}  ok (ultima {chars} ch, "
                  f"medio {medio} ch)", flush=True)
            buenos.append(pdf.name)
        except subprocess.TimeoutExpired:
            print(f"{pdf.name:34s} {mb:7.1f} {'-':>5}  COLGADO >{LIMITE_S}s "
                  f"(xref probablemente roto)", flush=True)
            malos.append(pdf.name)

    print(flush=True)
    print(f"Integros: {len(buenos)} de {len(pdfs)}", flush=True)
    if malos:
        print("Hay que volver a copiar desde Drive:", flush=True)
        for m in malos:
            print(f"   - {m}", flush=True)


if __name__ == "__main__":
    main()
