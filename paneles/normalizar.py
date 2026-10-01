"""paneles/normalizar.py — Métodos de BashkarApp extraídos de app.py.

Mixin: BashkarApp hereda de PanelNormalizar. Los cuerpos son copia literal del
original. Importa explícitamente lo que usa; los colores del tema se
leen de gui_comun.TEMA porque cambian en caliente.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from gui_comun import (
    ST,
    TEMA,
    _autor_local,
    _registrar_error,
    _resolver_api_key_modelo,
    _simbolo_estado_norm,
)


class PanelNormalizar:
    # ══════════════════════════════════════════════════════════════════════════
    # NORMALIZAR: revisión y edición del texto OCR por bloques
    # ══════════════════════════════════════════════════════════════════════════
    def _build_norm(self):
        f = self._tab_norm
        self._page_header(f, "Normalizar texto",
                          "Revisa y edita el texto OCR antes de analizar · 4 vistas por bloque", "📝")

        # ── Barra de acciones ─────────────────────────────────────────────────
        bbar = tk.Frame(f, bg=TEMA.CONTENT_BG)
        bbar.pack(fill="x", padx=24, pady=(0, 6))

        self._norm_var_numero = tk.StringVar()
        self._norm_cb_num = ttk.Combobox(bbar, textvariable=self._norm_var_numero,
                                          width=24, state="readonly")
        self._norm_cb_num.pack(side="left", padx=(0, 8))
        self._norm_cb_num.bind("<<ComboboxSelected>>", lambda e: self._norm_cargar_numero())

        ttk.Button(bbar, text="▶  Normalizar automático", style="P.TButton",
                   command=self._norm_auto).pack(side="left", padx=(0, 8))
        ttk.Button(bbar, text="🤖  Sugerir con IA", style="S.TButton",
                   command=self._norm_ia).pack(side="left", padx=(0, 8))
        ttk.Button(bbar, text="💾  Guardar ediciones", style="S.TButton",
                   command=self._norm_guardar).pack(side="left", padx=(0, 8))

        # Re-extraer con Tesseract — rescata páginas con OCR corrupto (ej. Kraken sin RAM)
        ttk.Button(bbar, text="🔄 Re-OCR Tesseract (página)",
                   style="S.TButton",
                   command=self._norm_reocr_pagina).pack(side="left", padx=(0, 8))
        ttk.Button(bbar, text="🔄 Re-OCR Tesseract (todo)",
                   style="S.TButton",
                   command=self._norm_reocr_numero).pack(side="left", padx=(0, 8))
        ttk.Button(bbar, text="🖼 Regenerar imágenes",
                   style="S.TButton",
                   command=self._norm_regenerar_imagenes).pack(side="left", padx=(0, 8))

        ttk.Button(bbar, text="📂 Importar .txt", style="S.TButton",
                   command=self._norm_importar_txt).pack(side="left", padx=(0, 8))
        ttk.Button(bbar, text="⚙ Reconstruir columnas BNC", style="S.TButton",
                   command=self._norm_reconstruir_columnas).pack(side="left", padx=(0, 8))
        ttk.Button(bbar, text="📖 Diccionario de corpus", style="S.TButton",
                   command=self._norm_diccionario_corpus).pack(side="left", padx=(0, 8))
        ttk.Button(bbar, text="🔍 Ver cambios", style="S.TButton",
                   command=self._norm_ver_diff).pack(side="left", padx=(0, 8))
        ttk.Button(bbar, text="🏋 Dataset HTR", style="S.TButton",
                   command=self._norm_exportar_ground_truth).pack(side="left", padx=(0, 8))
        ttk.Button(bbar, text="↺  Actualizar lista", style="S.TButton",
                   command=self._norm_refrescar_numeros).pack(side="right")
        ttk.Button(bbar, text="📓 Nota", style="S.TButton",
                   command=lambda: self._bitacora_nueva_nota("norm")).pack(side="right", padx=(0, 4))

        self._lbl_norm_estado = tk.Label(bbar, text="", bg=TEMA.CONTENT_BG, fg=TEMA.VERDE,
                                          font=("Segoe UI", 9, "bold"))
        self._lbl_norm_estado.pack(side="right", padx=8)

        # ── Selector de versión para el pipeline ──────────────────────────────
        vbar = tk.Frame(f, bg="#0E1114", pady=6)
        vbar.pack(fill="x", padx=24, pady=(0, 4))

        tk.Label(vbar,
                 text="Versión que pasa al análisis:",
                 bg="#0E1114", fg=TEMA.TXT_SEC,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 12))

        self._norm_var_version = tk.StringVar(
            value=getattr(ST, "norm_version", "manual"))

        _opciones = [
            ("crudo",  "🗒 Crudo (OCR sin cambios)",
             "El texto tal como salió del OCR o del conversor.\n"
             "Para investigadores que prefieren trabajar con el\n"
             "original y aplicar sus propias transformaciones."),
            ("manual", "✏ Manual (mis ediciones)",
             "Lo que escribiste o corregiste en el panel izquierdo.\n"
             "Si no editaste una página, usa el texto crudo.\n"
             "La opción más común para trabajo de investigación."),
            ("ia",     "🤖 IA (sugerencia revisada)",
             "La versión generada por el asistente IA.\n"
             "Si no hay sugerencia para una página, cae al manual\n"
             "y luego al crudo.\n"
             "Para quienes quieren modernizar la ortografía\n"
             "o acelerar la corrección masiva."),
        ]

        for val, etiq, ayuda in _opciones:
            rb = ttk.Radiobutton(vbar, text=etiq,
                                  variable=self._norm_var_version,
                                  value=val,
                                  command=self._norm_version_cambio)
            rb.pack(side="left", padx=(0, 4))
            self._mk_ayuda_bg(vbar, ayuda, bg="#0E1114")

        self._norm_lbl_version_info = tk.Label(
            vbar, text="", bg="#0E1114", fg=TEMA.TXT_DIM,
            font=("Segoe UI", 8, "italic"))
        self._norm_lbl_version_info.pack(side="right", padx=8)

        ttk.Button(vbar, text="✔ Verificar", style="S.TButton",
                   command=self._verif_abrir).pack(side="right", padx=(0, 8))
        self._mk_ayuda_bg(vbar,
            "Verificación palabra por palabra (estilo ABBYY FineReader):\n"
            "recorre las palabras de baja confianza del OCR de esta página,\n"
            "muestra el recorte ampliado y sugerencias, y aplica la\n"
            "corrección elegida al texto manual del bloque actual.",
            bg="#0E1114")

        # ── Selector de bloque (listbox de bloques de la página) ─────────────
        mid = tk.Frame(f, bg=TEMA.CONTENT_BG)
        mid.pack(fill="both", expand=True, padx=24, pady=(0, 12))

        # Panel izquierdo: lista de páginas y bloques
        izq = tk.Frame(mid, bg=TEMA.CARD_BG, relief="solid", bd=1, width=220)
        izq.pack(side="left", fill="y", padx=(0, 8))
        izq.pack_propagate(False)

        tk.Label(izq, text="Páginas / bloques", bg=TEMA.CARD_BG, fg=TEMA.TXT_PRI,
                 font=("Segoe UI", 9, "bold")).pack(pady=(8, 0), padx=8, anchor="w")
        tk.Label(izq, text="✓ revisado  ◐ solo IA  ○ OCR sin revisar",
                 bg=TEMA.CARD_BG, fg=TEMA.TXT_SEC, font=("Segoe UI", 8)).pack(
                     pady=(0, 4), padx=8, anchor="w")

        self._norm_lb = tk.Listbox(izq, bg=TEMA.CARD_BG, fg=TEMA.TXT_SEC, selectbackground=TEMA.AB_SEL,
                                    selectforeground="#E8E5DF", relief="flat",
                                    font=("Segoe UI", 9), activestyle="none",
                                    exportselection=False)
        sb_lb = ttk.Scrollbar(izq, orient="vertical", command=self._norm_lb.yview)
        self._norm_lb.config(yscrollcommand=sb_lb.set)
        sb_lb.pack(side="right", fill="y")
        self._norm_lb.pack(fill="both", expand=True, padx=(4, 0), pady=(0, 8))
        self._norm_lb.bind("<<ListboxSelect>>", lambda e: self._norm_seleccionar_bloque())

        # Panel derecho: 4 vistas
        der = tk.Frame(mid, bg=TEMA.CONTENT_BG)
        der.pack(side="left", fill="both", expand=True)

        # Qué es el texto vigente de esta página: evidencia (OCR), corrección
        # de máquina o revisión humana. Una interfaz atractiva no debe borrar
        # esa diferencia.
        self._lbl_norm_epistemico = tk.Label(der, text="", bg=TEMA.CONTENT_BG, fg=TEMA.TXT_SEC,
                                             font=("Segoe UI", 9), anchor="w")
        self._lbl_norm_epistemico.pack(fill="x", pady=(0, 4))

        # Fila 1: imagen + OCR crudo
        fila1 = tk.Frame(der, bg=TEMA.CONTENT_BG)
        fila1.pack(fill="both", expand=True, pady=(0, 6))

        # Vista 1: imagen de la página con zoom/pan
        v1 = tk.LabelFrame(fila1, text=" 🖼  Imagen original ",
                            bg=TEMA.CARD_BG, fg=TEMA.TXT_PRI, font=("Segoe UI", 9, "bold"),
                            relief="solid", bd=1)
        v1.pack(side="left", fill="both", expand=True, padx=(0, 6))

        # Toolbar de zoom
        v1_tb = tk.Frame(v1, bg=TEMA.CARD_BG)
        v1_tb.pack(fill="x", padx=6, pady=(4, 0))
        self._norm_zoom = 1.0
        self._norm_img_orig_full = None   # PIL Image a resolución original
        self._norm_pan_start     = None

        for txt, delta in [("−", -1), ("+", 1)]:
            tk.Button(v1_tb, text=txt, bg=TEMA.CARD_BG, fg=TEMA.TXT_SEC, relief="flat",
                      font=("Segoe UI", 10, "bold"), width=2, cursor="hand2",
                      command=lambda d=delta: self._norm_zoom_step(d)
                      ).pack(side="left", padx=1)
        self._norm_lbl_zoom = tk.Label(v1_tb, text="100%", bg=TEMA.CARD_BG, fg=TEMA.TXT_DIM,
                                        font=("Segoe UI", 8))
        self._norm_lbl_zoom.pack(side="left", padx=6)
        tk.Label(v1_tb, text="Ctrl+rueda: zoom  ·  Arrastrar: pan",
                 bg=TEMA.CARD_BG, fg=TEMA.TXT_DIM, font=("Segoe UI", 7)).pack(side="right")

        # Canvas con scrollbars
        v1_wrap = tk.Frame(v1, bg="#000000")
        v1_wrap.pack(fill="both", expand=True, padx=6, pady=(2, 6))
        _sb_cx = ttk.Scrollbar(v1_wrap, orient="horizontal")
        _sb_cy = ttk.Scrollbar(v1_wrap, orient="vertical")
        self._norm_canvas_img = tk.Canvas(v1_wrap, bg="#000000", width=300, height=180,
                                           highlightthickness=0,
                                           xscrollcommand=_sb_cx.set,
                                           yscrollcommand=_sb_cy.set)
        _sb_cx.config(command=self._norm_canvas_img.xview)
        _sb_cy.config(command=self._norm_canvas_img.yview)
        _sb_cy.pack(side="right",  fill="y")
        _sb_cx.pack(side="bottom", fill="x")
        self._norm_canvas_img.pack(fill="both", expand=True)

        # Bindings zoom y pan
        self._norm_canvas_img.bind("<Control-MouseWheel>", self._norm_on_zoom)
        self._norm_canvas_img.bind("<ButtonPress-1>",      self._norm_pan_start_cb)
        self._norm_canvas_img.bind("<B1-Motion>",          self._norm_pan_drag_cb)
        self._norm_canvas_img.bind("<ButtonRelease-1>",    self._norm_pan_end_cb)

        # Vista 2: OCR crudo (solo lectura)
        v2 = tk.LabelFrame(fila1, text=" 📄  OCR crudo (solo lectura) ",
                            bg=TEMA.CARD_BG, fg=TEMA.TXT_PRI, font=("Segoe UI", 9, "bold"),
                            relief="solid", bd=1)
        v2.pack(side="left", fill="both", expand=True)
        self._norm_txt_ocr = scrolledtext.ScrolledText(
            v2, bg="#0E1114", fg="#777F84", insertbackground="#E8E5DF",
            font=("Courier New", 9), relief="flat", wrap="word", state="disabled")
        self._norm_txt_ocr.pack(fill="both", expand=True, padx=6, pady=6)

        # Fila 2: normalizado usuario + normalizado IA
        fila2 = tk.Frame(der, bg=TEMA.CONTENT_BG)
        fila2.pack(fill="both", expand=True)

        # Vista 3: edición manual del usuario
        v3 = tk.LabelFrame(fila2, text=" ✏️  Normalizado por usuario ",
                            bg=TEMA.CARD_BG, fg=TEMA.TXT_PRI, font=("Segoe UI", 9, "bold"),
                            relief="solid", bd=1)
        v3.pack(side="left", fill="both", expand=True, padx=(0, 6))

        # Barra de herramientas del panel de usuario (dictado)
        v3_bar = tk.Frame(v3, bg=TEMA.CARD_BG)
        v3_bar.pack(fill="x", padx=6, pady=(4, 0))
        self._btn_dictar = ttk.Button(v3_bar, text="🎙 Dictar",
                                       style="S.TButton",
                                       command=self._norm_dictar_toggle)
        self._btn_dictar.pack(side="left")
        self._lbl_dictar_estado = tk.Label(v3_bar, text="", bg=TEMA.CARD_BG,
                                            fg=TEMA.TXT_DIM, font=("Segoe UI", 8))
        self._lbl_dictar_estado.pack(side="left", padx=(8, 0))
        self._dictar_session = None   # DictadoSession activa o None

        self._norm_txt_usuario = scrolledtext.ScrolledText(
            v3, bg="#171C20", fg="#E8E5DF", insertbackground="#E8E5DF",
            font=("Courier New", 9), relief="flat", wrap="word")
        self._norm_txt_usuario.pack(fill="both", expand=True, padx=6, pady=6)

        # Vista 4: sugerencia de IA (revisable)
        v4 = tk.LabelFrame(fila2, text=" 🤖  Normalizado por IA (revisable) ",
                            bg=TEMA.CARD_BG, fg=TEMA.TXT_PRI, font=("Segoe UI", 9, "bold"),
                            relief="solid", bd=1)
        v4.pack(side="left", fill="both", expand=True)
        self._norm_txt_ia = scrolledtext.ScrolledText(
            v4, bg="#171C20", fg="#E8E5DF", insertbackground="#E8E5DF",
            font=("Courier New", 9), relief="flat", wrap="word")
        self._norm_txt_ia.pack(fill="both", expand=True, padx=6, pady=6)

        # Estado interno del panel
        self._norm_bloques: list[dict] = []   # [{pagina, bloque_idx, ocr_crudo, norm_usuario, norm_ia}]
        self._norm_idx_actual: int = -1

    def _norm_refrescar_numeros(self):
        if not ST.out_dir:
            return
        txt_base = Path(ST.out_dir) / "03_ocr"
        if not txt_base.exists():
            return
        nums = sorted(p.name for p in txt_base.iterdir()
                      if p.is_dir() and list(p.glob("*.txt")))
        if not nums:
            return
        self._norm_cb_num["values"] = nums
        # Conservar selección actual si sigue siendo válida; si no, tomar el primero
        actual = self._norm_var_numero.get()
        if actual not in nums:
            actual = nums[0]
        self._norm_var_numero.set(actual)
        # Siempre recargar — puede haber archivos nuevos tras el OCR
        self._norm_cargar_numero()

    def _norm_cargar_numero(self):
        """Carga todas las páginas del número seleccionado."""
        num = self._norm_var_numero.get()
        if not num or not ST.out_dir:
            self._lbl_norm_estado.config(
                text="⚠ Sin proyecto abierto o sin OCR ejecutado")
            return
        txt_dir = Path(ST.out_dir) / "03_ocr" / num
        if not txt_dir.exists():
            self._lbl_norm_estado.config(
                text=f"⚠ Carpeta no encontrada: {txt_dir}")
            return
        db_path = Path(ST.ruta_db) if ST.ruta_db else None

        archivos = sorted(txt_dir.glob("*.txt"))
        if not archivos:
            self._lbl_norm_estado.config(
                text=f"⚠ Sin archivos .txt en {txt_dir}")
            return

        bloques = []
        for txt_path in archivos:
            pagina = txt_path.stem
            try:
                ocr_crudo = txt_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                ocr_crudo = ""
            norm_usuario, norm_ia, crudo_db = self._norm_leer_db(db_path, num, pagina)
            bloques.append({
                "numero":       num,
                "pagina":       pagina,
                # El .txt ya contiene el texto final tras el primer guardado:
                # el OCR original vive en SQLite y manda sobre el archivo.
                "ocr_crudo":    crudo_db or ocr_crudo,
                "norm_usuario": norm_usuario or "",
                "norm_ia":      norm_ia or "",
                "txt_path":     str(txt_path),
            })

        self._norm_bloques = bloques
        self._norm_lb.delete(0, "end")
        avisos_ocr = getattr(self, "_avisos_ocr", {})
        for b in bloques:
            estado = _simbolo_estado_norm(b)
            alerta = " ⚠" if (b["numero"], b["pagina"]) in avisos_ocr else ""
            self._norm_lb.insert("end", f"{estado} {b['pagina']}{alerta}")

        self._lbl_norm_estado.config(
            text=f"{len(bloques)} páginas cargadas — {num}")

        if bloques:
            self._norm_lb.selection_set(0)
            self._norm_idx_actual = 0
            self._norm_mostrar_bloque(0)

    def _norm_seleccionar_bloque(self):
        sel = self._norm_lb.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self._norm_bloques):
            self._norm_guardar_bloque_actual()
            self._norm_idx_actual = idx
            self._norm_mostrar_bloque(idx)

    def _norm_mostrar_bloque(self, idx: int):
        if idx < 0 or idx >= len(self._norm_bloques):
            return
        b = self._norm_bloques[idx]

        # Vista OCR crudo (solo lectura)
        self._norm_txt_ocr.config(state="normal")
        self._norm_txt_ocr.delete("1.0", "end")
        self._norm_txt_ocr.insert("1.0", b["ocr_crudo"])
        self._norm_txt_ocr.config(state="disabled")

        # Vista usuario — vacía si no hay edición manual previa (no rellenar con basura OCR)
        self._norm_txt_usuario.delete("1.0", "end")
        if b["norm_usuario"]:
            self._norm_txt_usuario.insert("1.0", b["norm_usuario"])

        # Vista IA
        self._norm_txt_ia.delete("1.0", "end")
        self._norm_txt_ia.insert("1.0", b["norm_ia"])

        self._norm_actualizar_epistemico(b)

        # Imagen del bloque
        self._norm_mostrar_imagen(b)

    def _norm_actualizar_epistemico(self, b: dict):
        """Muestra el estado de la página y quién tocó cada capa, y cuándo."""
        lbl = getattr(self, "_lbl_norm_epistemico", None)
        if lbl is None:
            return
        from datos import normalizaciones as NZ
        texto = NZ.ETIQUETAS_ESTADO[NZ.estado_epistemico(b)]
        try:
            fila = NZ.leer(Path(ST.ruta_db), b["numero"], b["pagina"]) if ST.ruta_db else None
        except Exception:
            fila = None
        if fila:
            if fila.get("ts_usuario") and (fila.get("norm_usuario") or "").strip():
                texto += f"  ·  revisión: {fila.get('autor_usuario') or '?'}, {fila['ts_usuario']}"
            if fila.get("ts_ia") and (fila.get("norm_ia") or "").strip():
                texto += f"  ·  IA: {fila.get('autor_ia') or '?'}, {fila['ts_ia']}"
        lbl.config(text=texto)

    def _norm_mostrar_imagen(self, bloque: dict):
        """Muestra la imagen de la página SIN bloquear la ventana.

        Antes, todo esto (recorrer carpetas, abrir el PDF, renderizar con
        PyMuPDF, decodificar y redimensionar con LANCZOS) corría en el hilo
        principal en CADA cambio de página: era la causa principal de que la
        aplicación se congelara al trabajar. Ahora el trabajo pesado va a un
        hilo y solo vuelve al principal la parte que obliga Tk (crear el
        PhotoImage y pintar el canvas).
        """
        self._norm_canvas_img.delete("all")
        self._norm_canvas_img.create_text(
            150, 90, text="Cargando imagen…", fill="#646D72",
            font=("Segoe UI", 9), anchor="center")

        # Token: si el usuario cambia de página antes de que termine el render,
        # la respuesta vieja se descarta en vez de pintar la página equivocada.
        self._norm_img_token = getattr(self, "_norm_img_token", 0) + 1
        token = self._norm_img_token

        def _trabajo():
            try:
                img = self._norm_render_pagina(bloque)
                error = None
            except Exception as e:          # noqa: BLE001 — se reporta en la UI
                img, error = None, e
            self.after(0, lambda: self._norm_pintar_imagen(img, error, token))

        threading.Thread(target=_trabajo, daemon=True).start()

    def _norm_render_pagina(self, bloque: dict):
        """Devuelve la imagen PIL de la página. Puro: NO toca Tk, corre en hilo.

        Cachea el render del PDF en disco local (`core.local_cache`) porque el
        proyecto suele vivir en Google Drive y volver a renderizar la misma
        página en cada visita es lo que hacía lenta la navegación.
        """
        from PIL import Image
        numero  = bloque["numero"]
        pagina  = bloque["pagina"]
        img_pil = None

        # 1. Buscar en 02_imagenes/ (originales a color, cualquier extensión)
        if ST.out_dir:
            img_dir = Path(ST.out_dir) / "02_imagenes" / numero
            for ext in ("*.png", "*.jpg", "*.tif", "*.tiff"):
                hits = sorted(img_dir.glob(f"*{pagina}*{ext[1:]}")) if img_dir.exists() else []
                if not hits:
                    hits = sorted(img_dir.glob(ext)) if img_dir.exists() else []
                if hits:
                    img_pil = Image.open(hits[0]).convert("RGB")
                    break

        # 2. Renderizar directamente desde el PDF (sin necesitar imágenes extraídas)
        if img_pil is None:
            import re as _re
            m_pag = _re.search(r'\d+', pagina)
            n_pag = max(0, int(m_pag.group()) - 1) if m_pag else 0

            # Candidatos: 01_pdfs/, archivos_sel, pdf_dir de entrada, carpeta entrada conversor
            candidatos_pdf: list[Path] = []
            if ST.out_dir:
                pdf_dir = Path(ST.out_dir) / "01_pdfs"
                if pdf_dir.exists():
                    candidatos_pdf += list(pdf_dir.glob(f"{numero}*.pdf"))
            candidatos_pdf += [p for p in getattr(ST, "archivos_sel", [])
                               if hasattr(p, "suffix") and p.suffix.lower() == ".pdf"]
            # Buscar en pdf_dir de entrada (lo que usó el conversor)
            if ST.pdf_dir and Path(ST.pdf_dir).exists():
                candidatos_pdf += list(Path(ST.pdf_dir).glob("*.pdf"))
            # Filtrar: preferir el que tenga el número en el stem
            exactos = [p for p in candidatos_pdf if numero in p.stem]
            pdfs = exactos or candidatos_pdf

            for pdf_path in pdfs:
                try:
                    import io

                    import fitz

                    from core.local_cache import clave_cache, ruta_cache
                    cache_png = (ruta_cache("norm_paginas")
                                 / f"{clave_cache(Path(pdf_path))}_{n_pag}_120.png")
                    if cache_png.exists():
                        img_pil = Image.open(cache_png).convert("RGB")
                        break

                    doc = fitz.open(str(pdf_path))
                    if n_pag < doc.page_count:
                        pix = doc[n_pag].get_pixmap(dpi=120)
                        datos = pix.tobytes("png")
                        img_pil = Image.open(io.BytesIO(datos)).convert("RGB")
                        try:
                            cache_png.write_bytes(datos)
                        except OSError:
                            pass   # la caché es un lujo, no una condición
                    doc.close()
                    if img_pil:
                        break
                except Exception:
                    continue

        return img_pil

    def _norm_pintar_imagen(self, img_pil, error, token: int):
        """Pinta en el canvas la imagen que preparó el hilo. Solo hilo principal."""
        if token != getattr(self, "_norm_img_token", 0):
            return                      # el usuario ya cambió de página
        from PIL import Image, ImageTk
        self._norm_canvas_img.delete("all")

        if error is not None:
            self._norm_canvas_img.create_text(
                150, 90, text=f"Error: {error}",
                fill="#D96B6B", font=("Segoe UI", 8), anchor="center")
            return

        if img_pil is None:
            self._norm_canvas_img.create_text(
                150, 90,
                text="Sin imagen\n(configura la carpeta de entrada en Configuración)",
                fill="#646D72", font=("Segoe UI", 9), anchor="center")
            return

        try:
            # Guardar original completa para zoom y resetear nivel
            self._norm_img_orig_full = img_pil.copy()
            self._norm_zoom = 1.0
            if hasattr(self, "_norm_lbl_zoom"):
                self._norm_lbl_zoom.config(text="100%")

            cw = max(self._norm_canvas_img.winfo_width(), 300)
            ch = max(self._norm_canvas_img.winfo_height(), 180)
            img_pil.thumbnail((cw, ch), Image.LANCZOS)
            self._norm_zoom = img_pil.width / max(self._norm_img_orig_full.width, 1)
            if hasattr(self, "_norm_lbl_zoom"):
                self._norm_lbl_zoom.config(text=f"{int(self._norm_zoom*100)}%")
            self._norm_canvas_img._img_ref = ImageTk.PhotoImage(img_pil)
            self._norm_canvas_img.configure(
                scrollregion=(0, 0, img_pil.width, img_pil.height))
            self._norm_canvas_img.create_image(
                cw // 2, ch // 2, anchor="center",
                image=self._norm_canvas_img._img_ref)
        except Exception as e:
            self._norm_canvas_img.create_text(
                150, 90, text=f"Error: {e}",
                fill="#D96B6B", font=("Segoe UI", 8), anchor="center")

    def _norm_guardar_bloque_actual(self):
        """Guarda el estado del bloque actualmente en pantalla."""
        idx = self._norm_idx_actual
        if idx < 0 or idx >= len(self._norm_bloques):
            return
        b = self._norm_bloques[idx]
        b["norm_usuario"] = self._norm_txt_usuario.get("1.0", "end-1c")
        b["norm_ia"]      = self._norm_txt_ia.get("1.0", "end-1c")
        self._marcar_modificado()

    def _norm_version_cambio(self):
        """Callback al cambiar el selector de versión — actualiza ST y muestra info."""
        ver = self._norm_var_version.get()
        ST.norm_version = ver
        _info = {
            "crudo":  "El texto crudo pasará al análisis tal como salió del OCR.",
            "manual": "Tus ediciones manuales pasarán al análisis (crudo si no editaste).",
            "ia":     "La sugerencia IA pasará al análisis (manual → crudo como fallback).",
        }
        if hasattr(self, "_norm_lbl_version_info"):
            self._norm_lbl_version_info.config(text=_info.get(ver, ""))

    def _norm_texto_para_pipeline(self, b: dict) -> str:
        """Devuelve el texto que debe usarse en el pipeline según ST.norm_version."""
        ver = getattr(ST, "norm_version", "manual")
        if ver == "crudo":
            return b["ocr_crudo"]
        if ver == "ia":
            return (b["norm_ia"].strip()
                    or b["norm_usuario"].strip()
                    or b["ocr_crudo"])
        # "manual" (default)
        return b["norm_usuario"].strip() or b["ocr_crudo"]

    # ══════════════════════════════════════════════════════════════════════════
    # VERIFICACIÓN OCR PALABRA POR PALABRA (estilo ABBYY FineReader)
    # ══════════════════════════════════════════════════════════════════════════
    def _verif_abrir(self):
        """Abre el diálogo de verificación sobre la página actualmente
        mostrada en Normalizar. Recalcula las palabras dudosas bajo demanda
        (nada se persiste aparte del texto corregido al cerrar)."""
        idx = self._norm_idx_actual
        if idx < 0 or idx >= len(self._norm_bloques):
            self.toast("Selecciona primero una página en la lista.", "warn")
            return
        img = getattr(self, "_norm_img_orig_full", None)
        if img is None:
            self.toast("No hay imagen cargada para esta página.", "warn")
            return

        b = self._norm_bloques[idx]
        texto_base = self._norm_txt_usuario.get("1.0", "end-1c") or b["ocr_crudo"]

        win, content = self._mk_glass_toplevel("Verificación OCR", 900, 620)
        self._verif_win = win
        self._verif_bloque_idx = idx
        self._verif_texto = texto_base
        self._verif_palabras = []
        self._verif_pos = 0
        self._verif_img_tk = None  # referencia viva contra el GC de Tk
        self._verif_q = queue.Queue()

        info = tk.Label(content, text="Analizando palabras de baja confianza…",
                         bg=TEMA.CONTENT_BG, fg=TEMA.TXT_SEC, font=("Segoe UI", 10))
        info.pack(pady=40)
        self._verif_lbl_info = info

        # Layout principal (se puebla cuando el worker entrega resultados)
        cuerpo = tk.Frame(content, bg=TEMA.CONTENT_BG)
        cuerpo.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        self._verif_cuerpo = cuerpo

        img_frame = tk.Frame(cuerpo, bg="#0E1114", relief="solid", bd=1, height=180)
        img_frame.pack(fill="x", pady=(0, 10))
        img_frame.pack_propagate(False)
        self._verif_lbl_img = tk.Label(img_frame, bg="#0E1114")
        self._verif_lbl_img.pack(expand=True)

        fila_txt = tk.Frame(cuerpo, bg=TEMA.CONTENT_BG)
        fila_txt.pack(fill="x", pady=(0, 8))
        tk.Label(fila_txt, text="Corrección:", bg=TEMA.CONTENT_BG, fg=TEMA.TXT_PRI,
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        self._verif_var_texto = tk.StringVar()
        entry = tk.Entry(fila_txt, textvariable=self._verif_var_texto,
                          font=("Consolas", 11), bg="#0E1114", fg="#E8E5DF",
                          insertbackground="#E8E5DF", relief="solid", bd=1)
        entry.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self._verif_entry = entry

        tk.Label(cuerpo, text="Sugerencias (doble clic para usar):",
                 bg=TEMA.CONTENT_BG, fg=TEMA.TXT_DIM, font=("Segoe UI", 8)).pack(anchor="w")
        self._verif_lb_sug = tk.Listbox(cuerpo, height=4, bg="#0E1114", fg="#E8E5DF",
                                         relief="solid", bd=1, font=("Segoe UI", 9))
        self._verif_lb_sug.pack(fill="x", pady=(2, 10))
        self._verif_lb_sug.bind("<Double-Button-1>", lambda e: self._verif_usar_sugerencia())

        botones = tk.Frame(cuerpo, bg=TEMA.CONTENT_BG)
        botones.pack(fill="x", pady=(0, 8))
        ttk.Button(botones, text="Omitir", style="S.TButton",
                   command=self._verif_omitir).pack(side="left", padx=(0, 6))
        ttk.Button(botones, text="Omitir todas", style="S.TButton",
                   command=self._verif_omitir_todas).pack(side="left", padx=(0, 6))
        ttk.Button(botones, text="Reemplazar", style="P.TButton",
                   command=self._verif_reemplazar).pack(side="left", padx=(0, 6))
        ttk.Button(botones, text="Reemplazar todas", style="P.TButton",
                   command=self._verif_reemplazar_todas).pack(side="left", padx=(0, 6))
        ttk.Button(botones, text="📖 Agregar a diccionario", style="S.TButton",
                   command=self._verif_agregar_diccionario).pack(side="left", padx=(0, 6))

        pie = tk.Frame(cuerpo, bg=TEMA.CONTENT_BG)
        pie.pack(fill="x")
        self._verif_lbl_contador = tk.Label(pie, text="", bg=TEMA.CONTENT_BG, fg=TEMA.TXT_DIM,
                                             font=("Segoe UI", 9))
        self._verif_lbl_contador.pack(side="left")
        ttk.Button(pie, text="✅ Terminar y guardar", style="P.TButton",
                   command=self._verif_cerrar).pack(side="right")

        cuerpo.pack_forget()  # se muestra al terminar el worker

        threading.Thread(target=self._verif_worker_analizar, args=(img,), daemon=True).start()
        win.after(100, self._verif_poll)
        win.protocol("WM_DELETE_WINDOW", self._verif_cerrar)

    def _verif_worker_analizar(self, img):
        """Corre en thread: extrae palabras dudosas + prepara diccionario de
        corpus para sugerencias. La imagen ya está en memoria (self._norm_img_orig_full,
        cargada una sola vez por _norm_mostrar_imagen) — no se vuelve a leer disco."""
        from core.word_verifier import extraer_palabras_dudosas
        try:
            palabras = extraer_palabras_dudosas(img)
        except Exception as e:
            self._verif_q.put(("error", str(e)))
            return

        dicc_corpus = None
        try:
            if ST.out_dir:
                from core.ocr_normalizer import construir_diccionario_corpus
                cache_path = Path(ST.out_dir) / "diccionario_corpus.json"
                txt_dir = Path(ST.out_dir) / "03_ocr"
                if txt_dir.exists():
                    dicc_corpus = construir_diccionario_corpus(
                        txt_dir, freq_min=3, cache_path=cache_path)
        except Exception:
            dicc_corpus = None
        self._verif_dicc_corpus = dicc_corpus
        self._verif_q.put(("ok", palabras))

    def _verif_poll(self):
        win = getattr(self, "_verif_win", None)
        if win is None or not win.winfo_exists():
            return
        try:
            tipo, payload = self._verif_q.get_nowait()
        except queue.Empty:
            win.after(100, self._verif_poll)
            return

        self._verif_lbl_info.pack_forget()
        if tipo == "error":
            tk.Label(win, text=f"Error: {payload}", bg=TEMA.CONTENT_BG, fg="#D96B6B",
                     font=("Segoe UI", 9)).pack(pady=20)
            return

        self._verif_palabras = payload
        self._verif_pos = 0
        self._verif_cuerpo.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        if not self._verif_palabras:
            self._verif_lbl_contador.config(
                text="Sin palabras de baja confianza en esta página. 🎉")
            for w in (self._verif_entry, self._verif_lb_sug):
                w.config(state="disabled")
            return
        self._verif_mostrar_actual()

    def _verif_mostrar_actual(self):
        from core.word_verifier import recortar_palabra, sugerencias_para
        img = self._norm_img_orig_full
        p = self._verif_palabras[self._verif_pos]

        recorte = recortar_palabra(img, p, margen=8, zoom=2.5)
        recorte.thumbnail((820, 160))
        from PIL import ImageTk
        self._verif_img_tk = ImageTk.PhotoImage(recorte)
        self._verif_lbl_img.config(image=self._verif_img_tk)

        self._verif_var_texto.set(p.texto)

        from core.spell_corrector import obtener_corrector
        corrector = obtener_corrector()
        corrector._cargar_diccionario()
        sugerencias = sugerencias_para(p.texto, corrector, getattr(self, "_verif_dicc_corpus", None))
        self._verif_lb_sug.delete(0, "end")
        for s in sugerencias:
            self._verif_lb_sug.insert("end", s)

        n = len(self._verif_palabras)
        self._verif_lbl_contador.config(
            text=f"Palabra {self._verif_pos + 1} de {n} — confianza {p.conf:.0f}%\n"
                 f"Contexto: …{p.contexto}…")

    def _verif_usar_sugerencia(self):
        sel = self._verif_lb_sug.curselection()
        if sel:
            self._verif_var_texto.set(self._verif_lb_sug.get(sel[0]))

    def _verif_avanzar(self):
        if self._verif_pos + 1 < len(self._verif_palabras):
            self._verif_pos += 1
            self._verif_mostrar_actual()
        else:
            self._verif_lbl_contador.config(text="✅ Última palabra revisada.")
            for w in (self._verif_entry, self._verif_lb_sug):
                w.config(state="disabled")

    def _verif_omitir(self):
        self._verif_avanzar()

    def _verif_omitir_todas(self):
        self._verif_lbl_contador.config(text="✅ Verificación cerrada sin más cambios.")
        for w in (self._verif_entry, self._verif_lb_sug):
            w.config(state="disabled")

    def _verif_reemplazar(self):
        from core.word_verifier import aplicar_reemplazo
        p = self._verif_palabras[self._verif_pos]
        nuevo_valor = self._verif_var_texto.get()
        texto, encontrada = aplicar_reemplazo(
            self._verif_texto, p.texto, nuevo_valor, p.idx_ocurrencia)
        self._verif_texto = texto
        if not encontrada:
            self.toast(f"«{p.texto}» (ocurrencia {p.idx_ocurrencia + 1}) no se "
                       "localizó en el texto — probablemente ya fue editado.", "warn")
        self._verif_avanzar()

    def _verif_reemplazar_todas(self):
        from core.word_verifier import reemplazar_todas
        p = self._verif_palabras[self._verif_pos]
        nuevo_valor = self._verif_var_texto.get()
        texto, n = reemplazar_todas(self._verif_texto, p.texto, nuevo_valor)
        self._verif_texto = texto
        self.toast(f"{n} ocurrencia(s) de «{p.texto}» reemplazadas.", "ok")
        self._verif_avanzar()

    def _verif_agregar_diccionario(self):
        from core.spell_corrector import obtener_corrector
        p = self._verif_palabras[self._verif_pos]
        obtener_corrector().agregar_palabra_usuario(p.texto)
        self.toast(f"«{p.texto}» agregada al vocabulario de usuario.", "ok")
        self._verif_avanzar()

    def _verif_cerrar(self):
        """Vuelca el texto corregido al bloque actual del panel Normalizar
        (mismo flujo de guardado que ya existe: _norm_guardar_bloque_actual
        → _norm_guardar → UPSERT en SQLite). El verificador nunca escribe
        directamente a disco/BD — un solo escritor."""
        win = getattr(self, "_verif_win", None)
        if getattr(self, "_verif_texto", None) is not None and \
           self._verif_bloque_idx == self._norm_idx_actual:
            self._norm_txt_usuario.delete("1.0", "end")
            self._norm_txt_usuario.insert("1.0", self._verif_texto)
            self._norm_guardar_bloque_actual()
        if win is not None and win.winfo_exists():
            win.destroy()
        self._verif_win = None

    def _norm_guardar(self):
        """Persiste todas las ediciones en SQLite y en los archivos .txt."""
        self._norm_guardar_bloque_actual()
        db_path = Path(ST.ruta_db) if ST.ruta_db else None
        ver     = getattr(ST, "norm_version", "manual")
        guardados = n_crudo = n_manual = n_ia = fallos_db = 0

        for b in self._norm_bloques:
            texto_final = self._norm_texto_para_pipeline(b)
            # Contadores por versión efectiva usada
            if ver == "crudo" or not b["norm_usuario"].strip():
                n_crudo += 1
            elif ver == "ia" and b["norm_ia"].strip():
                n_ia += 1
            else:
                n_manual += 1
            try:
                Path(b["txt_path"]).write_text(texto_final, encoding="utf-8")
                guardados += 1
            except Exception:
                pass
            # Persistir todas las versiones en SQLite para no perder nada
            if db_path and not self._norm_escribir_db(
                    db_path, b["numero"], b["pagina"],
                    b["ocr_crudo"], b["norm_usuario"], b["norm_ia"],
                    b.get("autor_ia", "")):
                fallos_db += 1

        ST.norm_done   = True
        ST.norm_version = ver
        # Las etapas posteriores deben re-ejecutarse con el nuevo texto
        ST.marcar_etapa("norm", "ready")
        self._actualizar_badges()

        _etiq = {"crudo": "crudo", "manual": "manual", "ia": "IA"}
        detalle = f"  ({n_manual} manual · {n_ia} IA · {n_crudo} crudo)"
        if fallos_db:
            detalle += f"  ⚠ {fallos_db} sin registrar en la base (ver registro de errores)"
        self._lbl_norm_estado.config(
            text=f"✅ {guardados} páginas guardadas como {_etiq[ver]}{detalle}")

    def _norm_reocr_pagina(self):
        """Re-extrae el texto de la página actual con Tesseract y actualiza el bloque."""
        idx = self._norm_idx_actual
        if idx < 0 or idx >= len(self._norm_bloques):
            messagebox.showwarning("Sin selección", "Selecciona una página primero.")
            return
        b = self._norm_bloques[idx]
        num, pagina = b["numero"], b["pagina"]

        # Buscar imagen original a color
        img_path = None
        if ST.out_dir:
            img_dir = Path(ST.out_dir) / "02_imagenes" / num
            for ext in ("*.png", "*.jpg", "*.tif", "*.tiff"):
                hits = sorted(img_dir.glob(f"*{pagina}*")) if img_dir.exists() else []
                if hits:
                    img_path = hits[0]
                    break
        if img_path is None:
            messagebox.showwarning("Sin imagen",
                "No se encontró la imagen original para esta página.\n"
                "Ejecuta primero la extracción OCR con Ruta 1.")
            return

        self._lbl_norm_estado.config(text=f"⏳ Re-OCR Tesseract: {pagina}…", fg="#E6A64C")
        self.update_idletasks()

        def _run():
            try:
                # Por zonas si la página tiene etiquetas guardadas; si no, completa
                from core.layout_tesseract import ocr_pagina_con_zonas
                texto, conf, con_z = ocr_pagina_con_zonas(
                    img_path, ST.out_dir, num, pagina, lang="spa")
                # Actualizar el bloque en memoria y en disco
                b["ocr_crudo"]    = texto
                b["norm_usuario"] = ""   # limpiar edición anterior (era basura)
                txt_path = Path(b["txt_path"])
                txt_path.write_text(texto, encoding="utf-8")
                _modo = " · por zonas" if con_z else ""
                self.after(0, lambda: (
                    self._norm_mostrar_bloque(idx),
                    self._lbl_norm_estado.config(
                        text=f"✅ {pagina} re-extraído (conf: {conf}%{_modo})", fg=TEMA.VERDE),
                    self._norm_refrescar_lista(),
                ))
            except Exception as e:
                self.after(0, lambda err=str(e): self._lbl_norm_estado.config(
                    text=f"⚠ Error: {err}", fg=TEMA.ROJO))

        threading.Thread(target=_run, daemon=True).start()

    def _norm_regenerar_imagenes(self):
        """Regenera las imágenes del número desde el PDF original, respetando rotación."""
        num = self._norm_var_numero.get()
        if not num or not ST.out_dir:
            return
        # Buscar el PDF original
        pdf_path = None
        for archivo in getattr(ST, "archivos_sel", []):
            if archivo.stem == num:
                pdf_path = archivo
                break
        if pdf_path is None:
            # Buscar en carpeta de entrada configurada
            if ST.pdf_dir:
                hits = list(Path(ST.pdf_dir).glob(f"{num}*.pdf"))
                if hits:
                    pdf_path = hits[0]
        if pdf_path is None:
            messagebox.showwarning("Sin PDF",
                f"No se encontró el PDF original para '{num}'.\n"
                "Asegúrate de que la carpeta de entrada está configurada.")
            return

        if not messagebox.askyesno("Regenerar imágenes",
            f"Se regenerarán las imágenes de '{num}' desde el PDF original.\n\n"
            "Esto corrige imágenes rotadas o en mal formato.\n"
            "Las imágenes anteriores se sobreescribirán.\n\n"
            "¿Continuar?"):
            return

        img_dir = Path(ST.out_dir) / "02_imagenes" / num
        self._lbl_norm_estado.config(text="⏳ Regenerando imágenes…", fg="#E6A64C")

        def _run():
            try:
                # Eliminar imágenes anteriores para forzar regeneración
                if img_dir.exists():
                    for f in img_dir.glob("*.png"):
                        f.unlink()
                img_dir.mkdir(parents=True, exist_ok=True)

                from core.ocr_engine import pdf_a_imagenes
                dpi = 150  # DPI recomendado
                imgs = pdf_a_imagenes(pdf_path, img_dir, dpi)

                self.after(0, lambda: (
                    self._lbl_norm_estado.config(
                        text=f"✅ {len(imgs)} imágenes regeneradas — {num}", fg=TEMA.VERDE),
                    self._norm_mostrar_bloque(self._norm_idx_actual),
                ))
            except Exception as e:
                self.after(0, lambda err=str(e): self._lbl_norm_estado.config(
                    text=f"⚠ Error: {err}", fg=TEMA.ROJO))

        threading.Thread(target=_run, daemon=True).start()

    def _norm_reocr_numero(self):
        """Re-extrae el texto de TODAS las páginas del número con Tesseract."""
        num = self._norm_var_numero.get()
        if not num or not ST.out_dir:
            return
        if not messagebox.askyesno("Re-OCR completo",
            f"Se re-extraerá el texto de {len(self._norm_bloques)} páginas con Tesseract.\n\n"
            "Esto sobreescribirá los .txt actuales (incluyendo texto basura de Kraken).\n"
            "¿Continuar?"):
            return

        self._lbl_norm_estado.config(text="⏳ Re-OCR Tesseract en curso…", fg="#E6A64C")

        def _run():
            from core.layout_tesseract import ocr_pagina_con_zonas
            total = len(self._norm_bloques)
            ok = 0
            for i, b in enumerate(self._norm_bloques):
                # Buscar imagen
                img_path = None
                img_dir = Path(ST.out_dir) / "02_imagenes" / b["numero"]
                for ext in ("*.png","*.jpg","*.tif","*.tiff"):
                    hits = sorted(img_dir.glob(f"*{b['pagina']}*")) if img_dir.exists() else []
                    if hits:
                        img_path = hits[0]; break

                if img_path is None:
                    continue
                try:
                    texto, conf, _cz = ocr_pagina_con_zonas(
                        img_path, ST.out_dir, b["numero"], b["pagina"], lang="spa")
                    b["ocr_crudo"]    = texto
                    b["norm_usuario"] = ""
                    Path(b["txt_path"]).write_text(texto, encoding="utf-8")
                    ok += 1
                except Exception:
                    pass

                n = i + 1
                self.after(0, lambda n=n, total=total: self._lbl_norm_estado.config(
                    text=f"⏳ Re-OCR {n}/{total}…", fg="#E6A64C"))

            self.after(0, lambda: (
                self._norm_cargar_numero(),
                self._lbl_norm_estado.config(
                    text=f"✅ {ok}/{total} páginas re-extraídas con Tesseract", fg=TEMA.VERDE),
            ))

        threading.Thread(target=_run, daemon=True).start()

    def _norm_importar_txt(self):
        """
        Importa un .txt externo (exportado desde Acrobat u otro programa)
        para la página actualmente seleccionada.
        El texto importado reemplaza el OCR crudo y se coloca en la vista usuario.
        """
        idx = self._norm_idx_actual
        if idx < 0 or idx >= len(self._norm_bloques):
            # Si no hay página seleccionada, ofrecer importar para todo el número
            self._norm_importar_txt_numero()
            return

        b = self._norm_bloques[idx]
        ruta = filedialog.askopenfilename(
            title=f"Importar texto para {b['pagina']}",
            filetypes=[("Archivos de texto", "*.txt"), ("Todos los archivos", "*.*")],
        )
        if not ruta:
            return

        try:
            texto = Path(ruta).read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            messagebox.showerror("Error al leer", str(e))
            return

        # Guardar como ocr_crudo (fuente externa) y limpiar edición previa
        b["ocr_crudo"]    = texto
        b["norm_usuario"] = ""
        Path(b["txt_path"]).write_text(texto, encoding="utf-8")

        self._norm_mostrar_bloque(idx)
        self._lbl_norm_estado.config(
            text=f"✅ Texto importado en {b['pagina']} ({len(texto.split())} palabras)",
            fg=TEMA.VERDE)

    def _norm_importar_txt_numero(self):
        """
        Importa una carpeta completa de .txt para reemplazar el OCR de un número.
        Útil cuando se exportó el texto desde Acrobat página por página.
        El nombre de cada archivo debe coincidir con el stem de la página (p0001, p0002, etc.)
        o ser numerado (1.txt, 2.txt, etc.).
        """
        num = self._norm_var_numero.get()
        if not num:
            messagebox.showwarning("Sin número", "Selecciona un número primero.")
            return

        carpeta = filedialog.askdirectory(
            title="Selecciona la carpeta con los archivos .txt exportados de Acrobat")
        if not carpeta:
            return

        txts = sorted(Path(carpeta).glob("*.txt"))
        if not txts:
            messagebox.showwarning("Sin archivos",
                "No se encontraron archivos .txt en esa carpeta.")
            return

        if not messagebox.askyesno("Importar textos externos",
            f"Se importarán {len(txts)} archivos .txt desde:\n{carpeta}\n\n"
            "Reemplazarán el OCR actual de cada página. ¿Continuar?"):
            return

        importados = 0
        for b in self._norm_bloques:
            # Buscar por nombre exacto (p0001.txt) o por número (1.txt, 01.txt)
            import re as _re
            m = _re.search(r'(\d+)', b["pagina"])
            n = int(m.group(1)) if m else -1
            candidatos = [
                Path(carpeta) / f"{b['pagina']}.txt",
                Path(carpeta) / f"{n}.txt",
                Path(carpeta) / f"{n:02d}.txt",
                Path(carpeta) / f"{n:03d}.txt",
                Path(carpeta) / f"{n:04d}.txt",
            ] + [t for t in txts if b["pagina"] in t.stem]

            for cand in candidatos:
                if cand.exists():
                    try:
                        texto = cand.read_text(encoding="utf-8", errors="replace")
                        b["ocr_crudo"]    = texto
                        b["norm_usuario"] = ""
                        Path(b["txt_path"]).write_text(texto, encoding="utf-8")
                        importados += 1
                    except Exception:
                        pass
                    break

        self._norm_cargar_numero()
        self._lbl_norm_estado.config(
            text=f"✅ {importados}/{len(self._norm_bloques)} páginas importadas desde carpeta",
            fg=TEMA.VERDE)

    def _norm_reconstruir_columnas(self):
        """
        Aplica la reconstrucción de líneas rotas (algoritmo BNC) al bloque actual
        o a todo el número. Corrige el problema de columnas mezcladas del texto BNC:
        une líneas cortas que pertenecen al mismo párrafo y separa las de columnas distintas.
        """
        idx = self._norm_idx_actual
        alcance = "pagina" if (idx >= 0 and idx < len(self._norm_bloques)) else "numero"

        if alcance == "pagina":
            resp = messagebox.askyesnocancel(
                "Reconstruir columnas",
                "¿Reconstruir columnas solo en esta página (Sí)\n"
                "o en todo el número (No)?")
            if resp is None:
                return
            alcance = "pagina" if resp else "numero"

        from core.ocr_normalizer import reconstruir_lineas_rotas

        if alcance == "pagina":
            b = self._norm_bloques[idx]
            base = b["norm_usuario"] if b["norm_usuario"] else b["ocr_crudo"]
            reconstruido = reconstruir_lineas_rotas(base)
            b["norm_usuario"] = reconstruido
            self._norm_mostrar_bloque(idx)
            palabras = len(reconstruido.split())
            self._lbl_norm_estado.config(
                text=f"✅ Columnas reconstruidas en {b['pagina']} ({palabras} palabras)",
                fg=TEMA.VERDE)
        else:
            n = 0
            for b in self._norm_bloques:
                base = b["norm_usuario"] if b["norm_usuario"] else b["ocr_crudo"]
                if base.strip():
                    b["norm_usuario"] = reconstruir_lineas_rotas(base)
                    n += 1
            self._norm_refrescar_lista()
            self._lbl_norm_estado.config(
                text=f"✅ Columnas reconstruidas en {n} páginas",
                fg=TEMA.VERDE)

    def _norm_diccionario_corpus(self):
        """Construye el diccionario de frecuencias del corpus completo y lo guarda en JSON."""
        if not ST.out_dir:
            messagebox.showwarning("Sin corpus",
                                   "Carga primero un corpus para construir el diccionario.")
            return

        txt_dir = Path(ST.out_dir) / "03_ocr"
        if not txt_dir.exists():
            messagebox.showwarning("Sin textos OCR",
                                   "No se encontró la carpeta 03_ocr/.\n"
                                   "Ejecuta primero el paso Extracción OCR o el Conversor PDF.")
            return

        cache_path = Path(ST.out_dir) / "diccionario_corpus.json"

        def _run():
            from core.ocr_normalizer import construir_diccionario_corpus
            self.after(0, lambda: self._lbl_norm_estado.config(
                text="⏳ Construyendo diccionario de corpus…", fg=TEMA.TXT_SEC))

            def _cb(n, total, nombre):
                self.after(0, lambda: self._lbl_norm_estado.config(
                    text=f"⏳ Procesando {n}/{total}: {nombre}", fg=TEMA.TXT_SEC))

            try:
                dic = construir_diccionario_corpus(
                    txt_dir, freq_min=3, cache_path=cache_path, callback=_cb)
                n_palabras = len(dic)
                top5 = sorted(dic.items(), key=lambda x: -x[1])[:5]
                top5_str = ", ".join(f"{p}({f})" for p, f in top5)
                self.after(0, lambda: self._lbl_norm_estado.config(
                    text=f"✅ Diccionario listo: {n_palabras:,} palabras · top: {top5_str}",
                    fg=TEMA.VERDE))
                self.after(0, lambda: messagebox.showinfo(
                    "Diccionario de corpus",
                    f"Diccionario construido con {n_palabras:,} palabras (freq ≥ 3).\n\n"
                    f"Top 5: {top5_str}\n\n"
                    f"Guardado en:\n{cache_path}"))
            except Exception as ex:
                self.after(0, lambda err=str(ex): self._lbl_norm_estado.config(
                    text=f"❌ Error: {err}", fg="#D96B6B"))

        threading.Thread(target=_run, daemon=True).start()

    def _norm_dictar_toggle(self):
        """Inicia o detiene la sesión de dictado por voz."""
        if self._dictar_session is not None:
            # Detener sesión activa
            self._dictar_session.detener()
            self._dictar_session = None
            self._btn_dictar.config(text="🎙 Dictar")
            self._lbl_dictar_estado.config(text="", fg=TEMA.TXT_DIM)
            return

        try:
            from core.voice_dictation import DictadoSession
        except ImportError:
            messagebox.showerror("Dependencia faltante",
                                 "Instala las dependencias de dictado:\n\n"
                                 "  pip install SpeechRecognition sounddevice\n\n"
                                 "Luego reinicia la aplicación.")
            return

        self._btn_dictar.config(text="⏹ Detener")
        self._lbl_dictar_estado.config(text="⏳ Iniciando micrófono…", fg=TEMA.TXT_SEC)

        def _on_texto(texto: str):
            # Llamado desde hilo de audio — usar after() para acceder a tkinter
            self.after(0, lambda t=texto: self._norm_dictar_insertar(t))

        self._dictar_session = DictadoSession(
            callback=_on_texto,
            idioma="es-CO",
            modo_online=True,
        )
        self._dictar_session.iniciar()
        # Iniciar polling de estados del hilo de audio
        self.after(200, self._norm_dictar_poll)

    def _norm_dictar_insertar(self, texto: str):
        """Inserta texto transcrito en el textarea de usuario, con espacio separador."""
        if not texto.strip():
            return
        widget = self._norm_txt_usuario
        # Posición actual del cursor; si no hay cursor, insertar al final
        try:
            pos = widget.index("insert")
        except Exception:
            pos = "end"
        # Añadir espacio si el texto previo no termina en espacio o salto
        contenido_actual = widget.get("1.0", pos)
        if contenido_actual and contenido_actual[-1] not in (" ", "\n"):
            texto = " " + texto
        widget.insert(pos, texto)
        widget.see("insert")
        # Indicador visual del último fragmento reconocido
        preview = texto.strip()[:40] + ("…" if len(texto.strip()) > 40 else "")
        self._lbl_dictar_estado.config(
            text=f"🔴 Escuchando · '{preview}'", fg="#D96B6B")

    def _norm_dictar_poll(self):
        """Polling de mensajes de estado del hilo de dictado (cada 200 ms)."""
        if self._dictar_session is None:
            return
        estado = self._dictar_session.estado()
        if estado:
            if estado == "escuchando":
                self._lbl_dictar_estado.config(text="🔴 Escuchando…", fg="#D96B6B")
            elif estado == "detenido":
                self._btn_dictar.config(text="🎙 Dictar")
                self._lbl_dictar_estado.config(text="", fg=TEMA.TXT_DIM)
                self._dictar_session = None
                return
            elif estado.startswith("error:"):
                msg = estado[6:]
                self._btn_dictar.config(text="🎙 Dictar")
                self._lbl_dictar_estado.config(text=f"⚠ {msg}", fg="#E6A64C")
                self._dictar_session = None
                return
        # Continuar polling mientras la sesión esté activa
        self.after(200, self._norm_dictar_poll)

    def _norm_auto(self):
        """Aplica normalización automática a todos los bloques no editados."""
        def _run():
            from core.text_postprocessor import normalizar_bloque
            for b in self._norm_bloques:
                if not b["norm_usuario"]:
                    b["norm_usuario"] = normalizar_bloque(b["ocr_crudo"])
            self.after(0, self._norm_refrescar_lista)
            self.after(0, lambda: self._lbl_norm_estado.config(
                text=f"✅ Normalización automática aplicada a {len(self._norm_bloques)} bloques"))
        threading.Thread(target=_run, daemon=True).start()

    def _norm_ia(self):
        """Solicita sugerencia de IA para el bloque actual."""
        if not ST.ia_habilitada:
            messagebox.showwarning("IA deshabilitada",
                                   "Activa la IA desde el switch en la barra superior.")
            return
        idx = self._norm_idx_actual
        if idx < 0 or idx >= len(self._norm_bloques):
            return
        b = self._norm_bloques[idx]
        texto_base = b["norm_usuario"] or b["ocr_crudo"]

        api_key = _resolver_api_key_modelo("ocr_mejora")[0]
        if not api_key:
            messagebox.showwarning("Sin API key",
                "No hay clave de API configurada.\n\n"
                "Ve a ⚙ Configuración → claves de API\n"
                "y pega tu clave de Anthropic, OpenAI o Gemini.")
            return

        def _run():
            try:
                from core.ocr_llm import corregir_texto
                sugerencia = corregir_texto(texto_base, api_key)
            except Exception as exc:
                # Un error NO es una capa de corrección: antes el texto
                # "[Error: ...]" quedaba guardado como norm_ia en SQLite.
                self.after(0, lambda m=str(exc): messagebox.showerror(
                    "Error IA", f"No se pudo obtener sugerencia:\n{m}"))
                return
            b["norm_ia"] = sugerencia
            b["autor_ia"] = "core.ocr_llm.corregir_texto"
            self.after(0, lambda: (
                self._norm_txt_ia.delete("1.0", "end"),
                self._norm_txt_ia.insert("1.0", sugerencia),
            ))
        threading.Thread(target=_run, daemon=True).start()

    def _norm_on_zoom(self, event):
        factor = 1.15 if event.delta > 0 else 1 / 1.15
        self._norm_zoom = max(0.15, min(6.0, self._norm_zoom * factor))
        self._norm_aplicar_zoom()

    def _norm_zoom_step(self, direction: int):
        factor = 1.25 if direction > 0 else 1 / 1.25
        self._norm_zoom = max(0.15, min(6.0, self._norm_zoom * factor))
        self._norm_aplicar_zoom()

    def _norm_aplicar_zoom(self):
        if self._norm_img_orig_full is None:
            return
        from PIL import ImageTk
        new_w = max(1, int(self._norm_img_orig_full.width  * self._norm_zoom))
        new_h = max(1, int(self._norm_img_orig_full.height * self._norm_zoom))
        img_r = self._norm_img_orig_full.resize((new_w, new_h), 1)  # 1 = LANCZOS
        self._norm_canvas_img._img_ref = ImageTk.PhotoImage(img_r)
        self._norm_canvas_img.delete("all")
        self._norm_canvas_img.create_image(0, 0, anchor="nw",
                                            image=self._norm_canvas_img._img_ref)
        self._norm_canvas_img.configure(scrollregion=(0, 0, new_w, new_h))
        pct = int(self._norm_zoom * 100)
        if hasattr(self, "_norm_lbl_zoom"):
            self._norm_lbl_zoom.config(text=f"{pct}%")

    def _norm_pan_start_cb(self, event):
        self._norm_pan_start = (event.x, event.y)
        self._norm_canvas_img.config(cursor="fleur")

    def _norm_pan_drag_cb(self, event):
        if self._norm_pan_start is None:
            return
        dx = self._norm_pan_start[0] - event.x
        dy = self._norm_pan_start[1] - event.y
        self._norm_pan_start = (event.x, event.y)
        self._norm_canvas_img.xview_scroll(int(dx), "units")
        self._norm_canvas_img.yview_scroll(int(dy), "units")

    def _norm_pan_end_cb(self, event):
        self._norm_pan_start = None
        self._norm_canvas_img.config(cursor="")

    def _norm_refrescar_lista(self):
        """Refresca los indicadores ✓/⚠ en la lista de bloques."""
        avisos_ocr = getattr(self, "_avisos_ocr", {})
        for i, b in enumerate(self._norm_bloques):
            estado = _simbolo_estado_norm(b)
            alerta = " ⚠" if (b["numero"], b["pagina"]) in avisos_ocr else ""
            self._norm_lb.delete(i)
            self._norm_lb.insert(i, f"{estado} {b['pagina']}{alerta}")
        if self._norm_idx_actual >= 0:
            self._norm_lb.selection_set(self._norm_idx_actual)
            self._norm_mostrar_bloque(self._norm_idx_actual)

    def _norm_leer_db(self, db_path, numero: str, pagina: str):
        """Lee (norm_usuario, norm_ia, ocr_crudo) de SQLite; Nones si no existe."""
        from datos import normalizaciones as NZ
        try:
            fila = NZ.leer(db_path, numero, pagina)
        except Exception as e:
            _registrar_error(f"normalizar: no se pudo leer {numero} {pagina}", e)
            fila = None
        if not fila:
            return None, None, None
        return fila.get("norm_usuario"), fila.get("norm_ia"), fila.get("ocr_crudo")

    def _norm_escribir_db(self, db_path, numero: str, pagina: str,
                           ocr_crudo: str, norm_usuario: str, norm_ia: str,
                           autor_ia: str = "") -> bool:
        """Guarda las capas de la página con historial. Devuelve False si falló.

        La lógica vive en datos/normalizaciones.py: el OCR crudo no se
        sobrescribe nunca y cada capa lleva su propia marca de tiempo.
        """
        from core.proveniencia import commit_software
        from core.servicios_corpus import procedencia_pagina
        from datos import normalizaciones as NZ
        # Con qué motor y versión se produjo el OCR crudo (ocr_metadatos.csv).
        motor, version = procedencia_pagina(getattr(ST, "corpus_meta", None), numero, pagina)
        try:
            NZ.guardar(db_path, numero, pagina, ocr_crudo=ocr_crudo,
                       norm_usuario=norm_usuario, norm_ia=norm_ia,
                       autor_usuario=_autor_local(),
                       autor_ia=autor_ia or "ia",
                       ocr_motor=motor, ocr_version=version,
                       commit_software=commit_software())
            return True
        except Exception as e:
            _registrar_error(f"normalizar: no se pudo guardar {numero} {pagina}", e)
            return False

    def _norm_ver_diff(self):
        """Abre ventana con diff coloreado entre OCR crudo y versión manual."""
        idx = self._norm_idx_actual
        if idx < 0 or idx >= len(self._norm_bloques):
            messagebox.showwarning("Sin selección", "Selecciona una página primero.")
            return
        import difflib
        b = self._norm_bloques[idx]
        crudo  = b.get("ocr_crudo", "").splitlines(keepends=True)
        manual = (b.get("norm_usuario") or b.get("ocr_crudo", "")).splitlines(keepends=True)

        diff = list(difflib.unified_diff(crudo, manual,
                                          fromfile="OCR crudo",
                                          tofile="Manual",
                                          lineterm="", n=2))
        if not diff:
            messagebox.showinfo("Sin cambios",
                                "No hay diferencias entre el texto crudo y el manual.")
            return

        win, diff_content = self._mk_glass_toplevel(
            f"🔍 Cambios — {b.get('pagina', '')}", ancho=700, alto=500)

        txt = scrolledtext.ScrolledText(
            diff_content, bg="#0E1114", fg=TEMA.TXT_PRI, font=("Courier New", 9),
            relief="flat", wrap="none")
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.tag_configure("add", foreground="#6EC69A", background="#15251F")
        txt.tag_configure("del", foreground="#D96B6B", background="#2A1719")
        txt.tag_configure("hdr", foreground="#6CA8E8")
        txt.tag_configure("ctx", foreground="#777F84")

        for line in diff:
            if line.startswith("+++") or line.startswith("---"):
                txt.insert("end", line + "\n", "hdr")
            elif line.startswith("+"):
                txt.insert("end", line + "\n", "add")
            elif line.startswith("-"):
                txt.insert("end", line + "\n", "del")
            elif line.startswith("@@"):
                txt.insert("end", line + "\n", "hdr")
            else:
                txt.insert("end", line + "\n", "ctx")
        txt.config(state="disabled")

    def _norm_exportar_ground_truth(self):
        """Exporta pares (imagen, texto) para reentrenamiento Kraken."""
        if not ST.out_dir:
            messagebox.showwarning("Sin corpus", "Carga un corpus primero.")
            return
        numero = self._norm_var_numero.get() if hasattr(self, "_norm_var_numero") else ""
        if not numero:
            messagebox.showwarning("Sin número", "Selecciona un número en Normalizar.")
            return
        from tkinter import filedialog
        dest = filedialog.askdirectory(title="Carpeta destino del dataset HTR")
        if not dest:
            return

        txt_dir = Path(ST.out_dir) / "03_ocr" / numero
        img_dir = Path(ST.out_dir) / "02_imagenes" / numero
        out_dir = Path(dest) / f"ground_truth_{numero}"

        self._lbl_norm_estado.config(text="⏳ Exportando dataset HTR…", fg=TEMA.TXT_SEC)

        def _run():
            from core.kraken_trainer import exportar_ground_truth
            def _cb(n, total, msg):
                self.after(0, lambda: self._lbl_norm_estado.config(
                    text=f"⏳ {n}/{total}: {msg}", fg=TEMA.TXT_SEC))
            try:
                res = exportar_ground_truth(txt_dir, img_dir, out_dir, callback=_cb)
                self.after(0, lambda r=res: (
                    self._lbl_norm_estado.config(
                        text=f"✅ {r['pares']} pares exportados a {r['out_dir']}",
                        fg=TEMA.VERDE),
                    messagebox.showinfo(
                        "Dataset HTR exportado",
                        f"Pares exportados: {r['pares']}\n"
                        f"Omitidos: {r['omitidos']}\n\n"
                        f"Carpeta:\n{r['out_dir']}\n\n"
                        f"Usa con:\n"
                        f"  ketos train -f binary "
                        f"--load {r['out_dir']}/manifest.txt\n"
                        f"  (en D:\\kraken_env)")
                ))
            except Exception as e:
                self.after(0, lambda err=str(e): self._lbl_norm_estado.config(
                    text=f"❌ {err}", fg="#D96B6B"))
        threading.Thread(target=_run, daemon=True).start()
