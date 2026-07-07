# -*- coding: utf-8 -*-
"""Recorrido de USUARIO REAL sobre Bashkar Station para la postulación.

Carga el proyecto real (corpus Estampa 1939, Instituto Caro y Cuervo), reconstruye
el corpus de texto desde la base SQLite y ejecuta el flujo de trabajo paso a paso
—igual que lo haría un investigador pulsando los botones— capturando cada panel
CON RESULTADOS reales:

  1. Configuración del corpus (proyecto cargado)
  2. Entidades  -> "Analizar corpus completo" (NER spaCy)
  3. Redes      -> fundir entidades canónicas + construir grafo
  4. Lingüística-> encuadre + polaridad
  5. Visualizar -> nube de palabras
  6. Resultados / Dashboard

Las capturas se guardan en
C:/Users/Lenovo/Desktop/Bashkar_Capturas_Postulacion/.

Uso:  python _recorrido_usuario.py
"""
import sqlite3
import time
import traceback
from pathlib import Path

OUT = Path(r"C:/Users/Lenovo/Desktop/Bashkar_Capturas_Postulacion")
OUT.mkdir(parents=True, exist_ok=True)

DB = Path(r"I:/Mi unidad/00_Programas y macros/Bashkar Station/bashkar_station/Proyecto_04_Mar_2026.db")

# Cuántos textos cargar al corpus (muestra para que el NER no tarde de más).
N_TEXTOS = 24


def _capturar_ventana(hwnd, ruta):
    """Captura el contenido de una ventana con PrintWindow (aunque esté tapada)."""
    from ctypes import windll

    import win32gui
    import win32ui
    from PIL import Image
    rect = win32gui.GetClientRect(hwnd)
    w, h = rect[2] - rect[0], rect[3] - rect[1]
    if w <= 0 or h <= 0:
        return None
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfc_dc, w, h)
    save_dc.SelectObject(bmp)
    # PW_RENDERFULLCONTENT = 2 (captura contenido aunque la ventana esté detrás)
    windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)
    info = bmp.GetInfo()
    bits = bmp.GetBitmapBits(True)
    img = Image.frombuffer("RGB", (info["bmWidth"], info["bmHeight"]),
                           bits, "raw", "BGRX", 0, 1)
    win32gui.DeleteObject(bmp.GetHandle())
    save_dc.DeleteDC(); mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)
    img.save(ruta)
    return img.size


def cargar_corpus_desde_db(st):
    """Reconstruye ST.corpus_txt y un df_articulos mínimo desde la tabla ocr."""
    import pandas as pd
    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(
        "SELECT texto_limpio, texto_crudo FROM ocr "
        "WHERE COALESCE(texto_limpio, texto_crudo) IS NOT NULL "
        "  AND LENGTH(COALESCE(texto_limpio, texto_crudo)) > 120 "
        "LIMIT ?", (N_TEXTOS,))
    textos = []
    for r in cur.fetchall():
        t = (r["texto_limpio"] or r["texto_crudo"] or "").strip()
        if t:
            textos.append(t)
    con.close()
    st.corpus_txt = textos
    # df_articulos mínimo con columna 'texto' para el NER de corpus
    st.df_articulos = pd.DataFrame({
        "id":     [f"doc_{i+1:04d}" for i in range(len(textos))],
        "titulo": [f"Estampa 1939 — art. {i+1}" for i in range(len(textos))],
        "texto":  textos,
    })
    return len(textos)


