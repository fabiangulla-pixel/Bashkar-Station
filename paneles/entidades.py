"""paneles/entidades.py — Métodos de BashkarApp extraídos de app.py.

Mixin: BashkarApp hereda de PanelEntidades. Los cuerpos son copia literal del
original; los nombres globales (ST, colores, tk…) los inyecta
paneles.sincronizar() desde app.py.
"""

from __future__ import annotations

# ruff: noqa: F821


class PanelEntidades:
    # ══════════════════════════════════════════════════════════════════════════
    # TAB NER: ÍNDICE DE ENTIDADES NOMBRADAS
    # ══════════════════════════════════════════════════════════════════════════
    def _build_ner(self):
        f = self._tab_ner
        self._page_header(f, "Índice de Entidades Nombradas",
                          "Personas · Lugares · Organizaciones · Fechas · Obras · Eventos", "🔍")
        self._build_ai_panel(f, "ner")

        # Contenedor con split horizontal (contenido izq + panel params der)
        main_split = tk.Frame(f, bg=CONTENT_BG)
        main_split.pack(fill="both", expand=True, padx=24, pady=16)

        # Panel de parámetros NER (derecha, colapsable)
        self._ner_params: dict = {}
        try:
            from core.ner_engine import PARAMS_SCHEMA as _NER_SCHEMA
            self._build_params_panel(main_split, _NER_SCHEMA, self._ner_params)
        except Exception:
            pass

        pad = tk.Frame(main_split, bg=CONTENT_BG)
        pad.pack(side="left", fill="both", expand=True)

        # ── Barra de acciones ─────────────────────────────────────────────────
        bf = tk.Frame(pad, bg=CONTENT_BG); bf.pack(fill="x", pady=(0, 8))
        self._btn_ner_art = ttk.Button(bf, text="▶  Analizar artículo actual",
                                        style="P.TButton", command=self._ner_articulo_actual)
        self._btn_ner_art.pack(side="left", padx=(0, 8))
        self._btn_ner_corpus = ttk.Button(bf, text="📚  Analizar corpus completo",
                                           style="S.TButton", command=self._ner_corpus_completo)
        self._btn_ner_corpus.pack(side="left", padx=(0, 8))
        self._var_ner_llm = tk.BooleanVar(value=False)
        ttk.Checkbutton(bf, text="🤖 Usar IA:", variable=self._var_ner_llm).pack(side="left", padx=(8, 2))
        self._var_ner_prov = tk.StringVar(value="claude")
        self._cmb_ner_prov = ttk.Combobox(bf, textvariable=self._var_ner_prov,
                                           values=["claude", "ollama", "lmstudio"], state="readonly",
                                           width=8, font=("Segoe UI", 9))
        self._cmb_ner_prov.pack(side="left", padx=(0, 4))
        self._var_ner_ollama_modelo = tk.StringVar(value="latamgpt")
        self._ent_ner_ollama_modelo = ttk.Entry(bf, textvariable=self._var_ner_ollama_modelo,
                                                width=10, font=("Segoe UI", 9))
        def _ner_prov_changed(*_):
            prov = self._var_ner_prov.get()
            if prov == "lmstudio":
                from core.ocr_llm import modelos_cargados_lmstudio
                modelos = modelos_cargados_lmstudio()
                if modelos:
                    self._var_ner_ollama_modelo.set(modelos[0])
                self._ent_ner_ollama_modelo.pack(side="left", padx=(0, 8))
            elif prov == "ollama":
                self._ent_ner_ollama_modelo.pack(side="left", padx=(0, 8))
            else:
                self._ent_ner_ollama_modelo.pack_forget()
        self._var_ner_prov.trace_add("write", _ner_prov_changed)
        ttk.Button(bf, text="📥 Exportar CSV", style="S.TButton",
                   command=self._ner_exportar_csv).pack(side="right")
        ttk.Button(bf, text="🌐 Enlazar Wikidata", style="S.TButton",
                   command=self._ner_enlazar_wikidata).pack(side="right", padx=(0, 6))
        ttk.Button(bf, text="📓 Nota", style="S.TButton",
                   command=lambda: self._bitacora_nueva_nota("ner")).pack(side="right", padx=(0, 6))

        self._lbl_ner_ok = tk.Label(pad, text="", bg=CONTENT_BG, fg=VERDE,
                                     font=("Segoe UI", 9, "bold"))
        self._lbl_ner_ok.pack(anchor="w", pady=(0, 4))

        # ── Split: treeview izquierda + detalle derecha ───────────────────────
        split = tk.Frame(pad, bg=CONTENT_BG); split.pack(fill="both", expand=True)

        izq = tk.Frame(split, bg=CONTENT_BG, width=440)
        izq.pack(side="left", fill="both", expand=True, padx=(0, 8))
        izq.pack_propagate(False)

        # Filtro categoría + búsqueda
        filt_f = tk.Frame(izq, bg=CARD_BG, relief="solid", bd=1)
        filt_f.pack(fill="x", pady=(0, 6))
        fi = tk.Frame(filt_f, bg=CARD_BG, padx=10, pady=6); fi.pack(fill="x")
        tk.Label(fi, text="Categoría:", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        _cats = ["Todas", "personas", "lugares", "organizaciones",
                 "fechas", "obras_publicaciones", "eventos_historicos"]
        self._var_ner_cat = tk.StringVar(value="Todas")
        self._cmb_ner_cat = ttk.Combobox(fi, textvariable=self._var_ner_cat, values=_cats,
                                          state="readonly", width=22, font=("Segoe UI", 9))
        self._cmb_ner_cat.pack(side="left", padx=8)
        self._cmb_ner_cat.bind("<<ComboboxSelected>>", lambda e: self._ner_refrescar_tv())
        tk.Label(fi, text="Buscar:", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(12, 0))
        self._var_ner_buscar = tk.StringVar()
        self._var_ner_buscar.trace_add("write", lambda *_: self._ner_refrescar_tv())
        tk.Entry(fi, textvariable=self._var_ner_buscar, width=18,
                 font=("Segoe UI", 9), relief="solid", bd=1).pack(side="left", padx=6)

        # Treeview
        tv_frame = tk.Frame(izq, bg=CARD_BG, relief="solid", bd=1)
        tv_frame.pack(fill="both", expand=True)
        cols = ("entidad", "tipo", "n_arts", "wikidata")
        self._tv_ner = ttk.Treeview(tv_frame, columns=cols, show="headings", height=22)
        self._tv_ner.heading("entidad",  text="Entidad")
        self._tv_ner.heading("tipo",     text="Tipo")
        self._tv_ner.heading("n_arts",   text="# Arts.")
        self._tv_ner.heading("wikidata", text="Wikidata")
        self._tv_ner.column("entidad",  width=220, anchor="w")
        self._tv_ner.column("tipo",     width=120, anchor="w")
        self._tv_ner.column("n_arts",   width=60,  anchor="center")
        self._tv_ner.column("wikidata", width=110, anchor="w")
        vsb = ttk.Scrollbar(tv_frame, orient="vertical", command=self._tv_ner.yview)
        self._tv_ner.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tv_ner.pack(fill="both", expand=True)
        self._tv_ner.bind("<<TreeviewSelect>>", self._ner_on_select)
        self._tv_ner.bind("<Double-1>", self._ner_abrir_wikidata)

        # Panel detalle
        der = tk.Frame(split, bg=CONTENT_BG, width=260)
        der.pack(side="left", fill="both")
        der.pack_propagate(False)
        det_card = tk.Frame(der, bg=CARD_BG, relief="solid", bd=1)
        det_card.pack(fill="both", expand=True)
        det_hdr = tk.Frame(det_card, bg="#171C20"); det_hdr.pack(fill="x")
        tk.Label(det_hdr, text="  📋  Detalle", bg="#171C20", fg=TXT_PRI,
                 font=("Segoe UI", 8, "bold")).pack(side="left", pady=4)
        self._txt_ner_det = scrolledtext.ScrolledText(det_card, font=("Consolas", 9),
                                                       bg="#171C20", fg="#E8E5DF",
                                                       relief="flat", state="disabled")
        self._txt_ner_det.pack(fill="both", expand=True, padx=1, pady=(0, 1))

        # Log
        log_f = tk.Frame(pad, bg="#12171B", bd=1, relief="solid")
        log_f.pack(fill="x", pady=(8, 0))
        log_hdr = tk.Frame(log_f, bg="#14202A"); log_hdr.pack(fill="x")
        tk.Label(log_hdr, text="  📋  Registro NER", bg="#14202A", fg="#B5B6B3",
                 font=("Segoe UI", 8, "bold")).pack(side="left", pady=4)
        self._log_ner = scrolledtext.ScrolledText(log_f, height=5, font=("Consolas", 9),
                                                   bg="#12171B", fg="#6EC69A",
                                                   relief="flat", state="disabled")
        self._log_ner.pack(fill="x", padx=1, pady=(0, 1))

    def _ner_log(self, msg: str):
        def _do():
            self._log_ner.config(state="normal")
            self._log_ner.insert("end", msg + "\n")
            self._log_ner.see("end")
            self._log_ner.config(state="disabled")
        self.after(0, _do)

    def _ner_articulo_actual(self):
        texto = ""
        art_id = "articulo_actual"
        if ST.df_articulos is not None and not ST.df_articulos.empty:
            sel = self._tv_seg.selection() if hasattr(self, "_tv_seg") else []
            if sel:
                idx = self._tv_seg.index(sel[0])
                row = ST.df_articulos.iloc[idx]
                texto = str(row.get("texto", row.get("contenido", "")))
                art_id = str(row.get("id", row.get("titulo", f"art_{idx}")))
        if not texto and ST.out_dir:
            txt_dir = ST.out_dir / "03_ocr"
            if txt_dir.exists():
                # Buscar el primer txt con contenido real (>100 palabras)
                # para evitar procesar archivos vacíos o de log
                for tf in sorted(txt_dir.rglob("*.txt")):
                    contenido = tf.read_text("utf-8", errors="replace")
                    if len(contenido.split()) > 100:
                        texto = contenido
                        art_id = tf.stem
                        break
        if not texto:
            messagebox.showwarning("Sin texto",
                "No hay texto disponible para analizar.\n\n"
                "Opciones:\n"
                "1. Selecciona un artículo en la pestaña Segmentar\n"
                "2. Completa la extracción OCR primero")
            return
        self._btn_ner_art.config(state="disabled")
        # Parámetros y variables Tk leídos en el hilo principal (ver _start_anal).
        threading.Thread(target=self._worker_ner_articulo,
                         args=(texto, art_id, self._snapshot_ner()),
                         daemon=True).start()

    def _worker_ner_articulo(self, texto: str, art_id: str, snap: dict):
        import spacy

        from core.ner_engine import actualizar_indice_global, pipeline_ner
        p = snap["params"]
        usar_ia = snap["usar_ia"]
        proveedor_llm = snap["proveedor_llm"]
        modelo_ollama = snap["modelo_ollama"]
        if usar_ia:
            if proveedor_llm == "ollama":
                api_key = ST.api_keys.get("ollama", "http://localhost:11434")
            elif proveedor_llm == "lmstudio":
                api_key = ST.api_keys.get("lmstudio", "http://localhost:1234")
            else:
                api_key, _modelo_ner = _resolver_api_key_modelo("ner")
        else:
            api_key = None
        min_palabras = int(p.get("min_longitud_texto", 100))
        if len(texto.split()) < min_palabras:
            self._ner_log(f"⚠ {art_id}: menos de {min_palabras} palabras, omitido")
            self.after(0, lambda: self._btn_ner_art.config(state="normal"))
            return
        self._ner_log(f"▶ Analizando: {art_id}")
        motor = p.get("motor", "auto")
        try:
            nlp = spacy.load("es_core_news_lg") if motor != "fallback" else None
        except OSError:
            nlp = None
            if motor == "spacy":
                self._ner_log("⚠ spaCy no instalado. Ejecuta: python -m spacy download es_core_news_lg")
                self.after(0, lambda: self._btn_ner_art.config(state="normal"))
                return
        umbral = float(p.get("umbral_confianza", 0.7))
        cats   = p.get("categorias") or None
        # usar_roberta=True salvo que la investigadora elija "spacy"/"fallback"
        # a propósito en "Motor NER". El segfault que sesión 62 le atribuyó a
        # un conflicto de threading torch/tokenizers (con
        # recursos.aplicar_limites_cpu() activo, línea ~26) no era eso — era
        # core/ner_roberta_local.py forzando HF_HUB_OFFLINE=1 DESPUÉS de que
        # `transformers` ya hubiera arrastrado huggingface_hub, que congela esa
        # variable como constante en su propio import. Confirmado y arreglado
        # en sesión 63 (ver ese módulo). nlp sigue cargado como red de
        # seguridad: si transformers falta o el modelo no carga, pipeline_ner
        # cae a spaCy solo.
        ner = pipeline_ner(texto, nlp, api_key=api_key, callback=self._ner_log,
                           umbral_confianza=umbral, categorias=cats,
                           proveedor_llm=proveedor_llm, modelo_ollama=modelo_ollama,
                           usar_roberta=(motor not in ("spacy", "fallback")))
        if not getattr(ST, "indice_ner_global", None):
            ST.indice_ner_global = {}
        actualizar_indice_global(ST.indice_ner_global, art_id, ner)
        ST.ner_done = True
        total = sum(len(v) for v in ner.values())
        self._ner_log(f"✅ {art_id}: {total} entidades")
        self.after(0, self._ner_refrescar_tv)
        self.after(0, lambda: self._btn_ner_art.config(state="normal"))
        self.after(0, lambda: self._lbl_ner_ok.config(text=f"✅ {art_id} analizado"))
        self.after(0, self._actualizar_badges)

    def _ner_corpus_completo(self):
        if not ST.ocr_done:
            messagebox.showwarning("OCR pendiente", "Completa la extracción OCR primero."); return
        if not messagebox.askyesno("Analizar corpus",
                "Esto analizará TODOS los textos del corpus.\n"
                "Con IA activada puede generar costo de API.\n\n¿Continuar?"):
            return
        self._btn_ner_corpus.config(state="disabled")
        self._btn_ner_art.config(state="disabled")
        threading.Thread(target=self._worker_ner_corpus,
                         args=(self._snapshot_ner(),), daemon=True).start()

    def _worker_ner_corpus(self, snap: dict):
        import spacy

        from core.ner_engine import (
            actualizar_indice_global,
            indice_global_vacio,
            pipeline_ner,
        )
        p = snap["params"]
        usar_ia = snap["usar_ia"]
        proveedor_llm = snap["proveedor_llm"]
        modelo_ollama = snap["modelo_ollama"]
        if usar_ia:
            if proveedor_llm == "ollama":
                api_key = ST.api_keys.get("ollama", "http://localhost:11434")
            elif proveedor_llm == "lmstudio":
                api_key = ST.api_keys.get("lmstudio", "http://localhost:1234")
            else:
                api_key = _resolver_api_key_modelo("ner")[0]
        else:
            api_key = None
        motor   = p.get("motor", "auto")
        umbral  = float(p.get("umbral_confianza", 0.7))
        cats    = p.get("categorias") or None
        min_palabras = int(p.get("min_longitud_texto", 100))
        try:
            nlp = spacy.load("es_core_news_lg") if motor != "fallback" else None
        except OSError:
            nlp = None
            if motor == "spacy":
                self._ner_log("⚠ spaCy no instalado. Ejecuta: python -m spacy download es_core_news_lg")
                self.after(0, lambda: self._btn_ner_corpus.config(state="normal"))
                self.after(0, lambda: self._btn_ner_art.config(state="normal"))
                return

        ST.indice_ner_global = indice_global_vacio()
        articulos = []
        if ST.df_articulos is not None and not ST.df_articulos.empty:
            for i, row in ST.df_articulos.iterrows():
                txt = str(row.get("texto", row.get("contenido", "")))
                aid = str(row.get("id", row.get("titulo", f"art_{i}")))
                if txt.strip() and len(txt.split()) >= min_palabras:
                    articulos.append((aid, txt))
        elif ST.out_dir:
            txt_dir = ST.out_dir / "03_ocr"
            if txt_dir.exists():
                for tf in sorted(txt_dir.rglob("*.txt")):
                    txt = tf.read_text("utf-8", errors="replace")
                    if txt.strip() and len(txt.split()) >= min_palabras:
                        articulos.append((tf.stem, txt))

        total = len(articulos)
        self._ner_log(f"📚 Corpus: {total} textos (umbral ≥{min_palabras} palabras)")
        for i, (aid, txt) in enumerate(articulos, 1):
            self._ner_log(f"[{i}/{total}] {aid}")
            # usar_roberta: ver comentario en _worker_ner_articulo.
            ner = pipeline_ner(txt, nlp, api_key=api_key,
                               umbral_confianza=umbral, categorias=cats,
                               proveedor_llm=proveedor_llm, modelo_ollama=modelo_ollama,
                               usar_roberta=(motor not in ("spacy", "fallback")))
            actualizar_indice_global(ST.indice_ner_global, aid, ner)
            if i % 5 == 0:
                self.after(0, self._ner_refrescar_tv)

        ST.ner_done = True
        n_ents = sum(len(v) for v in ST.indice_ner_global.values())
        self._ner_log(f"✅ Corpus completo: {n_ents} entidades únicas")
        self.after(0, self._ner_refrescar_tv)
        self.after(0, lambda: self._btn_ner_corpus.config(state="normal"))
        self.after(0, lambda: self._btn_ner_art.config(state="normal"))
        self.after(0, lambda: self._lbl_ner_ok.config(text=f"✅ {n_ents} entidades en índice global"))
        self.after(0, self._actualizar_badges)

    def _ner_refrescar_tv(self):
        self._tv_ner.delete(*self._tv_ner.get_children())
        if not getattr(ST, "indice_ner_global", None):
            return
        cat_filtro = self._var_ner_cat.get()
        buscar = self._var_ner_buscar.get().lower().strip()
        filas = []
        for cat, entidades in ST.indice_ner_global.items():
            if cat_filtro != "Todas" and cat != cat_filtro:
                continue
            for ent, arts in entidades.items():
                if buscar and buscar not in ent.lower():
                    continue
                filas.append((ent, cat, len(arts)))
        filas.sort(key=lambda r: (-r[2], r[1], r[0]))
        # Mapa wikidata: {cat: {entidad: {id, url, label}}}
        wiki = getattr(ST, "wikidata_enlaces", {}) or {}
        for ent, cat, n in filas:
            wiki_info = wiki.get(cat, {}).get(ent, {})
            wiki_id   = wiki_info.get("id", "")
            wiki_lbl  = wiki_info.get("label", wiki_id)
            wiki_cell = wiki_lbl if wiki_lbl else ""
            self._tv_ner.insert("", "end", values=(ent, cat, n, wiki_cell),
                                 tags=(cat,), iid=f"{cat}|{ent}")
        # Cada categoría con su fondo tintado y su texto en el mismo tono: en
        # una interfaz oscura, el chip claro con texto negro deslumbra.
        paleta = {"personas":            (INFO_BG,  AZ_INFO),
                  "lugares":             (READY_BG, VERDE),
                  "organizaciones":      (WARN_BG,  ACENT),
                  "fechas":              (TEAL_BG,  TEAL),
                  "obras_publicaciones": (PURP_BG,  PURPURA),
                  "eventos_historicos":  (ERR_BG,   ROJO)}
        for cat, (fondo, tinta) in paleta.items():
            self._tv_ner.tag_configure(cat, background=fondo, foreground=tinta)

    def _ner_abrir_wikidata(self, event=None):
        """Doble click en la tabla NER: abre el enlace Wikidata en el browser."""
        sel = self._tv_ner.selection()
        if not sel:
            return
        iid = sel[0]
        if "|" not in iid:
            return
        cat, ent = iid.split("|", 1)
        wiki = getattr(ST, "wikidata_enlaces", {}) or {}
        wiki_info = wiki.get(cat, {}).get(ent, {})
        url = wiki_info.get("url", "")
        if url:
            import webbrowser
            webbrowser.open(url)
        elif wiki_info.get("id"):
            import webbrowser
            webbrowser.open(f"https://www.wikidata.org/wiki/{wiki_info['id']}")
        else:
            messagebox.showinfo("Sin enlace",
                                f"No hay enlace Wikidata para «{ent}».\n"
                                f"Usa 'Enlazar Wikidata' para buscar coincidencias.")

    def _ner_on_select(self, event=None):
        sel = self._tv_ner.selection()
        if not sel:
            return
        # El iid puede ser "cat|ent" o simplemente el índice según la versión del treeview
        iid = sel[0]
        if "|" in iid:
            cat, ent = iid.split("|", 1)
        else:
            vals = self._tv_ner.item(iid)["values"]
            if not vals or len(vals) < 2:
                return
            ent, cat = str(vals[0]), str(vals[1])
        arts = ST.indice_ner_global.get(cat, {}).get(ent, [])
        txt = f"Entidad: {ent}\nTipo: {cat}\nArtículos ({len(arts)}):\n"
        for a in sorted(arts)[:30]:
            txt += f"  • {a}\n"
        if len(arts) > 30:
            txt += f"  … y {len(arts)-30} más\n"
        # Añadir enlace Wikidata si está disponible
        wikidata = getattr(ST, "wikidata_enlaces", {})
        enlace = wikidata.get(cat, {}).get(ent)
        if enlace:
            txt += "\n── Wikidata ──\n"
            txt += f"  ID:          {enlace.get('id','')}\n"
            txt += f"  Nombre:      {enlace.get('label','')}\n"
            txt += f"  Descripción: {enlace.get('description','')}\n"
            txt += f"  URL:         {enlace.get('url','')}\n"
            txt += f"  Confianza:   {enlace.get('confianza', 0):.0%}\n"
        self._txt_ner_det.config(state="normal")
        self._txt_ner_det.delete("1.0", "end")
        self._txt_ner_det.insert("1.0", txt)
        self._txt_ner_det.config(state="disabled")

    def _ner_exportar_csv(self):
        if not getattr(ST, "indice_ner_global", None):
            messagebox.showwarning("Sin datos", "Ejecuta el análisis NER primero."); return
        from pathlib import Path as _Path
        from tkinter import filedialog
        pub = getattr(ST, "publicacion", "corpus").replace(" ", "_")
        dest = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"indice_NER_{pub}.csv",
            title="Guardar índice NER")
        if not dest:
            return
        from core.ner_engine import exportar_csv
        n = exportar_csv(ST.indice_ner_global, _Path(dest))
        messagebox.showinfo("Exportado", f"✅ {n} entidades exportadas a:\n{dest}")

    def _build_busqueda_semantica(self):
        f = self._tab_bsem
        self._page_header(f, "Búsqueda Semántica",
                          "Encuentra artículos por similitud de significado · powered by FAISS + sentence-transformers",
                          "🔍")
        pad = tk.Frame(f, bg=CONTENT_BG); pad.pack(fill="both", expand=True, padx=24, pady=16)

        # ── Card: Construir índice ────────────────────────────────────────────
        card_idx = tk.Frame(pad, bg=CARD_BG, relief="solid", bd=1)
        card_idx.pack(fill="x", pady=(0, 12))
        hdr_idx = tk.Frame(card_idx, bg="#171C20"); hdr_idx.pack(fill="x")
        tk.Label(hdr_idx, text="  📦  Índice vectorial", bg="#171C20", fg=TXT_PRI,
                 font=("Segoe UI", 9, "bold")).pack(side="left", pady=4)
        self._lbl_bsem_estado = tk.Label(hdr_idx, text="Sin índice", bg="#171C20",
                                          fg="#D96B6B", font=("Segoe UI", 8))
        self._lbl_bsem_estado.pack(side="right", padx=10)

        body_idx = tk.Frame(card_idx, bg=CARD_BG, padx=12, pady=8)
        body_idx.pack(fill="x")
        tk.Label(body_idx,
                 text="Genera embeddings de todos los artículos del corpus y construye el índice FAISS.",
                 bg=CARD_BG, fg="#E8E5DF", font=("Segoe UI", 9), wraplength=580, justify="left"
                 ).pack(anchor="w", pady=(0, 6))
        bf_idx = tk.Frame(body_idx, bg=CARD_BG); bf_idx.pack(fill="x")
        self._btn_bsem_construir = ttk.Button(bf_idx, text="▶  Construir índice",
                                               style="P.TButton",
                                               command=self._bsem_construir)
        self._btn_bsem_construir.pack(side="left", padx=(0, 8))
        ttk.Button(bf_idx, text="💾  Guardar índice", style="S.TButton",
                   command=self._bsem_guardar).pack(side="left", padx=(0, 8))
        ttk.Button(bf_idx, text="📂  Cargar índice", style="S.TButton",
                   command=self._bsem_cargar).pack(side="left")
        self._lbl_bsem_n = tk.Label(bf_idx, text="", bg=CARD_BG, fg=VERDE,
                                     font=("Segoe UI", 8, "bold"))
        self._lbl_bsem_n.pack(side="right")

        # ── Card: Consulta ────────────────────────────────────────────────────
        card_q = tk.Frame(pad, bg=CARD_BG, relief="solid", bd=1)
        card_q.pack(fill="x", pady=(0, 12))
        hdr_q = tk.Frame(card_q, bg="#171C20"); hdr_q.pack(fill="x")
        tk.Label(hdr_q, text="  🔎  Consulta", bg="#171C20", fg=TXT_PRI,
                 font=("Segoe UI", 9, "bold")).pack(side="left", pady=4)

        body_q = tk.Frame(card_q, bg=CARD_BG, padx=12, pady=8)
        body_q.pack(fill="x")
        row_q = tk.Frame(body_q, bg=CARD_BG); row_q.pack(fill="x")
        tk.Label(row_q, text="Consulta:", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI", 9, "bold"), width=9).pack(side="left")
        self._var_bsem_q = tk.StringVar()
        self._ent_bsem_q = tk.Entry(row_q, textvariable=self._var_bsem_q,
                                     font=("Segoe UI", 10), relief="solid", bd=1)
        self._ent_bsem_q.pack(side="left", fill="x", expand=True, padx=(6, 8))
        self._ent_bsem_q.bind("<Return>", lambda e: self._bsem_buscar())

        tk.Label(row_q, text="K:", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        self._var_bsem_k = tk.IntVar(value=10)
        ttk.Spinbox(row_q, from_=1, to=50, textvariable=self._var_bsem_k,
                    width=4).pack(side="left", padx=(4, 8))
        self._btn_bsem_buscar = ttk.Button(row_q, text="Buscar", style="P.TButton",
                                            command=self._bsem_buscar)
        self._btn_bsem_buscar.pack(side="left")

        # ── Opciones de resultado ────────────────────────────────────────────
        opt_f = tk.Frame(body_q, bg=CARD_BG); opt_f.pack(fill="x", pady=(6, 0))
        ttk.Button(opt_f, text="💡  Explicar seleccionado", style="S.TButton",
                   command=self._bsem_explicar_seleccionado).pack(side="left", padx=(0, 8))
        ttk.Button(opt_f, text="📋  Explicar todos", style="S.TButton",
                   command=self._bsem_explicar_todos).pack(side="left")

        # ── Resultados ────────────────────────────────────────────────────────
        res_f = tk.Frame(pad, bg=CONTENT_BG); res_f.pack(fill="both", expand=True)

        # Treeview resultados
        tv_frame = tk.Frame(res_f, bg=CARD_BG, relief="solid", bd=1)
        tv_frame.pack(fill="both", expand=True)
        cols = ("rank", "articulo_id", "similitud", "titulo")
        self._tv_bsem = ttk.Treeview(tv_frame, columns=cols, show="headings", height=11)
        self._tv_bsem.heading("rank",        text="#")
        self._tv_bsem.heading("articulo_id", text="ID artículo")
        self._tv_bsem.heading("similitud",   text="Similitud")
        self._tv_bsem.heading("titulo",      text="Título / fragmento")
        self._tv_bsem.column("rank",        width=40,  anchor="center")
        self._tv_bsem.column("articulo_id", width=160, anchor="w")
        self._tv_bsem.column("similitud",   width=90,  anchor="center")
        self._tv_bsem.column("titulo",      width=460, anchor="w")
        vsb = ttk.Scrollbar(tv_frame, orient="vertical", command=self._tv_bsem.yview)
        self._tv_bsem.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tv_bsem.pack(fill="both", expand=True)
        self._bsem_resultados_raw = []  # lista de dicts con datos completos

        # Log
        log_bsem = tk.Frame(pad, bg="#12171B", bd=1, relief="solid")
        log_bsem.pack(fill="x", pady=(8, 0))
        log_hdr = tk.Frame(log_bsem, bg="#14202A"); log_hdr.pack(fill="x")
        tk.Label(log_hdr, text="  📋  Registro", bg="#14202A", fg="#B5B6B3",
                 font=("Segoe UI", 8, "bold")).pack(side="left", pady=4)
        self._log_bsem = scrolledtext.ScrolledText(log_bsem, height=4,
                                                    font=("Consolas", 8),
                                                    bg="#12171B", fg="#6EC69A",
                                                    relief="flat", state="disabled")
        self._log_bsem.pack(fill="x", padx=1, pady=(0, 1))

        # Estado interno
        self._bsem_indice = None  # instancia IndiceSemantico

    def _bsem_explicar_seleccionado(self):
        sel = self._tv_bsem.selection()
        if not sel:
            messagebox.showinfo("Sin selección", "Selecciona un resultado primero.")
            return
        idx = self._tv_bsem.index(sel[0])
        if idx >= len(self._bsem_resultados_raw):
            return
        resultado = self._bsem_resultados_raw[idx]
        query = self._var_bsem_q.get().strip()
        self._bsem_mostrar_explicacion(query, [resultado])

    def _bsem_explicar_todos(self):
        if not self._bsem_resultados_raw:
            messagebox.showwarning("Sin resultados", "Realiza una búsqueda primero.")
            return
        query = self._var_bsem_q.get().strip()
        self._bsem_mostrar_explicacion(query, self._bsem_resultados_raw)

    def _bsem_mostrar_explicacion(self, query: str, resultados: list):
        from core.explainer import explicar_lote, resumir_busqueda
        explicados = explicar_lote(query, resultados)
        resumen    = resumir_busqueda(query, explicados)

        win = tk.Toplevel(self)
        win.title(f"Explicación de resultados: '{query}'")
        win.geometry("780x540")
        win.configure(bg=CONTENT_BG)

        tk.Label(win, text="Síntesis de la búsqueda", bg=CONTENT_BG,
                 fg="#E8E5DF", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16, pady=(12, 4))
        lbl_res = tk.Label(win, text=resumen, bg=CONTENT_BG, fg="#B5B6B3",
                           font=("Segoe UI", 9), wraplength=740, justify="left")
        lbl_res.pack(anchor="w", padx=16, pady=(0, 10))

        txt = scrolledtext.ScrolledText(win, font=("Consolas", 9),
                                         bg="#171C20", fg="#E8E5DF",
                                         relief="flat", padx=10, pady=8)
        txt.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        for i, exp in enumerate(explicados, 1):
            e = exp.get("explicacion", {})
            proc = e.get("procedencia", {})
            txt.insert("end", f"── Resultado {i}: {proc.get('titulo','')[:60]} ──\n", "titulo")
            txt.insert("end", f"  {e.get('resumen_explicacion','')}\n")
            if e.get("terminos_relevantes"):
                tops = ", ".join(t["termino"] for t in e["terminos_relevantes"][:5])
                txt.insert("end", f"  Términos clave: {tops}\n")
            if e.get("fragmento_relevante"):
                txt.insert("end", f"  Fragmento: «{e['fragmento_relevante'][:120]}»\n")
            txt.insert("end", "\n")

        txt.tag_configure("titulo", foreground="#6CA8E8", font=("Consolas", 9, "bold"))
        txt.config(state="disabled")

    def _bsem_log(self, msg: str):
        def _do():
            self._log_bsem.config(state="normal")
            self._log_bsem.insert("end", msg + "\n")
            self._log_bsem.see("end")
            self._log_bsem.config(state="disabled")
        self.after(0, _do)

    def _bsem_construir(self):
        """Genera embeddings de todos los artículos y construye el índice FAISS."""
        try:
            from core.busqueda_semantica import IndiceSemantico, faiss_disponible
            from core.embeddings_local import (
                generar_embeddings,
                sentence_transformers_disponible,
            )
        except ImportError as e:
            messagebox.showerror("Módulo no disponible", str(e)); return

        if not sentence_transformers_disponible():
            messagebox.showerror("sentence-transformers no instalado",
                                 "Ejecuta: pip install sentence-transformers"); return
        if not faiss_disponible():
            messagebox.showerror("faiss-cpu no instalado",
                                 "Ejecuta: pip install faiss-cpu"); return

        # Recopilar textos desde df_articulos o archivos OCR
        textos, ids = [], []
        if ST.df_articulos is not None and not ST.df_articulos.empty:
            for i, row in ST.df_articulos.iterrows():
                t = str(row.get("texto", row.get("contenido", "")))
                if t and t != "nan" and len(t.strip()) > 10:
                    textos.append(t[:2000])   # truncar a 2000 chars para velocidad
                    ids.append(str(row.get("id", row.get("titulo", f"art_{i}"))))
        elif ST.out_dir:
            txt_dir = ST.out_dir / "03_ocr"
            if txt_dir.exists():
                for tf in sorted(txt_dir.rglob("*.txt")):
                    t = tf.read_text("utf-8", errors="replace")
                    if len(t.strip()) > 10:
                        textos.append(t[:2000])
                        ids.append(tf.stem)

        if not textos:
            messagebox.showwarning("Sin textos",
                "No hay textos disponibles. Ejecuta el OCR primero."); return

        self._btn_bsem_construir.config(state="disabled")
        self._bsem_log(f"Construyendo índice para {len(textos)} artículos…")

        def _worker():
            try:
                self.after(0, lambda: self._bsem_log("  Generando embeddings…"))
                embs = generar_embeddings(textos, mostrar_progreso=False)
                self.after(0, lambda: self._bsem_log(f"  Embeddings: {embs.shape}"))

                indice = IndiceSemantico(dimension=embs.shape[1])
                indice.construir(embs, ids)
                self._bsem_indice = indice

                self.after(0, lambda: self._lbl_bsem_estado.config(
                    text=f"✓ {indice.n_articulos} artículos indexados", fg=VERDE))
                self.after(0, lambda: self._lbl_bsem_n.config(
                    text=f"{indice.n_articulos} artículos"))
                self.after(0, lambda: self._bsem_log(
                    f"✅ Índice listo · {indice.n_articulos} artículos"))
            except Exception as exc:
                self.after(0, lambda err=str(exc): self._bsem_log(f"⚠️ Error: {err}"))
            finally:
                self.after(0, lambda: self._btn_bsem_construir.config(state="normal"))

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def _bsem_buscar(self):
        """Busca artículos similares a la consulta. Si no hay índice FAISS, usa búsqueda léxica."""
        consulta = self._var_bsem_q.get().strip()
        if not consulta:
            return

        # Fallback léxico si no hay índice semántico
        if self._bsem_indice is None or not getattr(self._bsem_indice, "construido", False):
            self._bsem_buscar_lexico(consulta)
            return

        k = max(1, min(self._var_bsem_k.get(), self._bsem_indice.n_articulos))

        try:
            from core.embeddings_local import generar_embeddings
        except ImportError as e:
            messagebox.showerror("Módulo no disponible", str(e)); return

        self._btn_bsem_buscar.config(state="disabled")

        def _worker():
            try:
                embs = generar_embeddings([consulta])
                resultados = self._bsem_indice.buscar(embs[0], k=k)

                # Enriquecer con título si está disponible
                titulos = {}
                if ST.df_articulos is not None and not ST.df_articulos.empty:
                    for _, row in ST.df_articulos.iterrows():
                        aid = str(row.get("id", row.get("titulo", "")))
                        titulos[aid] = str(row.get("titulo", aid))

                def _actualizar():
                    for item in self._tv_bsem.get_children():
                        self._tv_bsem.delete(item)
                    for r in resultados:
                        aid = r["articulo_id"]
                        self._tv_bsem.insert("", "end", values=(
                            r["rank"],
                            aid,
                            f"{r['similitud']:.3f}",
                            titulos.get(aid, aid),
                        ))
                    self._bsem_log(
                        f"🔍 '{consulta[:60]}' → {len(resultados)} resultados")

                self.after(0, _actualizar)
            except Exception as exc:
                self.after(0, lambda err=str(exc): self._bsem_log(f"⚠️ Error: {err}"))
            finally:
                self.after(0, lambda: self._btn_bsem_buscar.config(state="normal"))

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def _bsem_buscar_lexico(self, consulta: str):
        """
        Búsqueda léxica de fallback — no requiere FAISS.
        Busca la consulta en los TXT del corpus con coincidencias exactas e inexactas.
        Muestra resultados en la tabla de búsqueda semántica.
        """
        corpus_txt = getattr(ST, "corpus_txt", None) or []
        corpus_meta = getattr(ST, "corpus_meta", None)
        if corpus_meta is None:
            corpus_meta = {}

        if not corpus_txt:
            self._bsem_log("⚠ Sin corpus cargado. Ejecuta primero la extracción OCR.")
            return

        self._bsem_log(f"🔍 Búsqueda léxica (sin índice FAISS): '{consulta}'")
        k = self._var_bsem_k.get() if hasattr(self, "_var_bsem_k") else 10

        def _worker():
            from core.servicios_entidades import buscar_lexico
            resultados = buscar_lexico(corpus_txt, consulta, k, corpus_meta)

            def _mostrar():
                for item in self._tv_bsem.get_children():
                    self._tv_bsem.delete(item)
                for r in resultados[:k]:
                    self._tv_bsem.insert("", "end", values=(
                        r["rank"], r["articulo_id"],
                        f"{r['similitud']:.3f}", r["titulo"] or r["articulo_id"]))
                self._bsem_log(
                    f"✅ {len(resultados[:k])} resultados léxicos "
                    f"(construye el índice FAISS para búsqueda semántica)")
            self.after(0, _mostrar)

        threading.Thread(target=_worker, daemon=True).start()

    def _bsem_guardar(self):
        """Guarda el índice FAISS en disco."""
        if self._bsem_indice is None or not self._bsem_indice.construido:
            messagebox.showwarning("Sin índice", "Construye el índice primero."); return
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            defaultextension="",
            filetypes=[("Índice FAISS", "*.faiss"), ("Todos", "*.*")],
            initialfile="indice_semantico",
            title="Guardar índice semántico")
        if not dest:
            return
        # Quitar extensión si el usuario la puso manualmente
        ruta_base = dest.replace(".faiss", "")
        try:
            self._bsem_indice.guardar(ruta_base)
            messagebox.showinfo("Guardado",
                f"✅ Índice guardado:\n  {ruta_base}.faiss\n  {ruta_base}.ids.json")
            self._bsem_log(f"💾 Índice guardado en: {ruta_base}")
        except Exception as e:
            messagebox.showerror("Error al guardar", str(e))

    def _bsem_cargar(self):
        """Carga un índice FAISS desde disco."""
        try:
            from core.busqueda_semantica import IndiceSemantico
        except ImportError as e:
            messagebox.showerror("Módulo no disponible", str(e)); return
        from tkinter import filedialog
        src = filedialog.askopenfilename(
            filetypes=[("Índice FAISS", "*.faiss"), ("Todos", "*.*")],
            title="Abrir índice semántico")
        if not src:
            return
        ruta_base = src.replace(".faiss", "")
        try:
            indice = IndiceSemantico()
            ok = indice.cargar(ruta_base)
            if not ok:
                messagebox.showerror("Error", "No se pudo cargar el índice."); return
            self._bsem_indice = indice
            self._lbl_bsem_estado.config(
                text=f"✓ {indice.n_articulos} artículos (cargado)", fg=VERDE)
            self._lbl_bsem_n.config(text=f"{indice.n_articulos} artículos")
            self._bsem_log(f"📂 Índice cargado: {indice.n_articulos} artículos")
        except Exception as e:
            messagebox.showerror("Error al cargar", str(e))

    def _build_anot(self):
        self._page_header(self._tab_anot, "Anotación Semántica",
                          "Revisa y corrige entidades detectadas automáticamente · historial de cambios", "✍️")
        pad = tk.Frame(self._tab_anot, bg=CONTENT_BG, padx=16, pady=8)
        pad.pack(fill="both", expand=True)

        # ── Controles ──
        bf = tk.Frame(pad, bg=CONTENT_BG); bf.pack(fill="x", pady=(0, 8))
        ttk.Button(bf, text="📥  Importar NER automático", style="P.TButton",
                   command=self._anot_importar_ner).pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="⏳  Ver pendientes", style="S.TButton",
                   command=self._anot_ver_pendientes).pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="💾  Exportar JSON-LD", style="S.TButton",
                   command=self._anot_exportar).pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="📊  Estadísticas", style="S.TButton",
                   command=self._anot_stats).pack(side="left")
        ttk.Button(bf, text="📓 Nota", style="S.TButton",
                   command=lambda: self._bitacora_nueva_nota("anot")).pack(side="right")
        self._lbl_anot_ok = tk.Label(pad, text="Sin anotaciones cargadas",
                                      bg=CONTENT_BG, fg=GRIS2, font=("Segoe UI", 9))
        self._lbl_anot_ok.pack(anchor="w", pady=(0, 6))

        # ── Filtros ──
        ff = tk.Frame(pad, bg=CONTENT_BG); ff.pack(fill="x", pady=(0, 6))
        tk.Label(ff, text="Categoría:", bg=CONTENT_BG, fg=GRIS2,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self._var_anot_cat = tk.StringVar(value="Todas")
        self._cb_anot_cat = ttk.Combobox(ff, textvariable=self._var_anot_cat,
                                          values=["Todas","PER","LOC","ORG","OBRA","EVE","CARGO"],
                                          state="readonly", width=10)
        self._cb_anot_cat.pack(side="left", padx=(0, 12))
        tk.Label(ff, text="Estado:", bg=CONTENT_BG, fg=GRIS2,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self._var_anot_estado = tk.StringVar(value="Todos")
        ttk.Combobox(ff, textvariable=self._var_anot_estado,
                     values=["Todos","auto","confirmada","corregida","rechazada","pendiente"],
                     state="readonly", width=12).pack(side="left", padx=(0, 8))
        ttk.Button(ff, text="Filtrar", style="S.TButton",
                   command=self._anot_refrescar).pack(side="left")

        # ── Tabla ──
        cols = ("id", "art_id", "texto_norm", "categoria", "estado", "confianza")
        self._tv_anot = ttk.Treeview(pad, columns=cols, show="headings", height=12)
        heads = [("id","ID",50),("art_id","Artículo",120),("texto_norm","Entidad",180),
                 ("categoria","Categoría",90),("estado","Estado",100),("confianza","Conf.",70)]
        for cid, txt, w in heads:
            self._tv_anot.heading(cid, text=txt)
            self._tv_anot.column(cid, width=w, anchor="w")
        sv = ttk.Scrollbar(pad, orient="vertical", command=self._tv_anot.yview)
        self._tv_anot.configure(yscrollcommand=sv.set)
        self._tv_anot.pack(side="left", fill="both", expand=True)
        sv.pack(side="left", fill="y")

        # Tags de color por estado
        self._tv_anot.tag_configure("confirmada", foreground="#6EC69A")
        self._tv_anot.tag_configure("corregida",  foreground="#6CA8E8")
        self._tv_anot.tag_configure("rechazada",  foreground="#D96B6B")
        self._tv_anot.tag_configure("pendiente",  foreground="#E6A64C")
        self._tv_anot.tag_configure("auto",       foreground="#B5B6B3")

        # Botones de acción sobre selección
        ab = tk.Frame(pad, bg=CONTENT_BG); ab.pack(fill="x", pady=(6, 0))
        for label, estado in [("✅ Confirmar","confirmada"),("✏️ Corregir","corregida"),
                               ("❌ Rechazar","rechazada")]:
            ttk.Button(ab, text=label, style="S.TButton",
                       command=lambda e=estado: self._anot_cambiar_estado(e)
                       ).pack(side="left", padx=(0, 8))
        ttk.Button(ab, text="🕐 Ver historial", style="S.TButton",
                   command=self._anot_ver_historial).pack(side="left")

        self._anot_gestor = None
        self._anot_db_ruta = None

    def _anot_gestor_activo(self):
        """Gestor de anotaciones del proyecto ABIERTO AHORA.

        Antes se cacheaba el primero y nunca se renovaba: al abrir otro
        proyecto, las anotaciones seguían escribiéndose en la base del
        anterior (o en la global, si la pestaña se abrió sin proyecto).
        """
        from core.annotation_engine import GestorAnotaciones, ruta_anotaciones
        db = ruta_anotaciones(getattr(ST, "ruta_db", "") or None)
        if self._anot_gestor is None or self._anot_db_ruta != str(db):
            db.parent.mkdir(parents=True, exist_ok=True)
            self._anot_db_ruta = str(db)
            self._anot_gestor = GestorAnotaciones(db)
        return self._anot_gestor

    def _anot_importar_ner(self):
        ner = getattr(ST, "indice_ner_global", {})
        if not ner:
            messagebox.showwarning("Sin NER", "Ejecuta el análisis NER primero."); return

        # ST.indice_ner_global tiene forma {cat: {entidad: [art_ids]}}
        # importar_desde_ner espera         {art_id: {cat: [{texto, inicio, fin, confianza}]}}
        # Convertir antes de pasar.
        ner_por_art: dict = {}
        for cat, entidades in ner.items():
            for entidad, art_ids in entidades.items():
                for art_id in (art_ids if isinstance(art_ids, list) else [art_ids]):
                    ner_por_art.setdefault(art_id, {}).setdefault(cat, []).append({
                        "texto": entidad,
                        "inicio": 0,
                        "fin": len(str(entidad)),
                        "confianza": 0.9,
                    })

        g = self._anot_gestor_activo()
        n = g.importar_desde_ner(ner_por_art, reemplazar=True)
        self._lbl_anot_ok.config(text=f"✅ {n} anotaciones importadas")
        self._anot_refrescar()

    def _anot_refrescar(self):
        g = self._anot_gestor_activo()
        cat    = self._var_anot_cat.get()
        estado = self._var_anot_estado.get()
        rows = g.listar(categoria=None if cat == "Todas" else cat,
                        estado=None if estado == "Todos" else estado)

        for row in self._tv_anot.get_children():
            self._tv_anot.delete(row)
        for r in rows:
            self._tv_anot.insert("", "end", tags=(r["estado"],), values=(
                r["id"], r["art_id"], r["texto_norm"],
                r["categoria"], r["estado"], f"{r['confianza']:.2f}"))
        stats = self._anot_gestor_activo().estadisticas()
        self._lbl_anot_ok.config(
            text=f"{stats['total']} anotaciones  ·  "
                 f"confirmadas: {stats['por_estado'].get('confirmada',0)}  "
                 f"pendientes: {stats['por_estado'].get('auto',0)}")

    def _anot_cambiar_estado(self, nuevo_estado: str):
        sel = self._tv_anot.selection()
        if not sel:
            messagebox.showinfo("Sin selección", "Selecciona una anotación."); return
        g = self._anot_gestor_activo()
        for iid in sel:
            vals = self._tv_anot.item(iid)["values"]
            g.actualizar(int(vals[0]), {"estado": nuevo_estado}, razon="revisión manual")
        self._anot_refrescar()

    def _anot_ver_historial(self):
        sel = self._tv_anot.selection()
        if not sel:
            messagebox.showinfo("Sin selección", "Selecciona una anotación."); return
        vals   = self._tv_anot.item(sel[0])["values"]
        anot_id = int(vals[0])
        hist   = self._anot_gestor_activo().historial(anot_id)
        win = tk.Toplevel(self)
        win.title(f"Historial — anotación {anot_id}")
        win.geometry("580x300")
        win.configure(bg=CONTENT_BG)
        txt = scrolledtext.ScrolledText(win, font=("Consolas", 9),
                                         bg="#171C20", fg="#E8E5DF", relief="flat")
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        if not hist:
            txt.insert("end", "Sin cambios registrados.")
        for h in hist:
            txt.insert("end",
                f"{h['ts']}  [{h['campo']}]  {h['valor_ant']} → {h['valor_nuevo']}"
                f"  ({h['razon']})\n")
        txt.config(state="disabled")

    def _anot_ver_pendientes(self):
        g = self._anot_gestor_activo()
        pend = g.pendientes()
        self._var_anot_estado.set("auto")
        self._anot_refrescar()
        messagebox.showinfo("Pendientes", f"{len(pend)} anotaciones sin revisar.")

    def _anot_exportar(self):
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON-LD", "*.json"), ("Todos", "*.*")],
            initialfile="anotaciones_bashkar.json")
        if not dest: return
        n = self._anot_gestor_activo().exportar_json(dest, solo_confirmadas=False)
        messagebox.showinfo("Exportado", f"{n} anotaciones exportadas a:\n{dest}")

    def _anot_stats(self):
        stats = self._anot_gestor_activo().estadisticas()
        msg = f"Total: {stats['total']}\n\nPor estado:\n"
        for k, v in stats.get("por_estado", {}).items():
            msg += f"  {k}: {v}\n"
        msg += "\nPor categoría:\n"
        for k, v in stats.get("por_categoria", {}).items():
            msg += f"  {k}: {v}\n"
        messagebox.showinfo("Estadísticas de anotación", msg)

    def _build_red(self):
        pad = tk.Frame(self._tab_red, bg=CONTENT_BG, padx=16, pady=12)
        pad.pack(fill="both", expand=True)
        tk.Label(pad, text="Redes de co-ocurrencia", bg=CONTENT_BG,
                 fg="#E8E5DF", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(pad, text="Construye un grafo de entidades que co-ocurren en los mismos artículos.",
                 bg=CONTENT_BG, fg=GRIS2, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 10))

        # ── Controles ────────────────────────────────────────────────────────
        ctrl = tk.Frame(pad, bg=CONTENT_BG)
        ctrl.pack(fill="x", pady=(0, 8))

        # Categorías
        tk.Label(ctrl, text="Categorías:", bg=CONTENT_BG, fg=GRIS2,
                 font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", padx=(0, 4))
        self._var_red_cats = {}
        cats_frame = tk.Frame(ctrl, bg=CONTENT_BG)
        cats_frame.grid(row=0, column=1, sticky="w")
        cat_labels = {
            "personas": "Personas",
            "lugares": "Lugares",
            "organizaciones": "Organizaciones",
            "obras_publicaciones": "Obras",
            "eventos_historicos": "Eventos",
        }
        for cat, lbl in cat_labels.items():
            v = tk.BooleanVar(value=True)
            self._var_red_cats[cat] = v
            ttk.Checkbutton(cats_frame, text=lbl, variable=v).pack(side="left", padx=4)

        # Peso mínimo
        tk.Label(ctrl, text="Co-ocurrencias mínimas:", bg=CONTENT_BG, fg=GRIS2,
                 font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", padx=(0, 4), pady=(6,0))
        self._var_red_peso = tk.IntVar(value=2)
        ttk.Spinbox(ctrl, from_=1, to=20, textvariable=self._var_red_peso,
                    width=5).grid(row=1, column=1, sticky="w", pady=(6,0))

        # Botones
        bf = tk.Frame(pad, bg=CONTENT_BG)
        bf.pack(fill="x", pady=(0, 8))
        self._btn_red_construir = ttk.Button(bf, text="▶  Construir red",
                                              style="P.TButton",
                                              command=self._red_construir)
        self._btn_red_construir.pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="🔬  Métricas avanzadas",
                   style="S.TButton",
                   command=self._red_metricas_avanzadas).pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="📅  Evolución temporal",
                   style="S.TButton",
                   command=self._red_evolucion_temporal).pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="🌐  Ver en navegador",
                   style="S.TButton",
                   command=self._red_abrir_html).pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="📤  Exportar Gephi",
                   style="S.TButton",
                   command=self._red_exportar_gephi).pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="💾  CSV métricas",
                   style="S.TButton",
                   command=self._red_exportar_csv).pack(side="left", padx=(0, 8))
        self._lbl_red_ok = tk.Label(pad, text="", bg=CONTENT_BG, fg=VERDE,
                                     font=("Segoe UI", 9, "bold"))
        self._lbl_red_ok.pack(anchor="w", pady=(0, 6))

        # ── Notebook con pestañas de análisis ────────────────────────────────
        nb_red = ttk.Notebook(pad)
        nb_red.pack(fill="both", expand=True, pady=(4, 0))

        # ── Pestaña: Métricas globales + top centralidad ──────────────────────
        frm_met = tk.Frame(nb_red, bg=CONTENT_BG)
        nb_red.add(frm_met, text="  Métricas  ")

        met_frame = tk.Frame(frm_met, bg=CONTENT_BG)
        met_frame.pack(fill="x", pady=(6, 4))
        cols_met = ("metrica", "valor")
        self._tv_red_met = ttk.Treeview(met_frame, columns=cols_met,
                                         show="headings", height=7)
        self._tv_red_met.heading("metrica", text="Métrica")
        self._tv_red_met.heading("valor",   text="Valor")
        self._tv_red_met.column("metrica", width=240, anchor="w")
        self._tv_red_met.column("valor",   width=160, anchor="e")
        self._tv_red_met.pack(fill="x", padx=6)

        tk.Label(frm_met, text="Top nodos por centralidad de grado",
                 bg=CONTENT_BG, fg=GRIS2, font=("Segoe UI", 9, "bold")).pack(
                 anchor="w", padx=6, pady=(6, 2))
        cols_top = ("rango", "entidad", "categoria", "grado")
        self._tv_red_top = ttk.Treeview(frm_met, columns=cols_top,
                                         show="headings", height=8)
        self._tv_red_top.heading("rango",    text="#")
        self._tv_red_top.heading("entidad",  text="Entidad")
        self._tv_red_top.heading("categoria",text="Categoría")
        self._tv_red_top.heading("grado",    text="Centralidad grado")
        self._tv_red_top.column("rango",     width=35,  anchor="center")
        self._tv_red_top.column("entidad",   width=220, anchor="w")
        self._tv_red_top.column("categoria", width=140, anchor="w")
        self._tv_red_top.column("grado",     width=130, anchor="e")
        sv0 = ttk.Scrollbar(frm_met, orient="vertical", command=self._tv_red_top.yview)
        self._tv_red_top.configure(yscrollcommand=sv0.set)
        sv0.pack(side="right", fill="y", padx=(0, 6))
        self._tv_red_top.pack(fill="both", expand=True, padx=6)

        # ── Pestaña: Métricas avanzadas (betweenness, PageRank, closeness) ────
        frm_av = tk.Frame(nb_red, bg=CONTENT_BG)
        nb_red.add(frm_av, text="  Centralidad avanzada  ")

        bav = tk.Frame(frm_av, bg=CONTENT_BG)
        bav.pack(fill="x", padx=6, pady=(6, 4))
        tk.Label(bav, text="Tipo de centralidad:", bg=CONTENT_BG, fg=GRIS2,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self._var_red_cent_tipo = tk.StringVar(value="betweenness")
        for val, lbl in [("betweenness","Betweenness (puentes)"),
                          ("pagerank","PageRank (influencia)"),
                          ("closeness","Closeness (proximidad)")]:
            ttk.Radiobutton(bav, text=lbl, variable=self._var_red_cent_tipo,
                            value=val,
                            command=self._red_refrescar_avanzadas).pack(side="left", padx=4)

        cols_av = ("rango", "entidad", "categoria", "valor")
        self._tv_red_av = ttk.Treeview(frm_av, columns=cols_av,
                                        show="headings", height=16)
        self._tv_red_av.heading("rango",    text="#")
        self._tv_red_av.heading("entidad",  text="Entidad")
        self._tv_red_av.heading("categoria",text="Categoría")
        self._tv_red_av.heading("valor",    text="Valor")
        self._tv_red_av.column("rango",     width=35,  anchor="center")
        self._tv_red_av.column("entidad",   width=230, anchor="w")
        self._tv_red_av.column("categoria", width=140, anchor="w")
        self._tv_red_av.column("valor",     width=120, anchor="e")
        sv1 = ttk.Scrollbar(frm_av, orient="vertical", command=self._tv_red_av.yview)
        self._tv_red_av.configure(yscrollcommand=sv1.set)
        sv1.pack(side="right", fill="y", padx=(0, 6))
        self._tv_red_av.pack(fill="both", expand=True, padx=6)
        self._red_metricas_av_cache: dict = {}

        # ── Pestaña: Comunidades ──────────────────────────────────────────────
        frm_com = tk.Frame(nb_red, bg=CONTENT_BG)
        nb_red.add(frm_com, text="  Comunidades  ")

        tk.Label(frm_com,
                 text="Comunidades detectadas por algoritmo Louvain\n"
                      "(grupos de entidades fuertemente conectadas entre sí)",
                 bg=CONTENT_BG, fg=GRIS2, font=("Segoe UI", 8)).pack(
                 anchor="w", padx=6, pady=(6, 4))

        split_com = tk.Frame(frm_com, bg=CONTENT_BG)
        split_com.pack(fill="both", expand=True)

        # Lista de comunidades (izquierda)
        izq_com = tk.Frame(split_com, bg=CONTENT_BG, width=180)
        izq_com.pack(side="left", fill="y", padx=(6, 0))
        izq_com.pack_propagate(False)
        tk.Label(izq_com, text="Comunidades", bg=CONTENT_BG, fg=GRIS2,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self._lb_red_comunidades = tk.Listbox(
            izq_com, bg=CARD_BG, fg=TXT_SEC, selectbackground=AB_SEL,
            font=("Segoe UI", 9), relief="flat", activestyle="none")
        self._lb_red_comunidades.pack(fill="both", expand=True)
        self._lb_red_comunidades.bind("<<ListboxSelect>>",
                                      self._red_mostrar_comunidad)

        # Miembros de la comunidad (derecha)
        der_com = tk.Frame(split_com, bg=CONTENT_BG)
        der_com.pack(side="left", fill="both", expand=True, padx=6)
        tk.Label(der_com, text="Miembros", bg=CONTENT_BG, fg=GRIS2,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        cols_com = ("entidad", "categoria", "grado")
        self._tv_red_miembros = ttk.Treeview(der_com, columns=cols_com,
                                              show="headings", height=18)
        self._tv_red_miembros.heading("entidad",  text="Entidad")
        self._tv_red_miembros.heading("categoria",text="Categoría")
        self._tv_red_miembros.heading("grado",    text="Grado")
        self._tv_red_miembros.column("entidad",   width=200, anchor="w")
        self._tv_red_miembros.column("categoria", width=130, anchor="w")
        self._tv_red_miembros.column("grado",     width=70,  anchor="e")
        sv2 = ttk.Scrollbar(der_com, orient="vertical",
                             command=self._tv_red_miembros.yview)
        self._tv_red_miembros.configure(yscrollcommand=sv2.set)
        sv2.pack(side="right", fill="y")
        self._tv_red_miembros.pack(fill="both", expand=True)
        self._red_comunidades_cache: list = []

        # ── Pestaña: Evolución temporal ───────────────────────────────────────
        frm_evo = tk.Frame(nb_red, bg=CONTENT_BG)
        nb_red.add(frm_evo, text="  Evolución temporal  ")

        tk.Label(frm_evo,
                 text="Cómo cambia la red entre números del corpus "
                      "(requiere haber procesado varios números).",
                 bg=CONTENT_BG, fg=GRIS2, font=("Segoe UI", 8)).pack(
                 anchor="w", padx=6, pady=(6, 4))

        bevo = tk.Frame(frm_evo, bg=CONTENT_BG)
        bevo.pack(fill="x", padx=6, pady=(0, 4))
        ttk.Button(bevo, text="▶  Calcular evolución", style="P.TButton",
                   command=self._red_calcular_evolucion).pack(side="left")
        ttk.Button(bevo, text="📊  Graficar", style="S.TButton",
                   command=self._red_graficar_evolucion).pack(side="left", padx=(8, 0))
        ttk.Button(bevo, text="💾  CSV", style="S.TButton",
                   command=self._red_evolucion_csv).pack(side="left", padx=(8, 0))

        cols_evo = ("numero", "nodos", "aristas", "densidad", "top_nodo")
        self._tv_red_evo = ttk.Treeview(frm_evo, columns=cols_evo,
                                         show="headings", height=16)
        for cid, txt, w in [("numero","Número",150),("nodos","Nodos",70),
                              ("aristas","Aristas",70),("densidad","Densidad",80),
                              ("top_nodo","Nodo central",200)]:
            self._tv_red_evo.heading(cid, text=txt)
            self._tv_red_evo.column(cid, width=w, anchor="w")
        sv3 = ttk.Scrollbar(frm_evo, orient="vertical",
                             command=self._tv_red_evo.yview)
        self._tv_red_evo.configure(yscrollcommand=sv3.set)
        sv3.pack(side="right", fill="y", padx=(0, 6))
        self._tv_red_evo.pack(fill="both", expand=True, padx=6)
        self._red_evolucion_cache: list = []

        # ── Pestaña: Grafo canónico (entidades fundidas + relaciones) ─────────
        frm_can = tk.Frame(nb_red, bg=CONTENT_BG)
        nb_red.add(frm_can, text="  Grafo canónico  ")

        tk.Label(frm_can,
                 text="Funde las menciones NER en entidades canónicas (id estable) y\n"
                      "modela tripletas sujeto–predicado–objeto con procedencia y confianza.\n"
                      "Capa de grafo de conocimiento en el SQLite del proyecto.",
                 bg=CONTENT_BG, fg=GRIS2, font=("Segoe UI", 8), justify="left").pack(
                 anchor="w", padx=6, pady=(6, 4))

        bcan = tk.Frame(frm_can, bg=CONTENT_BG)
        bcan.pack(fill="x", padx=6, pady=(0, 4))
        self._btn_can_fundir = ttk.Button(
            bcan, text="▶  Fundir menciones → entidades canónicas",
            style="P.TButton", command=self._can_fundir)
        self._btn_can_fundir.pack(side="left")
        ttk.Button(bcan, text="🔗  Generar tripletas «mencionado_en»",
                   style="S.TButton",
                   command=self._can_generar_menciones).pack(side="left", padx=(8, 0))
        ttk.Button(bcan, text="💾  GEXF",
                   style="S.TButton",
                   command=self._can_exportar_gexf).pack(side="left", padx=(8, 0))
        ttk.Button(bcan, text="🌐  RDF/Turtle",
                   style="S.TButton",
                   command=self._can_exportar_rdf).pack(side="left", padx=(8, 0))

        # segunda fila: exploradores + editor de relaciones
        bcan2 = tk.Frame(frm_can, bg=CONTENT_BG)
        bcan2.pack(fill="x", padx=6, pady=(0, 4))
        ttk.Button(bcan2, text="🗺  Mapa de lugares",
                   style="S.TButton",
                   command=self._can_mapa_lugares).pack(side="left")
        ttk.Button(bcan2, text="📅  Timeline de números",
                   style="S.TButton",
                   command=self._can_timeline).pack(side="left", padx=(8, 0))
        ttk.Button(bcan2, text="📖  Vocabulario controlado",
                   style="S.TButton",
                   command=self._can_vocabulario).pack(side="left", padx=(8, 0))
        ttk.Button(bcan2, text="➕  Añadir relación…",
                   style="S.TButton",
                   command=self._can_editor_relacion).pack(side="left", padx=(8, 0))

        # tercera fila: portabilidad (OKF)
        bcan3 = tk.Frame(frm_can, bg=CONTENT_BG)
        bcan3.pack(fill="x", padx=6, pady=(0, 4))
        self._btn_can_okf = ttk.Button(
            bcan3, text="📦  Exportar bundle OKF…",
            style="S.TButton", command=self._can_exportar_okf)
        self._btn_can_okf.pack(side="left")

        self._lbl_can_ok = tk.Label(frm_can, text="", bg=CONTENT_BG, fg=VERDE,
                                     font=("Segoe UI", 9, "bold"))
        self._lbl_can_ok.pack(anchor="w", padx=6, pady=(2, 4))

        cols_can = ("id", "tipo", "nombre", "menciones", "wikidata", "fuente")
        self._tv_can = ttk.Treeview(frm_can, columns=cols_can,
                                    show="headings", height=16)
        for cid, txt, w, anc in [("id","id estable",200,"w"),("tipo","Tipo",90,"w"),
                                  ("nombre","Nombre",200,"w"),("menciones","Menc.",55,"e"),
                                  ("wikidata","Wikidata",90,"w"),("fuente","Fuente",90,"w")]:
            self._tv_can.heading(cid, text=txt)
            self._tv_can.column(cid, width=w, anchor=anc)
        svc = ttk.Scrollbar(frm_can, orient="vertical", command=self._tv_can.yview)
        self._tv_can.configure(yscrollcommand=svc.set)
        svc.pack(side="right", fill="y", padx=(0, 6))
        self._tv_can.pack(fill="both", expand=True, padx=6)

        # ── Log ───────────────────────────────────────────────────────────────
        self._txt_red_log = scrolledtext.ScrolledText(
            pad, height=4, font=("Consolas", 8),
            bg="#12171B", fg="#B5B6B3", state="disabled", wrap="word")
        self._txt_red_log.pack(fill="x", pady=(6, 0))

        self._grafo_actual = None
        self._html_red_path = None

    def _red_log(self, msg: str):
        self._txt_red_log.config(state="normal")
        self._txt_red_log.insert("end", msg + "\n")
        self._txt_red_log.see("end")
        self._txt_red_log.config(state="disabled")

    def _can_repo(self):
        """Repositorio del proyecto activo, o None con aviso si no hay DB."""
        if not getattr(ST, "ruta_db", ""):
            messagebox.showwarning(
                "Sin proyecto",
                "Abre o guarda un proyecto con base de datos para usar el grafo canónico.")
            return None
        from datos.repositorio import Repositorio
        return Repositorio(ST.ruta_db)

    def _can_fundir(self):
        repo = self._can_repo()
        if repo is None:
            return
        self._btn_can_fundir.config(state="disabled")
        self._lbl_can_ok.config(text="Fundiendo menciones…")
        threading.Thread(target=self._worker_can_fundir,
                         args=(repo,), daemon=True).start()

    def _worker_can_fundir(self, repo):
        try:
            res = repo.fundir_menciones_en_canonicas(fuente="ner")
            cans = repo.listar_entidades_canonicas()
        except Exception as e:
            self.after(0, lambda err=e: messagebox.showerror("Error", str(err)))
            self.after(0, lambda: self._btn_can_fundir.config(state="normal"))
            return

        def _ui():
            self._btn_can_fundir.config(state="normal")
            self._can_poblar_tabla(cans)
            self._lbl_can_ok.config(
                text=f"✓ {res['canonicas']} entidades canónicas "
                     f"({res['menciones_vinculadas']} menciones fundidas)")
            self._red_log(f"[grafo] {res['canonicas']} canónicas, "
                          f"{res['menciones_vinculadas']} menciones vinculadas")
            self.toast("Menciones fundidas en entidades canónicas", "ok")
        self.after(0, _ui)

    def _can_poblar_tabla(self, cans):
        for row in self._tv_can.get_children():
            self._tv_can.delete(row)
        for c in cans:
            self._tv_can.insert("", "end", values=(
                c.get("id", ""), c.get("tipo", ""), c.get("nombre", ""),
                c.get("n_menciones", 0), c.get("wikidata_id") or "—",
                c.get("fuente", ""),
            ))

    def _can_generar_menciones(self):
        repo = self._can_repo()
        if repo is None:
            return
        threading.Thread(target=self._worker_can_menciones,
                         args=(repo,), daemon=True).start()

    def _worker_can_menciones(self, repo):
        try:
            filas = repo.menciones_canonicas_por_articulo()
            if not filas:
                self.after(0, lambda: messagebox.showinfo(
                    "Sin menciones",
                    "Funde primero las menciones en entidades canónicas."))
                return
            n = 0
            for cid, art in filas:
                repo.guardar_relacion(cid, "mencionado_en",
                                      destino_pagina=art, evidencia=art,
                                      fuente="ner")
                n += 1
        except Exception as e:
            self.after(0, lambda err=e: messagebox.showerror("Error", str(err)))
            return

        def _ui():
            self._lbl_can_ok.config(text=f"✓ {n} tripletas «mencionado_en» generadas")
            self._red_log(f"[grafo] {n} tripletas mencionado_en")
            self.toast(f"{n} tripletas generadas", "ok")
        self.after(0, _ui)

    def _can_exportar_gexf(self):
        repo = self._can_repo()
        if repo is None:
            return
        graf = repo.grafo_entidades()
        if not graf["nodos"]:
            messagebox.showinfo("Grafo vacío",
                                "Funde menciones y genera tripletas primero.")
            return
        dest = filedialog.asksaveasfilename(
            defaultextension=".gexf",
            filetypes=[("Graph Exchange XML", "*.gexf")],
            initialfile="grafo_canonico.gexf")
        if not dest:
            return
        try:
            self._can_escribir_gexf(graf, dest)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self._red_log(f"[grafo] GEXF exportado: {dest}")
        self.toast("Grafo canónico exportado (GEXF)", "ok")

    @staticmethod
    def _can_escribir_gexf(graf, ruta):
        """Escribe el grafo canónico a GEXF (Gephi). Ver core.exploradores."""
        from core.exploradores import exportar_gexf
        exportar_gexf(graf, ruta)

    def _can_exportar_rdf(self):
        repo = self._can_repo()
        if repo is None:
            return
        graf = repo.grafo_entidades()
        if not graf["nodos"]:
            messagebox.showinfo("Grafo vacío", "Funde menciones primero.")
            return
        dest = filedialog.asksaveasfilename(
            defaultextension=".ttl",
            filetypes=[("RDF Turtle", "*.ttl")], initialfile="grafo_canonico.ttl")
        if not dest:
            return
        from core.exploradores import exportar_rdf
        res = exportar_rdf(graf, dest)
        self._red_log(f"[grafo] RDF ({res['motor']}): {res['n_tripletas']} tripletas")
        self.toast(f"RDF exportado ({res['motor']})", "ok")

    def _can_exportar_okf(self):
        repo = self._can_repo()
        if repo is None:
            return
        dest = filedialog.askdirectory(title="Carpeta destino del bundle OKF")
        if not dest:
            return
        nombre = getattr(ST, "publicacion", "") or "Corpus"
        self._btn_can_okf.config(state="disabled")
        self._lbl_can_ok.config(text="Exportando bundle OKF…")
        threading.Thread(target=self._worker_can_okf,
                         args=(repo, dest, nombre), daemon=True).start()

    def _worker_can_okf(self, repo, dest, nombre):
        try:
            from core.okf_export_engine import exportar_proyecto_okf
            res = exportar_proyecto_okf(repo, dest, nombre_proyecto=nombre)
        except Exception as e:
            self.after(0, lambda err=e: messagebox.showerror("Error", str(err)))
            self.after(0, lambda: self._btn_can_okf.config(state="normal"))
            return

        def _ui():
            self._btn_can_okf.config(state="normal")
            self._lbl_can_ok.config(
                text=f"✓ Bundle OKF: {res['n_documentos']} documentos, "
                     f"{res['n_articulos']} artículos, {res['n_entidades']} entidades")
            self._red_log(f"[okf] bundle exportado en {res['carpeta']}")
            self.toast(f"Bundle OKF exportado ({res['n_articulos']} artículos)", "ok")
        self.after(0, _ui)

    def _can_mapa_lugares(self):
        repo = self._can_repo()
        if repo is None:
            return
        from core.exploradores import geocodificar_lugares, mapa_lugares_html
        cans = repo.listar_entidades_canonicas(tipo="lugar")
        lug = geocodificar_lugares(cans)
        if not lug:
            messagebox.showinfo(
                "Sin lugares",
                "No hay entidades tipo «lugar» georreferenciables.\n"
                "Funde menciones primero (los lugares se geocodifican con el "
                "gazetteer local de Colombia).")
            return
        dest = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML", "*.html")], initialfile="mapa_lugares.html")
        if not dest:
            return
        res = mapa_lugares_html(lug, dest)
        self._red_log(f"[mapa] {res['n']} lugares ({res['motor']})")
        self.toast(f"Mapa de {res['n']} lugares generado", "ok")
        try:
            import webbrowser
            webbrowser.open(Path(dest).as_uri())
        except Exception:
            pass

    def _can_timeline(self):
        repo = self._can_repo()
        if repo is None:
            return
        from collections import defaultdict
        arts = repo.listar_articulos()
        if not arts:
            messagebox.showinfo("Sin artículos", "El proyecto no tiene artículos.")
            return
        por_num = defaultdict(lambda: {"n": 0, "fecha": ""})
        for a in arts:
            num = a.get("numero") or "—"
            por_num[num]["n"] += 1
            if not por_num[num]["fecha"] and a.get("fecha_publicacion"):
                por_num[num]["fecha"] = a["fecha_publicacion"]
        numeros = [{"numero": k, "fecha": v["fecha"], "n_articulos": v["n"]}
                   for k, v in por_num.items()]
        dest = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML", "*.html")], initialfile="timeline_numeros.html")
        if not dest:
            return
        from core.exploradores import timeline_numeros_html
        res = timeline_numeros_html(numeros, dest)
        self._red_log(f"[timeline] {res['n']} números")
        self.toast(f"Timeline de {res['n']} números generada", "ok")
        try:
            import webbrowser
            webbrowser.open(Path(dest).as_uri())
        except Exception:
            pass

    def _can_vocabulario(self):
        from core import vocabulario_controlado as vc
        ruta_db = getattr(ST, "ruta_db", "") or None
        vocab = vc.construir_vocabulario(ruta_db_proyecto=ruta_db,
                                         incluir_entidades=bool(ruta_db))
        st = vc.estadisticas(vocab)
        dest = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("JSON", "*.json")],
            initialfile="vocabulario_controlado.csv")
        if not dest:
            return
        if dest.lower().endswith(".json"):
            n = vc.exportar_json(vocab, dest)
        else:
            n = vc.exportar_csv(vocab, dest)
        cats = ", ".join(f"{k}:{v}" for k, v in st["por_categoria"].items())
        self._red_log(f"[vocab] {n} términos ({cats})")
        self.toast(f"Vocabulario controlado: {n} términos exportados", "ok")

    def _can_editor_relacion(self):
        repo = self._can_repo()
        if repo is None:
            return
        cans = repo.listar_entidades_canonicas()
        if len(cans) < 2:
            messagebox.showinfo(
                "Pocas entidades",
                "Funde menciones primero: necesitas al menos 2 entidades "
                "canónicas para crear una relación.")
            return

        etiquetas = [f"{c['nombre']} [{c['tipo']}]" for c in cans]
        ids = [c["id"] for c in cans]

        win = tk.Toplevel(self)
        win.title("Añadir relación (tripleta)")
        win.configure(bg=CONTENT_BG)
        win.transient(self)
        win.grab_set()

        tk.Label(win, text="Crear una aserción sujeto — predicado — objeto",
                 bg=CONTENT_BG, fg="#E8E5DF",
                 font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=2,
                                                     sticky="w", padx=12, pady=(12, 8))

        tk.Label(win, text="Sujeto:", bg=CONTENT_BG, fg=GRIS2).grid(
            row=1, column=0, sticky="e", padx=8, pady=4)
        cb_suj = ttk.Combobox(win, values=etiquetas, state="readonly", width=38)
        cb_suj.grid(row=1, column=1, sticky="w", padx=8, pady=4); cb_suj.current(0)

        tk.Label(win, text="Predicado:", bg=CONTENT_BG, fg=GRIS2).grid(
            row=2, column=0, sticky="e", padx=8, pady=4)
        cb_pred = ttk.Combobox(win, width=38, values=[
            "colaboro_con", "dirigio", "publico_en", "aliado_de", "opositor_de",
            "ubicado_en", "miembro_de", "fundador_de", "co_aparece_con"])
        cb_pred.grid(row=2, column=1, sticky="w", padx=8, pady=4)
        cb_pred.set("colaboro_con")

        tk.Label(win, text="Objeto:", bg=CONTENT_BG, fg=GRIS2).grid(
            row=3, column=0, sticky="e", padx=8, pady=4)
        cb_obj = ttk.Combobox(win, values=etiquetas, state="readonly", width=38)
        cb_obj.grid(row=3, column=1, sticky="w", padx=8, pady=4)
        cb_obj.current(1 if len(ids) > 1 else 0)

        tk.Label(win, text="Confianza:", bg=CONTENT_BG, fg=GRIS2).grid(
            row=4, column=0, sticky="e", padx=8, pady=4)
        var_conf = tk.DoubleVar(value=1.0)
        ttk.Spinbox(win, from_=0.1, to=1.0, increment=0.1, textvariable=var_conf,
                    width=6).grid(row=4, column=1, sticky="w", padx=8, pady=4)

        def _guardar():
            i_s, i_o = cb_suj.current(), cb_obj.current()
            pred = (cb_pred.get() or "").strip()
            if i_s == i_o:
                messagebox.showwarning("Inválido",
                                       "Sujeto y objeto deben ser distintos.",
                                       parent=win)
                return
            if not pred:
                messagebox.showwarning("Inválido", "Indica un predicado.",
                                       parent=win)
                return
            repo.guardar_relacion(ids[i_s], pred, destino_id=ids[i_o],
                                  confianza=var_conf.get(), fuente="revision_manual")
            self._red_log(f"[grafo] relación manual: {ids[i_s]} {pred} {ids[i_o]}")
            self.toast("Relación añadida al grafo", "ok")
            win.destroy()

        bf = tk.Frame(win, bg=CONTENT_BG)
        bf.grid(row=5, column=0, columnspan=2, pady=12)
        ttk.Button(bf, text="Guardar", style="P.TButton",
                   command=_guardar).pack(side="left", padx=6)
        ttk.Button(bf, text="Cancelar", style="S.TButton",
                   command=win.destroy).pack(side="left", padx=6)

    def _red_construir(self):
        if not getattr(ST, "indice_ner_global", None) or not any(ST.indice_ner_global.values()):
            messagebox.showwarning("Sin datos",
                "Analiza el corpus en la pestaña Índice NER primero.")
            return
        cats_sel = [c for c, v in self._var_red_cats.items() if v.get()]
        if not cats_sel:
            messagebox.showwarning("Sin categorías", "Selecciona al menos una categoría.")
            return
        peso = self._var_red_peso.get()
        self._btn_red_construir.config(state="disabled")
        self._lbl_red_ok.config(text="Construyendo red…")
        threading.Thread(target=self._worker_red_construir,
                         args=(cats_sel, peso), daemon=True).start()

    def _worker_red_construir(self, cats_sel, peso_min):
        try:
            from core.network_engine import construir_grafo, metricas_red
        except ImportError as e:
            self.after(0, lambda err=str(e): messagebox.showerror("Error", err))
            self.after(0, lambda: self._btn_red_construir.config(state="normal"))
            return

        def log(m):
            self.after(0, lambda msg=m: self._red_log(msg))

        try:
            G = construir_grafo(
                ST.indice_ner_global,
                categorias=cats_sel,
                peso_minimo=peso_min,
                callback=log,
            )
            self._grafo_actual = G
            met = metricas_red(G)
            # Publicar en el estado: los exportadores (PPTX, reportes) las
            # buscaban en ST y no las encontraba nadie porque solo eran local.
            ST.metricas_red = met

            def _actualizar_ui():
                # Tabla métricas
                for row in self._tv_red_met.get_children():
                    self._tv_red_met.delete(row)
                pares = [
                    ("Nodos", met.get("nodos", 0)),
                    ("Aristas", met.get("aristas", 0)),
                    ("Densidad", met.get("densidad", "—")),
                    ("Componentes conexas", met.get("componentes_conexas", "—")),
                    ("Comunidades (Louvain)", met.get("comunidades_louvain", "N/A")),
                    ("Modularidad", met.get("modularidad", "—")),
                ]
                for m, v in pares:
                    self._tv_red_met.insert("", "end", values=(m, v))

                # Tabla top nodos
                for row in self._tv_red_top.get_children():
                    self._tv_red_top.delete(row)
                top = met.get("top_centralidad", [])
                for rk, (nodo, cent) in enumerate(top, 1):
                    cat = G.nodes[nodo].get("categoria", "") if G.has_node(nodo) else ""
                    self._tv_red_top.insert("", "end",
                                             values=(rk, nodo, cat, f"{cent:.4f}"))

                n = met.get("nodos", 0)
                a = met.get("aristas", 0)
                self._lbl_red_ok.config(text=f"✅ Red construida: {n} nodos, {a} aristas")
                self._btn_red_construir.config(state="normal")

            self.after(0, _actualizar_ui)

            # Auto-generar HTML
            self.after(0, self._red_generar_html)

        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._red_log(f"⚠ Error: {err}"))
            self.after(0, lambda: self._btn_red_construir.config(state="normal"))
            self.after(0, lambda: self._lbl_red_ok.config(text=f"⚠ Error: {err}"))

    def _red_generar_html(self):
        if not self._grafo_actual:
            return
        try:
            from pathlib import Path as _PPath

            from core.network_engine import exportar_pyvis
            ruta_html = _PPath.home() / "Documents" / "BashkarStation" / "redes" / "red_entidades.html"
            ruta_html.parent.mkdir(parents=True, exist_ok=True)
            exportar_pyvis(self._grafo_actual, ruta_html)
            self._html_red_path = ruta_html
            self._red_log(f"HTML generado: {ruta_html}")
        except ImportError:
            self._red_log("pyvis no instalado. Para visualización HTML: pip install pyvis>=0.3.2")
        except Exception as e:
            self._red_log(f"HTML no generado: {e}")

    def _red_abrir_html(self):
        if not self._html_red_path or not self._html_red_path.exists():
            messagebox.showinfo("Sin HTML", "Construye la red primero. El HTML se genera automáticamente.")
            return
        import webbrowser
        webbrowser.open(str(self._html_red_path))

    def _red_exportar_gephi(self):
        if not self._grafo_actual:
            messagebox.showwarning("Sin red", "Construye la red primero.")
            return
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            defaultextension=".gexf",
            filetypes=[("GEXF Gephi", "*.gexf"), ("Todos", "*.*")],
            initialfile="red_estampa.gexf",
            title="Exportar red para Gephi")
        if not dest:
            return
        try:
            from pathlib import Path as _PPath

            from core.network_engine import exportar_gephi
            exportar_gephi(self._grafo_actual, _PPath(dest))
            messagebox.showinfo("Exportado", f"✅ Red exportada a:\n{dest}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _red_metricas_avanzadas(self):
        """Calcula betweenness, PageRank y closeness en worker thread."""
        if not self._grafo_actual:
            messagebox.showwarning("Sin red", "Construye la red primero."); return
        self._lbl_red_ok.config(text="⏳ Calculando métricas avanzadas…")

        def _worker():
            from core.network_engine import metricas_avanzadas
            av = metricas_avanzadas(self._grafo_actual)
            self._red_metricas_av_cache = av
            # También actualiza comunidades
            coms = av.get("comunidades", [])
            self._red_comunidades_cache = coms
            self.after(0, lambda: self._red_refrescar_avanzadas())
            self.after(0, lambda: self._red_refrescar_comunidades(coms))
            n_coms = len(coms)
            self.after(0, lambda: self._lbl_red_ok.config(
                text=f"✅ Métricas avanzadas calculadas · {n_coms} comunidades"))

        threading.Thread(target=_worker, daemon=True).start()

    def _red_refrescar_avanzadas(self):
        """Puebla la tabla de centralidad avanzada según el radio seleccionado."""
        if not hasattr(self, "_tv_red_av"):
            return
        tipo = self._var_red_cent_tipo.get()
        datos = self._red_metricas_av_cache.get(tipo, [])
        import networkx as nx
        cat_map = (nx.get_node_attributes(self._grafo_actual, "categoria")
                   if self._grafo_actual else {})
        for row in self._tv_red_av.get_children():
            self._tv_red_av.delete(row)
        for i, (nodo, valor) in enumerate(datos[:30], 1):
            self._tv_red_av.insert("", "end",
                values=(i, nodo, cat_map.get(nodo, ""), f"{valor:.6f}"))

    def _red_refrescar_comunidades(self, coms: list):
        """Puebla la lista de comunidades."""
        if not hasattr(self, "_lb_red_comunidades"):
            return
        self._lb_red_comunidades.delete(0, "end")
        for com_id, miembros in coms:
            self._lb_red_comunidades.insert("end",
                f"Comunidad {com_id}  ({len(miembros)} miembros)")

    def _red_mostrar_comunidad(self, event=None):
        """Muestra los miembros de la comunidad seleccionada."""
        sel = self._lb_red_comunidades.curselection()
        if not sel or not self._red_comunidades_cache:
            return
        idx = sel[0]
        if idx >= len(self._red_comunidades_cache):
            return
        com_id, miembros = self._red_comunidades_cache[idx]
        import networkx as nx
        G = self._grafo_actual
        cat_map = nx.get_node_attributes(G, "categoria") if G else {}
        grado_map = dict(G.degree()) if G else {}
        for row in self._tv_red_miembros.get_children():
            self._tv_red_miembros.delete(row)
        for nodo in sorted(miembros, key=lambda n: -grado_map.get(n, 0)):
            self._tv_red_miembros.insert("", "end",
                values=(nodo, cat_map.get(nodo, ""), grado_map.get(nodo, 0)))

    def _red_evolucion_temporal(self):
        """Abre pestaña de evolución temporal — la construcción es bajo demanda."""
        messagebox.showinfo(
            "Evolución temporal",
            "Usa el botón '▶ Calcular evolución' en la pestaña 'Evolución temporal'.\n\n"
            "Requiere que el corpus_meta tenga varios números procesados.")

    def _red_calcular_evolucion(self):
        """Calcula la evolución temporal de la red número por número."""
        # Esta función espera corpus_meta como dict {art_id: {...}} (flujo del
        # conversor); si es el DataFrame que arma _worker_ocr, se trata como
        # "no disponible" en vez de intentar iterarlo mal (.items() de un
        # DataFrame recorre columnas, no artículos).
        corpus_meta = getattr(ST, "corpus_meta", None)
        indice = getattr(ST, "indice_ner_global", {}) or {}
        if not isinstance(corpus_meta, dict) and not indice:
            messagebox.showwarning("Sin corpus",
                "Procesa al menos dos números del corpus primero."); return

        from core.servicios_entidades import indice_por_numero as _por_numero
        indice_por_numero = _por_numero(corpus_meta, indice)

        if len(indice_por_numero) < 2:
            messagebox.showwarning(
                "Pocos números",
                f"Solo se detectó {len(indice_por_numero)} número(s).\n"
                "La evolución temporal requiere al menos 2 números procesados."); return

        self._lbl_red_ok.config(text="⏳ Calculando evolución temporal…")

        def _worker():
            from core.network_engine import evolucion_temporal
            cats = [c for c, v in self._var_red_cats.items() if v.get()]
            peso  = self._var_red_peso.get()

            def _cb(n, total, numero):
                self.after(0, lambda: self._lbl_red_ok.config(
                    text=f"⏳ {n}/{total}: {numero}"))

            serie = evolucion_temporal(indice_por_numero, categorias=cats,
                                       peso_minimo=peso, callback=_cb)
            self._red_evolucion_cache = serie

            def _mostrar():
                for row in self._tv_red_evo.get_children():
                    self._tv_red_evo.delete(row)
                for r in serie:
                    self._tv_red_evo.insert("", "end", values=(
                        r["numero"], r["nodos"], r["aristas"],
                        f"{r['densidad']:.4f}", r["top_nodo"]))
                self._lbl_red_ok.config(
                    text=f"✅ Evolución calculada: {len(serie)} números")
            self.after(0, _mostrar)

        threading.Thread(target=_worker, daemon=True).start()

    def _red_graficar_evolucion(self):
        """Grafica la evolución temporal de nodos/aristas/densidad."""
        if not self._red_evolucion_cache:
            messagebox.showwarning("Sin datos", "Calcula la evolución primero."); return
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            from core.chart_builder import _FONDO, _TEXTO
        except ImportError:
            messagebox.showerror("Falta matplotlib", "pip install matplotlib"); return

        serie = self._red_evolucion_cache
        numeros  = [r["numero"] for r in serie]
        nodos    = [r["nodos"]   for r in serie]
        aristas  = [r["aristas"] for r in serie]
        densidad = [r["densidad"] for r in serie]

        win = tk.Toplevel(self)
        win.title("Evolución temporal de la red")
        win.geometry("800x520")
        win.configure(bg=CONTENT_BG)

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6),
                                        facecolor=_FONDO, sharex=True)
        x = range(len(numeros))

        ax1.plot(x, nodos,   "o-", color="#6CA8E8", label="Nodos",   linewidth=2)
        ax1.plot(x, aristas, "s-", color="#E6A64C", label="Aristas",  linewidth=2)
        ax1.set_ylabel("Cantidad", color=_TEXTO); ax1.legend(fontsize=8)
        ax1.set_facecolor(_FONDO); ax1.tick_params(colors=_TEXTO)
        for spine in ax1.spines.values(): spine.set_edgecolor("#2A3238")

        ax2.plot(x, densidad, "^-", color="#6EC69A", linewidth=2)
        ax2.set_ylabel("Densidad", color=_TEXTO)
        ax2.set_xticks(list(x))
        ax2.set_xticklabels(numeros, rotation=30, ha="right", fontsize=7, color=_TEXTO)
        ax2.set_facecolor(_FONDO); ax2.tick_params(colors=_TEXTO)
        for spine in ax2.spines.values(): spine.set_edgecolor("#2A3238")

        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _red_evolucion_csv(self):
        """Exporta la tabla de evolución temporal a CSV."""
        if not self._red_evolucion_cache:
            messagebox.showwarning("Sin datos", "Calcula la evolución primero."); return
        import csv
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV","*.csv")],
            initialfile="evolucion_red.csv")
        if not dest: return
        with open(dest, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["numero","nodos","aristas",
                                               "densidad","top_nodo","top_cent"])
            w.writeheader(); w.writerows(self._red_evolucion_cache)
        messagebox.showinfo("Exportado", f"✅ Evolución exportada:\n{dest}")

    def _red_exportar_csv(self):
        """Exporta métricas por nodo (grado, betweenness, PageRank, closeness) a CSV."""
        if not self._grafo_actual:
            messagebox.showwarning("Sin red", "Construye la red primero."); return
        if not self._red_metricas_av_cache:
            messagebox.showwarning("Sin métricas avanzadas",
                "Calcula primero las métricas avanzadas con el botón '🔬 Métricas avanzadas'.")
            return
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV","*.csv")],
            initialfile="metricas_red.csv")
        if not dest: return
        try:
            from core.network_engine import exportar_metricas_csv
            exportar_metricas_csv(self._grafo_actual,
                                   self._red_metricas_av_cache, Path(dest))
            messagebox.showinfo("Exportado", f"✅ Métricas exportadas:\n{dest}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _build_valid(self):
        import tkinter as tk
        from tkinter import ttk
        self._tab_valid.columnconfigure(0, weight=1)
        self._tab_valid.rowconfigure(3, weight=1)
        ttk.Label(self._tab_valid, text="Validación humana y confianza", style="H.TLabel").grid(
            row=0, column=0, sticky="w", padx=20, pady=(18, 4))
        ttk.Label(self._tab_valid, text="Revisa y valida entidades por nivel de confianza (🟢 confiable · 🟡 revisar · 🔴 obligatorio)",
                  style="Sub.TLabel").grid(row=1, column=0, sticky="w", padx=20, pady=(0, 8))

        bframe = ttk.Frame(self._tab_valid)
        bframe.grid(row=2, column=0, sticky="w", padx=20, pady=4)
        ttk.Button(bframe, text="🔄 Calcular confianza del corpus",
                   command=self._valid_calcular).pack(side="left", padx=2)
        ttk.Button(bframe, text="✅ Marcar seleccionada como verificada",
                   command=self._valid_verificar).pack(side="left", padx=4)
        ttk.Button(bframe, text="✅✅ Marcar todas 🟢 como verificadas",
                   command=self._valid_verificar_todas_verdes).pack(side="left", padx=4)
        ttk.Button(bframe, text="💾 Guardar en base de conocimiento",
                   command=self._valid_guardar_kb).pack(side="left", padx=4)
        ttk.Button(bframe, text="📥 Exportar CSV",
                   command=self._valid_exportar_csv).pack(side="left", padx=4)

        cuerpo = ttk.Frame(self._tab_valid)
        cuerpo.grid(row=3, column=0, sticky="nsew", padx=20, pady=4)
        cuerpo.columnconfigure(0, weight=1)
        cuerpo.rowconfigure(0, weight=1)

        cols = ("Entidad", "Categoría", "Score", "Nivel", "Verificada")
        self._valid_tree = ttk.Treeview(cuerpo, columns=cols, show="headings", height=20)
        for col in cols:
            self._valid_tree.heading(col, text=col)
            self._valid_tree.column(col, width=150 if col != "Score" else 80)
        vsb = ttk.Scrollbar(cuerpo, orient="vertical", command=self._valid_tree.yview)
        self._valid_tree.configure(yscrollcommand=vsb.set)
        self._valid_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        # Tag colors
        self._valid_tree.tag_configure("green",  background="#15251F", foreground="#6EC69A")
        self._valid_tree.tag_configure("yellow", background="#2A2116", foreground="#E6A64C")
        self._valid_tree.tag_configure("red",    background="#2A1719", foreground="#D96B6B")

        self._valid_stat_var = tk.StringVar(value="")
        ttk.Label(self._tab_valid, textvariable=self._valid_stat_var,
                  style="Sub.TLabel").grid(row=4, column=0, sticky="w", padx=20, pady=4)

    def _valid_calcular(self):
        """Semáforo de confianza de las entidades. Ver core.servicios_entidades."""
        from core.servicios_entidades import calificar_entidades, fuente_para_validar
        try:
            from conocimiento.base_conocimiento import buscar_entidad, inicializar_db
            inicializar_db()
            en_base = buscar_entidad
        except Exception:
            en_base = None   # sin base de conocimiento: esa señal no cuenta

        filas = []
        if ST.repo:
            try:
                filas = ST.repo.buscar_entidades()
            except Exception as e:
                _registrar_error("validación: no se pudieron leer las entidades", e)
        fuente, origen = fuente_para_validar(filas, ST.indice_ner_global)

        self._valid_tree.delete(*self._valid_tree.get_children())
        emojis = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
        conteo = {"green": 0, "yellow": 0, "red": 0}
        for r in calificar_entidades(fuente, en_base):
            self._valid_tree.insert("", "end", tags=(r["nivel"],), values=(
                r["entidad"], r["categoria"], f"{r['score']:.2f}",
                emojis.get(r["nivel"], r["nivel"]), "No"))
            conteo[r["nivel"]] = conteo.get(r["nivel"], 0) + 1
        self._valid_stat_var.set(
            f"🟢 {conteo['green']} confiables · 🟡 {conteo['yellow']} revisar · "
            f"🔴 {conteo['red']} validar  [fuente: {origen or 'sin datos'}]")

    def _valid_verificar(self):
        sel = self._valid_tree.selection()
        if not sel:
            return
        for item in sel:
            vals = list(self._valid_tree.item(item, "values"))
            vals[4] = "Sí"
            vals[2] = "1.00"
            vals[3] = "🟢"
            self._valid_tree.item(item, values=vals, tags=("green",))

    def _valid_guardar_kb(self):
        try:
            from conocimiento.base_conocimiento import inicializar_db, registrar_entidad
            inicializar_db()
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("KB", str(e))
            return
        n = 0
        for item in self._valid_tree.get_children():
            vals = self._valid_tree.item(item, "values")
            ent, cat, score, _, verif = vals
            registrar_entidad(
                nombre=ent,
                categoria=cat,
                proyecto=str(self._proyecto_ruta or ""),
                confianza=float(score),
                verificada=(verif == "Sí"),
            )
            n += 1
        from tkinter import messagebox
        messagebox.showinfo("KB", f"✅ {n} entidades guardadas en la base de conocimiento.")
        # Marcar etapa validación como lista en semáforos
        ST.marcar_etapa("anal", "ready")
        self._actualizar_badges()

    def _valid_verificar_todas_verdes(self):
        """Marca como verificadas todas las entidades con nivel 🟢."""
        n = 0
        for item in self._valid_tree.get_children():
            vals = list(self._valid_tree.item(item, "values"))
            if vals[3] == "🟢" and vals[4] != "Sí":
                vals[4] = "Sí"
                self._valid_tree.item(item, values=vals)
                n += 1
        if hasattr(self, "_valid_stat_var"):
            prev = self._valid_stat_var.get()
            self._valid_stat_var.set(f"{prev}  ·  +{n} verificadas manualmente")

    def _valid_exportar_csv(self):
        """Exporta la tabla de validación a CSV."""
        items = self._valid_tree.get_children()
        if not items:
            messagebox.showwarning("Sin datos", "Calcula la confianza primero.")
            return
        import csv
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile="entidades_validadas.csv",
            title="Exportar validación")
        if not dest:
            return
        with open(dest, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["entidad", "categoria", "score", "nivel", "verificada"])
            for item in items:
                w.writerow(self._valid_tree.item(item, "values"))
        messagebox.showinfo("Exportado", f"✅ {len(items)} entidades exportadas:\n{dest}")

    def _build_colab(self):
        import tkinter as tk
        from tkinter import ttk
        self._tab_colab.columnconfigure(0, weight=1)
        self._tab_colab.rowconfigure(3, weight=1)
        ttk.Label(self._tab_colab, text="Colaboración y trazabilidad", style="H.TLabel").grid(
            row=0, column=0, sticky="w", padx=20, pady=(18, 4))
        ttk.Label(self._tab_colab, text="Exporta parches de tus cambios · importa cambios de colegas · visualiza contribuciones",
                  style="Sub.TLabel").grid(row=1, column=0, sticky="w", padx=20, pady=(0, 8))

        bframe = ttk.Frame(self._tab_colab)
        bframe.grid(row=2, column=0, sticky="w", padx=20, pady=4)
        ttk.Button(bframe, text="📤 Exportar parche",
                   command=self._colab_exportar).pack(side="left", padx=2)
        ttk.Button(bframe, text="📥 Importar parche",
                   command=self._colab_importar).pack(side="left", padx=4)
        ttk.Button(bframe, text="📋 Ver trazabilidad",
                   command=self._colab_trazabilidad).pack(side="left", padx=4)
        ttk.Button(bframe, text="🌐 HTML trazabilidad",
                   command=self._colab_html_trazabilidad).pack(side="left", padx=4)

        self._colab_log = tk.Text(self._tab_colab, height=18, state="disabled",
                                   bg="#0E1114", fg="#B5B6B3",
                                   font=("Consolas", 9), wrap="word")
        self._colab_log.grid(row=3, column=0, sticky="nsew", padx=20, pady=8)

    def _colab_log_insert(self, msg):
        self._colab_log.config(state="normal")
        self._colab_log.insert("end", msg + "\n")
        self._colab_log.see("end")
        self._colab_log.config(state="disabled")

    def _colab_exportar(self):
        if not self._proyecto_ruta:
            from tkinter import messagebox
            messagebox.showwarning("Colaborar", "Abre o guarda un proyecto primero.")
            return
        from tkinter import filedialog, simpledialog
        investigador = simpledialog.askstring("Investigador", "Tu nombre:",
                                               initialvalue="") or "anon"
        notas = simpledialog.askstring("Notas", "Notas del parche:", initialvalue="") or ""
        dest = filedialog.asksaveasfilename(
            title="Guardar parche",
            defaultextension=".bashkar.patch",
            filetypes=[("Parche Bashkar", "*.bashkar.patch"), ("Todos", "*.*")],
        )
        if not dest:
            return
        import threading
        threading.Thread(
            target=self._colab_exportar_worker,
            args=(investigador, notas, dest), daemon=True
        ).start()

    def _colab_exportar_worker(self, investigador, notas, dest):
        def _log(msg): self.after(0, lambda m=msg: self._colab_log_insert(m))
        try:
            import json
            from pathlib import Path

            from core.colaboracion import crear_parche, exportar_parche
            actual = json.loads(Path(self._proyecto_ruta).read_text(encoding="utf-8"))
            # "_ruta" es como el resto del proyecto (core/comparador.py) ubica el
            # SQLite hermano cuando "db" quedo relativo. Sin esto el parche sale
            # sin las correcciones manuales de OCR, que en v11 viven alli.
            actual["_ruta"] = str(self._proyecto_ruta)
            # Construir estado actual con NER actualizado
            actual_mod = dict(actual)
            actual_mod["indice_ner_global"] = ST.indice_ner_global
            parche = crear_parche(actual, actual_mod, investigador, notas)
            exportar_parche(parche, Path(dest))
            _log(f"✅ Parche exportado: {dest}")
        except Exception as e:
            _log(f"❌ Error: {e}")

    def _colab_importar(self):
        from tkinter import filedialog
        ruta = filedialog.askopenfilename(
            title="Seleccionar parche",
            filetypes=[("Parche Bashkar", "*.bashkar.patch"), ("Todos", "*.*")],
        )
        if not ruta:
            return
        import threading
        threading.Thread(
            target=self._colab_importar_worker, args=(ruta,), daemon=True
        ).start()

    def _colab_importar_worker(self, ruta):
        def _log(msg): self.after(0, lambda m=msg: self._colab_log_insert(m))
        try:
            import json
            from pathlib import Path

            from core.colaboracion import aplicar_parche, cargar_parche
            parche = cargar_parche(Path(ruta))
            investigador = parche.get("_investigador", "?")
            fecha        = parche.get("_fecha", "")[:16]
            notas        = parche.get("_notas", "")
            n_cambios    = len([k for k in parche if not k.startswith("_")])

            _log("─── Parche recibido ───────────────────────────────────")
            _log(f"  De:     {investigador}")
            _log(f"  Fecha:  {fecha}")
            _log(f"  Notas:  {notas}")
            _log(f"  Secciones modificadas: {n_cambios}")
            _log("───────────────────────────────────────────────────────")

            # Vista previa de claves modificadas
            for k in list(parche.keys())[:10]:
                if not k.startswith("_"):
                    _log(f"  · {k}")

            if not self._proyecto_ruta:
                _log("⚠ Abre un proyecto primero para aplicar el parche.")
                return

            # Confirmación desde hilo principal
            def _confirmar():
                from tkinter import messagebox
                ok = messagebox.askyesno(
                    "Aplicar parche",
                    f"Parche de: {investigador}\n"
                    f"Fecha: {fecha}\n"
                    f"Notas: {notas}\n"
                    f"Secciones: {n_cambios}\n\n"
                    f"Se creará un backup automático del proyecto.\n"
                    f"¿Aplicar?")
                if ok:
                    import threading
                    threading.Thread(target=_aplicar, daemon=True).start()
                else:
                    self._colab_log_insert("Aplicación cancelada.")

            def _aplicar():
                try:
                    actual = json.loads(Path(self._proyecto_ruta).read_text(encoding="utf-8"))
                    actual["_ruta"] = str(self._proyecto_ruta)
                    # Backup automático antes de aplicar
                    backup = Path(self._proyecto_ruta).with_suffix(".bashkar.bak")
                    backup.write_text(json.dumps(actual, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
                    _log(f"Backup guardado: {backup.name}")

                    actualizado = aplicar_parche(actual, parche, callback=_log)
                    from core.colaboracion import indice_ner_de
                    ST.indice_ner_global = (indice_ner_de(actualizado)
                                            or ST.indice_ner_global)
                    # "_ruta" es contexto en memoria, no un campo del formato:
                    # persistirlo dejaria una ruta absoluta obsoleta dentro del
                    # .bashkar en cuanto el proyecto cambie de carpeta o de PC.
                    actualizado.pop("_ruta", None)
                    Path(self._proyecto_ruta).write_text(
                        json.dumps(actualizado, indent=2, ensure_ascii=False),
                        encoding="utf-8")
                    _log("✅ Parche aplicado y proyecto guardado.")
                except Exception as ex:
                    _log(f"❌ Error al aplicar: {ex}")

            self.after(0, _confirmar)

        except Exception as e:
            _log(f"❌ Error al cargar parche: {e}")

    def _colab_trazabilidad(self):
        if not self._proyecto_ruta:
            from tkinter import messagebox
            messagebox.showwarning("Colaborar", "Abre un proyecto primero.")
            return
        import json
        from pathlib import Path

        from core.colaboracion import reporte_trazabilidad
        data = json.loads(Path(self._proyecto_ruta).read_text(encoding="utf-8"))
        rep = reporte_trazabilidad(data)
        self._colab_log.config(state="normal")
        self._colab_log.delete("1.0", "end")
        self._colab_log.insert("end", rep)
        self._colab_log.config(state="disabled")

    def _colab_html_trazabilidad(self):
        if not self._proyecto_ruta:
            return
        import json
        import webbrowser
        from pathlib import Path

        from core.colaboracion import exportar_trazabilidad_html
        data = json.loads(Path(self._proyecto_ruta).read_text(encoding="utf-8"))
        out = Path.home() / "Documents" / "BashkarStation" / "trazabilidad.html"
        exportar_trazabilidad_html(data, out)
        webbrowser.open(f"file:///{str(out).replace(chr(92), '/')}")
