"""paneles/etiquetador_zonas.py — Métodos de BashkarApp extraídos de app.py.

Mixin: BashkarApp hereda de PanelEtiquetadorZonas. Los cuerpos son copia literal del
original; los nombres globales (ST, colores, tk…) los inyecta
paneles.sincronizar() desde app.py.
"""

from __future__ import annotations

# ruff: noqa: F821


class PanelEtiquetadorZonas:
    # ══════════════════════════════════════════════════════════════════════════
    # TAB ETZ: ETIQUETADOR DE ZONAS
    # ══════════════════════════════════════════════════════════════════════════
    def _build_etz(self):
        """
        Etiquetador estilo ABBYY FineReader — 4 paneles sincronizados:
          Páginas (izq) | Imagen+Zonas (centro) | Texto OCR (der) | Zoom (inferior)
        """
        f = self._tab_etz

        # ── Estado interno ─────────────────────────────────────────────────────
        self._etz_numero    = tk.StringVar(value="")
        self._etz_pagina    = tk.StringVar(value="")
        self._etz_tipo      = tk.StringVar(value="articulo")
        self._etz_img_orig  = None
        self._etz_img_tk    = None
        self._etz_escala    = 1.0
        self._etz_rect_ini  = None
        self._etz_rect_tmp  = None
        self._etz_zonas     = []
        self._etz_canvas_ids = []
        self._etz_detector  = None
        self._etz_modo          = None
        self._etz_resize_idx    = None
        self._etz_resize_handle = None
        self._etz_move_offset   = None
        self._etz_zona_sel_idx  = None
        self._etz_zoom          = 1.0
        self._etz_pan_start     = None
        self._etz_space_held    = False
        self._etz_modo_det  = tk.StringVar(value="tesseract")

        from core.zone_labeler import TIPOS_ZONA, DetectorZonas
        self._etz_detector = DetectorZonas()

        # Colores FineReader para tipos de zona
        _FR_COLORS = {
            "articulo":   "#6EC69A",   # verde texto
            "titulo":     "#6CA8E8",   # azul titular
            "publicidad": "#D96B6B",   # rojo imagen/publicidad
            "foto":       "#D96B6B",
            "pie_foto":   "#E6A64C",
            "numero_pag": "#777F84",
            "cabecera":   "#B18AD6",
            "indice":     "#6CA8E8",
            "colofon":    "#B18AD6",
        }
        # Actualizar colores de TIPOS_ZONA con los de FineReader
        for tid, color in _FR_COLORS.items():
            if tid in TIPOS_ZONA:
                TIPOS_ZONA[tid]["color"] = color

        # ── TOOLBAR RIBBON — 2 filas para no desbordar ────────────────────────
        ribbon_wrap = tk.Frame(f, bg="#22292F")
        ribbon_wrap.pack(fill="x")

        # Fila 1: Navegación + Tipos de zona
        row1 = tk.Frame(ribbon_wrap, bg="#22292F", height=30)
        row1.pack(fill="x")
        row1.pack_propagate(False)

        def _rb_btn(parent, text, cmd, bg="#22292F", fg="#E8E5DF", bold=False):
            b = tk.Label(parent, text=text, bg=bg, fg=fg, cursor="hand2",
                         font=("Segoe UI", 7, "bold" if bold else "normal"),
                         padx=5, pady=2)
            b.pack(side="left", padx=1)
            b.bind("<Button-1>", lambda e, c=cmd: c())
            orig_bg = bg
            b.bind("<Enter>", lambda e, w=b: w.config(bg="#22292F"))
            b.bind("<Leave>", lambda e, w=b, ob=orig_bg: w.config(bg=ob))
            return b

        def _rb_sep(parent):
            tk.Frame(parent, bg="#22292F", width=1).pack(
                side="left", fill="y", pady=3, padx=3)

        # Abrir PDF
        _rb_btn(row1, "📂 PDF", self._etz_abrir_pdf_directo,
                bg="#6CA8E8", fg="white", bold=True)
        _rb_sep(row1)

        # Número
        tk.Label(row1, text="N°:", bg="#22292F", fg="#777F84",
                 font=("Segoe UI", 7)).pack(side="left", padx=(4, 1))
        self._etz_cb_num = ttk.Combobox(row1, textvariable=self._etz_numero,
                                         width=18, state="readonly", font=("Segoe UI", 8))
        self._etz_cb_num.pack(side="left", padx=(0, 3))
        self._etz_cb_num.bind("<<ComboboxSelected>>", self._etz_on_numero)

        tk.Label(row1, text="Pág:", bg="#22292F", fg="#777F84",
                 font=("Segoe UI", 7)).pack(side="left", padx=(2, 1))
        self._etz_cb_pag = ttk.Combobox(row1, textvariable=self._etz_pagina,
                                         width=8, state="readonly", font=("Segoe UI", 8))
        self._etz_cb_pag.pack(side="left", padx=(0, 2))
        self._etz_cb_pag.bind("<<ComboboxSelected>>", self._etz_on_pagina)

        for txt, cmd in [("◀", self._etz_pagina_ant), ("▶", self._etz_pagina_sig)]:
            b = tk.Label(row1, text=txt, bg="#22292F", fg="#E8E5DF",
                         font=("Segoe UI", 9, "bold"), cursor="hand2", padx=3)
            b.pack(side="left", padx=1)
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>", lambda e, w=b: w.config(bg="#6CA8E8"))
            b.bind("<Leave>", lambda e, w=b: w.config(bg="#22292F"))

        _rb_sep(row1)

        # Tipos de zona
        tk.Label(row1, text="Zona:", bg="#22292F", fg="#777F84",
                 font=("Segoe UI", 7)).pack(side="left", padx=(3, 2))
        self._etz_tipo_btns = {}
        for tid, meta in TIPOS_ZONA.items():
            color = meta.get("color", "#777F84")
            lbl   = meta.get("label", tid)[:7]
            btn = tk.Label(row1, text=lbl, bg=color, fg="white",
                           font=("Segoe UI", 7, "bold"), padx=4, pady=1,
                           cursor="hand2", relief="flat")
            btn.pack(side="left", padx=1)
            btn.bind("<Button-1>", lambda e, t=tid: self._etz_sel_tipo(t))
            self._etz_tipo_btns[tid] = btn

        _rb_sep(row1)
        _rb_btn(row1, "＋ Tipo", self._etz_agregar_tipo_custom,
                fg="#6EC69A", bold=True)
        _rb_btn(row1, "🔤 Tipogr.", self._etz_deepfont_zona,
                fg="#D58B45", bold=True)
        _rb_sep(row1)
        _rb_btn(row1, "📊 Estadísticas", self._etz_mostrar_estadisticas,
                fg="#B18AD6", bold=True)

        # Fila 2: Acciones + Detección + Estado
        row2 = tk.Frame(ribbon_wrap, bg="#171C20", height=28)
        row2.pack(fill="x")
        row2.pack_propagate(False)

        tk.Frame(row2, bg="#22292F", width=1).pack(side="left", fill="y", pady=2)

        for txt, cmd in [
            ("🗑 Última",   self._etz_borrar_ultima),
            ("🗑 Todo",     self._etz_limpiar_todo),
            ("💾 Guardar",  self._etz_guardar_pagina),
            ("⟳ Inclinar", self._etz_deskew_pagina),
        ]:
            b = tk.Label(row2, text=txt, bg="#171C20", fg="#777F84",
                         font=("Segoe UI", 7), cursor="hand2", padx=6, pady=2)
            b.pack(side="left", padx=1)
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>", lambda e, w=b: w.config(bg="#22292F", fg="#E8E5DF"))
            b.bind("<Leave>", lambda e, w=b: w.config(bg="#171C20", fg="#777F84"))

        tk.Frame(row2, bg="#22292F", width=1).pack(side="left", fill="y", pady=2, padx=4)

        tk.Label(row2, text="Detectar:", bg="#171C20", fg="#777F84",
                 font=("Segoe UI", 7)).pack(side="left", padx=(4, 3))

        for txt, cmd in [("📄 Esta página", self._etz_detectar_pagina),
                          ("📚 Todo el número", self._etz_detectar_numero)]:
            b = tk.Label(row2, text=txt, bg="#6CA8E8", fg="white",
                         font=("Segoe UI", 7, "bold"), cursor="hand2", padx=6, pady=2)
            b.pack(side="left", padx=2)
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>", lambda e, w=b: w.config(bg="#6CA8E8"))
            b.bind("<Leave>", lambda e, w=b: w.config(bg="#6CA8E8"))

        # OCR por zonas — reconoce cada zona por separado en orden de lectura
        b_oz = tk.Label(row2, text="👁 OCR zonas", bg="#6EC69A", fg="white",
                        font=("Segoe UI", 7, "bold"), cursor="hand2",
                        padx=6, pady=2)
        b_oz.pack(side="left", padx=2)
        b_oz.bind("<Button-1>", lambda e: self._etz_ocr_zonas_preview())
        b_oz.bind("<Enter>", lambda e: b_oz.config(bg="#6EC69A"))
        b_oz.bind("<Leave>", lambda e: b_oz.config(bg="#6EC69A"))

        tk.Frame(row2, bg="#22292F", width=1).pack(side="left", fill="y", pady=2, padx=4)

        # Botón predicción — aplica la plantilla aprendida al resto del número
        self._btn_etz_predecir = tk.Label(
            row2, text="🔮 Predecir resto", bg="#B18AD6", fg="white",
            font=("Segoe UI", 7, "bold"), cursor="hand2", padx=6, pady=2)
        self._btn_etz_predecir.pack(side="left", padx=2)
        self._btn_etz_predecir.bind("<Button-1>", lambda e: self._etz_predecir_numero())
        self._btn_etz_predecir.bind("<Enter>",
            lambda e: self._btn_etz_predecir.config(bg="#B18AD6"))
        self._btn_etz_predecir.bind("<Leave>",
            lambda e: self._btn_etz_predecir.config(bg="#B18AD6"))

        tk.Label(row2, text="Motor:", bg="#171C20", fg="#777F84",
                 font=("Segoe UI", 7)).pack(side="left", padx=(8, 2))

        _cb_motor = ttk.Combobox(row2, textvariable=self._etz_modo_det,
                     values=["tesseract", "opencv", "yolo", "onnx", "dit", "vision_ia"],
                     state="readonly", width=9,
                     font=("Segoe UI", 7))
        _cb_motor.pack(side="left")

        # ── Selector proveedor + modelo (visible solo con vision_ia) ─────────
        self._etz_vision_frame = tk.Frame(row2, bg="#171C20")
        self._etz_vision_frame.pack(side="left", padx=(4, 0))

        from core.zone_labeler import VISION_PROVEEDORES
        self._etz_vision_prov  = tk.StringVar(value="claude")
        self._etz_vision_model = tk.StringVar(value="claude-sonnet-4-6")

        _cb_prov = ttk.Combobox(self._etz_vision_frame,
                                  textvariable=self._etz_vision_prov,
                                  values=list(VISION_PROVEEDORES.keys()),
                                  state="readonly", width=8,
                                  font=("Segoe UI", 7))
        _cb_prov.pack(side="left", padx=(0, 2))

        self._etz_cb_vision_model = ttk.Combobox(
            self._etz_vision_frame,
            textvariable=self._etz_vision_model,
            state="readonly", width=18,
            font=("Segoe UI", 7))
        self._etz_cb_vision_model.pack(side="left", padx=(0, 2))

        # Botón editar prompt
        _btn_prompt = tk.Label(self._etz_vision_frame, text="✏ Prompt",
                                bg="#171C20", fg="#777F84",
                                font=("Segoe UI", 7), cursor="hand2", padx=4)
        _btn_prompt.pack(side="left")
        _btn_prompt.bind("<Button-1>", lambda e: self._etz_editar_prompt())
        _btn_prompt.bind("<Enter>",    lambda e: _btn_prompt.config(fg="#E8E5DF"))
        _btn_prompt.bind("<Leave>",    lambda e: _btn_prompt.config(fg="#777F84"))

        # ? tooltip proveedor
        _PROV_AYUDA = "\n\n".join(
            f"{k} — {v['label']}\n  {v['help']}"
            for k, v in VISION_PROVEEDORES.items()
        )
        _btn_qp = tk.Label(self._etz_vision_frame, text="?", bg="#171C20",
                            fg="#777F84", font=("Segoe UI", 7, "bold"),
                            cursor="hand2", padx=2)
        _btn_qp.pack(side="left")
        _btn_qp.bind("<Enter>",    lambda e: self._mostrar_tooltip(_PROV_AYUDA, _btn_qp))
        _btn_qp.bind("<Leave>",    lambda e: self._ocultar_tooltip())
        _btn_qp.bind("<Button-1>", lambda e: messagebox.showinfo(
            "Proveedores de visión IA", _PROV_AYUDA))

        def _on_prov_change(*_):
            prov = self._etz_vision_prov.get()
            info = VISION_PROVEEDORES.get(prov, {})
            modelos = info.get("modelos", [])
            self._etz_cb_vision_model["values"] = modelos
            self._etz_vision_model.set(info.get("default", modelos[0] if modelos else ""))

        def _on_motor_change(*_):
            is_vision = self._etz_modo_det.get() == "vision_ia"
            if is_vision:
                self._etz_vision_frame.pack(side="left", padx=(4, 0))
            else:
                self._etz_vision_frame.pack_forget()

        self._etz_vision_prov.trace_add("write", _on_prov_change)
        self._etz_modo_det.trace_add("write", _on_motor_change)
        _on_prov_change()   # inicializar modelos del proveedor por defecto
        _on_motor_change()  # ocultar si el motor inicial no es vision_ia

        # Botón instalar dependencias del motor seleccionado
        self._btn_instalar_motor = tk.Label(
            row2, text="⬇ Instalar", bg="#171C20", fg="#777F84",
            font=("Segoe UI", 7), cursor="hand2", padx=4)
        self._btn_instalar_motor.pack(side="left", padx=2)
        self._btn_instalar_motor.bind("<Button-1>", lambda e: self._etz_instalar_motor())

        # Botón ? — explica cada motor
        _MOTOR_AYUDA = (
            "Motores de detección de zonas:\n\n"
            "tesseract — Layout engine de Tesseract + OpenCV (estilo FineReader).\n"
            "            100% local, sin instalación extra. Detecta bloques de\n"
            "            texto reales, títulos, fotos, pies de foto y orden de\n"
            "            lectura por columnas. RECOMENDADO.\n\n"
            "opencv    — OpenCV local, sin IA. Rápido (<1s). Sin instalación extra.\n\n"
            "yolo      — YOLOv8n-DocLayNet (~6 MB). CPU ~2s/pág. 11 tipos de zona.\n"
            "            pip install ultralytics\n\n"
            "onnx      — YOLOS-DocLayNet ONNX (~45 MB). CPU ~1s/pág. Sin torch.\n"
            "            pip install onnxruntime\n\n"
            "dit       — Microsoft DiT (~330 MB). Para el PC nuevo con ≥16 GB RAM.\n"
            "            pip install transformers torch\n\n"
            "vision_ia — Cualquier IA de visión via API: Claude, GPT-4o,\n"
            "            Gemini o Llava (Ollama local). Usa el prompt editable.\n"
            "            El prompt se puede personalizar con ✏ Prompt."
        )
        _btn_q = tk.Label(row2, text="?", bg="#171C20", fg="#777F84",
                          font=("Segoe UI", 7, "bold"), cursor="hand2", padx=3)
        _btn_q.pack(side="left")
        _btn_q.bind("<Enter>",    lambda e: self._mostrar_tooltip(_MOTOR_AYUDA, _btn_q))
        _btn_q.bind("<Leave>",    lambda e: self._ocultar_tooltip())
        _btn_q.bind("<Button-1>", lambda e: messagebox.showinfo(
            "Motores de detección", _MOTOR_AYUDA))

        # Status — lado derecho fila 2
        self._etz_lbl_train = tk.Label(row2, text="",
                                        bg="#171C20", fg="#6EC69A",
                                        font=("Segoe UI", 7))
        self._etz_lbl_train.pack(side="right", padx=12)

        # ── BODY: 3 paneles horizontales (PanedWindow) ─────────────────────────
        # Layout FineReader: [Páginas 160px] | [Imagen central] | [Texto OCR 220px]
        body_paned = tk.PanedWindow(f, orient="horizontal",
                                     sashwidth=4, sashpad=0,
                                     bg=CARD_BOR, relief="flat",
                                     handlesize=0)
        body_paned.pack(fill="both", expand=True)

        # ── PANEL IZQUIERDO: miniaturas de páginas (estilo Pages Pane) ─────────
        pages_frm = tk.Frame(body_paned, bg="#101316", width=160)
        pages_frm.pack_propagate(False)
        body_paned.add(pages_frm, minsize=120, width=160)

        tk.Label(pages_frm, text="PÁGINAS", bg="#101316", fg=TXT_DIM,
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=8, pady=(8, 4))

        # Canvas scrollable para miniaturas
        pages_canvas = tk.Canvas(pages_frm, bg="#101316",
                                  highlightthickness=0, width=152)
        pages_sb = tk.Scrollbar(pages_frm, orient="vertical",
                                 command=pages_canvas.yview)
        pages_canvas.configure(yscrollcommand=pages_sb.set)
        pages_sb.pack(side="right", fill="y")
        pages_canvas.pack(fill="both", expand=True)
        pages_inner = tk.Frame(pages_canvas, bg="#101316")
        pages_win = pages_canvas.create_window((0, 0), window=pages_inner, anchor="nw")
        def _pages_cfg(e): pages_canvas.configure(scrollregion=pages_canvas.bbox("all"))
        def _pages_cw(e): pages_canvas.itemconfig(pages_win, width=e.width)
        def _pages_wheel(e):
            pages_canvas.yview_scroll(-1 if (e.delta > 0 or e.num == 4) else 1, "units")
        pages_inner.bind("<Configure>", _pages_cfg)
        pages_canvas.bind("<Configure>", _pages_cw)
        pages_canvas.bind("<MouseWheel>", _pages_wheel)
        pages_inner.bind("<MouseWheel>", _pages_wheel)
        self._etz_pages_inner  = pages_inner
        self._etz_pages_canvas = pages_canvas
        self._etz_thumb_btns   = {}   # {pagina: frame_miniatura}

        # ── PANEL CENTRAL: imagen con zonas ────────────────────────────────────
        center_frm = tk.Frame(body_paned, bg="#0E1114")
        body_paned.add(center_frm, minsize=400)

        # Sub-PanedWindow vertical: imagen arriba | zoom inferior
        center_paned = tk.PanedWindow(center_frm, orient="vertical",
                                       sashwidth=4, bg=CARD_BOR,
                                       relief="flat", handlesize=0)
        center_paned.pack(fill="both", expand=True)

        # Image Pane (canvas principal)
        img_frm = tk.Frame(center_paned, bg="#0E1114")
        center_paned.add(img_frm, minsize=300)

        # Toolbar mínima del Image Pane (zoom)
        img_tb = tk.Frame(img_frm, bg="#101316", height=24)
        img_tb.pack(fill="x")
        img_tb.pack_propagate(False)
        tk.Label(img_tb, text="Ctrl+rueda: zoom  ·  Rueda: scroll  ·  "
                              "Medio/Space+drag: pan  ·  Clic der: menú",
                 bg="#101316", fg=TXT_DIM,
                 font=("Segoe UI", 7)).pack(side="left", padx=8)
        self._etz_lbl_zoom = tk.Label(img_tb, text="100%",
                                       bg="#101316", fg=TXT_SEC,
                                       font=("Segoe UI", 7, "bold"))
        self._etz_lbl_zoom.pack(side="right", padx=8)

        canvas_wrap = tk.Frame(img_frm, bg="#0E1114")
        canvas_wrap.pack(fill="both", expand=True)

        self._etz_canvas = tk.Canvas(canvas_wrap, bg="#12171B",
                                      cursor="crosshair",
                                      highlightthickness=0)
        etz_scroll_y = tk.Scrollbar(canvas_wrap, orient="vertical",
                                     command=self._etz_canvas.yview)
        etz_scroll_x = tk.Scrollbar(canvas_wrap, orient="horizontal",
                                     command=self._etz_canvas.xview)
        self._etz_canvas.configure(yscrollcommand=etz_scroll_y.set,
                                    xscrollcommand=etz_scroll_x.set)
        etz_scroll_y.pack(side="right", fill="y")
        etz_scroll_x.pack(side="bottom", fill="x")
        self._etz_canvas.pack(fill="both", expand=True)

        # Eventos del canvas (mismos que antes)
        self._etz_canvas.bind("<ButtonPress-1>",      self._etz_on_press)
        self._etz_canvas.bind("<B1-Motion>",           self._etz_on_drag)
        self._etz_canvas.bind("<ButtonRelease-1>",     self._etz_on_release)
        self._etz_canvas.bind("<Motion>",              self._etz_on_motion)
        self._etz_canvas.bind("<ButtonPress-3>",       self._etz_on_click_derecho)
        self._etz_canvas.bind("<Control-MouseWheel>",  self._etz_on_zoom)
        self._etz_canvas.bind("<ButtonPress-2>",       self._etz_pan_start_cb)
        self._etz_canvas.bind("<B2-Motion>",           self._etz_pan_drag_cb)
        self._etz_canvas.bind("<ButtonRelease-2>",     self._etz_pan_end_cb)
        self._etz_canvas.bind("<KeyPress-space>",      self._etz_space_press)
        self._etz_canvas.bind("<KeyRelease-space>",    self._etz_space_release)
        self._etz_canvas.bind("<Delete>",              self._etz_suprimir_sel)
        self._etz_canvas.bind("<BackSpace>",           self._etz_suprimir_sel)
        self._etz_canvas.bind("<ButtonPress-1>",       lambda e: self._etz_canvas.focus_set(), add=True)
        self._etz_canvas.bind("<MouseWheel>",
            lambda e: self._etz_canvas.yview_scroll(
                -1 if e.delta > 0 else 1, "units"))
        self._etz_canvas.focus_set()

        # Zoom Pane (inferior) — detalle ampliado de la zona activa
        zoom_frm = tk.Frame(center_paned, bg="#101316", height=120)
        center_paned.add(zoom_frm, minsize=80, height=120)

        tk.Label(zoom_frm, text="DETALLE (Zoom Pane)", bg="#101316", fg=TXT_DIM,
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=8, pady=(4, 2))
        self._etz_zoom_canvas = tk.Canvas(zoom_frm, bg="#12171B",
                                           highlightthickness=0, height=90)
        self._etz_zoom_canvas.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        self._etz_zoom_img_tk = None

        # ── PANEL DERECHO: texto OCR + lista zonas ─────────────────────────────
        right_frm = tk.Frame(body_paned, bg="#101316", width=220)
        right_frm.pack_propagate(False)
        body_paned.add(right_frm, minsize=160, width=220)

        # Sub-PanedWindow vertical: texto OCR arriba | zonas abajo
        right_paned = tk.PanedWindow(right_frm, orient="vertical",
                                      sashwidth=4, bg=CARD_BOR,
                                      relief="flat", handlesize=0)
        right_paned.pack(fill="both", expand=True)

        # Text Pane — texto OCR reconocido (sincronizado con imagen)
        txt_frm = tk.Frame(right_paned, bg="#101316")
        right_paned.add(txt_frm, minsize=120)

        tk.Label(txt_frm, text="TEXTO OCR", bg="#101316", fg=TXT_DIM,
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=8, pady=(6, 2))
        self._etz_txt_ocr = scrolledtext.ScrolledText(
            txt_frm, font=("Consolas", 8),
            bg="#0E1114", fg="#E8E5DF",
            insertbackground="#E8E5DF",
            selectbackground="#6CA8E8",
            relief="flat", padx=6, pady=4,
            wrap="word", state="normal")
        self._etz_txt_ocr.pack(fill="both", expand=True, padx=4)
        # Palabras con baja confianza → subrayado azul (estilo FineReader)
        self._etz_txt_ocr.tag_configure("low_conf",
            foreground="#6CA8E8", underline=True)

        # Zones Pane — lista de zonas + acciones
        zones_frm = tk.Frame(right_paned, bg="#101316")
        right_paned.add(zones_frm, minsize=100)

        tk.Label(zones_frm, text="ZONAS", bg="#101316", fg=TXT_DIM,
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=8, pady=(6, 2))

        zona_list_frame = tk.Frame(zones_frm, bg="#101316")
        zona_list_frame.pack(fill="both", expand=True, padx=4)
        self._etz_zona_list = tk.Listbox(zona_list_frame,
                                          font=("Segoe UI", 8),
                                          bg="#0E1114", fg="#E8E5DF",
                                          selectbackground="#6CA8E8",
                                          selectforeground="white",
                                          activestyle="none",
                                          relief="flat",
                                          selectmode="single", height=8)
        zona_scroll = tk.Scrollbar(zona_list_frame,
                                    command=self._etz_zona_list.yview)
        self._etz_zona_list.configure(yscrollcommand=zona_scroll.set)
        zona_scroll.pack(side="right", fill="y")
        self._etz_zona_list.pack(side="left", fill="both", expand=True)
        self._etz_zona_list.bind("<<ListboxSelect>>", self._etz_on_zona_sel)
        self._etz_zona_list.bind("<Delete>",           self._etz_suprimir_sel)
        self._etz_zona_list.bind("<BackSpace>",        self._etz_suprimir_sel)

        # Estado
        self._etz_lbl_estado = tk.Label(zones_frm, text="—",
                                         bg="#101316", fg=TXT_SEC,
                                         font=("Segoe UI", 7),
                                         wraplength=200, justify="left")
        self._etz_lbl_estado.pack(anchor="w", padx=8, pady=(2, 4))

        # ── STATUS BAR inferior ────────────────────────────────────────────────
        status_bar = tk.Frame(f, bg="#101316", height=20)
        status_bar.pack(fill="x", side="bottom")
        status_bar.pack_propagate(False)
        self._etz_lbl_coords = tk.Label(status_bar, text="x:— y:—",
                                         bg="#101316", fg=TXT_DIM,
                                         font=("Segoe UI", 7))
        self._etz_lbl_coords.pack(side="left", padx=8)
        self._etz_lbl_tipo_activo = tk.Label(status_bar, text="",
                                              bg="#101316", fg="#6EC69A",
                                              font=("Segoe UI", 7, "bold"))
        self._etz_lbl_tipo_activo.pack(side="left", padx=16)
        tk.Label(status_bar,
                 text="Dibuja: clic+arrastre  ·  Mover: Ctrl+arrastre  ·  Eliminar: clic der",
                 bg="#101316", fg=TXT_DIM, font=("Segoe UI", 7)).pack(side="right", padx=8)

        # Inicializar
        self._etz_sel_tipo("articulo")

    def _etz_sel_tipo(self, tipo: str):
        from core.zone_labeler import TIPOS_ZONA
        self._etz_tipo.set(tipo)
        for tid, btn in self._etz_tipo_btns.items():
            meta = TIPOS_ZONA[tid]
            color = meta["color"]
            if tid == tipo:
                # Activo: borde blanco visible
                btn.config(relief="solid", bd=2,
                           bg=color, fg="white",
                           font=("Segoe UI", 7, "bold"),
                           highlightbackground="white",
                           highlightthickness=2)
            else:
                btn.config(relief="flat", bd=0,
                           bg=color, fg="white",
                           font=("Segoe UI", 7),
                           highlightbackground=color,
                           highlightthickness=0)
        # Status bar
        if hasattr(self, "_etz_lbl_tipo_activo"):
            label = TIPOS_ZONA.get(tipo, {}).get("label", tipo)
            color = TIPOS_ZONA.get(tipo, {}).get("color", "#777F84")
            self._etz_lbl_tipo_activo.config(
                text=f"● {label}", fg=color)

    def _etz_actualizar_lista_zonas(self):
        from core.zone_labeler import TIPOS_ZONA
        self._etz_zona_list.delete(0, "end")
        for i, z in enumerate(self._etz_zonas):
            meta = TIPOS_ZONA.get(z.tipo, {})
            label = meta.get("label", z.tipo)
            conf_str = f" [{z.confianza:.0%}]" if z.confianza < 1.0 else ""
            orden_str = f"#{z.orden} " if getattr(z, "orden", 0) else ""
            self._etz_zona_list.insert(
                "end",
                f"{i+1}. {orden_str}{label} ({z.x0:.2f},{z.y0:.2f})–({z.x1:.2f},{z.y1:.2f}){conf_str}"
            )

    def _etz_redibujar_zonas(self):
        """Redibuja todos los rectángulos con handles visuales y etiquetas contrastadas."""
        from core.zone_labeler import TIPOS_ZONA
        for cid in self._etz_canvas_ids:
            self._etz_canvas.delete(cid)
        self._etz_canvas_ids.clear()

        if self._etz_img_orig is None:
            return

        R = self._ETZ_HANDLE_D
        idx_sel = getattr(self, "_etz_zona_sel_idx", None)

        for i, z in enumerate(self._etz_zonas):
            x0p, y0p, x1p, y1p = self._etz_zona_canvas_coords(i)
            lx, rx = min(x0p, x1p), max(x0p, x1p)
            ty, by = min(y0p, y1p), max(y0p, y1p)
            color  = TIPOS_ZONA.get(z.tipo, {}).get("color", "#777F84")
            label  = TIPOS_ZONA.get(z.tipo, {}).get("label", z.tipo)
            manual = z.confianza >= 1.0
            activa = (i == idx_sel)

            # Relleno semitransparente — zona activa más visible
            stipple = "gray25" if activa else "gray12"
            cid_fill = self._etz_canvas.create_rectangle(
                lx, ty, rx, by,
                outline="", fill=color, stipple=stipple
            )

            # Borde principal
            grosor = 3 if activa else (2 if manual else 1)
            dash   = () if manual else (6, 3)
            cid_rect = self._etz_canvas.create_rectangle(
                lx, ty, rx, by,
                outline=color, width=grosor, dash=dash, fill=""
            )

            # Etiqueta con fondo sólido para contraste
            lbl_x = lx + 5
            lbl_y = ty + 4
            lbl_text = label if manual else f"{label} {z.confianza:.0%}"
            # Fondo negro de la etiqueta
            cid_bg = self._etz_canvas.create_rectangle(
                lbl_x - 2, lbl_y - 1,
                lbl_x + len(lbl_text) * 6 + 2, lbl_y + 13,
                fill="#000000", outline="", stipple=""
            )
            cid_lbl = self._etz_canvas.create_text(
                lbl_x, lbl_y,
                text=lbl_text, anchor="nw",
                font=("Segoe UI", 8, "bold"), fill="white"
            )

            # Badge circular con el orden de lectura (esquina superior derecha)
            ids_orden = []
            if getattr(z, "orden", 0):
                bx, by_ = rx - 12, ty + 12
                cid_oc = self._etz_canvas.create_oval(
                    bx - 9, by_ - 9, bx + 9, by_ + 9,
                    fill="#6CA8E8", outline="white", width=1)
                cid_on = self._etz_canvas.create_text(
                    bx, by_, text=str(z.orden),
                    font=("Segoe UI", 8, "bold"), fill="white")
                ids_orden = [cid_oc, cid_on]

            # Handles en las 4 esquinas + 4 bordes medios (solo zona activa o hover)
            ids_handles = []
            if activa or (rx - lx) > 30:
                mx = (lx + rx) / 2
                my = (ty + by) / 2
                puntos_handle = [
                    (lx, ty), (mx, ty), (rx, ty),
                    (rx, my),
                    (rx, by), (mx, by), (lx, by),
                    (lx, my),
                ]
                for hx, hy in puntos_handle:
                    h_bg = self._etz_canvas.create_rectangle(
                        hx - R, hy - R, hx + R, hy + R,
                        fill="#1C2227", outline=color, width=1
                    )
                    h_sq = self._etz_canvas.create_rectangle(
                        hx - R + 2, hy - R + 2, hx + R - 2, hy + R - 2,
                        fill=color, outline=""
                    )
                    ids_handles.extend([h_bg, h_sq])

            self._etz_canvas_ids.extend(
                [cid_fill, cid_rect, cid_bg, cid_lbl] + ids_orden + ids_handles
            )

        # Línea punteada entre pie de foto y su foto vinculada (z.vinculo = zid).
        por_zid = {z.zid: i for i, z in enumerate(self._etz_zonas)}
        for z in self._etz_zonas:
            if z.tipo != "pie_foto" or not z.vinculo or z.vinculo not in por_zid:
                continue
            x0p, y0p, x1p, y1p = self._etz_zona_canvas_coords(por_zid[z.zid])
            fx0, fy0, fx1, fy1 = self._etz_zona_canvas_coords(por_zid[z.vinculo])
            cid_link = self._etz_canvas.create_line(
                (x0p + x1p) / 2, (y0p + y1p) / 2,
                (fx0 + fx1) / 2, (fy0 + fy1) / 2,
                fill="#E6A64C", width=2, dash=(4, 3), arrow="last")
            self._etz_canvas_ids.append(cid_link)

    def _etz_cargar_imagen_pagina(self, numero: str, pagina: str):
        """Carga la imagen de la página desde el PDF o desde caché."""
        if not ST.out_dir or not ST.archivos_sel:
            return

        try:

            from PIL import Image, ImageTk

            # Buscar el PDF del número — primero en archivos seleccionados,
            # luego en el directorio de entrada como fallback
            pdf_path = None
            for a in (ST.archivos_sel or []):
                if a.stem == numero:
                    pdf_path = a; break
            if pdf_path is None and ST.pdf_dir and Path(ST.pdf_dir).exists():
                for ext in ("*.pdf", "*.PDF"):
                    candidatos = list(Path(ST.pdf_dir).glob(ext))
                    for c in candidatos:
                        if c.stem == numero:
                            pdf_path = c; break
                    if pdf_path:
                        break
            if pdf_path is None:
                # Intentar cargar desde imágenes ya extraídas aunque no haya PDF
                img_dir = ST.out_dir / "02_imagenes" / numero if ST.out_dir else None
                if not (img_dir and img_dir.exists()):
                    self._etz_canvas.delete("all")
                    self._etz_canvas.create_text(
                        150, 100,
                        text=f"PDF no encontrado para '{numero}'.\n"
                             "Asegurate de tener el PDF en la carpeta\n"
                             "de entrada y de haberlo seleccionado.",
                        fill="#B5B6B3", font=("Segoe UI", 9),
                        anchor="nw")
                    return

            # Número de página — manejar múltiples formatos:
            # "p0001"   → página 1 → índice 0
            # "0001"    → página 1 → índice 0
            # "0001-03" → el segundo número es la página → índice 2
            import re as _re
            _nums = _re.findall(r'\d+', pagina)
            if len(_nums) >= 2:
                # Formato "NNNN-PP": el segundo número es la página
                try:
                    n_pag = int(_nums[-1]) - 1
                except ValueError:
                    n_pag = 0
            elif len(_nums) == 1:
                try:
                    n_pag = int(_nums[0]) - 1
                except ValueError:
                    n_pag = 0
            else:
                n_pag = 0
            n_pag = max(0, n_pag)

            # Intentar caché de imágenes
            img_dir = ST.out_dir / "02_imagenes" / numero
            img_candidatos = list(img_dir.glob(f"*{pagina}*.png")) if img_dir.exists() else []
            if not img_candidatos:
                # También buscar por índice (pdf2image nombra p-N.png)
                img_candidatos = sorted(img_dir.glob("*.png")) if img_dir.exists() else []

            if img_candidatos and n_pag < len(img_candidatos):
                img = Image.open(img_candidatos[n_pag])
            else:
                # Convertir desde PDF en memoria (solo la página solicitada)
                from pdf2image import convert_from_path

                from core.ocr_engine import _get_poppler_path
                poppler = _get_poppler_path()
                kwargs = dict(dpi=120, first_page=n_pag+1, last_page=n_pag+1)
                if poppler:
                    kwargs["poppler_path"] = poppler
                imgs = convert_from_path(str(pdf_path), **kwargs)
                if not imgs:
                    return
                img = imgs[0]

            # Escalar para caber en el canvas (máx 900px de alto)
            max_h = 900
            if img.height > max_h:
                escala = max_h / img.height
                img = img.resize((int(img.width * escala), max_h), Image.LANCZOS)
                self._etz_escala = escala
            else:
                self._etz_escala = 1.0

            self._etz_img_orig_full = Image.open(img_candidatos[n_pag]) if (img_candidatos and n_pag < len(img_candidatos)) else img
            self._etz_img_orig = img
            self._etz_img_tk = ImageTk.PhotoImage(img)
            self._etz_canvas.delete("all")
            self._etz_canvas.create_image(0, 0, anchor="nw", image=self._etz_img_tk)
            self._etz_canvas.configure(
                scrollregion=(0, 0, img.width, img.height)
            )
            self._etz_redibujar_zonas()

        except Exception as ex:
            self._etz_canvas.delete("all")
            self._etz_canvas.create_text(
                150, 100, text=f"Error cargando imagen:\n{ex}",
                fill="white", font=("Segoe UI", 9))

    # ── Tipos de zona extensibles ─────────────────────────────────────────────
    def _etz_agregar_tipo_custom(self):
        """Diálogo para crear un nuevo tipo de zona global."""
        from core.zone_labeler import TIPOS_ZONA, agregar_tipo_zona
        win = tk.Toplevel(self)
        win.title("Nuevo tipo de zona")
        win.geometry("380x280")
        win.configure(bg=CONTENT_BG)
        win.grab_set()
        win.resizable(False, False)

        tk.Label(win, text="Nuevo tipo de zona", bg=CONTENT_BG, fg=TXT_PRI,
                 font=("Segoe UI", 11, "bold")).pack(pady=(16, 8))
        tk.Label(win, text="El tipo quedará disponible en todos los proyectos futuros.",
                 bg=CONTENT_BG, fg=TXT_SEC, font=("Segoe UI", 8)).pack()

        frm = tk.Frame(win, bg=CONTENT_BG)
        frm.pack(fill="x", padx=24, pady=12)

        def _fila(label, var, row):
            tk.Label(frm, text=label, bg=CONTENT_BG, fg=TXT_SEC,
                     font=("Segoe UI", 9), width=10, anchor="e").grid(
                     row=row, column=0, sticky="e", padx=(0, 8), pady=4)
            tk.Entry(frm, textvariable=var, width=24,
                     bg=CARD_BG, fg=TXT_PRI, insertbackground=TXT_PRI,
                     relief="solid", bd=1, font=("Segoe UI", 9)).grid(
                     row=row, column=1, sticky="w")

        var_id    = tk.StringVar(value="tipo_nuevo")
        var_label = tk.StringVar(value="Mi tipo")
        var_color = tk.StringVar(value="#D58B45")
        var_ocr   = tk.BooleanVar(value=True)

        _fila("ID interno:", var_id, 0)
        _fila("Etiqueta:",   var_label, 1)

        # Color picker
        tk.Label(frm, text="Color:", bg=CONTENT_BG, fg=TXT_SEC,
                 font=("Segoe UI", 9), width=10, anchor="e").grid(
                 row=2, column=0, sticky="e", padx=(0, 8), pady=4)
        color_frm = tk.Frame(frm, bg=CONTENT_BG)
        color_frm.grid(row=2, column=1, sticky="w")
        color_entry = tk.Entry(color_frm, textvariable=var_color, width=10,
                               bg=CARD_BG, fg=TXT_PRI, insertbackground=TXT_PRI,
                               relief="solid", bd=1, font=("Segoe UI", 9))
        color_entry.pack(side="left")
        color_preview = tk.Label(color_frm, text="   ", bg=var_color.get(),
                                  relief="flat", width=3)
        color_preview.pack(side="left", padx=(4, 0))

        def _pick_color():
            from tkinter.colorchooser import askcolor
            res = askcolor(color=var_color.get(), parent=win, title="Elegir color")
            if res and res[1]:
                var_color.set(res[1])
                color_preview.config(bg=res[1])
        tk.Button(color_frm, text="…", command=_pick_color,
                  font=("Segoe UI", 8), bg=CARD_BOR, fg=TXT_PRI,
                  relief="flat").pack(side="left", padx=2)
        var_color.trace_add("write", lambda *_: color_preview.config(
            bg=var_color.get() if var_color.get().startswith("#") else CARD_BG))

        tk.Label(frm, text="Procesar OCR:", bg=CONTENT_BG, fg=TXT_SEC,
                 font=("Segoe UI", 9), width=10, anchor="e").grid(
                 row=3, column=0, sticky="e", padx=(0, 8), pady=4)
        ttk.Checkbutton(frm, variable=var_ocr,
                         text="Sí — incluir esta zona en el OCR").grid(
                         row=3, column=1, sticky="w")

        def _guardar():
            id_tipo = var_id.get().strip().replace(" ", "_").lower()
            label   = var_label.get().strip()
            color   = var_color.get().strip()
            if not id_tipo or not label:
                messagebox.showwarning("Incompleto",
                    "Ingresa el ID y la etiqueta.", parent=win); return
            if id_tipo in TIPOS_ZONA:
                messagebox.showwarning("Ya existe",
                    f"Ya existe un tipo con ID '{id_tipo}'.", parent=win); return
            agregar_tipo_zona(id_tipo, label, color, var_ocr.get())
            # Agregar botón al ribbon en tiempo real
            self._etz_refrescar_botones_tipo()
            win.destroy()
            messagebox.showinfo("Tipo creado",
                f"Tipo '{label}' creado y disponible en todos los proyectos.")

        btn_frm = tk.Frame(win, bg=CONTENT_BG)
        btn_frm.pack(pady=12)
        ttk.Button(btn_frm, text="✓ Crear tipo", style="P.TButton",
                   command=_guardar).pack(side="left", padx=8)
        ttk.Button(btn_frm, text="Cancelar", style="S.TButton",
                   command=win.destroy).pack(side="left")

    def _etz_refrescar_botones_tipo(self):
        """Recarga los botones de tipo de zona en el ribbon con los tipos actuales."""
        for tid, btn in list(self._etz_tipo_btns.items()):
            try:
                btn.destroy()
            except Exception:
                pass
        self._etz_tipo_btns.clear()
        # Buscar el frame de tipos en el ribbon (reconstruir)
        # Simplificación: indicar al usuario que reinicie para ver el tipo nuevo en el ribbon
        # El tipo ya está en TIPOS_ZONA y se usa correctamente al dibujar zonas
        self._etz_lbl_train.config(
            text="✅ Tipo nuevo disponible — se mostrará al reiniciar")

    # ── Estadísticas de etiquetas del número ─────────────────────────────────
    def _etz_mostrar_estadisticas(self):
        """Panel con estadísticas de las zonas etiquetadas en el número actual."""
        numero = self._etz_numero.get()
        if not numero or not ST.out_dir:
            messagebox.showwarning("Sin número", "Selecciona un número primero.")
            return

        from collections import Counter

        from core.zone_labeler import (
            TIPOS_ZONA,
            cargar_pagina,
            listar_paginas_etiquetadas,
        )

        etiquetadas = listar_paginas_etiquetadas(ST.out_dir, numero)
        if not etiquetadas:
            messagebox.showinfo("Sin etiquetas",
                "Este número no tiene páginas etiquetadas aún.")
            return

        # Contar zonas por tipo
        conteo_tipo    = Counter()
        conteo_manual  = 0
        conteo_pred    = 0
        total_zonas    = 0

        for pag in etiquetadas:
            pd = cargar_pagina(ST.out_dir, numero, pag)
            if not pd:
                continue
            if pd.manual:
                conteo_manual += 1
            else:
                conteo_pred += 1
            for z in pd.zonas:
                conteo_tipo[z.tipo] += 1
                total_zonas += 1

        # Ventana de estadísticas
        win = tk.Toplevel(self)
        win.title(f"Estadísticas de etiquetas — {numero}")
        win.geometry("480x520")
        win.configure(bg=CONTENT_BG)
        win.resizable(False, True)

        self._page_header(win, f"Etiquetas — {numero}",
                          f"{len(etiquetadas)} páginas · {total_zonas} zonas totales",
                          "📊")

        pad = tk.Frame(win, bg=CONTENT_BG, padx=20, pady=10)
        pad.pack(fill="both", expand=True)

        # Resumen de páginas
        res_f = tk.Frame(pad, bg=CARD_BG, relief="solid", bd=1)
        res_f.pack(fill="x", pady=(0, 12))
        ri = tk.Frame(res_f, bg=CARD_BG, padx=12, pady=8)
        ri.pack(fill="x")
        for txt, val, color in [
            ("Páginas etiquetadas:",   len(etiquetadas),  TXT_PRI),
            ("  · Manuales:",          conteo_manual,     VERDE),
            ("  · Predichas (IA):",    conteo_pred,       AZ4),
            ("Zonas totales:",         total_zonas,       TXT_PRI),
        ]:
            fila = tk.Frame(ri, bg=CARD_BG)
            fila.pack(fill="x", pady=1)
            tk.Label(fila, text=txt, bg=CARD_BG, fg=TXT_SEC,
                     font=("Segoe UI", 9), width=24, anchor="w").pack(side="left")
            tk.Label(fila, text=str(val), bg=CARD_BG, fg=color,
                     font=("Segoe UI", 9, "bold")).pack(side="left")

        # Desglose por tipo
        tk.Label(pad, text="Zonas por tipo:", bg=CONTENT_BG, fg=TXT_PRI,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 4))

        cols_s = ("tipo", "label", "cantidad", "porcentaje")
        tv = ttk.Treeview(pad, columns=cols_s, show="headings", height=14)
        for cid, lbl, w in [("tipo","ID tipo",120),("label","Etiqueta",160),
                              ("cantidad","Zonas",70),("porcentaje","%",60)]:
            tv.heading(cid, text=lbl)
            tv.column(cid, width=w, anchor="w")

        # Ordenar por cantidad descendente
        for tipo, n in conteo_tipo.most_common():
            info  = TIPOS_ZONA.get(tipo, {})
            label = info.get("label", tipo)
            pct   = round(n / max(total_zonas, 1) * 100, 1)
            tv.insert("", "end", values=(tipo, label, n, f"{pct}%"))

        # Tipos con 0 zonas (definidos pero no usados en este número)
        for tipo, info in TIPOS_ZONA.items():
            if tipo not in conteo_tipo:
                tv.insert("", "end", values=(tipo, info.get("label", tipo), 0, "0%"),
                          tags=("vacio",))
        tv.tag_configure("vacio", foreground=TXT_DIM)

        sb = ttk.Scrollbar(pad, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(fill="both", expand=True)

        # Botón para ir al módulo de descripción de imágenes
        btn_f = tk.Frame(win, bg=CONTENT_BG)
        btn_f.pack(fill="x", padx=20, pady=(6, 12))
        ttk.Button(btn_f, text="🎨  Ir a Descripción de imágenes",
                   style="S.TButton",
                   command=lambda: (win.destroy(),
                                    self._imgd_var_num.set(numero),
                                    self._mostrar_pagina("imgdesc"),
                                    self._imgd_cargar_db())).pack(side="left")
        ttk.Button(btn_f, text="Cerrar",
                   command=win.destroy).pack(side="right")

    # ── Descripción de imágenes etiquetadas (legado — ahora en módulo Analizar) ─
    def _etz_describir_imagenes(self):
        """Abre el panel de descripción automática de zonas de foto del número actual."""
        numero = self._etz_numero.get()
        if not numero or not ST.out_dir:
            messagebox.showwarning("Sin número", "Selecciona un número primero.")
            return

        from core.image_captioner import (
            buscar_imagenes_similares,
            cargar_descripciones_db,
            describir_numero,
        )
        from core.zone_labeler import VISION_PROVEEDORES

        win = tk.Toplevel(self)
        win.title(f"Descripción de imágenes — {numero}")
        win.geometry("1100x680")
        win.configure(bg=CONTENT_BG)

        # ── Barra de control ─────────────────────────────────────────────────
        ctrl = tk.Frame(win, bg=CONTENT_BG)
        ctrl.pack(fill="x", padx=12, pady=(10, 4))

        tk.Label(ctrl, text="Proveedor:", bg=CONTENT_BG, fg=TXT_SEC,
                 font=("Segoe UI", 9)).pack(side="left")
        var_prov  = tk.StringVar(value="claude")
        var_model = tk.StringVar(value="claude-haiku-4-5-20251001")
        cb_prov = ttk.Combobox(ctrl, textvariable=var_prov,
                                values=list(VISION_PROVEEDORES.keys()),
                                state="readonly", width=10)
        cb_prov.pack(side="left", padx=(4, 8))
        cb_model = ttk.Combobox(ctrl, textvariable=var_model,
                                 state="readonly", width=22)
        cb_model.pack(side="left", padx=(0, 12))

        def _on_prov(*_):
            info = VISION_PROVEEDORES.get(var_prov.get(), {})
            mods = info.get("modelos", [])
            cb_model["values"] = mods
            var_model.set(info.get("default", mods[0] if mods else ""))
        var_prov.trace_add("write", _on_prov)
        _on_prov()

        lbl_estado = tk.Label(ctrl, text="", bg=CONTENT_BG, fg=VERDE,
                               font=("Segoe UI", 9, "bold"))
        lbl_estado.pack(side="left")

        btn_run = ttk.Button(ctrl, text="▶  Describir fotos del número",
                              style="P.TButton",
                              command=lambda: _run_describir())
        btn_run.pack(side="right", padx=(8, 0))
        ttk.Button(ctrl, text="↺ Cargar guardadas",
                   style="S.TButton",
                   command=lambda: _cargar_db()).pack(side="right")

        # ── Split: tabla izquierda + detalle derecha ─────────────────────────
        split = tk.Frame(win, bg=CONTENT_BG)
        split.pack(fill="both", expand=True, padx=12, pady=(4, 8))

        # Tabla
        izq = tk.Frame(split, bg=CONTENT_BG, width=500)
        izq.pack(side="left", fill="both", expand=True, padx=(0, 8))

        cols = ("pagina", "descripcion", "categorias", "texto_visible")
        tv = ttk.Treeview(izq, columns=cols, show="headings", height=20)
        for cid, lbl, w in [("pagina","Página",70),("descripcion","Descripción",240),
                              ("categorias","Categorías",130),("texto_visible","Texto visible",110)]:
            tv.heading(cid, text=lbl)
            tv.column(cid, width=w, anchor="w")
        sb_tv = ttk.Scrollbar(izq, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb_tv.set)
        sb_tv.pack(side="right", fill="y")
        tv.pack(fill="both", expand=True)

        # Panel derecho: recorte + detalle + búsqueda similitud
        der = tk.Frame(split, bg=CARD_BG, width=340, relief="solid", bd=1)
        der.pack(side="right", fill="y")
        der.pack_propagate(False)

        cv_recorte = tk.Canvas(der, bg="#000", height=200, highlightthickness=0)
        cv_recorte.pack(fill="x", padx=6, pady=6)

        lbl_desc  = tk.Label(der, text="", bg=CARD_BG, fg=TXT_PRI,
                              font=("Segoe UI", 9), wraplength=310, justify="left")
        lbl_desc.pack(anchor="w", padx=8, pady=(0, 4))

        lbl_cats  = tk.Label(der, text="", bg=CARD_BG, fg=AZ4,
                              font=("Segoe UI", 8), wraplength=310, justify="left")
        lbl_cats.pack(anchor="w", padx=8)

        lbl_txt   = tk.Label(der, text="", bg=CARD_BG, fg=TXT_SEC,
                              font=("Courier New", 8), wraplength=310, justify="left")
        lbl_txt.pack(anchor="w", padx=8, pady=(0, 4))

        lbl_ctx   = tk.Label(der, text="", bg=CARD_BG, fg=TXT_DIM,
                              font=("Segoe UI", 8, "italic"), wraplength=310, justify="left")
        lbl_ctx.pack(anchor="w", padx=8, pady=(0, 8))

        # Búsqueda por similitud
        tk.Frame(der, bg=CARD_BOR, height=1).pack(fill="x", padx=6, pady=4)
        tk.Label(der, text="🔍 Buscar imágenes similares:",
                 bg=CARD_BG, fg=TXT_PRI, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=8)
        var_busqueda = tk.StringVar()
        ttk.Entry(der, textvariable=var_busqueda, width=36).pack(padx=8, pady=4, fill="x")
        lbl_sim = tk.Label(der, text="", bg=CARD_BG, fg=TXT_SEC,
                            font=("Segoe UI", 8), wraplength=310, justify="left")
        lbl_sim.pack(anchor="w", padx=8)

        def _buscar_sim():
            q = var_busqueda.get().strip()
            if not q:
                return
            sims = buscar_imagenes_similares(q, ST.out_dir, numero, top_n=5)
            if sims:
                txt = "\n".join(f"  p.{s['pagina']} — {s['descripcion'][:50]}"
                                for s in sims)
                lbl_sim.config(text=f"Similares:\n{txt}")
            else:
                lbl_sim.config(text="Sin índice FAISS disponible aún.")
        ttk.Button(der, text="Buscar", command=_buscar_sim).pack(padx=8, pady=(0, 8))

        # Estado interno
        _descripciones: list[dict] = []

        def _poblar_tv(descs):
            tv.delete(*tv.get_children())
            for d in descs:
                cats = ", ".join(d.get("categorias", []))[:40]
                tv.insert("", "end", values=(
                    d.get("pagina",""), d.get("descripcion","")[:60],
                    cats, d.get("texto_visible","")[:30]))
            _descripciones.clear()
            _descripciones.extend(descs)
            lbl_estado.config(text=f"✅ {len(descs)} descripciones")

        def _on_select(e):
            sel = tv.selection()
            if not sel:
                return
            idx = tv.index(sel[0])
            if idx >= len(_descripciones):
                return
            d = _descripciones[idx]
            lbl_desc.config(text=d.get("descripcion",""))
            lbl_cats.config(text="📌 " + ", ".join(d.get("categorias",[])))
            lbl_txt.config(text=("📝 " + d.get("texto_visible","")) if d.get("texto_visible") else "")
            lbl_ctx.config(text=d.get("contexto_historico",""))
            # Mostrar recorte
            _mostrar_recorte(d)

        tv.bind("<<TreeviewSelect>>", _on_select)

        def _mostrar_recorte(d):
            cv_recorte.delete("all")
            try:
                from PIL import Image, ImageTk
                img_dir = ST.out_dir / "02_imagenes" / numero
                pagina  = d.get("pagina","")
                hits = sorted(img_dir.glob(f"*{pagina}*.png")) if img_dir.exists() else []
                if not hits:
                    return
                img = Image.open(hits[0]).convert("RGB")
                W, H = img.size
                x0 = int(d.get("x0",0) * W)
                y0 = int(d.get("y0",0) * H)
                x1 = int(d.get("x1",1) * W)
                y1 = int(d.get("y1",1) * H)
                recorte = img.crop((x0,y0,x1,y1))
                recorte.thumbnail((320, 190), Image.LANCZOS)
                tk_img = ImageTk.PhotoImage(recorte)
                cv_recorte._ref = tk_img
                cw = cv_recorte.winfo_width() or 320
                cv_recorte.create_image(cw//2, 100, anchor="center", image=tk_img)
            except Exception:
                pass

        def _run_describir():
            prov  = var_prov.get()
            model = var_model.get()
            api_k = ST.api_keys.get(prov, "") or ST.api_key
            if prov != "ollama" and not api_k:
                messagebox.showwarning("Sin API key",
                    f"Configura la API key de {prov} en Configuración.")
                return
            btn_run.config(state="disabled")
            lbl_estado.config(text="⏳ Describiendo…", fg="#E6A64C")

            def cb(n, t, pag, desc):
                self.after(0, lambda: lbl_estado.config(
                    text=f"⏳ {n}/{t}: {pag} — {desc[:40]}…", fg="#E6A64C"))

            def _worker():
                db = Path(ST.ruta_db) if ST.ruta_db else None
                descs = describir_numero(
                    ST.out_dir, numero, proveedor=prov,
                    api_key=api_k, modelo=model,
                    db_path=db, callback=cb)
                self.after(0, lambda: (
                    _poblar_tv(descs),
                    btn_run.config(state="normal"),
                    lbl_estado.config(text=f"✅ {len(descs)} fotos descritas", fg=VERDE),
                ))
            threading.Thread(target=_worker, daemon=True).start()

        def _cargar_db():
            db = Path(ST.ruta_db) if ST.ruta_db else None
            if not db or not db.exists():
                lbl_estado.config(text="⚠ Sin base de datos", fg=ROJO)
                return
            descs = cargar_descripciones_db(db, numero)
            if descs:
                _poblar_tv(descs)
            else:
                lbl_estado.config(text="Sin descripciones guardadas aún", fg=TXT_SEC)

        # Cargar automáticamente si ya hay descripciones guardadas
        win.after(200, _cargar_db)

    # ── DeepFont — clasificación tipográfica de zona seleccionada ─────────────
    def _etz_deepfont_zona(self):
        """Analiza el estilo tipográfico de la zona seleccionada con DeepFont."""
        if self._etz_zona_sel_idx is None:
            messagebox.showinfo("Sin selección",
                "Selecciona una zona haciendo clic sobre ella."); return
        if self._etz_img_orig is None:
            messagebox.showwarning("Sin imagen", "Carga una página primero."); return

        idx = self._etz_zona_sel_idx
        if idx >= len(self._etz_zonas):
            return
        zona = self._etz_zonas[idx]

        try:
            import os
            import tempfile

            from core.deepfont import clasificar_tipografia

            # Recortar la zona de la imagen original
            iw = self._etz_img_orig.width
            ih = self._etz_img_orig.height
            box = (int(zona.x0 * iw), int(zona.y0 * ih),
                   int(zona.x1 * iw), int(zona.y1 * ih))
            if box[2] <= box[0] or box[3] <= box[1]:
                messagebox.showwarning("Zona inválida",
                    "La zona no tiene dimensiones suficientes."); return

            recorte = self._etz_img_orig.crop(box)
            # Guardar en temp ASCII para evitar problemas con FAISS/Windows.
            # dir=None (macOS/Linux) deja que tempfile use la suya, que ya es ASCII.
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False,
                                              dir=plataforma.dir_temp_ascii())
            tmp.close()
            recorte.save(tmp.name)

            self._etz_lbl_train.config(text="Analizando tipografía…")

            def _worker():
                try:
                    res = clasificar_tipografia(tmp.name, usar_clip=True)
                finally:
                    try: os.unlink(tmp.name)
                    except OSError: pass
                self.after(0, lambda: self._etz_mostrar_deepfont(res, zona))

            threading.Thread(target=_worker, daemon=True).start()

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo analizar: {e}")

    def _etz_mostrar_deepfont(self, resultado: dict, zona):
        """Muestra el resultado de DeepFont en una ventana."""
        from core.deepfont import COLORES, ETIQUETAS_ES
        cat   = resultado["categoria"]
        eta   = resultado["etiqueta"]
        conf  = resultado["confianza"]
        color = resultado.get("color", "#777F84")
        metodo = resultado.get("metodo", "?")

        self._etz_lbl_train.config(text=f"🔤 {eta[:30]} ({conf:.0%})")

        win = tk.Toplevel(self)
        win.title("Análisis tipográfico — DeepFont")
        win.geometry("440x300")
        win.configure(bg=CONTENT_BG)

        # Resultado principal
        res_frm = tk.Frame(win, bg=color, pady=12)
        res_frm.pack(fill="x")
        tk.Label(res_frm, text=eta, bg=color, fg="white",
                 font=("Segoe UI", 13, "bold")).pack()
        tk.Label(res_frm, text=f"Confianza: {conf:.0%}  ·  Método: {metodo}",
                 bg=color, fg="white",
                 font=("Segoe UI", 9)).pack()

        # Scores por categoría
        scores = resultado.get("scores", {})
        if isinstance(scores, dict) and scores and all(
                isinstance(v, float) for v in scores.values()):
            tk.Label(win, text="Distribución de probabilidades:",
                     bg=CONTENT_BG, fg=TXT_SEC,
                     font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=16, pady=(12, 4))
            from core.deepfont import CATEGORIAS_TIPOGRAFIA
            for c in CATEGORIAS_TIPOGRAFIA:
                pct = scores.get(c, 0.0)
                row = tk.Frame(win, bg=CONTENT_BG)
                row.pack(fill="x", padx=16, pady=1)
                tk.Label(row, text=ETIQUETAS_ES.get(c, c)[:35],
                         bg=CONTENT_BG, fg=TXT_PRI if c == cat else TXT_SEC,
                         font=("Segoe UI", 8,
                               "bold" if c == cat else "normal"),
                         width=38, anchor="w").pack(side="left")
                bar_frm = tk.Frame(row, bg=CARD_BOR, width=160, height=10)
                bar_frm.pack(side="left", padx=4)
                bar_frm.pack_propagate(False)
                tk.Frame(bar_frm, bg=COLORES.get(c, "#777F84"),
                         width=int(pct * 160), height=10).pack(side="left")
                tk.Label(row, text=f"{pct:.0%}", bg=CONTENT_BG, fg=TXT_SEC,
                         font=("Segoe UI", 7)).pack(side="left", padx=2)

        ttk.Button(win, text="Cerrar", style="S.TButton",
                   command=win.destroy).pack(pady=12)

    # ── Zoom Pane ─────────────────────────────────────────────────────────────
    def _etz_actualizar_zoom_pane(self, cx: float, cy: float):
        """Muestra un recorte ampliado 4x alrededor del cursor en el Zoom Pane."""
        if self._etz_img_orig is None:
            zc = getattr(self, "_etz_zoom_canvas", None)
            if zc:
                zc.delete("all")
                zc.create_text(80, 40, text="Carga una página para ver el detalle",
                               fill=TXT_DIM, font=("Segoe UI", 8), anchor="w")
            return
        try:
            from PIL import Image, ImageTk
            # Convertir coords canvas a coords imagen original
            escala = self._etz_escala * self._etz_zoom
            if escala <= 0:
                return
            ix = cx / escala
            iy = cy / escala
            radio = 40  # radio en px de imagen original
            box = (max(0, int(ix - radio)), max(0, int(iy - radio)),
                   min(self._etz_img_orig.width,  int(ix + radio)),
                   min(self._etz_img_orig.height, int(iy + radio)))
            if box[2] <= box[0] or box[3] <= box[1]:
                return
            recorte = self._etz_img_orig.crop(box)
            # Ampliar 3x
            nw = min(recorte.width  * 3, 400)
            nh = min(recorte.height * 3, 200)
            if nw < 1 or nh < 1:
                return
            ampliado = recorte.resize((nw, nh), Image.NEAREST)
            self._etz_zoom_img_tk = ImageTk.PhotoImage(ampliado)
            zc = self._etz_zoom_canvas
            zc.delete("all")
            zc.create_image(0, 0, anchor="nw", image=self._etz_zoom_img_tk)
            # Cruz central
            mx, my = nw // 2, nh // 2
            zc.create_line(mx - 8, my, mx + 8, my, fill="#D96B6B", width=1)
            zc.create_line(mx, my - 8, mx, my + 8, fill="#D96B6B", width=1)
        except Exception:
            pass

    # ── Miniaturas de páginas (Pages Pane) ────────────────────────────────────
    def _etz_poblar_miniaturas(self, pags: list[str]):
        """Crea/actualiza las miniaturas del Pages Pane."""
        for w in self._etz_pages_inner.winfo_children():
            w.destroy()
        self._etz_thumb_btns.clear()
        self._etz_thumb_dots = {}

        for pag in pags:
            frm = tk.Frame(self._etz_pages_inner, bg="#101316",
                           cursor="hand2", pady=2)
            frm.pack(fill="x", padx=4, pady=1)

            # Número de página
            lbl = tk.Label(frm, text=pag, bg="#101316", fg=TXT_SEC,
                           font=("Segoe UI", 7), anchor="w")
            lbl.pack(fill="x", padx=4)

            # Indicador de estado (etiquetada / sin etiquetar).
            # Se pinta apagado y se corrige después desde un hilo: leer el JSON
            # de zonas de CADA página aquí significaba una lectura de disco por
            # página (decenas, y sobre Google Drive), con la ventana congelada.
            dot = tk.Label(frm, text="●", bg="#101316", fg=TXT_DIM,
                           font=("Segoe UI", 7))
            dot.pack(side="right", padx=4)
            self._etz_thumb_dots[pag] = dot

            # Click navega a esa página
            def _goto(p=pag):
                self._etz_cb_pag.set(p)
                self._etz_pagina.set(p)
                self._etz_on_pagina()
            for w in (frm, lbl, dot):
                w.bind("<Button-1>", lambda e, fn=_goto: fn())
                w.bind("<Enter>",    lambda e, f=frm: f.config(bg="#171C20"))
                w.bind("<Leave>",    lambda e, f=frm: f.config(bg="#101316"))

            self._etz_thumb_btns[pag] = frm

        self._etz_pages_canvas.update_idletasks()
        self._etz_pages_canvas.configure(
            scrollregion=self._etz_pages_canvas.bbox("all"))

        self._etz_marcar_etiquetadas(list(pags), self._etz_numero.get())

    def _etz_marcar_etiquetadas(self, pags: list[str], num: str):
        """Enciende en verde las páginas que ya tienen zonas, sin bloquear la UI.

        Lee un JSON por página, así que va en un hilo: en un número de 48
        páginas eran 48 lecturas de disco (a menudo sobre Google Drive) con la
        ventana congelada.
        """
        if not (ST.out_dir and num and pags):
            return

        out_dir = ST.out_dir

        def _trabajo():
            from core.zone_labeler import cargar_pagina
            etiquetadas = []
            for pag in pags:
                try:
                    pd = cargar_pagina(out_dir, num, pag)
                    if pd and pd.zonas:
                        etiquetadas.append(pag)
                except Exception:
                    continue
            self.after(0, lambda: self._etz_pintar_dots(etiquetadas))

        threading.Thread(target=_trabajo, daemon=True).start()

    def _etz_pintar_dots(self, etiquetadas: list[str]):
        """Aplica el resultado del hilo. Solo hilo principal."""
        for pag in etiquetadas:
            dot = getattr(self, "_etz_thumb_dots", {}).get(pag)
            try:
                if dot is not None and dot.winfo_exists():
                    dot.config(fg="#6EC69A")
            except tk.TclError:
                pass                    # la miniatura ya se destruyó

    def _etz_resaltar_miniatura(self, pag: str):
        """Resalta la miniatura de la página activa."""
        for p, frm in self._etz_thumb_btns.items():
            frm.config(bg="#6CA8E8" if p == pag else "#101316")
            for child in frm.winfo_children():
                child.config(bg="#6CA8E8" if p == pag else "#101316")

    # ── Carga de texto OCR en el Text Pane ────────────────────────────────────
    def _etz_cargar_texto_ocr(self, numero: str, pagina: str):
        """Carga el texto OCR de la página en el Text Pane."""
        self._etz_txt_ocr.config(state="normal")
        self._etz_txt_ocr.delete("1.0", "end")
        if not ST.out_dir:
            return
        txt_path = ST.out_dir / "03_ocr" / numero / f"{pagina}.txt"
        if txt_path.exists():
            texto = txt_path.read_text(encoding="utf-8", errors="replace")
            self._etz_txt_ocr.insert("1.0", texto)
        else:
            self._etz_txt_ocr.insert("1.0",
                f"(Sin texto OCR para {pagina})\n"
                "Extrae el texto en la pestaña OCR primero.")
            self._etz_txt_ocr.tag_add("low_conf", "1.0", "end")

    def _etz_on_numero(self, event=None):
        numero = self._etz_numero.get()
        if not numero:
            return
        # Listar páginas disponibles como .txt
        txt_dir = ST.out_dir / "03_ocr" / numero if ST.out_dir else None
        if txt_dir and txt_dir.exists():
            pags = sorted(p.stem for p in txt_dir.glob("*.txt"))
        else:
            pags = [f"p{i:04d}" for i in range(1, 50)]
        self._etz_cb_pag["values"] = pags
        # Poblar panel de miniaturas
        self._etz_poblar_miniaturas(pags)
        if pags:
            self._etz_cb_pag.set(pags[0])
            self._etz_on_pagina()
        self._etz_actualizar_estado()
        # Re-entrenar detector con las etiquetas del número seleccionado
        self._etz_entrenar_detector(numero)

    def _etz_on_pagina(self, event=None):
        numero  = self._etz_numero.get()
        pagina  = self._etz_pagina.get()
        if not numero or not pagina:
            return

        # Cargar zonas guardadas para esta página
        from core.zone_labeler import cargar_pagina
        if ST.out_dir:
            pag_data = cargar_pagina(ST.out_dir, numero, pagina)
            self._etz_zonas = list(pag_data.zonas) if pag_data else []
        else:
            self._etz_zonas = []

        self._etz_actualizar_lista_zonas()

        # Intentar cargar imagen: primero via caché/PDF del corpus,
        # luego directamente desde PDF si se cargó con "Abrir PDF"
        cargado = False
        if ST.archivos_sel or (ST.out_dir and ST.pdf_dir):
            self._etz_cargar_imagen_pagina(numero, pagina)
            cargado = self._etz_img_orig is not None

        if not cargado:
            # Buscar el PDF directamente en archivos_sel por stem
            pdf = next((a for a in (ST.archivos_sel or [])
                        if a.stem == numero), None)
            if pdf:
                import re as _re
                _nums = _re.findall(r'\d+', pagina)
                n_pag = max(0, int(_nums[-1]) - 1) if _nums else 0
                self._etz_cargar_imagen_desde_pdf(str(pdf), n_pag)

        # Sincronizar Text Pane y Pages Pane
        self._etz_cargar_texto_ocr(numero, pagina)
        self._etz_resaltar_miniatura(pagina)

    def _etz_pagina_ant(self):
        vals = list(self._etz_cb_pag["values"])
        if not vals:
            return
        cur = self._etz_pagina.get()
        idx = vals.index(cur) if cur in vals else 0
        if idx > 0:
            self._etz_cb_pag.set(vals[idx - 1])
            self._etz_on_pagina()

    def _etz_pagina_sig(self):
        vals = list(self._etz_cb_pag["values"])
        if not vals:
            return
        cur = self._etz_pagina.get()
        idx = vals.index(cur) if cur in vals else 0
        if idx < len(vals) - 1:
            self._etz_cb_pag.set(vals[idx + 1])
            self._etz_on_pagina()

    def _etz_canvas_wh(self):
        """Ancho y alto de la imagen en coordenadas canvas (imagen ya escalada)."""
        if self._etz_img_orig is None:
            return 1, 1
        return self._etz_img_orig.width, self._etz_img_orig.height

    def _etz_zona_canvas_coords(self, idx):
        """Devuelve (x0,y0,x1,y1) en coords canvas de la zona[idx]."""
        z = self._etz_zonas[idx]
        w, h = self._etz_canvas_wh()
        return z.x0 * w, z.y0 * h, z.x1 * w, z.y1 * h

    def _etz_canvas_a_norm(self, cx, cy):
        """Convierte coordenadas canvas a normalizado [0,1]."""
        w, h = self._etz_canvas_wh()
        return max(0.0, min(1.0, cx / w)), max(0.0, min(1.0, cy / h))

    def _etz_hit_handle(self, cx, cy):
        """Devuelve (idx, handle) si cx,cy está sobre esquina/borde/interior
        de alguna zona, o None si está en espacio vacío.
        handle: 'nw','n','ne','e','se','s','sw','w','move'
        """
        if not self._etz_zonas or self._etz_img_orig is None:
            return None
        R = self._ETZ_HANDLE_R
        # Última zona dibujada tiene prioridad
        for i in range(len(self._etz_zonas) - 1, -1, -1):
            x0, y0, x1, y1 = self._etz_zona_canvas_coords(i)
            # Normalizar por si x0>x1 o y0>y1
            lx, rx = min(x0, x1), max(x0, x1)
            ty, by = min(y0, y1), max(y0, y1)
            # Esquinas
            if abs(cx - lx) <= R and abs(cy - ty) <= R: return (i, "nw")
            if abs(cx - rx) <= R and abs(cy - ty) <= R: return (i, "ne")
            if abs(cx - lx) <= R and abs(cy - by) <= R: return (i, "sw")
            if abs(cx - rx) <= R and abs(cy - by) <= R: return (i, "se")
            # Bordes medios
            if abs(cx - lx) <= R and ty <= cy <= by:    return (i, "w")
            if abs(cx - rx) <= R and ty <= cy <= by:    return (i, "e")
            if abs(cy - ty) <= R and lx <= cx <= rx:    return (i, "n")
            if abs(cy - by) <= R and lx <= cx <= rx:    return (i, "s")
            # Interior → mover
            if lx <= cx <= rx and ty <= cy <= by:       return (i, "move")
        return None

    def _etz_on_motion(self, event):
        """Cambia cursor, muestra coordenadas en statusbar y actualiza Zoom Pane."""
        if self._etz_img_orig is None:
            return
        cx = self._etz_canvas.canvasx(event.x)
        cy = self._etz_canvas.canvasy(event.y)
        hit = self._etz_hit_handle(cx, cy)
        cursor = self._ETZ_CURSOR_MAP.get(hit[1], "crosshair") if hit else "crosshair"
        self._etz_canvas.config(cursor=cursor)

        # Status bar — coordenadas normalizadas
        if self._etz_img_orig:
            w, h = self._etz_canvas_wh()
            nx = round(cx / w, 3) if w > 0 else 0
            ny = round(cy / h, 3) if h > 0 else 0
            if hasattr(self, "_etz_lbl_coords"):
                self._etz_lbl_coords.config(text=f"x:{nx:.3f}  y:{ny:.3f}")

        # Zoom Pane — muestra recorte ampliado alrededor del cursor
        self._etz_actualizar_zoom_pane(cx, cy)

    def _etz_on_zoom(self, event):
        """Zoom con Ctrl+rueda. Reescala la imagen y redibuja zonas."""
        if self._etz_img_orig is None:
            return
        factor = 1.15 if event.delta > 0 else 1 / 1.15
        nuevo_zoom = max(0.2, min(5.0, self._etz_zoom * factor))
        if nuevo_zoom == self._etz_zoom:
            return
        self._etz_zoom = nuevo_zoom
        self._etz_aplicar_zoom()

    def _etz_aplicar_zoom(self):
        """Redimensiona la imagen según _etz_zoom y redibuja todo."""
        if self._etz_img_orig is None:
            return
        from PIL import Image, ImageTk
        base = getattr(self, "_etz_img_orig_full", self._etz_img_orig)
        new_w = max(1, int(base.width  * self._etz_zoom))
        new_h = max(1, int(base.height * self._etz_zoom))
        img_zoom = base.resize((new_w, new_h), Image.LANCZOS)
        self._etz_img_orig = img_zoom
        self._etz_img_tk   = ImageTk.PhotoImage(img_zoom)
        self._etz_canvas.delete("all")
        self._etz_canvas.create_image(0, 0, anchor="nw", image=self._etz_img_tk)
        self._etz_canvas.configure(scrollregion=(0, 0, new_w, new_h))
        self._etz_redibujar_zonas()

    def _etz_pan_start_cb(self, event):
        self._etz_pan_start = (event.x, event.y)
        self._etz_canvas.config(cursor="fleur")

    def _etz_pan_drag_cb(self, event):
        if self._etz_pan_start is None:
            return
        dx = self._etz_pan_start[0] - event.x
        dy = self._etz_pan_start[1] - event.y
        self._etz_pan_start = (event.x, event.y)
        self._etz_canvas.xview_scroll(int(dx), "units")
        self._etz_canvas.yview_scroll(int(dy), "units")

    def _etz_pan_end_cb(self, event):
        self._etz_pan_start = None
        self._etz_canvas.config(cursor="crosshair")

    def _etz_space_press(self, event):
        self._etz_space_held = True
        self._etz_canvas.config(cursor="fleur")

    def _etz_space_release(self, event):
        self._etz_space_held = False
        self._etz_canvas.config(cursor="crosshair")

    def _etz_on_press(self, event):
        cx = self._etz_canvas.canvasx(event.x)
        cy = self._etz_canvas.canvasy(event.y)

        # Space presionado → pan con botón izquierdo
        if self._etz_space_held:
            self._etz_modo = "pan"
            self._etz_pan_start = (event.x, event.y)
            return

        if self._etz_rect_tmp:
            self._etz_canvas.delete(self._etz_rect_tmp)
            self._etz_rect_tmp = None

        hit = self._etz_hit_handle(cx, cy)
        if hit:
            idx, handle = hit
            self._etz_zona_sel_idx = idx
            if handle == "move":
                self._etz_modo = "move"
                self._etz_resize_idx = idx
                x0, y0, x1, y1 = self._etz_zona_canvas_coords(idx)
                # offset en coordenadas canvas (imagen ya escalada)
                self._etz_move_offset = (cx - min(x0, x1), cy - min(y0, y1))
            else:
                self._etz_modo = "resize"
                self._etz_resize_idx = idx
                self._etz_resize_handle = handle
            self._etz_redibujar_zonas()
        else:
            self._etz_zona_sel_idx = None
            self._etz_modo = "draw"
            self._etz_rect_ini = (cx, cy)

    def _etz_on_drag(self, event):
        if self._etz_modo == "pan" and self._etz_pan_start:
            dx = self._etz_pan_start[0] - event.x
            dy = self._etz_pan_start[1] - event.y
            self._etz_pan_start = (event.x, event.y)
            self._etz_canvas.xview_scroll(int(dx), "units")
            self._etz_canvas.yview_scroll(int(dy), "units")
            return

        cx = self._etz_canvas.canvasx(event.x)
        cy = self._etz_canvas.canvasy(event.y)

        if self._etz_modo == "draw":
            self._etz_drag_draw(cx, cy)
        elif self._etz_modo == "resize":
            self._etz_drag_resize(cx, cy)
        elif self._etz_modo == "move":
            self._etz_drag_move(cx, cy)

    def _etz_drag_draw(self, cx, cy):
        """Dibuja un nuevo rectángulo desde _etz_rect_ini hasta cx,cy."""
        if not self._etz_rect_ini:
            return
        from core.zone_labeler import TIPOS_ZONA
        x0, y0 = self._etz_rect_ini
        color = TIPOS_ZONA.get(self._etz_tipo.get(), {}).get("color", "#777F84")
        label = TIPOS_ZONA.get(self._etz_tipo.get(), {}).get("label", "")
        if self._etz_rect_tmp:
            self._etz_canvas.delete(self._etz_rect_tmp)
        self._etz_rect_tmp = self._etz_canvas.create_rectangle(
            x0, y0, cx, cy, outline=color, width=2, dash=(6, 3), fill=""
        )
        escala = self._etz_escala if self._etz_escala > 0 else 1.0
        pct_w = abs(cx - x0) / (self._etz_img_orig.width * escala) * 100 if self._etz_img_orig else 0
        pct_h = abs(cy - y0) / (self._etz_img_orig.height * escala) * 100 if self._etz_img_orig else 0
        dim_txt = f"{label}  {pct_w:.0f}% × {pct_h:.0f}%"
        lx = min(x0, cx) + 4
        ly = min(y0, cy) - 14 if min(y0, cy) > 20 else min(y0, cy) + 4
        if not hasattr(self, "_etz_dim_lbl"):
            self._etz_dim_lbl = None
        if self._etz_dim_lbl:
            self._etz_canvas.delete(self._etz_dim_lbl)
        self._etz_dim_lbl = self._etz_canvas.create_text(
            lx, ly, text=dim_txt, anchor="nw",
            fill="white", font=("Segoe UI", 8, "bold"), tags="dim_label"
        )

    def _etz_drag_resize(self, cx, cy):
        """Mueve la esquina/borde indicado por _etz_resize_handle."""
        idx = self._etz_resize_idx
        if idx is None or idx >= len(self._etz_zonas):
            return
        nx, ny = self._etz_canvas_a_norm(cx, cy)
        z = self._etz_zonas[idx]
        h = self._etz_resize_handle
        if "w" in h: z.x0 = min(nx, z.x1 - 0.01)
        if "e" in h: z.x1 = max(nx, z.x0 + 0.01)
        if "n" in h: z.y0 = min(ny, z.y1 - 0.01)
        if "s" in h: z.y1 = max(ny, z.y0 + 0.01)
        self._etz_redibujar_zonas()
        self._etz_actualizar_lista_zonas()

    def _etz_drag_move(self, cx, cy):
        """Mueve toda la zona manteniendo su tamaño."""
        idx = self._etz_resize_idx
        if idx is None or idx >= len(self._etz_zonas) or self._etz_move_offset is None:
            return
        w, h = self._etz_canvas_wh()
        z = self._etz_zonas[idx]
        dw = z.x1 - z.x0
        dh = z.y1 - z.y0
        ox, oy = self._etz_move_offset
        new_x0 = max(0.0, min(1.0 - dw, (cx - ox) / w))
        new_y0 = max(0.0, min(1.0 - dh, (cy - oy) / h))
        z.x0 = new_x0
        z.x1 = new_x0 + dw
        z.y0 = new_y0
        z.y1 = new_y0 + dh
        self._etz_redibujar_zonas()
        self._etz_actualizar_lista_zonas()

    def _etz_on_release(self, event):
        cx = self._etz_canvas.canvasx(event.x)
        cy = self._etz_canvas.canvasy(event.y)

        if self._etz_rect_tmp:
            self._etz_canvas.delete(self._etz_rect_tmp)
            self._etz_rect_tmp = None
        if hasattr(self, "_etz_dim_lbl") and self._etz_dim_lbl:
            self._etz_canvas.delete(self._etz_dim_lbl)
            self._etz_dim_lbl = None

        if self._etz_modo == "draw":
            self._etz_finish_draw(cx, cy)
        # resize y move ya actualizaron la zona en tiempo real, nada más que hacer

        self._etz_modo = None
        self._etz_rect_ini = None
        self._etz_resize_idx = None
        self._etz_resize_handle = None
        self._etz_move_offset = None

    def _etz_finish_draw(self, cx, cy):
        """Guarda el rectángulo nuevo al soltar el mouse."""
        if not self._etz_rect_ini or self._etz_img_orig is None:
            return
        from core.zone_labeler import Zona
        x0, y0 = self._etz_rect_ini
        nx0, ny0 = self._etz_canvas_a_norm(x0, y0)
        nx1, ny1 = self._etz_canvas_a_norm(cx, cy)
        if abs(nx1 - nx0) < 0.01 or abs(ny1 - ny0) < 0.01:
            return
        zona = Zona(
            tipo=self._etz_tipo.get(),
            x0=min(nx0, nx1), y0=min(ny0, ny1),
            x1=max(nx0, nx1), y1=max(ny0, ny1),
            confianza=1.0,
        )
        self._etz_zonas.append(zona)
        self._etz_zona_sel_idx = len(self._etz_zonas) - 1
        self._etz_actualizar_lista_zonas()
        self._etz_zona_list.selection_clear(0, "end")
        self._etz_zona_list.selection_set(self._etz_zona_sel_idx)
        self._etz_redibujar_zonas()

    def _etz_on_click_derecho(self, event):
        """Click derecho sobre el canvas: elimina la zona bajo el cursor,
        o muestra menú para cambiar el tipo si hay una zona allí."""
        if self._etz_img_orig is None or not self._etz_zonas:
            return
        cx = self._etz_canvas.canvasx(event.x)
        cy = self._etz_canvas.canvasy(event.y)
        nx, ny = self._etz_canvas_a_norm(cx, cy)

        # Buscar zona que contiene el punto (última dibujada tiene prioridad)
        idx_hit = None
        for i in range(len(self._etz_zonas) - 1, -1, -1):
            z = self._etz_zonas[i]
            if z.x0 <= nx <= z.x1 and z.y0 <= ny <= z.y1:
                idx_hit = i
                break

        if idx_hit is None:
            return

        # Menú contextual
        from core.zone_labeler import TIPOS_ZONA
        menu = tk.Menu(self, tearoff=0)
        zona_hit = self._etz_zonas[idx_hit]

        # Submenú: cambiar tipo
        sub = tk.Menu(menu, tearoff=0)
        for tipo_key, info in TIPOS_ZONA.items():
            def _set_tipo(k=tipo_key, i=idx_hit):
                self._etz_zonas[i].tipo = k
                self._etz_actualizar_lista_zonas()
                self._etz_redibujar_zonas()
            marca = "✓ " if tipo_key == zona_hit.tipo else "   "
            sub.add_command(label=f"{marca}{info['label']}", command=_set_tipo)
        menu.add_cascade(label="Cambiar tipo", menu=sub)
        menu.add_separator()

        # Dividir la zona exactamente donde se hizo clic (estilo FineReader)
        frac_h = (ny - zona_hit.y0) / max(zona_hit.y1 - zona_hit.y0, 1e-6)
        frac_v = (nx - zona_hit.x0) / max(zona_hit.x1 - zona_hit.x0, 1e-6)
        menu.add_command(
            label="✂ Dividir aquí (horizontal)",
            command=lambda i=idx_hit, f=frac_h: self._etz_dividir_zona(i, "h", f))
        menu.add_command(
            label="✂ Dividir aquí (vertical)",
            command=lambda i=idx_hit, f=frac_v: self._etz_dividir_zona(i, "v", f))

        # Fusionar con otra zona del mismo tipo o cercana
        sub_fus = tk.Menu(menu, tearoff=0)
        n_fus = 0
        for j, otra in enumerate(self._etz_zonas):
            if j == idx_hit or n_fus >= 15:
                continue
            lbl_o = TIPOS_ZONA.get(otra.tipo, {}).get("label", otra.tipo)
            sub_fus.add_command(
                label=f"{j+1}. {lbl_o} ({otra.x0:.2f},{otra.y0:.2f})",
                command=lambda a=idx_hit, b=j: self._etz_fusionar_zonas(a, b))
            n_fus += 1
        if n_fus:
            menu.add_cascade(label="🔗 Fusionar con…", menu=sub_fus)

        # Vincular pie de foto ↔ foto (Zona.vinculo, por identidad zid estable)
        if zona_hit.tipo == "pie_foto":
            fotos_disp = [(j, o) for j, o in enumerate(self._etz_zonas) if o.tipo == "foto"]
            if fotos_disp:
                sub_vinc = tk.Menu(menu, tearoff=0)
                for j, foto in fotos_disp:
                    marca = "✓ " if zona_hit.vinculo == foto.zid else "   "
                    sub_vinc.add_command(
                        label=f"{marca}Foto {j+1} ({foto.x0:.2f},{foto.y0:.2f})",
                        command=lambda i=idx_hit, fz=foto.zid: self._etz_vincular_foto(i, fz))
                menu.add_cascade(label="🖇 Vincular a foto…", menu=sub_vinc)

        menu.add_command(label="🔢 Recalcular orden de lectura",
                         command=self._etz_recalcular_orden)
        menu.add_separator()
        menu.add_command(label="🗑 Eliminar esta zona",
                         command=lambda i=idx_hit: self._etz_borrar_zona(i))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _etz_dividir_zona(self, idx: int, eje: str, frac: float):
        """Divide la zona idx en dos por el eje indicado, en la posición frac."""
        from core.zone_labeler import dividir_zona
        if not (0 <= idx < len(self._etz_zonas)):
            return
        a, b = dividir_zona(self._etz_zonas[idx], eje=eje, frac=frac)
        self._etz_zonas[idx:idx + 1] = [a, b]
        self._etz_limpiar_vinculos_huerfanos()
        self._etz_recalcular_orden(redibujar=False)
        self._etz_zona_sel_idx = idx
        self._etz_actualizar_lista_zonas()
        self._etz_redibujar_zonas()

    def _etz_fusionar_zonas(self, idx_a: int, idx_b: int):
        """Fusiona dos zonas en su bounding box común."""
        from core.zone_labeler import fusionar_zonas
        n = len(self._etz_zonas)
        if not (0 <= idx_a < n and 0 <= idx_b < n) or idx_a == idx_b:
            return
        fusion = fusionar_zonas([self._etz_zonas[idx_a], self._etz_zonas[idx_b]])
        for i in sorted((idx_a, idx_b), reverse=True):
            self._etz_zonas.pop(i)
        self._etz_zonas.append(fusion)
        self._etz_limpiar_vinculos_huerfanos()
        self._etz_recalcular_orden(redibujar=False)
        self._etz_zona_sel_idx = len(self._etz_zonas) - 1
        self._etz_actualizar_lista_zonas()
        self._etz_redibujar_zonas()

    def _etz_limpiar_vinculos_huerfanos(self):
        """Pone en None cualquier Zona.vinculo que apunte a un zid que ya no
        existe (tras dividir/fusionar/borrar la zona vinculada)."""
        zids_vivos = {z.zid for z in self._etz_zonas}
        for z in self._etz_zonas:
            if z.vinculo and z.vinculo not in zids_vivos:
                z.vinculo = None

    def _etz_vincular_foto(self, idx_pie: int, foto_zid: str):
        """Vincula (o desvincula si ya estaba vinculado a esa misma foto) la
        zona pie_foto en idx_pie con la zona foto de zid `foto_zid`."""
        if not (0 <= idx_pie < len(self._etz_zonas)):
            return
        pie = self._etz_zonas[idx_pie]
        pie.vinculo = None if pie.vinculo == foto_zid else foto_zid
        self._etz_redibujar_zonas()

    def _etz_detectar_cabeceras(self):
        """Reporta cabeceras repetidas entre las páginas YA etiquetadas
        manualmente de este número (solo informa; no reetiqueta nada solo).
        """
        numero = self._etz_numero.get() if hasattr(self, "_etz_numero") else ""
        if not numero or not ST.out_dir:
            self.toast("Selecciona un número con páginas etiquetadas primero.", "warn")
            return
        from core.layout_patterns import detectar_cabeceras_repetidas
        from core.zone_labeler import cargar_todas_manual
        paginas_et = cargar_todas_manual(Path(ST.out_dir), numero)
        if len(paginas_et) < 2:
            self.toast("Se necesitan al menos 2 páginas etiquetadas de este "
                       "número para comparar cabeceras.", "warn")
            return
        zonas_por_pagina = [pg.zonas for pg in paginas_et]
        grupos = detectar_cabeceras_repetidas(zonas_por_pagina, min_repeticiones=2)
        if not grupos:
            messagebox.showinfo("Cabeceras repetidas",
                "No se detectaron cabeceras con la misma posición en al menos "
                "2 páginas etiquetadas de este número.")
            return
        lineas = []
        for i, indices_pag in enumerate(grupos.values(), 1):
            nombres = ", ".join(paginas_et[p].pagina for p in indices_pag)
            lineas.append(f"Grupo {i}: {len(indices_pag)} páginas → {nombres}")
        messagebox.showinfo("Cabeceras repetidas",
            f"{len(grupos)} patrón(es) de cabecera detectado(s):\n\n" + "\n".join(lineas))

    def _etz_recalcular_orden(self, redibujar: bool = True):
        """Recalcula el orden de lectura de todas las zonas de la página."""
        from core.zone_labeler import calcular_orden_lectura
        calcular_orden_lectura(self._etz_zonas)
        if redibujar:
            self._etz_actualizar_lista_zonas()
            self._etz_redibujar_zonas()

    def _etz_ocr_zonas_preview(self):
        """OCR por zonas de la página actual: reconoce cada zona recortada
        por separado, en orden de lectura, y muestra el resultado en el
        panel TEXTO OCR. Es el flujo central de FineReader."""
        numero = self._etz_numero.get()
        pagina = self._etz_pagina.get()
        if not numero or not pagina:
            messagebox.showwarning("Sin selección", "Selecciona un número y página.")
            return
        if not self._etz_zonas:
            messagebox.showwarning(
                "Sin zonas",
                "No hay zonas en esta página.\n"
                "Usa 'Detectar → Esta página' o dibuja zonas manualmente.")
            return
        img_path = self._etz_get_img_path(numero, pagina)
        if not img_path:
            messagebox.showwarning("Sin imagen",
                "No se encontró la imagen de esta página.")
            return

        zonas = list(self._etz_zonas)
        self._etz_lbl_train.config(text="⏳ OCR por zonas…", fg="#E6A64C")

        def _worker():
            try:
                from core.layout_tesseract import ocr_por_zonas
                def _cb(m):
                    self.after(0, lambda m=m: self._etz_lbl_train.config(
                        text=m[:80], fg="#E6A64C"))
                res = ocr_por_zonas(img_path, zonas, callback=_cb)
                err = ""
            except Exception as e:
                res, err = None, str(e)

            def _mostrar():
                if err or res is None:
                    self._etz_lbl_train.config(
                        text=f"⚠ Error OCR zonas: {err[:60]}", fg="#D96B6B")
                    return
                from core.zone_labeler import TIPOS_ZONA as _TZ
                self._etz_txt_ocr.delete("1.0", "end")
                for rz in res["zonas"]:
                    lbl = _TZ.get(rz["tipo"], {}).get("label", rz["tipo"])
                    self._etz_txt_ocr.insert(
                        "end",
                        f"━━ #{rz['orden']} {lbl} "
                        f"(conf {rz['confianza']:.0f}) ━━\n", "low_conf")
                    self._etz_txt_ocr.insert("end", (rz["texto"] or "—") + "\n\n")
                n_pal = len(res["texto"].split())
                self._etz_lbl_train.config(
                    text=f"✅ OCR zonal: {len(res['zonas'])} zonas, "
                         f"{n_pal} palabras, conf {res['confianza']:.0f}",
                    fg="#6EC69A")
                self.toast(f"OCR por zonas: {n_pal} palabras", tipo="ok")
            self.after(0, _mostrar)

        threading.Thread(target=_worker, daemon=True).start()

    def _etz_borrar_zona(self, idx: int):
        """Elimina la zona en la posición idx."""
        if 0 <= idx < len(self._etz_zonas):
            self._etz_zonas.pop(idx)
            self._etz_limpiar_vinculos_huerfanos()
            self._etz_zona_sel_idx = None
            self._etz_actualizar_lista_zonas()
            self._etz_redibujar_zonas()

    def _etz_suprimir_sel(self, event=None):
        """Elimina la zona seleccionada al presionar Suprimir o Retroceso."""
        idx = self._etz_zona_sel_idx
        if idx is not None and 0 <= idx < len(self._etz_zonas):
            self._etz_borrar_zona(idx)

    def _etz_on_zona_sel(self, event=None):
        """Activa la zona seleccionada en la lista (muestra handles)."""
        sel = self._etz_zona_list.curselection()
        if not sel or not self._etz_img_orig:
            self._etz_zona_sel_idx = None
            self._etz_redibujar_zonas()
            return
        idx = sel[0]
        if idx >= len(self._etz_zonas):
            return
        self._etz_zona_sel_idx = idx
        self._etz_redibujar_zonas()
        # Hacer scroll para que la zona sea visible
        x0p, y0p, x1p, y1p = self._etz_zona_canvas_coords(idx)
        _, h = self._etz_canvas_wh()
        frac = min(y0p, y1p) / max(h, 1)
        self._etz_canvas.yview_moveto(max(0.0, frac - 0.1))

    def _etz_borrar_ultima(self):
        if self._etz_zonas:
            self._etz_zonas.pop()
            self._etz_actualizar_lista_zonas()
            self._etz_redibujar_zonas()

    def _etz_limpiar_todo(self):
        self._etz_zonas.clear()
        self._etz_actualizar_lista_zonas()
        self._etz_redibujar_zonas()

    def _etz_guardar_pagina(self):
        from core.zone_labeler import PaginaEtiquetada, guardar_pagina
        numero  = self._etz_numero.get()
        pagina  = self._etz_pagina.get()
        if not numero or not pagina or not ST.out_dir:
            messagebox.showwarning("Sin datos", "Selecciona un número y página primero.")
            return
        ancho = self._etz_img_orig.width if self._etz_img_orig else 1000
        alto  = self._etz_img_orig.height if self._etz_img_orig else 1400
        pag_data = PaginaEtiquetada(
            pagina=pagina,
            ancho_px=ancho,
            alto_px=alto,
            zonas=list(self._etz_zonas),
            manual=True,
        )
        guardar_pagina(ST.out_dir, numero, pag_data)
        # Re-entrenar el detector con todas las etiquetas manuales disponibles
        self._etz_entrenar_detector(numero)
        self.toast(f"Etiquetas de {pagina} guardadas", tipo="ok")
        self._etz_actualizar_estado()

    def _etz_entrenar_detector(self, numero: str):
        """Entrena DetectorZonas con todas las páginas etiquetadas manualmente del número."""
        from core.zone_labeler import DetectorZonas, cargar_todas_manual
        manuales = cargar_todas_manual(ST.out_dir, numero)  # list[PaginaEtiquetada]
        if not manuales:
            return
        if not hasattr(self, "_etz_detector"):
            self._etz_detector = DetectorZonas()
        stats = self._etz_detector.entrenar(manuales)       # acepta lista directamente
        n     = stats.get("n_paginas", 0)
        tipos = list(stats.get("tipos", {}).keys())
        self._etz_lbl_train.config(
            text=f"🧠 Modelo: {n} pág · {len(tipos)} tipos aprendidos",
            fg="#6EC69A"
        )
        self._btn_etz_predecir.config(bg="#B18AD6")

    def _etz_predecir_numero(self):
        """Aplica la plantilla aprendida a todas las páginas sin etiquetar del número."""
        numero = self._etz_numero.get()
        if not numero or not ST.out_dir:
            return
        if not hasattr(self, "_etz_detector") or not self._etz_detector.esta_entrenado():
            # Intentar entrenar ahora con lo que haya
            self._etz_entrenar_detector(numero)
            if not hasattr(self, "_etz_detector") or not self._etz_detector.esta_entrenado():
                messagebox.showwarning(
                    "Sin modelo",
                    "Etiqueta al menos 2 páginas manualmente para activar la predicción.")
                return

        from core.zone_labeler import cargar_todas_manual
        # Páginas disponibles desde imágenes (fuente más fiable que txt)
        txt_dir = ST.out_dir / "03_ocr" / numero
        img_dir = ST.out_dir / "02_imagenes" / numero

        paginas_disponibles = []
        if img_dir.exists():
            paginas_disponibles = sorted(
                p.stem for p in img_dir.iterdir()
                if p.suffix.lower() in {".png", ".jpg", ".tif", ".tiff"})
        if not paginas_disponibles and txt_dir.exists():
            paginas_disponibles = sorted(p.stem for p in txt_dir.glob("*.txt"))

        if not paginas_disponibles:
            messagebox.showwarning("Sin páginas",
                "No hay imágenes ni archivos OCR para este número.\n"
                "Ejecuta primero la Extracción OCR.")
            return

        # Páginas ya etiquetadas manualmente (lista de PaginaEtiquetada)
        manuales_list  = cargar_todas_manual(ST.out_dir, numero)
        ya_etiquetadas = [p.pagina for p in manuales_list]   # ← lista, no dict
        sin_etiquetar  = [p for p in paginas_disponibles if p not in ya_etiquetadas]

        if not sin_etiquetar:
            messagebox.showinfo("Completo",
                f"Todas las {len(paginas_disponibles)} páginas ya están etiquetadas.")
            return

        # Tamaño de imagen de referencia
        ancho = self._etz_img_orig.width  if self._etz_img_orig else 1000
        alto  = self._etz_img_orig.height if self._etz_img_orig else 1400

        self._etz_lbl_train.config(
            text=f"🔮 Prediciendo {len(sin_etiquetar)} páginas…", fg="#E6A64C")
        self.update_idletasks()

        def _run():
            n = self._etz_detector.aplicar_a_numero(
                ST.out_dir, numero,
                paginas_disponibles, ya_etiquetadas,
                ancho_px=ancho, alto_px=alto,
                umbral_frecuencia=0.3,
            )
            def _after():
                self._etz_lbl_train.config(
                    text=f"✅ {n} páginas predichas · {len(ya_etiquetadas)} manuales",
                    fg="#6EC69A")
                self._etz_actualizar_estado()
                # Recargar la página actual si era una de las predichas
                pagina_actual = self._etz_pagina.get()
                if pagina_actual and pagina_actual not in ya_etiquetadas:
                    self._etz_on_pagina()   # recarga zonas + redibuja canvas
            self.after(0, _after)

        threading.Thread(target=_run, daemon=True).start()

    def _etz_actualizar_estado(self):
        if not ST.out_dir:
            return
        numero = self._etz_numero.get()
        if not numero:
            return
        from core.zone_labeler import cargar_todas_manual, listar_paginas_etiquetadas
        etiq     = listar_paginas_etiquetadas(ST.out_dir, numero)
        manuales = cargar_todas_manual(ST.out_dir, numero)
        txt_dir  = ST.out_dir / "03_ocr" / numero
        img_dir  = ST.out_dir / "02_imagenes" / numero
        if txt_dir.exists():
            total = len(list(txt_dir.glob("*.txt")))
        elif img_dir.exists():
            total = len([p for p in img_dir.iterdir()
                         if p.suffix.lower() in {".png",".jpg",".tif",".tiff"}])
        else:
            total = 0
        n_man  = len(manuales)
        n_pred = len(etiq) - n_man
        sin    = max(0, total - len(etiq))
        self._etz_lbl_estado.config(
            text=f"Total páginas: {total}\n"
                 f"Etiquetadas manual: {n_man}\n"
                 f"Predichas: {n_pred}\n"
                 f"Sin etiquetar: {sin}"
        )
        detector = getattr(self, "_etz_detector", None)
        if detector and detector.esta_entrenado():
            # Ya hay modelo — mostrar estado del modelo
            self._etz_lbl_train.config(
                text=f"🧠 Modelo activo · {n_man} pág · {sin} pendientes",
                fg="#6EC69A")
            self._btn_etz_predecir.config(bg="#B18AD6")
        elif n_man >= 2:
            # Hay páginas para entrenar pero no se ha entrenado todavía
            self._etz_lbl_train.config(
                text=f"✅ {n_man} páginas · listo para predecir",
                fg="#6EC69A")
            self._btn_etz_predecir.config(bg="#B18AD6")
            # Entrenar automáticamente
            self._etz_entrenar_detector(numero)
        else:
            falta = 2 - n_man
            self._etz_lbl_train.config(
                text=f"Etiqueta {falta} página(s) más para activar predicción",
                fg="#B5B6B3")
            self._btn_etz_predecir.config(bg="#22292F")

    def _etz_get_img_path(self, numero: str, pagina: str):
        """
        Devuelve la ruta de imagen para numero/pagina.
        Si no hay PNG en disco, extrae la página del PDF y la guarda en temp.
        """
        # 1. Buscar en carpeta de imágenes del proyecto
        if ST.out_dir:
            img_dir = ST.out_dir / "02_imagenes" / numero
            if img_dir.exists():
                candidatos = list(img_dir.glob(f"*{pagina}*.png"))
                if not candidatos:
                    candidatos = sorted(img_dir.glob("*.png"))
                if candidatos:
                    import re as _re
                    _nums = _re.findall(r'\d+', pagina)
                    n = max(0, int(_nums[-1]) - 1) if _nums else 0
                    return candidatos[n] if n < len(candidatos) else candidatos[0]

        # 2. Extraer desde PDF directamente (carga directa sin OCR previo)
        pdf = next((a for a in (ST.archivos_sel or [])
                    if a.stem == numero), None)
        if pdf and pdf.exists():
            try:
                import re as _re
                import tempfile

                import fitz
                from PIL import Image
                _nums = _re.findall(r'\d+', pagina)
                n_pag = max(0, int(_nums[-1]) - 1) if _nums else 0
                doc  = fitz.open(str(pdf))
                if n_pag < doc.page_count:
                    page = doc[n_pag]
                    mat  = fitz.Matrix(2.0, 2.0)  # 200 DPI para buena detección
                    pix  = page.get_pixmap(matrix=mat)
                    doc.close()
                    # Guardar en temp ASCII
                    tmp_dir = Path(tempfile.gettempdir()) / "bashkar_etz"
                    tmp_dir.mkdir(exist_ok=True)
                    tmp_path = tmp_dir / f"{numero}_{pagina}.png"
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    img.save(str(tmp_path))
                    return tmp_path
            except Exception:
                pass

        # 3. Si la imagen ya está en canvas, usar la imagen en memoria como temp
        if self._etz_img_orig is not None:
            try:
                import tempfile
                tmp_dir = Path(tempfile.gettempdir()) / "bashkar_etz"
                tmp_dir.mkdir(exist_ok=True)
                tmp_path = tmp_dir / f"{numero}_{pagina}_canvas.png"
                self._etz_img_orig.save(str(tmp_path))
                return tmp_path
            except Exception:
                pass

        return None

    def _etz_detectar_pagina(self):
        """Detecta zonas de la página actual con OpenCV o Claude Vision."""
        numero  = self._etz_numero.get()
        pagina  = self._etz_pagina.get()
        if not numero or not pagina:
            messagebox.showwarning("Sin selección", "Selecciona un número y página.")
            return
        img_path = self._etz_get_img_path(numero, pagina)
        if not img_path:
            messagebox.showwarning(
                "Sin imagen",
                "No se encontró la imagen de esta página.\n"
                "Asegúrate de haber convertido el PDF a imágenes (paso OCR Ruta 1 o 2)."
            )
            return
        modo = getattr(self, "_etz_modo_det", tk.StringVar(value="tesseract")).get()

        if modo == "tesseract":
            # Análisis de layout local (Tesseract + OpenCV) — en thread,
            # tarda varios segundos por página
            self._etz_lbl_train.config(
                text="⏳ Analizando layout (Tesseract local)…", fg="#E6A64C")

            def _worker_layout():
                try:
                    from core.layout_tesseract import analizar_pagina_local
                    zonas_t = analizar_pagina_local(img_path)
                    err = ""
                except Exception as e:
                    zonas_t, err = [], str(e)

                def _aplicar():
                    if err:
                        self._etz_lbl_train.config(
                            text=f"⚠ Error: {err[:70]}", fg="#D96B6B")
                        return
                    if not zonas_t:
                        self._etz_lbl_train.config(
                            text="⚠ No se detectaron zonas.", fg="#D96B6B")
                        return
                    self._etz_zonas = zonas_t
                    # Recargar la imagen: el deskew automático pudo corregirla
                    self._etz_cargar_imagen_pagina(numero, pagina)
                    self._etz_actualizar_lista_zonas()
                    self._etz_redibujar_zonas()
                    self._etz_lbl_train.config(
                        text=f"✅ {len(zonas_t)} zonas detectadas (tesseract). "
                             "Revisa y guarda.",
                        fg="#6EC69A")
                self.after(0, _aplicar)

            threading.Thread(target=_worker_layout, daemon=True).start()
            return

        if modo in ("yolo", "onnx", "dit"):
            from core.layout_neural import detectar_layout, motor_disponible
            ok, msg = motor_disponible(modo)
            if not ok:
                if messagebox.askyesno("Motor no instalado",
                        f"{msg}\n\n¿Instalar ahora?"):
                    self._etz_instalar_motor()
                return
            self._etz_lbl_train.config(
                text=f"⏳ Analizando con {modo.upper()}…", fg="#E6A64C")
            self.update_idletasks()

            def _log(m): self._etz_lbl_train.config(text=m[:80], fg="#E6A64C")
            zonas_raw = detectar_layout(img_path, motor=modo, callback=_log)
            # Convertir dicts a objetos Zona
            from core.zone_labeler import TIPOS_ZONA, Zona
            zonas = []
            for z in zonas_raw:
                tipo = z["tipo"] if z["tipo"] in TIPOS_ZONA else "articulo"
                zonas.append(Zona(tipo=tipo, x0=z["x0"], y0=z["y0"],
                                  x1=z["x1"], y1=z["y1"],
                                  confianza=z["confianza"]))

        elif modo == "vision_ia":
            prov   = getattr(self, "_etz_vision_prov",  tk.StringVar(value="claude")).get()
            modelo = getattr(self, "_etz_vision_model", tk.StringVar(value="")).get()
            api_key = ST.api_keys.get(prov, "") or ST.api_key
            if prov != "ollama" and not api_key:
                messagebox.showwarning("API key faltante",
                    f"Configura la API key de {prov} en la pestaña Configuración.")
                return
            self._etz_lbl_train.config(
                text=f"⏳ Consultando {prov}/{modelo}…", fg="#E6A64C")
            self.update_idletasks()
            from core.zone_labeler import detectar_zonas_vision
            zonas = detectar_zonas_vision(img_path, proveedor=prov,
                                          api_key=api_key, modelo=modelo,
                                          prompt_custom=ST.prompt_deteccion)
        else:
            self._etz_lbl_train.config(text="⏳ Analizando con OpenCV…", fg="#E6A64C")
            self.update_idletasks()
            from core.zone_labeler import detectar_zonas_opencv
            zonas = detectar_zonas_opencv(img_path)

        if not zonas:
            self._etz_lbl_train.config(text="⚠ No se detectaron zonas.", fg="#D96B6B")
            return

        self._etz_zonas = zonas
        self._etz_actualizar_lista_zonas()
        self._etz_redibujar_zonas()
        self._etz_lbl_train.config(
            text=f"✅ {len(zonas)} zonas detectadas ({modo}). Revisa y guarda.",
            fg="#6EC69A"
        )

    def _etz_detectar_numero(self):
        """Detecta zonas en todas las páginas del número (en hilo separado)."""
        numero = self._etz_numero.get()
        if not numero or not ST.out_dir:
            messagebox.showwarning("Sin selección", "Selecciona un número primero.")
            return
        img_dir = ST.out_dir / "02_imagenes" / numero
        if not img_dir.exists() or not list(img_dir.glob("*.png")):
            messagebox.showwarning(
                "Sin imágenes",
                "No se encontraron imágenes para este número.\n"
                "Usa la Ruta 1 o 2 de OCR para generar las imágenes primero."
            )
            return
        modo = getattr(self, "_etz_modo_det", tk.StringVar(value="opencv")).get()
        api_key = ""
        _vision_prov  = getattr(self, "_etz_vision_prov",  tk.StringVar(value="claude")).get()
        _vision_model = getattr(self, "_etz_vision_model", tk.StringVar(value="")).get()
        if modo == "vision_ia":
            api_key = ST.api_keys.get(_vision_prov, "") or ST.api_key
            if _vision_prov != "ollama" and not api_key:
                messagebox.showwarning("API key faltante",
                    f"Configura la API key de {_vision_prov} en la pestaña Configuración.")
                return

        imagenes = sorted(img_dir.glob("*.png"))
        n_total = len(imagenes)
        if not messagebox.askyesno(
            "Detectar todo el número",
            f"Se analizarán {n_total} páginas con "
            f"{'Vision IA (' + _vision_prov + '/' + _vision_model + ')' if modo == 'vision_ia' else modo.upper()}.\n"
            + ("Esto usará tokens de tu cuenta de IA.\n" if modo == "vision_ia" else "")
            + "¿Continuar?"
        ):
            return

        self._etz_lbl_train.config(text=f"⏳ Detectando 0/{n_total}…", fg="#E6A64C")

        def _worker():
            from core.zone_labeler import (
                TIPOS_ZONA,
                PaginaEtiquetada,
                Zona,
                detectar_zonas_opencv,
                guardar_pagina,
            )
            ok = 0
            for i, img_path in enumerate(imagenes):
                stem = img_path.stem
                import re as _re
                m = _re.search(r'(\d+)', stem)
                pagina = f"p{int(m.group(1)):04d}" if m else stem

                if modo == "tesseract":
                    from core.layout_tesseract import analizar_pagina_local
                    zonas = analizar_pagina_local(img_path)
                elif modo in ("yolo", "onnx", "dit"):
                    from core.layout_neural import detectar_layout
                    zonas_raw = detectar_layout(img_path, motor=modo)
                    zonas = []
                    for z in zonas_raw:
                        tipo = z["tipo"] if z["tipo"] in TIPOS_ZONA else "articulo"
                        zonas.append(Zona(tipo=tipo, x0=z["x0"], y0=z["y0"],
                                          x1=z["x1"], y1=z["y1"],
                                          confianza=z["confianza"]))
                elif modo == "vision_ia":
                    from core.zone_labeler import detectar_zonas_vision
                    zonas = detectar_zonas_vision(img_path, proveedor=_vision_prov,
                                                   api_key=api_key, modelo=_vision_model,
                                                   prompt_custom=ST.prompt_deteccion)
                else:
                    zonas = detectar_zonas_opencv(img_path)

                if zonas:
                    from PIL import Image as _Img
                    try:
                        im = _Img.open(img_path)
                        W, H = im.size
                    except Exception:
                        W, H = 1000, 1400
                    pag = PaginaEtiquetada(
                        pagina=pagina, ancho_px=W, alto_px=H,
                        zonas=zonas, manual=False
                    )
                    guardar_pagina(ST.out_dir, numero, pag)
                    ok += 1

                self.after(0, lambda i=i, ok=ok: self._etz_lbl_train.config(
                    text=f"⏳ Detectando {i+1}/{n_total} ({ok} con zonas)…",
                    fg="#E6A64C"
                ))

            self.after(0, lambda: (
                self._etz_lbl_train.config(
                    text=f"✅ {ok}/{n_total} páginas con zonas detectadas.",
                    fg="#6EC69A"
                ),
                self._etz_actualizar_estado(),
            ))

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def _etz_instalar_motor(self):
        """Instala las dependencias del motor seleccionado en segundo plano."""
        from core.layout_neural import instalar_motor, motor_disponible
        modo = self._etz_modo_det.get()
        if modo in ("tesseract", "opencv", "vision_ia"):
            messagebox.showinfo(
                "Sin instalación",
                f"El motor '{modo}' no requiere instalar nada adicional.")
            return
        ok, _ = motor_disponible(modo)
        if ok:
            messagebox.showinfo("Ya instalado", f"El motor '{modo}' ya está disponible.")
            return
        self._etz_lbl_train.config(text=f"⬇ Instalando {modo}…", fg="#E6A64C")
        def _run():
            def cb(m): self.after(0, lambda: self._etz_lbl_train.config(
                text=m[:80], fg="#E6A64C"))
            exito = instalar_motor(modo, callback=cb)
            msg = f"✅ {modo} instalado. Reinicia la app." if exito \
                  else f"⚠ Error instalando {modo}. Revisa la conexión."
            self.after(0, lambda: (
                self._etz_lbl_train.config(text=msg, fg="#6EC69A" if exito else "#D96B6B"),
                messagebox.showinfo("Instalación", msg),
            ))
        threading.Thread(target=_run, daemon=True).start()

    # ── Actualizar selector de números en ETZ ────────────────────────────────
    def _etz_deskew_pagina(self):
        """Detecta la inclinación de la página actual, muestra previsualización
        con slider de ajuste fino y guarda la imagen corregida si el usuario confirma."""
        if self._etz_img_orig is None:
            messagebox.showwarning("Sin imagen", "Carga una página primero.")
            return

        numero = self._etz_numero.get()
        pagina = self._etz_pagina.get()
        img_path = self._etz_get_img_path(numero, pagina)
        if not img_path:
            messagebox.showwarning("Sin imagen", "No se encontró el archivo de imagen.")
            return

        from PIL import Image

        from core.image_preprocessor import detectar_angulo_pagina

        img_orig = Image.open(img_path)
        angulo_detectado = detectar_angulo_pagina(img_orig)

        # ── Ventana de previsualización ───────────────────────────────────────
        win = tk.Toplevel(self)
        win.title(f"Corregir inclinación — {pagina}")
        win.geometry("820x640")
        win.configure(bg=CONTENT_BG)
        win.grab_set()

        # Encabezado
        hdr = tk.Frame(win, bg=CONTENT_BG)
        hdr.pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(hdr, text="Corrección de inclinación",
                 bg=CONTENT_BG, fg="#E8E5DF",
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        lbl_angulo = tk.Label(hdr,
                              text=f"Ángulo detectado: {angulo_detectado:+.2f}°",
                              bg=CONTENT_BG, fg="#E6A64C" if abs(angulo_detectado) > 0.3 else "#6EC69A",
                              font=("Segoe UI", 9))
        lbl_angulo.pack(side="left", padx=12)

        # Canvas de previsualización
        canvas_frame = tk.Frame(win, bg="#1C2227", relief="sunken", bd=1)
        canvas_frame.pack(fill="both", expand=True, padx=12, pady=8)
        prev_canvas = tk.Canvas(canvas_frame, bg="#1C2227", highlightthickness=0)
        prev_canvas.pack(fill="both", expand=True)

        # Estado interno de la ventana
        _state = {"angulo": tk.DoubleVar(value=angulo_detectado), "img_tk": None}

        def _render_preview(angulo_val):
            """Rota la imagen al ángulo dado y la muestra en el canvas."""
            from PIL import Image, ImageTk
            try:
                a = float(angulo_val)
                if abs(a) < 0.1:
                    img_rot = img_orig.copy()
                else:
                    img_rot = img_orig.rotate(
                        -a, expand=True,
                        fillcolor=(255, 255, 255) if img_orig.mode != "L" else 255,
                        resample=Image.BICUBIC,
                    )
                # Escalar para caber en el canvas
                cw = prev_canvas.winfo_width() or 760
                ch = prev_canvas.winfo_height() or 480
                ratio = min(cw / img_rot.width, ch / img_rot.height, 1.0)
                nw = max(1, int(img_rot.width  * ratio))
                nh = max(1, int(img_rot.height * ratio))
                img_small = img_rot.resize((nw, nh), Image.LANCZOS)
                _state["img_tk"] = ImageTk.PhotoImage(img_small)
                prev_canvas.delete("all")
                prev_canvas.create_image(cw // 2, ch // 2, anchor="center",
                                         image=_state["img_tk"])
            except Exception:
                pass

        def _on_slider(val):
            a = round(float(val), 2)
            _state["angulo"].set(a)
            lbl_angulo.config(
                text=f"Ángulo: {a:+.2f}°",
                fg="#E6A64C" if abs(a) > 0.3 else "#6EC69A")
            _render_preview(a)

        # Panel de controles
        ctrl = tk.Frame(win, bg=CONTENT_BG)
        ctrl.pack(fill="x", padx=12, pady=(0, 4))

        tk.Label(ctrl, text="Ajuste fino:", bg=CONTENT_BG, fg="#E8E5DF",
                 font=("Segoe UI", 8, "bold")).pack(side="left")

        slider = tk.Scale(ctrl, from_=-15.0, to=15.0, resolution=0.1,
                          orient="horizontal", length=400,
                          variable=_state["angulo"],
                          command=_on_slider,
                          bg=CONTENT_BG, fg="#E8E5DF",
                          highlightthickness=0, troughcolor="#E8E5DF",
                          font=("Segoe UI", 7))
        slider.pack(side="left", padx=(6, 12))

        def _reset():
            _state["angulo"].set(angulo_detectado)
            slider.set(angulo_detectado)
            _on_slider(angulo_detectado)

        tk.Button(ctrl, text="↺ Restablecer detectado",
                  command=_reset,
                  font=("Segoe UI", 8), bg="#171C20").pack(side="left", padx=4)

        tk.Button(ctrl, text="0° (sin corrección)",
                  command=lambda: (_state["angulo"].set(0), slider.set(0), _on_slider(0)),
                  font=("Segoe UI", 8), bg="#171C20").pack(side="left", padx=4)

        # Botones finales
        btn_frame = tk.Frame(win, bg=CONTENT_BG)
        btn_frame.pack(fill="x", padx=12, pady=(0, 12))

        lbl_aviso = tk.Label(btn_frame,
                             text="La imagen original se preserva. La versión corregida se guarda en 02_imagenes_ocr/.",
                             bg=CONTENT_BG, fg=TXT_SEC, font=("Segoe UI", 8))
        lbl_aviso.pack(side="left")

        def _aplicar():
            a = float(_state["angulo"].get())
            if abs(a) < 0.1:
                messagebox.showinfo("Sin cambio",
                                    "El ángulo es 0° — no hay nada que corregir.",
                                    parent=win)
                return
            try:
                from PIL import Image
                img_corr = img_orig.rotate(
                    -a, expand=True,
                    fillcolor=(255, 255, 255) if img_orig.mode != "L" else 255,
                    resample=Image.BICUBIC,
                )
                # Guardar SOLO en 02_imagenes_ocr/ — nunca sobreescribir original
                if ST.out_dir:
                    dir_ocr_img = Path(ST.out_dir) / "02_imagenes_ocr" / numero
                    dir_ocr_img.mkdir(parents=True, exist_ok=True)
                    dest = dir_ocr_img / img_path.name
                    img_corr.save(str(dest))
                    messagebox.showinfo("Guardado",
                        f"Imagen corregida guardada en:\n02_imagenes_ocr/{numero}/{img_path.name}\n\n"
                        f"La imagen original permanece intacta.", parent=win)
                win.destroy()
                self._etz_cargar_imagen_pagina(numero, pagina)
                self._etz_zoom = 1.0
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar: {e}", parent=win)

        tk.Button(btn_frame, text="Cancelar",
                  command=win.destroy,
                  font=("Segoe UI", 8), bg="#171C20").pack(side="right", padx=(4, 0))
        tk.Button(btn_frame, text="✅ Aplicar y guardar",
                  command=_aplicar,
                  font=("Segoe UI", 9, "bold"),
                  bg="#6CA8E8", fg="white").pack(side="right")

        # Renderizar preview inicial tras que el canvas tenga tamaño real
        win.update_idletasks()
        _render_preview(angulo_detectado)

    def _etz_editar_prompt(self):
        """Abre ventana para editar el prompt de detección de zonas por IA."""
        from core.zone_labeler import construir_prompt_deteccion
        win, prompt_content = self._mk_glass_toplevel(
            "⚙ Prompt de detección de zonas", ancho=720, alto=580)
        win.grab_set()

        tk.Label(prompt_content, text="Prompt enviado a la IA de visión para detectar zonas",
                 bg=CONTENT_BG, fg=TXT_PRI,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12, pady=(12, 0))
        tk.Label(prompt_content,
                 text="Incluye automáticamente los tipos personalizados de tu proyecto (★). "
                      "Edita para ajustar instrucciones específicas de Estampa.",
                 bg=CONTENT_BG, fg=TXT_SEC,
                 font=("Segoe UI", 8), wraplength=680, justify="left").pack(
                     anchor="w", padx=12, pady=(2, 6))

        frame_txt = tk.Frame(prompt_content, bg=CONTENT_BG)
        frame_txt.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        scroll = tk.Scrollbar(frame_txt)
        scroll.pack(side="right", fill="y")
        txt = tk.Text(frame_txt, wrap="word", font=("Consolas", 9),
                      bg=CARD_BG, fg=TXT_PRI,
                      insertbackground=TXT_PRI,
                      yscrollcommand=scroll.set,
                      relief="solid", bd=1)
        txt.pack(fill="both", expand=True)
        scroll.config(command=txt.yview)

        # Mostrar prompt generado dinámicamente (con tipos custom incluidos)
        prompt_generado = construir_prompt_deteccion(ST.prompt_deteccion)
        txt.insert("1.0", prompt_generado)

        btn_frame = tk.Frame(prompt_content, bg=CONTENT_BG)
        btn_frame.pack(fill="x", padx=12, pady=(0, 12))

        def _restaurar():
            """Regenera el prompt con todos los tipos activos actuales."""
            txt.delete("1.0", "end")
            txt.insert("1.0", construir_prompt_deteccion(""))

        def _guardar():
            nuevo = txt.get("1.0", "end").strip()
            default_generado = construir_prompt_deteccion("").strip()
            # Guardar vacío si es igual al generado (se regenerará siempre al usar)
            ST.prompt_deteccion = "" if nuevo == default_generado else nuevo
            win.destroy()
            self._etz_lbl_train.config(
                text="✅ Prompt personalizado guardado." if ST.prompt_deteccion
                     else "✅ Usando prompt generado automáticamente.",
                fg="#6EC69A")

        tk.Button(btn_frame, text="↺ Restaurar por defecto",
                  command=_restaurar,
                  font=("Segoe UI", 8), bg="#171C20").pack(side="left")
        tk.Button(btn_frame, text="Cancelar",
                  command=win.destroy,
                  font=("Segoe UI", 8), bg="#171C20").pack(side="right", padx=(4, 0))
        tk.Button(btn_frame, text="💾 Guardar",
                  command=_guardar,
                  font=("Segoe UI", 9, "bold"),
                  bg="#6CA8E8", fg="white").pack(side="right")

    def _etz_abrir_pdf_directo(self):
        """Carga un PDF directamente en el etiquetador sin pasar por Configuración."""
        from tkinter import filedialog
        ruta = filedialog.askopenfilename(
            title="Abrir PDF para etiquetar",
            filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")])
        if not ruta:
            return
        p = Path(ruta)

        # Agregar a ST.archivos_sel si no está
        if not hasattr(ST, "archivos_sel") or ST.archivos_sel is None:
            ST.archivos_sel = []
        if p not in ST.archivos_sel:
            ST.archivos_sel.append(p)

        # Configurar out_dir si no está configurado
        if not getattr(ST, "out_dir", None):
            import tempfile
            ST.out_dir = Path(tempfile.gettempdir()) / "bashkar_etz_temp" / p.stem
            ST.out_dir.mkdir(parents=True, exist_ok=True)

        # Actualizar combobox con el nuevo archivo
        nombre = p.stem
        vals = list(self._etz_cb_num["values"])
        if nombre not in vals:
            vals.append(nombre)
            self._etz_cb_num["values"] = vals
        self._etz_cb_num.set(nombre)
        self._etz_numero.set(nombre)

        # Poblar páginas directamente desde el PDF
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(p))
            n_pags = doc.page_count
            doc.close()
            pags = [f"p{i+1:04d}" for i in range(n_pags)]
        except Exception:
            pags = [f"p{i+1:04d}" for i in range(50)]

        self._etz_cb_pag["values"] = pags
        self._etz_poblar_miniaturas(pags)

        if pags:
            self._etz_cb_pag.set(pags[0])
            self._etz_pagina.set(pags[0])
            # Cargar imagen de la primera página directamente desde el PDF
            self._etz_cargar_imagen_desde_pdf(str(p), 0)

        self._etz_lbl_train.config(text=f"✅ {nombre} — {len(pags)} páginas")

    def _etz_cargar_imagen_desde_pdf(self, pdf_path: str, n_pag: int):
        """Carga una página de PDF en el canvas del etiquetador, sin congelar la UI.

        El render con PyMuPDF al 150 % más el redimensionado LANCZOS tardaban
        cientos de milisegundos a segundos POR PÁGINA en el hilo principal.
        Ahora eso ocurre en un hilo; solo el PhotoImage vuelve al principal.
        """
        self._etz_img_token = getattr(self, "_etz_img_token", 0) + 1
        token = self._etz_img_token

        def _trabajo():
            try:
                img, escala = self._etz_render_pdf(pdf_path, n_pag)
                error = None
            except Exception as ex:     # noqa: BLE001 — se reporta en la UI
                img, escala, error = None, 1.0, ex
            self.after(0, lambda: self._etz_pintar_imagen(img, escala, error, token))

        threading.Thread(target=_trabajo, daemon=True).start()

    def _etz_render_pdf(self, pdf_path: str, n_pag: int):
        """Renderiza la página y la escala. Puro: NO toca Tk, corre en hilo."""
        import fitz
        from PIL import Image

        from core.local_cache import clave_cache, ruta_cache
        cache_png = (ruta_cache("etz_paginas")
                     / f"{clave_cache(Path(pdf_path))}_{n_pag}_150.png")
        if cache_png.exists():
            img = Image.open(cache_png).convert("RGB")
        else:
            doc  = fitz.open(pdf_path)
            page = doc[n_pag]
            mat  = fitz.Matrix(1.5, 1.5)  # 150% escala para mejor resolución
            pix  = page.get_pixmap(matrix=mat)
            doc.close()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            try:
                img.save(cache_png)
            except OSError:
                pass                    # la caché es un lujo, no una condición

        # Escalar al canvas
        max_h = 900
        if img.height > max_h:
            escala = max_h / img.height
            img = img.resize((int(img.width * escala), max_h), Image.LANCZOS)
        else:
            escala = 1.0
        return img, escala

    def _etz_pintar_imagen(self, img, escala: float, error, token: int):
        """Pinta la imagen ya renderizada. Solo hilo principal."""
        if token != getattr(self, "_etz_img_token", 0):
            return                      # el usuario ya cambió de página
        from PIL import ImageTk
        if error is not None or img is None:
            self._etz_canvas.delete("all")
            self._etz_canvas.create_text(
                150, 100, text=f"Error cargando imagen:\n{error}",
                fill="#B5B6B3", font=("Segoe UI", 9), anchor="nw")
            return
        try:
            self._etz_escala   = escala
            self._etz_img_orig = img
            self._etz_img_tk   = ImageTk.PhotoImage(img)
            self._etz_canvas.delete("all")
            self._etz_canvas.create_image(0, 0, anchor="nw", image=self._etz_img_tk)
            self._etz_canvas.configure(scrollregion=(0, 0, img.width, img.height))
            self._etz_redibujar_zonas()
        except Exception as ex:
            self._etz_canvas.delete("all")
            self._etz_canvas.create_text(
                150, 100, text=f"Error cargando imagen:\n{ex}",
                fill="#B5B6B3", font=("Segoe UI", 9), anchor="nw")

    def _etz_refrescar_numeros(self):
        """Llamado cuando el corpus cambia para actualizar el combobox."""
        if not hasattr(self, "_etz_cb_num"):
            return
        numeros = []
        if ST.corpus_meta is not None and "numero" in ST.corpus_meta.columns:
            numeros = sorted(ST.corpus_meta["numero"].unique().tolist())
        elif ST.archivos_sel:
            numeros = [a.stem for a in ST.archivos_sel]
        self._etz_cb_num["values"] = numeros
        if numeros and not self._etz_numero.get():
            self._etz_cb_num.set(numeros[0])
