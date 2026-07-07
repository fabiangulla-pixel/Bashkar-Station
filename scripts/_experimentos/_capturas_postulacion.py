# -*- coding: utf-8 -*-
"""Driver de captura de pantallas para la postulación a la Fiesta del Libro 2026.

Lanza BashkarApp con mainloop REAL, deja que cargue el último proyecto y captura
los paneles más representativos con PIL.ImageGrab sobre el bounding box real de la
ventana. Guarda PNGs en C:/Users/Lenovo/Desktop/Bashkar_Capturas_Postulacion/.

Uso:  python _capturas_postulacion.py
"""
import time
import traceback
from pathlib import Path

OUT = Path(r"C:/Users/Lenovo/Desktop/Bashkar_Capturas_Postulacion")
OUT.mkdir(parents=True, exist_ok=True)

# Páginas a capturar: (pid, nombre_archivo, descripción para la postulación)
PANELES = [
    ("cfg",  "01_configuracion",  "Configuración del corpus"),
    ("ocr",  "02_extraccion_ocr", "Extracción de texto por OCR"),
    ("norm", "03_normalizar",     "Normalización del texto"),
    ("seg",  "04_segmentar",      "Segmentación en artículos"),
    ("ner",  "05_entidades",      "Índice de entidades nombradas"),
    ("red",  "06_redes",          "Redes y grafo canónico"),
    ("ling", "07_linguistica",    "Lingüística computacional"),
    ("viz",  "08_visualizar",     "Visualizaciones"),
    ("res",  "09_resultados",     "Resultados y exportación"),
    ("dash", "10_dashboard",      "Dashboard ejecutivo"),
]


def main():
    from PIL import ImageGrab

    import app as appmod

    a = appmod.BashkarApp()
    a.update_idletasks()
    a.update()

    log = []
    estado = {"i": 0, "fase": "esperar_carga", "t0": time.time()}

    def traer_al_frente():
        try:
            a.deiconify()
            a.lift()
            a.attributes("-topmost", True)
            a.focus_force()
            a.update_idletasks(); a.update()
        except Exception as e:
            log.append(f"[WARN] traer_al_frente: {e}")

    def capturar(pid, fname, desc):
        try:
            a._mostrar_pagina(pid)
        except Exception as e:
            log.append(f"[WARN] _mostrar_pagina({pid}): {e}")
        # Dejar que se construya/refresque el panel
        for _ in range(8):
            a.update_idletasks(); a.update(); time.sleep(0.12)
        traer_al_frente()
        time.sleep(0.4)
        a.update_idletasks(); a.update()
        # Bounding box real de la ventana
        x = a.winfo_rootx(); y = a.winfo_rooty()
        w = a.winfo_width(); h = a.winfo_height()
        bbox = (x, y, x + w, y + h)
        try:
            img = ImageGrab.grab(bbox=bbox)
            ruta = OUT / f"{fname}.png"
            img.save(ruta)
            log.append(f"[OK]  {fname:22s} {desc}  -> {img.size}")
        except Exception as e:
            log.append(f"[ERR] {fname}: {e}")

    def paso():
        # Fase 1: esperar a que el proyecto cargue (after(200) + refrescos)
        if estado["fase"] == "esperar_carga":
            if time.time() - estado["t0"] < 4.0:
                a.after(200, paso); return
            estado["fase"] = "capturar"

        # Fase 2: capturar panel a panel
        if estado["fase"] == "capturar":
            i = estado["i"]
            if i < len(PANELES):
                pid, fname, desc = PANELES[i]
                capturar(pid, fname, desc)
                estado["i"] += 1
                a.after(250, paso); return
            estado["fase"] = "fin"

        # Fase 3: cerrar
        if estado["fase"] == "fin":
            print("\n".join(log))
            print(f"\nCapturas en: {OUT}")
            try:
                a.destroy()
            except Exception:
                pass

    # Maximizar para capturas grandes y nítidas
    try:
        a.state("zoomed")
    except Exception:
        pass
    a.after(200, paso)

    # Captura de excepciones de tkinter para no morir en silencio
    def _exc(exc, val, tb):
        log.append(f"[TK-EXC] {exc.__name__}: {val}")
    a.report_callback_exception = _exc

    try:
        a.mainloop()
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    main()
