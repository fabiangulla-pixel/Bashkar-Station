#!/usr/bin/env python
"""
cli.py — Bashkar Station CLI

Ejecuta el pipeline de análisis sin interfaz gráfica.
Útil para automatización, scripting y servidores sin display.

Uso básico:
    python cli.py --proyecto ruta/a/proyecto.bashkar --etapas ocr,norm,seg,anal

Uso completo:
    python cli.py \\
        --proyecto  ruta/a/proyecto.bashkar \\
        --etapas    ocr,norm,seg,anal,ner \\
        --out       ruta/a/resultados/ \\
        --verbose

Etapas disponibles:
    ocr     Extracción/OCR de texto (Tesseract)
    norm    Normalización post-OCR
    seg     Segmentación de artículos
    anal    Análisis textual (LDA, NER básico, campos semánticos)
    ner     NER híbrido (spaCy + opcionalmente Claude)
    tei     Exportar XML-TEI P5
    bibtex  Exportar BibTeX
    csv     Exportar entidades CSV

Ejemplos:
    # Solo OCR + normalización
    python cli.py --proyecto estampa.bashkar --etapas ocr,norm

    # Pipeline completo con exportación
    python cli.py --proyecto estampa.bashkar --etapas ocr,norm,seg,anal,ner,tei,csv

    # Ver qué contiene un proyecto
    python cli.py --proyecto estampa.bashkar --info
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from core import recursos

# Antes de que nada importe torch o numpy: OpenMP lee estas variables una sola
# vez, al inicializarse. Sin esto un lote por CLI deja la máquina sin CPU para
# nada más, que es justo lo contrario de lo que se espera de un modo desatendido.
recursos.aplicar_limites_cpu()

# La consola de Windows por defecto usa cp1252 (no UTF-8): imprimir ✅/⬜/⚠/─
# revienta con UnicodeEncodeError a mitad de la salida. reconfigure() no existe
# en streams ya redirigidos a un objeto que no lo soporta (algunos entornos CI),
# de ahí el guard.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _log(msg: str, verbose: bool = True):
    if verbose:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {msg}", flush=True)


def _cargar_proyecto(ruta: str) -> dict:
    """Lee el archivo .bashkar y retorna el dict de configuración."""
    p = Path(ruta)
    if not p.exists():
        print(f"ERROR: No se encontró el proyecto: {ruta}", file=sys.stderr)
        sys.exit(1)
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _info_proyecto(ruta: str):
    """Muestra información del proyecto sin ejecutar nada."""
    datos = _cargar_proyecto(ruta)
    cfg  = datos.get("config", {})
    prog = datos.get("progreso", {})
    res  = datos.get("resultados", {})

    print(f"\n{'='*60}")
    print("  Bashkar Station — Información del proyecto")
    print(f"{'='*60}")
    print(f"  Nombre:       {datos.get('nombre', '—')}")
    print(f"  Publicación:  {cfg.get('publicacion', '—')}")
    print(f"  Período:      {cfg.get('periodo', '—')}")
    print(f"  Carpeta OCR:  {cfg.get('out_dir', '—')}")
    print(f"  Archivos:     {len(cfg.get('archivos_sel', []))} seleccionados")
    print("\n  Etapas completadas:")
    for etapa, hecho in prog.items():
        estado = "✅" if hecho else "⬜"
        print(f"    {estado}  {etapa}")
    if res.get("indice_ner_global"):
        ner = res["indice_ner_global"]
        n_ents = sum(len(v) for v in ner.values() if isinstance(v, dict))
        print(f"\n  NER:          {n_ents} entidades en índice global")
    print(f"\n  Modificado:   {datos.get('modificado', '—')}")
    print(f"{'='*60}\n")


def _etapa_ocr(cfg: dict, verbose: bool):
    """Ejecuta OCR sobre los archivos del proyecto."""
    out_dir = Path(cfg.get("out_dir", ""))
    input_tipo = cfg.get("input_tipo", "carpetas")
    archivos = cfg.get("archivos_sel", [])

    if not out_dir or not archivos:
        _log("⚠ Sin archivos configurados — omitiendo OCR", verbose)
        return {}

    _log(f"OCR sobre {len(archivos)} archivo(s) en modo '{input_tipo}'", verbose)
    from core.ocr_engine import procesar_imagen, procesar_pdf

    resultados = {}
    for i, archivo in enumerate(archivos, 1):
        p = Path(archivo)
        if not p.exists():
            _log(f"  [{i}/{len(archivos)}] No encontrado: {archivo}", verbose)
            continue
        _log(f"  [{i}/{len(archivos)}] {p.name}", verbose)
        try:
            nombre = p.stem
            txt_dir = out_dir / "03_ocr" / nombre
            txt_dir.mkdir(parents=True, exist_ok=True)

            if p.suffix.lower() == ".pdf":
                textos = procesar_pdf(p, dpi=150, lang="spa")
            else:
                textos = [procesar_imagen(p, lang="spa")]

            for j, texto in enumerate(textos, 1):
                txt_path = txt_dir / f"p{j:04d}.txt"
                txt_path.write_text(texto, encoding="utf-8")

            resultados[nombre] = len(textos)
        except Exception as e:
            _log(f"    ERROR: {e}", verbose)

    _log(f"OCR completado: {sum(resultados.values())} páginas", verbose)
    return resultados


def _etapa_norm(cfg: dict, verbose: bool):
    """Normaliza los textos OCR extraídos."""
    out_dir = Path(cfg.get("out_dir", ""))
    if not out_dir.exists():
        return
    _log("Normalizando textos…", verbose)
    from core.ocr_normalizer import normalizar_texto_ocr
    count = 0
    for txt_path in sorted((out_dir / "03_ocr").rglob("*.txt")):
        try:
            texto = txt_path.read_text(encoding="utf-8", errors="replace")
            normalizado = normalizar_texto_ocr(texto)
            txt_path.write_text(normalizado, encoding="utf-8")
            count += 1
        except Exception:
            pass
    _log(f"Normalización completada: {count} archivos", verbose)


def _etapa_seg(cfg: dict, verbose: bool) -> list[dict]:
    """Segmenta artículos y retorna lista de dicts."""
    out_dir = Path(cfg.get("out_dir", ""))
    if not out_dir.exists():
        return []
    _log("Segmentando artículos…", verbose)
    try:
        from core.article_segmenter import segmentar_numero
        articulos = []
        ocr_dir = out_dir / "03_ocr"
        for num_dir in sorted(ocr_dir.iterdir()):
            if not num_dir.is_dir():
                continue
            _log(f"  Segmentando: {num_dir.name}", verbose)
            arts = segmentar_numero(ocr_dir, num_dir.name)
            articulos.extend(arts)
        _log(f"Segmentación completada: {len(articulos)} artículos", verbose)
        # Guardar CSV
        import csv
        csv_path = out_dir / "segmentacion.csv"
        if articulos:
            with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=list(articulos[0].keys()))
                w.writeheader(); w.writerows(articulos)
            _log(f"  CSV guardado: {csv_path}", verbose)
        return articulos
    except Exception as e:
        _log(f"  ERROR en segmentación: {e}", verbose)
        return []


def _etapa_ner(articulos: list[dict], verbose: bool) -> dict:
    """Ejecuta NER sobre los artículos segmentados."""
    if not articulos:
        return {}
    _log(f"NER sobre {len(articulos)} artículos…", verbose)
    try:
        import spacy
        nlp = spacy.load("es_core_news_sm")
    except Exception:
        _log("  ⚠ spaCy no disponible — omitiendo NER", verbose)
        return {}

    from core.ner_engine import (
        actualizar_indice_global,
        indice_global_vacio,
        pipeline_ner,
    )
    indice = indice_global_vacio()
    for i, art in enumerate(articulos, 1):
        if i % 20 == 0:
            _log(f"  {i}/{len(articulos)}", verbose)
        texto = art.get("texto", "") or art.get("ocr_limpio", "")
        if not texto:
            continue
        try:
            # usar_roberta=True (el default de pipeline_ner): el segfault que
            # sesión 62 le atribuyó a un conflicto de threading torch/tokenizers
            # (con recursos.aplicar_limites_cpu() activo) no era eso. Causa
            # real, confirmada en sesión 63 sobre el corpus completo (792
            # páginas): core/ner_roberta_local.py importaba `transformers`
            # (que arrastra huggingface_hub) ANTES de forzar HF_HUB_OFFLINE=1
            # — huggingface_hub congela esa variable como constante en su
            # propio import, así que fijarla después no evitaba que pipeline()
            # saliera a red aunque el modelo ya estuviera en caché. Esa
            # llamada de red era la que reventaba con access violation en
            # Windows. Arreglado en ner_roberta_local.py (offline forzado a
            # nivel de módulo, antes de cualquier import de transformers).
            ner = pipeline_ner(texto, nlp)
            actualizar_indice_global(indice, art.get("id", str(i)), ner)
        except Exception:
            pass
    n = sum(len(v) for v in indice.values() if isinstance(v, dict))
    _log(f"NER completado: {n} entidades únicas", verbose)
    return indice


def _etapa_exportar(out_dir: Path, articulos: list, indice_ner: dict,
                    etapas: list[str], cfg: dict, verbose: bool):
    """Exporta TEI, BibTeX y/o CSV según etapas solicitadas."""
    if "tei" in etapas:
        _log("Exportando XML-TEI…", verbose)
        try:
            from core.tei_engine import exportar_corpus_tei
            ruta = out_dir / "corpus.xml"
            arts_tei = [{"id": a.get("id", str(i)), "texto": a.get("texto", "")}
                        for i, a in enumerate(articulos)]
            exportar_corpus_tei(arts_tei, ruta,
                                proyecto_nombre=cfg.get("publicacion", "Corpus"),
                                fuente=f"{cfg.get('publicacion', '')} ({cfg.get('periodo', '')})")
            _log(f"  TEI: {ruta}", verbose)
        except Exception as e:
            _log(f"  ERROR TEI: {e}", verbose)

    if "bibtex" in etapas:
        _log("Exportando BibTeX…", verbose)
        try:
            from core.tei_engine import exportar_bibtex
            ruta = out_dir / "corpus.bib"
            arts_bib = [{"id": a.get("id", str(i)), "texto": a.get("texto", "")}
                        for i, a in enumerate(articulos)]
            exportar_bibtex(arts_bib, ruta)
            _log(f"  BibTeX: {ruta}", verbose)
        except Exception as e:
            _log(f"  ERROR BibTeX: {e}", verbose)

    if "csv" in etapas and indice_ner:
        _log("Exportando entidades CSV…", verbose)
        try:
            from core.ner_engine import exportar_csv
            ruta = out_dir / "entidades.csv"
            exportar_csv(indice_ner, ruta)
            _log(f"  CSV: {ruta}", verbose)
        except Exception as e:
            _log(f"  ERROR CSV: {e}", verbose)


def main():
    parser = argparse.ArgumentParser(
        description="Bashkar Station CLI — pipeline sin interfaz gráfica",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)

    parser.add_argument("--proyecto", required=False, metavar="RUTA",
                        help="Ruta al archivo .bashkar del proyecto")
    parser.add_argument("--etapas", default="ocr,norm,seg,anal",
                        metavar="ETAPAS",
                        help="Etapas a ejecutar separadas por coma (ocr,norm,seg,anal,ner,tei,bibtex,csv)")
    parser.add_argument("--out", default=None, metavar="CARPETA",
                        help="Carpeta de salida (sobreescribe la del proyecto)")
    parser.add_argument("--verbose", action="store_true",
                        help="Mostrar progreso detallado")
    parser.add_argument("--info", action="store_true",
                        help="Mostrar información del proyecto y salir")
    parser.add_argument("--version", action="store_true",
                        help="Mostrar versión de Bashkar Station y salir")

    args = parser.parse_args()

    if args.version:
        try:
            import app as _app
            print(f"Bashkar Station v{_app.APP_VERSION}")
        except Exception:
            print("Bashkar Station CLI")
        return

    if not args.proyecto:
        parser.print_help()
        return

    if args.info:
        _info_proyecto(args.proyecto)
        return

    # ── Cargar proyecto ─────────────────────────────────────────────────────
    datos = _cargar_proyecto(args.proyecto)
    cfg   = datos.get("config", {})

    if args.out:
        cfg["out_dir"] = args.out
    if not cfg.get("out_dir"):
        print("ERROR: El proyecto no tiene carpeta de salida configurada. "
              "Usa --out para especificarla.", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(cfg["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    etapas = [e.strip().lower() for e in args.etapas.split(",") if e.strip()]
    verbose = args.verbose

    _log(f"Bashkar Station CLI — proyecto: {datos.get('nombre', args.proyecto)}", verbose)
    _log(f"Etapas: {', '.join(etapas)}", verbose)
    t0 = time.time()

    articulos: list[dict] = []
    indice_ner: dict      = {}

    if "ocr" in etapas:
        _etapa_ocr(cfg, verbose)
    if "norm" in etapas:
        _etapa_norm(cfg, verbose)
    if "seg" in etapas:
        articulos = _etapa_seg(cfg, verbose)
    if "anal" in etapas:
        _log("Análisis textual (requiere artículos segmentados)…", verbose)
        # Análisis básico — LDA y campos semánticos requieren la UI completa
        # para acceso a ST; aquí solo reportamos conteo
        _log(f"  {len(articulos)} artículos disponibles para análisis", verbose)
    if "ner" in etapas:
        indice_ner = _etapa_ner(articulos, verbose)
        # Guardar índice NER en JSON para uso posterior
        ner_path = out_dir / "indice_ner.json"
        with open(ner_path, "w", encoding="utf-8") as f:
            json.dump(indice_ner, f, ensure_ascii=False, indent=2)
        _log(f"Índice NER guardado: {ner_path}", verbose)

    # Exportaciones
    if any(e in etapas for e in ("tei", "bibtex", "csv")):
        _etapa_exportar(out_dir, articulos, indice_ner, etapas, cfg, verbose)

    elapsed = time.time() - t0
    _log(f"\n✅ Pipeline completado en {elapsed:.1f}s", verbose)
    print(f"Salida: {out_dir}")


if __name__ == "__main__":
    main()
