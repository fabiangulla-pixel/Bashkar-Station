#!/usr/bin/env python
"""scripts/verificar_licencias.py — LICENCIAS_DE_TERCEROS.md al día.

Dos usos:

    python scripts/verificar_licencias.py            # comprobar (CI)
    python scripts/verificar_licencias.py --tabla    # regenerar la tabla de
                                                     # dependencias de Python

Comprueba que cada paquete de requirements.lock.txt y cada modelo que el
código descarga figuren en LICENCIAS_DE_TERCEROS.md. Sale con código 1 si
falta alguno: añadir una dependencia sin declarar su licencia rompe la CI.

La tabla se genera desde los metadatos de los paquetes instalados (licencia
declarada por cada autor), entre los marcadores INICIO/FIN del documento.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DOC = RAIZ / "LICENCIAS_DE_TERCEROS.md"
LOCK = RAIZ / "requirements.lock.txt"
INICIO = "<!-- INICIO tabla generada por scripts/verificar_licencias.py --tabla -->"
FIN = "<!-- FIN tabla generada -->"

# Modelos que el código descarga o puede descargar. Si se añade uno al código,
# añadirlo aquí y en el documento.
MODELOS = (
    "stanford-oval/churro-3B",
    "mrm8488/bert-spanish-cased-finetuned-ner",
    "pysentimiento/robertuito-sentiment-analysis",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "es_core_news_sm",
    "es_core_news_md",
    "es_core_news_lg",
    "CATMuS-Print",
)


def paquetes_lock() -> list[tuple[str, str]]:
    salida = []
    for linea in LOCK.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith(("#", "-")):
            continue
        nombre = re.split(r"[=<>;\[ @]", linea)[0].strip()
        version = linea.split("==")[1].split(";")[0].strip() if "==" in linea else ""
        if nombre:
            salida.append((nombre, version))
    return salida


def _norm(nombre: str) -> str:
    return re.sub(r"[-_.]+", "-", nombre).lower()


def faltantes() -> list[str]:
    texto = DOC.read_text(encoding="utf-8") if DOC.exists() else ""
    presentes = {_norm(m) for m in re.findall(r"`([^`]+)`", texto)}
    falta = [f"paquete {n}" for n, _ in paquetes_lock() if _norm(n) not in presentes]
    falta += [f"modelo {m}" for m in MODELOS if m not in texto]
    return falta


def licencia_instalada(nombre: str) -> str:
    import importlib.metadata as md
    try:
        m = md.metadata(nombre)
    except md.PackageNotFoundError:
        return "no instalado en este entorno"
    lic = (m.get("License-Expression") or "").strip()
    if not lic:
        clas = [c.split("::")[-1].strip() for c in (m.get_all("Classifier") or [])
                if c.startswith("License ::")]
        lic = "; ".join(clas)
    if not lic:
        lic = ((m.get("License") or "").strip().splitlines() or [""])[0][:60]
    return lic or "no declarada"


def regenerar_tabla() -> None:
    filas = ["| Paquete | Versión | Licencia declarada |", "|---|---|---|"]
    filas += [f"| `{n}` | {v} | {licencia_instalada(n)} |" for n, v in paquetes_lock()]
    texto = DOC.read_text(encoding="utf-8")
    nuevo = re.sub(re.escape(INICIO) + r".*?" + re.escape(FIN),
                   INICIO + "\n" + "\n".join(filas) + "\n" + FIN, texto, flags=re.S)
    DOC.write_text(nuevo, encoding="utf-8")


def main() -> int:
    if "--tabla" in sys.argv:
        regenerar_tabla()
        print(f"Tabla regenerada en {DOC.name}")
    falta = faltantes()
    if falta:
        print(f"Faltan en {DOC.name}:")
        for f in falta:
            print(f"  - {f}")
        return 1
    print(f"{DOC.name}: {len(paquetes_lock())} paquetes y {len(MODELOS)} modelos declarados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