def main():

    import app as appmod

    log = []
    a = appmod.BashkarApp()

    # Silenciar excepciones de tkinter (workers que mueren al cerrar, popups de Ollama)
    a.report_callback_exception = lambda exc, val, tb: log.append(f"[TK-EXC] {exc.__name__}: {val}")

    # Anular diálogos modales que bloquearían el recorrido headless
    import tkinter.messagebox as mb
    for fn in ("showinfo", "showwarning", "showerror", "askyesno", "askokcancel"):
        setattr(mb, fn, lambda *a_, **k_: log.append(f"[modal-suprimido] {a_[:1]}") or True)

    def bombear(seg):
        """Procesa eventos tkinter durante 'seg' segundos sin bloquear el loop."""
        t0 = time.time()
        while time.time() - t0 < seg:
            a.update_idletasks(); a.update(); time.sleep(0.05)

    def al_frente():
        try:
            a.deiconify(); a.lift(); a.attributes("-topmost", True); a.focus_force()
            a.update_idletasks(); a.update()
        except Exception as e:
            log.append(f"[WARN] al_frente: {e}")

    def captura(fname, desc):
        bombear(0.4)
        try:
            hwnd = a.winfo_id()
            # subir al toplevel real (winfo_id da el frame interno)
            import win32gui
            parent = win32gui.GetParent(hwnd)
            while parent:
                hwnd, parent = parent, win32gui.GetParent(parent)
            size = _capturar_ventana(hwnd, str(OUT / f"{fname}.png"))
            if size:
                log.append(f"[OK]  {fname:24s} {desc}  {size}")
            else:
                log.append(f"[ERR] {fname}: ventana sin tamaño")
        except Exception as e:
            log.append(f"[ERR] {fname}: {e}")

    def esperar_boton(attr, timeout=240):
        """Espera a que un ttk.Button vuelva a 'normal' (worker terminado)."""
        btn = getattr(a, attr, None)
        if btn is None:
            log.append(f"[WARN] sin botón {attr}"); bombear(2); return
        t0 = time.time()
        while time.time() - t0 < timeout:
            bombear(0.3)
            try:
                if str(btn["state"]) == "normal":
                    bombear(0.6); return
            except Exception:
                return
        log.append(f"[TIMEOUT] {attr} tras {timeout}s")

    def ir(pid):
        try:
            a._mostrar_pagina(pid)
        except Exception as e:
            log.append(f"[WARN] _mostrar_pagina({pid}): {e}")
        bombear(0.8)

    # ── Arranque ──────────────────────────────────────────────────────────────
    try:
        a.state("zoomed")
    except Exception:
        pass
    bombear(0.5)

    # Dejar que el autocargado intente correr (creará proyecto vacío) y luego
    # SOBRESCRIBIMOS con el corpus real desde la DB.
    bombear(3.0)

    from app import ST
    ST.publicacion = "Estampa"
    ST.periodo     = "1939"
    try:
        a._lbl_proyecto.config(text="Estampa 1939 — Instituto Caro y Cuervo")
    except Exception:
        pass

    n = cargar_corpus_desde_db(ST)
    ST.ruta_db = str(DB)
    log.append(f"[corpus] {n} textos cargados desde la base de datos real")
    a._sincronizar_ui_con_st() if hasattr(a, "_sincronizar_ui_con_st") else None
    bombear(1.0)

    # 1) CONFIGURACIÓN ----------------------------------------------------------
    ir("cfg");   captura("11_flujo_configuracion", "Paso 1: corpus Estampa configurado")

    # 2) ENTIDADES (NER) --------------------------------------------------------
    ir("ner")
    log.append("[accion] Entidades: pulsar 'Analizar corpus completo'")
    # Acelerar: motor spaCy 'sm', sin IA, umbral de longitud bajo
    try:
        a._var_ner_llm.set(False)
    except Exception:
        pass
    try:
        import spacy as _sp
        _nlp_sm = _sp.load("es_core_news_sm")
        _orig_load = _sp.load
        _sp.load = lambda name, *a_, **k_: _nlp_sm  # el worker carga 'sm' al instante
        log.append("[ner] motor acelerado: es_core_news_sm")
    except Exception as e:
        log.append(f"[WARN] acelerar NER: {e}")
    try:
        a._ner_corpus_completo()
    except Exception as e:
        log.append(f"[ERR] _ner_corpus_completo: {e}")
    esperar_boton("_btn_ner_corpus", timeout=300)
    try:
        a._ner_refrescar_tv()
    except Exception:
        pass
    bombear(0.5)
    captura("12_flujo_entidades", "Paso 2: índice NER poblado")

    # 3) REDES: fundir entidades canónicas + grafo ------------------------------
    ir("red")
    log.append("[accion] Redes: fundir entidades canónicas")
    for m in ("_can_fundir", "_can_generar_menciones"):
        if hasattr(a, m):
            try:
                getattr(a, m)(); bombear(2.0)
            except Exception as e:
                log.append(f"[WARN] {m}: {e}")
    if hasattr(a, "_red_construir"):
        try:
            a._red_construir()
        except Exception as e:
            log.append(f"[WARN] _red_construir: {e}")
    bombear(5.0)
    captura("13_flujo_redes", "Paso 3: grafo de entidades / redes")

    # 4) LINGÜÍSTICA: encuadre + polaridad --------------------------------------
    ir("ling")
    log.append("[accion] Lingüística: análisis de encuadre")
    if hasattr(a, "_ling_frames"):
        try:
            a._ling_frames(); esperar_boton("_btn_ling_frame", timeout=180)
        except Exception as e:
            log.append(f"[WARN] _ling_frames: {e}")
    captura("14_flujo_encuadre", "Paso 4a: análisis de encuadre")
    if hasattr(a, "_ir_a_ling_pestania"):
        try:
            a._ir_a_ling_pestania(7); bombear(0.6)   # pestaña Polaridad
        except Exception:
            pass
    if hasattr(a, "_ling_polaridad"):
        try:
            a._ling_polaridad(); esperar_boton("_btn_ling_pol", timeout=180)
        except Exception as e:
            log.append(f"[WARN] _ling_polaridad: {e}")
    captura("15_flujo_polaridad", "Paso 4b: polaridad / sentimiento")

    # 5) VISUALIZAR: nube de palabras -------------------------------------------
    ir("viz")
    log.append("[accion] Visualizar: nube de palabras")
    if hasattr(a, "_viz_nube"):
        try:
            a._viz_nube(); bombear(10.0)
        except Exception as e:
            log.append(f"[WARN] _viz_nube: {e}")
    bombear(2.0)
    captura("16_flujo_nube", "Paso 5: nube de palabras del corpus")

    # 6) RESULTADOS + DASHBOARD -------------------------------------------------
    ir("res");  captura("17_flujo_resultados", "Paso 6: resultados y exportación")
    ir("dash")
    if hasattr(a, "_dash_actualizar"):
        try:
            a._dash_actualizar(); bombear(3.0)
        except Exception as e:
            log.append(f"[WARN] _dash_actualizar: {e}")
    captura("18_flujo_dashboard", "Paso 6b: dashboard ejecutivo")

    print("\n".join(log))
    print(f"\nCapturas en: {OUT}")
    try:
        a.destroy()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
