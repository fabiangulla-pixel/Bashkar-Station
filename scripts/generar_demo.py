#!/usr/bin/env python
"""scripts/generar_demo.py — Demo pública de solo lectura de un corpus de Bashkar.

Dos etapas, para que el repositorio no cargue con las imágenes:

1. ``datos``: desde un proyecto ya procesado (.bashkar + .db) escribe JSON
   pequeños en ``demo/datos/`` (números, páginas con su transcripción,
   unidades editoriales, entidades, grafo, cifras) y las descargas (TEI,
   CSV de entidades, BibTeX). Se versionan.

       python scripts/generar_demo.py datos --proyecto ruta.bashkar

2. ``sitio``: arma el sitio estático en una carpeta: copia la plantilla de
   ``demo/plantilla/``, los datos y las imágenes de página reducidas a WebP.
   Las imágenes salen de una carpeta ``<numero>/pNNNN.jpg`` (los ZIP de la
   *release* ``vision-ocr-entrada-v1``) o de los PDF originales.

       python scripts/generar_demo.py sitio --imagenes carpeta --salida _site
       python scripts/generar_demo.py sitio --pdf-dir carpeta_pdf --salida _site

Las cifras que muestra el sitio salen de los datos; nada se escribe a mano.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sqlite3
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
DATOS = RAIZ / "demo" / "datos"
PLANTILLA = RAIZ / "demo" / "plantilla"

MESES = {"ene": "Enero", "feb": "Febrero", "mar": "Marzo", "abr": "Abril", "may": "Mayo",
         "jun": "Junio", "jul": "Julio", "ago": "Agosto", "sep": "Septiembre",
         "oct": "Octubre", "nov": "Noviembre", "dic": "Diciembre"}
NODOS_GRAFO = 250          # entidades más frecuentes en el grafo
PESO_MIN_ARISTA = 2        # unidades compartidas para dibujar una relación


def etiqueta_numero(numero: str) -> str:
    m = re.search(r"_(\w{3})_(\d{4})$", numero)
    return f"{MESES.get(m.group(1), m.group(1))} de {m.group(2)}" if m else numero


def paginas_de(valor) -> list[str]:
    return [p for p in re.split(r"[-,\s]+", str(valor or "")) if re.fullmatch(r"p\d{4}", p)]


def _limpio(v) -> str:
    s = str(v if v is not None else "").strip()
    return "" if s.lower() in ("nan", "none") else s


# ── Etapa 1: datos ────────────────────────────────────────────────────────────

def exportar_datos(ruta_proyecto: Path, destino: Path = DATOS) -> dict:
    from core.estado import Estado
    from core.metadatos_exportacion import metadatos_proyecto
    from core.project_manager import cargar_proyecto
    from core.servicios_exportacion import articulos_para_tei
    from core.tei_engine import exportar_bibtex, exportar_corpus_tei

    st = Estado()
    res = cargar_proyecto(ruta_proyecto, st)
    if not res.get("ok"):
        raise SystemExit(f"No se pudo abrir el proyecto: {res.get('mensaje')}")
    df = st.df_articulos
    if df is None or df.empty:
        raise SystemExit("El proyecto no tiene unidades segmentadas.")
    indice = st.indice_ner_global or {}

    destino.mkdir(parents=True, exist_ok=True)
    (destino / "numeros").mkdir(exist_ok=True)
    (destino / "descargas").mkdir(exist_ok=True)

    # Entidades por unidad
    por_unidad: dict[str, dict[str, list[str]]] = {}
    entidades = []
    for cat, ents in indice.items():
        if not isinstance(ents, dict):
            continue
        for texto, unidades in ents.items():
            entidades.append({"t": texto, "c": cat, "u": list(unidades)})
            for u in unidades:
                por_unidad.setdefault(u, {}).setdefault(cat, []).append(texto)
    menciones = sum(len(e["u"]) for e in entidades)   # pares forma escrita–unidad
    formas_escritas = len(entidades)
    entidades = fundir_variantes(entidades)

    # Números, páginas y unidades
    ocr_dir = Path(st.out_dir) / "03_ocr"
    meta = st.corpus_meta
    numeros = []
    for numero in sorted(df["numero"].unique(), key=_orden_numero):
        filas = df[df["numero"] == numero]
        paginas_txt = sorted((ocr_dir / numero).glob("p*.txt"))
        unidades_por_pag: dict[str, list[str]] = {}
        unidades = []
        for _, a in filas.iterrows():
            pags = paginas_de(a.get("pagina") or a.get("paginas"))
            for p in pags:
                unidades_por_pag.setdefault(p, []).append(a["id"])
            unidades.append({
                "id": a["id"], "titulo": _limpio(a.get("titulo")) or "Sin título",
                "autor": _limpio(a.get("autor")), "seccion": _limpio(a.get("seccion")),
                "paginas": pags, "palabras": int(a.get("palabras") or 0),
                "entidades": por_unidad.get(a["id"], {}),
            })
        paginas = []
        for t in paginas_txt:
            texto = t.read_text(encoding="utf-8", errors="replace")
            pag = {"p": t.stem, "texto": texto, "unidades": unidades_por_pag.get(t.stem, [])}
            if es_descripcion_del_modelo(texto):
                pag["texto"], pag["sin_texto"] = "", True
            paginas.append(pag)
        (destino / "numeros" / f"{numero}.json").write_text(
            json.dumps({"id": numero, "paginas": paginas, "unidades": unidades},
                       ensure_ascii=False), encoding="utf-8")
        numeros.append({"id": numero, "etiqueta": etiqueta_numero(numero),
                        "paginas": len(paginas), "unidades": len(unidades),
                        "portada": pagina_portada(paginas)})

    (destino / "entidades.json").write_text(json.dumps(entidades, ensure_ascii=False),
                                            encoding="utf-8")
    grafo = construir_grafo(entidades)
    (destino / "grafo.json").write_text(json.dumps(grafo, ensure_ascii=False), encoding="utf-8")

    # Descargas, con los mismos exportadores de la aplicación
    md = metadatos_proyecto(st, res.get("nombre", ""), res.get("historial_ia"))
    arts = articulos_para_tei(st.corpus_txt, indice, articulos=df)
    exportar_corpus_tei(arts, destino / "descargas" / "corpus_tei.xml", metadatos=md)
    exportar_bibtex(arts, destino / "descargas" / "corpus.bib", fuente=md["publicacion"],
                    editor=md["responsable"], periodo=md["periodo"])
    with open(destino / "descargas" / "entidades.csv", "w", encoding="utf-8-sig",
              newline="") as f:
        w = csv.writer(f)
        w.writerow(["entidad", "categoria", "n_unidades", "otras_formas", "unidades"])
        for e in entidades:
            w.writerow([e["t"], e["c"], len(e["u"]), " | ".join(e.get("f", [])),
                        " ".join(e["u"])])

    canon = relaciones = 0
    if st.ruta_db:
        con = sqlite3.connect(st.ruta_db)
        canon = con.execute("SELECT COUNT(*) FROM entidades_canonicas").fetchone()[0]
        relaciones = con.execute("SELECT COUNT(*) FROM relaciones").fetchone()[0]
        con.close()
    cifras = {
        "numeros": len(numeros),
        "paginas": sum(n["paginas"] for n in numeros),
        "unidades": int(len(df)),
        "entidades_unicas": formas_escritas,
        "entidades_indice": len(entidades),
        "menciones": menciones,
        "por_categoria": dict(Counter(e["c"] for e in entidades)),
        "entidades_canonicas": canon,
        "relaciones": relaciones,
        "metodo_ocr": md["herramientas"]["ocr"],
        "motor_ner": md["herramientas"]["ner"],
    }
    corpus = {
        "proyecto": md["proyecto"], "publicacion": md["publicacion"],
        "periodo": md["periodo"], "lugar": md["lugar"],
        "creditos": md["creditos"], "disponibilidad": md["disponibilidad"],
        "cifras": cifras, "numeros": numeros,
    }
    (destino / "corpus.json").write_text(json.dumps(corpus, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    return cifras


_RE_DESCRIPCION = re.compile(
    r"^\s*(La imagen (que se muestra|corresponde)|Esta página no contiene texto"
    r"|No hay texto legible|La página (está en blanco|no contiene))", re.I)


def es_descripcion_del_modelo(texto: str) -> bool:
    """¿El «texto» es una descripción que escribió el modelo de visión, no la
    revista? Pasa en páginas sin texto (lomo del volumen, hojas en blanco): en
    enero de 1939, las páginas 1 y 3. La demo no la presenta como transcripción.
    """
    return bool(_RE_DESCRIPCION.match(texto or ""))


def pagina_portada(paginas: list[dict], buscar_en: int = 6) -> str:
    """Página que sirve de portada en la miniatura del número.

    La página 1 del escaneo no siempre es la portada: en enero de 1939 es el
    lomo del volumen empastado, y le siguen la hoja de sello de la BNC y una en
    blanco. Se toma la primera, entre las primeras, que nombra la revista con
    poco texto (la cabecera); si ninguna, la 1.
    """
    for p in paginas[:buscar_en]:
        texto = p["texto"]
        if "estampa" in texto.lower() and len(texto.split()) <= 40:
            return p["p"]
    return paginas[0]["p"] if paginas else "p0001"


def _sin_acentos(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                   if unicodedata.category(c) != "Mn")


def fundir_variantes(entidades: list[dict]) -> list[dict]:
    """Une las formas escritas de una misma entidad dentro de su categoría.

    «Bogotá», «BOGOTA» y «Bogota» son tres entradas en el índice del proyecto
    (252 grupos así en Estampa ene–may 1939). Aquí se agrupan sin distinguir
    mayúsculas ni acentos; se muestra la forma presente en más unidades (a
    igualdad, la que no va toda en mayúsculas) y las demás quedan en ``f``.
    Es una decisión de presentación de la demo: no cambia el proyecto.
    """
    grupos: dict[tuple, list[dict]] = {}
    for e in entidades:
        grupos.setdefault((e["c"], _sin_acentos(e["t"])), []).append(e)
    salida = []
    for (cat, _), formas in grupos.items():
        formas.sort(key=lambda e: (-len(e["u"]), e["t"].isupper(), e["t"]))
        unidades: list[str] = []
        for f in formas:
            unidades += [u for u in f["u"] if u not in unidades]
        ent = {"t": formas[0]["t"], "c": cat, "u": unidades}
        if len(formas) > 1:
            ent["f"] = [f["t"] for f in formas[1:]]
        salida.append(ent)
    salida.sort(key=lambda e: (-len(e["u"]), e["t"].lower()))
    return salida


def _orden_numero(numero: str):
    orden = list(MESES)
    m = re.search(r"_(\w{3})_(\d{4})$", numero)
    return (m.group(2), orden.index(m.group(1))) if m and m.group(1) in orden else (numero, 0)


def construir_grafo(entidades: list[dict], n_nodos: int = NODOS_GRAFO,
                    peso_min: int = PESO_MIN_ARISTA) -> dict:
    """Co-ocurrencia de las entidades más frecuentes en las mismas unidades."""
    top = [e for e in entidades if e["c"] in ("personas", "lugares", "organizaciones")][:n_nodos]
    ids = {(e["c"], e["t"]): i for i, e in enumerate(top)}
    unidades: dict[str, list[int]] = {}
    for e in top:
        for u in e["u"]:
            unidades.setdefault(u, []).append(ids[(e["c"], e["t"])])
    pesos: Counter = Counter()
    for nodos in unidades.values():
        for a, b in combinations(sorted(set(nodos)), 2):
            pesos[(a, b)] += 1
    return {
        "nodos": [{"id": i, "t": e["t"], "c": e["c"], "n": len(e["u"])} for i, e in enumerate(top)],
        "aristas": [{"a": a, "b": b, "w": w} for (a, b), w in pesos.items() if w >= peso_min],
    }


# ── Etapa 2: sitio ────────────────────────────────────────────────────────────

def construir_sitio(salida: Path, imagenes: Path | None = None, pdf_dir: Path | None = None,
                    ancho: int = 1000, ancho_miniatura: int = 220, calidad: int = 72) -> int:
    from PIL import Image

    if salida.exists():
        shutil.rmtree(salida)
    shutil.copytree(PLANTILLA, salida)
    shutil.copytree(DATOS, salida / "datos")
    vis = RAIZ / "lib" / "vis-9.1.2" / "vis-network.min.js"
    if vis.exists():
        shutil.copy2(vis, salida / "vis-network.min.js")
    corpus = json.loads((DATOS / "corpus.json").read_text(encoding="utf-8"))
    n = 0
    for numero in corpus["numeros"]:
        nid = numero["id"]
        dst = salida / "img" / nid
        dst.mkdir(parents=True, exist_ok=True)
        for img, pid in _paginas_imagen(nid, imagenes, pdf_dir):
            img = img.convert("RGB")
            grande = img.copy()
            grande.thumbnail((ancho, ancho * 2))
            grande.save(dst / f"{pid}.webp", "WEBP", quality=calidad, method=6)
            mini = img.copy()
            mini.thumbnail((ancho_miniatura, ancho_miniatura * 2))
            mini.save(dst / f"{pid}_mini.webp", "WEBP", quality=60, method=6)
            n += 1
    (salida / ".nojekyll").write_text("", encoding="utf-8")
    return n


def _paginas_imagen(numero: str, imagenes: Path | None, pdf_dir: Path | None):
    from PIL import Image
    if imagenes is not None:
        for jpg in sorted((imagenes / numero).glob("p*.jpg")):
            with Image.open(jpg) as im:
                yield im.copy(), jpg.stem
        return
    import pymupdf
    doc = pymupdf.open(str(pdf_dir / f"{numero}.pdf"))
    try:
        for i, pagina in enumerate(doc, 1):
            pix = pagina.get_pixmap(dpi=110)
            yield Image.frombytes("RGB", (pix.width, pix.height), pix.samples), f"p{i:04d}"
    finally:
        doc.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="etapa", required=True)
    d = sub.add_parser("datos")
    d.add_argument("--proyecto", required=True, type=Path)
    s = sub.add_parser("sitio")
    s.add_argument("--salida", required=True, type=Path)
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--imagenes", type=Path)
    g.add_argument("--pdf-dir", type=Path)
    args = ap.parse_args()
    if args.etapa == "datos":
        cifras = exportar_datos(args.proyecto)
        print(json.dumps(cifras, ensure_ascii=False, indent=1))
    else:
        n = construir_sitio(args.salida, args.imagenes, args.pdf_dir)
        print(f"Sitio en {args.salida}: {n} páginas con imagen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
