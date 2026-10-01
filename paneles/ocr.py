"""paneles/ocr.py — Métodos de BashkarApp extraídos de app.py.

Mixin: BashkarApp hereda de PanelOCR. Los cuerpos son copia literal del
original; los nombres globales (ST, colores, tk…) los inyecta
paneles.sincronizar() desde app.py.
"""

from __future__ import annotations

# ruff: noqa: F821


class PanelOCR:
    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2: EXTRACCIÓN / OCR
    # ══════════════════════════════════════════════════════════════════════════
    def _build_ocr(self):
        f = self._tab_ocr
        self._page_header(f, "Extracción de texto",
                          "Detecta texto digital o aplica OCR automáticamente página a página", "📄")

        self._build_ai_panel(f, "ocr")
        pad = tk.Frame(f, bg=CONTENT_BG); pad.pack(fill="both", expand=True, padx=24, pady=16)

        # ── Tarjetas de métricas ──────────────────────────────────────────────
        ind = tk.Frame(pad, bg=CONTENT_BG); ind.pack(fill="x", pady=(0, 16))
        self._lbl_o_pdf = self._mk_ind(ind, "Archivos",      "—", 0)
        self._lbl_o_pag = self._mk_ind(ind, "Páginas",       "—", 1)
        self._lbl_o_pal = self._mk_ind(ind, "Palabras",      "—", 2)
        self._lbl_o_con = self._mk_ind(ind, "Confianza OCR", "—", 3)
        self._lbl_o_rev = self._mk_ind(ind, "Para revisión", "—", 4)

        # ── Progreso ──────────────────────────────────────────────────────────
        prog_card = tk.Frame(pad, bg=CARD_BG, relief="solid", bd=1,
                             highlightbackground=CARD_BOR, highlightthickness=1)
        prog_card.pack(fill="x", pady=(0, 12))
        prog_inner = tk.Frame(prog_card, bg=CARD_BG, padx=16, pady=12)
        prog_inner.pack(fill="x")
        self._lbl_fase = tk.Label(prog_inner, text="Esperando…",
                                   bg=CARD_BG, fg="#777F84",
                                   font=("Segoe UI", 9, "italic"))
        self._lbl_fase.pack(anchor="w")
        self._prog = ttk.Progressbar(prog_inner, mode="determinate", length=600)
        self._prog.pack(fill="x", pady=(6, 4))
        self._lbl_pct = tk.Label(prog_inner, text="", bg=CARD_BG, fg="#777F84",
                                  font=("Courier", 8))
        self._lbl_pct.pack(anchor="w")

        # ── Selector de ruta de extracción ───────────────────────────────────
        ruta_card = tk.Frame(pad, bg=CARD_BG, relief="solid", bd=1,
                             highlightbackground=CARD_BOR, highlightthickness=1)
        ruta_card.pack(fill="x", pady=(0, 10))
        ruta_inner = tk.Frame(ruta_card, bg=CARD_BG, padx=16, pady=10)
        ruta_inner.pack(fill="x")

        ruta_hdr = tk.Frame(ruta_inner, bg=CARD_BG)
        ruta_hdr.pack(fill="x", pady=(0, 6))
        tk.Label(ruta_hdr, text="Ruta de extracción", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        self._mk_ayuda(ruta_hdr,
            "Elige cómo se obtiene el texto de cada página del PDF.\n\n"
            "Ruta 1 — Tesseract propio (recomendada para corpus BNC):\n"
            "  Convierte el PDF a imágenes y aplica OCR con Tesseract.\n"
            "  Ignora el texto embebido por la BNC, que mezcla columnas.\n"
            "  Resultado: texto limpio, columnas en orden correcto.\n\n"
            "Ruta 2 — Claude Vision (máxima calidad, requiere API key):\n"
            "  Envía cada página como imagen a Claude. Comprende el\n"
            "  layout visual y transcribe respetando columnas, títulos\n"
            "  y pies de foto. Más lento y tiene costo en tokens.\n\n"
            "Ruta 3 — Texto BNC + reconstrucción de líneas (más rápida):\n"
            "  Usa el texto ya extraído por la BNC pero aplica un\n"
            "  algoritmo que detecta y une líneas rotas de columna.\n\n"
            "Ruta 4 — Kraken + CATMuS-Print (★ MEJOR para prensa histórica):\n"
            "  Motor OCR entrenado específicamente en prensa latinoamericana\n"
            "  del siglo XX. 100% offline. Requiere instalar kraken y\n"
            "  descargar el modelo CATMuS-Print (~200 MB, botón abajo).\n"
            "  Confianza típica: 85-92% en textos de los años 30-40.\n\n"
            "Ruta 5 — Ollama Vision (offline con modelo de visión local):\n"
            "  Usa Qwen2.5-VL u otro modelo multimodal instalado en Ollama.\n"
            "  100% offline, sin costo de API. Requiere Ollama instalado\n"
            "  y al menos 8 GB de RAM. Más lento que Kraken.")

        self._var_ruta_ocr = tk.StringVar(value="tesseract")
        rutas = [
            ("tesseract", "Ruta 1 — Tesseract propio  ✓ Recomendada"),
            ("vision_ia", "Ruta 2 — IA de visión  (Claude · GPT-4o · Gemini · Ollama)"),
            ("bnc",       "Ruta 3 — Texto BNC + reconstrucción de líneas"),
            ("kraken",    "Ruta 4 — Kraken + CATMuS-Print  ★ Mejor para prensa histórica (offline)"),
            ("ollama",    "Ruta 5 — Ollama Vision  (offline, requiere Ollama + modelo visión)"),
        ]
        for val, etiq in rutas:
            r = tk.Frame(ruta_inner, bg=CARD_BG)
            r.pack(fill="x", pady=1)
            ttk.Radiobutton(r, text=etiq, variable=self._var_ruta_ocr,
                            value=val).pack(side="left")

        # ── Sub-panel Ruta 2: selector proveedor + modelo ─────────────────────
        from core.zone_labeler import VISION_PROVEEDORES
        self._ocr_vision_frame = tk.Frame(ruta_inner, bg=CARD_BG)
        self._ocr_vision_frame.pack(fill="x", pady=(2, 0), padx=(24, 0))

        self._ocr_vision_prov  = tk.StringVar(value="claude")
        self._ocr_vision_model = tk.StringVar(value="claude-sonnet-4-6")

        tk.Label(self._ocr_vision_frame, text="Proveedor:",
                 bg=CARD_BG, fg=TXT_SEC, font=("Segoe UI", 8)).pack(side="left")
        _cb_ocr_prov = ttk.Combobox(
            self._ocr_vision_frame, textvariable=self._ocr_vision_prov,
            values=list(VISION_PROVEEDORES.keys()), state="readonly", width=10)
        _cb_ocr_prov.pack(side="left", padx=(4, 8))

        tk.Label(self._ocr_vision_frame, text="Modelo:",
                 bg=CARD_BG, fg=TXT_SEC, font=("Segoe UI", 8)).pack(side="left")
        self._cb_ocr_vision_model = ttk.Combobox(
            self._ocr_vision_frame, textvariable=self._ocr_vision_model,
            state="readonly", width=26)
        self._cb_ocr_vision_model.pack(side="left", padx=(4, 0))

        # Tooltip ?
        _VISION_OCR_AYUDA = (
            "Ruta 2 — IA de visión para OCR:\n\n"
            "claude  — Claude Sonnet/Haiku. Alta calidad, entiende layout histórico.\n"
            "openai  — GPT-4o / GPT-4o-mini. Muy buena calidad, gpt-4o-mini es económico.\n"
            "gemini  — Gemini 1.5 Flash. Casi gratuito en el tier libre de Google.\n"
            "ollama  — Llava local, 100% offline. Requiere Ollama + modelo visión.\n\n"
            "Todos usan el mismo prompt interno de transcripción OCR.\n"
            "Costo estimado con Claude Haiku: ~$0.002/página."
        )
        _btn_q = tk.Label(self._ocr_vision_frame, text=" ?", bg=CARD_BG,
                          fg=TXT_SEC, font=("Segoe UI", 8, "bold"), cursor="hand2")
        _btn_q.pack(side="left", padx=(6, 0))
        _btn_q.bind("<Enter>",    lambda e: self._mostrar_tooltip(_VISION_OCR_AYUDA, _btn_q))
        _btn_q.bind("<Leave>",    lambda e: self._ocultar_tooltip())
        _btn_q.bind("<Button-1>", lambda e: messagebox.showinfo("Ruta 2 — IA de visión",
                                                                  _VISION_OCR_AYUDA))

        def _on_ocr_prov(*_):
            prov = self._ocr_vision_prov.get()
            info = VISION_PROVEEDORES.get(prov, {})
            mods = info.get("modelos", [])
            self._cb_ocr_vision_model["values"] = mods
            self._ocr_vision_model.set(info.get("default", mods[0] if mods else ""))

        def _on_ruta_change(*_):
            if self._var_ruta_ocr.get() == "vision_ia":
                self._ocr_vision_frame.pack(fill="x", pady=(2, 0), padx=(24, 0))
            else:
                self._ocr_vision_frame.pack_forget()

        _cb_ocr_prov.bind("<<ComboboxSelected>>", _on_ocr_prov)
        self._var_ruta_ocr.trace_add("write", _on_ruta_change)
        _on_ocr_prov()
        _on_ruta_change()   # estado inicial

        # ── Opción: usar zonas etiquetadas ────────────────────────────────────
        etz_card = tk.Frame(ruta_inner, bg="#0E1114", relief="solid", bd=1)
        etz_card.pack(fill="x", pady=(8, 0))
        etz_inner = tk.Frame(etz_card, bg="#0E1114", padx=10, pady=6)
        etz_inner.pack(fill="x")

        self._var_ocr_usar_etiquetas = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            etz_inner,
            text="Usar zonas etiquetadas del Etiquetador",
            variable=self._var_ocr_usar_etiquetas,
        ).pack(side="left")

        tk.Label(etz_inner,
                 text="— solo procesa las zonas marcadas como texto; mantiene el orden de lectura",
                 bg="#0E1114", fg="#646D72", font=("Segoe UI", 8)).pack(side="left", padx=(6, 0))

        self._var_ocr_det_auto = tk.BooleanVar(value=False)
        det_row = tk.Frame(etz_card, bg="#0E1114", padx=10, pady=6)
        det_row.pack(fill="x")
        ttk.Checkbutton(
            det_row,
            text="Detección automática IA en páginas sin etiquetar",
            variable=self._var_ocr_det_auto,
        ).pack(side="left")
        tk.Label(det_row,
                 text="(requiere IA activa)",
                 bg="#0E1114", fg="#646D72", font=("Segoe UI", 8)).pack(side="left", padx=4)

        # ── Sub-opciones Kraken ────────────────────────────────────────────────
        kraken_card = tk.Frame(ruta_inner, bg=CONTENT_BG, relief="solid", bd=1)
        kraken_card.pack(fill="x", pady=(4, 0))
        ki = tk.Frame(kraken_card, bg=CONTENT_BG, padx=10, pady=6); ki.pack(fill="x")
        tk.Label(ki, text="Modelo Kraken:", bg=CONTENT_BG, fg="#E8E5DF",
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        self._var_kraken_modelo = tk.StringVar(value="")
        tk.Entry(ki, textvariable=self._var_kraken_modelo, width=42,
                 font=("Segoe UI", 8), relief="solid", bd=1).pack(side="left", padx=6)
        ttk.Button(ki, text="📂", width=3,
                   command=self._ocr_elegir_modelo_kraken).pack(side="left", padx=(0, 6))
        self._btn_catmus = ttk.Button(ki, text="⬇ Descargar CATMuS-Print",
                                       style="S.TButton",
                                       command=self._ocr_descargar_catmus)
        self._btn_catmus.pack(side="left")
        self._lbl_kraken_ok = tk.Label(ki, text="", bg=CONTENT_BG, fg=VERDE,
                                        font=("Segoe UI", 8))
        self._lbl_kraken_ok.pack(side="left", padx=6)
        # Verificar Kraken al construir el panel
        self.after(200, self._ocr_verificar_kraken)

        # ── Paralelismo Kraken ────────────────────────────────────────────────
        kpar = tk.Frame(kraken_card, bg=CONTENT_BG, padx=10, pady=4)
        kpar.pack(fill="x")

        # Fila 1: selector de workers + explicación
        kpar_row1 = tk.Frame(kpar, bg=CONTENT_BG); kpar_row1.pack(fill="x")
        tk.Label(kpar_row1, text="Páginas en paralelo:", bg=CONTENT_BG, fg="#E8E5DF",
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        self._var_kraken_workers = tk.IntVar(value=3)
        spin = tk.Spinbox(kpar_row1, from_=1, to=12,
                          textvariable=self._var_kraken_workers,
                          width=3, font=("Segoe UI", 9),
                          command=self._ocr_actualizar_estimacion)
        spin.pack(side="left", padx=(6, 10))
        spin.bind("<FocusOut>", lambda e: self._ocr_actualizar_estimacion())
        spin.bind("<Return>",   lambda e: self._ocr_actualizar_estimacion())

        tk.Label(kpar_row1, text="Timeout por página (seg):", bg=CONTENT_BG,
                 fg="#E8E5DF", font=("Segoe UI", 8)).pack(side="left", padx=(10, 0))
        self._var_kraken_timeout = tk.IntVar(value=600)
        spin_to = tk.Spinbox(kpar_row1, from_=60, to=3600,
                             textvariable=self._var_kraken_timeout,
                             increment=60, width=5, font=("Segoe UI", 9))
        spin_to.pack(side="left", padx=(6, 6))
        self._mk_ayuda(kpar_row1,
            "Tiempo máximo que Bashkar espera a Kraken por página.\n\n"
            "Si Kraken tarda más que este límite, la página se marca\n"
            "como fallida y se intenta con Tesseract como respaldo.\n\n"
            "Valores sugeridos:\n"
            "  Páginas simples (texto solo):       120–180 seg\n"
            "  Páginas mixtas (texto + fotos):     300–600 seg\n"
            "  Páginas muy complejas (publicidad): 600–900 seg\n\n"
            "Si ves muchos errores de timeout, súbelo.\n"
            "Si el corpus es simple, bájalo para detectar\n"
            "páginas problemáticas más rápido.")

        self._mk_ayuda(kpar_row1,
            "Cuántas páginas procesa Kraken al mismo tiempo.\n\n"
            "Cada proceso paralelo carga el modelo en RAM (~400 MB).\n"
            "Recomendaciones según tu equipo:\n\n"
            "  4 GB RAM  →  1 proceso (sin paralelismo)\n"
            "  8 GB RAM  →  2-3 procesos  ← tu equipo (7.3 GB)\n"
            "  16 GB RAM →  4-6 procesos\n"
            "  32 GB RAM →  8-10 procesos\n\n"
            "Más procesos = más rápido, pero si te quedas sin RAM\n"
            "el sistema empieza a usar disco (swap) y se vuelve\n"
            "más lento que con menos procesos.\n\n"
            "Empieza con el valor sugerido y auméntalo si el\n"
            "procesador no llega al 80% de uso durante el OCR.")

        # Fila 2: estimación de tiempo
        kpar_row2 = tk.Frame(kpar, bg=CONTENT_BG); kpar_row2.pack(fill="x", pady=(4, 0))
        tk.Label(kpar_row2, text="Tiempo estimado:", bg=CONTENT_BG, fg="#E8E5DF",
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        self._lbl_kraken_est = tk.Label(kpar_row2,
                                         text="— (carga un proyecto para estimar)",
                                         bg=CONTENT_BG, fg="#777F84",
                                         font=("Segoe UI", 8))
        self._lbl_kraken_est.pack(side="left", padx=(6, 10))

        self._mk_ayuda(kpar_row2,
            "Estimación basada en el corpus del proyecto activo.\n\n"
            "Velocidad de referencia: ~60 seg/página en Ryzen 5 5500U\n"
            "con 1 proceso. Con N procesos: tiempo ÷ N (aprox.).\n\n"
            "La primera vez que corres Kraken en tu equipo puede\n"
            "ser más lento por la carga inicial del modelo.\n"
            "Las corridas siguientes suelen ser más rápidas.\n\n"
            "La estimación mejora si previamente usas 'Calibrar'\n"
            "sobre una página real de tu corpus.")

        ttk.Button(kpar_row2, text="↺ Calibrar",
                   style="S.TButton",
                   command=self._ocr_calibrar_kraken).pack(side="left")

        # Calcular estimación inicial si hay proyecto cargado
        self.after(500, self._ocr_actualizar_estimacion)

        # ── Sub-opciones Ollama ────────────────────────────────────────────────
        ollama_card = tk.Frame(ruta_inner, bg=CONTENT_BG, relief="solid", bd=1)
        ollama_card.pack(fill="x", pady=(4, 0))
        oi = tk.Frame(ollama_card, bg=CONTENT_BG, padx=10, pady=6); oi.pack(fill="x")
        tk.Label(oi, text="Modelo Ollama:", bg=CONTENT_BG, fg="#E8E5DF",
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        self._var_ollama_modelo = tk.StringVar(value="qwen3.6:latest")
        self._cmb_ollama = ttk.Combobox(
            oi, textvariable=self._var_ollama_modelo,
            # Valores por defecto ANTES de que "🔄 Detectar modelos" corra
            # (se pobla de verdad con lo que haya instalado, vía la API real
            # de Ollama — ver _ocr_detectar_ollama). qwen3.6/gemma4/gemma3
            # son los modelos de visión que confirmadamente tiene el
            # investigador instalados (ollama show → capabilities: vision).
            values=["qwen3.6:latest", "gemma4:latest", "gemma3:4b", "qwen2.5vl:7b", "llava:13b"],
            state="normal", width=20, font=("Segoe UI", 8))
        self._cmb_ollama.pack(side="left", padx=6)
        ttk.Button(oi, text="🔄 Detectar modelos", style="S.TButton",
                   command=self._ocr_detectar_ollama).pack(side="left", padx=(0, 6))
        self._lbl_ollama_ok = tk.Label(oi, text="", bg=CONTENT_BG, fg="#777F84",
                                        font=("Segoe UI", 8))
        self._lbl_ollama_ok.pack(side="left", padx=6)
        self.after(300, self._ocr_detectar_ollama)

        # ── Preprocesamiento de imagen ────────────────────────────────────────
        pre_card = tk.Frame(ruta_inner, bg=CARD_BG, relief="solid", bd=1)
        pre_card.pack(fill="x", pady=(6, 0))
        pi_f = tk.Frame(pre_card, bg=CARD_BG, padx=10, pady=5)
        pi_f.pack(fill="x")
        tk.Label(pi_f, text="Preprocesamiento de imagen:",
                 bg=CARD_BG, fg=TXT_PRI,
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        # Desactivados por defecto — activar solo si la imagen lo necesita
        self._var_pre_deskew    = tk.BooleanVar(value=False)
        self._var_pre_enhance   = tk.BooleanVar(value=False)
        self._var_pre_despeckle = tk.BooleanVar(value=False)
        for txt, var in [("Deskew (inclinación)", self._var_pre_deskew),
                          ("CLAHE (contraste)",    self._var_pre_enhance),
                          ("Despeckle (ruido)",    self._var_pre_despeckle)]:
            ttk.Checkbutton(pi_f, text=txt, variable=var).pack(side="left", padx=(8, 0))

        # Botón preview — muestra la imagen antes y después del preprocesamiento
        tk.Label(pi_f, text="  ", bg=CARD_BG).pack(side="left")
        _btn_prev = tk.Label(pi_f, text="🔍 Preview", bg=CARD_BG, fg=TXT_SEC,
                              font=("Segoe UI", 8), cursor="hand2")
        _btn_prev.pack(side="left", padx=(4, 0))
        _btn_prev.bind("<Button-1>", lambda e: self._ocr_preview_preprocesamiento())
        _btn_prev.bind("<Enter>", lambda e: _btn_prev.config(fg=TXT_PRI))
        _btn_prev.bind("<Leave>", lambda e: _btn_prev.config(fg=TXT_SEC))

        self._mk_ayuda(pi_f,
            "Preprocesamiento aplicado antes del OCR (desactivado por defecto):\n\n"
            "Deskew: Endereza páginas torcidas 1-4°. Útil para escanes de la BNC.\n"
            "Activar solo si las páginas tienen inclinación visible.\n\n"
            "CLAHE: Mejora contraste en papel amarillado o con iluminación no uniforme.\n\n"
            "Despeckle: Elimina puntos de papel envejecido.\n"
            "Puede borrar puntuación fina — activar con cuidado.\n\n"
            "Las originales a color siempre se preservan en 02_imagenes/.\n"
            "Las imágenes procesadas se guardan en 02_imagenes_ocr/.\n"
            "Usa 🔍 Preview para ver el efecto antes de correr el OCR completo.")

        # ── Opciones avanzadas de salida ──────────────────────────────────────
        def _build_ocr_avanzado(f):
            row1 = tk.Frame(f, bg=CONTENT_BG); row1.pack(fill="x", pady=2)
            tk.Label(row1, text="Umbral confianza para revisión manual (%):",
                     bg=CONTENT_BG, fg=TXT_SEC, font=("Segoe UI", 8)).pack(side="left")
            self._var_ocr_umbral_rev = tk.IntVar(value=70)
            ttk.Spinbox(row1, from_=10, to=99, textvariable=self._var_ocr_umbral_rev,
                        width=5).pack(side="left", padx=6)
            tk.Label(row1, text="(páginas por debajo irán a revisión)",
                     bg=CONTENT_BG, fg=TXT_DIM, font=("Segoe UI", 8)).pack(side="left")

            row2 = tk.Frame(f, bg=CONTENT_BG); row2.pack(fill="x", pady=2)
            self._var_ocr_guardar_json = tk.BooleanVar(value=False)
            ttk.Checkbutton(row2, text="Guardar metadata de confianza por página (.json)",
                            variable=self._var_ocr_guardar_json).pack(side="left")

            row3 = tk.Frame(f, bg=CONTENT_BG); row3.pack(fill="x", pady=2)
            self._var_ocr_combinar_paginas = tk.BooleanVar(value=True)
            ttk.Checkbutton(row3, text="Combinar páginas en un solo TXT por número",
                            variable=self._var_ocr_combinar_paginas).pack(side="left")

        self._mk_avanzado(pad, "Opciones avanzadas de extracción", _build_ocr_avanzado)

        # ── Botones ───────────────────────────────────────────────────────────
        bf = tk.Frame(pad, bg=CONTENT_BG); bf.pack(fill="x", pady=(0, 8))
        self._btn_ocr = ttk.Button(bf, text="▶  Iniciar extracción",
                                    style="P.TButton", command=self._start_ocr)
        self._btn_ocr.pack(side="left", padx=(0, 12))
        ttk.Button(bf, text="✍ Re-normalizar textos", style="S.TButton",
                   command=self._renormalizar_textos).pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="📐 Completar costura", style="S.TButton",
                   command=self._gutter_completar_corpus).pack(side="left", padx=(0, 8))
        self._mk_ayuda(bf,
            "Completar costura: detecta palabras cortadas por el pliegue de\n"
            "encuadernación y las reconstruye con IA. Las palabras generadas\n"
            "aparecen marcadas con ⟦⟧ y en rojo en las exportaciones DOCX.\n"
            "Requiere IA habilitada y API key configurada.")
        ttk.Button(bf, text="Mejorar con IA", style="S.TButton",
                   command=self._start_mejorar_ocr).pack(side="left", padx=(0, 4))
        # Selector de proveedor LLM para corrección post-OCR
        self._var_ocr_llm_prov = tk.StringVar(value="claude")
        cmb_prov_ocr = ttk.Combobox(bf, textvariable=self._var_ocr_llm_prov,
                     values=["claude", "openai", "gemini", "ollama", "lmstudio"],
                     state="readonly", width=8,
                     font=("Segoe UI", 9))
        cmb_prov_ocr.pack(side="left", padx=(0, 2))
        # Modelo local (visible solo cuando proveedor=ollama/lmstudio)
        self._var_ocr_ollama_modelo = tk.StringVar(value="qwen3.6")
        self._cmb_ocr_ollama_modelo = ttk.Combobox(
            bf, textvariable=self._var_ocr_ollama_modelo,
            values=["qwen3.6", "gemma4", "gemma3:4b", "latamgpt", "llama3.1", "mistral", "qwen2.5"],
            state="normal", width=10, font=("Segoe UI", 9))
        # mostrar/ocultar según proveedor; para lmstudio consulta qué hay cargado
        def _ocr_prov_changed(*_):
            prov = self._var_ocr_llm_prov.get()
            if prov == "lmstudio":
                from core.ocr_llm import modelos_cargados_lmstudio
                modelos = modelos_cargados_lmstudio()
                self._cmb_ocr_ollama_modelo.config(values=modelos)
                if modelos and self._var_ocr_ollama_modelo.get() not in modelos:
                    self._var_ocr_ollama_modelo.set(modelos[0])
                self._cmb_ocr_ollama_modelo.pack(side="left", padx=(0, 8))
            elif prov == "ollama":
                self._cmb_ocr_ollama_modelo.config(
                    values=["qwen3.6", "gemma4", "gemma3:4b", "latamgpt", "llama3.1", "mistral", "qwen2.5"])
                self._cmb_ocr_ollama_modelo.pack(side="left", padx=(0, 8))
            else:
                self._cmb_ocr_ollama_modelo.pack_forget()
        self._var_ocr_llm_prov.trace_add("write", _ocr_prov_changed)
        self._mk_ayuda(bf,
            "Mejorar con IA: aplica Vision o corrección post-OCR\n"
            "a páginas con confianza Tesseract por debajo del umbral.\n"
            "Proveedores: claude / openai / gemini / ollama / lmstudio\n"
            "  → ollama: escribe el modelo (ej: latamgpt, llama3.1)\n"
            "  → lmstudio: servidor local (Developer → Start Server),\n"
            "    lista los modelos cargados automáticamente\n"
            "Umbral 60: solo páginas malas. Umbral 40: más agresivo.")
        tk.Label(bf, text="Umbral IA:", bg=CONTENT_BG, fg="#E8E5DF",
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 2))
        self._var_ocr_umbral = tk.IntVar(value=60)
        tk.Spinbox(bf, from_=10, to=90, textvariable=self._var_ocr_umbral,
                   width=4, font=("Segoe UI", 9), relief="solid", bd=1).pack(side="left", padx=(0,12))
        tk.Label(bf, text="⚠  Confirma la configuración antes de empezar",
                 bg=CONTENT_BG, fg=ACENT, font=("Segoe UI", 9)).pack(side="left")

        # ── Log ───────────────────────────────────────────────────────────────
        log_frame = tk.Frame(pad, bg="#12171B", bd=1, relief="solid")
        log_frame.pack(fill="both", expand=True)
        log_hdr = tk.Frame(log_frame, bg="#14202A")
        log_hdr.pack(fill="x")
        tk.Label(log_hdr, text="  📋  Registro de actividad",
                 bg="#14202A", fg="#B5B6B3",
                 font=("Segoe UI", 8, "bold")).pack(side="left", pady=4)
        self._log_w = scrolledtext.ScrolledText(log_frame, height=12,
                                                 font=("Consolas", 9),
                                                 bg="#12171B", fg="#6CA8E8",
                                                 relief="flat", insertbackground="white",
                                                 selectbackground="#6CA8E8")
        self._log_w.pack(fill="both", expand=True, padx=1, pady=(0, 1))
        self._log_w.config(state="disabled")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB CONV: CONVERSOR MASIVO PDF → WORD / TXT
    # ══════════════════════════════════════════════════════════════════════════
    def _build_conv(self):
        """Panel de conversión masiva PDF→Word/TXT (ruta rápida, sin re-OCR)."""
        try:
            from core.conversor_pdf_a_word import (
                ConfiguracionConversor,
                ConversorPDFaWord,
            )
            self._conv_disponible = True
        except ImportError as _conv_err:
            self._conv_disponible = False
            self._conv_import_error = str(_conv_err)

        f = self._tab_conv
        self._page_header(
            f,
            "Conversor masivo PDF → Word / TXT",
            "Para PDFs que ya tienen texto: extrae y organiza en carpetas sin volver a hacer OCR.",
            "⚡",
        )

        pad = tk.Frame(f, bg=CONTENT_BG)
        pad.pack(fill="both", expand=True, padx=24, pady=16)

        # ── Dependencias faltantes ────────────────────────────────────────────
        if not self._conv_disponible:
            err_card = tk.Frame(pad, bg="#2A2116", relief="solid", bd=1,
                                highlightbackground="#D58B45", highlightthickness=1)
            err_card.pack(fill="x", pady=(0, 16))
            err_inner = tk.Frame(err_card, bg="#2A2116", padx=16, pady=14)
            err_inner.pack(fill="x")
            tk.Label(err_inner, text="⚠  Faltan librerías requeridas",
                     bg="#2A2116", fg="#D58B45",
                     font=("Segoe UI", 10, "bold")).pack(anchor="w")
            tk.Label(err_inner,
                     text=f"Error: {getattr(self, '_conv_import_error', '')}\n\n"
                          "Solución: abrí una terminal y ejecutá\n"
                          "    pip install pymupdf python-docx",
                     bg="#2A2116", fg="#E5AD5A",
                     font=("Segoe UI", 9), justify="left").pack(anchor="w", pady=(6, 0))
            return

        # ── Variables de estado ───────────────────────────────────────────────
        self._conv_entrada  = tk.StringVar(value=getattr(ST, "pdf_dir", "") or "")
        self._conv_salida   = tk.StringVar(value=getattr(ST, "out_dir", "") or "")
        self._conv_word_con = tk.BooleanVar(value=True)
        self._conv_word_pag = tk.BooleanVar(value=False)
        self._conv_txt_con  = tk.BooleanVar(value=True)
        self._conv_txt_pag  = tk.BooleanVar(value=False)
        self._conv_frag     = tk.BooleanVar(value=False)
        self._conv_limpiar   = tk.BooleanVar(value=True)
        self._conv_al_norm   = tk.BooleanVar(value=True)
        self._conv_desde     = tk.StringVar(value="")
        self._conv_hasta     = tk.StringVar(value="")
        self._conv_modo      = tk.StringVar(value="texto")
        self._conv_proc      = None

        # ══ PASO 1 — Carpetas ════════════════════════════════════════════════
        c1 = self._card(pad, "  1  Elegí las carpetas")

        def _fila_dir(parent, etiqueta, descripcion, var, comando):
            fila = tk.Frame(parent, bg=CARD_BG)
            fila.pack(fill="x", pady=(0, 8))
            tk.Label(fila, text=etiqueta, bg=CARD_BG, fg=TXT_PRI,
                     font=("Segoe UI", 9, "bold"), width=8,
                     anchor="w").pack(side="left")
            tk.Label(fila, text=descripcion, bg=CARD_BG, fg=TXT_DIM,
                     font=("Segoe UI", 8)).pack(side="left", padx=(0, 8))
            tk.Button(fila, text="📁 Seleccionar", bg=AZ3, fg="#E8E5DF",
                      relief="flat", font=("Segoe UI", 8), padx=8, pady=3,
                      cursor="hand2", command=comando).pack(side="right")
            tk.Entry(fila, textvariable=var, bg=CARD_BG, fg=TXT_SEC,
                     relief="solid", bd=1, font=("Segoe UI", 8),
                     state="readonly").pack(side="right", fill="x",
                                           expand=True, padx=(0, 8))

        def _sel_entrada():
            d = filedialog.askdirectory(title="Carpeta con los PDF originales")
            if d:
                self._conv_entrada.set(d)
                ST.pdf_dir = d

        def _sel_salida():
            d = filedialog.askdirectory(title="Carpeta donde guardar los archivos convertidos")
            if d:
                self._conv_salida.set(d)
                ST.out_dir = d

        _fila_dir(c1, "Entrada", "carpeta con los PDF a convertir",
                  self._conv_entrada, _sel_entrada)
        _fila_dir(c1, "Salida",  "dónde guardar los Word y TXT",
                  self._conv_salida, _sel_salida)

        # ── Nota explicativa ──────────────────────────────────────────────────
        tk.Label(c1,
                 text="ℹ  Cada PDF genera su propia subcarpeta con los archivos organizados.",
                 bg=CARD_BG, fg=TXT_DIM, font=("Segoe UI", 8),
                 justify="left").pack(anchor="w", pady=(0, 4))

        # ══ PASO 2 — Qué generar ═════════════════════════════════════════════
        c2 = self._card(pad, "  2  Qué archivos querés generar")

        for var, titulo, desc in [
            (self._conv_word_con, "📄  Word (.docx)",
             "Un documento Word por PDF, con todo el texto. Ideal para leer y citar."),
            (self._conv_txt_con,  "📃  Texto plano (.txt)",
             "Un archivo TXT por PDF. Más liviano, ideal para análisis computacional."),
            (self._conv_frag,     "📎  PDF por página",
             "Divide cada PDF en páginas individuales (opcional, ocupa más espacio)."),
        ]:
            row = tk.Frame(c2, bg=CARD_BG)
            row.pack(fill="x", pady=3)
            ttk.Checkbutton(row, text=titulo, variable=var).pack(side="left")
            tk.Label(row, text=desc, bg=CARD_BG, fg=TXT_DIM,
                     font=("Segoe UI", 8)).pack(side="left", padx=(8, 0))

        # ── Separador ─────────────────────────────────────────────────────────
        tk.Frame(c2, bg=CARD_BOR, height=1).pack(fill="x", pady=(8, 8))

        # ── Limpieza de texto ─────────────────────────────────────────────────
        limpiar_row = tk.Frame(c2, bg=CARD_BG)
        limpiar_row.pack(fill="x", pady=2)
        ttk.Checkbutton(limpiar_row,
                        text="🧹  Limpiar el texto automáticamente",
                        variable=self._conv_limpiar).pack(side="left")
        self._mk_ayuda(limpiar_row,
            "Aplica limpieza al texto extraído de cada página:\n\n"
            "  ✓ Elimina los números de coordenadas que aparecen\n"
            "    entre párrafos (artefacto de los PDF de la BNC)\n"
            "  ✓ Elimina el sello 'Digitalizado Biblioteca Nacional'\n"
            "  ✓ Une palabras cortadas al final de columna (pági-\n"
            "    nas → páginas)\n"
            "  ✓ Corrige errores OCR frecuentes (6→á, 11→ll, 1→l)\n"
            "  ✓ Normaliza tildes y caracteres especiales\n\n"
            "Preserva el español de época: habia, fué, Luégo, etc.\n"
            "son grafías históricas legítimas, no errores.\n\n"
            "Desactivá esta opción solo si necesitás el texto\n"
            "completamente sin procesar.")
        tk.Label(limpiar_row,
                 text="  ← recomendado para corpus BNC",
                 bg=CARD_BG, fg=TXT_DIM, font=("Segoe UI", 8)).pack(side="left")

        norm_row = tk.Frame(c2, bg=CARD_BG)
        norm_row.pack(fill="x", pady=(4, 0))
        ttk.Checkbutton(norm_row,
                        text="📝  Enviar al módulo Normalizar",
                        variable=self._conv_al_norm).pack(side="left")
        self._mk_ayuda(norm_row,
            "Copia el texto de cada página en la estructura que\n"
            "usa el módulo Normalizar (03_ocr/<nombre>/p0001.txt).\n\n"
            "Con esta opción activada, al terminar la conversión\n"
            "podés ir directamente a Normalizar para revisar y\n"
            "corregir el texto página por página antes del NER.\n\n"
            "Usa la carpeta de salida del proyecto (configurada\n"
            "en Configuración). Si no hay proyecto abierto, esta\n"
            "opción se ignora.")
        tk.Label(norm_row,
                 text="  ← conecta con el pipeline de análisis",
                 bg=CARD_BG, fg=TXT_DIM, font=("Segoe UI", 8)).pack(side="left")

        # ── Rango de páginas (avanzado, colapsado) ────────────────────────────
        rango_row = tk.Frame(c2, bg=CARD_BG)
        rango_row.pack(fill="x", pady=(6, 0))
        tk.Label(rango_row, text="Páginas:", bg=CARD_BG, fg=TXT_DIM,
                 font=("Segoe UI", 8)).pack(side="left")
        tk.Label(rango_row, text="desde", bg=CARD_BG, fg=TXT_DIM,
                 font=("Segoe UI", 8)).pack(side="left", padx=(8, 2))
        tk.Entry(rango_row, textvariable=self._conv_desde, width=5,
                 bg=CARD_BG, fg=TXT_PRI, relief="solid", bd=1,
                 font=("Segoe UI", 8)).pack(side="left")
        tk.Label(rango_row, text="hasta", bg=CARD_BG, fg=TXT_DIM,
                 font=("Segoe UI", 8)).pack(side="left", padx=(6, 2))
        tk.Entry(rango_row, textvariable=self._conv_hasta, width=5,
                 bg=CARD_BG, fg=TXT_PRI, relief="solid", bd=1,
                 font=("Segoe UI", 8)).pack(side="left")
        tk.Label(rango_row, text="  (vacío = todas)",
                 bg=CARD_BG, fg=TXT_DIM, font=("Segoe UI", 8)).pack(side="left")

        # ══ BOTONES DE ACCIÓN ════════════════════════════════════════════════
        # Deben ir ANTES del widget con expand=True (regla de layout Tkinter)
        btn_row = tk.Frame(pad, bg=CONTENT_BG)
        btn_row.pack(fill="x", pady=(4, 10))

        self._btn_conv_iniciar = tk.Button(
            btn_row, text="⚡  Convertir ahora",
            bg=AZ3, fg="#E8E5DF", relief="flat",
            font=("Segoe UI", 11, "bold"), padx=24, pady=8,
            cursor="hand2", command=self._conv_iniciar)
        self._btn_conv_iniciar.pack(side="left", padx=(0, 10))

        self._btn_conv_cancelar = tk.Button(
            btn_row, text="✖  Detener",
            bg=CARD_BG, fg=TXT_SEC, relief="flat",
            font=("Segoe UI", 10), padx=16, pady=8,
            cursor="hand2", command=self._conv_cancelar,
            state="disabled")
        self._btn_conv_cancelar.pack(side="left", padx=(0, 10))

        self._btn_conv_abrir = tk.Button(
            btn_row, text="📂  Ver archivos generados",
            bg=CARD_BG, fg=TXT_SEC, relief="flat",
            font=("Segoe UI", 10), padx=16, pady=8,
            cursor="hand2", command=self._conv_abrir_salida,
            state="disabled")
        self._btn_conv_abrir.pack(side="left")

        # ══ PROGRESO ═════════════════════════════════════════════════════════
        prog_card = tk.Frame(pad, bg=CARD_BG, relief="solid", bd=1,
                             highlightbackground=CARD_BOR, highlightthickness=1)
        prog_card.pack(fill="x", pady=(0, 8))
        prog_inner = tk.Frame(prog_card, bg=CARD_BG, padx=16, pady=12)
        prog_inner.pack(fill="x")

        self._conv_lbl_fase = tk.Label(
            prog_inner, text="Listo para convertir.",
            bg=CARD_BG, fg=TXT_DIM, font=("Segoe UI", 9, "italic"))
        self._conv_lbl_fase.pack(anchor="w")

        self._conv_prog = ttk.Progressbar(
            prog_inner, mode="determinate", length=600, maximum=100)
        self._conv_prog.pack(fill="x", pady=(6, 0))

        # ══ REGISTRO DE ACTIVIDAD ════════════════════════════════════════════
        log_hdr = tk.Frame(pad, bg=CONTENT_BG)
        log_hdr.pack(fill="x", pady=(4, 2))
        tk.Label(log_hdr, text="Registro de actividad",
                 bg=CONTENT_BG, fg=TXT_DIM,
                 font=("Segoe UI", 8, "bold")).pack(side="left")

        self._conv_log = tk.Text(
            pad, bg=CARD_BG, fg=TXT_SEC,
            font=("Segoe UI", 9), height=8,
            relief="solid", bd=1, state="disabled",
            wrap="word")
        self._conv_log.pack(fill="both", expand=True)

    def _conv_log_append(self, texto: str, color: str = "#B5B6B3"):
        try:
            self._conv_log.config(state="normal")
            tag = f"c{abs(hash(color))}"
            self._conv_log.tag_configure(tag, foreground=color)
            self._conv_log.insert("end", texto + "\n", tag)
            self._conv_log.see("end")
            self._conv_log.config(state="disabled")
        except Exception:
            pass

    def _conv_log_clear(self):
        try:
            self._conv_log.config(state="normal")
            self._conv_log.delete("1.0", "end")
            self._conv_log.config(state="disabled")
        except Exception:
            pass

    def _conv_iniciar(self):
        try:
            from core.conversor_pdf_a_word import (
                ConfiguracionConversor,
                ConversorPDFaWord,
            )
        except ImportError as e:
            messagebox.showerror("Conversor", f"Faltan librerías:\n{e}\n\npip install pymupdf python-docx")
            return

        entrada = self._conv_entrada.get().strip()
        salida  = self._conv_salida.get().strip()
        if not entrada:
            messagebox.showwarning("Conversor", "Selecciona la carpeta de entrada.")
            return
        if not salida:
            messagebox.showwarning("Conversor", "Selecciona la carpeta de salida.")
            return
        if not os.path.isdir(entrada):
            messagebox.showwarning("Conversor",
                f"La carpeta de entrada no existe:\n{entrada}")
            return
        pdfs_disponibles = list(Path(entrada).glob("*.pdf"))
        if not pdfs_disponibles:
            messagebox.showwarning("Conversor",
                f"No se encontraron archivos PDF en:\n{entrada}\n\n"
                "Verificá que la carpeta seleccionada contenga los PDF directamente\n"
                "(no en subcarpetas).")
            return

        def _int_o_none(var):
            v = var.get().strip()
            try:
                return int(v) if v else None
            except ValueError:
                return None

        al_norm  = self._conv_al_norm.get()
        out_dir  = getattr(ST, "out_dir", None)
        cfg = ConfiguracionConversor(
            carpeta_entrada          = entrada,
            carpeta_salida           = salida,
            modo_texto               = self._conv_modo.get(),
            fragmentar_pdf           = self._conv_frag.get(),
            word_consolidado         = self._conv_word_con.get(),
            word_por_pagina          = self._conv_word_pag.get(),
            txt_consolidado          = self._conv_txt_con.get(),
            txt_por_pagina           = self._conv_txt_pag.get(),
            limpiar_texto            = self._conv_limpiar.get(),
            exportar_para_normalizar = al_norm and out_dir is not None,
            carpeta_out_dir          = out_dir,
            paginas_desde            = _int_o_none(self._conv_desde),
            paginas_hasta            = _int_o_none(self._conv_hasta),
        )

        self._btn_conv_iniciar.config(state="disabled")
        self._btn_conv_cancelar.config(state="normal")
        self._btn_conv_abrir.config(state="disabled")
        self._conv_prog["value"] = 0
        self._conv_lbl_fase.config(text="Iniciando conversión…")
        self._conv_log_clear()
        self._conv_log_append(f"Carpeta de entrada:  {entrada}", "#646D72")
        self._conv_log_append(f"Carpeta de salida:   {salida}", "#646D72")
        self._conv_log_append("─" * 48, "#22292F")

        def _on_progress(ev):
            pct  = ev.get("porcentaje", 0)
            npdf = ev.get("indice_pdf", 0)
            tot  = ev.get("total_pdfs", 1)
            pag  = ev.get("pagina", 0)
            tpag = ev.get("total_paginas", 0)
            nombre = ev.get("pdf", "")
            msg  = f"PDF {npdf}/{tot}  ·  {nombre}  ·  página {pag}/{tpag}"
            self._conv_prog.after(0, lambda p=pct, m=msg: (
                self._conv_prog.config(value=p),
                self._conv_lbl_fase.config(text=m),
            ))

        def _worker():
            try:
                proc = ConversorPDFaWord(cfg, callback_progreso=_on_progress)
                self._conv_proc = proc
                reporte = proc.procesar_todo()
                self._conv_prog.after(0, lambda: self._conv_finalizar(reporte))
            except Exception as exc:
                import traceback
                tb = traceback.format_exc()
                self._conv_prog.after(0, lambda e=str(exc), t=tb: self._conv_error(e, t))

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def _conv_finalizar(self, reporte: dict):
        self._btn_conv_iniciar.config(state="normal")
        self._btn_conv_cancelar.config(state="disabled")
        self._btn_conv_abrir.config(state="normal")

        cancelado = reporte.get("cancelado", False)
        pdfs      = reporte.get("pdfs", [])
        n_ok      = sum(1 for d in pdfs if "error" not in d)
        n_err     = sum(1 for d in pdfs if "error" in d)
        n_pags    = sum(d.get("paginas_procesadas", 0) for d in pdfs if "error" not in d)
        seg       = reporte.get("segundos_totales", 0)

        if cancelado:
            self._conv_prog["value"] = 0
            self._conv_lbl_fase.config(text="Conversión detenida por el usuario.")
            self._conv_log_append("\n⚠  Proceso detenido antes de terminar.", "#D58B45")
        else:
            self._conv_prog["value"] = 100
            mins = int(seg) // 60
            secs = int(seg) % 60
            tiempo = f"{mins} min {secs} s" if mins else f"{secs} s"
            self._conv_lbl_fase.config(
                text=f"✓  Conversión completada en {tiempo}")
            self._conv_log_append("─" * 48, "#22292F")
            self._conv_log_append(
                f"✓  {n_ok} PDF convertidos  ·  {n_pags} páginas procesadas  ·  {tiempo}",
                "#6EC69A")

        if n_err:
            self._conv_log_append(
                f"⚠  {n_err} PDF no pudieron procesarse:", "#D58B45")
            for d in pdfs:
                if "error" in d:
                    self._conv_log_append(
                        f"   • {d['archivo']}: {d['error']}", "#D58B45")
        for d in pdfs:
            if "error" not in d and d.get("paginas_sin_texto", 0) > 0:
                self._conv_log_append(
                    f"   ℹ  {d['archivo']}: {d['paginas_sin_texto']} páginas sin texto detectable",
                    "#777F84")

        # Refrescar Normalizar y reconstruir corpus_meta si se exportó a 03_ocr/
        if self._conv_al_norm.get() and getattr(ST, "out_dir", None):
            try:
                self._reconstruir_corpus_meta_desde_txt()
                self._norm_refrescar_numeros()
                self._conv_log_append(
                    "📝  Texto disponible en Normalizar y Segmentar.", "#6EC69A")
            except Exception:
                pass

    def _conv_error(self, exc_str: str, tb: str):
        self._btn_conv_iniciar.config(state="normal")
        self._btn_conv_cancelar.config(state="disabled")
        self._conv_lbl_fase.config(text="Error durante la conversión.")
        self._conv_log_append(f"\n✗ Error: {exc_str}", "#D58B45")
        self._conv_log_append(tb, "#646D72")

    def _conv_cancelar(self):
        if self._conv_proc:
            self._conv_proc.cancelar()
        self._btn_conv_cancelar.config(state="disabled")
        self._conv_lbl_fase.config(text="Cancelando…")

    def _conv_abrir_salida(self):
        salida = self._conv_salida.get().strip()
        if salida and os.path.isdir(salida):
            import subprocess
            subprocess.Popen(["explorer", os.path.normpath(salida)])

    def _build_mmx(self):
        """Panel de extracción multimodal: imágenes de página → JSON estricto
        (artículo jerárquico + imágenes con pies + publicidad) → .md, con opción
        de alimentar el corpus textual. Respuesta al hallazgo de auditoría: las
        imágenes BNC requieren IA de visión; aquí su salida queda estructurada."""
        try:
            from core import extractor_multimodal  # noqa: F401
            self._mmx_disponible = True
        except ImportError as _mmx_err:
            self._mmx_disponible = False
            self._mmx_import_error = str(_mmx_err)

        f = self._tab_mmx
        self._page_header(
            f,
            "Extracción multimodal con IA",
            "Convierte imágenes de página en datos estructurados (texto jerárquico, "
            "fotos con pies, publicidad) usando IA de visión.",
            "🧠",
        )

        pad = tk.Frame(f, bg=CONTENT_BG)
        pad.pack(fill="both", expand=True, padx=24, pady=16)

        if not self._mmx_disponible:
            err = tk.Frame(pad, bg="#2A2116", relief="solid", bd=1)
            err.pack(fill="x", pady=(0, 16))
            tk.Label(err, text="⚠  No se pudo cargar core/extractor_multimodal",
                     bg="#2A2116", fg="#D58B45",
                     font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=14, pady=10)
            tk.Label(err, text=getattr(self, "_mmx_import_error", ""),
                     bg="#2A2116", fg="#E5AD5A", font=("Segoe UI", 9)).pack(
                         anchor="w", padx=14, pady=(0, 10))
            return

        # ── Variables ─────────────────────────────────────────────────────────
        self._mmx_entrada = tk.StringVar(value="")
        self._mmx_salida  = tk.StringVar(value="")
        self._mmx_prov    = tk.StringVar(value="gemini")
        self._mmx_modelo  = tk.StringVar(value=self._MMX_MODELOS["gemini"][0])
        self._mmx_guardar_json = tk.BooleanVar(value=True)
        self._mmx_alimentar    = tk.BooleanVar(value=True)
        self._mmx_corriendo    = False

        # ══ PASO 1 — Carpetas ═══════════════════════════════════════════════
        c1 = self._card(pad, "  1  Carpetas")

        def _fila_dir(parent, etiqueta, descripcion, var, comando):
            fila = tk.Frame(parent, bg=CARD_BG)
            fila.pack(fill="x", pady=(0, 8))
            tk.Label(fila, text=etiqueta, bg=CARD_BG, fg=TXT_PRI,
                     font=("Segoe UI", 9, "bold"), width=8, anchor="w").pack(side="left")
            tk.Label(fila, text=descripcion, bg=CARD_BG, fg=TXT_DIM,
                     font=("Segoe UI", 8)).pack(side="left", padx=(0, 8))
            tk.Button(fila, text="📁 Seleccionar", bg=AZ3, fg="#E8E5DF",
                      relief="flat", font=("Segoe UI", 8), padx=8, pady=3,
                      cursor="hand2", command=comando).pack(side="right")
            tk.Entry(fila, textvariable=var, bg=CARD_BG, fg=TXT_SEC, relief="solid",
                     bd=1, font=("Segoe UI", 8), state="readonly").pack(
                         side="right", fill="x", expand=True, padx=(0, 8))

        def _sel_entrada():
            d = filedialog.askdirectory(title="Carpeta con las imágenes de página")
            if d:
                self._mmx_entrada.set(d)
                if not self._mmx_salida.get():
                    self._mmx_salida.set(os.path.join(d, "extraccion_ia"))

        def _sel_salida():
            d = filedialog.askdirectory(title="Carpeta donde guardar JSON y .md")
            if d:
                self._mmx_salida.set(d)

        _fila_dir(c1, "Entrada", "carpeta con .jpg/.png/.tif de cada página",
                  self._mmx_entrada, _sel_entrada)
        _fila_dir(c1, "Salida", "dónde guardar los .json y .md",
                  self._mmx_salida, _sel_salida)

        # ══ PASO 2 — Proveedor de IA ════════════════════════════════════════
        c2 = self._card(pad, "  2  IA de visión")
        rowp = tk.Frame(c2, bg=CARD_BG)
        rowp.pack(fill="x", pady=2)
        tk.Label(rowp, text="Proveedor:", bg=CARD_BG, fg=TXT_PRI,
                 font=("Segoe UI", 9)).pack(side="left")
        cb_prov = ttk.Combobox(rowp, textvariable=self._mmx_prov, width=12,
                               state="readonly",
                               values=["gemini", "claude", "openai", "ollama", "lmstudio"])
        cb_prov.pack(side="left", padx=(6, 16))
        tk.Label(rowp, text="Modelo:", bg=CARD_BG, fg=TXT_PRI,
                 font=("Segoe UI", 9)).pack(side="left")
        # Combobox editable: muestra los modelos de visión vigentes del proveedor,
        # pero permite escribir uno propio.
        self._mmx_cb_modelo = ttk.Combobox(
            rowp, textvariable=self._mmx_modelo, width=22, state="normal",
            values=self._MMX_MODELOS.get(self._mmx_prov.get(), []))
        self._mmx_cb_modelo.pack(side="left", padx=(6, 0))

        def _prov_cambio(*_a):
            prov = self._mmx_prov.get()
            if prov == "lmstudio":
                from core.ocr_llm import modelos_cargados_lmstudio
                modelos = modelos_cargados_lmstudio()
            else:
                modelos = self._MMX_MODELOS.get(prov, [])
            self._mmx_cb_modelo.config(values=modelos)
            # Al cambiar de proveedor, selecciona su modelo recomendado (1.º).
            self._mmx_modelo.set(modelos[0] if modelos else "")
        self._mmx_prov.trace_add("write", _prov_cambio)

        self._mk_ayuda(rowp,
            "El selector lista los modelos de visión vigentes del proveedor\n"
            "elegido (el 1.º es el recomendado); podés escribir otro si querés.\n"
            "Gemini 2.5 Flash es ideal para lotes (rápido y económico).\n"
            "La clave se toma de ⚙ Configuración → Claves API por proveedor.\n"
            "Ollama corre localmente (modelo de visión, p.ej. llava) sin costo.\n"
            "LM Studio corre localmente (Developer → Start Server en LM Studio);\n"
            "  el selector consulta qué modelo tenés cargado ahora mismo.")

        # ══ PASO 3 — Qué hacer con el resultado ═════════════════════════════
        c3 = self._card(pad, "  3  Salida")
        ttk.Checkbutton(c3, text="💾  Guardar JSON crudo por página (auditable, trazable)",
                        variable=self._mmx_guardar_json).pack(anchor="w", pady=2)
        ttk.Checkbutton(c3, text="📥  Alimentar el corpus textual (para NER, análisis, grafo)",
                        variable=self._mmx_alimentar).pack(anchor="w", pady=2)

        # ══ PASO 4 — Ejecutar ═══════════════════════════════════════════════
        c4 = self._card(pad, "  4  Procesar")
        rowb = tk.Frame(c4, bg=CARD_BG)
        rowb.pack(fill="x", pady=(0, 8))
        tk.Button(rowb, text="🧮 Estimar costo", bg="#1C2227", fg="#B5B6B3",
                  relief="flat", font=("Segoe UI", 9), padx=12, pady=5,
                  cursor="hand2", command=self._mmx_estimar).pack(side="left")
        self._mmx_btn = tk.Button(rowb, text="🧠 Extraer todo", bg=AZ3, fg="#E8E5DF",
                                  relief="flat", font=("Segoe UI", 9, "bold"),
                                  padx=14, pady=5, cursor="hand2",
                                  command=self._mmx_iniciar)
        self._mmx_btn.pack(side="left", padx=(8, 0))
        tk.Button(rowb, text="📂 Abrir salida", bg="#1C2227", fg="#B5B6B3",
                  relief="flat", font=("Segoe UI", 9), padx=12, pady=5,
                  cursor="hand2", command=self._mmx_abrir_salida).pack(side="right")

        self._mmx_prog = ttk.Progressbar(c4, mode="determinate")
        self._mmx_prog.pack(fill="x", pady=(0, 6))
        self._mmx_log = tk.Text(c4, height=11, bg="#0E1114", fg="#777F84",
                                relief="solid", bd=1, font=("Consolas", 8),
                                wrap="word")
        self._mmx_log.pack(fill="both", expand=True)

    def _mmx_log_add(self, texto: str):
        self._mmx_log.insert("end", texto + "\n")
        self._mmx_log.see("end")

    def _mmx_clave(self):
        """Devuelve (api_key, proveedor, modelo) validando que haya clave."""
        prov = self._mmx_prov.get().strip().lower()
        modelo = self._mmx_modelo.get().strip() or None
        if prov == "ollama":
            return ST.api_keys.get("ollama", "http://localhost:11434"), prov, modelo
        if prov == "lmstudio":
            return ST.api_keys.get("lmstudio", "http://localhost:1234"), prov, modelo
        clave_map = {"gemini": "gemini", "claude": "anthropic", "openai": "openai"}
        api_key = ST.api_keys.get(clave_map.get(prov, prov), "") or ST.api_key
        return api_key, prov, modelo

    def _mmx_estimar(self):
        carpeta = self._mmx_entrada.get().strip()
        if not carpeta or not os.path.isdir(carpeta):
            messagebox.showwarning("Sin carpeta", "Elegí la carpeta de imágenes.")
            return
        try:
            from core import extractor_multimodal as em
            _, prov, modelo = self._mmx_clave()
            est = em.estimar_costo_directorio(carpeta, proveedor=prov, modelo=modelo)
            messagebox.showinfo("Estimación de costo", est.resumen())
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", str(e))

    def _mmx_iniciar(self):
        if self._mmx_corriendo:
            return
        carpeta = self._mmx_entrada.get().strip()
        salida = self._mmx_salida.get().strip()
        if not carpeta or not os.path.isdir(carpeta):
            messagebox.showwarning("Sin carpeta", "Elegí la carpeta de imágenes.")
            return
        if not salida:
            messagebox.showwarning("Sin salida", "Elegí la carpeta de salida.")
            return

        from core import extractor_multimodal as em
        try:
            imgs = em.listar_imagenes(carpeta)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", str(e))
            return
        if not imgs:
            messagebox.showinfo("Sin imágenes", "No hay imágenes en esa carpeta.")
            return

        api_key, prov, modelo = self._mmx_clave()
        if prov != "ollama" and not api_key:
            messagebox.showwarning(
                "Falta API key",
                f"No hay clave para «{prov}».\nConfigurala en ⚙ Configuración.")
            return

        # Estándar de costo IA: estimar y confirmar antes de gastar.
        try:
            est = em.estimar_costo_directorio(carpeta, proveedor=prov, modelo=modelo)
            costo_txt = est.resumen() + "\n\n"
        except Exception:  # noqa: BLE001
            costo_txt = f"{len(imgs)} imagen(es); proveedor {prov}.\n\n"
        if not messagebox.askyesno(
                "Extracción multimodal",
                f"{costo_txt}Se procesarán {len(imgs)} imagen(es) con IA de visión.\n"
                "¿Continuar?"):
            return

        self._mmx_corriendo = True
        self._mmx_btn.config(state="disabled")
        self._mmx_log.delete("1.0", "end")
        self._mmx_prog.config(value=0, maximum=len(imgs))
        threading.Thread(target=self._mmx_worker,
                         args=(carpeta, salida, api_key, prov, modelo),
                         daemon=True).start()

    def _mmx_worker(self, carpeta, salida, api_key, prov, modelo):
        from core import extractor_multimodal as em
        from core import ocr_llm
        self.after(0, lambda: self._mmx_log_add(
            f"Iniciando extracción con {prov} ({modelo or 'default'})…"))

        def cb(i, total, res):
            estado = "✓" if res.ok else "✗"
            detalle = (res.error if not res.ok else
                       f"{len(res.datos.get('imagenes_registro', []))} fotos, "
                       f"{len(res.datos.get('bloque_publicitario', []))} anuncios")
            self.after(0, lambda: (
                self._mmx_prog.config(value=i),
                self._mmx_log_add(f"  [{i}/{total}] {estado} {res.imagen} — {detalle}")))

        try:
            resultados = em.procesar_directorio(
                carpeta, api_key, salida, proveedor=prov, modelo=modelo,
                guardar_json=self._mmx_guardar_json.get(), guardar_md=True,
                callback=cb)
            resumen = em.resumen_lote(resultados)

            # Costo real desde el acumulador de usages (estándar costo-IA).
            costo_str = ""
            try:
                from core import costos
                cr = costos.costo_real_desde_usages(prov, modelo or "", ocr_llm.usages())
                if cr.costo_usd > 0:
                    costo_str = (f"\n💲 Costo real: ${cr.costo_usd:.4f} USD "
                                 f"({cr.tokens_input + cr.tokens_output:,} tokens)")
            except Exception:  # noqa: BLE001
                pass

            # Alimentar el corpus textual existente.
            alim = ""
            if self._mmx_alimentar.get():
                nuevos = [em.json_a_texto_plano(r.datos) for r in resultados
                          if r.ok and em.json_a_texto_plano(r.datos)]
                if nuevos:
                    if getattr(ST, "corpus_txt", None):
                        ST.corpus_txt.extend(nuevos)
                    else:
                        ST.corpus_txt = list(nuevos)
                    alim = f"\n📥 {len(nuevos)} textos añadidos al corpus."
                    self.after(0, self._marcar_modificado)

            msg = (f"Extracción completada\n"
                   f"  Páginas OK:   {resumen['ok']}\n"
                   f"  Fallidas:     {resumen['fallidas']}\n"
                   f"  Fotos:        {resumen['imagenes_detectadas']}\n"
                   f"  Anuncios:     {resumen['anuncios_detectados']}"
                   f"{costo_str}{alim}")
            self.after(0, lambda: self._mmx_log_add("\n" + msg))
            self.after(0, lambda: messagebox.showinfo("Extracción completada", msg))
        except Exception as e:  # noqa: BLE001
            err = str(e)
            self.after(0, lambda: self._mmx_log_add(f"ERROR: {err}"))
            self.after(0, lambda: messagebox.showerror("Error", err))
        finally:
            self._mmx_corriendo = False
            self.after(0, lambda: self._mmx_btn.config(state="normal"))

    def _mmx_abrir_salida(self):
        salida = self._mmx_salida.get().strip()
        if salida and os.path.isdir(salida):
            import subprocess
            subprocess.Popen(["explorer", os.path.normpath(salida)])

    # ══════════════════════════════════════════════════════════════════════════
    # ══════════════════════════════════════════════════════════════════════════
    # DESCRIPCIÓN E ICONOGRAFÍA DE IMÁGENES
    # ══════════════════════════════════════════════════════════════════════════
    def _build_imgdesc(self):
        f = self._frames_pagina["imgdesc"]
        self._page_header(f, "Descripción e iconografía de imágenes",
                          "Describe, categoriza y busca imágenes etiquetadas · "
                          "Claude · GPT-4o · Gemini · Ollama", "🎨")

        from core.image_captioner import CATEGORIAS_TEMATICAS
        from core.zone_labeler import VISION_PROVEEDORES

        # ── Barra de control ─────────────────────────────────────────────────
        ctrl = tk.Frame(f, bg=CONTENT_BG)
        ctrl.pack(fill="x", padx=24, pady=(0, 6))

        # Selector de número
        tk.Label(ctrl, text="Número:", bg=CONTENT_BG, fg=TXT_SEC,
                 font=("Segoe UI", 9)).pack(side="left")
        self._imgd_var_num = tk.StringVar()
        self._imgd_cb_num  = ttk.Combobox(ctrl, textvariable=self._imgd_var_num,
                                           width=28, state="readonly")
        self._imgd_cb_num.pack(side="left", padx=(4, 12))
        self._imgd_cb_num.bind("<<ComboboxSelected>>",
                                lambda e: self._imgd_cargar_db())

        # Proveedor + modelo
        tk.Label(ctrl, text="IA:", bg=CONTENT_BG, fg=TXT_SEC,
                 font=("Segoe UI", 9)).pack(side="left")
        self._imgd_var_prov  = tk.StringVar(value="claude")
        self._imgd_var_model = tk.StringVar(value="claude-haiku-4-5-20251001")
        cb_prov = ttk.Combobox(ctrl, textvariable=self._imgd_var_prov,
                                values=list(VISION_PROVEEDORES.keys()),
                                state="readonly", width=9)
        cb_prov.pack(side="left", padx=(4, 4))
        self._imgd_cb_model = ttk.Combobox(ctrl, textvariable=self._imgd_var_model,
                                            state="readonly", width=24)
        self._imgd_cb_model.pack(side="left", padx=(0, 8))

        def _on_prov(*_):
            info = VISION_PROVEEDORES.get(self._imgd_var_prov.get(), {})
            mods = info.get("modelos", [])
            self._imgd_cb_model["values"] = mods
            self._imgd_var_model.set(info.get("default", mods[0] if mods else ""))
        cb_prov.bind("<<ComboboxSelected>>", _on_prov)
        _on_prov()

        # Botones principales
        self._imgd_btn_run = ttk.Button(ctrl, text="▶  Describir fotos",
                                         style="P.TButton",
                                         command=self._imgd_describir)
        self._imgd_btn_run.pack(side="left", padx=(0, 6))
        ttk.Button(ctrl, text="↺ Cargar guardadas", style="S.TButton",
                   command=self._imgd_cargar_db).pack(side="left", padx=(0, 6))
        ttk.Button(ctrl, text="📥 Exportar CSV", style="S.TButton",
                   command=self._imgd_exportar).pack(side="left", padx=(0, 6))
        ttk.Button(ctrl, text="↺ Actualizar números", style="S.TButton",
                   command=self._imgd_refrescar_numeros).pack(side="right")

        self._imgd_lbl_estado = tk.Label(ctrl, text="", bg=CONTENT_BG,
                                          fg=VERDE, font=("Segoe UI", 9, "bold"))
        self._imgd_lbl_estado.pack(side="right", padx=8)

        # ── Filtros por categoría ─────────────────────────────────────────────
        filt_f = tk.Frame(f, bg=CARD_BG, relief="solid", bd=1)
        filt_f.pack(fill="x", padx=24, pady=(0, 6))
        fi = tk.Frame(filt_f, bg=CARD_BG, padx=10, pady=6)
        fi.pack(fill="x")
        tk.Label(fi, text="Filtrar por categoría:", bg=CARD_BG, fg=TXT_PRI,
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        self._imgd_var_cat = tk.StringVar(value="todas")
        cats = ["todas"] + sorted(CATEGORIAS_TEMATICAS)
        ttk.Combobox(fi, textvariable=self._imgd_var_cat,
                     values=cats, state="readonly", width=22).pack(
                         side="left", padx=(6, 12))
        self._imgd_var_cat.trace_add("write", lambda *_: self._imgd_filtrar())

        tk.Label(fi, text="Buscar similitud:", bg=CARD_BG, fg=TXT_SEC,
                 font=("Segoe UI", 8)).pack(side="left")
        self._imgd_var_busq = tk.StringVar()
        ttk.Entry(fi, textvariable=self._imgd_var_busq, width=28).pack(
            side="left", padx=(4, 6))
        ttk.Button(fi, text="Buscar", style="S.TButton",
                   command=self._imgd_buscar_similitud).pack(side="left")

        # ── Split: tabla + detalle ────────────────────────────────────────────
        split = tk.Frame(f, bg=CONTENT_BG)
        split.pack(fill="both", expand=True, padx=24, pady=(0, 12))

        # Tabla izquierda
        izq = tk.Frame(split, bg=CONTENT_BG)
        izq.pack(side="left", fill="both", expand=True, padx=(0, 8))

        cols = ("pagina", "descripcion", "categorias", "texto_visible", "contexto")
        self._imgd_tv = ttk.Treeview(izq, columns=cols, show="headings", height=22)
        for cid, lbl, w in [
            ("pagina",       "Página",        70),
            ("descripcion",  "Descripción",   260),
            ("categorias",   "Categorías",    140),
            ("texto_visible","Texto visible",  110),
            ("contexto",     "Contexto hist.", 160),
        ]:
            self._imgd_tv.heading(cid, text=lbl,
                command=lambda c=cid: self._imgd_ordenar(c))
            self._imgd_tv.column(cid, width=w, anchor="w")
        sv = ttk.Scrollbar(izq, orient="vertical",   command=self._imgd_tv.yview)
        sh = ttk.Scrollbar(izq, orient="horizontal",  command=self._imgd_tv.xview)
        self._imgd_tv.configure(yscrollcommand=sv.set, xscrollcommand=sh.set)
        sv.pack(side="right", fill="y")
        sh.pack(side="bottom", fill="x")
        self._imgd_tv.pack(fill="both", expand=True)
        self._imgd_tv.bind("<<TreeviewSelect>>", self._imgd_on_sel)

        # Panel derecho: recorte + metadatos
        der = tk.Frame(split, bg=CARD_BG, width=320, relief="solid", bd=1)
        der.pack(side="right", fill="y")
        der.pack_propagate(False)

        self._imgd_canvas = tk.Canvas(der, bg="#000", height=210, highlightthickness=0)
        self._imgd_canvas.pack(fill="x", padx=6, pady=6)

        self._imgd_lbl_desc = tk.Label(der, text="", bg=CARD_BG, fg=TXT_PRI,
                                        font=("Segoe UI", 9, "bold"),
                                        wraplength=300, justify="left")
        self._imgd_lbl_desc.pack(anchor="w", padx=8, pady=(4, 2))

        self._imgd_lbl_cats = tk.Label(der, text="", bg=CARD_BG, fg=AZ4,
                                        font=("Segoe UI", 8),
                                        wraplength=300, justify="left")
        self._imgd_lbl_cats.pack(anchor="w", padx=8)

        self._imgd_lbl_txt = tk.Label(der, text="", bg=CARD_BG, fg=TXT_SEC,
                                       font=("Courier New", 8),
                                       wraplength=300, justify="left")
        self._imgd_lbl_txt.pack(anchor="w", padx=8, pady=(2, 0))

        self._imgd_lbl_ctx = tk.Label(der, text="", bg=CARD_BG, fg=TXT_DIM,
                                       font=("Segoe UI", 8, "italic"),
                                       wraplength=300, justify="left")
        self._imgd_lbl_ctx.pack(anchor="w", padx=8, pady=(2, 8))

        # Búsqueda por similitud — resultados
        tk.Frame(der, bg=CARD_BOR, height=1).pack(fill="x", padx=6, pady=4)
        tk.Label(der, text="Imágenes similares:", bg=CARD_BG, fg=TXT_PRI,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=8)
        self._imgd_lbl_sim = tk.Label(der, text="", bg=CARD_BG, fg=TXT_SEC,
                                       font=("Segoe UI", 8),
                                       wraplength=300, justify="left")
        self._imgd_lbl_sim.pack(anchor="w", padx=8, pady=(2, 8))

        # Estado interno
        self._imgd_datos: list[dict] = []
        self._imgd_sort_col = ""
        self._imgd_sort_rev = False

        # Cargar al entrar al panel
        self.after(300, self._imgd_refrescar_numeros)

    def _imgd_refrescar_numeros(self):
        if not ST.out_dir:
            return
        etiq_dir = Path(ST.out_dir) / "05_etiquetas"
        if not etiq_dir.exists():
            return
        nums = sorted(p.name for p in etiq_dir.iterdir() if p.is_dir())
        self._imgd_cb_num["values"] = nums
        if nums and not self._imgd_var_num.get():
            self._imgd_var_num.set(nums[0])
            self._imgd_cargar_db()

    def _imgd_cargar_db(self):
        num = self._imgd_var_num.get()
        if not num or not ST.ruta_db:
            return
        from core.image_captioner import cargar_descripciones_db
        db = Path(ST.ruta_db)
        if not db.exists():
            self._imgd_lbl_estado.config(
                text="Sin descripciones guardadas aún — usa ▶ Describir fotos", fg=TXT_SEC)
            return
        datos = cargar_descripciones_db(db, num)
        self._imgd_datos = datos
        self._imgd_poblar_tv(datos)
        self._imgd_lbl_estado.config(
            text=f"{len(datos)} imágenes descritas — {num}", fg=VERDE)

    def _imgd_poblar_tv(self, datos: list[dict]):
        self._imgd_tv.delete(*self._imgd_tv.get_children())
        for d in datos:
            cats = ", ".join(d.get("categorias", []))[:45]
            self._imgd_tv.insert("", "end", values=(
                d.get("pagina", ""),
                d.get("descripcion", "")[:70],
                cats,
                d.get("texto_visible", "")[:35],
                d.get("contexto_historico", "")[:50],
            ))

    def _imgd_filtrar(self, *_):
        cat = self._imgd_var_cat.get()
        if cat == "todas":
            self._imgd_poblar_tv(self._imgd_datos)
        else:
            filtrados = [d for d in self._imgd_datos
                         if cat in d.get("categorias", [])]
            self._imgd_poblar_tv(filtrados)
        self._imgd_lbl_estado.config(
            text=f"Filtrando: {cat}", fg=TXT_SEC)

    def _imgd_ordenar(self, col: str):
        if self._imgd_sort_col == col:
            self._imgd_sort_rev = not self._imgd_sort_rev
        else:
            self._imgd_sort_col = col
            self._imgd_sort_rev = False
        datos_ord = sorted(self._imgd_datos,
                           key=lambda d: str(d.get(col, "")),
                           reverse=self._imgd_sort_rev)
        self._imgd_poblar_tv(datos_ord)

    def _imgd_on_sel(self, event=None):
        sel = self._imgd_tv.selection()
        if not sel:
            return
        idx = self._imgd_tv.index(sel[0])
        datos_visibles = [
            self._imgd_tv.item(iid)["values"]
            for iid in self._imgd_tv.get_children()
        ]
        # Encontrar el dict completo que corresponde a esta fila
        pag_sel = datos_visibles[idx][0] if datos_visibles else ""
        d = next((x for x in self._imgd_datos
                  if x.get("pagina") == pag_sel), None)
        if d is None:
            return
        self._imgd_lbl_desc.config(text=d.get("descripcion", ""))
        cats = d.get("categorias", [])
        self._imgd_lbl_cats.config(
            text=("📌 " + " · ".join(cats)) if cats else "")
        tv = d.get("texto_visible", "")
        self._imgd_lbl_txt.config(
            text=("📝 " + tv) if tv else "")
        self._imgd_lbl_ctx.config(
            text=d.get("contexto_historico", ""))
        self._imgd_mostrar_recorte(d)

    def _imgd_mostrar_recorte(self, d: dict):
        self._imgd_canvas.delete("all")
        try:
            from PIL import Image, ImageTk
            num     = self._imgd_var_num.get()
            pagina  = d.get("pagina", "")
            img_dir = Path(ST.out_dir) / "02_imagenes" / num
            hits    = sorted(img_dir.glob(f"*{pagina}*.png")) if img_dir.exists() else []
            if not hits:
                return
            img = Image.open(hits[0]).convert("RGB")
            W, H = img.size
            x0 = int(d.get("x0", 0) * W)
            y0 = int(d.get("y0", 0) * H)
            x1 = int(d.get("x1", 1) * W)
            y1 = int(d.get("y1", 1) * H)
            recorte = img.crop((x0, y0, x1, y1))
            recorte.thumbnail((306, 200), Image.LANCZOS)
            tk_img = ImageTk.PhotoImage(recorte)
            self._imgd_canvas._ref = tk_img
            cw = self._imgd_canvas.winfo_width() or 306
            self._imgd_canvas.create_image(cw // 2, 105, anchor="center", image=tk_img)
        except Exception:
            pass

    def _imgd_describir(self):
        num = self._imgd_var_num.get()
        if not num or not ST.out_dir:
            messagebox.showwarning("Sin número",
                "Selecciona un número con imágenes etiquetadas.")
            return
        prov  = self._imgd_var_prov.get()
        model = self._imgd_var_model.get()
        api_k = ST.api_keys.get(prov, "") or ST.api_key
        if prov != "ollama" and not api_k:
            messagebox.showwarning("Sin API key",
                f"Configura la API key de {prov} en ⚙ Configuración.")
            return

        self._imgd_btn_run.config(state="disabled")
        self._imgd_lbl_estado.config(text="⏳ Describiendo…", fg="#E6A64C")

        from core.image_captioner import describir_numero

        def cb(n, t, pag, desc):
            self.after(0, lambda: self._imgd_lbl_estado.config(
                text=f"⏳ {n}/{t}: {pag} — {desc[:45]}…", fg="#E6A64C"))

        def _run():
            db = Path(ST.ruta_db) if ST.ruta_db else None
            datos = describir_numero(ST.out_dir, num, proveedor=prov,
                                     api_key=api_k, modelo=model,
                                     db_path=db, callback=cb)
            self.after(0, lambda: (
                self._imgd_datos.__setitem__(slice(None), datos),
                self._imgd_poblar_tv(datos),
                self._imgd_btn_run.config(state="normal"),
                self._imgd_lbl_estado.config(
                    text=f"✅ {len(datos)} imágenes descritas", fg=VERDE),
            ))
        threading.Thread(target=_run, daemon=True).start()

    def _imgd_buscar_similitud(self):
        q = self._imgd_var_busq.get().strip()
        if not q:
            return
        num = self._imgd_var_num.get()
        if not num or not ST.out_dir:
            return
        from core.image_captioner import buscar_imagenes_similares
        sims = buscar_imagenes_similares(q, ST.out_dir, num, top_n=5)
        if sims:
            txt = "\n".join(
                f"  p.{s['pagina']} — {s['descripcion'][:55]}"
                for s in sims)
            self._imgd_lbl_sim.config(text=txt)
        else:
            self._imgd_lbl_sim.config(
                text="Sin índice FAISS. Describe las imágenes primero.")

    def _imgd_exportar(self):
        if not self._imgd_datos:
            messagebox.showwarning("Sin datos", "Describe las imágenes primero.")
            return
        ruta = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("JSON", "*.json")],
            initialfile=f"imagenes_{self._imgd_var_num.get()}.csv")
        if not ruta:
            return
        import pandas as _pd
        df = _pd.DataFrame(self._imgd_datos)
        if ruta.endswith(".json"):
            import json as _json
            Path(ruta).write_text(
                _json.dumps(self._imgd_datos, ensure_ascii=False, indent=2),
                encoding="utf-8")
        else:
            df.to_csv(ruta, index=False, encoding="utf-8-sig")
        self.toast(f"Exportado → {Path(str(ruta)).name}", tipo="ok")

    # ── Kraken handlers ───────────────────────────────────────────────────────
    def _ocr_verificar_kraken(self):
        """Verifica si Kraken + modelo están disponibles y actualiza el label."""
        try:
            from core.ocr_kraken import _buscar_modelo, kraken_disponible
            if kraken_disponible():
                modelo = _buscar_modelo()
                nombre = Path(modelo).name if modelo else "modelo"
                self._lbl_kraken_ok.config(text=f"✅ {nombre}", fg=VERDE)
                if modelo:
                    self._var_kraken_modelo.set(str(modelo))
            else:
                # Verificar via subprocess (Kraken está en venv separado, no en Python principal)
                import subprocess

                from core.ocr_kraken import _python_kraken
                chk = subprocess.run([_python_kraken(), "-c", "import kraken"],
                                     capture_output=True, timeout=10)
                if chk.returncode == 0:
                    self._lbl_kraken_ok.config(text="⚠ Sin modelo — descarga CATMuS-Print", fg="#E6A64C")
                else:
                    self._lbl_kraken_ok.config(text="✗ Kraken no instalado en venv", fg=ROJO)
        except Exception as e:
            self._lbl_kraken_ok.config(text=f"✗ {e}", fg=ROJO)

    def _ocr_elegir_modelo_kraken(self):
        """Abre diálogo para seleccionar un archivo .mlmodel de Kraken."""
        from tkinter import filedialog
        ruta = filedialog.askopenfilename(
            title="Seleccionar modelo Kraken (.mlmodel)",
            filetypes=[("Kraken model", "*.mlmodel"), ("Todos", "*.*")],
        )
        if ruta:
            self._var_kraken_modelo.set(ruta)
            self._lbl_kraken_ok.config(text=f"✅ {Path(ruta).name}", fg=VERDE)

    def _ocr_descargar_catmus(self):
        """Descarga el modelo CATMuS-Print Large en un thread."""
        self._lbl_kraken_ok.config(text="⏳ Descargando (~300 MB)…", fg="#777F84")

        def _worker():
            try:
                from core.ocr_kraken import descargar_modelo_catmus
                def cb(msg):
                    self.after(0, lambda m=msg: self._lbl_kraken_ok.config(text=m, fg="#777F84"))
                ruta = descargar_modelo_catmus(callback=cb)
                self.after(0, lambda r=ruta: (
                    self._var_kraken_modelo.set(r),
                    self._lbl_kraken_ok.config(text=f"✅ {Path(r).name}", fg=VERDE),
                ))
            except Exception as e:
                msg = str(e)
                if "No module named kraken" in msg:
                    msg = ("✗ Kraken no instalado — incompatible con torch 2.x.\n"
                           "Para instalar: pip install kraken (requiere torch<1.11)")
                elif "Error descargando" in msg:
                    msg = "✗ " + msg.split("\n")[0]
                else:
                    msg = f"✗ {msg[:120]}"
                self.after(0, lambda m=msg: self._lbl_kraken_ok.config(
                    text=m, fg=ROJO, wraplength=320))

        threading.Thread(target=_worker, daemon=True).start()

    def _ocr_contar_paginas_corpus(self) -> int:
        """Cuenta páginas pendientes de OCR en el corpus activo."""
        from core.servicios_corpus import contar_paginas_pendientes
        return contar_paginas_pendientes(ST.out_dir, ST.archivos_sel)

    def _ocr_actualizar_estimacion(self, *_):
        """Recalcula y muestra la estimación de tiempo según workers y corpus."""
        if not hasattr(self, "_lbl_kraken_est"):
            return
        try:
            workers = max(1, int(self._var_kraken_workers.get()))
        except (ValueError, tk.TclError):
            return
        paginas = self._ocr_contar_paginas_corpus()
        if paginas == 0:
            self._lbl_kraken_est.config(
                text="— (carga un proyecto para estimar)", fg="#777F84")
            return
        seg_total = (paginas * self._KRAKEN_SEG_PAG) / workers
        horas  = int(seg_total // 3600)
        minutos = int((seg_total % 3600) // 60)
        if horas > 0:
            tiempo_txt = f"~{horas}h {minutos:02d}min"
        else:
            tiempo_txt = f"~{minutos} min"
        color = "#6EC69A" if seg_total < 3600 else ("#E6A64C" if seg_total < 7200 else "#D96B6B")
        self._lbl_kraken_est.config(
            text=f"{tiempo_txt}  ({paginas} páginas, {workers} proceso{'s' if workers>1 else ''})",
            fg=color)

    def _ocr_calibrar_kraken(self):
        """Mide el tiempo real de Kraken en una página del corpus y actualiza la estimación."""
        if not ST.out_dir or not ST.archivos_sel:
            messagebox.showwarning("Sin proyecto", "Carga un proyecto primero.")
            return
        # Buscar la primera imagen disponible
        img_path = None
        for pdf in ST.archivos_sel:
            img_dir = ST.out_dir / "02_imagenes" / pdf.stem
            if img_dir.exists():
                imgs = sorted(img_dir.glob("*.png"))
                if imgs:
                    img_path = imgs[0]
                    break
        if not img_path:
            messagebox.showwarning(
                "Sin imágenes",
                "No hay imágenes generadas.\nProcesa primero al menos 1 página con Ruta 1.")
            return

        self._lbl_kraken_est.config(text="⏳ Calibrando (1 página)…", fg="#E6A64C")
        self.update_idletasks()

        def _worker():
            import time

            from core.ocr_kraken import ocr_kraken
            modelo = getattr(self, "_var_kraken_modelo", tk.StringVar()).get() or None
            t0 = time.perf_counter()
            try:
                ocr_kraken(str(img_path), modelo)
                seg = time.perf_counter() - t0
                # Actualizar referencia y recalcular
                BashkarApp._KRAKEN_SEG_PAG = round(seg, 1)
                self.after(0, lambda: self._lbl_kraken_est.config(
                    text=f"✅ Calibrado: {seg:.0f} seg/página — recalculando…",
                    fg="#6EC69A"))
                self.after(200, self._ocr_actualizar_estimacion)
            except Exception as e:
                self.after(0, lambda err=str(e): self._lbl_kraken_est.config(
                    text=f"✗ Error calibrando: {err}", fg="#D96B6B"))

        threading.Thread(target=_worker, daemon=True).start()

    def _ocr_detectar_ollama(self):
        """Detecta modelos de visión disponibles en Ollama y puebla el combobox."""
        def _worker():
            try:
                from core.ocr_ollama_local import listar_modelos_vision
                url_ollama = ST.api_keys.get("ollama", "http://localhost:11434") or "http://localhost:11434"
                modelos = listar_modelos_vision(url_ollama)
                def _update(ms=modelos):
                    if ms:
                        self._cmb_ollama["values"] = ms
                        if not self._var_ollama_modelo.get() or \
                                self._var_ollama_modelo.get() not in ms:
                            self._var_ollama_modelo.set(ms[0])
                        self._lbl_ollama_ok.config(
                            text=f"✅ {len(ms)} modelo(s)", fg=VERDE)
                    else:
                        self._lbl_ollama_ok.config(
                            text="⚠ Ollama sin modelos de visión", fg="#E6A64C")
                self.after(0, _update)
            except Exception as e:
                self.after(0, lambda err=e: self._lbl_ollama_ok.config(
                    text=f"✗ {err}", fg=ROJO))

        threading.Thread(target=_worker, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────────────
    def _ocr_aplicar_zonas(self, texto: str, numero: str, pagina: str,
                            det_auto: bool = False, api_key: str = "") -> str:
        """
        Filtra el texto de una página usando las zonas etiquetadas.

        - Toma solo las zonas con ocr=True, en orden de arriba a abajo (y0).
        - Si la página no tiene etiquetas y det_auto=True, detecta automáticamente.
        - El texto de cada zona se extrae por posición relativa en las líneas del OCR.
        - Retorna el texto ordenado según el flujo de lectura de las zonas.
        """
        from core.zone_labeler import TIPOS_ZONA, cargar_pagina

        if not ST.out_dir:
            return texto

        pag_data = cargar_pagina(ST.out_dir, numero, pagina)
        zonas_ocr = []

        if pag_data and pag_data.zonas:
            # Filtrar solo zonas que deben procesarse con OCR, ordenadas por y0
            zonas_ocr = sorted(
                [z for z in pag_data.zonas if TIPOS_ZONA.get(z.tipo, {}).get("ocr", True)],
                key=lambda z: (z.y0, z.x0)
            )
        elif det_auto and api_key:
            # Detección automática en páginas sin etiquetar
            try:
                img_path = self._etz_get_img_path(numero, pagina)
                if img_path:
                    from core.zone_labeler import detectar_zonas_claude
                    zonas_detectadas = detectar_zonas_claude(img_path, api_key)
                    zonas_ocr = sorted(
                        [z for z in zonas_detectadas if TIPOS_ZONA.get(z.tipo, {}).get("ocr", True)],
                        key=lambda z: (z.y0, z.x0)
                    )
                    self._put(tipo="log",
                              texto=f"    🤖 {len(zonas_ocr)} zonas detectadas automáticamente")
            except Exception:
                pass

        if not zonas_ocr:
            return texto  # sin zonas → devolver texto completo

        # Dividir el texto en líneas y asignar cada línea a la zona más cercana
        lineas = texto.splitlines()
        total_lineas = len(lineas) or 1
        bloques = {i: [] for i in range(len(zonas_ocr))}

        for i_linea, linea in enumerate(lineas):
            pos_rel = i_linea / total_lineas  # posición 0.0-1.0 en la página
            # Buscar la zona que más se superpone con esta posición vertical
            mejor_zona = None
            mejor_dist = float("inf")
            for i_zona, zona in enumerate(zonas_ocr):
                if zona.y0 <= pos_rel <= zona.y1:
                    # Dentro de la zona — asignar directamente
                    mejor_zona = i_zona
                    break
                dist = min(abs(pos_rel - zona.y0), abs(pos_rel - zona.y1))
                if dist < mejor_dist:
                    mejor_dist = dist
                    mejor_zona = i_zona
            if mejor_zona is not None:
                bloques[mejor_zona].append(linea)

        # Reconstruir texto en orden de lectura de las zonas
        partes = []
        for i_zona in range(len(zonas_ocr)):
            bloque = "\n".join(bloques[i_zona]).strip()
            if bloque:
                partes.append(bloque)

        return "\n\n".join(partes) if partes else texto

    def _ocr_preview_preprocesamiento(self):
        """Abre ventana con antes/después del preprocesamiento sobre la primera imagen disponible."""
        if not ST.out_dir or not ST.archivos_sel:
            messagebox.showwarning("Sin archivos", "Configura el corpus primero.")
            return
        # Buscar primera imagen disponible
        img_path = None
        for archivo in ST.archivos_sel:
            img_dir = ST.out_dir / "02_imagenes" / archivo.stem
            if img_dir.exists():
                hits = sorted(img_dir.glob("*.png"))
                if hits:
                    img_path = hits[0]
                    break
        if img_path is None:
            messagebox.showwarning("Sin imágenes",
                "Ejecuta primero la extracción OCR para generar las imágenes.")
            return

        from PIL import Image, ImageTk

        from core.image_preprocessor import preprocesar_para_ocr

        win = tk.Toplevel(self)
        win.title(f"Preview preprocesamiento — {img_path.name}")
        win.geometry("900x500")
        win.configure(bg=CONTENT_BG)
        win.grab_set()

        tk.Label(win, text="Original", bg=CONTENT_BG, fg=TXT_PRI,
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=0, pady=(8, 2))
        tk.Label(win, text="Procesada", bg=CONTENT_BG, fg=TXT_PRI,
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=1, pady=(8, 2))

        cv_orig = tk.Canvas(win, bg="#000", width=420, height=420, highlightthickness=0)
        cv_orig.grid(row=1, column=0, padx=8, pady=4)
        cv_proc = tk.Canvas(win, bg="#000", width=420, height=420, highlightthickness=0)
        cv_proc.grid(row=1, column=1, padx=8, pady=4)

        def _mostrar():
            img_o = Image.open(img_path).convert("RGB")
            img_p = preprocesar_para_ocr(
                img_o.copy(),
                deskew_en    = self._var_pre_deskew.get(),
                enhance_en   = self._var_pre_enhance.get(),
                despeckle_en = self._var_pre_despeckle.get(),
            )
            for cv, im in [(cv_orig, img_o), (cv_proc, img_p)]:
                im.thumbnail((420, 420), Image.LANCZOS)
                tk_img = ImageTk.PhotoImage(im)
                cv._ref = tk_img
                cv.delete("all")
                cv.create_image(210, 210, anchor="center", image=tk_img)

        _mostrar()

        # Checkboxes dentro del preview para ajustar en tiempo real
        ctrl = tk.Frame(win, bg=CONTENT_BG)
        ctrl.grid(row=2, column=0, columnspan=2, pady=6)
        for txt, var in [("Deskew", self._var_pre_deskew),
                          ("CLAHE",  self._var_pre_enhance),
                          ("Despeckle", self._var_pre_despeckle)]:
            ttk.Checkbutton(ctrl, text=txt, variable=var,
                             command=_mostrar).pack(side="left", padx=10)
        ttk.Button(ctrl, text="↺ Actualizar", command=_mostrar).pack(side="left", padx=10)
        ttk.Button(ctrl, text="Cerrar", command=win.destroy).pack(side="left", padx=10)

    def _start_ocr(self):
        if ST.pdf_dir is None:
            messagebox.showwarning("Sin config","Confirma la configuración primero."); return
        self._btn_ocr.config(state="disabled")
        threading.Thread(target=self._worker_ocr, args=(self._snapshot_ocr(),),
                         daemon=True).start()

    def _ocr_paginas_faltantes(self, archivo, nombre, txt_dir, dir_img,
                               paginas, dpi):
        """Tesseract sobre las páginas de un PDF que NO traen texto embebido.

        Un documento puede declarar la capa oculta de Paper Capture y tenerla
        solo en algunas páginas (El Día: 2 de 16). Antes esas páginas se
        escribían vacías y el número se daba por completo. Aquí se rasterizan
        y se reconocen SOLO ellas, y la fila queda marcada `revision=True`
        para que se vea de dónde salió el texto.

        `paginas` son números 1-based. Devuelve las filas de metadatos.
        """
        from core.ocr_engine import ocr_pagina
        from core.ocr_normalizer import normalizar_texto_ocr

        filas = []
        img_dir_n = dir_img / nombre
        img_dir_n.mkdir(parents=True, exist_ok=True)
        try:
            import fitz
            doc = fitz.open(str(archivo))
        except Exception as e:
            self._put(tipo="log", texto=f"  ❌ No se pudo rasterizar: {e}")
            return filas

        try:
            mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
            for n in paginas:
                pagina_id = f"p{n:04d}"
                tp = txt_dir / f"{pagina_id}.txt"
                img_path = img_dir_n / f"{pagina_id}.png"
                try:
                    if not img_path.exists():
                        doc[n - 1].get_pixmap(matrix=mat).save(str(img_path))
                    texto, conf = ocr_pagina(img_path)
                    texto = normalizar_texto_ocr(texto)
                except Exception as e:
                    # Sin texto y sin OCR: NO se escribe un .txt vacío que haga
                    # pasar la página por procesada. Se avisa y se omite.
                    self._put(tipo="log",
                              texto=f"  ⚠ {pagina_id} sin texto y sin OCR: {e}")
                    continue
                tp.write_text(texto, encoding="utf-8")
                filas.append({
                    "numero":   nombre,
                    "pagina":   pagina_id,
                    "txt_path": str(tp),
                    "palabras": len(texto.split()),
                    "confianza": conf,
                    "revision": True,
                    "metodo":   "tesseract_relleno",
                })
        finally:
            try:
                doc.close()
            except Exception:
                pass
        return filas

    def _worker_ocr(self, snap: dict | None = None):
        snap = snap if snap is not None else self._snapshot_ocr()
        from core.ocr_engine import (
            EXTS_IMAGEN,
            analizar_pdf,
            imagenes_a_texto,
            ocr_pagina,
            pdf_a_imagenes,
        )

        # Modo subcarpetas: cada "archivo" en archivos_sel es una carpeta con PDFs
        # Expandimos la lista: cada PDF de la subcarpeta se procesa como una página
        if ST.input_tipo == "carpetas":
            archivos_orig = ST.archivos_sel
            archivos_expandidos = []
            for sc in archivos_orig:
                pdfs = sorted(Path(sc).glob("*.pdf"))
                archivos_expandidos.append({
                    "nombre": Path(sc).name,   # nombre del número
                    "pdfs":   pdfs,             # lista de PDFs de la carpeta
                    "carpeta": Path(sc),
                })
            self._put(tipo="log",
                texto=f"📁 Modo subcarpetas: {len(archivos_expandidos)} número(s) detectado(s)")
            self._worker_ocr_carpetas(archivos_expandidos, snap)
            return

        archivos   = ST.archivos_sel; total = len(archivos)
        dpi  = snap["_var_dpi"].get()  if "_var_dpi"  in snap else 300
        lang = snap["_var_lang"].get() if "_var_lang" in snap else "spa"
        ruta_ocr   = snap.get("_var_ruta_ocr")
        ruta_ocr      = ruta_ocr.get() if ruta_ocr else "tesseract"
        usar_etiq     = snap.get("_var_ocr_usar_etiquetas")
        usar_etiq     = usar_etiq.get() if usar_etiq else False
        det_auto      = snap.get("_var_ocr_det_auto")
        det_auto      = det_auto.get() if det_auto else False
        out           = ST.out_dir
        dir_img       = out/"02_imagenes"; dir_ocr = out/"03_ocr"
        dir_img.mkdir(exist_ok=True); dir_ocr.mkdir(exist_ok=True)
        meta_rows, errores = [], []

        # Leer proveedor/modelo de visión si se seleccionó Ruta 2
        # Ojo: aquí antes se construía un tk.StringVar de respaldo, lo que era
        # una llamada a Tcl desde el hilo. El valor viene ya congelado del snapshot.
        _vp = snap.get("_ocr_vision_prov")
        _ocr_vision_prov  = (_vp.get() if _vp else "") or "claude"
        _vm = snap.get("_ocr_vision_model")
        _ocr_vision_model = (_vm.get() if _vm else "") or "claude-sonnet-4-6"

        RUTA_LABELS = {
            "tesseract": "Ruta 1 · Tesseract propio",
            "vision_ia": f"Ruta 2 · {_ocr_vision_prov}/{_ocr_vision_model}",
            "claude":    "Ruta 2 · Claude Vision (legado)",
            "bnc":       "Ruta 3 · Texto BNC + reconstrucción",
            "kraken":    "Ruta 4 · Kraken CATMuS-Print",
            "ollama":    "Ruta 5 · Ollama Vision",
        }
        etiq_label = " · con zonas etiquetadas" if usar_etiq else ""
        self._put(tipo="log", texto=f"📄 {total} archivo(s) · {RUTA_LABELS.get(ruta_ocr, ruta_ocr)}{etiq_label}")
        self._put(tipo="fase", txt="Detectando tipos…")

        # En Ruta 1 (tesseract), Ruta 2 (vision_ia) forzamos re-OCR.
        # En Ruta 3 (bnc) usamos el texto embebido con reconstrucción de líneas.
        modos = {}
        censos = {}
        for p in archivos:
            if ST.input_tipo == "img" or p.suffix.lower() in EXTS_IMAGEN:
                modos[p.name] = "imagen"
            elif ruta_ocr in ("tesseract", "vision_ia", "claude", "kraken", "ollama"):
                # Forzar re-OCR desde imágenes, ignorar texto BNC
                modos[p.name] = "escaneado"
            else:
                # Ruta 3: usar texto embebido si existe. El censo es por página
                # (ver core/calidad_ocr.py): un ejemplar puede traer texto en
                # unas páginas y no en otras, y antes eso se perdía entero.
                info = analizar_pdf(p)
                censos[p.name] = info.get("modos_pagina") or []
                modos[p.name] = "digital" if info["tiene_texto"] else "escaneado"
                if info.get("mixto"):
                    self._put(tipo="log",
                        texto=f"   ⚠ {p.name}: {info['resumen']}")

        n_dig = sum(1 for m in modos.values() if m=="digital")
        n_ocr = sum(1 for m in modos.values() if m=="escaneado")
        n_img = sum(1 for m in modos.values() if m=="imagen")
        parts = []
        if n_dig: parts.append(f"⚡ {n_dig} digital(es)")
        if n_ocr: parts.append(f"🔍 {n_ocr} escaneado(s)")
        if n_img: parts.append(f"🖼️ {n_img} imagen(es)")
        self._put(tipo="log", texto="   "+"|".join(parts))
        ST.modos_detec = modos
        ST.censos_pagina = censos

        for idx, archivo in enumerate(archivos):
            nombre = archivo.stem; modo = modos.get(archivo.name,"escaneado")
            icono  = {"digital":"⚡","escaneado":"🔍","imagen":"🖼️"}.get(modo,"📄")
            self._put(tipo="log", texto=f"{icono} {archivo.name} ({idx+1}/{total})")
            txt_dir = dir_ocr/nombre; txt_dir.mkdir(exist_ok=True)
            try:
                if modo == "digital":
                    # Ruta 3: texto BNC con reconstrucción por coordenadas (alto_reconstructor)
                    # Usa las coordenadas X/Y de cada span para reconstruir el orden de columnas
                    # en vez de confiar en el orden lineal del PDF (que mezcla columnas).
                    import fitz

                    from core.alto_reconstructor import reconstruir_texto_pagina
                    from core.ocr_normalizer import normalizar_texto_ocr

                    _MARCA_BNC = "Digitalizado Biblioteca Nacional de Colombia"

                    # La ruta se decide POR PÁGINA, nunca por la declaración de
                    # fuentes del documento: El Día declara la capa oculta de
                    # Paper Capture igual que Estampa y solo 2 de sus 16 páginas
                    # la tienen. Con un veredicto de documento se escribían
                    # catorce archivos vacíos y se reportaba éxito.
                    modos_pag = (ST.censos_pagina.get(archivo.name)
                                 if hasattr(ST, "censos_pagina") else None) or []

                    rows = []
                    sin_texto = []
                    doc_bnc = fitz.open(str(archivo))
                    for i, page in enumerate(doc_bnc):
                        pagina_id = f"p{i+1:04d}"
                        tp = txt_dir / f"{pagina_id}.txt"
                        if not tp.exists():
                            if i < len(modos_pag) and modos_pag[i] != "digital":
                                # No tiene texto embebido: no se escribe un .txt
                                # vacío. Se anota para OCR y se resuelve abajo.
                                sin_texto.append(i + 1)
                                continue
                            try:
                                resultado = reconstruir_texto_pagina(
                                    page,
                                    ignorar_ocr_basura=True,
                                )
                                texto = resultado.get("texto", "")
                                # Eliminar marca de digitalización de la BNC
                                texto = texto.replace(_MARCA_BNC, "").strip()
                                texto = normalizar_texto_ocr(texto)
                            except Exception:
                                texto = page.get_text("text")
                            tp.write_text(texto, encoding="utf-8")
                        else:
                            texto = tp.read_text("utf-8", errors="replace")
                        rows.append({
                            "numero":   nombre,
                            "pagina":   pagina_id,
                            "txt_path": str(tp),
                            "palabras": len(texto.split()),
                            "confianza": None,
                            "revision": False,
                            "metodo":   "bnc_coordenadas",
                        })
                    doc_bnc.close()

                    if sin_texto:
                        self._put(tipo="log",
                            texto=f"  🔍 {len(sin_texto)} pág sin texto embebido "
                                  "→ Tesseract (no se dan por vacías)")
                        rows.extend(self._ocr_paginas_faltantes(
                            archivo, nombre, txt_dir, dir_img, sin_texto, dpi))

                    meta_rows.extend(rows)
                    self._put(tipo="log",
                        texto=f"  ✅ {len(rows)} pág · BNC + reconstrucción por coordenadas")

                elif modo == "escaneado":
                    img_dir_n = dir_img/nombre
                    try:
                        imgs = pdf_a_imagenes(archivo, img_dir_n, dpi)
                    except Exception as e:
                        if "poppler" in str(e).lower():
                            try:
                                from instalar import instalar_poppler_windows
                                instalar_poppler_windows()
                                from core.ocr_engine import _get_poppler_path as _gp
                                nr = _gp()
                                if nr: os.environ["PATH"]=nr+os.pathsep+os.environ.get("PATH","")
                                imgs = pdf_a_imagenes(archivo, img_dir_n, dpi)
                            except Exception as e2:
                                self._put(tipo="log",texto=f"  ❌ Poppler: {e2}"); errores.append(archivo.name); continue
                        else:
                            self._put(tipo="log",texto=f"  ❌ {e}"); errores.append(archivo.name); continue
                    np_total = len(imgs)

                    # ── Preprocesamiento opcional — guarda en carpeta separada ──
                    # Las originales a color se preservan en 02_imagenes/<nombre>/
                    # Las procesadas para OCR van a 02_imagenes_ocr/<nombre>/
                    pre_deskew    = snap.get("_var_pre_deskew")
                    pre_enhance   = snap.get("_var_pre_enhance")
                    pre_despeckle = snap.get("_var_pre_despeckle")
                    do_pre = (
                        (pre_deskew    and pre_deskew.get()) or
                        (pre_enhance   and pre_enhance.get()) or
                        (pre_despeckle and pre_despeckle.get())
                    )
                    if do_pre:
                        try:
                            from PIL import Image as _PIL

                            from core.image_preprocessor import preprocesar_para_ocr
                            dir_ocr_imgs = out / "02_imagenes_ocr" / nombre
                            dir_ocr_imgs.mkdir(parents=True, exist_ok=True)
                            imgs_procesadas = []
                            for ip in imgs:
                                img_pil = _PIL.open(ip).convert("RGB")
                                img_proc = preprocesar_para_ocr(
                                    img_pil,
                                    deskew_en    = bool(pre_deskew    and pre_deskew.get()),
                                    enhance_en   = bool(pre_enhance   and pre_enhance.get()),
                                    despeckle_en = bool(pre_despeckle and pre_despeckle.get()),
                                )
                                # Guardar procesada en carpeta OCR, original intacta
                                dest = dir_ocr_imgs / ip.name
                                img_proc.save(str(dest))
                                imgs_procesadas.append(dest)
                            imgs = imgs_procesadas
                            self._put(tipo="log", texto=f"  🔧 Preprocesamiento aplicado a {len(imgs)} imágenes")
                        except Exception as ep:
                            self._put(tipo="log", texto=f"  ⚠ Preprocesamiento omitido: {ep}")

                    if ruta_ocr in ("vision_ia", "claude"):
                        # Ruta 2: IA de visión multiproveedor (Claude/GPT-4o/Gemini/Ollama)
                        prov  = _ocr_vision_prov  if ruta_ocr == "vision_ia" else "claude"
                        model = _ocr_vision_model if ruta_ocr == "vision_ia" else ""
                        api_key = ST.api_keys.get(prov, "") or ST.api_key
                        if prov != "ollama" and not api_key:
                            self._put(tipo="log",
                                texto=f"  ❌ Ruta 2 requiere API key de {prov}. Configúrala en ⚙ Configuración.")
                            errores.append(archivo.name); continue

                        for pi, ip in enumerate(imgs):
                            tp = txt_dir/(ip.stem+".txt")
                            if tp.exists():
                                texto = tp.read_text("utf-8", errors="replace"); conf = 95.0
                            else:
                                try:
                                    # core.ocr_llm es la ÚNICA implementación
                                    # de OCR por visión. app.py tenía la suya
                                    # propia, divergente: sin el prompt
                                    # calibrado contra el juez de ground truth,
                                    # sin registrar el gasto de IA, sin filtrar
                                    # los rechazos del modelo y sin lmstudio.
                                    # La Ruta 2 —la que se paga— usaba esa.
                                    from core.ocr_llm import ocr_con_vision
                                    texto = ocr_con_vision(
                                        ip, api_key=api_key,
                                        modelo=model or _MODELO_VISION_DEFECTO,
                                        proveedor=prov)
                                    conf  = 95.0
                                except Exception as ec:
                                    self._put(tipo="log",
                                        texto=f"    ⚠ {prov} falló en {ip.stem}: {ec}. Usando Tesseract.")
                                    texto, conf = ocr_pagina(ip, lang=lang)
                                tp.write_text(texto, "utf-8")
                            meta_rows.append({"numero":nombre,"pagina":ip.stem,"txt_path":str(tp),
                                              "palabras":len(texto.split()),"confianza":conf,
                                              "revision":False,"metodo":f"vision_{prov}"})
                            pct=int(((idx*np_total+pi+1)/(total*max(np_total,1)))*100)
                            self._put(tipo="prog",val=pct,txt=f"{nombre}·pg{pi+1}/{np_total}")
                        self._put(tipo="log",texto=f"  ✅ {np_total} pág · {prov}/{model}")

                    elif ruta_ocr == "kraken":
                        # Ruta 4: Kraken CATMuS-Print
                        from core.ocr_kraken import ocr_kraken_lote
                        _vk = snap.get("_var_kraken_modelo")
                        modelo_k = (_vk.get() if _vk else "") or None
                        try:
                            workers_k = max(1, int(snap["_var_kraken_workers"].get()))
                        except Exception:
                            workers_k = 3
                        try:
                            timeout_k = max(60, int(snap["_var_kraken_timeout"].get()))
                        except Exception:
                            timeout_k = 600
                        rutas_imgs = [str(ip) for ip in imgs]
                        resultados_k = ocr_kraken_lote(
                            rutas_imgs, modelo_path=modelo_k,
                            workers=workers_k, timeout=timeout_k,
                            callback=lambda i,t,r,ok: self._put(
                                tipo="prog",
                                val=int(((idx*t+i)/(total*max(t,1)))*100),
                                txt=f"{nombre}·pg{i}/{t}")
                        )
                        for pi, (ip, res_k) in enumerate(zip(imgs, resultados_k)):
                            tp = txt_dir/(ip.stem+".txt")
                            if res_k["ok"]:
                                texto = res_k["texto"]; conf = round(res_k["confianza"]*100, 1)
                                tp.write_text(texto, "utf-8")
                            else:
                                err_msg = res_k['error'] or ""
                                self._put(tipo="log", texto=f"    ⚠ Kraken falló en {ip.stem}: {err_msg[:120]}")
                                # Intentar fallback Tesseract; si no está disponible, guardar vacío
                                try:
                                    texto, conf = ocr_pagina(ip, lang=lang)
                                    tp.write_text(texto, "utf-8")
                                    self._put(tipo="log", texto="      → Tesseract usado como respaldo")
                                except Exception as ef:
                                    texto, conf = "", 0.0
                                    tp.write_text("", "utf-8")
                                    self._put(tipo="log", texto=f"      → Sin respaldo disponible ({ef}). Página marcada para revisión manual.")
                            meta_rows.append({"numero":nombre,"pagina":ip.stem,"txt_path":str(tp),
                                              "palabras":len(texto.split()),"confianza":conf,
                                              "revision":bool(conf and conf<60),"metodo":"kraken"})
                        self._put(tipo="log",texto=f"  ✅ {np_total} pág · Kraken CATMuS-Print")

                    elif ruta_ocr == "ollama":
                        # Ruta 5: Ollama Vision local
                        from core.ocr_ollama_local import ocr_ollama_lote
                        _vo = snap.get("_var_ollama_modelo")
                        modelo_o = (_vo.get() if _vo else "") or "qwen3.6:latest"
                        rutas_imgs = [str(ip) for ip in imgs]
                        resultados_o = ocr_ollama_lote(
                            rutas_imgs, modelo=modelo_o,
                            callback=lambda i,t,r,ok: self._put(
                                tipo="prog",
                                val=int(((idx*t+i)/(total*max(t,1)))*100),
                                txt=f"{nombre}·pg{i}/{t}")
                        )
                        for pi, (ip, res_o) in enumerate(zip(imgs, resultados_o)):
                            tp = txt_dir/(ip.stem+".txt")
                            if res_o["ok"]:
                                texto = res_o["texto"]; conf = round(res_o["confianza"]*100, 1)
                                tp.write_text(texto, "utf-8")
                            else:
                                self._put(tipo="log", texto=f"    ⚠ Ollama falló en {ip.stem}: {res_o['error']}. Usando Tesseract.")
                                texto, conf = ocr_pagina(ip, lang=lang)
                                tp.write_text(texto, "utf-8")
                            meta_rows.append({"numero":nombre,"pagina":ip.stem,"txt_path":str(tp),
                                              "palabras":len(texto.split()),"confianza":conf,
                                              "revision":bool(conf and conf<60),"metodo":"ollama"})
                        self._put(tipo="log",texto=f"  ✅ {np_total} pág · Ollama Vision")

                    else:
                        # Ruta 1: Tesseract propio (ignora texto BNC).
                        # Si la página tiene zonas etiquetadas (05_etiquetas/),
                        # se OCR-ea por zonas en orden de lectura (estilo FineReader).
                        from core.layout_tesseract import ocr_pagina_con_zonas
                        n_zonal = 0
                        for pi, ip in enumerate(imgs):
                            tp = txt_dir/(ip.stem+".txt")
                            metodo_pag = "ocr"
                            # Forzar re-OCR si la fuente era texto BNC (sobreescribir)
                            if tp.exists() and ruta_ocr == "tesseract":
                                # Solo reusar si el metodo ya fue tesseract (no BNC)
                                meta_csv = out/"04_analisis"/"ocr_metadatos.csv"
                                fue_tesseract = False
                                if meta_csv.exists():
                                    try:
                                        import pandas as _pd
                                        _m = _pd.read_csv(meta_csv)
                                        row_m = _m[(_m["numero"]==nombre) & (_m["pagina"]==ip.stem)]
                                        if not row_m.empty and row_m.iloc[0].get("metodo","") in ("ocr","ocr_zonas"):
                                            fue_tesseract = True
                                            metodo_pag = row_m.iloc[0].get("metodo","ocr")
                                    except Exception:
                                        pass
                                if fue_tesseract:
                                    texto=tp.read_text("utf-8",errors="replace"); conf=None
                                else:
                                    texto, conf, con_z = ocr_pagina_con_zonas(
                                        ip, out, nombre, ip.stem, lang=lang)
                                    tp.write_text(texto,"utf-8")
                                    if con_z:
                                        metodo_pag = "ocr_zonas"; n_zonal += 1
                            else:
                                texto, conf, con_z = ocr_pagina_con_zonas(
                                    ip, out, nombre, ip.stem, lang=lang)
                                tp.write_text(texto,"utf-8")
                                if con_z:
                                    metodo_pag = "ocr_zonas"; n_zonal += 1
                            meta_rows.append({"numero":nombre,"pagina":ip.stem,"txt_path":str(tp),
                                              "palabras":len(texto.split()),"confianza":conf,
                                              "revision":bool(conf and conf<60),"metodo":metodo_pag})
                            pct=int(((idx*np_total+pi+1)/(total*max(np_total,1)))*100)
                            self._put(tipo="prog",val=pct,txt=f"{nombre}·pg{pi+1}/{np_total}")
                        extra_z = f" ({n_zonal} por zonas)" if n_zonal else ""
                        self._put(tipo="log",texto=f"  ✅ {np_total} pág · Tesseract{extra_z}")
                else:
                    rows=imagenes_a_texto(archivo.parent,txt_dir,lang)
                    for r in rows: r["numero"]=nombre
                    meta_rows.extend(rows)
                    self._put(tipo="log",texto=f"  ✅ {len(rows)} imágenes")
            except Exception as e:
                self._put(tipo="log",texto=f"  ❌ {e}"); errores.append(archivo.name)
            gc.collect()
            self._put(tipo="prog",val=int((idx+1)/total*100),txt=f"{idx+1}/{total}")

        # ── Postprocesamiento: aplicar zonas etiquetadas si está activo ──────────
        if usar_etiq and meta_rows:
            api_key_det = ""
            if det_auto:
                api_key_det, _ = _resolver_api_key_modelo("deteccion")
            n_filtradas = 0
            self._put(tipo="fase", txt="Aplicando zonas etiquetadas…")
            for row in meta_rows:
                try:
                    tp = Path(row["txt_path"])
                    if tp.exists():
                        texto_orig = tp.read_text("utf-8", errors="replace")
                        texto_filt = self._ocr_aplicar_zonas(
                            texto_orig, row["numero"], row["pagina"],
                            det_auto=det_auto, api_key=api_key_det)
                        if texto_filt != texto_orig:
                            tp.write_text(texto_filt, "utf-8")
                            row["palabras"] = len(texto_filt.split())
                            n_filtradas += 1
                except Exception:
                    pass
            if n_filtradas:
                self._put(tipo="log",
                          texto=f"✂️ {n_filtradas} páginas filtradas por zonas etiquetadas")

        # ── Avisos de calidad por página (estilo FineReader) ─────────────────────
        # Se calculan desde los datos YA disponibles en meta_rows (texto, conteo
        # de palabras, confianza) sin reabrir ninguna imagen — el DPI real solo se
        # chequea bajo demanda cuando el investigador abre una página puntual en
        # Normalizar, para no sumar una relectura de disco/Drive por cada página
        # del lote (que puede ser de cientos de páginas).
        if meta_rows:
            from core.page_quality import es_pagina_vacia
            self._avisos_ocr = {}
            for row in meta_rows:
                claves = []
                texto = ""
                tp = Path(row["txt_path"]) if row.get("txt_path") else None
                if tp and tp.exists():
                    try:
                        texto = tp.read_text("utf-8", errors="replace")
                    except Exception:
                        texto = ""
                if es_pagina_vacia(texto, n_tokens=row.get("palabras")):
                    claves.append("Página posiblemente en blanco o sin texto útil")
                conf = row.get("confianza")
                if conf is not None and conf < 30:
                    claves.append(f"Confianza OCR muy baja: {conf:.0f}%")
                if claves:
                    self._avisos_ocr[(row["numero"], row["pagina"])] = claves
            if self._avisos_ocr:
                self._put(tipo="log",
                    texto=f"⚠ {len(self._avisos_ocr)} página(s) con avisos de calidad "
                          "(ver detalle en Normalizar)")

        if not meta_rows:
            self._put(tipo="err",txt="No se pudo procesar ningún archivo.")
            self.after(0, lambda: self._btn_ocr.config(state="normal")); return

        COLS=["numero","pagina","txt_path","palabras","confianza","revision"]
        df=pd.DataFrame(meta_rows)
        for c in COLS:
            if c not in df.columns: df[c]=None
        df["palabras"]=pd.to_numeric(df["palabras"],errors="coerce").fillna(0).astype(int)
        df["confianza"]=pd.to_numeric(df["confianza"],errors="coerce")
        df["revision"]=df["confianza"].apply(lambda c: bool(pd.notna(c) and c<60))
        ad=out/"04_analisis"; ad.mkdir(exist_ok=True)
        df.to_csv(ad/"ocr_metadatos.csv", index=False)
        ST.corpus_meta=df; ST.ocr_done=True
        ST.marcar_etapa("ocr", "ready")

        n_rev=int(df["revision"].sum()); cm=df["confianza"].dropna().mean(); tp=int(df["palabras"].sum())
        n_dir=int(df.get("metodo",pd.Series()).eq("texto_embebido").sum()) if "metodo" in df.columns else 0
        self.after(0,lambda: self._lbl_o_pdf.config(text=str(total-len(errores))))
        self.after(0,lambda: self._lbl_o_pag.config(text=f"{len(df):,}"))
        self.after(0,lambda: self._lbl_o_pal.config(text=f"{tp:,}"))
        self.after(0,lambda: self._lbl_o_con.config(text=f"{cm:.0f}%" if pd.notna(cm) else "—"))
        self.after(0,lambda: self._lbl_o_rev.config(text=str(n_rev)))
        if errores: self._put(tipo="log",texto=f"⚠️ Errores: {', '.join(errores)}")
        self._put(tipo="prog",val=100,txt="✅"); self._put(tipo="fase",txt="✅ Extracción completada")
        self._put(tipo="log",texto=f"🎉 {len(df):,} páginas · {tp:,} palabras")
        self._put(tipo="ok",res="ocr")

    def _worker_ocr_carpetas(self, numeros: list[dict], snap: dict | None = None):
        """
        Worker OCR para el modo 'subcarpetas': cada elemento de numeros es
        {'nombre': str, 'pdfs': list[Path], 'carpeta': Path}.
        Cada PDF de la subcarpeta es una página del número.
        Usa alto_reconstructor para reconstruir el orden de columnas.
        """
        import fitz
        import pandas as pd

        from core.alto_reconstructor import reconstruir_texto_pagina
        from core.ocr_normalizer import normalizar_texto_ocr

        out  = ST.out_dir
        snap = snap if snap is not None else self._snapshot_ocr()
        _vr = snap.get("_var_ruta_ocr")
        ruta_ocr = (_vr.get() if _vr else "") or "bnc"
        _vl = snap.get("_var_lang")
        lang = (_vl.get() if _vl else "") or "spa"

        _MARCA_BNC = "Digitalizado Biblioteca Nacional de Colombia"
        meta_rows  = []
        errores    = []
        total_nums = len(numeros)

        for n_idx, num_info in enumerate(numeros):
            nombre = num_info["nombre"]
            pdfs   = num_info["pdfs"]
            self._put(tipo="log", texto=f"📁 {nombre} ({n_idx+1}/{total_nums}) — {len(pdfs)} páginas")

            txt_dir = out / "03_ocr" / nombre
            img_dir = out / "02_imagenes" / nombre
            txt_dir.mkdir(parents=True, exist_ok=True)
            img_dir.mkdir(parents=True, exist_ok=True)

            for p_idx, pdf_path in enumerate(pdfs):
                pagina_id = f"p{p_idx+1:04d}"
                tp = txt_dir / f"{pagina_id}.txt"
                pct = int(((n_idx * len(pdfs) + p_idx + 1) /
                           max(total_nums * len(pdfs), 1)) * 100)
                self._put(tipo="prog", val=pct,
                          txt=f"{nombre}·{pagina_id}")

                palabras = 0
                confianza = None
                metodo = "bnc_coordenadas"

                try:
                    if ruta_ocr in ("bnc", "tesseract") or not tp.exists():
                        doc = fitz.open(str(pdf_path))
                        page = doc[0]

                        # Guardar imagen original a color
                        img_dest = img_dir / f"{pagina_id}.png"
                        if not img_dest.exists():
                            import io

                            from PIL import Image as _PIL
                            zoom = 150 / 72.0
                            mat  = fitz.Matrix(zoom, zoom)
                            pix  = page.get_pixmap(matrix=mat, alpha=False)
                            img  = _PIL.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                            img.save(str(img_dest), "PNG")

                        if not tp.exists():
                            if ruta_ocr == "tesseract":
                                # OCR con Tesseract sobre la imagen extraída
                                from core.ocr_engine import ocr_pagina
                                texto, confianza = ocr_pagina(img_dest, lang=lang)
                                metodo = "tesseract"
                            else:
                                # Ruta 3 BNC: reconstrucción por coordenadas
                                resultado = reconstruir_texto_pagina(page,
                                                ignorar_ocr_basura=True)
                                texto = resultado.get("texto", "")
                                texto = texto.replace(_MARCA_BNC, "").strip()
                                texto = normalizar_texto_ocr(texto)

                            tp.write_text(texto, encoding="utf-8")
                        else:
                            texto = tp.read_text("utf-8", errors="replace")

                        doc.close()
                        palabras = len(texto.split())

                except Exception as e:
                    self._put(tipo="log",
                        texto=f"  ⚠ {pagina_id}: {str(e)[:80]}")
                    errores.append(f"{nombre}/{pagina_id}")
                    continue

                meta_rows.append({
                    "numero":    nombre,
                    "pagina":    pagina_id,
                    "txt_path":  str(tp),
                    "palabras":  palabras,
                    "confianza": confianza,
                    "revision":  False,
                    "metodo":    metodo,
                })

            n_pag = len(pdfs)
            pal   = sum(r["palabras"] for r in meta_rows if r["numero"] == nombre)
            self._put(tipo="log",
                texto=f"  ✅ {n_pag} pág · {pal:,} palabras · {nombre}")

        # Consolidar metadatos
        COLS = ["numero","pagina","txt_path","palabras","confianza","revision","metodo"]
        df = pd.DataFrame(meta_rows) if meta_rows else pd.DataFrame(columns=COLS)
        for c in COLS:
            if c not in df.columns: df[c] = None
        df["palabras"]  = pd.to_numeric(df["palabras"],  errors="coerce").fillna(0).astype(int)
        df["confianza"] = pd.to_numeric(df["confianza"], errors="coerce")
        df["revision"]  = df["confianza"].apply(
            lambda c: bool(pd.notna(c) and c < 60))

        ad = out / "04_analisis"
        ad.mkdir(exist_ok=True)
        df.to_csv(ad / "ocr_metadatos.csv", index=False)
        ST.corpus_meta = df
        ST.ocr_done    = True
        ST.marcar_etapa("ocr", "ready")

        tp_total = int(df["palabras"].sum())
        self._put(tipo="prog", val=100, txt="✅")
        self._put(tipo="fase", txt="✅ Extracción completada")
        self._put(tipo="log",
            texto=f"🎉 {total_nums} números · {len(df):,} páginas · {tp_total:,} palabras")
        if errores:
            self._put(tipo="log", texto=f"⚠ Errores: {len(errores)} páginas")
        self._put(tipo="ok", res="ocr")
