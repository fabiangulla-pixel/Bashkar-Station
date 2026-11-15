#!/usr/bin/env python
"""scripts/recorrido_e2e.py — El flujo principal de punta a punta, con la GUI real.

Crea un proyecto, carga un PDF, hace OCR, segmenta, corre el NER, guarda,
construye el grafo de conocimiento (sin reabrir), exporta el TEI y reabre el
proyecto. Usa la ventana real de Bashkar Station y llama a los mismos métodos
que los botones, dentro del bucle de eventos de Tk: sin clics de pantalla.
Los cuadros de diálogo se interceptan y se registran.

Uso:
    python scripts/recorrido_e2e.py --pdf ruta.pdf --trabajo carpeta [--json salida.json]

Sale con código 0 si todos los pasos cumplen su criterio y 1 si alguno falla.
Para no tocar los proyectos del usuario, conviene correrlo con USERPROFILE
apuntando a una carpeta vacía (así lo hace la CI).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import time
import traceback
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", required=True, type=Path)
    ap.add_argument("--trabajo", required=True, type=Path)
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--timeout-ocr", type=int, default=1800)
    args = ap.parse_args()
    trabajo = args.trabajo.resolve()
    trabajo.mkdir(parents=True, exist_ok=True)

    import os
    os.chdir(RAIZ)
    from tkinter import filedialog, messagebox

    t0 = time.time()
    pasos: dict = {}
    dialogos: list = []

    def log(m):
        print(f"[{time.time() - t0:7.1f}s] {m}", flush=True)

    for n in ("showinfo", "showwarning", "showerror"):
        setattr(messagebox, n, (lambda n: lambda t="", m="", *a, **k:
                                dialogos.append([n, t, str(m)[:300]]))(n))
    messagebox.askyesno = lambda *a, **k: True
    tei = trabajo / "corpus_tei.xml"
    filedialog.asksaveasfilename = lambda *a, **k: str(tei)

    import app as appmod
    appmod.BashkarApp._cargar_ultimo_proyecto = lambda self: None
    ST = appmod.ST
    a = appmod.BashkarApp()

    def anotar(nombre, ok, **datos):
        pasos[nombre] = {"ok": bool(ok), **datos}
        log(f"{nombre}: {'OK' if ok else 'FALLA'} {datos}")

    def recorrido():
        import tkinter as tk
        try:
            # Crear proyecto con el diálogo y el botón reales
            antes = set(a.winfo_children())
            a._nuevo_proyecto_dialogo()
            a.update()
            dlg = [w for w in a.winfo_children()
                   if w not in antes and isinstance(w, tk.Toplevel)][-1]

            def todos(w):
                for c in w.winfo_children():
                    yield c
                    yield from todos(c)
            ents = [w for w in todos(dlg) if isinstance(w, tk.Entry)]
            for e, v in zip(ents, ("Recorrido E2E", "Estampa", "1939")):
                e.delete(0, "end")
                e.insert(0, v)
            [w for w in todos(dlg) if w.winfo_class() in ("TButton", "Button")
             and "Crear" in str(w.cget("text"))][0].invoke()
            anotar("crear_proyecto", bool(a._proyecto_ruta), ruta=str(a._proyecto_ruta))

            # Configurar y cargar el PDF
            ent = trabajo / "entrada"
            ent.mkdir(exist_ok=True)
            shutil.copy2(args.pdf, ent / args.pdf.name)
            a._mostrar_pagina("cfg")
            a._var_tipo.set("pdf")
            a._var_ent.set(str(ent))
            a._var_sal.set(str(trabajo / "salida"))
            a._poblar_lista(ent)
            a._lb.select_set(0, "end")
            a._confirmar_cfg()
            anotar("configurar", ST.pdf_dir is not None, archivos=len(ST.archivos_sel or []))

            a._mostrar_pagina("ocr")
            a._start_ocr()
            yield lambda: ST.ocr_done and str(a._btn_ocr.cget("state")) != "disabled", \
                args.timeout_ocr
            n = 0 if ST.corpus_meta is None else len(ST.corpus_meta)
            anotar("ocr", n > 0, paginas=n,
                   palabras=int(ST.corpus_meta["palabras"].sum()) if n else 0)

            a._start_seg()
            yield lambda: ST.seg_done and str(a._btn_seg.cget("state")) != "disabled", 900
            n_art = len(ST.df_articulos) if ST.df_articulos is not None else 0
            anotar("segmentar", n_art > 0, unidades=n_art)

            a._ner_corpus_completo()
            yield lambda: str(a._btn_ner_corpus.cget("state")) != "disabled", 1800
            idx = ST.indice_ner_global or {}
            unicas = sum(len(v) for v in idx.values() if isinstance(v, dict))
            anotar("ner", unicas > 0, entidades=unicas, motor=getattr(ST, "ner_motor", ""))

            a._guardar_proyecto()
            con = sqlite3.connect(ST.ruta_db)
            en_db = con.execute("SELECT COUNT(DISTINCT categoria || '|' || texto) "
                                "FROM entidades WHERE fuente='ner_engine'").fetchone()[0]
            con.close()
            anotar("guardar", en_db == unicas, entidades_en_base=en_db)

            # Grafo SIN reabrir (fallo 4 del diagnóstico)
            a._can_fundir()
            yield lambda: str(a._btn_can_fundir.cget("state")) != "disabled", 900
            a._can_generar_menciones()
            yield lambda: False, 10
            con = sqlite3.connect(ST.ruta_db)
            canon = con.execute("SELECT COUNT(*) FROM entidades_canonicas").fetchone()[0]
            rel = con.execute("SELECT COUNT(*) FROM relaciones").fetchone()[0]
            con.close()
            bloqueo = [d for d in dialogos if "Sin proyecto" in d[1]]
            anotar("grafo", canon > 0 and not bloqueo, canonicas=canon, relaciones=rel)

            a._res_exportar_tei()
            from core.tei_engine import contar_entidades_en_tei, validar_tei
            errores = validar_tei(tei, entidades_esperadas=unicas) if tei.exists() else ["sin TEI"]
            anotar("tei", tei.exists() and not errores,
                   entidades=contar_entidades_en_tei(tei) if tei.exists() else 0,
                   errores=errores)

            from core.estado import Estado
            from core.project_manager import cargar_proyecto
            st2 = Estado()
            cargar_proyecto(a._proyecto_ruta, st2)
            u2 = sum(len(v) for v in (st2.indice_ner_global or {}).values()
                     if isinstance(v, dict))
            anotar("reabrir", u2 == unicas and len(st2.corpus_meta) == n,
                   paginas=len(st2.corpus_meta), entidades=u2)
        except Exception:
            pasos["excepcion"] = {"ok": False, "traza": traceback.format_exc()}
            log(pasos["excepcion"]["traza"])

    gen = recorrido()
    espera = {"cond": None, "fin": 0.0}

    def tick():
        if espera["cond"] is not None:
            try:
                listo = espera["cond"]()
            except Exception:
                listo = False
            if not listo and time.time() < espera["fin"]:
                a.after(200, tick)
                return
        try:
            espera["cond"], t = next(gen)
            espera["fin"] = time.time() + t
            a.after(200, tick)
        except StopIteration:
            a.after(300, a.quit)

    a.after(800, tick)
    a.mainloop()
    try:
        a.destroy()
    except Exception:
        pass

    ok = bool(pasos) and all(p.get("ok") for p in pasos.values())
    resultado = {"ok": ok, "segundos": round(time.time() - t0), "pasos": pasos,
                 "dialogos": dialogos}
    if args.json:
        args.json.write_text(json.dumps(resultado, ensure_ascii=False, indent=1,
                                        default=str), encoding="utf-8")
    log("RESULTADO: " + ("todos los pasos OK" if ok else "hay pasos que fallan"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
