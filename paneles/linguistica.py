"""paneles/linguistica.py — Métodos de BashkarApp extraídos de app.py.

Mixin: BashkarApp hereda de PanelLinguistica. Los cuerpos son copia literal del
original; los nombres globales (ST, colores, tk…) los inyecta
paneles.sincronizar() desde app.py.
"""

from __future__ import annotations

# ruff: noqa: F821


class PanelLinguistica:
    def _build_ling(self):
        pad = tk.Frame(self._frames_pagina["ling"], bg=CONTENT_BG, padx=16, pady=12)
        pad.pack(fill="both", expand=True)
        tk.Label(pad, text="Lingüística Computacional", bg=CONTENT_BG,
                 fg="#E8E5DF", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(pad,
                 text="Sintaxis, correferencia, morfología histórica, emociones, encuadre, "
                      "polaridad, revisión NER y validación metodológica (Kappa).",
                 bg=CONTENT_BG, fg=GRIS2, font=("Segoe UI", 9),
                 wraplength=760, justify="left").pack(anchor="w", pady=(0, 10))

        nb_ling = ttk.Notebook(pad)
        nb_ling.pack(fill="both", expand=True)
        self._nb_ling = nb_ling

        # ── Pestaña 1: Análisis sintáctico ────────────────────────────────────
        frm_sint = tk.Frame(nb_ling, bg=CONTENT_BG)
        nb_ling.add(frm_sint, text="  🌲 Sintaxis  ")

        ctrl_sint = tk.Frame(frm_sint, bg=CONTENT_BG)
        ctrl_sint.pack(fill="x", padx=8, pady=(8, 4))
        tk.Label(ctrl_sint, text="Patrón sintáctico:", bg=CONTENT_BG, fg=GRIS2,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self._var_ling_patron = tk.StringVar(value="verbo_sujeto")
        _patrones = [
            ("verbo_sujeto",  "Verbo + sujeto"),
            ("verbo_objeto",  "Verbo + objeto"),
            ("sustantivo_adj","Sust. + adjetivo"),
            ("entidad_verbo", "Entidad como sujeto"),
            ("negacion",      "Negaciones"),
        ]
        for val, lbl in _patrones:
            ttk.Radiobutton(ctrl_sint, text=lbl, variable=self._var_ling_patron,
                            value=val).pack(side="left", padx=3)

        tk.Label(ctrl_sint, text="  Máx. resultados:", bg=CONTENT_BG, fg=GRIS2,
                 font=("Segoe UI", 9)).pack(side="left", padx=(12, 4))
        self._var_ling_max = tk.IntVar(value=200)
        ttk.Spinbox(ctrl_sint, from_=50, to=1000, textvariable=self._var_ling_max,
                    width=6).pack(side="left")

        bf_sint = tk.Frame(frm_sint, bg=CONTENT_BG)
        bf_sint.pack(fill="x", padx=8, pady=(0, 6))
        self._btn_ling_sint = ttk.Button(bf_sint, text="▶  Analizar concordancias sintácticas",
                                          style="P.TButton",
                                          command=self._ling_concordancias)
        self._btn_ling_sint.pack(side="left", padx=(0, 8))
        ttk.Button(bf_sint, text="💾  Exportar CSV", style="S.TButton",
                   command=self._ling_sint_csv).pack(side="left", padx=(0, 8))
        ttk.Button(bf_sint, text="🔗  Relaciones SVO", style="S.TButton",
                   command=self._ling_relaciones).pack(side="left", padx=(0, 8))
        self._lbl_ling_sint = tk.Label(frm_sint, text="", bg=CONTENT_BG,
                                        fg=VERDE, font=("Segoe UI", 9, "bold"))
        self._lbl_ling_sint.pack(anchor="w", padx=8)

        cols_sint = ("patron", "principal", "secundario", "descripcion", "fragmento")
        self._tv_ling_sint = ttk.Treeview(frm_sint, columns=cols_sint,
                                           show="headings", height=16)
        for cid, txt, w in [("patron","Patrón",110),("principal","Elem. 1",140),
                              ("secundario","Elem. 2",140),
                              ("descripcion","Descripción",200),
                              ("fragmento","Fragmento",340)]:
            self._tv_ling_sint.heading(cid, text=txt)
            self._tv_ling_sint.column(cid, width=w, anchor="w")
        sv_s = ttk.Scrollbar(frm_sint, orient="vertical",
                              command=self._tv_ling_sint.yview)
        self._tv_ling_sint.configure(yscrollcommand=sv_s.set)
        sv_s.pack(side="right", fill="y", padx=(0, 6))
        self._tv_ling_sint.pack(fill="both", expand=True, padx=6, pady=(0, 4))
        self._ling_sint_resultados: list = []

        # ── Pestaña 2: Relaciones SVO ─────────────────────────────────────────
        frm_svo = tk.Frame(nb_ling, bg=CONTENT_BG)
        nb_ling.add(frm_svo, text="  🔗 Relaciones SVO  ")

        ctrl_svo = tk.Frame(frm_svo, bg=CONTENT_BG)
        ctrl_svo.pack(fill="x", padx=8, pady=(8, 4))
        self._var_ling_solo_ent = tk.BooleanVar(value=True)
        ttk.Checkbutton(ctrl_svo, text="Solo entidades nombradas como sujeto/objeto",
                        variable=self._var_ling_solo_ent).pack(side="left")
        tk.Label(ctrl_svo, text="  Confianza mínima:", bg=CONTENT_BG, fg=GRIS2,
                 font=("Segoe UI", 9)).pack(side="left", padx=(12, 4))
        self._var_ling_conf = tk.DoubleVar(value=0.5)
        ttk.Spinbox(ctrl_svo, from_=0.1, to=1.0, increment=0.1,
                    textvariable=self._var_ling_conf, width=5,
                    format="%.1f").pack(side="left")

        bf_svo = tk.Frame(frm_svo, bg=CONTENT_BG)
        bf_svo.pack(fill="x", padx=8, pady=(0, 6))
        self._btn_ling_svo = ttk.Button(bf_svo, text="▶  Extraer relaciones",
                                         style="P.TButton",
                                         command=self._ling_relaciones)
        self._btn_ling_svo.pack(side="left", padx=(0, 8))
        ttk.Button(bf_svo, text="💾  Exportar CSV", style="S.TButton",
                   command=self._ling_svo_csv).pack(side="left", padx=(0, 8))
        ttk.Button(bf_svo, text="📊  Agrupar por verbo", style="S.TButton",
                   command=self._ling_svo_agrupar).pack(side="left", padx=(0, 8))
        self._lbl_ling_svo = tk.Label(frm_svo, text="", bg=CONTENT_BG,
                                       fg=VERDE, font=("Segoe UI", 9, "bold"))
        self._lbl_ling_svo.pack(anchor="w", padx=8)

        cols_svo = ("sujeto", "suj_tipo", "relacion", "objeto", "obj_tipo",
                    "confianza", "oracion")
        self._tv_ling_svo = ttk.Treeview(frm_svo, columns=cols_svo,
                                          show="headings", height=16)
        for cid, txt, w in [("sujeto","Sujeto",150),("suj_tipo","Tipo S",80),
                              ("relacion","Relación",110),("objeto","Objeto",150),
                              ("obj_tipo","Tipo O",80),("confianza","Conf.",60),
                              ("oracion","Oración",320)]:
            self._tv_ling_svo.heading(cid, text=txt)
            self._tv_ling_svo.column(cid, width=w, anchor="w")
        sv_svo = ttk.Scrollbar(frm_svo, orient="vertical",
                                command=self._tv_ling_svo.yview)
        self._tv_ling_svo.configure(yscrollcommand=sv_svo.set)
        sv_svo.pack(side="right", fill="y", padx=(0, 6))
        self._tv_ling_svo.pack(fill="both", expand=True, padx=6, pady=(0, 4))
        self._ling_svo_resultados: list = []

        # ── Pestaña 3: Correferencia ──────────────────────────────────────────
        frm_coref = tk.Frame(nb_ling, bg=CONTENT_BG)
        nb_ling.add(frm_coref, text="  🔁 Correferencia  ")

        ctrl_coref = tk.Frame(frm_coref, bg=CONTENT_BG)
        ctrl_coref.pack(fill="x", padx=8, pady=(8, 4))
        tk.Label(ctrl_coref, text="Entidad a rastrear (vacío = todas):",
                 bg=CONTENT_BG, fg=GRIS2, font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self._ent_coref = ttk.Entry(ctrl_coref, width=24)
        self._ent_coref.pack(side="left", padx=(0, 12))

        bf_coref = tk.Frame(frm_coref, bg=CONTENT_BG)
        bf_coref.pack(fill="x", padx=8, pady=(0, 6))
        self._btn_ling_coref = ttk.Button(bf_coref, text="▶  Resolver correferencias",
                                           style="P.TButton",
                                           command=self._ling_coref)
        self._btn_ling_coref.pack(side="left", padx=(0, 8))
        ttk.Button(bf_coref, text="📊  Estadísticas corpus", style="S.TButton",
                   command=self._ling_coref_stats).pack(side="left", padx=(0, 8))
        self._lbl_ling_coref = tk.Label(frm_coref, text="", bg=CONTENT_BG,
                                         fg=VERDE, font=("Segoe UI", 9, "bold"))
        self._lbl_ling_coref.pack(anchor="w", padx=8)

        # Split: lista de cadenas izquierda, menciones derecha
        split_coref = tk.Frame(frm_coref, bg=CONTENT_BG)
        split_coref.pack(fill="both", expand=True, padx=6)

        izq_coref = tk.Frame(split_coref, bg=CONTENT_BG, width=220)
        izq_coref.pack(side="left", fill="y", padx=(0, 6))
        izq_coref.pack_propagate(False)
        tk.Label(izq_coref, text="Cadenas referenciales", bg=CONTENT_BG,
                 fg=GRIS2, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self._lb_coref = tk.Listbox(
            izq_coref, bg=CARD_BG, fg=TXT_SEC, selectbackground=AB_SEL,
            font=("Segoe UI", 9), relief="flat", activestyle="none")
        self._lb_coref.pack(fill="both", expand=True)
        self._lb_coref.bind("<<ListboxSelect>>", self._ling_coref_mostrar_cadena)

        der_coref = tk.Frame(split_coref, bg=CONTENT_BG)
        der_coref.pack(side="left", fill="both", expand=True)
        tk.Label(der_coref, text="Menciones", bg=CONTENT_BG,
                 fg=GRIS2, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        cols_coref = ("texto", "tipo", "oracion")
        self._tv_coref_men = ttk.Treeview(der_coref, columns=cols_coref,
                                           show="headings", height=18)
        for cid, txt, w in [("texto","Mención",160),("tipo","Tipo",100),
                              ("oracion","Contexto",440)]:
            self._tv_coref_men.heading(cid, text=txt)
            self._tv_coref_men.column(cid, width=w, anchor="w")
        sv_c = ttk.Scrollbar(der_coref, orient="vertical",
                              command=self._tv_coref_men.yview)
        self._tv_coref_men.configure(yscrollcommand=sv_c.set)
        sv_c.pack(side="right", fill="y")
        self._tv_coref_men.pack(fill="both", expand=True)
        self._ling_coref_cadenas: list = []

        # ── Pestaña 4: Morfología histórica ──────────────────────────────────
        frm_morf = tk.Frame(nb_ling, bg=CONTENT_BG)
        nb_ling.add(frm_morf, text="  📜 Morfología histórica  ")

        bf_morf = tk.Frame(frm_morf, bg=CONTENT_BG)
        bf_morf.pack(fill="x", padx=8, pady=(8, 4))
        self._btn_ling_morf = ttk.Button(bf_morf, text="▶  Analizar corpus",
                                          style="P.TButton",
                                          command=self._ling_morf_analizar)
        self._btn_ling_morf.pack(side="left", padx=(0, 8))
        ttk.Button(bf_morf, text="📖  Ver glosario", style="S.TButton",
                   command=self._ling_morf_glosario).pack(side="left", padx=(0, 8))
        ttk.Button(bf_morf, text="🔍  Ver detalle", style="S.TButton",
                   command=self._ling_morf_detalle).pack(side="left", padx=(0, 8))
        ttk.Button(bf_morf, text="💾  Exportar CSV", style="S.TButton",
                   command=self._ling_morf_csv).pack(side="left", padx=(0, 8))
        self._var_morf_normalizar = tk.BooleanVar(value=True)
        ttk.Checkbutton(bf_morf, text="Normalizar grafías históricas antes de analizar",
                        variable=self._var_morf_normalizar).pack(side="left", padx=(8, 0))
        self._lbl_ling_morf = tk.Label(frm_morf, text="", bg=CONTENT_BG,
                                        fg=VERDE, font=("Segoe UI", 9, "bold"))
        self._lbl_ling_morf.pack(anchor="w", padx=8)

        # Resumen del corpus
        frm_morf_stats = tk.Frame(frm_morf, bg=CONTENT_BG)
        frm_morf_stats.pack(fill="x", padx=8, pady=(0, 4))
        self._lbl_morf_resumen = tk.Label(frm_morf_stats,
                                           text="Analiza el corpus para ver la densidad de formas históricas.",
                                           bg=CONTENT_BG, fg=GRIS2, font=("Segoe UI", 9))
        self._lbl_morf_resumen.pack(anchor="w")

        cols_morf = ("doc", "tokens", "arcaismos", "score", "marcadores", "top_formas")
        self._tv_ling_morf = ttk.Treeview(frm_morf, columns=cols_morf,
                                           show="headings", height=16)
        for cid, txt, w in [("doc","Doc.",50),("tokens","Tokens",70),
                              ("arcaismos","Arcaísmos",80),("score","Score hist.",80),
                              ("marcadores","Marcadores",200),
                              ("top_formas","Formas top",320)]:
            self._tv_ling_morf.heading(cid, text=txt)
            self._tv_ling_morf.column(cid, width=w, anchor="w" if w > 100 else "center")
        # Color por densidad
        self._tv_ling_morf.tag_configure("alta",  background="#15251F", foreground="#62C6B5")
        self._tv_ling_morf.tag_configure("media", background="#2A2116", foreground="#E6A64C")
        self._tv_ling_morf.tag_configure("baja",  background=CONTENT_BG, foreground=TXT_PRI)
        sv_m = ttk.Scrollbar(frm_morf, orient="vertical",
                              command=self._tv_ling_morf.yview)
        self._tv_ling_morf.configure(yscrollcommand=sv_m.set)
        sv_m.pack(side="right", fill="y", padx=(0, 6))
        self._tv_ling_morf.pack(fill="both", expand=True, padx=6, pady=(0, 4))
        self._ling_morf_datos: list = []

        # ── Pestaña 5: Árbol de dependencias ─────────────────────────────────
        frm_dep = tk.Frame(nb_ling, bg=CONTENT_BG)
        nb_ling.add(frm_dep, text="  🌳 Árbol dep.  ")

        bf_dep = tk.Frame(frm_dep, bg=CONTENT_BG)
        bf_dep.pack(fill="x", padx=8, pady=(8, 4))
        self._btn_ling_dep = ttk.Button(bf_dep, text="▶  Analizar oración",
                                         style="P.TButton",
                                         command=self._ling_dep_analizar)
        self._btn_ling_dep.pack(side="left", padx=(0, 8))
        ttk.Button(bf_dep, text="💾  Exportar CSV", style="S.TButton",
                   command=self._ling_dep_csv).pack(side="left", padx=(0, 8))
        tk.Label(bf_dep, text="Máx. oraciones:", bg=CONTENT_BG,
                 fg=TXT_SEC, font=("Segoe UI", 9)).pack(side="left", padx=(12, 4))
        self._var_dep_max = tk.IntVar(value=20)
        ttk.Spinbox(bf_dep, from_=1, to=100, textvariable=self._var_dep_max,
                    width=5).pack(side="left")
        self._lbl_ling_dep = tk.Label(frm_dep, text="", bg=CONTENT_BG,
                                       fg=VERDE, font=("Segoe UI", 9, "bold"))
        self._lbl_ling_dep.pack(anchor="w", padx=8)

        # Selector de artículo
        sel_dep = tk.Frame(frm_dep, bg=CONTENT_BG)
        sel_dep.pack(fill="x", padx=8, pady=(0, 4))
        tk.Label(sel_dep, text="Artículo:", bg=CONTENT_BG, fg=TXT_SEC,
                 font=("Segoe UI", 9)).pack(side="left")
        self._var_dep_art = tk.IntVar(value=0)
        self._spn_dep_art = ttk.Spinbox(sel_dep, from_=0, to=9999,
                                         textvariable=self._var_dep_art, width=6)
        self._spn_dep_art.pack(side="left", padx=4)
        tk.Label(sel_dep, text="(índice en corpus)", bg=CONTENT_BG, fg=TXT_DIM,
                 font=("Segoe UI", 8)).pack(side="left")

        # Panel split: lista oraciones | detalle tokens
        split_dep = tk.Frame(frm_dep, bg=CONTENT_BG)
        split_dep.pack(fill="both", expand=True, padx=6)

        izq_dep = tk.Frame(split_dep, bg=CONTENT_BG)
        izq_dep.pack(side="left", fill="both", expand=False)
        tk.Label(izq_dep, text="Oraciones", bg=CONTENT_BG,
                 fg=GRIS2, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self._lb_dep = tk.Listbox(izq_dep, bg=CARD_BG, fg=TXT_PRI,
                                   selectbackground=AZ3, font=("Segoe UI", 9),
                                   width=42, height=18, relief="flat")
        sv_dep_lb = ttk.Scrollbar(izq_dep, orient="vertical",
                                   command=self._lb_dep.yview)
        self._lb_dep.configure(yscrollcommand=sv_dep_lb.set)
        sv_dep_lb.pack(side="right", fill="y")
        self._lb_dep.pack(fill="y", expand=True)
        self._lb_dep.bind("<<ListboxSelect>>", self._ling_dep_mostrar_tokens)

        der_dep = tk.Frame(split_dep, bg=CONTENT_BG)
        der_dep.pack(side="left", fill="both", expand=True, padx=(8, 0))
        tk.Label(der_dep, text="Tokens y dependencias", bg=CONTENT_BG,
                 fg=GRIS2, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        cols_dep = ("texto", "lemma", "pos", "dep_es", "cabeza")
        self._tv_dep_tok = ttk.Treeview(der_dep, columns=cols_dep,
                                         show="headings", height=18)
        for cid, txt, w in [("texto","Token",100),("lemma","Lema",100),
                              ("pos","POS",60),("dep_es","Relación",140),
                              ("cabeza","Cabeza",100)]:
            self._tv_dep_tok.heading(cid, text=txt)
            self._tv_dep_tok.column(cid, width=w, anchor="w")
        # Tags POS
        self._tv_dep_tok.tag_configure("VERB", foreground="#62C6B5")
        self._tv_dep_tok.tag_configure("NOUN", foreground="#6CA8E8")
        self._tv_dep_tok.tag_configure("PROPN", foreground="#D58B45")
        sv_dep_tok = ttk.Scrollbar(der_dep, orient="vertical",
                                    command=self._tv_dep_tok.yview)
        self._tv_dep_tok.configure(yscrollcommand=sv_dep_tok.set)
        sv_dep_tok.pack(side="right", fill="y")
        self._tv_dep_tok.pack(fill="both", expand=True)
        self._ling_dep_datos: list = []

        # ── Pestaña 6: Emociones y subjetividad ──────────────────────────────
        frm_emo = tk.Frame(nb_ling, bg=CONTENT_BG)
        nb_ling.add(frm_emo, text="  💭 Emociones  ")

        bf_emo = tk.Frame(frm_emo, bg=CONTENT_BG)
        bf_emo.pack(fill="x", padx=8, pady=(8, 4))
        self._btn_ling_emo = ttk.Button(bf_emo, text="▶  Analizar emociones",
                                         style="P.TButton",
                                         command=self._ling_emociones)
        self._btn_ling_emo.pack(side="left", padx=(0, 8))
        ttk.Button(bf_emo, text="📊  Graficar distribución", style="S.TButton",
                   command=self._ling_emo_graficar).pack(side="left", padx=(0, 8))
        ttk.Button(bf_emo, text="💾  Exportar CSV", style="S.TButton",
                   command=self._ling_emo_csv).pack(side="left", padx=(0, 8))
        self._lbl_ling_emo = tk.Label(frm_emo, text="", bg=CONTENT_BG,
                                       fg=VERDE, font=("Segoe UI", 9, "bold"))
        self._lbl_ling_emo.pack(anchor="w", padx=8)

        # Resumen global
        frm_emo_resumen = tk.Frame(frm_emo, bg=CONTENT_BG)
        frm_emo_resumen.pack(fill="x", padx=8, pady=(0, 4))
        self._lbl_emo_resumen = tk.Label(frm_emo_resumen, text="",
                                          bg=CONTENT_BG, fg=TXT_SEC,
                                          font=("Segoe UI", 9), wraplength=700,
                                          justify="left")
        self._lbl_emo_resumen.pack(anchor="w")

        cols_emo = ("art_id", "emocion_dom", "subjetividad", "tipo_discurso",
                    "intensidad", "palabras_emo")
        self._tv_ling_emo = ttk.Treeview(frm_emo, columns=cols_emo,
                                          show="headings", height=15)
        for cid, txt, w in [("art_id","Artículo",90),
                              ("emocion_dom","Emoción dom.",110),
                              ("subjetividad","Subjetividad",95),
                              ("tipo_discurso","Tipo discurso",110),
                              ("intensidad","Intensidad",90),
                              ("palabras_emo","Palabras emocionales",340)]:
            self._tv_ling_emo.heading(cid, text=txt)
            self._tv_ling_emo.column(cid, width=w, anchor="w")
        sv_e = ttk.Scrollbar(frm_emo, orient="vertical",
                              command=self._tv_ling_emo.yview)
        self._tv_ling_emo.configure(yscrollcommand=sv_e.set)
        sv_e.pack(side="right", fill="y", padx=(0, 6))
        self._tv_ling_emo.pack(fill="both", expand=True, padx=6, pady=(0, 4))
        self._ling_emo_datos: list = []

        # ── Pestaña 7: Encuadre (framing) ─────────────────────────────────────
        frm_frame = tk.Frame(nb_ling, bg=CONTENT_BG)
        nb_ling.add(frm_frame, text="  🖼 Encuadre  ")

        bf_frame = tk.Frame(frm_frame, bg=CONTENT_BG)
        bf_frame.pack(fill="x", padx=8, pady=(8, 4))
        self._btn_ling_frame = ttk.Button(
            bf_frame, text="▶  Analizar encuadres del corpus",
            style="P.TButton", command=self._ling_frames)
        self._btn_ling_frame.pack(side="left", padx=(0, 8))
        ttk.Button(bf_frame, text="📊  Graficar distribución", style="S.TButton",
                   command=self._ling_frames_graficar).pack(side="left", padx=(0, 8))
        ttk.Button(bf_frame, text="💾  Exportar CSV", style="S.TButton",
                   command=self._ling_frames_csv).pack(side="left", padx=(0, 8))
        self._lbl_ling_frame = tk.Label(frm_frame, text="", bg=CONTENT_BG,
                                         fg=VERDE, font=("Segoe UI", 9, "bold"))
        self._lbl_ling_frame.pack(anchor="w", padx=8)

        tk.Label(frm_frame,
                 text="Encuadre periodístico (Media Frames Corpus adaptado a prensa "
                      "ilustrada 1930s): desde qué ÁNGULO cubre cada artículo su tema.",
                 bg=CONTENT_BG, fg=GRIS2, font=("Segoe UI", 9),
                 wraplength=720, justify="left").pack(anchor="w", padx=8, pady=(0, 4))
        self._lbl_frame_resumen = tk.Label(frm_frame, text="",
                                            bg=CONTENT_BG, fg=TXT_SEC,
                                            font=("Segoe UI", 9), wraplength=720,
                                            justify="left")
        self._lbl_frame_resumen.pack(anchor="w", padx=8, pady=(0, 4))

        cols_frame = ("art_id", "frame", "etiqueta", "porcentaje", "secundario",
                      "marcadores")
        self._tv_ling_frame = ttk.Treeview(frm_frame, columns=cols_frame,
                                            show="headings", height=15)
        for cid, txt, w in [("art_id","Artículo",90),("frame","Frame dom.",110),
                              ("etiqueta","Etiqueta",230),
                              ("porcentaje","% dom.",70),
                              ("secundario","Frame 2º",110),
                              ("marcadores","N marcadores",90)]:
            self._tv_ling_frame.heading(cid, text=txt)
            self._tv_ling_frame.column(cid, width=w, anchor="w")
        sv_f = ttk.Scrollbar(frm_frame, orient="vertical",
                             command=self._tv_ling_frame.yview)
        self._tv_ling_frame.configure(yscrollcommand=sv_f.set)
        sv_f.pack(side="right", fill="y", padx=(0, 6))
        self._tv_ling_frame.pack(fill="both", expand=True, padx=6, pady=(0, 4))
        self._ling_frame_datos: list = []
        self._ling_frame_corpus: dict = {}

        # ── Pestaña 8: Polaridad discriminante ────────────────────────────────
        frm_pol = tk.Frame(nb_ling, bg=CONTENT_BG)
        nb_ling.add(frm_pol, text="  ⚖ Polaridad  ")

        bf_pol = tk.Frame(frm_pol, bg=CONTENT_BG)
        bf_pol.pack(fill="x", padx=8, pady=(8, 4))
        self._btn_ling_pol = ttk.Button(
            bf_pol, text="▶  Analizar polaridad del corpus",
            style="P.TButton", command=self._ling_polaridad)
        self._btn_ling_pol.pack(side="left", padx=(0, 8))
        ttk.Button(bf_pol, text="💾  Exportar CSV", style="S.TButton",
                   command=self._ling_pol_csv).pack(side="left", padx=(0, 8))
        self._lbl_ling_pol = tk.Label(frm_pol, text="", bg=CONTENT_BG,
                                      fg=VERDE, font=("Segoe UI", 9, "bold"))
        self._lbl_ling_pol.pack(anchor="w", padx=8)

        tk.Label(frm_pol,
                 text="Polaridad pos/neg/neutro discriminante (complemento al análisis "
                      "de 8 emociones, que sesga a «confianza»).",
                 bg=CONTENT_BG, fg=GRIS2, font=("Segoe UI", 9),
                 wraplength=720, justify="left").pack(anchor="w", padx=8, pady=(0, 4))

        # Polaridad hacia una entidad concreta
        pol_ent = tk.Frame(frm_pol, bg=CONTENT_BG)
        pol_ent.pack(fill="x", padx=8, pady=(0, 4))
        tk.Label(pol_ent, text="Polaridad hacia entidad (formas separadas por «;»):",
                 bg=CONTENT_BG, fg=TXT_SEC, font=("Segoe UI", 9)).pack(side="left")
        self._ent_pol_entidad = ttk.Entry(pol_ent, width=30)
        self._ent_pol_entidad.pack(side="left", padx=(6, 6))
        ttk.Button(pol_ent, text="🎯  Calcular", style="S.TButton",
                   command=self._ling_pol_hacia).pack(side="left")
        self._lbl_pol_hacia = tk.Label(pol_ent, text="", bg=CONTENT_BG,
                                       fg="#6CA8E8", font=("Segoe UI", 9, "bold"))
        self._lbl_pol_hacia.pack(side="left", padx=(10, 0))

        self._lbl_pol_resumen = tk.Label(frm_pol, text="",
                                         bg=CONTENT_BG, fg=TXT_SEC,
                                         font=("Segoe UI", 9), wraplength=720,
                                         justify="left")
        self._lbl_pol_resumen.pack(anchor="w", padx=8, pady=(0, 4))

        cols_pol = ("art_id", "polaridad", "score", "n_pos", "n_neg", "intensidad")
        self._tv_ling_pol = ttk.Treeview(frm_pol, columns=cols_pol,
                                          show="headings", height=14)
        for cid, txt, w in [("art_id","Artículo",90),("polaridad","Polaridad",100),
                              ("score","Score",80),("n_pos","Pos.",60),
                              ("n_neg","Neg.",60),("intensidad","Intensidad %",100)]:
            self._tv_ling_pol.heading(cid, text=txt)
            self._tv_ling_pol.column(cid, width=w, anchor="w")
        self._tv_ling_pol.tag_configure("positivo", foreground="#62C6B5")
        self._tv_ling_pol.tag_configure("negativo", foreground="#D96B6B")
        self._tv_ling_pol.tag_configure("neutro",   foreground=TXT_DIM)
        sv_p = ttk.Scrollbar(frm_pol, orient="vertical",
                             command=self._tv_ling_pol.yview)
        self._tv_ling_pol.configure(yscrollcommand=sv_p.set)
        sv_p.pack(side="right", fill="y", padx=(0, 6))
        self._tv_ling_pol.pack(fill="both", expand=True, padx=6, pady=(0, 4))
        self._ling_pol_datos: list = []

        # ── Pestaña 9: Revisión NER (human-in-the-loop) ───────────────────────
        frm_rev = tk.Frame(nb_ling, bg=CONTENT_BG)
        nb_ling.add(frm_rev, text="  🔍 Revisión NER  ")

        bf_rev = tk.Frame(frm_rev, bg=CONTENT_BG)
        bf_rev.pack(fill="x", padx=8, pady=(8, 4))
        self._btn_ling_rev = ttk.Button(
            bf_rev, text="▶  Construir cola de revisión",
            style="P.TButton", command=self._ling_rev_construir)
        self._btn_ling_rev.pack(side="left", padx=(0, 8))
        ttk.Button(bf_rev, text="✓  Verificar", style="S.TButton",
                   command=lambda: self._ling_rev_decidir("verificada")).pack(side="left", padx=(0, 4))
        ttk.Button(bf_rev, text="✗  Descartar", style="S.TButton",
                   command=lambda: self._ling_rev_decidir("descartada")).pack(side="left", padx=(0, 4))
        ttk.Button(bf_rev, text="✎  Renombrar…", style="S.TButton",
                   command=self._ling_rev_renombrar).pack(side="left", padx=(0, 8))
        self._lbl_ling_rev = tk.Label(frm_rev, text="", bg=CONTENT_BG,
                                      fg=VERDE, font=("Segoe UI", 9, "bold"))
        self._lbl_ling_rev.pack(anchor="w", padx=8)

        tk.Label(frm_rev,
                 text="Entidades dudosas (1 artículo = rojo, 2 = ámbar) priorizadas para "
                      "validar a mano. Las decisiones se guardan y se re-aplican al índice.",
                 bg=CONTENT_BG, fg=GRIS2, font=("Segoe UI", 9),
                 wraplength=720, justify="left").pack(anchor="w", padx=8, pady=(0, 4))

        cols_rev = ("nombre", "categoria", "n_articulos", "nivel", "etiqueta")
        self._tv_ling_rev = ttk.Treeview(frm_rev, columns=cols_rev,
                                          show="headings", height=16)
        for cid, txt, w in [("nombre","Entidad",220),("categoria","Categoría",120),
                              ("n_articulos","N arts.",70),("nivel","Nivel",80),
                              ("etiqueta","Estado",130)]:
            self._tv_ling_rev.heading(cid, text=txt)
            self._tv_ling_rev.column(cid, width=w, anchor="w")
        self._tv_ling_rev.tag_configure("red",    foreground="#D96B6B")
        self._tv_ling_rev.tag_configure("yellow", foreground="#E6A64C")
        sv_r = ttk.Scrollbar(frm_rev, orient="vertical",
                             command=self._tv_ling_rev.yview)
        self._tv_ling_rev.configure(yscrollcommand=sv_r.set)
        sv_r.pack(side="right", fill="y", padx=(0, 6))
        self._tv_ling_rev.pack(fill="both", expand=True, padx=6, pady=(0, 4))

        # ── Pestaña 10: Validación (Kappa) ────────────────────────────────────
        frm_val = tk.Frame(nb_ling, bg=CONTENT_BG)
        nb_ling.add(frm_val, text="  ✔ Validación  ")

        tk.Label(frm_val, text="Validación metodológica (fiabilidad inter-codificador)",
                 bg=CONTENT_BG, fg="#E8E5DF", font=("Segoe UI", 11, "bold")).pack(
                     anchor="w", padx=8, pady=(8, 2))
        tk.Label(frm_val,
                 text="1) Exporta una muestra aleatoria (semilla fija → reproducible) con la "
                      "clasificación automática y columnas vacías para codificar a mano.\n"
                      "2) Tras codificar el CSV, calcula el % de acuerdo y el Kappa de Cohen.",
                 bg=CONTENT_BG, fg=GRIS2, font=("Segoe UI", 9),
                 justify="left").pack(anchor="w", padx=8, pady=(0, 8))

        val_cfg = tk.Frame(frm_val, bg=CONTENT_BG)
        val_cfg.pack(fill="x", padx=8, pady=(0, 4))
        tk.Label(val_cfg, text="Dimensión:", bg=CONTENT_BG, fg=TXT_SEC,
                 font=("Segoe UI", 9)).pack(side="left")
        self._var_val_dim = tk.StringVar(value="polaridad")
        ttk.Combobox(val_cfg, textvariable=self._var_val_dim, width=12,
                     state="readonly",
                     values=["polaridad", "frame", "emocion"]).pack(side="left", padx=(4, 12))
        tk.Label(val_cfg, text="Tamaño muestra:", bg=CONTENT_BG, fg=TXT_SEC,
                 font=("Segoe UI", 9)).pack(side="left")
        self._var_val_n = tk.IntVar(value=30)
        ttk.Spinbox(val_cfg, from_=10, to=300, textvariable=self._var_val_n,
                    width=6).pack(side="left", padx=(4, 12))
        tk.Label(val_cfg, text="Semilla:", bg=CONTENT_BG, fg=TXT_SEC,
                 font=("Segoe UI", 9)).pack(side="left")
        self._var_val_semilla = tk.IntVar(value=42)
        ttk.Spinbox(val_cfg, from_=0, to=9999, textvariable=self._var_val_semilla,
                    width=6).pack(side="left", padx=(4, 0))

        bf_val = tk.Frame(frm_val, bg=CONTENT_BG)
        bf_val.pack(fill="x", padx=8, pady=(6, 4))
        ttk.Button(bf_val, text="💾  Exportar muestra para codificar…",
                   style="P.TButton",
                   command=self._ling_val_exportar).pack(side="left", padx=(0, 8))
        ttk.Button(bf_val, text="📐  Calcular concordancia (Kappa)…",
                   style="S.TButton",
                   command=self._ling_val_concordancia).pack(side="left", padx=(0, 8))
        self._lbl_ling_val = tk.Label(frm_val, text="", bg=CONTENT_BG,
                                      fg=VERDE, font=("Segoe UI", 9, "bold"))
        self._lbl_ling_val.pack(anchor="w", padx=8, pady=(4, 0))

        self._txt_val_res = scrolledtext.ScrolledText(
            frm_val, height=14, font=("Consolas", 9),
            bg=CARD_BG, fg=TXT_PRI, state="disabled", wrap="word")
        self._txt_val_res.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        # ── Log compartido ────────────────────────────────────────────────────
        self._txt_ling_log = scrolledtext.ScrolledText(
            pad, height=3, font=("Consolas", 8),
            bg="#12171B", fg="#B5B6B3", state="disabled", wrap="word")
        self._txt_ling_log.pack(fill="x", pady=(6, 0))

    def _ling_log(self, msg: str):
        self._txt_ling_log.config(state="normal")
        self._txt_ling_log.insert("end", msg + "\n")
        self._txt_ling_log.see("end")
        self._txt_ling_log.config(state="disabled")

    def _ling_corpus_txt(self) -> list[str]:
        """Corpus como lista de textos planos. Ver core.servicios_corpus.textos_corpus."""
        from core.servicios_corpus import textos_corpus
        return textos_corpus(getattr(ST, "corpus_txt", None),
                             getattr(ST, "df_articulos", None),
                             getattr(ST, "corpus_meta", None))

    def _ling_concordancias(self):
        corpus = self._ling_corpus_txt()
        if not corpus:
            messagebox.showwarning("Sin corpus",
                "Procesa primero el corpus en Normalizar o Segmentar.")
            return
        self._btn_ling_sint.config(state="disabled")
        self._lbl_ling_sint.config(text="Analizando…")
        patron = self._var_ling_patron.get()
        max_r = self._var_ling_max.get()
        threading.Thread(target=self._worker_ling_sint,
                         args=(corpus, patron, max_r), daemon=True).start()

    def _worker_ling_sint(self, corpus, patron, max_r):
        try:
            from core.sintaxis_engine import concordancias_sintaticas
        except ImportError as e:
            self.after(0, lambda err=str(e): messagebox.showerror("Import error", err))
            self.after(0, lambda: self._btn_ling_sint.config(state="normal"))
            return

        def cb(i, total):
            self.after(0, lambda: self._ling_log(f"Parseando doc {i}/{total}…"))

        try:
            res = concordancias_sintaticas(corpus, patron=patron,
                                           max_resultados=max_r, callback=cb)
            self._ling_sint_resultados = res
            self.after(0, lambda: self._poblar_tv_sint(res))
        except Exception as ex:
            self.after(0, lambda err=str(ex): messagebox.showerror("Error sintaxis", err))
        finally:
            self.after(0, lambda: self._btn_ling_sint.config(state="normal"))

    def _ling_sint_csv(self):
        if not self._ling_sint_resultados:
            messagebox.showinfo("Sin datos", "Ejecuta el análisis primero.")
            return
        import csv
        from tkinter import filedialog
        ruta = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="concordancias_sintaticas.csv",
        )
        if not ruta:
            return
        campos = ["patron", "match_principal", "match_secundario",
                  "descripcion", "texto_completo", "doc_idx"]
        with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
            w.writeheader()
            w.writerows(self._ling_sint_resultados)
        messagebox.showinfo("Exportado", f"CSV guardado en:\n{ruta}")

    def _ling_relaciones(self):
        corpus = self._ling_corpus_txt()
        if not corpus:
            messagebox.showwarning("Sin corpus",
                "Procesa primero el corpus en Normalizar o Segmentar.")
            return
        self._btn_ling_svo.config(state="disabled")
        self._btn_ling_sint.config(state="disabled")
        self._lbl_ling_svo.config(text="Extrayendo relaciones…")
        solo_ent = self._var_ling_solo_ent.get()
        conf = self._var_ling_conf.get()
        threading.Thread(target=self._worker_ling_svo,
                         args=(corpus, solo_ent, conf), daemon=True).start()

    def _worker_ling_svo(self, corpus, solo_ent, conf_min):
        try:
            from core.sintaxis_engine import extraer_relaciones
        except ImportError as e:
            self.after(0, lambda err=str(e): messagebox.showerror("Import error", err))
            self.after(0, lambda: self._btn_ling_svo.config(state="normal"))
            self.after(0, lambda: self._btn_ling_sint.config(state="normal"))
            return

        def cb(i, total):
            self.after(0, lambda: self._ling_log(f"Extrayendo relaciones doc {i}/{total}…"))

        try:
            res = extraer_relaciones(corpus, solo_entidades=solo_ent,
                                     min_confianza=conf_min, callback=cb)
            self._ling_svo_resultados = res
            self.after(0, lambda: self._poblar_tv_svo(res))
        except Exception as ex:
            self.after(0, lambda err=str(ex): messagebox.showerror("Error relaciones", err))
        finally:
            self.after(0, lambda: self._btn_ling_svo.config(state="normal"))
            self.after(0, lambda: self._btn_ling_sint.config(state="normal"))

    def _ling_svo_csv(self):
        if not self._ling_svo_resultados:
            messagebox.showinfo("Sin datos", "Ejecuta la extracción primero.")
            return
        from tkinter import filedialog

        from core.sintaxis_engine import exportar_relaciones_csv
        ruta = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="relaciones_svo.csv",
        )
        if not ruta:
            return
        exportar_relaciones_csv(self._ling_svo_resultados, ruta)
        messagebox.showinfo("Exportado", f"CSV guardado en:\n{ruta}")

    def _ling_svo_agrupar(self):
        if not self._ling_svo_resultados:
            messagebox.showinfo("Sin datos", "Ejecuta la extracción primero.")
            return
        from core.sintaxis_engine import agrupar_relaciones
        agrup = agrupar_relaciones(self._ling_svo_resultados)
        # Mostrar en ventana simple
        win, content_agrup = self._mk_glass_toplevel(
            "🔗 Relaciones agrupadas por verbo", ancho=600, alto=500)
        txt = scrolledtext.ScrolledText(content_agrup, font=("Consolas", 9),
                                         bg="#12171B", fg="#E8E5DF", relief="flat")
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        for verbo, info in agrup.items():
            txt.insert("end", f"\n{'─'*50}\n{verbo.upper()} ({info['n']} ocurrencias)\n")
            for r in info["relaciones"][:5]:
                txt.insert("end",
                    f"  {r.get('sujeto','—')} → {verbo} → {r.get('objeto','—')}\n")
        txt.config(state="disabled")

    def _ling_coref(self):
        corpus = self._ling_corpus_txt()
        if not corpus:
            messagebox.showwarning("Sin corpus",
                "Procesa primero el corpus en Normalizar o Segmentar.")
            return
        entidad = self._ent_coref.get().strip()
        self._btn_ling_coref.config(state="disabled")
        self._lbl_ling_coref.config(text="Resolviendo correferencias…")
        threading.Thread(target=self._worker_ling_coref,
                         args=(corpus, entidad), daemon=True).start()

    def _worker_ling_coref(self, corpus, entidad_filtro):
        try:
            from core.coref_engine import cadena_referencial, resolver_correferencias
        except ImportError as e:
            self.after(0, lambda err=str(e): messagebox.showerror("Import error", err))
            self.after(0, lambda: self._btn_ling_coref.config(state="normal"))
            return

        try:
            todas_cadenas = []
            for i, texto in enumerate(corpus[:50]):  # límite para velocidad
                self.after(0, lambda i=i: self._ling_log(
                    f"Correferencia texto {i+1}/{min(len(corpus),50)}…"))
                cadenas = resolver_correferencias(texto)
                for c in cadenas:
                    c["doc_idx"] = i
                    todas_cadenas.append(c)

            # Filtrar si hay entidad específica
            if entidad_filtro:
                filtradas = [c for c in todas_cadenas
                             if entidad_filtro.lower() in
                             c["entidad_principal"].lower()]
            else:
                filtradas = todas_cadenas

            # Ordenar por nº de menciones
            filtradas.sort(key=lambda x: -x.get("n_menciones", 0))

            self._ling_coref_cadenas = filtradas
            self.after(0, lambda: self._poblar_coref(filtradas))
        except Exception as ex:
            self.after(0, lambda err=str(ex): messagebox.showerror("Error coref", err))
        finally:
            self.after(0, lambda: self._btn_ling_coref.config(state="normal"))

    def _ling_coref_mostrar_cadena(self, event=None):
        sel = self._lb_coref.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(self._ling_coref_cadenas):
            return
        cadena = self._ling_coref_cadenas[idx]
        for row in self._tv_coref_men.get_children():
            self._tv_coref_men.delete(row)
        for m in cadena.get("menciones", []):
            self._tv_coref_men.insert("", "end", values=(
                m.get("texto", ""),
                m.get("tipo", ""),
                m.get("oracion", "")[:120],
            ))

    def _ling_coref_stats(self):
        corpus = self._ling_corpus_txt()
        if not corpus:
            messagebox.showwarning("Sin corpus",
                "Procesa primero el corpus.")
            return
        self._btn_ling_coref.config(state="disabled")
        threading.Thread(target=self._worker_coref_stats,
                         args=(corpus,), daemon=True).start()

    def _ling_morf_analizar(self):
        corpus = self._ling_corpus_txt()
        if not corpus:
            messagebox.showwarning("Sin corpus",
                "Procesa primero el corpus.")
            return
        normalizar = getattr(self, "_var_morf_normalizar",
                             tk.BooleanVar(value=True)).get()
        self._btn_ling_morf.config(state="disabled")
        self._lbl_ling_morf.config(text="Analizando formas históricas…")
        threading.Thread(target=self._worker_ling_morf,
                         args=(corpus, normalizar), daemon=True).start()

    def _worker_ling_morf(self, corpus, normalizar: bool = True):
        try:
            from core.morfologia_historica import (
                enriquecer_corpus_con_lemas,
                normalizar_formas_historicas,
            )
        except ImportError as e:
            self.after(0, lambda err=str(e): messagebox.showerror("Import error", err))
            self.after(0, lambda: self._btn_ling_morf.config(state="normal"))
            return

        def cb(i, t): self.after(0, lambda: self._ling_log(
            f"Morfología doc {i}/{t}…"))

        try:
            corpus_proc = ([normalizar_formas_historicas(t) for t in corpus]
                           if normalizar else corpus)
            datos = enriquecer_corpus_con_lemas(corpus_proc, callback=cb)
            self._ling_morf_datos = datos
            self.after(0, lambda: self._poblar_tv_morf(datos))
        except Exception as ex:
            self.after(0, lambda err=str(ex): messagebox.showerror("Error morfología", err))
        finally:
            self.after(0, lambda: self._btn_ling_morf.config(state="normal"))

    def _ling_morf_detalle(self):
        """Muestra detalle de marcadores y ejemplos del documento seleccionado."""
        sel = self._tv_ling_morf.selection()
        if not sel or not self._ling_morf_datos:
            self.toast("Selecciona un documento en la tabla primero", tipo="warn")
            return
        idx = self._tv_ling_morf.index(sel[0])
        if idx >= len(self._ling_morf_datos):
            return
        d = self._ling_morf_datos[idx]

        win, content = self._mk_glass_toplevel(
            f"📜 Detalle morfológico — Doc {d['doc_idx']+1}", ancho=560, alto=480)

        # Resumen numérico
        info = tk.Frame(content, bg=CONTENT_BG, pady=10)
        info.pack(fill="x", padx=16)
        for lbl, val in [("Tokens:", d["n_tokens"]),
                         ("Arcaísmos:", d["n_arcaismos"]),
                         ("Score histórico:", f"{d['score']:.4f}")]:
            row = tk.Frame(info, bg=CONTENT_BG); row.pack(fill="x", pady=1)
            tk.Label(row, text=lbl, bg=CONTENT_BG, fg=TXT_SEC,
                     font=("Segoe UI", 9), width=20, anchor="w").pack(side="left")
            tk.Label(row, text=str(val), bg=CONTENT_BG, fg=TXT_PRI,
                     font=("Segoe UI", 9, "bold")).pack(side="left")

        tk.Frame(content, bg=CARD_BOR, height=1).pack(fill="x", padx=8)

        # Marcadores morfosintácticos
        tk.Label(content, text="Marcadores morfosintácticos detectados",
                 bg=CONTENT_BG, fg=AZ4, font=("Segoe UI", 9, "bold")).pack(
                 anchor="w", padx=16, pady=(8, 2))
        marc = d.get("marcadores", {})
        if marc:
            for tipo, n in marc.items():
                row = tk.Frame(content, bg=CONTENT_BG); row.pack(fill="x", padx=24, pady=1)
                tk.Label(row, text=f"• {tipo}", bg=CONTENT_BG, fg=VERDE,
                         font=("Segoe UI", 9), width=30, anchor="w").pack(side="left")
                tk.Label(row, text=f"{n} ocurrencias", bg=CONTENT_BG, fg=TXT_SEC,
                         font=("Segoe UI", 9)).pack(side="left")
        else:
            tk.Label(content, text="  (ninguno)", bg=CONTENT_BG, fg=TXT_DIM,
                     font=("Segoe UI", 9, "italic")).pack(anchor="w", padx=24)

        tk.Frame(content, bg=CARD_BOR, height=1).pack(fill="x", padx=8, pady=(6, 0))

        # Ejemplos
        tk.Label(content, text="Ejemplos de formas históricas",
                 bg=CONTENT_BG, fg=AZ4, font=("Segoe UI", 9, "bold")).pack(
                 anchor="w", padx=16, pady=(8, 2))
        ejs = d.get("ejemplos", [])
        if ejs:
            cols_ej = ("token", "tipo")
            tv_ej = ttk.Treeview(content, columns=cols_ej, show="headings", height=8)
            tv_ej.heading("token", text="Forma"); tv_ej.column("token", width=200, anchor="w")
            tv_ej.heading("tipo",  text="Tipo");  tv_ej.column("tipo",  width=280, anchor="w")
            for ej in ejs:
                tv_ej.insert("", "end", values=(ej["token"], ej["tipo"]))
            tv_ej.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        else:
            tk.Label(content, text="  (ninguno)", bg=CONTENT_BG, fg=TXT_DIM,
                     font=("Segoe UI", 9, "italic")).pack(anchor="w", padx=24)

    def _ling_morf_glosario(self):
        from core.morfologia_historica import glosario_arcaismos
        glos = glosario_arcaismos()
        win, content = self._mk_glass_toplevel(
            f"📖 Glosario de arcaísmos ({len(glos)} entradas)", ancho=500, alto=600)

        # ── Pie con botón exportar ────────────────────────────────────────────
        pie = tk.Frame(content, bg=CONTENT_BG); pie.pack(side="bottom", fill="x", padx=6, pady=(4, 6))

        def _exportar_glosario():
            import csv
            import pathlib
            # ST.datos_dir no existe en core/estado.py: leerlo así reventaba
            # con AttributeError antes de llegar al diálogo de guardado, y el
            # botón "Exportar glosario" no funcionaba nunca. El directorio de
            # salida real del proyecto es ST.out_dir.
            destino = getattr(ST, "out_dir", None)
            out = pathlib.Path(destino) / "glosario_arcaismos.csv" if destino else None
            if out is None:
                from tkinter import filedialog
                ruta = filedialog.asksaveasfilename(
                    defaultextension=".csv", filetypes=[("CSV","*.csv")],
                    initialfile="glosario_arcaismos.csv")
                if not ruta: return
                out = pathlib.Path(ruta)
            with open(out, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["forma_historica", "lema_moderno"])
                for g in glos:
                    w.writerow([g["forma_historica"], g["lema_moderno"]])
            self.toast(f"Glosario exportado → {out.name}", tipo="ok")

        ttk.Button(pie, text="💾  Exportar CSV", style="S.TButton",
                   command=_exportar_glosario).pack(side="right")

        # ── Treeview ─────────────────────────────────────────────────────────
        cols = ("forma", "lema")
        tv = ttk.Treeview(content, columns=cols, show="headings", height=26)
        tv.heading("forma", text="Forma histórica")
        tv.heading("lema",  text="Lema moderno")
        tv.column("forma",  width=200, anchor="w")
        tv.column("lema",   width=200, anchor="w")
        sv = ttk.Scrollbar(content, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sv.set)
        sv.pack(side="right", fill="y")
        tv.pack(fill="both", expand=True, padx=6, pady=(6, 0))
        for g in glos:
            tv.insert("", "end", values=(g["forma_historica"], g["lema_moderno"]))

    def _ling_morf_csv(self):
        if not self._ling_morf_datos:
            messagebox.showinfo("Sin datos", "Ejecuta el análisis primero.")
            return
        import csv
        from tkinter import filedialog
        ruta = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="morfologia_historica.csv",
        )
        if not ruta:
            return
        with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
            campos = ["doc_idx", "n_tokens", "n_arcaismos", "score", "top_arcaismos"]
            w = csv.writer(f)
            w.writerow(campos)
            for d in self._ling_morf_datos:
                top = " | ".join(f"{x['forma']}x{x['n']}"
                                  for x in d.get("top_arcaismos", []))
                w.writerow([d["doc_idx"], d["n_tokens"],
                             d["n_arcaismos"], d["score"], top])
        messagebox.showinfo("Exportado", f"CSV guardado en:\n{ruta}")

    def _ling_dep_analizar(self):
        corpus = self._ling_corpus_txt()
        if not corpus:
            messagebox.showwarning("Sin corpus", "Procesa primero el corpus."); return
        art_idx = self._var_dep_art.get()
        if art_idx >= len(corpus):
            messagebox.showwarning("Índice inválido",
                f"El corpus tiene {len(corpus)} artículos (0–{len(corpus)-1})."); return
        texto = corpus[art_idx]
        max_or = self._var_dep_max.get()
        self._btn_ling_dep.config(state="disabled")
        self._lbl_ling_dep.config(text="Analizando dependencias…")
        threading.Thread(target=self._worker_ling_dep,
                         args=(texto, max_or), daemon=True).start()

    def _worker_ling_dep(self, texto: str, max_or: int):
        try:
            from core.sintaxis_engine import analizar_dependencias, resumir_arbol_dep
        except ImportError as e:
            self.after(0, lambda err=str(e): messagebox.showerror("Import error", err))
            self.after(0, lambda: self._btn_ling_dep.config(state="normal"))
            return
        try:
            datos = analizar_dependencias(texto, max_oraciones=max_or)
            self._ling_dep_datos = datos
            self.after(0, lambda: self._poblar_dep(datos))
        except Exception as ex:
            self.after(0, lambda err=str(ex): messagebox.showerror("Error árbol dep.", err))
        finally:
            self.after(0, lambda: self._btn_ling_dep.config(state="normal"))

    def _ling_dep_mostrar_tokens(self, event):
        sel = self._lb_dep.curselection()
        if not sel or not self._ling_dep_datos:
            return
        idx = sel[0]
        if idx >= len(self._ling_dep_datos):
            return
        d = self._ling_dep_datos[idx]
        for row in self._tv_dep_tok.get_children():
            self._tv_dep_tok.delete(row)
        for tok in d.get("tokens", []):
            tag = tok.get("pos", "")
            self._tv_dep_tok.insert("", "end", tags=(tag,), values=(
                tok["texto"], tok["lemma"], tok["pos"],
                tok["dep_es"], tok["cabeza"],
            ))

    def _ling_dep_csv(self):
        if not self._ling_dep_datos:
            self.toast("Ejecuta el análisis primero", tipo="warn"); return
        import csv
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="arbol_dependencias.csv")
        if not dest:
            return
        with open(dest, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["oracion_idx", "oracion", "sujeto", "verbo", "objeto",
                         "token", "lemma", "pos", "dep_es", "cabeza"])
            for i, d in enumerate(self._ling_dep_datos):
                for tok in d.get("tokens", []):
                    w.writerow([i + 1, d["oracion"][:80],
                                 d.get("sujeto", ""), d.get("verbo", ""),
                                 d.get("objeto", ""),
                                 tok["texto"], tok["lemma"], tok["pos"],
                                 tok["dep_es"], tok["cabeza"]])
        self.toast(f"CSV exportado → {Path(dest).name}", tipo="ok")

    def _ling_emociones(self):
        corpus = self._ling_corpus_txt()
        if not corpus:
            messagebox.showwarning("Sin corpus",
                "Procesa primero el corpus.")
            return
        self._btn_ling_emo.config(state="disabled")
        self._lbl_ling_emo.config(text="Analizando emociones…")
        threading.Thread(target=self._worker_ling_emo,
                         args=(corpus,), daemon=True).start()

    def _worker_ling_emo(self, corpus):
        try:
            from core.sentiment_engine import analisis_completo_emocion
        except ImportError as e:
            self.after(0, lambda err=str(e): messagebox.showerror("Import error", err))
            self.after(0, lambda: self._btn_ling_emo.config(state="normal"))
            return

        try:
            resultados = []
            total = len(corpus)
            for i, texto in enumerate(corpus):
                self.after(0, lambda i=i: self._ling_log(
                    f"Emociones doc {i+1}/{total}…"))
                res = analisis_completo_emocion(texto)
                res["doc_idx"] = i
                res["art_id"]  = f"doc_{i+1:04d}"
                resultados.append(res)
            self._ling_emo_datos = resultados
            self.after(0, lambda: self._poblar_tv_emo(resultados))
        except Exception as ex:
            self.after(0, lambda err=str(ex): messagebox.showerror("Error emociones", err))
        finally:
            self.after(0, lambda: self._btn_ling_emo.config(state="normal"))

    def _ling_emo_graficar(self):
        if not self._ling_emo_datos:
            messagebox.showinfo("Sin datos", "Ejecuta el análisis primero.")
            return
        from collections import Counter
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            messagebox.showerror("Error", "Instala matplotlib para graficar.")
            return

        cnt: Counter = Counter()
        for r in self._ling_emo_datos:
            emo = r.get("emociones", {}).get("emocion_dominante")
            if emo:
                cnt[emo] += 1

        if not cnt:
            messagebox.showinfo("Sin datos", "No se detectaron emociones.")
            return

        emociones = list(cnt.keys())
        valores = [cnt[e] for e in emociones]
        colores = ["#6EC69A","#6CA8E8","#D96B6B","#E6A64C",
                   "#B18AD6","#B18AD6","#62C6B5","#D58B45"]

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(emociones, valores,
               color=colores[:len(emociones)], edgecolor="none")
        ax.set_title("Distribución de emociones dominantes en el corpus",
                     pad=12, fontsize=11)
        ax.set_ylabel("Artículos")
        ax.set_facecolor("#12171B")
        fig.patch.set_facecolor("#12171B")
        ax.tick_params(colors="#B5B6B3")
        ax.yaxis.label.set_color("#B5B6B3")
        ax.title.set_color("#E8E5DF")
        for spine in ax.spines.values():
            spine.set_edgecolor("#30291F")
        plt.tight_layout()
        plt.show()

    def _ling_emo_csv(self):
        if not self._ling_emo_datos:
            messagebox.showinfo("Sin datos", "Ejecuta el análisis primero.")
            return
        import csv
        from tkinter import filedialog
        ruta = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="emociones_corpus.csv",
        )
        if not ruta:
            return
        with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
            campos = ["art_id", "emocion_dominante", "score_subjetividad",
                      "tipo_discurso", "score_intensidad", "palabras_emocionales"]
            w = csv.writer(f)
            w.writerow(campos)
            for r in self._ling_emo_datos:
                emo_data = r.get("emociones", {})
                subj     = r.get("subjetividad", {})
                intens   = r.get("intensidad", {})
                palabras = " | ".join(
                    p["palabra"] for p in emo_data.get("palabras_detectadas", [])[:10]
                )
                w.writerow([
                    r.get("art_id", ""),
                    emo_data.get("emocion_dominante", ""),
                    subj.get("score_subjetividad", 0),
                    subj.get("tipo_discurso", ""),
                    intens.get("score_intensidad", 0),
                    palabras,
                ])
        messagebox.showinfo("Exportado", f"CSV guardado en:\n{ruta}")

    def _ling_frames(self):
        corpus = self._ling_corpus_txt()
        if not corpus:
            messagebox.showwarning("Sin corpus", "Procesa primero el corpus.")
            return
        self._btn_ling_frame.config(state="disabled")
        self._lbl_ling_frame.config(text="Analizando encuadres…")
        threading.Thread(target=self._worker_ling_frames,
                         args=(corpus,), daemon=True).start()

    def _worker_ling_frames(self, corpus):
        try:
            from core import frame_engine
        except ImportError as e:
            self.after(0, lambda err=str(e): messagebox.showerror("Import error", err))
            self.after(0, lambda: self._btn_ling_frame.config(state="normal"))
            return
        try:
            corpus_dict = {f"doc_{i+1:04d}": t for i, t in enumerate(corpus)}
            resumen = frame_engine.analizar_corpus_frames(corpus_dict)
            self._ling_frame_corpus = resumen
            datos = []
            for art_id, r in resumen["por_articulo"].items():
                datos.append({"art_id": art_id, **r})
            self._ling_frame_datos = datos
            self.after(0, lambda: self._poblar_tv_frame(resumen, datos))
        except Exception as ex:
            self.after(0, lambda err=str(ex): messagebox.showerror("Error encuadre", err))
        finally:
            self.after(0, lambda: self._btn_ling_frame.config(state="normal"))

    def _ling_frames_graficar(self):
        if not self._ling_frame_corpus:
            messagebox.showinfo("Sin datos", "Ejecuta el análisis primero.")
            return
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            messagebox.showerror("Error", "Instala matplotlib para graficar.")
            return
        dist = self._ling_frame_corpus.get("distribucion_corpus", {})
        if not dist:
            messagebox.showinfo("Sin datos", "No se detectaron encuadres.")
            return
        frames = list(dist.keys())
        valores = [dist[f] for f in frames]
        fig, ax = plt.subplots(figsize=(9, 4.5))
        ax.barh(frames[::-1], valores[::-1], color="#6CA8E8", edgecolor="none")
        ax.set_title("Encuadres dominantes en el corpus", pad=12, fontsize=11)
        ax.set_xlabel("Artículos")
        fig.tight_layout()
        plt.show()

    def _ling_frames_csv(self):
        if not self._ling_frame_datos:
            messagebox.showinfo("Sin datos", "Ejecuta el análisis primero.")
            return
        import csv
        from tkinter import filedialog
        ruta = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile="encuadres_corpus.csv")
        if not ruta:
            return
        with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["art_id", "frame_dominante", "etiqueta", "porcentaje_dom",
                        "total_marcadores", "distribucion"])
            for d in self._ling_frame_datos:
                dist = d.get("distribucion", [])
                pct = dist[0]["porcentaje"] if dist else 0
                resumen_dist = "; ".join(
                    f"{x['frame']}:{x['porcentaje']}%" for x in dist)
                w.writerow([d.get("art_id", ""), d.get("frame_dominante") or "",
                            d.get("etiqueta") or "", pct,
                            d.get("total_marcadores", 0), resumen_dist])
        messagebox.showinfo("Exportado", f"CSV guardado en:\n{ruta}")

    def _ling_polaridad(self):
        corpus = self._ling_corpus_txt()
        if not corpus:
            messagebox.showwarning("Sin corpus", "Procesa primero el corpus.")
            return
        self._btn_ling_pol.config(state="disabled")
        self._lbl_ling_pol.config(text="Analizando polaridad…")
        threading.Thread(target=self._worker_ling_pol,
                         args=(corpus,), daemon=True).start()

    def _worker_ling_pol(self, corpus):
        try:
            from core import sentimiento_discriminante as sd
        except ImportError as e:
            self.after(0, lambda err=str(e): messagebox.showerror("Import error", err))
            self.after(0, lambda: self._btn_ling_pol.config(state="normal"))
            return
        try:
            datos = []
            for i, texto in enumerate(corpus):
                r = sd.analizar_polaridad(texto)
                r["art_id"] = f"doc_{i+1:04d}"
                datos.append(r)
            self._ling_pol_datos = datos
            self.after(0, lambda: self._poblar_tv_pol(datos))
        except Exception as ex:
            self.after(0, lambda err=str(ex): messagebox.showerror("Error polaridad", err))
        finally:
            self.after(0, lambda: self._btn_ling_pol.config(state="normal"))

    def _ling_pol_hacia(self):
        formas = [s.strip() for s in self._ent_pol_entidad.get().split(";")
                  if s.strip()]
        if not formas:
            messagebox.showinfo("Entidad vacía",
                "Escribe una o más formas de la entidad, separadas por «;».")
            return
        corpus = self._ling_corpus_txt()
        if not corpus:
            messagebox.showwarning("Sin corpus", "Procesa primero el corpus.")
            return
        try:
            from core import sentimiento_discriminante as sd
        except ImportError as e:
            messagebox.showerror("Import error", str(e))
            return
        r = sd.polaridad_hacia_corpus(corpus, formas)
        n_docs = r.get("n_documentos", 0)
        extra = f" en {n_docs} art." if n_docs else ""
        self._lbl_pol_hacia.config(
            text=f"→ {r['polaridad']}  (score {r.get('score', 0):+.3f}, "
                 f"{r.get('n_menciones', 0)} menciones{extra})")

    def _ling_pol_csv(self):
        if not self._ling_pol_datos:
            messagebox.showinfo("Sin datos", "Ejecuta el análisis primero.")
            return
        import csv
        from tkinter import filedialog
        ruta = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile="polaridad_corpus.csv")
        if not ruta:
            return
        with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["art_id", "polaridad", "score", "n_pos", "n_neg",
                        "intensidad"])
            for r in self._ling_pol_datos:
                w.writerow([r.get("art_id", ""), r.get("polaridad", ""),
                            r.get("score", 0), r.get("n_pos", 0),
                            r.get("n_neg", 0), r.get("intensidad", 0)])
        messagebox.showinfo("Exportado", f"CSV guardado en:\n{ruta}")

    def _ling_rev_con(self):
        """Conexión SQLite para la cola de revisión (la del proyecto, o una junto a él)."""
        import sqlite3
        from pathlib import Path
        ruta = getattr(ST, "ruta_db", "") or ""
        if not ruta:
            base = getattr(ST, "out_dir", None) or Path.cwd()
            ruta = str(Path(base) / "revision_ner.db")
        con = sqlite3.connect(ruta, timeout=30)
        con.row_factory = sqlite3.Row
        return con

    def _ling_rev_construir(self):
        indice = getattr(ST, "indice_ner_global", None)
        if not indice:
            messagebox.showwarning("Sin índice NER",
                "Ejecuta primero el NER del corpus (panel Entidades).")
            return
        try:
            from core import revision_engine
            con = self._ling_rev_con()
            cola = revision_engine.construir_cola(indice)
            revision_engine.guardar_cola(con, cola)
            pend = revision_engine.pendientes(con)
            con.close()
        except Exception as ex:
            messagebox.showerror("Error revisión", str(ex))
            return
        self._poblar_tv_rev(pend)
        self._lbl_ling_rev.config(
            text=f"✓ {len(pend)} entidades pendientes de revisar.")

    def _ling_rev_sel(self):
        sel = self._tv_ling_rev.selection()
        if not sel:
            messagebox.showinfo("Sin selección",
                "Selecciona una entidad de la lista.")
            return None
        vals = self._tv_ling_rev.item(sel[0], "values")
        return vals[0], vals[1]  # nombre, categoria

    def _ling_rev_aplicar_al_indice(self, con):
        """Re-aplica TODAS las decisiones tomadas al índice NER en memoria
        (descarta lo rechazado, fusiona renombres). Mantiene el índice limpio
        para exportación y para que la cola no vuelva a mostrar lo ya resuelto."""
        from core import revision_engine
        decisiones = revision_engine.cargar_decisiones(con)
        revision_engine.aplicar_revisiones(
            getattr(ST, "indice_ner_global", {}) or {}, decisiones)

    def _ling_rev_decidir(self, decision):
        s = self._ling_rev_sel()
        if not s:
            return
        nombre, categoria = s
        try:
            from core import revision_engine
            con = self._ling_rev_con()
            revision_engine.decidir(con, nombre, categoria, decision)
            self._ling_rev_aplicar_al_indice(con)
            pend = revision_engine.pendientes(con)
            con.close()
        except Exception as ex:
            messagebox.showerror("Error revisión", str(ex))
            return
        self._poblar_tv_rev(pend)
        self._lbl_ling_rev.config(
            text=f"«{nombre}» → {decision}.  {len(pend)} pendientes.")

    def _ling_rev_renombrar(self):
        s = self._ling_rev_sel()
        if not s:
            return
        nombre, categoria = s
        from tkinter import simpledialog
        nuevo = simpledialog.askstring(
            "Renombrar entidad",
            f"Nuevo nombre canónico para «{nombre}»:", initialvalue=nombre)
        if not nuevo or nuevo == nombre:
            return
        try:
            from core import revision_engine
            con = self._ling_rev_con()
            revision_engine.decidir(con, nombre, categoria, "renombrada",
                                    nombre_nuevo=nuevo)
            self._ling_rev_aplicar_al_indice(con)
            pend = revision_engine.pendientes(con)
            con.close()
        except Exception as ex:
            messagebox.showerror("Error revisión", str(ex))
            return
        self._poblar_tv_rev(pend)
        self._lbl_ling_rev.config(text=f"«{nombre}» → «{nuevo}».")

    def _ling_val_articulos(self):
        """Construye la lista de artículos para la muestra de validación."""
        corpus = self._ling_corpus_txt()
        return [{"art_id": f"doc_{i+1:04d}", "texto": t}
                for i, t in enumerate(corpus)]

    def _ling_val_etiquetador(self, dim):
        try:
            if dim == "polaridad":
                from core import sentimiento_discriminante as sd
                return lambda a: sd.analizar_polaridad(a.get("texto", "")).get("polaridad", "")
            elif dim == "emocion":
                from core.sentiment_engine import analizar_emociones
                return lambda a: (analizar_emociones(a.get("texto", "")) or {}).get(
                    "emocion_dominante") or ""
            else:  # frame
                from core import frame_engine
                return lambda a: frame_engine.analizar_frame(
                    a.get("texto", "")).get("frame_dominante") or ""
        except ImportError:
            return None

    def _ling_val_exportar(self):
        arts = self._ling_val_articulos()
        if not arts:
            messagebox.showwarning("Sin corpus", "Procesa primero el corpus.")
            return
        from tkinter import filedialog
        dim = self._var_val_dim.get()
        ruta = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile=f"muestra_validacion_{dim}.csv")
        if not ruta:
            return
        try:
            from core import validacion_engine
            etiquetador = self._ling_val_etiquetador(dim)
            validacion_engine.exportar_muestra(
                arts, ruta, n=self._var_val_n.get(),
                semilla=self._var_val_semilla.get(),
                etiqueta_auto=etiquetador, nombre_etiqueta=dim)
        except Exception as ex:
            messagebox.showerror("Error validación", str(ex))
            return
        self._lbl_ling_val.config(
            text=f"✓ Muestra exportada. Codifica la columna «{dim}_manual» y vuelve.")
        self._val_log(
            f"Muestra de {self._var_val_n.get()} artículos (semilla "
            f"{self._var_val_semilla.get()}) → {ruta}\n"
            f"Codifica a mano la columna '{dim}_manual' (mismas etiquetas que "
            f"'{dim}_auto') y luego usa «Calcular concordancia».")

    def _ling_val_concordancia(self):
        from tkinter import filedialog
        dim = self._var_val_dim.get()
        ruta = filedialog.askopenfilename(
            filetypes=[("CSV", "*.csv")], title="CSV codificado a mano")
        if not ruta:
            return
        try:
            from core import validacion_engine
            r = validacion_engine.calcular_concordancia(ruta, nombre_etiqueta=dim)
        except Exception as ex:
            messagebox.showerror("Error validación", str(ex))
            return
        if r.get("error"):
            self._val_log("⚠ " + r["error"])
            self._lbl_ling_val.config(text="Sin filas codificadas a mano.")
            return
        lineas = [
            f"Concordancia para «{dim}»  (n = {r['n']} artículos codificados)",
            "─" * 56,
            f"  Acuerdo observado : {r['acuerdo']*100:.1f}%",
            f"  Kappa de Cohen    : {r['kappa']:.3f}  ({r['interpretacion']})",
            "",
            "Matriz de confusión (manual ↓ / auto →):",
        ]
        matriz = r.get("matriz_confusion", {})
        autos = sorted({a for fila in matriz.values() for a in fila})
        lineas.append("            " + "  ".join(f"{a[:8]:>8}" for a in autos))
        for man, fila in matriz.items():
            celdas = "  ".join(f"{fila.get(a, 0):>8}" for a in autos)
            lineas.append(f"  {man[:10]:<10}{celdas}")
        self._val_log("\n".join(lineas))
        self._lbl_ling_val.config(
            text=f"Kappa = {r['kappa']:.3f} ({r['interpretacion']}), "
                 f"acuerdo {r['acuerdo']*100:.1f}%")
