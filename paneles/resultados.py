"""paneles/resultados.py — Métodos de BashkarApp extraídos de app.py.

Mixin: BashkarApp hereda de PanelResultados. Los cuerpos son copia literal del
original; los nombres globales (ST, colores, tk…) los inyecta
paneles.sincronizar() desde app.py.
"""

from __future__ import annotations

# ruff: noqa: F821


class PanelResultados:
    # ══════════════════════════════════════════════════════════════════════════
    # TAB 7: RESULTADOS
    # ══════════════════════════════════════════════════════════════════════════
    def _build_res(self):
        f = self._tab_res
        self._page_header(f, "Resultados y exportación",
                          "Gráficas interactivas, análisis de red y exportación Excel", "📈")
        self._build_ai_panel(f, "res")
        pad = tk.Frame(f, bg=CONTENT_BG); pad.pack(fill="both", expand=True, padx=24, pady=12)
        # Métricas
        ind = tk.Frame(pad, bg=CONTENT_BG); ind.pack(fill="x", pady=(0,12))
        self._lbl_r_num  = self._mk_ind(ind,"Números","—",0)
        self._lbl_r_pag  = self._mk_ind(ind,"Páginas","—",1)
        self._lbl_r_pal  = self._mk_ind(ind,"Palabras","—",2)
        self._lbl_r_art  = self._mk_ind(ind,"Artículos","—",3)
        self._lbl_r_aut  = self._mk_ind(ind,"Autores","—",4)
        self._lbl_r_fir  = self._mk_ind(ind,"Firmas NER","—",5)
        # Notebook de gráficas
        nb_r = ttk.Notebook(pad); nb_r.pack(fill="both",expand=True,pady=6)
        self._figs_tabs = {}
        for key, label in [
            ("secciones","📋 Secciones"),("firmas","✍️ Firmas"),
            ("campos","🔤 Campos sem."),("articulos","📝 Artículos"),
            ("lda","🧩 Temas LDA"),("red","🕸️ Red"),
            ("visual","🖼️ Visual"),("comparativo","📊 Comparativo"),("layout","📐 Layout"),
        ]:
            tab = tk.Frame(nb_r, bg=CONTENT_BG); nb_r.add(tab, text=f"  {label}  ")
            self._figs_tabs[key] = tab
        # Botones de exportación
        bb = ttk.Frame(pad,padding=8); bb.pack(fill="x")
        ttk.Button(bb, text="📊  Excel completo (10 hojas)",
                   style="P.TButton", command=self._gen_excel).pack(side="left",padx=8)
        ttk.Button(bb, text="🕸️  Red .graphml",
                   style="S.TButton", command=self._guardar_graphml).pack(side="left",padx=8)
        ttk.Button(bb, text="📁  Abrir carpeta",
                   style="S.TButton", command=self._abrir_carpeta).pack(side="left",padx=8)
        ttk.Button(bb, text="📄  XML-TEI",
                   style="S.TButton", command=self._res_exportar_tei).pack(side="left",padx=4)
        ttk.Button(bb, text="✓  Validar TEI",
                   style="S.TButton", command=self._res_validar_tei).pack(side="left",padx=2)
        ttk.Button(bb, text="📚  BibTeX",
                   style="S.TButton", command=self._res_exportar_bibtex).pack(side="left",padx=4)
        ttk.Button(bb, text="📦  Paquete publicación",
                   style="S.TButton", command=self._res_paquete_publicacion).pack(side="left",padx=4)
        ttk.Button(bb, text="📋  METHODS.md",
                   style="S.TButton", command=self._res_generar_methods).pack(side="left",padx=4)
        ttk.Button(bb, text="🔗  JSON Observable",
                   style="S.TButton", command=self._res_exportar_json_observable).pack(side="left",padx=4)
        ttk.Button(bb, text="📊  PowerPoint",
                   style="S.TButton", command=self._res_exportar_pptx).pack(side="left",padx=4)
        ttk.Button(bb, text="💾  Guardar como…",
                   style="P.TButton", command=self._exp_abrir_dialogo).pack(side="left",padx=4)
        self._lbl_excel = tk.Label(bb, text="", bg=CONTENT_BG, fg=VERDE, font=("Segoe UI",10,"bold"))
        self._lbl_excel.pack(side="left",padx=12)

    # ══════════════════════════════════════════════════════════════════════════
    # BENCHMARK OCR — comparar rutas contra un estándar de oro
    # ══════════════════════════════════════════════════════════════════════════
    def _build_bench(self):
        self._page_header(
            self._tab_bench, "Benchmark de OCR",
            "Mide qué ruta transcribe mejor tu corpus: CER, WER y similitud "
            "contra una transcripción de referencia", "⚖️")
        pad = tk.Frame(self._tab_bench, bg=CONTENT_BG, padx=16, pady=8)
        pad.pack(fill="both", expand=True)

        tk.Label(
            pad,
            text="Elegir ruta de OCR «a ojo» no es defendible en una publicación. "
                 "Aquí se compara cada ruta contra páginas que tú transcribiste a "
                 "mano (el estándar de oro) y se obtienen las métricas que pide la "
                 "literatura: CER, WER y similitud de Levenshtein normalizada.",
            bg=CONTENT_BG, fg=GRIS2, font=("Segoe UI", 9),
            wraplength=880, justify="left").pack(anchor="w", pady=(0, 10))

        # ── 1. Estándar de oro ────────────────────────────────────────────────
        f1 = tk.LabelFrame(pad, text=" 1 · Estándar de oro ", bg=CONTENT_BG,
                           fg=TXT_SEC, font=("Segoe UI", 9, "bold"), padx=10, pady=8)
        f1.pack(fill="x", pady=(0, 8))
        tk.Label(f1, text="Carpeta con las transcripciones de referencia (un .txt "
                          "por página, con el mismo nombre que la imagen).",
                 bg=CONTENT_BG, fg=GRIS2, font=("Segoe UI", 8),
                 wraplength=820, justify="left").pack(anchor="w")
        fr1 = tk.Frame(f1, bg=CONTENT_BG); fr1.pack(fill="x", pady=(4, 0))
        self._var_bench_oro = tk.StringVar()
        ttk.Entry(fr1, textvariable=self._var_bench_oro, width=70).pack(side="left")
        ttk.Button(fr1, text="📂 Elegir…",
                   command=self._bench_elegir_oro).pack(side="left", padx=6)

        # ── 2. Imágenes a transcribir ─────────────────────────────────────────
        f2 = tk.LabelFrame(pad, text=" 2 · Páginas a evaluar ", bg=CONTENT_BG,
                           fg=TXT_SEC, font=("Segoe UI", 9, "bold"), padx=10, pady=8)
        f2.pack(fill="x", pady=(0, 8))
        fr2 = tk.Frame(f2, bg=CONTENT_BG); fr2.pack(fill="x")
        self._var_bench_imgs = tk.StringVar()
        ttk.Entry(fr2, textvariable=self._var_bench_imgs, width=70).pack(side="left")
        ttk.Button(fr2, text="📂 Elegir…",
                   command=self._bench_elegir_imgs).pack(side="left", padx=6)

        # ── 3. Rutas a comparar ───────────────────────────────────────────────
        f3 = tk.LabelFrame(pad, text=" 3 · Rutas a comparar ", bg=CONTENT_BG,
                           fg=TXT_SEC, font=("Segoe UI", 9, "bold"), padx=10, pady=8)
        f3.pack(fill="x", pady=(0, 8))

        self._bench_rutas_vars = {}
        for clave, etiqueta, nota in self._bench_catalogo_rutas():
            fila = tk.Frame(f3, bg=CONTENT_BG); fila.pack(fill="x", anchor="w")
            var = tk.BooleanVar(value=(clave == "tesseract"))
            self._bench_rutas_vars[clave] = var
            ttk.Checkbutton(fila, text=etiqueta, variable=var).pack(side="left")
            if nota:
                tk.Label(fila, text=f"  {nota}", bg=CONTENT_BG, fg=TXT_DIM,
                         font=("Segoe UI", 8)).pack(side="left")

        # ── Acciones ──────────────────────────────────────────────────────────
        acc = tk.Frame(pad, bg=CONTENT_BG); acc.pack(fill="x", pady=(4, 8))
        self._btn_bench = ttk.Button(acc, text="▶  Ejecutar benchmark",
                                     style="P.TButton", command=self._bench_iniciar)
        self._btn_bench.pack(side="left", padx=(0, 8))
        self._btn_bench_descargar = ttk.Button(
            acc, text="⬇ Descargar modelo CHURRO",
            command=self._bench_descargar_churro)
        self._btn_bench_descargar.pack(side="left", padx=4)
        ttk.Button(acc, text="📤 Preparar estándar de oro",
                   command=self._bench_preparar_oro).pack(side="left", padx=4)
        ttk.Button(acc, text="📊 Avance",
                   command=self._bench_estado_oro).pack(side="left", padx=4)
        ttk.Button(acc, text="💾 Exportar CSV",
                   command=lambda: self._bench_exportar("csv")).pack(side="left", padx=4)
        ttk.Button(acc, text="📋 Copiar tabla Markdown",
                   command=self._bench_copiar_md).pack(side="left", padx=4)
        self._lbl_bench = tk.Label(acc, text="", bg=CONTENT_BG, fg=TXT_DIM,
                                   font=("Segoe UI", 9))
        self._lbl_bench.pack(side="left", padx=10)

        # ── Resultados ────────────────────────────────────────────────────────
        cols = ("ruta", "cer", "wer", "sim", "spp", "calidad")
        self._tv_bench = ttk.Treeview(pad, columns=cols, show="headings", height=8)
        for c, txt, w in (("ruta", "Ruta", 220), ("cer", "CER ↓", 90),
                          ("wer", "WER ↓", 90), ("sim", "Similitud ↑", 100),
                          ("spp", "s/página", 90), ("calidad", "Calidad", 160)):
            self._tv_bench.heading(c, text=txt)
            self._tv_bench.column(c, width=w, anchor="w" if c in ("ruta", "calidad") else "e")
        self._tv_bench.pack(fill="both", expand=True, pady=(0, 6))

        self._txt_bench = scrolledtext.ScrolledText(
            pad, height=9, bg="#0E1114", fg="#E8E5DF", font=("Consolas", 9),
            insertbackground="#E8E5DF", wrap="word")
        self._txt_bench.pack(fill="both", expand=True)
        self._bench_resultados = []

    def _bench_catalogo_rutas(self):
        """Rutas ofrecidas, con su estado real de disponibilidad a la vista."""
        from core.benchmark_ocr import catalogo_rutas
        return catalogo_rutas()

    def _bench_preparar_oro(self):
        """Exporta las zonas etiquetadas listas para transcribir a mano.

        Sin transcripción de referencia solo se pueden comparar unas rutas con
        otras; el CER absoluto exige un estándar de oro. Se exporta por ZONAS
        —no por páginas— porque transcribir bloques cortos y homogéneos es
        mucho más llevadero, se puede parar y seguir, y el avance es medible.
        """
        from core.estandar_oro import exportar_zonas

        if not ST.out_dir:
            messagebox.showwarning("Sin proyecto",
                                   "Abre primero un proyecto con corpus."); return
        numero = ""
        if hasattr(self, "_etz_numero"):
            numero = self._etz_numero.get() or ""
        if not numero:
            messagebox.showwarning(
                "Sin número",
                "Elige un número en el Etiquetador: se exportan sus zonas."); return

        etq_dir = Path(ST.out_dir) / "05_etiquetas" / numero
        paginas = sorted(p.stem for p in etq_dir.glob("*.json")) if etq_dir.is_dir() else []
        if not paginas:
            messagebox.showwarning(
                "Sin páginas etiquetadas",
                f"No hay etiquetas en:\n{etq_dir}\n\n"
                "Etiqueta primero las zonas en el panel Etiquetador."); return

        destino = filedialog.askdirectory(
            title="¿Dónde dejar los recortes para transcribir?")
        if not destino:
            return

        self._txt_bench.delete("1.0", "end")

        def log(m):
            self.after(0, lambda msg=m: (self._txt_bench.insert("end", msg + "\n"),
                                         self._txt_bench.see("end")))

        def _trabajo():
            try:
                zonas = exportar_zonas(ST.out_dir, numero, paginas, destino,
                                       callback=log)
                self.after(0, lambda: (
                    self.toast(f"{len(zonas)} zona(s) listas para transcribir", "ok"),
                    self._var_bench_oro.set(destino)))
                log("\nAbre la carpeta y lee INSTRUCCIONES.md antes de empezar.")
            except Exception as e:                  # noqa: BLE001
                log(f"✖ Error: {e}")

        threading.Thread(target=_trabajo, daemon=True).start()

    def _bench_estado_oro(self):
        """Cuánto se lleva transcrito, sin tener que abrir la carpeta."""
        from core.estandar_oro import estado

        carpeta = (self._var_bench_oro.get() or "").strip()
        if not carpeta or not Path(carpeta).is_dir():
            messagebox.showinfo("Sin carpeta",
                                "Indica primero la carpeta del estándar de oro."); return
        e = estado(carpeta)
        if not e["total"]:
            messagebox.showinfo(
                "Carpeta no preparada",
                "Esa carpeta no tiene manifiesto. Usa «Preparar estándar de oro»."); return

        detalle = "\n".join(
            f"   {tipo}: {d['hechas']}/{d['total']}"
            for tipo, d in sorted(e["por_tipo"].items()))
        aviso = ("\n\n⚠ Se prellenó con OCR automático: revisa que no hayas dado "
                 "por buenos errores del motor." if e.get("prellenado") else "")
        messagebox.showinfo(
            "Avance del estándar de oro",
            f"{e['hechas']} de {e['total']} zonas transcritas "
            f"({e['porcentaje']} %)\n"
            f"{e['pendientes']} pendiente(s) · {e['palabras']} palabras escritas\n\n"
            f"Por tipo:\n{detalle}{aviso}")

    def _bench_descargar_churro(self):
        """Descarga el modelo CHURRO desde la propia aplicación.

        El usuario de Bashkar no abre una terminal: si la única forma de tener
        la ruta fuera `huggingface-cli download`, la función no existiría para
        quien usa el .exe.
        """
        from core import ocr_churro
        motivo = ocr_churro.motivo_no_disponible()
        if motivo:
            messagebox.showerror("CHURRO no disponible", motivo); return
        if ocr_churro.esta_descargado():
            self.toast("El modelo CHURRO ya está descargado.", "ok"); return
        if not messagebox.askyesno(
                "Descargar CHURRO-3B",
                "Se van a descargar unos 7 GB del modelo CHURRO-3B.\n\n"
                "Es una sola vez: después funciona sin conexión.\n"
                "Puede tardar bastante según tu conexión.\n\n¿Continuar?"):
            return

        self._btn_bench_descargar.config(state="disabled")
        self._txt_bench.delete("1.0", "end")

        def log(m):
            self.after(0, lambda msg=m: (self._txt_bench.insert("end", msg + "\n"),
                                         self._txt_bench.see("end")))

        def _trabajo():
            try:
                ocr_churro.descargar_modelo(callback=log)
                self.after(0, lambda: (
                    self._btn_bench_descargar.config(state="normal"),
                    self.toast("Modelo CHURRO descargado.", "ok")))
            except Exception as e:                  # noqa: BLE001
                log(f"✖ Error en la descarga: {e}")
                self.after(0, lambda: self._btn_bench_descargar.config(state="normal"))

        threading.Thread(target=_trabajo, daemon=True).start()

    def _bench_elegir_oro(self):
        d = filedialog.askdirectory(title="Carpeta con las transcripciones de referencia")
        if d:
            self._var_bench_oro.set(d)

    def _bench_elegir_imgs(self):
        d = filedialog.askdirectory(title="Carpeta con las imágenes de las páginas")
        if d:
            self._var_bench_imgs.set(d)

    def _bench_iniciar(self):
        """Valida, estima el costo en tiempo y pide confirmación antes de lanzar."""
        # OJO: Path("") es Path(".") y `.is_dir()` daría True — un campo vacío
        # habría pasado la validación y el benchmark se habría lanzado sobre el
        # directorio de trabajo. Hay que comprobar la cadena antes.
        s_oro = (self._var_bench_oro.get() or "").strip()
        s_imgs = (self._var_bench_imgs.get() or "").strip()
        oro, imgs = Path(s_oro), Path(s_imgs)
        if not s_oro or not s_imgs or not oro.is_dir() or not imgs.is_dir():
            messagebox.showwarning("Faltan carpetas",
                                   "Indica la carpeta del estándar de oro y la de imágenes.")
            return
        seleccionadas = [k for k, v in self._bench_rutas_vars.items() if v.get()]
        if not seleccionadas:
            messagebox.showwarning("Sin rutas", "Marca al menos una ruta a comparar.")
            return

        refs = sorted(oro.glob("*.txt"))
        if not refs:
            messagebox.showwarning("Estándar de oro vacío",
                                   f"No hay archivos .txt en:\n{oro}")
            return

        # Estimación previa: estándar del proyecto, nunca lanzar un lote caro a ciegas
        from core import ocr_churro, ocr_pero
        n = len(refs)
        detalle = []
        total_min = 0.0
        for r in seleccionadas:
            if r == "churro":
                e = ocr_churro.estimar_tiempo(n); total_min += e["minutos"]
                extra = (f" + descarga de {e['descarga_pendiente_gb']:.0f} GB"
                         if e["descarga_pendiente_gb"] else "")
                detalle.append(f"  · CHURRO-3B: {e['minutos']} min{extra}")
            elif r == "pero":
                e = ocr_pero.estimar_tiempo(n); total_min += e["minutos"]
                detalle.append(f"  · PERO-OCR: {e['minutos']} min")
            else:
                m = round(n * 4 / 60, 1); total_min += m
                detalle.append(f"  · {r}: ~{m} min")

        if not messagebox.askyesno(
                "Confirmar benchmark",
                f"Se van a transcribir {n} página(s) con {len(seleccionadas)} ruta(s).\n\n"
                + "\n".join(detalle)
                + f"\n\nTiempo total estimado: ~{round(total_min, 1)} min.\n"
                  "Costo en dinero: $0 (todas las rutas son locales).\n\n¿Continuar?"):
            return

        self._btn_bench.config(state="disabled")
        self._lbl_bench.config(text="Ejecutando…", fg="#E6A64C")
        self._txt_bench.delete("1.0", "end")
        # El número del corpus se lee AQUÍ (hilo principal): el worker lo
        # necesita para localizar las zonas etiquetadas y no puede tocar Tk.
        numero_etq = ""
        if hasattr(self, "_etz_numero"):
            try:
                numero_etq = self._etz_numero.get() or ""
            except tk.TclError:
                numero_etq = ""
        threading.Thread(target=self._worker_bench,
                         args=(oro, imgs, seleccionadas, numero_etq),
                         daemon=True).start()

    def _worker_bench(self, oro: Path, imgs: Path, rutas: list,
                      numero_etq: str = ""):
        """Corre cada ruta sobre las mismas páginas y compara. En hilo."""
        import time as _t

        from core import benchmark_ocr

        def log(m):
            self.after(0, lambda msg=m: (self._txt_bench.insert("end", msg + "\n"),
                                         self._txt_bench.see("end")))

        try:
            # Carpeta preparada con «Preparar estándar de oro»: se lee por su
            # manifiesto, que sabe qué zona es cada .txt y en qué orden van.
            # Si no lo tiene, se acepta una carpeta suelta de .txt por página.
            from core.estandar_oro import MANIFIESTO, recolectar
            if (oro / MANIFIESTO).exists():
                referencias = recolectar(oro, por_pagina=True)
                log(f"Estándar de oro por zonas: {len(referencias)} página(s)")
            else:
                referencias = {p.stem: p.read_text(encoding="utf-8", errors="replace")
                               for p in sorted(oro.glob("*.txt"))}
            imagenes = [p for p in sorted(imgs.iterdir())
                        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".tif", ".tiff")
                        and p.stem in referencias]
            log(f"Estándar de oro: {len(referencias)} página(s)")
            log(f"Imágenes emparejadas: {len(imagenes)}")
            if not imagenes:
                log("⚠ Ninguna imagen coincide por nombre con el estándar de oro.")
                self.after(0, self._bench_fin, [])
                return

            salidas, tiempos = {}, {}
            for ruta in rutas:
                log(f"\n▶ Ruta «{ruta}»…")
                t0 = _t.perf_counter()
                try:
                    salidas[ruta] = self._bench_correr_ruta(ruta, imagenes, log,
                                                            numero_etq)
                except Exception as e:                      # noqa: BLE001
                    log(f"  ✖ {ruta} falló: {e}")
                    continue
                tiempos[ruta] = _t.perf_counter() - t0
                log(f"  ✔ {len(salidas[ruta])} página(s) en {tiempos[ruta]:.1f} s")

            resultados = benchmark_ocr.evaluar_rutas(referencias, salidas, tiempos)
            log("\n" + benchmark_ocr.tabla_markdown(resultados))
            self.after(0, self._bench_fin, resultados)
        except Exception as e:                              # noqa: BLE001
            log(f"\n✖ Error: {e}")
            self.after(0, self._bench_fin, [])

    def _bench_correr_ruta(self, ruta: str, imagenes: list, log,
                           numero_etq: str = "") -> dict:
        """Ejecuta UNA ruta sobre las imágenes. Ver core.benchmark_ocr.correr_ruta.

        Corre DENTRO del hilo del benchmark: no toca Tk. `numero_etq` viene ya
        leído desde el hilo principal.
        """
        from core.benchmark_ocr import correr_ruta
        return correr_ruta(ruta, imagenes, log, out_dir=ST.out_dir, numero_etq=numero_etq)

    def _bench_fin(self, resultados):
        """Vuelca los resultados en la tabla. Solo hilo principal."""
        self._bench_resultados = resultados
        self._tv_bench.delete(*self._tv_bench.get_children())
        for r in resultados:
            self._tv_bench.insert("", "end", values=(
                r.ruta, f"{r.cer:.4f}", f"{r.wer:.4f}", f"{r.similitud:.4f}",
                f"{r.segundos_por_pagina:.1f}", r.calidad))
        self._btn_bench.config(state="normal")
        if resultados:
            self._lbl_bench.config(text=f"✅ Mejor: {resultados[0].ruta}", fg="#6EC69A")
            self.toast(f"Benchmark listo — mejor ruta: {resultados[0].ruta}", "ok")
        else:
            self._lbl_bench.config(text="Sin resultados", fg="#D96B6B")

    def _bench_exportar(self, formato: str = "csv"):
        if not self._bench_resultados:
            messagebox.showinfo("Sin datos", "Ejecuta primero el benchmark."); return
        from core import benchmark_ocr
        destino = filedialog.asksaveasfilename(
            defaultextension=f".{formato}",
            filetypes=[(formato.upper(), f"*.{formato}")],
            initialfile=f"benchmark_ocr.{formato}")
        if not destino:
            return
        if formato == "csv":
            benchmark_ocr.exportar_csv(self._bench_resultados, Path(destino))
        else:
            benchmark_ocr.exportar_json(self._bench_resultados, Path(destino))
        self.toast(f"Exportado a {Path(destino).name}", "ok")

    def _bench_copiar_md(self):
        if not self._bench_resultados:
            messagebox.showinfo("Sin datos", "Ejecuta primero el benchmark."); return
        from core import benchmark_ocr
        md = benchmark_ocr.tabla_markdown(self._bench_resultados)
        self.clipboard_clear(); self.clipboard_append(md)
        self.toast("Tabla Markdown copiada al portapapeles", "ok")

    def _build_rep(self):
        pad = tk.Frame(self._tab_rep, bg=CONTENT_BG, padx=16, pady=12)
        pad.pack(fill="both", expand=True)
        tk.Label(pad, text="Reporte narrativo del corpus", bg=CONTENT_BG,
                 fg="#E8E5DF", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(pad,
                 text="Genera narrativas académicas con IA y exporta el reporte completo del análisis.",
                 bg=CONTENT_BG, fg=GRIS2, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 10))

        # ── Narrativas ────────────────────────────────────────────────────────
        nar_frame = tk.LabelFrame(pad, text=" Narrativas académicas (Claude) ",
                                   bg=CONTENT_BG, fg=GRIS2, font=("Segoe UI", 9))
        nar_frame.pack(fill="x", pady=(0, 10))

        bf = tk.Frame(nar_frame, bg=CONTENT_BG)
        bf.pack(fill="x", padx=8, pady=6)
        self._btn_rep_nar = ttk.Button(bf, text="▶  Generar narrativas IA",
                                        style="P.TButton",
                                        command=self._rep_generar_narrativas)
        self._btn_rep_nar.pack(side="left", padx=(0, 8))
        self._lbl_rep_nar = tk.Label(bf, text="", bg=CONTENT_BG, fg=VERDE,
                                      font=("Segoe UI", 9))
        self._lbl_rep_nar.pack(side="left")

        self._txt_rep_nar = scrolledtext.ScrolledText(
            nar_frame, height=8, font=("Georgia", 9),
            bg="#12171B", fg="#B5B6B3", wrap="word", state="disabled")
        self._txt_rep_nar.pack(fill="x", padx=8, pady=(0, 8))

        # ── Exportar HTML ─────────────────────────────────────────────────────
        html_frame = tk.LabelFrame(pad, text=" Reporte HTML scrollytelling ",
                                    bg=CONTENT_BG, fg=GRIS2, font=("Segoe UI", 9))
        html_frame.pack(fill="x", pady=(0, 10))
        hf = tk.Frame(html_frame, bg=CONTENT_BG)
        hf.pack(fill="x", padx=8, pady=6)
        self._btn_rep_html = ttk.Button(hf, text="▶  Generar reporte HTML",
                                         style="P.TButton",
                                         command=self._rep_generar_html)
        self._btn_rep_html.pack(side="left", padx=(0, 8))
        ttk.Button(hf, text="🌐  Abrir en navegador", style="S.TButton",
                   command=self._rep_abrir_html).pack(side="left", padx=(0, 8))
        self._lbl_rep_html = tk.Label(hf, text="", bg=CONTENT_BG, fg=VERDE,
                                       font=("Segoe UI", 9))
        self._lbl_rep_html.pack(side="left")

        # ── Exportar Word ─────────────────────────────────────────────────────
        word_frame = tk.LabelFrame(pad, text=" Exportar Word (.docx) ",
                                    bg=CONTENT_BG, fg=GRIS2, font=("Segoe UI", 9))
        word_frame.pack(fill="x", pady=(0, 10))
        wf = tk.Frame(word_frame, bg=CONTENT_BG)
        wf.pack(fill="x", padx=8, pady=6)
        self._btn_rep_word = ttk.Button(wf, text="📄  Exportar Word",
                                         style="S.TButton",
                                         command=self._rep_exportar_word)
        self._btn_rep_word.pack(side="left", padx=(0, 8))
        self._lbl_rep_word = tk.Label(wf, text="", bg=CONTENT_BG, fg=VERDE,
                                       font=("Segoe UI", 9))
        self._lbl_rep_word.pack(side="left")

        self._narrativas_data = {}
        self._rep_html_path = None

    def _rep_generar_narrativas(self):
        api_key, _m = _resolver_api_key_modelo("narrativas")
        if not api_key:
            messagebox.showwarning("Sin API key", "Configura tu clave Claude API en Configuración.")
            return
        self._btn_rep_nar.config(state="disabled")
        self._lbl_rep_nar.config(text="Generando narrativas…")
        threading.Thread(target=self._worker_narrativas, daemon=True).start()

    def _rep_generar_html(self):
        self._btn_rep_html.config(state="disabled")
        self._lbl_rep_html.config(text="Generando HTML…")
        threading.Thread(target=self._worker_rep_html, daemon=True).start()

    def _worker_rep_html(self):
        from pathlib import Path as _PPath

        from core.storytelling_engine import generar_reporte_html
        try:
            nombre = getattr(ST, "proyecto_nombre", "Corpus Estampa")
            ruta = _PPath.home() / "Documents" / "BashkarStation" / "reporte" / "reporte_bashkar.html"
            generar_reporte_html(
                proyecto_nombre=nombre,
                stats_corpus=self._rep_stats_corpus(),
                indice_ner=getattr(ST, "indice_ner_global", {}),
                stats_tono=getattr(self, "_tono_resultados", None),
                metricas_red=getattr(self, "_metricas_red_cache", None),
                narrativas=self._narrativas_data,
                ruta=ruta,
            )
            self._rep_html_path = ruta
            self.after(0, lambda: self._lbl_rep_html.config(text=f"✅ HTML generado: {ruta}"))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._lbl_rep_html.config(text=f"⚠ Error: {err}"))
        self.after(0, lambda: self._btn_rep_html.config(state="normal"))

    def _rep_abrir_html(self):
        if not self._rep_html_path or not self._rep_html_path.exists():
            messagebox.showinfo("Sin reporte", "Genera el reporte HTML primero.")
            return
        import webbrowser
        webbrowser.open(str(self._rep_html_path))

    def _rep_exportar_word(self):
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            defaultextension=".docx",
            filetypes=[("Word", "*.docx"), ("Todos", "*.*")],
            initialfile="reporte_estampa.docx",
            title="Guardar reporte Word")
        if not dest:
            return
        self._btn_rep_word.config(state="disabled")
        threading.Thread(target=self._worker_rep_word, args=(dest,), daemon=True).start()

    def _worker_rep_word(self, dest):
        from pathlib import Path as _PPath

        from core.storytelling_engine import exportar_word
        try:
            nombre = getattr(ST, "proyecto_nombre", "Corpus Estampa")
            exportar_word(
                proyecto_nombre=nombre,
                stats_corpus=self._rep_stats_corpus(),
                indice_ner=getattr(ST, "indice_ner_global", {}),
                narrativas=self._narrativas_data,
                ruta=_PPath(dest),
            )
            self.after(0, lambda: self._lbl_rep_word.config(text=f"✅ Exportado: {dest}"))
            self.after(0, lambda: messagebox.showinfo("Exportado", f"Word guardado en:\n{dest}"))
        except ImportError:
            self.after(0, lambda: self._lbl_rep_word.config(
                text="⚠ python-docx no instalado. pip install python-docx>=1.1.0"))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._lbl_rep_word.config(text=f"⚠ Error: {err}"))
        self.after(0, lambda: self._btn_rep_word.config(state="normal"))

    def _rep_stats_corpus(self) -> dict:
        return {
            "n_pdfs": len(getattr(ST, "pdf_files", []) or []),
            "n_paginas": len(_cm) if (_cm := getattr(ST, "corpus_meta", None)) is not None else 0,
            "n_articulos": len(getattr(ST, "articulos", []) or []),
            "n_palabras_total": sum(
                len((t or "").split())
                for t in (getattr(ST, "corpus_txt", []) or [])
            ),
            "proyecto": getattr(ST, "proyecto_nombre", "Corpus Estampa"),
        }

    def _exp_abrir_dialogo(self):
        """Diálogo con 4 presets: Copia exacta (PDF buscable) / Edición
        académica (TEI+BibTeX) / Datos de análisis (Excel) / Texto plano.
        Reusa los exportadores YA existentes para los 3 últimos; el único
        camino nuevo es el PDF buscable."""
        from core.user_prefs import guardar_pref, obtener_pref

        win, content = self._mk_glass_toplevel("Guardar como…", 480, 380)
        pad = tk.Frame(content, bg=CONTENT_BG)
        pad.pack(fill="both", expand=True, padx=20, pady=16)

        var_abrir = tk.BooleanVar(value=obtener_pref("exp_abrir_al_terminar", True))
        ttk.Checkbutton(pad, text="Abrir el archivo al terminar",
                         variable=var_abrir,
                         command=lambda: guardar_pref("exp_abrir_al_terminar", var_abrir.get())
                         ).pack(anchor="w", pady=(0, 12))

        def _tarjeta(titulo, descripcion, comando):
            c = tk.Frame(pad, bg=CARD_BG, relief="solid", bd=1, cursor="hand2")
            c.pack(fill="x", pady=4)
            tk.Label(c, text=titulo, bg=CARD_BG, fg=TXT_PRI,
                     font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
            tk.Label(c, text=descripcion, bg=CARD_BG, fg=TXT_DIM,
                     font=("Segoe UI", 8), wraplength=400, justify="left").pack(
                         anchor="w", padx=12, pady=(0, 8))

            def _click(_e=None, fn=comando):
                win.destroy()
                fn(abrir_al_terminar=var_abrir.get())
            c.bind("<Button-1>", _click)
            for w in c.winfo_children():
                w.bind("<Button-1>", _click)

        _tarjeta("📄 Copia exacta", "PDF buscable: imagen de cada página + capa de "
                 "texto invisible (búsqueda y copiar/pegar). Estilo FineReader.",
                 self._exp_pdf_buscable)
        _tarjeta("🎓 Edición académica", "XML-TEI P5 + BibTeX del corpus (pide destino "
                 "para cada uno).", self._exp_edicion_academica)
        _tarjeta("📊 Datos de análisis", "Excel completo (10 hojas) con todo lo "
                 "generado en Análisis/Visualizar.", self._exp_datos_analisis)
        _tarjeta("📝 Texto plano", "Todo el corpus concatenado en un único .md/.txt.",
                 self._exp_texto_plano)

    def _exp_resolver_imagen(self, numero: str, pagina: str) -> "Path | None":
        """Busca la imagen original de una página en 02_imagenes/<numero>/."""
        if not ST.out_dir:
            return None
        img_dir = Path(ST.out_dir) / "02_imagenes" / str(numero)
        if not img_dir.exists():
            return None
        for ext in ("png", "jpg", "jpeg", "tif", "tiff"):
            hits = sorted(img_dir.glob(f"*{pagina}*.{ext}"))
            if hits:
                return hits[0]
        return None

    def _exp_pdf_buscable(self, abrir_al_terminar: bool = True):
        if ST.corpus_meta is None or ST.corpus_meta.empty:
            messagebox.showwarning("Sin datos",
                "No hay páginas con OCR. Ejecuta Extracción OCR primero.")
            return
        dest = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
            initialfile="corpus_buscable.pdf", title="Guardar PDF buscable")
        if not dest:
            return
        threading.Thread(target=self._exp_pdf_worker,
                         args=(dest, abrir_al_terminar), daemon=True).start()

    def _exp_pdf_worker(self, dest: str, abrir_al_terminar: bool):
        from core.pdf_export import exportar_pdf_buscable

        paginas = []
        for _, row in ST.corpus_meta.iterrows():
            numero, pagina = str(row.get("numero", "")), str(row.get("pagina", ""))
            img_path = self._exp_resolver_imagen(numero, pagina)
            if not img_path:
                continue
            texto = ""
            tp = row.get("txt_path")
            if tp and Path(tp).exists():
                try:
                    texto = Path(tp).read_text("utf-8", errors="replace")
                except Exception:
                    texto = ""
            paginas.append({"img_path": img_path, "texto": texto})

        if not paginas:
            self.after(0, lambda: messagebox.showwarning("Sin imágenes",
                "No se encontraron imágenes de página en 02_imagenes/ para exportar."))
            return

        prog_win = tk.Toplevel(self)
        prog_win.title("Generando PDF buscable…")
        prog_win.geometry("360x90")
        tk.Label(prog_win, text="Generando PDF buscable…").pack(pady=(14, 4))
        bar = ttk.Progressbar(prog_win, mode="determinate", maximum=len(paginas))
        bar.pack(fill="x", padx=16)
        lbl = tk.Label(prog_win, text=f"0/{len(paginas)}")
        lbl.pack(pady=6)

        def cb(n, total):
            self.after(0, lambda: (bar.config(value=n), lbl.config(text=f"{n}/{total}")))

        try:
            exportar_pdf_buscable(paginas, dest, callback=cb)
            self.after(0, prog_win.destroy)
            self.after(0, lambda: self.toast(
                f"✅ PDF buscable exportado: {len(paginas)} páginas", "ok"))
            if abrir_al_terminar:
                self.after(0, lambda: plataforma.abrir_en_sistema(dest))
        except Exception as e:
            self.after(0, prog_win.destroy)
            self.after(0, lambda err=str(e): messagebox.showerror("Error", err))

    def _exp_edicion_academica(self, abrir_al_terminar: bool = True):
        self._res_exportar_tei()
        self._res_exportar_bibtex()

    def _exp_datos_analisis(self, abrir_al_terminar: bool = True):
        self._gen_excel()

    def _exp_texto_plano(self, abrir_al_terminar: bool = True):
        corpus_txt = getattr(ST, "corpus_txt", []) or []
        if not corpus_txt:
            messagebox.showwarning("Sin corpus", "Extrae el texto del corpus primero.")
            return
        dest = filedialog.asksaveasfilename(
            defaultextension=".md", filetypes=[("Markdown", "*.md"), ("Texto", "*.txt")],
            initialfile="corpus_completo.md", title="Guardar texto plano")
        if not dest:
            return
        try:
            contenido = "\n\n---\n\n".join(
                f"## Artículo {i:04d}\n\n{t}" for i, t in enumerate(corpus_txt))
            Path(dest).write_text(contenido, encoding="utf-8")
            self.toast(f"✅ Texto plano exportado: {len(corpus_txt)} artículos", "ok")
            if abrir_al_terminar:
                plataforma.abrir_en_sistema(dest)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _res_exportar_tei(self):
        """Exporta corpus XML-TEI P5 desde el panel Resultados."""
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            defaultextension=".xml",
            filetypes=[("XML-TEI", "*.xml"), ("Todos", "*.*")],
            initialfile="corpus_estampa_tei.xml",
            title="Exportar XML-TEI")
        if not dest:
            return
        corpus_txt = getattr(ST, "corpus_txt", []) or []
        ner_global = getattr(ST, "indice_ner_global", {}) or {}
        if not corpus_txt:
            messagebox.showwarning("Sin corpus", "Extrae el texto del corpus primero.")
            return
        from core.servicios_exportacion import articulos_para_tei
        articulos = articulos_para_tei(corpus_txt, ner_global)
        try:
            from pathlib import Path as _PPath

            from core.tei_engine import exportar_corpus_tei
            proyecto = getattr(ST, "proyecto_nombre", "Corpus Estampa")
            exportar_corpus_tei(articulos, _PPath(dest),
                                proyecto_nombre=proyecto)
            messagebox.showinfo("Exportado", f"✅ XML-TEI exportado:\n{dest}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _res_exportar_pptx(self):
        """Exporta presentación PowerPoint con resultados del corpus."""
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            title="Guardar presentación PowerPoint",
            defaultextension=".pptx",
            filetypes=[("PowerPoint", "*.pptx"), ("Todos", "*.*")],
        )
        if not dest:
            return
        import threading
        threading.Thread(target=self._res_exportar_pptx_worker, args=(dest,), daemon=True).start()

    def _res_exportar_pptx_worker(self, dest):
        try:
            from pathlib import Path

            from exportadores.exportar_pptx import exportar_presentacion
            # Los nombres ST.topicos_resultado / ST.narrativa_corpus no existen
            # en core/estado.py y nunca se asignan: el getattr los tapaba y la
            # presentación salía siempre sin tópicos, sin métricas de red y sin
            # narrativa. Se leen los atributos reales del estado.
            temas = getattr(ST, "temas_lda", None) or []
            datos = {
                "articulos": {},
                "indice_ner_global": ST.indice_ner_global,
                "topicos": {"topicos": {
                    str(i): (t if isinstance(t, dict) else {"palabras": [str(t)]})
                    for i, t in enumerate(temas)}} if temas else {},
                "metricas_red": getattr(ST, "metricas_red", {}) or {},
                "estadisticas_tono": getattr(ST, "estadisticas_tono", {}) or {},
                "narrativa": getattr(ST, "narrativa_corpus", "") or "",
            }
            if ST.df_articulos is not None:
                for _, row in ST.df_articulos.iterrows():
                    aid = str(row.get("id", row.name))
                    # 'paginas' es la columna real del segmentador; sin ella la
                    # diapositiva de estadísticas informaba siempre 0 páginas.
                    pags = row.get("paginas", "")
                    if not isinstance(pags, (list, tuple)):
                        pags = [p for p in str(pags or "").split(",") if p.strip()]
                    datos["articulos"][aid] = {
                        "texto_limpio": str(row.get("texto", "")),
                        "paginas": list(pags),
                    }
            exportar_presentacion(
                datos, Path(dest),
                titulo_proyecto=ST.publicacion,
                investigador=getattr(ST, "investigador", ""),
                institucion=getattr(ST, "institucion", "Instituto Caro y Cuervo"),
            )
            ST.pptx_path = dest
            self.after(0, lambda: __import__("tkinter.messagebox", fromlist=["showinfo"]).showinfo(
                "PowerPoint", f"✅ Presentación guardada:\n{dest}"))
        except ImportError:
            self.after(0, lambda: __import__("tkinter.messagebox", fromlist=["showerror"]).showerror(
                "PowerPoint", "Instala python-pptx: pip install python-pptx"))
        except Exception as e:
            self.after(0, lambda err=e: __import__("tkinter.messagebox", fromlist=["showerror"]).showerror(
                "PowerPoint", str(err)))

    def _res_exportar_bibtex(self):
        """Exporta BibTeX del corpus."""
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            defaultextension=".bib",
            filetypes=[("BibTeX", "*.bib"), ("Todos", "*.*")],
            initialfile="corpus_estampa.bib",
            title="Exportar BibTeX")
        if not dest:
            return
        corpus_txt = getattr(ST, "corpus_txt", []) or []
        if not corpus_txt:
            messagebox.showwarning("Sin corpus", "Extrae el texto del corpus primero.")
            return
        articulos = [{"id": f"art_{i:04d}", "texto": t} for i, t in enumerate(corpus_txt)]
        try:
            from pathlib import Path as _PPath

            from core.tei_engine import exportar_bibtex
            exportar_bibtex(articulos, _PPath(dest))
            messagebox.showinfo("Exportado", f"✅ BibTeX exportado:\n{dest}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _res_exportar_json_observable(self):
        """Exporta datos en JSON para Observable / Flourish."""
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
            initialfile="corpus_observable.json",
            title="Exportar JSON para Observable/Flourish")
        if not dest:
            return
        import json as _json
        ner = getattr(ST, "indice_ner_global", {}) or {}
        grafo = getattr(self, "_grafo_actual", None)
        datos = {
            "proyecto": getattr(ST, "proyecto_nombre", "Corpus Estampa"),
            "n_articulos": len(getattr(ST, "corpus_txt", []) or []),
            "entidades": {
                cat: [{"entidad": e, "n_articulos": len(arts)}
                      for e, arts in sorted(ents.items(), key=lambda x: -len(x[1]))[:50]]
                for cat, ents in ner.items()
            },
            "red": {
                "nodos": [{"id": n, **d} for n, d in grafo.nodes(data=True)]
                if grafo else [],
                "aristas": [{"source": u, "target": v, "peso": d.get("weight", 1)}
                             for u, v, d in grafo.edges(data=True)]
                if grafo else [],
            },
        }
        try:
            with open(dest, "w", encoding="utf-8") as f:
                _json.dump(datos, f, ensure_ascii=False, indent=2, default=str)
            messagebox.showinfo("Exportado", f"✅ JSON exportado:\n{dest}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _res_generar_methods(self):
        """Genera METHODS.md con descripción metodológica completa."""
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown","*.md"),("Texto","*.txt")],
            initialfile="METHODS.md",
            title="Guardar sección de metodología")
        if not dest:
            return
        try:
            from core.methods_reporter import generar_methods_md
            from core.servicios_exportacion import config_methods, estadisticas_methods
            ruta = generar_methods_md(config_methods(ST, APP_VERSION),
                                      estadisticas_methods(ST), Path(dest))
            messagebox.showinfo("METHODS.md generado",
                                f"✅ Sección de metodología guardada:\n{ruta}\n\n"
                                f"Revisa y complementa antes de publicar.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _res_validar_tei(self):
        """Valida el último XML-TEI exportado."""
        from tkinter import filedialog
        ruta = filedialog.askopenfilename(
            title="Seleccionar XML-TEI para validar",
            filetypes=[("XML-TEI", "*.xml"), ("Todos", "*.*")])
        if not ruta:
            return
        try:
            from core.tei_engine import validar_tei
            errores = validar_tei(Path(ruta))
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        if not errores:
            messagebox.showinfo("TEI válido ✅",
                                f"El archivo es un XML-TEI P5 válido.\n\n{ruta}")
        else:
            resumen = "\n".join(f"• {e}" for e in errores[:10])
            messagebox.showwarning("Problemas encontrados",
                                   f"{len(errores)} problema(s):\n\n{resumen}\n\n{ruta}")

    def _res_paquete_publicacion(self):
        """Genera ZIP con todos los artefactos para publicación académica."""
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP", "*.zip")],
            initialfile=f"paquete_publicacion_{datetime.now().strftime('%Y%m%d')}.zip",
            title="Guardar paquete de publicación")
        if not dest:
            return
        self._lbl_excel.config(text="⏳ Generando paquete…")
        threading.Thread(
            target=self._worker_paquete_publicacion,
            args=(dest,), daemon=True).start()

    def _worker_paquete_publicacion(self, dest_zip: str):
        import json as _json
        import shutil
        import tempfile
        import zipfile
        from pathlib import Path as _PPath

        tmp = _PPath(tempfile.mkdtemp(prefix="bashkar_pub_"))
        errores = []
        contenido: list[str] = []   # lo que de verdad quedó en el ZIP

        def _log(msg):
            self.after(0, lambda m=msg: self._lbl_excel.config(text=f"⏳ {m}"))

        try:
            # 1. XML-TEI
            _log("Exportando TEI…")
            try:
                from core.servicios_exportacion import articulos_para_tei
                from core.tei_engine import exportar_corpus_tei
                corpus_txt = getattr(ST, "corpus_txt", []) or []
                arts_tei = articulos_para_tei(
                    corpus_txt, getattr(ST, "indice_ner_global", {}) or {})
                if arts_tei:
                    # Antes pasaba titulo=/fecha=, que la función no acepta: el
                    # TypeError dejaba el paquete SIEMPRE sin corpus.xml.
                    exportar_corpus_tei(
                        arts_tei, tmp / "corpus.xml",
                        proyecto_nombre=getattr(ST, "publicacion", "") or "Corpus",
                        investigador=getattr(ST, "investigador", "") or "Investigador",
                        institucion=getattr(ST, "institucion", "") or "",
                    )
            except Exception as e:
                errores.append(f"TEI: {e}")

            # 2. BibTeX
            _log("Exportando BibTeX…")
            try:
                from core.tei_engine import exportar_bibtex
                corpus_txt = getattr(ST, "corpus_txt", []) or []
                arts_bib = [{"id": f"art_{i:04d}", "texto": t}
                            for i, t in enumerate(corpus_txt)]
                if arts_bib:
                    exportar_bibtex(arts_bib, tmp / "corpus.bib")
            except Exception as e:
                errores.append(f"BibTeX: {e}")

            # 3. CSV entidades
            _log("Exportando entidades CSV…")
            try:
                from core.ner_engine import exportar_csv as _ner_csv
                ner = getattr(ST, "indice_ner_global", {}) or {}
                if ner:
                    _ner_csv(ner, tmp / "entidades.csv")
            except Exception as e:
                errores.append(f"CSV NER: {e}")

            # 4. Bitácora Markdown
            _log("Exportando bitácora…")
            try:
                eng = self._bitacora_engine()
                if eng is not None:
                    eng.exportar_markdown(
                        tmp / "bitacora.md",
                        publicacion=getattr(ST, "publicacion", ""))
            except Exception as e:
                errores.append(f"Bitácora: {e}")

            # 5. Metadatos JSON
            _log("Escribiendo metadatos…")
            meta = {
                "publicacion":   getattr(ST, "publicacion", ""),
                "periodo":       getattr(ST, "periodo", ""),
                "investigador":  getattr(ST, "investigador", ""),
                "institucion":   getattr(ST, "institucion", ""),
                "fecha_export":  datetime.now().isoformat(),
                "bashkar_version": APP_VERSION,
                "n_archivos":    len(getattr(ST, "archivos_sel", []) or []),
                "modulos_usados": [k for k, v in ST.estado_etapas.items() if v == "ready"],
            }
            (tmp / "metadatos.json").write_text(
                _json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

            # 6. METHODS.md
            _log("Generando METHODS.md…")
            try:
                from core.methods_reporter import generar_methods_md
                from core.servicios_exportacion import (
                    config_methods,
                    estadisticas_methods,
                )
                generar_methods_md(config_methods(ST, APP_VERSION),
                                   estadisticas_methods(ST), tmp / "METHODS.md")
            except Exception as e:
                errores.append(f"METHODS.md: {e}")

            # 7. Empaquetar ZIP
            _log("Comprimiendo…")
            with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in tmp.rglob("*"):
                    if f.is_file():
                        zf.write(f, f.relative_to(tmp))
                        if not f.name.endswith(".proveniencia.json"):
                            contenido.append(f.relative_to(tmp).as_posix())

        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        def _fin():
            esperados = {"corpus.xml", "corpus.bib", "entidades.csv",
                         "bitacora.md", "METHODS.md", "metadatos.json"}
            faltan = sorted(esperados - set(contenido))
            if faltan and not errores:
                # Nada falló, pero no había datos para esas piezas: decirlo.
                errores.append("Sin datos para: " + ", ".join(faltan))
            if errores:
                self._lbl_excel.config(
                    text=f"⚠ Paquete con {len(errores)} advertencias")
                messagebox.showwarning(
                    "Paquete generado (con advertencias)",
                    f"ZIP guardado en:\n{dest_zip}\n\n"
                    f"Advertencias:\n" + "\n".join(f"• {e}" for e in errores))
            else:
                self._lbl_excel.config(text="✅ Paquete de publicación listo")
                messagebox.showinfo(
                    "Paquete listo ✅",
                    f"Paquete generado exitosamente:\n{dest_zip}\n\n"
                    "Contiene: " + " · ".join(sorted(contenido)))
            plataforma.abrir_en_sistema(Path(dest_zip).parent)
        self.after(0, _fin)
