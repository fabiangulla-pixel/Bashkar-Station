"""paneles/analisis.py — Métodos de BashkarApp extraídos de app.py.

Mixin: BashkarApp hereda de PanelAnalisis. Los cuerpos son copia literal del
original. Importa explícitamente lo que usa; los colores del tema se
leen de gui_comun.TEMA porque cambian en caliente.
"""

from __future__ import annotations

import gc
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from core import plataforma
from gui_comun import (
    CAMPOS_DEFAULT,
    PALETTE,
    ST,
    TEMA,
    _resolver_api_key_modelo,
)


class PanelAnalisis:
    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3: SEGMENTACIÓN DE ARTÍCULOS
    # ══════════════════════════════════════════════════════════════════════════
    def _build_seg(self):
        f = self._tab_seg
        self._page_header(f, "Segmentación de artículos",
                          "Identifica artículos y asigna autoría por bylines y firmas", "📝")
        self._build_ai_panel(f, "seg")
        pad = tk.Frame(f, bg=TEMA.CONTENT_BG); pad.pack(fill="both", expand=True, padx=24, pady=16)

        # ── Barra de acción fija (siempre visible) ────────────────────────────
        bf = tk.Frame(pad, bg=TEMA.CONTENT_BG); bf.pack(fill="x", pady=(0, 8))
        self._btn_seg = ttk.Button(bf, text="▶  Segmentar artículos",
                                    style="P.TButton", command=self._start_seg)
        self._btn_seg.pack(side="left", padx=(0,12))
        self._var_seg_v2 = tk.BooleanVar(value=True)
        ttk.Checkbutton(bf, text="Segmentador avanzado (v2)",
                        variable=self._var_seg_v2).pack(side="left", padx=(0, 12))
        self._lbl_seg_n = tk.Label(bf, text="", bg=TEMA.CONTENT_BG, fg=TEMA.VERDE,
                                    font=("Segoe UI",10,"bold"))
        self._lbl_seg_n.pack(side="left", padx=8)
        ttk.Button(bf, text="💾 Exportar CSV", style="S.TButton",
                   command=self._export_seg_csv).pack(side="left", padx=8)
        ttk.Button(bf, text="📄 Exportar DOCX (con costura)", style="S.TButton",
                   command=self._export_seg_docx_costura).pack(side="left", padx=4)
        tk.Label(bf, text="⚠  Requiere extracción completada",
                 bg=TEMA.CONTENT_BG, fg=TEMA.ACENT, font=("Segoe UI",9)).pack(side="left", padx=8)
        ttk.Button(bf, text="📓 Nota", style="S.TButton",
                   command=lambda: self._bitacora_nueva_nota("seg")).pack(side="right")

        # Progressive disclosure — opciones avanzadas de segmentación
        def _build_seg_avanzado(f):
            row1 = tk.Frame(f, bg=TEMA.CONTENT_BG); row1.pack(fill="x", pady=2)
            tk.Label(row1, text="Umbral confianza autoría:", bg=TEMA.CONTENT_BG,
                     fg=TEMA.TXT_SEC, font=("Segoe UI",8)).pack(side="left")
            self._var_seg_umbral = tk.DoubleVar(value=0.4)
            ttk.Scale(row1, from_=0.1, to=0.9, variable=self._var_seg_umbral,
                      orient="horizontal", length=120).pack(side="left", padx=6)
            tk.Label(row1, textvariable=self._var_seg_umbral, bg=TEMA.CONTENT_BG,
                     fg=TEMA.TXT_SEC, font=("Segoe UI",8), width=4).pack(side="left")
            row2 = tk.Frame(f, bg=TEMA.CONTENT_BG); row2.pack(fill="x", pady=2)
            self._var_seg_max_art = tk.IntVar(value=0)
            tk.Label(row2, text="Máx. artículos por número (0=sin límite):",
                     bg=TEMA.CONTENT_BG, fg=TEMA.TXT_SEC, font=("Segoe UI",8)).pack(side="left")
            ttk.Spinbox(row2, from_=0, to=200, textvariable=self._var_seg_max_art,
                        width=5).pack(side="left", padx=6)
        self._mk_avanzado(pad, "Opciones avanzadas de segmentación", _build_seg_avanzado)

        cols = ("Número", "Título", "Autor", "Confianza", "Sección", "Páginas", "Palabras")
        anchos = {"Número":140,"Título":340,"Autor":180,"Confianza":75,
                  "Sección":110,"Páginas":110,"Palabras":75}
        tv_outer = tk.Frame(pad, bg=TEMA.CARD_BG, relief="solid", bd=1)
        tv_outer.pack(fill="both", expand=True)
        self._tv_seg_outer = tv_outer   # para skeleton
        self._seg_skeleton = None
        sb_y = ttk.Scrollbar(tv_outer, orient="vertical")
        sb_x = ttk.Scrollbar(tv_outer, orient="horizontal")
        self._tv_seg = ttk.Treeview(tv_outer, columns=cols, show="headings",
                                     yscrollcommand=sb_y.set, xscrollcommand=sb_x.set, height=13)
        for col in cols:
            self._tv_seg.heading(col, text=col, anchor="w",
                                  command=lambda c=col: self._sort_tv_seg(c))
            self._tv_seg.column(col, width=anchos[col], minwidth=50, stretch=False)
        self._tv_seg.tag_configure("alta",    background="#15251F", foreground="#6EC69A")
        self._tv_seg.tag_configure("media",   background="#2A2116", foreground="#D58B45")
        self._tv_seg.tag_configure("anonimo", background="#171C20", foreground="#777F84")
        sb_y.config(command=self._tv_seg.yview)
        sb_x.config(command=self._tv_seg.xview)
        sb_y.pack(side="right", fill="y")
        sb_x.pack(side="bottom", fill="x")
        self._tv_seg.pack(fill="both", expand=True)
        self._tv_seg.bind("<<TreeviewSelect>>", self._on_seg_select)
        self._tv_seg_sort_rev = {c: False for c in cols}

        ley_f = tk.Frame(pad, bg=TEMA.CONTENT_BG); ley_f.pack(anchor="w", pady=(4, 0))
        # Pastillas de estado: fondo tintado oscuro + texto del color de la
        # señal. Antes eran chips claros con texto oscuro, herencia del tema
        # claro original, y desentonaban con el resto de la interfaz.
        for bg_, fg_, txt in [(TEMA.READY_BG, TEMA.VERDE,     "  ✓ Autoría identificada  "),
                               (TEMA.WARN_BG,  TEMA.ACENT,    "  ≈ Confianza media  "),
                               (TEMA.CARD_BG,  TEMA.TXT_DIM,  "  — Anónimo  ")]:
            tk.Label(ley_f, text=txt, bg=bg_, fg=fg_,
                     font=("Segoe UI",8), relief="solid", bd=1).pack(side="left", padx=3)

        det_outer = tk.Frame(pad, bg=TEMA.CARD_BOR, relief="solid", bd=1)
        det_outer.pack(fill="x", pady=(10,0))
        det_hdr = tk.Frame(det_outer, bg="#171C20"); det_hdr.pack(fill="x")
        tk.Label(det_hdr, text="  📄  Texto del artículo seleccionado",
                 bg="#171C20", fg=TEMA.TXT_PRI, font=("Segoe UI",8,"bold")).pack(side="left", pady=4)
        self._txt_seg_art = scrolledtext.ScrolledText(det_outer, height=6, font=("Consolas",9), bg="#0E1114", fg="#E8E5DF", relief="flat", state="disabled", wrap="word")
        self._txt_seg_art.pack(fill="x", padx=1, pady=(0,1))

    def _export_seg_csv(self):
        if ST.df_articulos is None or ST.df_articulos.empty:
            messagebox.showwarning("Sin datos","Ejecuta la segmentación primero."); return
        dest = filedialog.asksaveasfilename(defaultextension=".csv",
               filetypes=[("CSV","*.csv")], initialfile="articulos_segmentados.csv")
        if dest:
            ST.df_articulos.drop(columns=["texto"],errors="ignore").to_csv(dest, index=False, encoding="utf-8-sig")
            self.toast(f"CSV guardado → {Path(dest).name}", tipo="ok")

    def _export_seg_docx_costura(self):
        """Exporta artículos a DOCX con palabras de costura marcadas en rojo."""
        articulos = getattr(ST, "articulos", None) or []
        if not articulos:
            messagebox.showwarning("Sin datos", "Segmenta el corpus primero."); return
        dest = filedialog.asksaveasfilename(
            defaultextension=".docx",
            filetypes=[("Word DOCX", "*.docx")],
            initialfile="corpus_con_costura.docx",
            title="Exportar DOCX con marcas de costura")
        if not dest:
            return
        try:
            from docx import Document
            from docx.shared import Pt, RGBColor

            from core.gutter_completion import RE_GENERADO, exportar_docx_con_marcas
        except ImportError:
            messagebox.showerror("Falta python-docx", "pip install python-docx"); return

        doc = Document()
        n_marcadas = 0
        for art in articulos:
            texto = art.get("texto", "") or ""
            titulo = art.get("titulo", "Sin título")
            doc.add_heading(titulo, level=2)
            # Detectar si tiene marcas de costura
            if RE_GENERADO.search(texto):
                # Renderizar con marcas rojas
                segmentos = RE_GENERADO.split(texto)
                p = doc.add_paragraph()
                for j, seg in enumerate(segmentos):
                    if not seg:
                        continue
                    run = p.add_run(seg)
                    if j % 2 == 1:
                        run.font.color.rgb = RGBColor(0xEF, 0x44, 0x44)
                        run.bold = True
                        n_marcadas += 1
            else:
                doc.add_paragraph(texto)
            doc.add_paragraph()

        doc.save(dest)
        messagebox.showinfo("Exportado",
            f"DOCX guardado en:\n{dest}\n\n"
            f"Palabras reconstruidas marcadas en rojo: {n_marcadas}")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 4: ANÁLISIS TEXTUAL
    # ══════════════════════════════════════════════════════════════════════════
    def _build_anal(self):
        f = self._tab_anal
        self._page_header(f, "Análisis textual y semántico",
                          "NER · LDA · campos semánticos · Word2Vec · red de autoría", "🔍")
        self._build_ai_panel(f, "anal")
        pad = tk.Frame(f, bg=TEMA.CONTENT_BG); pad.pack(fill="both", expand=True, padx=24, pady=16)

        # ── Barra de acción fija ──────────────────────────────────────────────
        bf_an = tk.Frame(pad, bg=TEMA.CONTENT_BG); bf_an.pack(fill="x", pady=(0, 8))
        self._btn_anal = ttk.Button(bf_an, text="▶  Iniciar análisis textual",
                                     style="P.TButton", command=self._start_anal)
        self._btn_anal.pack(side="left", padx=(0,12))
        tk.Label(bf_an, text="⚠  Requiere extracción completada",
                 bg=TEMA.CONTENT_BG, fg=TEMA.ACENT, font=("Segoe UI",9)).pack(side="left")
        ttk.Button(bf_an, text="📓 Nota", style="S.TButton",
                   command=lambda: self._bitacora_nueva_nota("anal")).pack(side="right")

        self._lbl_fase_a = tk.Label(pad, text="Esperando…",
                                     bg=TEMA.CONTENT_BG, fg="#777F84",
                                     font=("Segoe UI",9,"italic"))
        self._lbl_fase_a.pack(anchor="w")
        self._prog_a = ttk.Progressbar(pad, mode="determinate", length=600)
        self._prog_a.pack(fill="x", pady=(6,4))
        self._lbl_pct_a = tk.Label(pad, text="", bg=TEMA.CONTENT_BG, fg="#777F84",
                                    font=("Courier",8))
        self._lbl_pct_a.pack(anchor="w")

        log_frame = tk.Frame(pad, bg="#12171B", bd=1, relief="solid")
        log_frame.pack(fill="both", expand=True, pady=(12,0))
        log_hdr = tk.Frame(log_frame, bg="#14202A"); log_hdr.pack(fill="x")
        tk.Label(log_hdr, text="  📋  Registro", bg="#14202A", fg="#B5B6B3",
                 font=("Segoe UI",8,"bold")).pack(side="left", pady=4)
        self._log_a = scrolledtext.ScrolledText(log_frame, height=14,
                                                 font=("Consolas",9), bg="#12171B",
                                                 fg="#6EC69A", relief="flat",
                                                 insertbackground="white")
        self._log_a.pack(fill="both", expand=True, padx=1, pady=(0,1))
        self._log_a.config(state="disabled")

        # Inicializar vars antes de que _mk_avanzado las construya lazy
        self._var_nt         = tk.IntVar(value=2)
        self._var_mf         = tk.IntVar(value=3)
        self._var_wv         = tk.BooleanVar(value=False)
        self._var_campo_exp  = tk.StringVar(value=list(CAMPOS_DEFAULT.keys())[0])
        self._txt_exp_res    = None  # se crea dentro del lazy builder

        def _build_anal_params(frame):
            p2 = tk.Frame(frame, bg=TEMA.CARD_BG, padx=16, pady=10)
            p2.pack(fill="x")
            # N-gramas
            row_ng = tk.Frame(p2, bg=TEMA.CARD_BG); row_ng.pack(anchor="w", pady=3)
            tk.Label(row_ng, text="N-gramas máx.:", bg=TEMA.CARD_BG, fg="#E8E5DF",
                     font=("Segoe UI",9,"bold"), width=16, anchor="w").pack(side="left")
            tk.Spinbox(row_ng, from_=1, to=4, textvariable=self._var_nt,
                       width=4, font=("Segoe UI",10), relief="solid", bd=1).pack(side="left", padx=6)
            tk.Label(row_ng, text="(1=unigramas, 2=bigramas, etc.)", bg=TEMA.CARD_BG,
                     fg="#646D72", font=("Segoe UI",8)).pack(side="left", padx=4)
            # Frecuencia mínima
            row_mf = tk.Frame(p2, bg=TEMA.CARD_BG); row_mf.pack(anchor="w", pady=3)
            tk.Label(row_mf, text="Frec. mínima:", bg=TEMA.CARD_BG, fg="#E8E5DF",
                     font=("Segoe UI",9,"bold"), width=16, anchor="w").pack(side="left")
            tk.Spinbox(row_mf, from_=1, to=20, textvariable=self._var_mf,
                       width=4, font=("Segoe UI",10), relief="solid", bd=1).pack(side="left", padx=6)
            tk.Label(row_mf, text="apariciones mínimas para incluir en vocabulario", bg=TEMA.CARD_BG,
                     fg="#646D72", font=("Segoe UI",8)).pack(side="left", padx=4)
            # Word2Vec
            row_wv = tk.Frame(p2, bg=TEMA.CARD_BG); row_wv.pack(anchor="w", pady=3)
            ttk.Checkbutton(row_wv, text="🧠  Entrenar Word2Vec (expansión semántica automática de campos)",
                            variable=self._var_wv).pack(side="left")

        def _build_anal_exp(frame):
            exp_inner = tk.Frame(frame, bg=TEMA.CARD_BG, padx=16, pady=10)
            exp_inner.pack(fill="x")
            exp_ctrl = tk.Frame(exp_inner, bg=TEMA.CARD_BG); exp_ctrl.pack(anchor="w")
            tk.Label(exp_ctrl, text="Campo:", bg=TEMA.CARD_BG, fg="#E8E5DF",
                     font=("Segoe UI",9,"bold")).pack(side="left")
            campo_cmb = ttk.Combobox(exp_ctrl, textvariable=self._var_campo_exp,
                                      values=list(CAMPOS_DEFAULT.keys()),
                                      state="readonly", width=20, font=("Segoe UI",9))
            campo_cmb.pack(side="left", padx=8)
            ttk.Button(exp_ctrl, text="Explorar →", style="S.TButton",
                       command=self._explorar_expansion).pack(side="left")
            self._txt_exp_res = scrolledtext.ScrolledText(
                exp_inner, height=4, font=("Consolas",9),
                bg="#0E1114", fg="#E8E5DF", relief="solid", bd=1, state="disabled")
            self._txt_exp_res.pack(fill="x", pady=(8,0))

        self._mk_avanzado(pad, "⚙  Parámetros del análisis", _build_anal_params)
        self._mk_avanzado(pad, "🔎  Expansión semántica (requiere Word2Vec)", _build_anal_exp)

    # TAB 5: ANÁLISIS VISUAL Y TIPOGRÁFICO
    # ══════════════════════════════════════════════════════════════════════════
    def _build_vis(self):
        f = self._tab_vis
        self._page_header(f, "Análisis visual y tipográfico",
                          "Fuentes tipográficas · imágenes detectadas · diagrama de layout", "🖼")
        self._build_ai_panel(f, "vis")
        # Sub-pestañas con botones propios (no ttk.Notebook para mantener estilo)
        top = tk.Frame(f, bg=TEMA.CONTENT_BG); top.pack(fill="x", padx=24, pady=(12,0))
        self._vis_tabs_btns = {}
        for i, (tid, label) in enumerate([("tip","🔤 Tipografía"),
                                           ("ele","📷 Imágenes"),
                                           ("diag","📐 Diagrama")]):
            btn = tk.Label(top, text=f"  {label}  ", bg=TEMA.CARD_BOR if i > 0 else TEMA.AZ3,
                           fg="white" if i == 0 else "#646D72",
                           font=("Segoe UI",9,"bold"), cursor="hand2",
                           padx=10, pady=6, relief="flat")
            btn.pack(side="left", padx=(0,2))
            self._vis_tabs_btns[tid] = btn
        tk.Frame(f, bg=TEMA.CARD_BOR, height=1).pack(fill="x")

        # Frames de sub-contenido
        self._vis_frames = {}
        for tid in ("tip","ele","diag"):
            frm = tk.Frame(f, bg=TEMA.CONTENT_BG)
            self._vis_frames[tid] = frm

        self._tab_vis_tip  = self._vis_frames["tip"]
        self._tab_vis_ele  = self._vis_frames["ele"]
        self._tab_vis_diag = self._vis_frames["diag"]

        self._build_vis_tip(); self._build_vis_ele(); self._build_vis_diag()

        for tid, btn in self._vis_tabs_btns.items():
            btn.bind("<Button-1>", lambda e, t=tid: self._vis_switch(t))

        # Botones de acción
        bf = tk.Frame(f, bg=TEMA.CONTENT_BG); bf.pack(fill="x", padx=24, pady=10)
        self._btn_vis = ttk.Button(bf, text="▶  Analizar visual y tipografía",
                                    style="P.TButton", command=self._start_vis)
        self._btn_vis.pack(side="left", padx=(0,12))
        self._lbl_vis_ok = tk.Label(bf, text="", bg=TEMA.CONTENT_BG, fg=TEMA.VERDE,
                                     font=("Segoe UI",10,"bold"))
        self._lbl_vis_ok.pack(side="left")
        tk.Label(bf, text="⚠  Requiere extracción completada",
                 bg=TEMA.CONTENT_BG, fg=TEMA.ACENT, font=("Segoe UI",9)).pack(side="left", padx=8)

        # Mostrar primera sub-pestaña
        self._vis_switch("tip")

    def _vis_switch(self, tid: str):
        for t, frm in self._vis_frames.items():
            frm.pack_forget()
        self._vis_frames[tid].pack(fill="both", expand=True)
        for t, btn in self._vis_tabs_btns.items():
            if t == tid:
                btn.config(bg=TEMA.AZ3, fg="white")
            else:
                btn.config(bg=TEMA.CARD_BOR, fg="#777F84")

    def _build_vis_tip(self):
        pad = self._tab_vis_tip
        cols = ("Número","Fuente principal","Clasificación","N fuentes","Cuerpo (pt)",
                "Título (pt)","Ratio T/C","Interlineado","Columnas","% Negrita","% Cursiva","Imgs.")
        widths = [110,160,130,70,80,80,60,80,70,70,70,50]
        tv_f = tk.Frame(pad, bg=TEMA.CONTENT_BG); tv_f.pack(fill="both", expand=True, padx=8, pady=8)
        sbv = ttk.Scrollbar(tv_f, orient="vertical")
        sbh = ttk.Scrollbar(tv_f, orient="horizontal")
        self._tv_tip = ttk.Treeview(tv_f, columns=cols, show="headings",
                                     yscrollcommand=sbv.set, xscrollcommand=sbh.set, height=14)
        for col, w in zip(cols, widths):
            self._tv_tip.heading(col, text=col, anchor="w")
            self._tv_tip.column(col, width=w, minwidth=40)
        sbv.config(command=self._tv_tip.yview); sbh.config(command=self._tv_tip.xview)
        sbv.pack(side="right", fill="y"); sbh.pack(side="bottom", fill="x")
        self._tv_tip.pack(fill="both", expand=True)
        # detalle de fuentes al hacer clic
        det_f = tk.Frame(pad, bg=TEMA.CARD_BG, relief="solid", bd=1); tk.Label(det_f, text="  Detalle de fuentes del número seleccionado", bg="#171C20", fg=TEMA.TXT_PRI, font=("Segoe UI",8,"bold")).pack(fill="x")
        det_f.pack(fill="x", padx=8, pady=(0,6))
        self._txt_tip_det = scrolledtext.ScrolledText(det_f, height=5, font=("Courier",9), bg="#0E1114", fg="#E8E5DF", relief="flat", state="disabled")
        self._txt_tip_det.pack(fill="x")
        self._tv_tip.bind("<<TreeviewSelect>>", self._on_tip_select)

    def _build_vis_ele(self):
        pad = self._tab_vis_ele
        cols = ("Número","Página","Tipo","Confianza","Ancho cm","Alto cm","Área cm²",
                "Pos X%","Pos Y%","Autor imagen","Pie de foto","Descripción IA")
        widths = [110,80,130,70,70,70,70,60,60,120,160,280]
        tv_f = tk.Frame(pad, bg=TEMA.CONTENT_BG); tv_f.pack(fill="both", expand=True, padx=8, pady=8)
        sbv = ttk.Scrollbar(tv_f, orient="vertical")
        sbh = ttk.Scrollbar(tv_f, orient="horizontal")
        self._tv_ele = ttk.Treeview(tv_f, columns=cols, show="headings",
                                     yscrollcommand=sbv.set, xscrollcommand=sbh.set, height=16)
        for col, w in zip(cols, widths):
            self._tv_ele.heading(col, text=col, anchor="w")
            self._tv_ele.column(col, width=w, minwidth=40)
        sbv.config(command=self._tv_ele.yview); sbh.config(command=self._tv_ele.xview)
        sbv.pack(side="right", fill="y"); sbh.pack(side="bottom", fill="x")
        self._tv_ele.pack(fill="both", expand=True)
        # Etiquetas de color por tipo
        self._tv_ele.tag_configure("foto",        background="#14202A", foreground="#6CA8E8")
        self._tv_ele.tag_configure("ilustracion", background="#15251F", foreground="#6EC69A")
        self._tv_ele.tag_configure("publicidad",  background="#2A2116", foreground="#D58B45")
        self._tv_ele.tag_configure("mixto",       background="#221C2E", foreground="#B18AD6")
        # Contador
        cnt_f = tk.Frame(pad, bg=TEMA.CONTENT_BG); cnt_f.pack(anchor="w", padx=8, pady=(0,4))
        self._lbl_ele_cnt = ttk.Label(cnt_f, text="", foreground="#777F84", font=("Segoe UI",9))
        self._lbl_ele_cnt.pack(side="left")
        ttk.Button(cnt_f, text="📥 Exportar CSV", style="S.TButton",
                   command=self._exportar_csv_imagenes).pack(side="left", padx=12)
        ttk.Button(cnt_f, text="🖼 Exportar imágenes recortadas", style="A.TButton",
                   command=self._exportar_imagenes_carpeta).pack(side="left", padx=4)

    def _build_vis_diag(self):
        pad = self._tab_vis_diag
        ctrl = tk.Frame(pad, bg=TEMA.CONTENT_BG); ctrl.pack(fill="x", padx=12, pady=8)
        ttk.Label(ctrl, text="Número:", font=("Segoe UI",10)).pack(side="left")
        self._var_diag_num = tk.StringVar()
        self._cmb_diag = ttk.Combobox(ctrl, textvariable=self._var_diag_num,
                                       state="readonly", width=30, font=("Segoe UI",10))
        self._cmb_diag.pack(side="left", padx=8)
        ttk.Label(ctrl, text="Página:", font=("Segoe UI",10)).pack(side="left")
        self._var_diag_pag = tk.StringVar()
        self._cmb_diag_pag = ttk.Combobox(ctrl, textvariable=self._var_diag_pag,
                                            state="readonly", width=14, font=("Segoe UI",10))
        self._cmb_diag_pag.pack(side="left", padx=8)
        self._cmb_diag.bind("<<ComboboxSelected>>", self._on_diag_num_sel)
        self._cmb_diag_pag.bind("<<ComboboxSelected>>", self._on_diag_pag_sel)
        ttk.Button(ctrl, text="📐 Mostrar diagrama", style="S.TButton",
                   command=self._mostrar_diagrama).pack(side="left", padx=8)
        # Canvas para la imagen
        self._canvas_diag = tk.Canvas(pad, bg=TEMA.CONTENT_BG, highlightthickness=0)
        self._canvas_diag.pack(fill="both", expand=True, padx=12, pady=4)
        self._diag_img_ref = None   # evitar GC de la imagen

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 6: ANÁLISIS COMPARATIVO
    # ══════════════════════════════════════════════════════════════════════════
    def _build_comp(self):
        f = self._tab_comp
        self._page_header(f, "Análisis comparativo",
                          "Compara el perfil temático con otras publicaciones del período", "📊")
        self._build_ai_panel(f, "comp")
        pad = tk.Frame(f, bg=TEMA.CONTENT_BG); pad.pack(fill="both", expand=True)
        # Sub-pestañas
        top = tk.Frame(pad, bg=TEMA.CONTENT_BG); top.pack(fill="x", padx=24, pady=(12,0))
        self._comp_tabs_btns = {}
        for i,(tid,label) in enumerate([("sim","🔁 Similaridad"),
                                         ("dist","🏷 Términos distintivos"),
                                         ("cam","📊 Campos semánticos")]):
            btn = tk.Label(top, text=f"  {label}  ",
                           bg=TEMA.AZ3 if i==0 else TEMA.CARD_BOR,
                           fg="white" if i==0 else "#646D72",
                           font=("Segoe UI",9,"bold"), cursor="hand2",
                           padx=10, pady=6)
            btn.pack(side="left", padx=(0,2))
            self._comp_tabs_btns[tid] = btn
        tk.Frame(pad, bg=TEMA.CARD_BOR, height=1).pack(fill="x")

        # ── Barra de acción fija ──────────────────────────────────────────────
        bf_comp = tk.Frame(pad, bg=TEMA.CONTENT_BG); bf_comp.pack(fill="x", padx=0, pady=(0,8))
        self._btn_comp = ttk.Button(bf_comp, text="▶  Ejecutar análisis comparativo",
                                     style="P.TButton", command=self._start_comp)
        self._btn_comp.pack(side="left", padx=(0,12))
        self._lbl_comp_ok = tk.Label(bf_comp, text="", bg=TEMA.CONTENT_BG, fg=TEMA.VERDE,
                                      font=("Segoe UI",10,"bold"))
        self._lbl_comp_ok.pack(side="left")
        tk.Label(bf_comp, text="⚠  Requiere corpus de referencia configurado",
                 bg=TEMA.CONTENT_BG, fg=TEMA.ACENT, font=("Segoe UI",9)).pack(side="left",padx=8)

        self._comp_frames = {}
        for tid in ("sim","dist","cam"):
            frm = tk.Frame(pad, bg=TEMA.CONTENT_BG)
            self._comp_frames[tid] = frm
        self._tab_c_sim  = self._comp_frames["sim"]
        self._tab_c_dist = self._comp_frames["dist"]
        self._tab_c_cam  = self._comp_frames["cam"]

        self._build_comp_sim(); self._build_comp_dist(); self._build_comp_cam()

        for tid, btn in self._comp_tabs_btns.items():
            btn.bind("<Button-1>", lambda e, t=tid: self._comp_switch(t))

        self._comp_switch("sim")

    def _comp_switch(self, tid: str):
        for t, frm in self._comp_frames.items():
            frm.pack_forget()
        self._comp_frames[tid].pack(fill="both", expand=True)
        for t, btn in self._comp_tabs_btns.items():
            btn.config(bg=TEMA.AZ3 if t==tid else TEMA.CARD_BOR,
                       fg="white" if t==tid else "#646D72")

    def _build_comp_sim(self):
        pad = self._tab_c_sim
        tk.Label(pad,text="Matriz de similaridad coseno (TF-IDF)",bg=TEMA.CONTENT_BG,fg=TEMA.TXT_PRI,font=("Segoe UI",10,"bold")).pack(anchor="w",padx=8,pady=6)
        self._txt_sim = scrolledtext.ScrolledText(pad, height=12, font=("Consolas",9), bg=TEMA.CARD_BG, fg="#E8E5DF", relief="flat")
        self._txt_sim.pack(fill="both",expand=True,padx=8,pady=4)

    def _build_comp_dist(self):
        pad = self._tab_c_dist
        tk.Label(pad,text="Palabras más distintivas de la publicación analizada",bg=TEMA.CONTENT_BG,fg=TEMA.TXT_PRI,font=("Segoe UI",10,"bold")).pack(anchor="w",padx=8,pady=6)
        self._txt_dist = scrolledtext.ScrolledText(pad, height=14, font=("Consolas",9), bg=TEMA.CARD_BG, fg="#E8E5DF", relief="flat")
        self._txt_dist.pack(fill="both",expand=True,padx=8,pady=4)

    def _build_comp_cam(self):
        pad = self._tab_c_cam
        tk.Label(pad,text="Perfil de campos semánticos por publicación",bg=TEMA.CONTENT_BG,fg=TEMA.TXT_PRI,font=("Segoe UI",10,"bold")).pack(anchor="w",padx=8,pady=6)
        # Figura embebida
        self._fig_cam_frame = tk.Frame(pad, bg=TEMA.CONTENT_BG); self._fig_cam_frame.pack(fill="both",expand=True,padx=8,pady=4)

    def _start_seg(self):
        if not ST.ocr_done:
            # Intentar reconstruir desde TXT del conversor antes de bloquear
            if not self._reconstruir_corpus_meta_desde_txt():
                messagebox.showwarning("Sin texto extraído",
                    "No se encontró texto en 03_ocr/.\n\n"
                    "Usá primero el Conversor PDF o la Extracción OCR.")
                return
        self._btn_seg.config(state="disabled")
        self._seg_skeleton = self._skeleton_show(self._tv_seg_outer, n_filas=8)
        threading.Thread(target=self._worker_seg, daemon=True).start()

    def _worker_seg(self):
        from core.article_segmenter import segmentar_numero
        from core.zone_labeler import (
            filtrar_texto_con_etiquetas,
            listar_paginas_etiquetadas,
        )
        usar_v2 = getattr(self, "_var_seg_v2", None)
        usar_v2 = usar_v2.get() if usar_v2 else False

        out     = ST.out_dir; txt_dir = out / "03_ocr"

        # Obtener lista de números desde corpus_meta si existe,
        # o desde las carpetas en 03_ocr/ si el texto vino del conversor.
        if ST.corpus_meta is not None and "numero" in ST.corpus_meta.columns:
            numeros = sorted(ST.corpus_meta["numero"].unique().tolist())
        elif txt_dir.exists():
            numeros = sorted(p.name for p in txt_dir.iterdir()
                             if p.is_dir() and list(p.glob("*.txt")))
        elif ST.archivos_sel:
            numeros = [a.stem for a in ST.archivos_sel]
        else:
            self._put(tipo="err",
                      txt="No hay texto extraído. Ejecutá primero Extracción OCR o el Conversor.")
            return

        if not numeros:
            self._put(tipo="err",
                      txt="No se encontraron números con texto en 03_ocr/.")
            return

        total   = len(numeros); todos = []

        for k, nombre in enumerate(numeros):
            self._put(tipo="fase", txt=f"Segmentando {nombre}…")
            etiq_pags = listar_paginas_etiquetadas(out, nombre)
            if etiq_pags:
                self._put(tipo="log", texto=f"  📌 {len(etiq_pags)} páginas con etiquetas de zona")
                carpeta_txt = txt_dir / nombre
                if carpeta_txt.exists():
                    for tf in sorted(carpeta_txt.glob("*.txt")):
                        texto_orig = tf.read_text("utf-8", errors="replace")
                        texto_filt = filtrar_texto_con_etiquetas(out, nombre, tf.stem, texto_orig)
                        if texto_filt != texto_orig:
                            tf.write_text(texto_filt, encoding="utf-8")

            pdf_path = None
            for a in ST.archivos_sel:
                if a.stem == nombre: pdf_path = a; break

            if usar_v2:
                # Segmentador avanzado v2 — grafo de continuidad
                from core.article_segmenter_v2 import (
                    comparar_segmentaciones,
                    segmentar_avanzado,
                )
                carpeta_txt = txt_dir / nombre
                paginas_txt = []
                if carpeta_txt.exists():
                    paginas_txt = [
                        tf.read_text("utf-8", errors="replace")
                        for tf in sorted(carpeta_txt.glob("*.txt"))
                    ]
                arts_v2 = segmentar_avanzado(paginas_txt, numero=nombre)
                # Convertir a formato dict compatible con el resto del pipeline
                arts = []
                for a in arts_v2:
                    arts.append({
                        "numero":    nombre,
                        "titulo":    a.titulo,
                        "autor":     a.autor,
                        "tipo":      a.seccion,
                        "paginas":   str(a.paginas),
                        "palabras":  a.palabras,
                        "confianza": a.confianza,
                        "metodo_seg": a.metodo,
                        "texto":     a.texto,
                    })
                # Log comparativo con v1
                arts_v1 = segmentar_numero(txt_dir, nombre, pdf_path)
                comp = comparar_segmentaciones(arts_v1, arts_v2)
                self._put(tipo="log", texto=
                    f"  {nombre}: {comp['v2_articulos']} arts (v2, conf. media "
                    f"{comp['v2_confianza_media']:.2f}) vs {comp['v1_articulos']} arts (v1)")
            else:
                arts = segmentar_numero(txt_dir, nombre, pdf_path)
                self._put(tipo="log", texto=f"  {nombre}: {len(arts)} artículos detectados")

            todos.extend(arts)

        ST.df_articulos = pd.DataFrame(todos) if todos else pd.DataFrame()
        # Poblar ST.articulos para módulos que lo esperan como lista de dicts
        ST.articulos = todos
        if not ST.df_articulos.empty:
            ad = out/"04_analisis"; ad.mkdir(exist_ok=True)
            ST.df_articulos.drop(columns=["texto"], errors="ignore").to_csv(
                ad/"articulos_segmentados.csv", index=False, encoding="utf-8-sig")
        # Construir lista plana de textos para módulo de Lingüística y búsqueda semántica
        if not ST.df_articulos.empty and "texto" in ST.df_articulos.columns:
            ST.corpus_txt = ST.df_articulos["texto"].dropna().tolist()
        elif todos:
            ST.corpus_txt = [
                str(a.get("texto", "") or a.get("contenido", ""))
                for a in todos if a.get("texto") or a.get("contenido")
            ]

        ST.seg_done = True
        ST.marcar_etapa("seg", "ready")
        self.after(0, self._marcar_modificado)
        self._put(tipo="ok", res="seg")

    # ══════════════════════════════════════════════════════════════════════════
    # WORKERS — ANÁLISIS TEXTUAL
    # ══════════════════════════════════════════════════════════════════════════
    def _start_anal(self):
        if not ST.ocr_done and not self._reconstruir_corpus_meta_desde_txt():
            messagebox.showwarning("Sin texto extraído",
                "No se encontró texto en 03_ocr/.\n"
                "Usá primero el Conversor PDF o la Extracción OCR."); return
        self._btn_anal.config(state="disabled")
        # Las variables Tk se leen AQUÍ, en el hilo principal. Tcl no es
        # thread-safe: leerlas desde el worker serializa la llamada contra el
        # bucle de eventos y congela la ventana.
        cfg = {
            "colabs": self._txt_col.get("1.0", "end"),
            "modelo": self._var_spacy.get(),
            "n_t":    self._var_nt.get(),
            "min_f":  self._var_mf.get(),
            "wv":     self._var_wv.get(),
            "layout": self._var_layout.get(),
            "red":    self._var_red.get(),
        }
        threading.Thread(target=self._worker_anal, args=(cfg,), daemon=True).start()

    def _worker_anal(self, cfg: dict):
        import spacy

        from core.analysis_engine import (
            analizar_layout_pagina,
            analizar_numero_con_campos_expandidos,
            construir_red,
            leer_numero,
            run_lda,
        )
        from core.word_vectors import (
            entrenar_word2vec,
            expandir_campo_semantico,
        )
        def log(m): self.after(0, lambda msg=m: self._log_a_write(msg))
        def prg(v,t=""): self.after(0, lambda: self._set_prog_a(v,t))

        colabs  = [c.strip() for c in cfg["colabs"].strip().splitlines() if c.strip()]
        modelo  = cfg["modelo"]; n_t=cfg["n_t"]; min_f=cfg["min_f"]
        out     = ST.out_dir; txt_dir=out/"03_ocr"; img_dir=out/"02_imagenes"
        ad      = out/"04_analisis"; ad.mkdir(exist_ok=True)
        campos_semillas = getattr(ST,"campos_semillas",CAMPOS_DEFAULT)

        log(f"🧠 Cargando spaCy {modelo}…"); prg(2,"Cargando modelo NLP…")
        try:
            nlp = spacy.load(modelo)
        except OSError:
            self.after(0, lambda: messagebox.showerror("Modelo no encontrado",
                f"Ejecuta: python -m spacy download {modelo}"))
            self.after(0, lambda: self._btn_anal.config(state="normal")); return
        stopwords = spacy.lang.es.stop_words.STOP_WORDS | {
            "año","años","así","vez","día","días","hacer","gran","mismo",
            "todo","todos","toda","todas","estampa","revista","número","hace","sido"
        }

        if ST.corpus_meta is None:
            self._reconstruir_corpus_meta_desde_txt()
        if ST.corpus_meta is None:
            self._put(tipo="err", txt="No hay texto extraído. Usá el Conversor o la Extracción OCR primero.")
            return
        numeros = sorted(ST.corpus_meta["numero"].unique()); total=len(numeros)
        fr_rows,se_rows,ca_rows,lay_rows,lema_docs,lema_nms = [],[],[],[],[],[]

        # --- Paso 1: Word2Vec (si activado)
        word_model = None
        if cfg["wv"]:
            log("🔢 Recopilando corpus para Word2Vec…"); prg(5,"Corpus Word2Vec…")
            corpus_txt = []
            for nombre in numeros:
                from core.analysis_engine import leer_numero as _lr
                corpus_txt.append(_lr(txt_dir, nombre))
            log("📐 Entrenando Word2Vec…"); prg(8,"Entrenando vectores…")
            model_path = ad/"word2vec.model"
            word_model = entrenar_word2vec(corpus_txt, model_path)
            if word_model:
                log(f"  ✅ Modelo entrenado ({len(word_model.wv)} términos)")
            else:
                log("  ⚠️ Corpus insuficiente para Word2Vec — omitido")
            gc.collect()
        ST.word_model = word_model

        # --- Expandir campos semánticos con Word2Vec
        campos_expandidos = {}
        if word_model:
            log("🔤 Expandiendo campos semánticos con Word2Vec…")
            for campo, semillas in campos_semillas.items():
                res = expandir_campo_semantico(semillas, word_model, topn=20, umbral_sim=0.3)
                campos_expandidos[campo] = res["campo_expandido"]
                log(f"  {campo}: {len(res['campo_expandido'])} términos ({len(semillas)} semillas + {len(res['expansiones'])} expansiones)")
        else:
            campos_expandidos = campos_semillas
        ST.campos_expandidos = campos_expandidos

        # Actualizar combobox de campos
        self.after(0, lambda: self._cb_campos.config(values=list(campos_expandidos.keys())))

        # --- Paso 2: Análisis texto número a número
        for k, nombre in enumerate(numeros):
            log(f"── {nombre} ({k+1}/{total})"); prg(int(10+k/total*65),f"Analizando {nombre}…")
            texto = leer_numero(txt_dir, nombre)
            if not texto.strip(): log("  ⚠️ Sin texto"); continue
            firmas,secciones,campos,lema = analizar_numero_con_campos_expandidos(
                nombre, texto, colabs, nlp, stopwords, campos_expandidos)
            for fi in firmas: fr_rows.append({"numero":nombre,"firma":fi})
            for s,c in secciones.items(): se_rows.append({"numero":nombre,"seccion":s,"menciones":c})
            campos["numero"]=nombre; ca_rows.append(campos)
            if lema.strip(): lema_docs.append(lema); lema_nms.append(nombre)
            del texto; gc.collect()
            if cfg["layout"]:
                imgd = img_dir/nombre
                if imgd.exists():
                    for ip in sorted(imgd.glob("*.png")):
                        r=analizar_layout_pagina(ip)
                        if r: r["numero"]=nombre; r["pagina"]=ip.stem; lay_rows.append(r)

        log("🧠 Liberando modelo NLP…"); del nlp; gc.collect()

        # --- LDA
        log(f"🧩 LDA ({n_t} temas)…"); prg(78,"Modelado LDA…")
        df_temas=pd.DataFrame(); df_doc_temas=pd.DataFrame()
        if lema_docs:
            try:
                df_temas,df_doc_temas=run_lda(lema_docs,lema_nms,n_t)
                log(f"  ✅ {n_t} temas")
            except Exception as e: log(f"  ⚠️ LDA: {e}")

        # --- Red de autoría
        graph_path=None
        if cfg["red"] and fr_rows:
            log("🕸️ Red de autoría…"); prg(85,"Red…")
            import networkx as nx
            df_f_tmp=pd.DataFrame(fr_rows)
            G=construir_red(df_f_tmp,min_f); graph_path=ad/"red_autoria.graphml"
            nx.write_graphml(G,str(graph_path))
            log(f"  ✅ {G.number_of_nodes()} nodos · {G.number_of_edges()} aristas"); del G; gc.collect()

        # --- Guardar
        log("💾 Guardando resultados…"); prg(92,"Guardando…")
        df_firmas    = pd.DataFrame(fr_rows)
        df_secciones = pd.DataFrame(se_rows)
        df_campos    = pd.DataFrame(ca_rows)
        df_layout    = pd.DataFrame(lay_rows)
        for df_i,fn in [(df_firmas,"firmas.csv"),(df_secciones,"secciones.csv"),
                         (df_campos,"campos_semanticos.csv"),(df_layout,"layout.csv"),
                         (df_temas,"lda_temas.csv")]:
            if not df_i.empty: df_i.to_csv(ad/fn,index=False)
        if not df_doc_temas.empty: df_doc_temas.to_csv(ad/"lda_distribucion.csv")
        ST.df_firmas=df_firmas; ST.df_secciones=df_secciones; ST.df_campos=df_campos
        ST.df_layout=df_layout; ST.df_temas=df_temas; ST.df_doc_temas=df_doc_temas
        ST.graph_path=graph_path; ST.anal_done=True
        ST.marcar_etapa("anal", "ready")
        self.after(0, self._marcar_modificado)
        prg(100,"✅"); log("🎉 Análisis textual completado.")
        self._put(tipo="ok",res="anal")

    # ══════════════════════════════════════════════════════════════════════════
    # WORKERS — VISUAL Y TIPOGRAFÍA
    # ══════════════════════════════════════════════════════════════════════════
    def _start_vis(self):
        if not ST.ocr_done and not self._reconstruir_corpus_meta_desde_txt():
            messagebox.showwarning("Sin texto extraído",
                "No se encontró texto en 03_ocr/.\n"
                "Usá primero el Conversor PDF o la Extracción OCR."); return
        self._btn_vis.config(state="disabled")
        # dpi se lee en el hilo principal (ver nota en _start_anal).
        threading.Thread(target=self._worker_vis, args=(self._var_dpi.get(),),
                         daemon=True).start()

    def _worker_vis(self, dpi: int):
        from core.image_analyzer import analizar_numero_imagenes
        from core.visual_analyzer import analizar_tipografia_numero
        out     = ST.out_dir
        img_dir = out / "02_imagenes"
        ocr_dir = out / "03_ocr"
        if ST.corpus_meta is None:
            self._reconstruir_corpus_meta_desde_txt()
        if ST.corpus_meta is None:
            self._put(tipo="err", txt="No hay texto extraído. Usá el Conversor o la Extracción OCR primero.")
            return
        numeros = sorted(ST.corpus_meta["numero"].unique())
        tip_global = {}

        self.after(0, lambda: self._tv_tip.delete(*self._tv_tip.get_children()))
        self.after(0, lambda: self._tv_ele.delete(*self._tv_ele.get_children()))

        api_key, _modelo_vis = _resolver_api_key_modelo("asistente")
        max_ia  = getattr(ST, "max_ia", 15)

        for k, nombre in enumerate(numeros):
            self._put(tipo="log",  texto=f"🖼️  {nombre} ({k+1}/{len(numeros)})…")
            self._put(tipo="prog", val=int(k/len(numeros)*100), txt=f"{nombre}…")
            pdf_path = None
            for a in ST.archivos_sel:
                if a.stem == nombre and a.suffix.lower() == ".pdf":
                    pdf_path = a; break

            if pdf_path and pdf_path.exists():
                try:
                    tip = analizar_tipografia_numero(pdf_path)
                    if tip and tip.get("n_fuentes", 0) > 0:
                        tip["numero"] = nombre; tip_global[nombre] = tip
                        self._put(tipo="log",
                            texto=f"  ✅ Tipografía: {tip.get('n_fuentes',0)} fuentes · "
                                  f"{tip.get('fuente_principal','N/D')} · cuerpo {tip.get('tam_cuerpo_medio',0)} pt")
                    else:
                        self._put(tipo="log", texto="  ⚠️ Tipografía: sin datos")
                except Exception as e:
                    self._put(tipo="log", texto=f"  ⚠️ Tipografía: {e}")

            imgd = img_dir / nombre
            if imgd.exists():
                def _cb(msg): self._put(tipo="log", texto=f"  {msg}")
                datos_img = analizar_numero_imagenes(
                    imgd, ocr_dir, nombre,
                    dpi=dpi, api_key=api_key, max_ia=max_ia, callback=_cb)
                if datos_img:
                    ST.datos_imagenes[nombre] = datos_img
                    self._put(tipo="log",
                        texto=f"  ✅ Visual: {datos_img['total_fotos']} fotos · "
                              f"{datos_img['total_ilustraciones']} ilustraciones · "
                              f"{datos_img['total_publicidades']} avisos · "
                              f"{datos_img['area_visual_media']}% área visual promedio")
            else:
                self._put(tipo="log", texto="  ℹ️ Sin imágenes PNG (solo tipografía disponible)")
            gc.collect()

        ST.datos_visual = {"tipografia": tip_global, "visual_elementos": ST.datos_imagenes}
        ST.vis_done = True

        # ── Descripción con IA (opcional) ─────────────────────────────────────
        api_key, _modelo_vis2 = _resolver_api_key_modelo("asistente")
        if api_key and ST.datos_imagenes:
            self._put(tipo="log", texto="🤖 Describiendo imágenes con Claude AI… (esto puede tardar)")
            try:
                from core.image_describer import describir_pagina
                img_dir_base = ST.out_dir / "02_imagenes"
                n_descritos  = 0
                for nombre, datos_num in ST.datos_imagenes.items():
                    imgd = img_dir_base / nombre
                    if not imgd.exists(): continue
                    nuevas_pags = []
                    for pag_datos in datos_num.get("paginas", []):
                        pagina_id = pag_datos.get("pagina","")
                        ip = imgd / f"{pagina_id}.png"
                        if not ip.exists():
                            nuevas_pags.append(pag_datos); continue
                        pag_desc = describir_pagina(ip, pag_datos, api_key, max_elementos=6)
                        nuevas_pags.append(pag_desc)
                        n_desc_pag = sum(1 for el in pag_desc.get("elementos",[]) if el.get("descrito_por_ai"))
                        if n_desc_pag: n_descritos += n_desc_pag
                        self._put(tipo="log", texto=f"  🤖 {nombre}/{pagina_id}: {n_desc_pag} elemento(s) descritos")
                    datos_num["paginas"] = nuevas_pags
                self._put(tipo="log", texto=f"  ✅ IA: {n_descritos} elemento(s) descritos en total")
            except Exception as e:
                self._put(tipo="log", texto=f"  ⚠️ Descripción IA: {e}")

        for nombre, tip in tip_global.items():
            vals = (
                nombre,
                tip.get("fuente_principal","N/D"),
                tip.get("clasificacion_fuente",""),
                tip.get("n_fuentes","—"),
                tip.get("tam_cuerpo_medio","—"),
                tip.get("tam_titulo_medio","—"),
                tip.get("ratio_titulo_cuerpo","—"),
                tip.get("interlineado_rel","—"),
                tip.get("columnas_moda", tip.get("columnas_prom","—")),
                tip.get("negrita_pct","—"),
                tip.get("cursiva_pct","—"),
                tip.get("imagenes_total","—"),
            )
            self.after(0, lambda v=vals: self._tv_tip.insert("","end",values=v))

        tag_map = {
            "Fotografía":            "foto",
            "Ilustración/Caricatura":"ilustracion",
            "Publicidad/Aviso":      "publicidad",
            "Mixto":                 "mixto",
        }
        total_el = 0
        for nombre, datos in ST.datos_imagenes.items():
            for pag in datos.get("paginas", []):
                pagina = pag.get("pagina","")
                for el in pag.get("elementos", []):
                    if el.get("tipo") == "Texto": continue
                    vals = (
                        nombre, pagina,
                        el.get("tipo",""),
                        f"{el.get('confianza',0):.2f}",
                        f"{el.get('w_cm',0):.1f}",
                        f"{el.get('h_cm',0):.1f}",
                        f"{el.get('area_cm2',0):.1f}",
                        f"{el.get('pos_x_pct',0):.0f}",
                        f"{el.get('pos_y_pct',0):.0f}",
                        el.get("autor_imagen",""),
                        el.get("pie_de_foto","")[:80],
                        el.get("descripcion_ia","")[:120],
                    )
                    tag = tag_map.get(el.get("tipo",""), "")
                    self.after(0, lambda v=vals, t=tag: self._tv_ele.insert("","end",values=v,tags=(t,)))
                    total_el += 1

        numeros_con_imgs = [n for n in numeros if n in ST.datos_imagenes]
        if numeros_con_imgs:
            self.after(0, lambda ns=numeros_con_imgs: self._actualizar_combos_diag(ns))

        cnt_msg = f"{total_el} elementos visuales detectados"
        self.after(0, lambda m=cnt_msg: self._lbl_ele_cnt.config(text=m))
        resumen = f"✅ {len(tip_global)} número(s) con tipografía · {total_el} elementos visuales"
        self._put(tipo="log", texto=f"🎉 {resumen}")
        self.after(0, lambda: self._lbl_vis_ok.config(text=resumen))
        self.after(0, lambda: self._btn_vis.config(state="normal"))
        self._put(tipo="prog", val=100, txt="✅")

    # ══════════════════════════════════════════════════════════════════════════
    # WORKERS — ANÁLISIS COMPARATIVO
    # ══════════════════════════════════════════════════════════════════════════
    def _start_comp(self):
        ref = self._var_ref.get().strip()
        if not ref or not Path(ref).exists():
            messagebox.showwarning("Sin referencia",
                "Configura la carpeta de publicaciones de referencia en ⚙️ Config."); return
        if not ST.ocr_done and not self._reconstruir_corpus_meta_desde_txt():
            messagebox.showwarning("Sin texto extraído",
                "No se encontró texto en 03_ocr/.\n"
                "Usá primero el Conversor PDF o la Extracción OCR."); return
        self._btn_comp.config(state="disabled")
        threading.Thread(target=self._worker_comp, args=(Path(ref),), daemon=True).start()

    def _worker_comp(self, ref_dir):
        from core.comparative_analyzer import (
            cargar_corpora,
            generar_reporte_comparativo,
        )
        self._put(tipo="log",texto="📚 Cargando corpora de referencia…")
        # Corpus principal: concatenar todos los textos OCR
        out=ST.out_dir; txt_dir=out/"03_ocr"
        if ST.corpus_meta is None:
            self._reconstruir_corpus_meta_desde_txt()
        if ST.corpus_meta is None:
            self._put(tipo="err", txt="No hay texto extraído. Usá el Conversor o la Extracción OCR primero.")
            return
        texto_principal = ""
        for nombre in sorted(ST.corpus_meta["numero"].unique()):
            carpeta = txt_dir/nombre
            if carpeta.exists():
                for tf in sorted(carpeta.glob("*.txt")):
                    texto_principal += tf.read_text("utf-8",errors="replace") + "\n"
        pub_nombre = ST.publicacion
        corpus_principal = {pub_nombre: texto_principal}
        # Cargar referencia
        corpora = cargar_corpora(ref_dir, corpus_principal)
        self._put(tipo="log",texto=f"  {len(corpora)} publicaciones: {', '.join(corpora.keys())}")
        if len(corpora) < 2:
            self._put(tipo="log",texto="⚠️ Se necesitan al menos 2 publicaciones para comparar.")
            self.after(0, lambda: self._btn_comp.config(state="normal")); return
        # Campos con expansión si disponible
        campos = ST.campos_expandidos if ST.campos_expandidos else getattr(ST,"campos_semillas",CAMPOS_DEFAULT)
        campos_simple = {k: v for k,v in campos.items()}
        self._put(tipo="log",texto="📊 Calculando similaridad y palabras distintivas…")
        rep = generar_reporte_comparativo(pub_nombre, corpora, campos_simple)
        ST.datos_comparativo=rep; ST.comp_done=True
        # Mostrar en UI
        sim=rep.get("similaridad"); dist=rep.get("palabras_distintivas",{}); pc=rep.get("perfil_campos")
        if sim is not None:
            sim_txt=sim.to_string()
            def _show_sim(t=sim_txt):
                self._txt_sim.delete("1.0","end"); self._txt_sim.insert("1.0",t)
            self.after(0,_show_sim)
        if dist:
            lines=[]
            for ref_n,pals in dist.items():
                lines.append(f"\n── vs. {ref_n} ──")
                for p,s in pals[:15]: lines.append(f"  {p:<25} G²={s:.1f}")
            def _show_dist(t="\n".join(lines)):
                self._txt_dist.delete("1.0","end"); self._txt_dist.insert("1.0",t)
            self.after(0,_show_dist)
        if pc is not None and not pc.empty:
            def _show_campos_fig():
                for w in self._fig_cam_frame.winfo_children(): w.destroy()
                fig,ax=plt.subplots(figsize=(10,4))
                x=np.arange(len(pc.columns)); w_bar=0.8/max(len(pc),1)
                cols_pal=PALETTE
                for i,(pub,row) in enumerate(pc.iterrows()):
                    ax.bar(x+i*w_bar,row.values,width=w_bar,label=pub,color=cols_pal[i%len(cols_pal)],alpha=0.85)
                ax.set_xticks(x+w_bar*(len(pc)-1)/2)
                ax.set_xticklabels(pc.columns,rotation=30,ha="right",fontsize=9)
                ax.set_ylabel("Menciones/1000 pal."); ax.legend(fontsize=8)
                ax.set_title("Campos semánticos — comparativo",fontsize=11,fontweight="bold")
                plt.tight_layout()
                canvas=FigureCanvasTkAgg(fig,master=self._fig_cam_frame)
                canvas.draw(); canvas.get_tk_widget().pack(fill="both",expand=True)
                plt.close(fig)
            self.after(0,_show_campos_fig)
        self._put(tipo="log",texto="🎉 Análisis comparativo completado.")
        self.after(0,lambda: self._lbl_comp_ok.config(text="✅ Comparativo completado"))
        self.after(0,lambda: self._btn_comp.config(state="normal"))

    def _build_coloc(self):
        self._page_header(self._tab_coloc, "Collocates y Redes Léxicas",
                          "Palabras que co-ocurren con una clave · KWIC · Dispersión léxica", "🔤")
        outer = tk.Frame(self._tab_coloc, bg=TEMA.CONTENT_BG)
        outer.pack(fill="both", expand=True, padx=16, pady=8)

        self._coloc_params: dict = {}
        try:
            from core.collocation_engine import PARAMS_SCHEMA as _COLOC_SCHEMA
            self._build_params_panel(outer, _COLOC_SCHEMA, self._coloc_params)
        except Exception:
            pass

        pad = tk.Frame(outer, bg=TEMA.CONTENT_BG)
        pad.pack(side="left", fill="both", expand=True)

        # Botón bitácora en la barra superior
        bbar_coloc = tk.Frame(pad, bg=TEMA.CONTENT_BG)
        bbar_coloc.pack(fill="x", pady=(0, 4))
        ttk.Button(bbar_coloc, text="📓 Nota", style="S.TButton",
                   command=lambda: self._bitacora_nueva_nota("coloc")).pack(side="right")

        nb = ttk.Notebook(pad)
        nb.pack(fill="both", expand=True)

        # ── Sub-pestaña: Collocates ──
        frm_col = tk.Frame(nb, bg=TEMA.CONTENT_BG); nb.add(frm_col, text="  Collocates  ")
        pad_col = tk.Frame(frm_col, bg=TEMA.CONTENT_BG, padx=10, pady=8); pad_col.pack(fill="both", expand=True)

        bf = tk.Frame(pad_col, bg=TEMA.CONTENT_BG); bf.pack(fill="x", pady=(0, 6))
        tk.Label(bf, text="Palabra clave:", bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self._var_coloc_kw = tk.StringVar()
        tk.Entry(bf, textvariable=self._var_coloc_kw, width=20,
                 font=("Segoe UI", 10), relief="solid", bd=1,
                 bg="#12171B", fg="#E8E5DF").pack(side="left", padx=(0, 8))
        tk.Label(bf, text="Ventana:", bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self._var_coloc_vent = tk.IntVar(value=5)
        ttk.Spinbox(bf, from_=2, to=15, textvariable=self._var_coloc_vent,
                    width=4).pack(side="left", padx=(0, 8))
        tk.Label(bf, text="Top N:", bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self._var_coloc_n = tk.IntVar(value=20)
        ttk.Spinbox(bf, from_=5, to=50, textvariable=self._var_coloc_n,
                    width=4).pack(side="left", padx=(0, 8))
        self._btn_coloc = ttk.Button(bf, text="▶  Calcular", style="P.TButton",
                                      command=self._coloc_calcular)
        self._btn_coloc.pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="📊  Graficar red", style="S.TButton",
                   command=self._coloc_graficar_red).pack(side="left")
        ttk.Button(bf, text="💾 CSV", style="S.TButton",
                   command=self._coloc_exportar_csv).pack(side="left", padx=(8, 0))

        self._lbl_coloc_ok = tk.Label(pad_col, text="", bg=TEMA.CONTENT_BG, fg=TEMA.VERDE,
                                       font=("Segoe UI", 9, "bold"))
        self._lbl_coloc_ok.pack(anchor="w", pady=(0, 4))

        cols = ("palabra", "frecuencia", "pmi")
        self._tv_coloc = ttk.Treeview(pad_col, columns=cols, show="headings", height=14)
        heads = [("palabra", "Palabra collocate", 200),
                 ("frecuencia", "Frecuencia", 100),
                 ("pmi", "PMI (asociación)", 120)]
        for cid, txt, w in heads:
            self._tv_coloc.heading(cid, text=txt)
            self._tv_coloc.column(cid, width=w, anchor="w")
        sv = ttk.Scrollbar(pad_col, orient="vertical", command=self._tv_coloc.yview)
        self._tv_coloc.configure(yscrollcommand=sv.set)
        self._tv_coloc.pack(side="left", fill="both", expand=True)
        sv.pack(side="left", fill="y")

        # ── Sub-pestaña: KWIC ──
        frm_kwic = tk.Frame(nb, bg=TEMA.CONTENT_BG); nb.add(frm_kwic, text="  KWIC  ")
        pad_kwic = tk.Frame(frm_kwic, bg=TEMA.CONTENT_BG, padx=10, pady=8); pad_kwic.pack(fill="both", expand=True)

        bk = tk.Frame(pad_kwic, bg=TEMA.CONTENT_BG); bk.pack(fill="x", pady=(0, 6))
        tk.Label(bk, text="Palabra:", bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self._var_kwic_kw = tk.StringVar()
        tk.Entry(bk, textvariable=self._var_kwic_kw, width=22,
                 font=("Segoe UI", 10), relief="solid", bd=1,
                 bg="#12171B", fg="#E8E5DF").pack(side="left", padx=(0, 8))
        ttk.Button(bk, text="▶  Buscar concordancias", style="P.TButton",
                   command=self._coloc_kwic).pack(side="left")
        ttk.Button(bk, text="💾 Exportar CSV", style="S.TButton",
                   command=self._coloc_kwic_exportar_csv).pack(side="left", padx=(8, 0))
        self._kwic_resultados: list[dict] = []

        self._txt_kwic = scrolledtext.ScrolledText(pad_kwic, font=("Consolas", 9),
                                                    bg="#12171B", fg="#E8E5DF",
                                                    height=20, relief="flat")
        self._txt_kwic.pack(fill="both", expand=True)
        self._txt_kwic.tag_configure("kw", foreground="#E6A64C", font=("Consolas", 9, "bold"))

        # ── Sub-pestaña: Frecuencias ──
        frm_freq = tk.Frame(nb, bg=TEMA.CONTENT_BG); nb.add(frm_freq, text="  Frecuencias  ")
        pad_freq = tk.Frame(frm_freq, bg=TEMA.CONTENT_BG, padx=10, pady=8); pad_freq.pack(fill="both", expand=True)

        bfr = tk.Frame(pad_freq, bg=TEMA.CONTENT_BG); bfr.pack(fill="x", pady=(0, 6))
        self._var_freq_n = tk.IntVar(value=30)
        tk.Label(bfr, text="Top N:", bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        ttk.Spinbox(bfr, from_=10, to=100, textvariable=self._var_freq_n,
                    width=4).pack(side="left", padx=(0, 8))
        ttk.Button(bfr, text="▶  Calcular frecuencias", style="P.TButton",
                   command=self._coloc_frecuencias).pack(side="left", padx=(0, 8))
        ttk.Button(bfr, text="📊  Graficar", style="S.TButton",
                   command=self._coloc_graficar_freq).pack(side="left")
        ttk.Button(bfr, text="💾 CSV", style="S.TButton",
                   command=self._coloc_freq_exportar_csv).pack(side="left", padx=(8, 0))
        self._var_freq_relativa = tk.BooleanVar(value=False)
        ttk.Checkbutton(bfr, text="Relativa (/10.000)", variable=self._var_freq_relativa).pack(
            side="left", padx=(12, 0))

        cols_f = ("rank", "palabra", "freq", "df")
        self._tv_freq = ttk.Treeview(pad_freq, columns=cols_f, show="headings", height=16)
        for cid, txt, w in [("rank","#",40),("palabra","Palabra",200),
                             ("freq","Frecuencia",100),("df","En N docs",100)]:
            self._tv_freq.heading(cid, text=txt)
            self._tv_freq.column(cid, width=w, anchor="w")
        svf = ttk.Scrollbar(pad_freq, orient="vertical", command=self._tv_freq.yview)
        self._tv_freq.configure(yscrollcommand=svf.set)
        self._tv_freq.pack(side="left", fill="both", expand=True)
        svf.pack(side="left", fill="y")

        # ── Sub-pestaña: N-gramas ─────────────────────────────────────────────
        frm_ng = tk.Frame(nb, bg=TEMA.CONTENT_BG); nb.add(frm_ng, text="  N-gramas  ")
        pad_ng = tk.Frame(frm_ng, bg=TEMA.CONTENT_BG, padx=10, pady=8)
        pad_ng.pack(fill="both", expand=True)

        bng = tk.Frame(pad_ng, bg=TEMA.CONTENT_BG); bng.pack(fill="x", pady=(0, 6))
        tk.Label(bng, text="N:", bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self._var_ng_n = tk.IntVar(value=2)
        ttk.Spinbox(bng, from_=2, to=5, textvariable=self._var_ng_n,
                    width=3).pack(side="left", padx=(0, 8))
        tk.Label(bng, text="Top:", bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self._var_ng_top = tk.IntVar(value=30)
        ttk.Spinbox(bng, from_=10, to=100, textvariable=self._var_ng_top,
                    width=4).pack(side="left", padx=(0, 8))
        self._var_ng_sw = tk.BooleanVar(value=False)
        ttk.Checkbutton(bng, text="Filtrar stopwords", variable=self._var_ng_sw).pack(
            side="left", padx=(0, 8))
        ttk.Button(bng, text="▶  Calcular", style="P.TButton",
                   command=self._coloc_ngramas).pack(side="left")
        ttk.Button(bng, text="💾 CSV", style="S.TButton",
                   command=self._coloc_ngramas_csv).pack(side="left", padx=(8, 0))

        cols_ng = ("rank", "ngrama", "freq")
        self._tv_ng = ttk.Treeview(pad_ng, columns=cols_ng, show="headings", height=16)
        for cid, txt, w in [("rank","#",40),("ngrama","N-grama",320),("freq","Frecuencia",100)]:
            self._tv_ng.heading(cid, text=txt)
            self._tv_ng.column(cid, width=w, anchor="w")
        sv_ng = ttk.Scrollbar(pad_ng, orient="vertical", command=self._tv_ng.yview)
        self._tv_ng.configure(yscrollcommand=sv_ng.set)
        self._tv_ng.pack(side="left", fill="both", expand=True)
        sv_ng.pack(side="left", fill="y")

        # ── Sub-pestaña: Dispersión léxica ────────────────────────────────────
        frm_disp = tk.Frame(nb, bg=TEMA.CONTENT_BG); nb.add(frm_disp, text="  Dispersión  ")
        pad_disp = tk.Frame(frm_disp, bg=TEMA.CONTENT_BG, padx=10, pady=8)
        pad_disp.pack(fill="both", expand=True)

        bdisp = tk.Frame(pad_disp, bg=TEMA.CONTENT_BG); bdisp.pack(fill="x", pady=(0, 6))
        tk.Label(bdisp, text="Palabras (coma):", bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self._var_disp_words = tk.StringVar()
        tk.Entry(bdisp, textvariable=self._var_disp_words, width=40,
                 font=("Segoe UI", 9), bg="#12171B", fg="#E8E5DF",
                 relief="solid", bd=1).pack(side="left", padx=(0, 8))
        ttk.Button(bdisp, text="▶  Graficar", style="P.TButton",
                   command=self._coloc_dispersion).pack(side="left")

        self._frm_disp_canvas = tk.Frame(pad_disp, bg=TEMA.CONTENT_BG)
        self._frm_disp_canvas.pack(fill="both", expand=True)

        # ── Sub-pestaña: Stopwords del proyecto ───────────────────────────────
        frm_sw = tk.Frame(nb, bg=TEMA.CONTENT_BG); nb.add(frm_sw, text="  Stopwords  ")
        pad_sw = tk.Frame(frm_sw, bg=TEMA.CONTENT_BG, padx=10, pady=8)
        pad_sw.pack(fill="both", expand=True)

        tk.Label(pad_sw,
                 text="Stopwords adicionales para este proyecto "
                      "(una por línea, se suman a la lista base en español):",
                 bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 4))
        self._txt_stopwords = scrolledtext.ScrolledText(
            pad_sw, height=10, bg="#171C20", fg=TEMA.TXT_PRI,
            insertbackground=TEMA.TXT_PRI, font=("Courier New", 9),
            relief="solid", bd=1, wrap="word")
        self._txt_stopwords.pack(fill="both", expand=True)
        # Cargar stopwords del proyecto si existen
        sw_guardadas = getattr(ST, "stopwords_proyecto", [])
        if sw_guardadas:
            self._txt_stopwords.insert("1.0", "\n".join(sw_guardadas))
        bsw = tk.Frame(pad_sw, bg=TEMA.CONTENT_BG); bsw.pack(fill="x", pady=(6, 0))
        ttk.Button(bsw, text="💾 Guardar stopwords del proyecto", style="P.TButton",
                   command=self._coloc_guardar_stopwords).pack(side="left")
        tk.Label(bsw,
                 text="Se aplican a Collocates, Frecuencias y N-gramas al activar 'Filtrar stopwords'",
                 bg=TEMA.CONTENT_BG, fg=TEMA.TXT_DIM, font=("Segoe UI", 8)).pack(
                 side="left", padx=10)

    def _coloc_calcular(self):
        from core.collocation_engine import collocates
        kw = self._var_coloc_kw.get().strip()
        if not kw:
            messagebox.showwarning("Sin palabra clave", "Escribe una palabra clave."); return
        corpus = getattr(ST, "corpus_txt", None) or []
        if not corpus:
            messagebox.showwarning("Sin corpus", "Extrae el texto del corpus primero."); return
        self._btn_coloc.config(state="disabled")
        self._lbl_coloc_ok.config(text="Calculando…")

        def _worker():
            res = collocates(corpus, kw,
                             ventana=self._var_coloc_vent.get(),
                             top_n=self._var_coloc_n.get())
            def _show():
                for row in self._tv_coloc.get_children():
                    self._tv_coloc.delete(row)
                for r in res:
                    self._tv_coloc.insert("", "end", values=(
                        r["palabra"], r["frecuencia"], f"{r['pmi']:.3f}"))
                self._lbl_coloc_ok.config(text=f"✅ {len(res)} collocates de «{kw}»")
                self._btn_coloc.config(state="normal")
            self.after(0, _show)

        threading.Thread(target=_worker, daemon=True).start()

    def _coloc_graficar_red(self):

        from core.collocation_engine import red_lexica
        corpus = getattr(ST, "corpus_txt", None) or []
        if not corpus:
            messagebox.showwarning("Sin corpus", "Extrae el texto del corpus primero."); return
        kw = self._var_coloc_kw.get().strip()
        palabras_clave = [kw] if kw else None

        def _worker():
            red = red_lexica(corpus, palabras_clave=palabras_clave, top_n_nodos=25)
            self.after(0, lambda: self._coloc_mostrar_red(red))

        threading.Thread(target=_worker, daemon=True).start()

    def _coloc_mostrar_red(self, red):
        try:
            import matplotlib.pyplot as plt
            import networkx as nx
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except ImportError:
            messagebox.showerror("Falta networkx", "pip install networkx"); return

        G = nx.Graph()
        for n in red["nodos"]:
            G.add_node(n["id"], size=n["size"])
        for a in red["aristas"]:
            G.add_edge(a["source"], a["target"], weight=a["weight"])

        win = tk.Toplevel(self)
        win.title("Red léxica")
        win.geometry("700x560")
        win.configure(bg="#171C20")

        fig, ax = plt.subplots(figsize=(8, 6))
        fig.patch.set_facecolor("#171C20")
        ax.set_facecolor("#171C20")
        pos = nx.spring_layout(G, seed=42, k=1.2)
        sizes = [G.nodes[n].get("size", 20) * 15 for n in G.nodes]
        nx.draw_networkx(G, pos=pos, ax=ax,
                         node_color="#6CA8E8", node_size=sizes,
                         font_color="#E8E5DF", font_size=7,
                         edge_color="#2A3238", width=0.8, alpha=0.85)
        ax.axis("off")
        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _coloc_kwic(self):
        from core.collocation_engine import concordancias
        kw = self._var_kwic_kw.get().strip()
        if not kw:
            messagebox.showwarning("Sin palabra", "Escribe una palabra."); return
        corpus = getattr(ST, "corpus_txt", None) or []
        if not corpus:
            messagebox.showwarning("Sin corpus", "Extrae el texto primero."); return

        def _worker():
            res = concordancias(corpus, kw, max_resultados=200)
            self._kwic_resultados = res

            def _show():
                self._txt_kwic.config(state="normal")
                self._txt_kwic.delete("1.0", "end")
                for r in res:
                    self._txt_kwic.insert("end", r["izquierda"] + " ")
                    self._txt_kwic.insert("end", r["kwic"], "kw")
                    self._txt_kwic.insert("end", " " + r["derecha"] + "\n")
                self._txt_kwic.config(state="disabled")
            self.after(0, _show)

        threading.Thread(target=_worker, daemon=True).start()

    def _coloc_kwic_exportar_csv(self):
        """Exporta las concordancias KWIC actuales a CSV."""
        if not getattr(self, "_kwic_resultados", None):
            messagebox.showwarning("Sin resultados", "Busca concordancias primero.")
            return
        import csv
        from tkinter import filedialog
        kw = self._var_kwic_kw.get().strip() or "kwic"
        dest = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"concordancias_{kw}.csv",
            title="Exportar concordancias KWIC")
        if not dest:
            return
        with open(dest, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["doc_idx", "izquierda", "kwic", "derecha", "posicion"])
            w.writeheader()
            w.writerows(self._kwic_resultados)
        messagebox.showinfo("Exportado", f"✅ {len(self._kwic_resultados)} concordancias exportadas:\n{dest}")

    def _coloc_frecuencias(self):
        from core.collocation_engine import frecuencias
        corpus = getattr(ST, "corpus_txt", None) or []
        if not corpus:
            messagebox.showwarning("Sin corpus", "Extrae el texto primero."); return
        relativa = getattr(self, "_var_freq_relativa", None)
        usar_relativa = relativa.get() if relativa else False

        def _worker():
            res = frecuencias(corpus, top_n=self._var_freq_n.get())
            # Total de tokens para normalización
            total_tokens = sum(r["freq"] for r in res) or 1
            self._freq_resultados = res
            self._freq_total_tokens = total_tokens

            def _show():
                for row in self._tv_freq.get_children():
                    self._tv_freq.delete(row)
                for i, r in enumerate(res, 1):
                    if usar_relativa:
                        freq_display = f"{r['freq'] / total_tokens * 10000:.1f}"
                    else:
                        freq_display = r["freq"]
                    self._tv_freq.insert("", "end", values=(
                        i, r["palabra"], freq_display, r.get("df", "")))
            self.after(0, _show)

        threading.Thread(target=_worker, daemon=True).start()

    def _coloc_exportar_csv(self):
        """Exporta collocates a CSV."""
        items = self._tv_coloc.get_children() if hasattr(self, "_tv_coloc") else []
        if not items:
            messagebox.showwarning("Sin datos", "Calcula collocates primero."); return
        import csv
        from tkinter import filedialog
        kw = self._var_coloc_kw.get().strip() or "collocates"
        dest = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV","*.csv")],
            initialfile=f"collocates_{kw}.csv")
        if not dest: return
        with open(dest, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["palabra", "frecuencia", "pmi"])
            for iid in items:
                w.writerow(self._tv_coloc.item(iid)["values"])
        messagebox.showinfo("Exportado", f"✅ Collocates exportados:\n{dest}")

    def _coloc_freq_exportar_csv(self):
        """Exporta frecuencias a CSV."""
        items = self._tv_freq.get_children() if hasattr(self, "_tv_freq") else []
        if not items:
            messagebox.showwarning("Sin datos", "Calcula frecuencias primero."); return
        import csv
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV","*.csv")],
            initialfile="frecuencias.csv")
        if not dest: return
        relativa = getattr(self, "_var_freq_relativa", None)
        usar_rel  = relativa.get() if relativa else False
        total     = getattr(self, "_freq_total_tokens", 1) or 1
        res       = getattr(self, "_freq_resultados", [])
        with open(dest, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            if usar_rel:
                w.writerow(["rank", "palabra", "freq_relativa_x10000", "freq_absoluta", "n_documentos"])
                for i, r in enumerate(res, 1):
                    w.writerow([i, r["palabra"],
                                round(r["freq"]/total*10000, 2),
                                r["freq"], r.get("df","")])
            else:
                w.writerow(["rank", "palabra", "frecuencia", "n_documentos"])
                for i, r in enumerate(res, 1):
                    w.writerow([i, r["palabra"], r["freq"], r.get("df","")])
        messagebox.showinfo("Exportado", f"✅ Frecuencias exportadas:\n{dest}")

    def _coloc_ngramas(self):
        from core.collocation_engine import ngramas
        corpus = getattr(ST, "corpus_txt", None) or []
        if not corpus:
            messagebox.showwarning("Sin corpus", "Extrae el texto primero."); return
        n   = self._var_ng_n.get()
        top = self._var_ng_top.get()
        sw  = self._var_ng_sw.get()

        def _worker():
            res = ngramas(corpus, n=n, top_n=top, stopwords=sw)
            self._ng_resultados = res
            def _show():
                for row in self._tv_ng.get_children():
                    self._tv_ng.delete(row)
                for i, r in enumerate(res, 1):
                    self._tv_ng.insert("", "end", values=(i, r["ngrama"], r["frecuencia"]))
            self.after(0, _show)
        threading.Thread(target=_worker, daemon=True).start()

    def _coloc_ngramas_csv(self):
        items = self._tv_ng.get_children() if hasattr(self, "_tv_ng") else []
        if not items:
            messagebox.showwarning("Sin datos", "Calcula n-gramas primero."); return
        import csv
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV","*.csv")],
            initialfile=f"ngramas_n{self._var_ng_n.get()}.csv")
        if not dest: return
        res = getattr(self, "_ng_resultados", [])
        with open(dest, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["rank", "ngrama", "frecuencia"])
            for i, r in enumerate(res, 1):
                w.writerow([i, r["ngrama"], r["frecuencia"]])
        messagebox.showinfo("Exportado", f"✅ N-gramas exportados:\n{dest}")

    def _coloc_dispersion(self):
        corpus = getattr(ST, "corpus_txt", None) or []
        if not corpus:
            messagebox.showwarning("Sin corpus", "Extrae el texto primero."); return
        palabras_raw = self._var_disp_words.get()
        palabras = [p.strip() for p in palabras_raw.split(",") if p.strip()]
        if not palabras:
            messagebox.showwarning("Sin palabras", "Escribe al menos una palabra."); return

        def _worker():
            from core.collocation_engine import dispersion
            res = dispersion(corpus, palabras)
            self.after(0, lambda: self._coloc_mostrar_dispersion(res, palabras))
        threading.Thread(target=_worker, daemon=True).start()

    def _coloc_mostrar_dispersion(self, resultado: dict, palabras: list[str]):
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            from core.chart_builder import _FONDO, _TEXTO
        except ImportError:
            messagebox.showerror("Falta matplotlib", "pip install matplotlib"); return

        # Limpiar canvas anterior
        for w in self._frm_disp_canvas.winfo_children():
            w.destroy()

        n = len(palabras)
        fig, axes = plt.subplots(n, 1, figsize=(10, max(2, n * 1.4)),
                                  facecolor=_FONDO, sharex=True)
        if n == 1:
            axes = [axes]

        colores = ["#6CA8E8","#E6A64C","#6EC69A","#D96B6B","#B18AD6","#E6A64C"]
        for ax, palabra, color in zip(axes, palabras, colores * 10):
            posiciones = resultado.get(palabra, [])
            ax.vlines(posiciones, 0, 1, linewidth=0.8, alpha=0.7, color=color)
            ax.set_yticks([])
            ax.set_ylabel(palabra, rotation=0, labelpad=50,
                          fontsize=9, color=_TEXTO, ha="right", va="center")
            ax.set_facecolor(_FONDO)
            for spine in ax.spines.values():
                spine.set_edgecolor("#2A3238")

        axes[-1].set_xlabel("Posición en el corpus (0 = inicio, 1 = final)",
                             color=_TEXTO, fontsize=8)
        plt.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self._frm_disp_canvas)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _coloc_guardar_stopwords(self):
        """Guarda las stopwords personalizadas en ST y en el proyecto."""
        texto = self._txt_stopwords.get("1.0", "end-1c")
        palabras = [p.strip().lower() for p in texto.splitlines() if p.strip()]
        ST.stopwords_proyecto = palabras
        # Actualizar la lista global en collocation_engine para esta sesión
        try:
            import core.collocation_engine as _ce
            _ce.STOPWORDS_ES = _ce.STOPWORDS_ES | frozenset(palabras)
        except Exception:
            pass
        messagebox.showinfo("Guardadas",
                            f"✅ {len(palabras)} stopwords guardadas para este proyecto.")

    def _coloc_graficar_freq(self):
        items = self._tv_freq.get_children()
        if not items:
            messagebox.showwarning("Sin datos", "Calcula las frecuencias primero."); return
        palabras, freqs = [], []
        for iid in list(items)[:25]:
            vals = self._tv_freq.item(iid)["values"]
            palabras.append(str(vals[1]))
            freqs.append(int(vals[2]))

        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            from core.chart_builder import _FONDO, _TEXTO, _fig
        except ImportError:
            messagebox.showerror("Falta matplotlib", "pip install matplotlib"); return

        win = tk.Toplevel(self)
        win.title("Frecuencias léxicas")
        win.geometry("720x480")
        win.configure(bg=TEMA.CONTENT_BG)
        fig, ax = _fig(8, 5)
        ax.barh(palabras[::-1], freqs[::-1], color="#6CA8E8", alpha=0.85)
        ax.set_xlabel("Frecuencia")
        ax.set_title("Palabras más frecuentes del corpus")
        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _build_nov(self):
        self._page_header(self._tab_nov, "Novedad y Cambio Discursivo",
                          "Palabras nuevas · cambio de vocabulario entre períodos · eventos temáticos", "🆕")
        pad = tk.Frame(self._tab_nov, bg=TEMA.CONTENT_BG, padx=16, pady=8)
        pad.pack(fill="both", expand=True)

        nb = ttk.Notebook(pad)
        nb.pack(fill="both", expand=True)

        # ── Sub-pestaña: Cambio discursivo ──
        frm_cd = tk.Frame(nb, bg=TEMA.CONTENT_BG); nb.add(frm_cd, text="  Cambio discursivo  ")
        pad_cd = tk.Frame(frm_cd, bg=TEMA.CONTENT_BG, padx=10, pady=8); pad_cd.pack(fill="both", expand=True)

        tk.Label(pad_cd,
                 text="Mide cuánto cambia el vocabulario entre números consecutivos. "
                      "Alta distancia = cambio abrupto de tema o tono.",
                 bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2, font=("Segoe UI", 9),
                 wraplength=800, justify="left").pack(anchor="w", pady=(0, 8))

        bf_cd = tk.Frame(pad_cd, bg=TEMA.CONTENT_BG); bf_cd.pack(fill="x", pady=(0, 6))
        self._btn_nov_cd = ttk.Button(bf_cd, text="▶  Calcular cambio discursivo",
                                       style="P.TButton", command=self._nov_cambio)
        self._btn_nov_cd.pack(side="left", padx=(0, 8))
        ttk.Button(bf_cd, text="📊  Graficar", style="S.TButton",
                   command=self._nov_graficar_cambio).pack(side="left")
        self._lbl_nov_ok = tk.Label(pad_cd, text="", bg=TEMA.CONTENT_BG, fg=TEMA.VERDE,
                                     font=("Segoe UI", 9, "bold"))
        self._lbl_nov_ok.pack(anchor="w", pady=(0, 4))

        cols_cd = ("periodo_a", "periodo_b", "distancia", "ganadas", "perdidas")
        self._tv_nov_cd = ttk.Treeview(pad_cd, columns=cols_cd, show="headings", height=8)
        for cid, txt, w in [("periodo_a","De",100),("periodo_b","A",100),
                              ("distancia","Distancia",90),
                              ("ganadas","Palabras ganadas",250),
                              ("perdidas","Palabras perdidas",250)]:
            self._tv_nov_cd.heading(cid, text=txt)
            self._tv_nov_cd.column(cid, width=w, anchor="w")
        sv_cd = ttk.Scrollbar(pad_cd, orient="vertical", command=self._tv_nov_cd.yview)
        self._tv_nov_cd.configure(yscrollcommand=sv_cd.set)
        self._tv_nov_cd.pack(side="left", fill="both", expand=True)
        sv_cd.pack(side="left", fill="y")
        self._nov_cambio_data = []

        # ── Sub-pestaña: Palabras nuevas ──
        frm_pn = tk.Frame(nb, bg=TEMA.CONTENT_BG); nb.add(frm_pn, text="  Palabras nuevas  ")
        pad_pn = tk.Frame(frm_pn, bg=TEMA.CONTENT_BG, padx=10, pady=8); pad_pn.pack(fill="both", expand=True)

        bf_pn = tk.Frame(pad_pn, bg=TEMA.CONTENT_BG); bf_pn.pack(fill="x", pady=(0, 6))
        tk.Label(bf_pn, text="Freq. mínima:", bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self._var_nov_freq = tk.IntVar(value=3)
        ttk.Spinbox(bf_pn, from_=1, to=20, textvariable=self._var_nov_freq,
                    width=4).pack(side="left", padx=(0, 8))
        ttk.Button(bf_pn, text="▶  Detectar palabras nuevas", style="P.TButton",
                   command=self._nov_palabras_nuevas).pack(side="left")

        self._txt_nov_pn = scrolledtext.ScrolledText(pad_pn, font=("Consolas", 9),
                                                      bg="#12171B", fg="#E8E5DF",
                                                      height=18, relief="flat")
        self._txt_nov_pn.pack(fill="both", expand=True)

        # ── Sub-pestaña: Tendencia de términos ──
        frm_td = tk.Frame(nb, bg=TEMA.CONTENT_BG); nb.add(frm_td, text="  Tendencia de términos  ")
        pad_td = tk.Frame(frm_td, bg=TEMA.CONTENT_BG, padx=10, pady=8); pad_td.pack(fill="both", expand=True)

        tk.Label(pad_td, text="Términos a seguir (separados por coma):",
                 bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2, font=("Segoe UI", 9)).pack(anchor="w")
        self._var_nov_terms = tk.StringVar(value="radio, cine, mujer, guerra, colombia")
        tk.Entry(pad_td, textvariable=self._var_nov_terms, width=60,
                 font=("Segoe UI", 9), relief="solid", bd=1,
                 bg="#12171B", fg="#E8E5DF").pack(anchor="w", pady=(4, 8))
        bf_td = tk.Frame(pad_td, bg=TEMA.CONTENT_BG); bf_td.pack(fill="x", pady=(0, 6))
        ttk.Button(bf_td, text="▶  Calcular tendencia", style="P.TButton",
                   command=self._nov_tendencia).pack(side="left", padx=(0, 8))
        ttk.Button(bf_td, text="📊  Graficar", style="S.TButton",
                   command=self._nov_graficar_tendencia).pack(side="left")
        self._nov_tendencia_data = {}
        self._lbl_nov_td = tk.Label(pad_td, text="", bg=TEMA.CONTENT_BG, fg=TEMA.VERDE,
                                     font=("Segoe UI", 9, "bold"))
        self._lbl_nov_td.pack(anchor="w", pady=(0, 4))
        self._txt_nov_td = scrolledtext.ScrolledText(pad_td, font=("Consolas", 9),
                                                      bg="#12171B", fg="#E8E5DF",
                                                      height=14, relief="flat")
        self._txt_nov_td.pack(fill="both", expand=True)

    def _nov_corpus_por_periodo(self) -> dict:
        """Agrupa textos del corpus por número."""
        from core.servicios_corpus import agrupar_por_numero
        return agrupar_por_numero(getattr(ST, "articulos", None),
                                  getattr(ST, "corpus_txt", None))

    def _nov_cambio(self):
        from core.novelty_engine import cambio_discursivo
        corpus = self._nov_corpus_por_periodo()
        if len(corpus) < 2:
            messagebox.showwarning("Pocos datos",
                "Se necesitan al menos 2 períodos. Segmenta el corpus primero."); return
        self._btn_nov_cd.config(state="disabled")
        self._lbl_nov_ok.config(text="Calculando…")

        def _worker():
            res = cambio_discursivo(corpus)
            self._nov_cambio_data = res
            def _show():
                for row in self._tv_nov_cd.get_children():
                    self._tv_nov_cd.delete(row)
                for r in res:
                    ganadas  = ", ".join(g["palabra"] for g in r["palabras_ganadas"][:5])
                    perdidas = ", ".join(p["palabra"] for p in r["palabras_perdidas"][:5])
                    self._tv_nov_cd.insert("", "end", values=(
                        r["periodo_a"], r["periodo_b"],
                        f"{r['distancia']:.3f}", ganadas, perdidas))
                self._lbl_nov_ok.config(
                    text=f"✅ {len(res)} transiciones analizadas")
                self._btn_nov_cd.config(state="normal")
            self.after(0, _show)

        threading.Thread(target=_worker, daemon=True).start()

    def _nov_graficar_cambio(self):
        if not self._nov_cambio_data:
            messagebox.showwarning("Sin datos", "Calcula el cambio discursivo primero."); return
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            from core.chart_builder import _fig
        except ImportError:
            messagebox.showerror("Falta matplotlib", "pip install matplotlib"); return

        pares = [f"{r['periodo_a']}→{r['periodo_b']}" for r in self._nov_cambio_data]
        dists = [r["distancia"] for r in self._nov_cambio_data]
        pares_ord = [x for _, x in sorted(zip(
            [r["periodo_a"] for r in self._nov_cambio_data], pares))]
        dists_ord = [d for _, d in sorted(zip(
            [r["periodo_a"] for r in self._nov_cambio_data], dists))]

        win = tk.Toplevel(self)
        win.title("Cambio discursivo por período")
        win.geometry("720x400")
        win.configure(bg=TEMA.CONTENT_BG)
        fig, ax = _fig(8, 4)
        colores = ["#D96B6B" if d > 0.5 else "#6CA8E8" for d in dists_ord]
        ax.bar(pares_ord, dists_ord, color=colores, alpha=0.85)
        ax.axhline(0.5, color="#E6A64C", linestyle="--", linewidth=1, label="umbral alto")
        ax.set_ylabel("Distancia coseno")
        ax.set_title("Cambio discursivo entre períodos consecutivos")
        ax.legend(facecolor="#1C2227", labelcolor="#E8E5DF", fontsize=8)
        plt.xticks(rotation=35, ha="right")
        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _nov_palabras_nuevas(self):
        from core.novelty_engine import palabras_nuevas
        corpus = self._nov_corpus_por_periodo()
        if not corpus:
            messagebox.showwarning("Sin corpus", "Segmenta el corpus primero."); return

        def _worker():
            res = palabras_nuevas(corpus, min_freq=self._var_nov_freq.get())
            def _show():
                self._txt_nov_pn.config(state="normal")
                self._txt_nov_pn.delete("1.0", "end")
                for periodo in sorted(res.keys()):
                    nuevas = res[periodo]
                    self._txt_nov_pn.insert("end",
                        f"── {periodo} ({len(nuevas)} palabras nuevas) ──\n",
                        "titulo")
                    if nuevas:
                        self._txt_nov_pn.insert("end",
                            "  " + ", ".join(nuevas[:40]) + "\n\n")
                    else:
                        self._txt_nov_pn.insert("end", "  (ninguna)\n\n")
                self._txt_nov_pn.tag_configure(
                    "titulo", foreground="#6CA8E8", font=("Consolas", 9, "bold"))
                self._txt_nov_pn.config(state="disabled")
            self.after(0, _show)

        threading.Thread(target=_worker, daemon=True).start()

    def _nov_tendencia(self):
        from core.novelty_engine import tendencia_vocabulario
        corpus = self._nov_corpus_por_periodo()
        if not corpus:
            messagebox.showwarning("Sin corpus", "Segmenta el corpus primero."); return
        palabras = [p.strip() for p in self._var_nov_terms.get().split(",") if p.strip()]
        if not palabras:
            messagebox.showwarning("Sin términos", "Escribe términos a seguir."); return

        def _worker():
            res = tendencia_vocabulario(corpus, palabras)
            self._nov_tendencia_data = res
            def _show():
                self._txt_nov_td.config(state="normal")
                self._txt_nov_td.delete("1.0", "end")
                periodos = sorted(corpus.keys())
                header = f"{'Término':<20}" + "".join(f"{p:<14}" for p in periodos) + "\n"
                self._txt_nov_td.insert("end", header, "header")
                self._txt_nov_td.insert("end", "─" * len(header) + "\n")
                for palabra in palabras:
                    row = f"{palabra:<20}"
                    for p in periodos:
                        v = res.get(palabra, {}).get(p, 0)
                        row += f"{v:<14.1f}"
                    self._txt_nov_td.insert("end", row + "\n")
                self._txt_nov_td.tag_configure(
                    "header", foreground="#E6A64C", font=("Consolas", 9, "bold"))
                self._lbl_nov_td.config(text=f"✅ Tendencia de {len(palabras)} términos")
                self._txt_nov_td.config(state="disabled")
            self.after(0, _show)

        threading.Thread(target=_worker, daemon=True).start()

    def _nov_graficar_tendencia(self):
        if not self._nov_tendencia_data:
            messagebox.showwarning("Sin datos", "Calcula la tendencia primero."); return
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            from core.chart_builder import PALETA, _fig
        except ImportError:
            messagebox.showerror("Falta matplotlib", "pip install matplotlib"); return

        win = tk.Toplevel(self)
        win.title("Tendencia de vocabulario")
        win.geometry("760x460")
        win.configure(bg=TEMA.CONTENT_BG)
        fig, ax = _fig(9, 5)
        corpus = self._nov_corpus_por_periodo()
        periodos = sorted(corpus.keys())
        for i, (palabra, por_periodo) in enumerate(self._nov_tendencia_data.items()):
            vals = [por_periodo.get(p, 0) for p in periodos]
            ax.plot(periodos, vals, marker="o", label=palabra,
                    color=PALETA[i % len(PALETA)], linewidth=2)
        ax.set_ylabel("Frecuencia relativa (×10.000)")
        ax.set_title("Tendencia de términos a lo largo del corpus")
        ax.legend(facecolor="#1C2227", labelcolor="#E8E5DF", fontsize=8)
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _build_sem(self):
        outer = tk.Frame(self._tab_sem, bg=TEMA.CONTENT_BG)
        outer.pack(fill="both", expand=True, padx=16, pady=12)

        self._sem_params: dict = {}
        try:
            from core.sentiment_engine import PARAMS_SCHEMA as _SEM_SCHEMA
            self._build_params_panel(outer, _SEM_SCHEMA, self._sem_params)
        except Exception:
            pass

        pad = tk.Frame(outer, bg=TEMA.CONTENT_BG)
        pad.pack(side="left", fill="both", expand=True)

        tk.Label(pad, text="Análisis semántico profundo", bg=TEMA.CONTENT_BG,
                 fg="#E8E5DF", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(pad, text="Tono editorial, léxico histórico y estilometría del corpus Estampa.",
                 bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 10))

        # ── Pestañas internas ─────────────────────────────────────────────────
        nb = ttk.Notebook(pad)
        nb.pack(fill="both", expand=True)

        # Tab Tono
        frm_tono = tk.Frame(nb, bg=TEMA.CONTENT_BG)
        nb.add(frm_tono, text="  Tono editorial  ")
        self._build_sem_tono(frm_tono)

        # Tab Léxico
        frm_lex = tk.Frame(nb, bg=TEMA.CONTENT_BG)
        nb.add(frm_lex, text="  Léxico histórico  ")
        self._build_sem_lexico(frm_lex)

        # Tab Estilometría
        frm_estilo = tk.Frame(nb, bg=TEMA.CONTENT_BG)
        nb.add(frm_estilo, text="  Estilometría  ")
        self._build_sem_estilo(frm_estilo)

    # ── Sub-panel: Tono editorial ─────────────────────────────────────────────
    def _build_sem_tono(self, parent):
        from core.sentiment_engine import COLORES_TONO
        pad = tk.Frame(parent, bg=TEMA.CONTENT_BG, padx=10, pady=8)
        pad.pack(fill="both", expand=True)

        # ── Botones principales ──
        bf = tk.Frame(pad, bg=TEMA.CONTENT_BG)
        bf.pack(fill="x", pady=(0, 4))
        self._btn_tono_art = ttk.Button(bf, text="▶  Artículo actual",
                                         style="P.TButton",
                                         command=self._sem_tono_articulo)
        self._btn_tono_art.pack(side="left", padx=(0, 8))
        self._btn_tono_corpus = ttk.Button(bf, text="📚  Corpus completo",
                                            style="S.TButton",
                                            command=self._sem_tono_corpus)
        self._btn_tono_corpus.pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="📊  Ver evolución",
                   style="S.TButton",
                   command=self._sem_tono_ver_evolucion).pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="📝  Síntesis narrativa",
                   style="S.TButton",
                   command=self._sem_tono_narrativa).pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="💾  Exportar CSV",
                   style="S.TButton",
                   command=self._sem_tono_exportar).pack(side="right")

        self._lbl_tono_ok = tk.Label(pad, text="", bg=TEMA.CONTENT_BG, fg=TEMA.VERDE,
                                      font=("Segoe UI", 9, "bold"))
        self._lbl_tono_ok.pack(anchor="w", pady=(0, 4))

        # ── Chips de distribución (se actualizan al terminar el análisis) ──
        self._frm_tono_chips = tk.Frame(pad, bg=TEMA.CONTENT_BG)
        self._frm_tono_chips.pack(fill="x", pady=(0, 6))
        self._tono_chips = {}
        tonos_orden = ("celebratorio", "crítico", "neutro", "elegíaco", "polémico", "informativo")
        for tono in tonos_orden:
            color = COLORES_TONO.get(tono, "#777F84")
            frm = tk.Frame(self._frm_tono_chips, bg=color, padx=6, pady=2)
            frm.pack(side="left", padx=(0, 4))
            lbl = tk.Label(frm, text=f"{tono}: —", bg=color, fg="white",
                           font=("Segoe UI", 8, "bold"))
            lbl.pack()
            self._tono_chips[tono] = lbl

        # ── Filtro por campo ──
        ff = tk.Frame(pad, bg=TEMA.CONTENT_BG)
        ff.pack(fill="x", pady=(0, 4))
        tk.Label(ff, text="Filtrar por:", bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self._var_tono_filtro_campo = tk.StringVar(value="todos")
        self._var_tono_filtro_valor = tk.StringVar(value="")
        ttk.Combobox(ff, textvariable=self._var_tono_filtro_campo,
                     values=["todos", "tono_principal", "intensidad", "numero"],
                     state="readonly", width=14).pack(side="left", padx=(0, 4))
        ttk.Entry(ff, textvariable=self._var_tono_filtro_valor,
                  width=16).pack(side="left", padx=(0, 8))
        ttk.Button(ff, text="Filtrar", style="S.TButton",
                   command=self._sem_tono_refrescar).pack(side="left")

        # ── Tabla resultados ──
        cols = ("articulo", "tono_principal", "tono_sec", "intensidad",
                "confianza", "numero", "resumen")
        self._tv_tono = ttk.Treeview(pad, columns=cols, show="headings", height=11)
        heads = [("articulo",      "Artículo",       130),
                 ("tono_principal","Tono principal",  110),
                 ("tono_sec",      "Secundario",       90),
                 ("intensidad",    "Intensidad",       75),
                 ("confianza",     "Confianza",        70),
                 ("numero",        "Número",           80),
                 ("resumen",       "Resumen",         330)]
        for cid, txt, w in heads:
            self._tv_tono.heading(cid, text=txt)
            self._tv_tono.column(cid, width=w, anchor="w")
        sv = ttk.Scrollbar(pad, orient="vertical", command=self._tv_tono.yview)
        self._tv_tono.configure(yscrollcommand=sv.set)
        self._tv_tono.pack(side="left", fill="both", expand=True)
        sv.pack(side="left", fill="y")

        # Tags de color por tono
        for tono, color in COLORES_TONO.items():
            self._tv_tono.tag_configure(tono, foreground=color)

        self._tono_resultados = {}

    # ── Sub-panel: Léxico histórico ───────────────────────────────────────────
    def _build_sem_lexico(self, parent):
        pad = tk.Frame(parent, bg=TEMA.CONTENT_BG, padx=10, pady=8)
        pad.pack(fill="both", expand=True)

        bf = tk.Frame(pad, bg=TEMA.CONTENT_BG)
        bf.pack(fill="x", pady=(0, 6))
        self._btn_lex_art = ttk.Button(bf, text="▶  Artículo actual",
                                        style="P.TButton",
                                        command=self._sem_lex_articulo)
        self._btn_lex_art.pack(side="left", padx=(0, 8))
        self._btn_lex_corpus = ttk.Button(bf, text="📚  Corpus completo",
                                           style="S.TButton",
                                           command=self._sem_lex_corpus)
        self._btn_lex_corpus.pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="💾  Exportar glosario",
                   style="S.TButton",
                   command=self._sem_lex_exportar).pack(side="right")
        self._lbl_lex_ok = tk.Label(pad, text="", bg=TEMA.CONTENT_BG, fg=TEMA.VERDE,
                                     font=("Segoe UI", 9, "bold"))
        self._lbl_lex_ok.pack(anchor="w", pady=(0, 4))

        # Filtro categoría
        fi = tk.Frame(pad, bg=TEMA.CONTENT_BG)
        fi.pack(fill="x", pady=(0, 4))
        tk.Label(fi, text="Categoría:", bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self._var_lex_cat = tk.StringVar(value="Todas")
        cats = ["Todas", "arcaismos", "neologismos", "colombianismos", "tecnicismos"]
        ttk.Combobox(fi, textvariable=self._var_lex_cat, values=cats,
                     state="readonly", width=14).pack(side="left")

        # Tabla
        cols = ("categoria", "palabra", "n_arts", "info")
        self._tv_lex = ttk.Treeview(pad, columns=cols, show="headings", height=12)
        heads = [("categoria", "Categoría", 110), ("palabra", "Palabra", 140),
                 ("n_arts", "Artículos", 70), ("info", "Información", 380)]
        for cid, txt, w in heads:
            self._tv_lex.heading(cid, text=txt)
            self._tv_lex.column(cid, width=w, anchor="w")
        sv = ttk.Scrollbar(pad, orient="vertical", command=self._tv_lex.yview)
        self._tv_lex.configure(yscrollcommand=sv.set)
        self._tv_lex.pack(side="left", fill="both", expand=True)
        sv.pack(side="left", fill="y")

        self._glosario_data = {}

    # ── Sub-panel: Estilometría ───────────────────────────────────────────────
    def _build_sem_estilo(self, parent):
        pad = tk.Frame(parent, bg=TEMA.CONTENT_BG, padx=10, pady=8)
        pad.pack(fill="both", expand=True)

        tk.Label(pad, text="Agrupa artículos anónimos por similitud estilística (TF-IDF n-gramas de caracteres).",
                 bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 6))

        cf = tk.Frame(pad, bg=TEMA.CONTENT_BG)
        cf.pack(fill="x", pady=(0, 6))
        tk.Label(cf, text="N° clusters:", bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self._var_estilo_clusters = tk.IntVar(value=5)
        ttk.Spinbox(cf, from_=2, to=15, textvariable=self._var_estilo_clusters,
                    width=4).pack(side="left")

        bf = tk.Frame(pad, bg=TEMA.CONTENT_BG)
        bf.pack(fill="x", pady=(0, 6))
        self._btn_estilo = ttk.Button(bf, text="▶  Calcular clusters",
                                       style="P.TButton",
                                       command=self._sem_estilo_calcular)
        self._btn_estilo.pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="💾  Exportar CSV",
                   style="S.TButton",
                   command=self._sem_estilo_exportar).pack(side="left")
        self._lbl_estilo_ok = tk.Label(pad, text="", bg=TEMA.CONTENT_BG, fg=TEMA.VERDE,
                                        font=("Segoe UI", 9, "bold"))
        self._lbl_estilo_ok.pack(anchor="w", pady=(0, 4))

        cols = ("articulo", "cluster")
        self._tv_estilo = ttk.Treeview(pad, columns=cols, show="headings", height=14)
        self._tv_estilo.heading("articulo", text="Artículo")
        self._tv_estilo.heading("cluster",  text="Cluster")
        self._tv_estilo.column("articulo", width=300, anchor="w")
        self._tv_estilo.column("cluster",  width=80,  anchor="center")
        sv = ttk.Scrollbar(pad, orient="vertical", command=self._tv_estilo.yview)
        self._tv_estilo.configure(yscrollcommand=sv.set)
        self._tv_estilo.pack(side="left", fill="both", expand=True)
        sv.pack(side="left", fill="y")

        self._estilo_resultados = {}

    # ── Workers: Tono ─────────────────────────────────────────────────────────
    def _sem_tono_articulo(self):
        api_key, _m = _resolver_api_key_modelo("tono")
        if not api_key:
            messagebox.showwarning("Sin API key", "Configura tu clave Claude API en Configuración.")
            return
        texto, art_id = self._ner_articulo_actual()
        if not texto:
            return
        self._btn_tono_art.config(state="disabled")
        threading.Thread(target=self._worker_tono, args=({art_id: texto},),
                         daemon=True).start()

    def _sem_tono_corpus(self):
        api_key, _m = _resolver_api_key_modelo("tono")
        if not api_key:
            messagebox.showwarning("Sin API key", "Configura tu clave Claude API en Configuración.")
            return
        if not getattr(ST, "corpus_txt", None):
            messagebox.showwarning("Sin corpus", "Extrae el texto del corpus primero.")
            return
        self._btn_tono_corpus.config(state="disabled")
        # Enriquecer entradas con metadatos disponibles en ST
        articulos = ST.articulos if getattr(ST, "articulos", None) else []
        entradas = {}
        for i, texto in enumerate(ST.corpus_txt):
            if not texto or not texto.strip():
                continue
            art_id = str(i)
            entrada = {"texto": texto}
            if i < len(articulos):
                art = articulos[i]
                entrada["seccion"]  = art.get("tipo", "")
                entrada["numero"]   = art.get("numero", "")
                entrada["autor"]    = art.get("autor", "")
            entradas[art_id] = entrada
        threading.Thread(target=self._worker_tono, args=(entradas,),
                         daemon=True).start()

    def _sem_tono_actualizar_chips(self, stats):
        dist = stats.get("distribucion", {})
        for tono, lbl in self._tono_chips.items():
            pct = dist.get(tono, {}).get("porcentaje", 0.0)
            n   = dist.get(tono, {}).get("n", 0)
            lbl.config(text=f"{tono}: {pct}% ({n})")

    def _sem_tono_refrescar(self):
        for row in self._tv_tono.get_children():
            self._tv_tono.delete(row)

        campo  = self._var_tono_filtro_campo.get()
        valor  = self._var_tono_filtro_valor.get().strip().lower()

        for art_id, res in self._tono_resultados.items():
            tono = res.get("tono_principal", "neutro")
            # Filtro
            if campo != "todos" and valor:
                val_campo = str(res.get(campo, "")).lower()
                if valor not in val_campo:
                    continue
            self._tv_tono.insert("", "end",
                tags=(tono,),
                values=(
                    art_id,
                    tono,
                    res.get("tono_secundario", "") or "",
                    res.get("intensidad", ""),
                    f"{res.get('confianza', 0):.2f}",
                    res.get("numero", ""),
                    res.get("resumen", ""),
                ))

    def _sem_tono_ver_evolucion(self):
        from core.sentiment_engine import (
            COLORES_TONO,
            evolucion_temporal,
            tendencia_tono,
        )
        if not self._tono_resultados:
            messagebox.showwarning("Sin datos", "Analiza el tono del corpus primero.")
            return

        evol = evolucion_temporal(self._tono_resultados, campo_periodo="numero")
        if len(evol) < 2:
            messagebox.showinfo("Evolución temporal",
                "Se necesitan al menos 2 números para ver la evolución temporal.\n"
                "Analiza el corpus completo primero.")
            return

        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except ImportError:
            messagebox.showerror("Falta matplotlib",
                "Instala matplotlib para ver el gráfico.")
            return

        win = tk.Toplevel(self)
        win.title("Evolución temporal del tono editorial")
        win.geometry("860x520")
        win.configure(bg=TEMA.CONTENT_BG)

        periodos = sorted(evol.keys())
        fig, ax = plt.subplots(figsize=(9, 4.5))
        fig.patch.set_facecolor("#171C20")
        ax.set_facecolor("#171C20")

        tonos_a_mostrar = ("celebratorio", "crítico", "elegíaco", "polémico")
        for tono in tonos_a_mostrar:
            vals = [evol[p].get(tono, 0.0) for p in periodos]
            t_info = tendencia_tono(evol, tono)
            dir_arrow = {"sube": " ↑", "baja": " ↓", "estable": ""}.get(
                t_info["direccion"], "")
            ax.plot(periodos, vals,
                    marker="o", linewidth=2,
                    color=COLORES_TONO.get(tono, "#777F84"),
                    label=f"{tono}{dir_arrow}")

        ax.set_xlabel("Número", color="#E8E5DF", fontsize=9)
        ax.set_ylabel("% artículos", color="#E8E5DF", fontsize=9)
        ax.set_title("Evolución del tono editorial por número", color="#E8E5DF", fontsize=10)
        ax.tick_params(colors="#E8E5DF", labelsize=8)
        ax.legend(facecolor="#1C2227", labelcolor="#E8E5DF", fontsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#2A3238")
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

        # Tabla de tendencias
        tf = tk.Frame(win, bg=TEMA.CONTENT_BG)
        tf.pack(fill="x", padx=10, pady=(0, 8))
        for tono in tonos_a_mostrar:
            t_info = tendencia_tono(evol, tono)
            color = COLORES_TONO.get(tono, "#777F84")
            icono = {"sube": "↑", "baja": "↓", "estable": "→"}.get(t_info["direccion"], "")
            tk.Label(tf, text=f"{icono} {tono}  (pend. {t_info['pendiente']:+.2f})",
                     bg=TEMA.CONTENT_BG, fg=color,
                     font=("Segoe UI", 9, "bold")).pack(side="left", padx=8)

    def _sem_tono_narrativa(self):
        from core.sentiment_engine import (
            estadisticas_tono,
            evolucion_temporal,
            resumen_narrativo,
        )
        if not self._tono_resultados:
            messagebox.showwarning("Sin datos", "Analiza el tono del corpus primero.")
            return
        api_key, _m = _resolver_api_key_modelo("tono")
        if not api_key:
            messagebox.showwarning("Sin API key", "Configura tu clave Claude API.")
            return

        win = tk.Toplevel(self)
        win.title("Síntesis narrativa del tono editorial")
        win.geometry("680x360")
        win.configure(bg=TEMA.CONTENT_BG)

        lbl = tk.Label(win, text="Generando síntesis…", bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2,
                       font=("Segoe UI", 9))
        lbl.pack(anchor="w", padx=16, pady=(12, 4))
        txt = tk.Text(win, bg="#171C20", fg="#E8E5DF", font=("Segoe UI", 10),
                      wrap="word", padx=12, pady=10, relief="flat")
        txt.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        def _generar():
            stats = estadisticas_tono(self._tono_resultados)
            evol  = evolucion_temporal(self._tono_resultados, "numero")
            nombre = getattr(ST, "nombre_proyecto", "el corpus")
            parrafo = resumen_narrativo(stats, evol, api_key, nombre_corpus=nombre)
            self.after(0, lambda: lbl.config(text="Síntesis generada"))
            self.after(0, lambda: txt.insert("1.0", parrafo or "No se pudo generar la síntesis."))

        threading.Thread(target=_generar, daemon=True).start()

    def _sem_tono_exportar(self):
        if not self._tono_resultados:
            messagebox.showwarning("Sin datos", "Analiza el tono del corpus primero.")
            return
        import csv
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
            initialfile="tono_editorial.csv",
            title="Guardar análisis de tono")
        if not dest:
            return
        fieldnames = ["articulo", "tono_principal", "tono_secundario", "intensidad",
                      "confianza", "numero", "seccion", "autor", "resumen", "indicadores"]
        with open(dest, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            for art_id, res in self._tono_resultados.items():
                inds = res.get("indicadores", [])
                w.writerow({
                    "articulo":        art_id,
                    "tono_principal":  res.get("tono_principal", ""),
                    "tono_secundario": res.get("tono_secundario", "") or "",
                    "intensidad":      res.get("intensidad", ""),
                    "confianza":       res.get("confianza", 0),
                    "numero":          res.get("numero", ""),
                    "seccion":         res.get("seccion", ""),
                    "autor":           res.get("autor", ""),
                    "resumen":         res.get("resumen", ""),
                    "indicadores":     "; ".join(inds) if isinstance(inds, list) else str(inds),
                })
        messagebox.showinfo("Exportado", f"Tono exportado a:\n{dest}")

    # ── Workers: Léxico ───────────────────────────────────────────────────────
    def _sem_lex_articulo(self):
        api_key, _m = _resolver_api_key_modelo("tono")
        if not api_key:
            messagebox.showwarning("Sin API key", "Configura tu clave Claude API en Configuración.")
            return
        texto, art_id = self._ner_articulo_actual()
        if not texto:
            return
        self._btn_lex_art.config(state="disabled")
        threading.Thread(target=self._worker_lexico, args=({art_id: texto},),
                         daemon=True).start()

    def _sem_lex_corpus(self):
        api_key, _m = _resolver_api_key_modelo("tono")
        if not api_key:
            messagebox.showwarning("Sin API key", "Configura tu clave Claude API en Configuración.")
            return
        if not getattr(ST, "corpus_txt", None):
            messagebox.showwarning("Sin corpus", "Extrae el texto del corpus primero.")
            return
        self._btn_lex_corpus.config(state="disabled")
        textos = {str(i): t for i, t in enumerate(ST.corpus_txt) if t and t.strip()}
        threading.Thread(target=self._worker_lexico, args=(textos,), daemon=True).start()

    def _sem_lex_refrescar(self):
        for row in self._tv_lex.get_children():
            self._tv_lex.delete(row)
        cat_filtro = self._var_lex_cat.get()
        for cat, entradas in self._glosario_data.items():
            if cat_filtro not in ("Todas", cat):
                continue
            for palabra, info in sorted(entradas.items()):
                extra = info.get("definicion") or info.get("significado") or info.get("origen") or ""
                n_arts = len(info.get("articulos", []))
                self._tv_lex.insert("", "end", values=(cat, palabra, n_arts, extra))

    def _sem_lex_exportar(self):
        if not self._glosario_data:
            messagebox.showwarning("Sin datos", "Construye el glosario primero.")
            return
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
            initialfile="glosario_estampa.csv",
            title="Guardar glosario")
        if not dest:
            return
        from pathlib import Path as _PPath

        from core.lexicon_engine import exportar_glosario_csv
        n = exportar_glosario_csv(self._glosario_data, _PPath(dest))
        messagebox.showinfo("Exportado", f"✅ {n} entradas exportadas a:\n{dest}")

    # ── Workers: Estilometría ─────────────────────────────────────────────────
    def _sem_estilo_calcular(self):
        if not getattr(ST, "corpus_txt", None):
            messagebox.showwarning("Sin corpus", "Extrae el texto del corpus primero.")
            return
        n_clusters = self._var_estilo_clusters.get()
        textos = {str(i): t for i, t in enumerate(ST.corpus_txt) if t and t.strip()}
        if len(textos) < 2:
            messagebox.showwarning("Datos insuficientes", "Se necesitan al menos 2 artículos.")
            return
        self._btn_estilo.config(state="disabled")
        threading.Thread(target=self._worker_estilo, args=(textos, n_clusters),
                         daemon=True).start()

    def _sem_estilo_refrescar(self):
        for row in self._tv_estilo.get_children():
            self._tv_estilo.delete(row)
        for art_id, cluster in sorted(self._estilo_resultados.items(),
                                       key=lambda x: (x[1], x[0])):
            self._tv_estilo.insert("", "end", values=(art_id, cluster))

    def _sem_estilo_exportar(self):
        if not self._estilo_resultados:
            messagebox.showwarning("Sin datos", "Calcula los clusters primero.")
            return
        import csv
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="estilometria_clusters.csv",
            title="Exportar estilometría")
        if not dest:
            return
        with open(dest, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["articulo", "cluster"])
            w.writeheader()
            for art_id, cluster in self._estilo_resultados.items():
                w.writerow({"articulo": art_id, "cluster": cluster})
        messagebox.showinfo("Exportado", f"Clusters exportados a:\n{dest}")

    def _build_viz(self):
        from core.chart_builder import CATALOGO
        pad = tk.Frame(self._tab_viz, bg=TEMA.CONTENT_BG, padx=16, pady=12)
        pad.pack(fill="both", expand=True)

        tk.Label(pad, text="Constructor de visualizaciones", bg=TEMA.CONTENT_BG,
                 fg="#E8E5DF", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(pad,
                 text="Selecciona qué dato graficar y con qué tipo de gráfico. "
                      "Cada opción incluye una descripción de cuándo usarla.",
                 bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 10))

        nb = ttk.Notebook(pad)
        nb.pack(fill="both", expand=True)

        # ── Pestaña: Constructor interactivo ──────────────────────────────────
        frm_build = tk.Frame(nb, bg=TEMA.CONTENT_BG)
        nb.add(frm_build, text="  Constructor  ")
        self._build_viz_constructor(frm_build, CATALOGO)

        # ── Pestañas legacy (se mantienen para compatibilidad) ────────────────
        frm_nube = tk.Frame(nb, bg=TEMA.CONTENT_BG)
        nb.add(frm_nube, text="  Nube de palabras  ")
        self._build_viz_nube(frm_nube)

        frm_heat = tk.Frame(nb, bg=TEMA.CONTENT_BG)
        nb.add(frm_heat, text="  Heatmap términos  ")
        self._build_viz_heatmap(frm_heat)

        frm_mapa = tk.Frame(nb, bg=TEMA.CONTENT_BG)
        nb.add(frm_mapa, text="  Mapa  ")
        self._build_viz_mapa(frm_mapa)

        frm_tl = tk.Frame(nb, bg=TEMA.CONTENT_BG)
        nb.add(frm_tl, text="  Timeline  ")
        self._build_viz_timeline(frm_tl)

    # ── Constructor interactivo de gráficos ───────────────────────────────────
    def _build_viz_constructor(self, parent, catalogo):
        pad = tk.Frame(parent, bg=TEMA.CONTENT_BG, padx=10, pady=8)
        pad.pack(fill="both", expand=True)

        # ── Fila de selectores ──
        sel_frm = tk.Frame(pad, bg=TEMA.CONTENT_BG)
        sel_frm.pack(fill="x", pady=(0, 6))

        tk.Label(sel_frm, text="Fuente de datos:", bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2,
                 font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", padx=(0, 6))
        self._var_viz_fuente = tk.StringVar()
        fuentes = list(catalogo.keys())
        cb_fuente = ttk.Combobox(sel_frm, textvariable=self._var_viz_fuente,
                                  values=fuentes, state="readonly", width=20)
        cb_fuente.grid(row=0, column=1, padx=(0, 16))
        cb_fuente.current(0)

        tk.Label(sel_frm, text="Tipo de gráfico:", bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2,
                 font=("Segoe UI", 9)).grid(row=0, column=2, sticky="w", padx=(0, 6))
        self._var_viz_tipo = tk.StringVar()
        self._cb_viz_tipo = ttk.Combobox(sel_frm, textvariable=self._var_viz_tipo,
                                          values=[], state="readonly", width=28)
        self._cb_viz_tipo.grid(row=0, column=3, padx=(0, 16))

        tk.Label(sel_frm, text="Título (opcional):", bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2,
                 font=("Segoe UI", 9)).grid(row=0, column=4, sticky="w", padx=(0, 6))
        self._var_viz_titulo = tk.StringVar()
        tk.Entry(sel_frm, textvariable=self._var_viz_titulo,
                 width=22, font=("Segoe UI", 9),
                 relief="solid", bd=1, bg="#12171B", fg="#E8E5DF"
                 ).grid(row=0, column=5, padx=(0, 8))

        self._btn_viz_gen = ttk.Button(sel_frm, text="▶  Generar",
                                        style="P.TButton",
                                        command=self._viz_generar)
        self._btn_viz_gen.grid(row=0, column=6, padx=(0, 8))
        ttk.Button(sel_frm, text="💾  Guardar PNG",
                   style="S.TButton",
                   command=self._viz_guardar).grid(row=0, column=7)

        # ── Descripción del gráfico seleccionado ──
        self._lbl_viz_desc = tk.Label(pad, text="",
                                       bg=TEMA.CONTENT_BG, fg="#B5B6B3",
                                       font=("Segoe UI", 8), wraplength=900,
                                       justify="left")
        self._lbl_viz_desc.pack(anchor="w", pady=(0, 4))

        self._lbl_viz_ok = tk.Label(pad, text="", bg=TEMA.CONTENT_BG, fg=TEMA.VERDE,
                                     font=("Segoe UI", 9, "bold"))
        self._lbl_viz_ok.pack(anchor="w", pady=(0, 4))

        # ── Canvas para el gráfico ──
        self._frm_viz_canvas = tk.Frame(pad, bg=TEMA.CONTENT_BG)
        self._frm_viz_canvas.pack(fill="both", expand=True)
        self._viz_canvas_widget = None
        self._viz_fig_actual    = None

        # ── Conectar eventos ──
        self._viz_catalogo = catalogo
        cb_fuente.bind("<<ComboboxSelected>>", self._viz_actualizar_tipos)
        self._cb_viz_tipo.bind("<<ComboboxSelected>>", self._viz_actualizar_desc)
        self._viz_actualizar_tipos()

    def _viz_actualizar_tipos(self, _event=None):
        fuente = self._var_viz_fuente.get()
        opciones = self._viz_catalogo.get(fuente, [])
        labels = [o["label"] for o in opciones]
        self._cb_viz_tipo["values"] = labels
        if labels:
            self._cb_viz_tipo.current(0)
        self._viz_actualizar_desc()

    def _viz_actualizar_desc(self, _event=None):
        fuente = self._var_viz_fuente.get()
        tipo   = self._var_viz_tipo.get()
        opciones = self._viz_catalogo.get(fuente, [])
        for op in opciones:
            if op["label"] == tipo:
                self._lbl_viz_desc.config(text=f"ℹ  {op['desc']}")
                return
        self._lbl_viz_desc.config(text="")

    def _viz_generar(self):
        fuente = self._var_viz_fuente.get()
        tipo   = self._var_viz_tipo.get()
        titulo = self._var_viz_titulo.get().strip()
        opciones = self._viz_catalogo.get(fuente, [])
        op = next((o for o in opciones if o["label"] == tipo), None)
        if not op:
            return

        self._btn_viz_gen.config(state="disabled")
        self._lbl_viz_ok.config(text="Generando…")
        threading.Thread(target=self._viz_worker, args=(op, titulo),
                         daemon=True).start()

    def _viz_worker(self, op, titulo):
        try:
            fig = self._viz_obtener_datos_y_graficar(op, titulo)
            self.after(0, lambda: self._viz_mostrar(fig))
            self.after(0, lambda: self._lbl_viz_ok.config(text="✅ Gráfico generado"))
        except Exception as e:
            self.after(0, lambda err=str(e): self._lbl_viz_ok.config(
                text=f"⚠ Error: {err}"))
        finally:
            self.after(0, lambda: self._btn_viz_gen.config(state="normal"))

    def _viz_obtener_datos_y_graficar(self, op, titulo):
        param = op["param"]
        fn    = op["fn"]

        if param == "resultados":
            datos = getattr(self, "_tono_resultados", {})
            if not datos:
                raise ValueError("Analiza el tono del corpus primero.")
            return fn(datos, titulo=titulo)

        elif param == "confianza":
            datos = getattr(ST, "confianza_corpus", {})
            if not datos:
                raise ValueError("No hay datos de confianza OCR. Extrae el corpus primero.")
            return fn(datos, titulo=titulo)

        elif param == "ner":
            datos = getattr(ST, "indice_ner_global", {})
            if not datos:
                raise ValueError("Ejecuta el análisis NER primero.")
            # Para frecuencia necesita categoría — usa la primera disponible
            cat = next(iter(datos.keys()), "PER")
            import inspect
            sig = inspect.signature(fn)
            if "categoria" in sig.parameters:
                return fn(datos, categoria=cat, titulo=titulo)
            return fn(datos, titulo=titulo)

        elif param == "articulos":
            datos = getattr(ST, "articulos", None) or []
            if not datos:
                raise ValueError("Segmenta los artículos del corpus primero.")
            return fn(datos, titulo=titulo)

        elif param == "corpus_txt":
            datos = getattr(ST, "corpus_txt", None) or []
            if not datos:
                raise ValueError("Extrae el texto del corpus primero.")
            return fn(datos, titulo=titulo)

        elif param == "delta":
            raise ValueError(
                "El gráfico comparativo requiere seleccionar dos números. "
                "Usa la pestaña Comparativo.")

        elif param == "resultados_por_numero":
            datos = getattr(self, "_tono_resultados", {})
            if not datos:
                raise ValueError("Analiza el tono del corpus completo primero.")
            from collections import defaultdict
            por_num = defaultdict(dict)
            for aid, res in datos.items():
                num = res.get("numero", "sin_número")
                por_num[num][aid] = res
            return fn(dict(por_num), titulo=titulo)

        raise ValueError(f"Fuente de datos desconocida: {param}")

    def _viz_mostrar(self, fig):
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except ImportError:
            messagebox.showerror("Error", "Falta matplotlib.")
            return

        # Limpiar canvas anterior
        for widget in self._frm_viz_canvas.winfo_children():
            widget.destroy()

        self._viz_fig_actual = fig
        canvas = FigureCanvasTkAgg(fig, master=self._frm_viz_canvas)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self._viz_canvas_widget = canvas

    def _viz_guardar(self):
        if self._viz_fig_actual is None:
            messagebox.showwarning("Sin gráfico", "Genera un gráfico primero.")
            return
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("SVG", "*.svg"), ("PDF", "*.pdf")],
            initialfile="grafico_bashkar.png",
            title="Guardar gráfico")
        if not dest:
            return
        self._viz_fig_actual.savefig(dest, dpi=150, bbox_inches="tight",
                                      facecolor=self._viz_fig_actual.get_facecolor())
        self.toast(f"Gráfico guardado → {Path(dest).name}", tipo="ok")

    # ── Nube de palabras ───────────────────────────────────────────────────────
    def _build_viz_nube(self, parent):
        pad = tk.Frame(parent, bg=TEMA.CONTENT_BG, padx=10, pady=8)
        pad.pack(fill="both", expand=True)

        bf = tk.Frame(pad, bg=TEMA.CONTENT_BG)
        bf.pack(fill="x", pady=(0, 8))
        self._btn_nube = ttk.Button(bf, text="▶  Generar nube",
                                     style="P.TButton",
                                     command=self._viz_nube)
        self._btn_nube.pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="🌐  Abrir imagen", style="S.TButton",
                   command=self._viz_nube_abrir).pack(side="left")
        self._lbl_nube_ok = tk.Label(pad, text="", bg=TEMA.CONTENT_BG, fg=TEMA.VERDE,
                                      font=("Segoe UI", 9, "bold"))
        self._lbl_nube_ok.pack(anchor="w", pady=(0, 6))

        # Preview de imagen
        self._lbl_nube_img = tk.Label(pad, bg=TEMA.CONTENT_BG,
                                       text="(La imagen aparecerá aquí después de generarla)",
                                       fg=TEMA.GRIS2, font=("Segoe UI", 9))
        self._lbl_nube_img.pack(fill="both", expand=True)
        self._nube_path = None

    # ── Heatmap ────────────────────────────────────────────────────────────────
    def _build_viz_heatmap(self, parent):
        pad = tk.Frame(parent, bg=TEMA.CONTENT_BG, padx=10, pady=8)
        pad.pack(fill="both", expand=True)

        tk.Label(pad, text="Términos a seguir (uno por línea):",
                 bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2, font=("Segoe UI", 9)).pack(anchor="w")
        self._txt_heat_terms = scrolledtext.ScrolledText(
            pad, height=6, font=("Consolas", 9),
            bg="#12171B", fg="#B5B6B3", wrap="word")
        self._txt_heat_terms.pack(fill="x", pady=(0, 6))
        default_terms = "colombia\nbogotá\nmedellín\nmujer\ncine\nradio\npolítica\ncultura"
        self._txt_heat_terms.insert("1.0", default_terms)

        bf = tk.Frame(pad, bg=TEMA.CONTENT_BG)
        bf.pack(fill="x", pady=(0, 6))
        self._btn_heat = ttk.Button(bf, text="▶  Generar heatmap",
                                     style="P.TButton",
                                     command=self._viz_heatmap)
        self._btn_heat.pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="🌐  Abrir imagen", style="S.TButton",
                   command=self._viz_heat_abrir).pack(side="left")
        self._lbl_heat_ok = tk.Label(pad, text="", bg=TEMA.CONTENT_BG, fg=TEMA.VERDE,
                                      font=("Segoe UI", 9, "bold"))
        self._lbl_heat_ok.pack(anchor="w")
        self._heat_path = None

    # ── Mapa ──────────────────────────────────────────────────────────────────
    def _build_viz_mapa(self, parent):
        pad = tk.Frame(parent, bg=TEMA.CONTENT_BG, padx=10, pady=8)
        pad.pack(fill="both", expand=True)

        tk.Label(pad,
                 text="Genera un mapa HTML interactivo con los lugares del índice NER.",
                 bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 8))

        bf = tk.Frame(pad, bg=TEMA.CONTENT_BG)
        bf.pack(fill="x", pady=(0, 6))
        self._btn_mapa = ttk.Button(bf, text="▶  Generar mapa",
                                     style="P.TButton",
                                     command=self._viz_mapa)
        self._btn_mapa.pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="🌐  Abrir en navegador", style="S.TButton",
                   command=self._viz_mapa_abrir).pack(side="left")
        self._lbl_mapa_ok = tk.Label(pad, text="", bg=TEMA.CONTENT_BG, fg=TEMA.VERDE,
                                      font=("Segoe UI", 9, "bold"))
        self._lbl_mapa_ok.pack(anchor="w")
        self._mapa_path = None

        tk.Label(pad,
                 text="Nota: se mapean automáticamente ciudades colombianas conocidas del período.",
                 bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2, font=("Segoe UI", 8)).pack(anchor="w", pady=(8, 0))

    # ── Timeline ──────────────────────────────────────────────────────────────
    def _build_viz_timeline(self, parent):
        pad = tk.Frame(parent, bg=TEMA.CONTENT_BG, padx=10, pady=8)
        pad.pack(fill="both", expand=True)

        tk.Label(pad,
                 text="Genera timeline HTML con personas y eventos del índice NER.",
                 bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 8))

        bf = tk.Frame(pad, bg=TEMA.CONTENT_BG)
        bf.pack(fill="x", pady=(0, 6))
        self._btn_tl = ttk.Button(bf, text="▶  Generar timeline",
                                   style="P.TButton",
                                   command=self._viz_timeline)
        self._btn_tl.pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="🌐  Abrir en navegador", style="S.TButton",
                   command=self._viz_tl_abrir).pack(side="left")
        self._lbl_tl_ok = tk.Label(pad, text="", bg=TEMA.CONTENT_BG, fg=TEMA.VERDE,
                                    font=("Segoe UI", 9, "bold"))
        self._lbl_tl_ok.pack(anchor="w")
        self._tl_path = None

    # ── Workers: Nube ─────────────────────────────────────────────────────────
    def _viz_nube(self):
        if not getattr(ST, "corpus_txt", None):
            messagebox.showwarning("Sin corpus", "Extrae el texto del corpus primero.")
            return
        self._btn_nube.config(state="disabled")
        textos = [t for t in ST.corpus_txt if t and t.strip()]
        threading.Thread(target=self._worker_nube, args=(textos,), daemon=True).start()

    def _viz_nube_mostrar_preview(self):
        if not self._nube_path or not self._nube_path.exists():
            return
        try:
            from PIL import Image, ImageTk
            img = Image.open(str(self._nube_path))
            img.thumbnail((700, 350))
            self._nube_tk = ImageTk.PhotoImage(img)
            self._lbl_nube_img.config(image=self._nube_tk, text="")
        except Exception:
            pass

    def _viz_nube_abrir(self):
        if not self._nube_path or not self._nube_path.exists():
            messagebox.showinfo("Sin imagen", "Genera la nube de palabras primero.")
            return
        plataforma.abrir_en_sistema(self._nube_path)

    # ── Workers: Heatmap ──────────────────────────────────────────────────────
    def _viz_heatmap(self):
        if not getattr(ST, "corpus_txt", None):
            messagebox.showwarning("Sin corpus", "Extrae el texto del corpus primero.")
            return
        terminos_raw = self._txt_heat_terms.get("1.0", "end").strip()
        terminos = [t.strip() for t in terminos_raw.splitlines() if t.strip()]
        if not terminos:
            messagebox.showwarning("Sin términos", "Ingresa al menos un término.")
            return
        self._btn_heat.config(state="disabled")
        threading.Thread(target=self._worker_heatmap, args=(terminos,), daemon=True).start()

    def _viz_heat_abrir(self):
        if not self._heat_path or not self._heat_path.exists():
            messagebox.showinfo("Sin imagen", "Genera el heatmap primero.")
            return
        plataforma.abrir_en_sistema(self._heat_path)

    # ── Workers: Mapa ─────────────────────────────────────────────────────────
    def _viz_mapa(self):
        if not getattr(ST, "indice_ner_global", None):
            messagebox.showwarning("Sin NER", "Analiza el corpus en la pestaña Índice NER primero.")
            return
        self._btn_mapa.config(state="disabled")
        threading.Thread(target=self._worker_mapa, daemon=True).start()

    def _viz_mapa_abrir(self):
        if not self._mapa_path or not self._mapa_path.exists():
            messagebox.showinfo("Sin mapa", "Genera el mapa primero.")
            return
        import webbrowser
        webbrowser.open(str(self._mapa_path))

    # ── Workers: Timeline ─────────────────────────────────────────────────────
    def _viz_timeline(self):
        if not getattr(ST, "indice_ner_global", None):
            messagebox.showwarning("Sin NER", "Analiza el corpus en la pestaña Índice NER primero.")
            return
        self._btn_tl.config(state="disabled")
        threading.Thread(target=self._worker_timeline, daemon=True).start()

    def _viz_tl_abrir(self):
        if not self._tl_path or not self._tl_path.exists():
            messagebox.showinfo("Sin timeline", "Genera la timeline primero.")
            return
        import webbrowser
        webbrowser.open(str(self._tl_path))

    def _build_dash(self):
        pad = tk.Frame(self._tab_dash, bg=TEMA.CONTENT_BG, padx=16, pady=12)
        pad.pack(fill="both", expand=True)
        tk.Label(pad, text="Dashboard ejecutivo", bg=TEMA.CONTENT_BG,
                 fg="#E8E5DF", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(pad, text="Resumen del estado del proyecto y exportación del paquete completo.",
                 bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 10))

        # ── Grid de indicadores ───────────────────────────────────────────────
        grid = tk.Frame(pad, bg=TEMA.CONTENT_BG)
        grid.pack(fill="x", pady=(0, 12))
        self._dash_cards = {}
        indicadores = [
            ("pdfs",      "PDFs cargados",    "0"),
            ("paginas",   "Páginas OCR",      "0"),
            ("articulos", "Artículos",         "0"),
            ("palabras",  "Palabras",          "0"),
            ("entidades", "Entidades NER",     "0"),
            ("red_nodos", "Nodos en red",      "0"),
        ]
        for col, (key, lbl, val) in enumerate(indicadores):
            frm = tk.Frame(grid, bg="#1C2227", padx=12, pady=8, relief="flat", bd=0)
            frm.grid(row=0, column=col, padx=4, pady=2, sticky="nsew")
            grid.columnconfigure(col, weight=1)
            lbl_num = tk.Label(frm, text=val, bg="#1C2227", fg="#B18AD6",
                                font=("Segoe UI", 20, "bold"))
            lbl_num.pack()
            tk.Label(frm, text=lbl, bg="#1C2227", fg="#B5B6B3",
                     font=("Segoe UI", 8)).pack()
            self._dash_cards[key] = lbl_num

        # ── Progreso por módulo ───────────────────────────────────────────────
        prog_frame = tk.LabelFrame(pad, text=" Estado del análisis ",
                                    bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2, font=("Segoe UI", 9))
        prog_frame.pack(fill="x", pady=(0, 10))
        self._dash_prog_labels = {}
        modulos = [
            ("ocr",  "OCR / Extracción",    "ocr_done"),
            ("seg",  "Segmentación",         "seg_done"),
            ("ner",  "Índice NER",           "ner_done"),
            ("red",  "Redes",                None),
            ("sem",  "Semántico",            None),
            ("rep",  "Reporte",              None),
        ]
        for i, (mid, mlabel, badge) in enumerate(modulos):
            row = i // 3
            col = i % 3
            frm = tk.Frame(prog_frame, bg=TEMA.CONTENT_BG)
            frm.grid(row=row, column=col, padx=8, pady=4, sticky="w")
            lbl = tk.Label(frm, text=f"◦ {mlabel}", bg=TEMA.CONTENT_BG,
                           fg=TEMA.GRIS2, font=("Segoe UI", 9))
            lbl.pack(side="left")
            self._dash_prog_labels[mid] = (lbl, badge)

        # ── Botón actualizar ──────────────────────────────────────────────────
        bf = tk.Frame(pad, bg=TEMA.CONTENT_BG)
        bf.pack(fill="x", pady=(0, 8))
        ttk.Button(bf, text="↻  Actualizar dashboard",
                   style="S.TButton",
                   command=self._dash_actualizar).pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="▶  Generar reporte completo",
                   style="P.TButton",
                   command=self._dash_reporte_completo).pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="🚀  Paquete completo (pipeline maestro)",
                   style="P.TButton",
                   command=self._dash_pipeline_maestro).pack(side="left", padx=(0, 8))
        self._btn_dash_zip = ttk.Button(bf, text="📦  Exportar ZIP",
                                         style="S.TButton",
                                         command=self._dash_exportar_zip)
        self._btn_dash_zip.pack(side="right")
        self._lbl_dash_ok = tk.Label(pad, text="", bg=TEMA.CONTENT_BG, fg=TEMA.VERDE,
                                      font=("Segoe UI", 9, "bold"))
        self._lbl_dash_ok.pack(anchor="w", pady=(0, 6))

        # ── Log ───────────────────────────────────────────────────────────────
        self._txt_dash_log = scrolledtext.ScrolledText(
            pad, height=7, font=("Consolas", 8),
            bg="#12171B", fg="#B5B6B3", state="disabled", wrap="word")
        self._txt_dash_log.pack(fill="x")

        # Actualizar al abrir
        self.after(500, self._dash_actualizar)

    def _dash_log(self, msg: str):
        self._txt_dash_log.config(state="normal")
        self._txt_dash_log.insert("end", msg + "\n")
        self._txt_dash_log.see("end")
        self._txt_dash_log.config(state="disabled")

    def _dash_actualizar(self):
        # Indicadores numéricos
        def set_card(key, val):
            if key in self._dash_cards:
                self._dash_cards[key].config(text=str(val))

        set_card("pdfs",      len(getattr(ST, "pdf_files", []) or []))
        _cm = getattr(ST, "corpus_meta", None)
        set_card("paginas",   len(_cm) if _cm is not None else 0)
        set_card("articulos", len(getattr(ST, "articulos", []) or []))
        n_words = sum(len((t or "").split()) for t in (getattr(ST, "corpus_txt", []) or []))
        set_card("palabras",  f"{n_words:,}")
        ner = getattr(ST, "indice_ner_global", {}) or {}
        set_card("entidades", sum(len(v) for v in ner.values()))
        grafo = getattr(self, "_grafo_actual", None)
        set_card("red_nodos", grafo.number_of_nodes() if grafo else 0)

        # Estado módulos
        for mid, (lbl, badge) in self._dash_prog_labels.items():
            if badge:
                done = getattr(ST, badge, False)
            else:
                # Inferir por existencia de datos
                if mid == "red":
                    done = getattr(self, "_grafo_actual", None) is not None
                elif mid == "sem":
                    done = bool(getattr(self, "_tono_resultados", {}))
                elif mid == "rep":
                    done = bool(getattr(self, "_narrativas_data", {}))
                else:
                    done = False
            color = TEMA.VERDE if done else TEMA.GRIS2
            ico = "✅" if done else "◦"
            lbl.config(text=f"{ico} {mid.upper()}", fg=color)

        self._lbl_dash_ok.config(text="Dashboard actualizado")

    def _dash_reporte_completo(self):
        self._dash_log("Iniciando generación de reporte completo…")
        self._dash_log("  1/3 Narrativas IA…")
        self._rep_generar_narrativas()
        self.after(3000, lambda: (
            self._dash_log("  2/3 Reporte HTML…"),
            self._rep_generar_html(),
        ))
        self.after(6000, lambda: (
            self._dash_log("  3/3 Dashboard actualizado"),
            self._dash_actualizar(),
            self._lbl_dash_ok.config(text="✅ Reporte completo generado"),
        ))

    def _dash_exportar_zip(self):
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP", "*.zip"), ("Todos", "*.*")],
            initialfile="bashkar_export.zip",
            title="Exportar paquete ZIP")
        if not dest:
            return
        self._btn_dash_zip.config(state="disabled")
        self._lbl_dash_ok.config(text="Empaquetando…")
        threading.Thread(target=self._worker_zip, args=(dest,), daemon=True).start()

    def _build_top(self):
        outer = tk.Frame(self._tab_top, bg=TEMA.CONTENT_BG)
        outer.pack(fill="both", expand=True, padx=16, pady=12)

        self._top_params: dict = {}
        try:
            from core.topic_engine import PARAMS_SCHEMA as _TOP_SCHEMA
            self._build_params_panel(outer, _TOP_SCHEMA, self._top_params)
        except Exception:
            pass

        pad = tk.Frame(outer, bg=TEMA.CONTENT_BG)
        pad.pack(side="left", fill="both", expand=True)

        tk.Label(pad, text="Topic modeling del corpus", bg=TEMA.CONTENT_BG,
                 fg="#E8E5DF", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(pad, text="Detecta temas recurrentes y su distribución en el corpus.",
                 bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 10))

        # Controles
        cf = tk.Frame(pad, bg=TEMA.CONTENT_BG)
        cf.pack(fill="x", pady=(0, 6))
        tk.Label(cf, text="N° tópicos:", bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self._var_top_n = tk.IntVar(value=8)
        ttk.Spinbox(cf, from_=3, to=20, textvariable=self._var_top_n,
                    width=4).pack(side="left", padx=(0, 12))
        self._var_top_llm = tk.BooleanVar(value=True)
        ttk.Checkbutton(cf, text="Etiquetar con IA (Claude)",
                        variable=self._var_top_llm).pack(side="left", padx=(0, 12))
        self._var_top_bertopic = tk.BooleanVar(value=False)
        ttk.Checkbutton(cf, text="BERTopic (requiere GPU/modelos)",
                        variable=self._var_top_bertopic).pack(side="left")

        # Botones
        bf = tk.Frame(pad, bg=TEMA.CONTENT_BG)
        bf.pack(fill="x", pady=(0, 6))
        self._btn_top = ttk.Button(bf, text="▶  Modelar tópicos",
                                    style="P.TButton",
                                    command=self._top_ejecutar)
        self._btn_top.pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="💾  Exportar CSV", style="S.TButton",
                   command=self._top_exportar).pack(side="left", padx=(0, 8))
        self._lbl_top_ok = tk.Label(pad, text="", bg=TEMA.CONTENT_BG, fg=TEMA.VERDE,
                                     font=("Segoe UI", 9, "bold"))
        self._lbl_top_ok.pack(anchor="w", pady=(0, 4))

        # Tabla de tópicos
        tk.Label(pad, text="Tópicos detectados", bg=TEMA.CONTENT_BG, fg=TEMA.GRIS2,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(4, 2))
        cols_top = ("id", "nombre", "n_docs", "porcentaje", "palabras_clave")
        self._tv_top = ttk.Treeview(pad, columns=cols_top, show="headings", height=10)
        heads_top = [("id", "#", 40), ("nombre", "Nombre/Tema", 160),
                     ("n_docs", "Artículos", 70), ("porcentaje", "%", 60),
                     ("palabras_clave", "Palabras clave", 380)]
        for cid, txt, w in heads_top:
            self._tv_top.heading(cid, text=txt)
            self._tv_top.column(cid, width=w, anchor="w")
        sv = ttk.Scrollbar(pad, orient="vertical", command=self._tv_top.yview)
        self._tv_top.configure(yscrollcommand=sv.set)
        self._tv_top.pack(side="left", fill="both", expand=True)
        sv.pack(side="left", fill="y")

        self._top_resultado = {}

    def _top_ejecutar(self):
        if not getattr(ST, "corpus_txt", None):
            messagebox.showwarning("Sin corpus", "Extrae el texto del corpus primero.")
            return
        # Leer params del panel lateral (prioridad sobre spinboxes legacy)
        p = self._params_get_values(self._top_params) if getattr(self, "_top_params", None) else {}
        n             = int(p.get("n_topics",          self._var_top_n.get()))
        usar_llm      = bool(p.get("etiquetar_ia",     self._var_top_llm.get()))
        usar_bertopic = p.get("backend", "nmf") == "bertopic"
        min_df        = int(p.get("min_df", 2))
        max_df        = float(p.get("max_df", 0.95))
        n_words       = int(p.get("palabras_por_topic", 10))
        if usar_llm and not ST.api_key:
            messagebox.showwarning("Sin API key", "Configura tu clave Claude API o desactiva 'Etiquetar con IA'.")
            return
        self._btn_top.config(state="disabled")
        self._lbl_top_ok.config(text="Modelando tópicos…")
        textos = [t for t in ST.corpus_txt if t and t.strip()]
        threading.Thread(target=self._worker_top,
                         args=(textos, n, usar_llm, usar_bertopic, min_df, max_df, n_words),
                         daemon=True).start()

    def _worker_top(self, textos, n, usar_llm, usar_bertopic,
                    min_df=2, max_df=0.95, n_words=10):
        from core.topic_engine import estadisticas_topicos, modelar_topicos
        def cb(m):
            self.after(0, lambda msg=m: self._lbl_top_ok.config(text=str(msg)[:80]))
        try:
            resultado = modelar_topicos(
                textos, n_topicos=n,
                api_key=ST.api_key if usar_llm else None,
                usar_bertopic=usar_bertopic,
                min_df=min_df, max_df=max_df,
                n_palabras=n_words,
                callback=cb,
            )
            self._top_resultado = resultado
            stats = estadisticas_topicos(resultado)
            self.after(0, lambda s=stats: self._top_refrescar(s))
            backend = resultado.get("backend", "?")
            n_top = len(resultado.get("topicos", {}))
            self.after(0, lambda: self._lbl_top_ok.config(
                text=f"✅ {n_top} tópicos detectados ({backend})"))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._lbl_top_ok.config(text=f"⚠ Error: {err}"))
        self.after(0, lambda: self._btn_top.config(state="normal"))

    def _top_refrescar(self, stats):
        for row in self._tv_top.get_children():
            self._tv_top.delete(row)
        for tid, info in sorted(stats.get("topicos", {}).items(), key=lambda x: -x[1].get("n_docs", 0)):
            self._tv_top.insert("", "end", values=(
                tid,
                info.get("nombre", f"Tópico {tid}"),
                info.get("n_docs", 0),
                f"{info.get('porcentaje', 0)}%",
                ", ".join(info.get("palabras_clave", [])[:6]),
            ))

    def _top_exportar(self):
        if not self._top_resultado:
            messagebox.showwarning("Sin datos", "Ejecuta el topic modeling primero.")
            return
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="topicos_corpus.csv",
            title="Exportar tópicos")
        if not dest:
            return
        from pathlib import Path as _PPath

        from core.topic_engine import exportar_topicos_csv
        n = exportar_topicos_csv(self._top_resultado, _PPath(dest))
        messagebox.showinfo("Exportado", f"✅ {n} entradas exportadas a:\n{dest}")

    def _dash_pipeline_maestro(self):
        """Lanza el PipelineMaestro completo desde el Dashboard."""
        if not ST.api_key:
            messagebox.showwarning("Sin API key", "Configura tu clave Claude API en Configuración.")
            return
        if not self._proyecto_ruta:
            messagebox.showwarning("Sin proyecto",
                "Guarda el proyecto primero (Archivo > Guardar proyecto).")
            return
        if not messagebox.askyesno("Generar paquete completo",
            "Esto ejecutará todo el análisis y generará el paquete ZIP de investigación.\n"
            "Puede tardar varios minutos según el tamaño del corpus.\n\n"
            "¿Continuar?"):
            return

        self._lbl_dash_ok.config(text="🚀 Pipeline Maestro iniciado…")
        self._dash_log("=== PIPELINE MAESTRO INICIADO ===")
        self._dash_log(f"Proyecto: {self._proyecto_ruta}")

        articulos = self._pipeline_maestro_articulos()

        from core.pipeline_maestro import PipelineMaestro
        pm = PipelineMaestro(
            bashkar_path=str(self._proyecto_ruta),
            api_key=ST.api_key,
            callback_progreso=lambda p, m: self.after(0, lambda pct=p, msg=m: (
                self._lbl_dash_ok.config(text=f"[{pct}%] {msg}"),
                self._dash_log(f"[{pct}%] {msg}"),
            )),
            callback_log=lambda m: self.after(0, lambda msg=m: self._dash_log(msg)),
            repositorio=ST.repo,
        )
        pm.ejecutar_en_hilo(articulos_existentes=articulos if articulos else None)
