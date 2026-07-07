# -*- coding: utf-8 -*-
"""Parte 2 (a prueba de cuelgues): tiempos fijos, sin esperas indefinidas."""
import sqlite3
import time
import traceback
from pathlib import Path

OUT = Path(r"C:/Users/Lenovo/Desktop/Bashkar_Capturas_Postulacion")
DB  = Path(r"I:/Mi unidad/00_Programas y macros/Bashkar Station/bashkar_station/Proyecto_04_Mar_2026.db")
N_TEXTOS = 25


def _capturar_ventana(hwnd, ruta):
    from ctypes import windll

    import win32gui
    import win32ui
    from PIL import Image
    r = win32gui.GetClientRect(hwnd)
    w, h = r[2]-r[0], r[3]-r[1]
    if w <= 0 or h <= 0: return None
    hdc = win32gui.GetWindowDC(hwnd); mfc = win32ui.CreateDCFromHandle(hdc)
    sdc = mfc.CreateCompatibleDC(); bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfc, w, h); sdc.SelectObject(bmp)
    windll.user32.PrintWindow(hwnd, sdc.GetSafeHdc(), 2)
    info = bmp.GetInfo(); bits = bmp.GetBitmapBits(True)
    img = Image.frombuffer("RGB", (info["bmWidth"], info["bmHeight"]), bits, "raw", "BGRX", 0, 1)
    win32gui.DeleteObject(bmp.GetHandle()); sdc.DeleteDC(); mfc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hdc); img.save(ruta); return img.size


def cargar_corpus(st):
    import pandas as pd
    con = sqlite3.connect(str(DB)); con.row_factory = sqlite3.Row; cur = con.cursor()
    cur.execute("SELECT texto_limpio, texto_crudo FROM ocr "
                "WHERE COALESCE(texto_limpio,texto_crudo) IS NOT NULL "
                "AND LENGTH(COALESCE(texto_limpio,texto_crudo))>120 LIMIT ?", (N_TEXTOS,))
    textos = [(r["texto_limpio"] or r["texto_crudo"]).strip() for r in cur.fetchall()]
    con.close()
    st.corpus_txt = textos
    st.df_articulos = pd.DataFrame({"id":[f"doc_{i+1:04d}" for i in range(len(textos))],
        "titulo":[f"Estampa 1939 — art. {i+1}" for i in range(len(textos))], "texto":textos})
    return len(textos)


def main():
    import app as appmod
    log = []
    a = appmod.BashkarApp()
    a.report_callback_exception = lambda e, v, t: log.append(f"[TK-EXC] {e.__name__}: {v}")
    import tkinter.messagebox as mb
    for fn in ("showinfo","showwarning","showerror","askyesno","askokcancel","askquestion"):
        setattr(mb, fn, lambda *a_, **k_: True)

    def bombear(seg):
        t0 = time.time()
        while time.time()-t0 < seg:
            a.update_idletasks(); a.update(); time.sleep(0.05)

    def captura(fname, desc):
        bombear(0.4)
        try:
            import win32gui
            hwnd = a.winfo_id(); p = win32gui.GetParent(hwnd)
            while p: hwnd, p = p, win32gui.GetParent(p)
            size = _capturar_ventana(hwnd, str(OUT / f"{fname}.png"))
            log.append(f"[OK] {fname:24s} {desc} {size}")
        except Exception as e:
            log.append(f"[ERR] {fname}: {e}")

    def call(m, *args):
        fn = getattr(a, m, None)
        if not fn: log.append(f"[WARN] sin {m}"); return
        try: fn(*args)
        except Exception as e: log.append(f"[WARN] {m}: {e}")

    def ir(pid):
        call("_mostrar_pagina", pid); bombear(0.8)

    try: a.state("zoomed")
    except Exception: pass
    bombear(3.0)
    from app import ST
    ST.publicacion, ST.periodo = "Estampa", "1939"; ST.ruta_db = str(DB)
    n = cargar_corpus(ST); log.append(f"[corpus] {n} textos")
    try: a._lbl_proyecto.config(text="Estampa 1939 — Instituto Caro y Cuervo")
    except Exception: pass
    bombear(0.5)

    # ENCUADRE (pestaña 6) — frame_engine es léxico, rápido
    ir("ling")
    call("_ir_a_ling_pestania", 6); bombear(0.5)
    call("_ling_frames"); bombear(8.0)            # tiempo fijo, no espera de botón
    call("_ir_a_ling_pestania", 6); bombear(0.6)
    captura("14_flujo_encuadre", "Encuadre / framing")

    # POLARIDAD (pestaña 7)
    call("_ir_a_ling_pestania", 7); bombear(0.5)
    call("_ling_polaridad"); bombear(8.0)
    call("_ir_a_ling_pestania", 7); bombear(0.6)
    captura("15_flujo_polaridad", "Polaridad / sentimiento")

    # NUBE DE PALABRAS
    ir("viz")
    call("_viz_nube"); bombear(16.0)
    captura("16_flujo_nube", "Nube de palabras")

    # RESULTADOS
    ir("res"); captura("17_flujo_resultados", "Resultados y exportación")

    # DASHBOARD
    ir("dash"); call("_dash_actualizar"); bombear(4.0)
    captura("18_flujo_dashboard", "Dashboard ejecutivo")

    print("===LOG==="); print("\n".join(log)); print(f"Capturas en: {OUT}")
    try: a.destroy()
    except Exception: pass


if __name__ == "__main__":
    try: main()
    except Exception: traceback.print_exc()
