"""paneles/bitacora.py — Métodos de BashkarApp extraídos de app.py.

Mixin: BashkarApp hereda de PanelBitacora. Los cuerpos son copia literal del
original. Importa explícitamente lo que usa; los colores del tema se
leen de gui_comun.TEMA porque cambian en caliente.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.bitacora_engine import BitacoraEngine

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

from gui_comun import (
    ST,
    TEMA,
    _registrar_error,
)


class PanelBitacora:
    def _bitacora_engine(self) -> "BitacoraEngine | None":
        """Retorna instancia de BitacoraEngine para el proyecto activo."""
        if not ST.ruta_db:
            return None
        # Se renueva al cambiar de proyecto: si no, las notas irían a la base
        # del primer proyecto abierto en la sesión.
        if self._bitacora_eng_cache is None or self._bitacora_eng_db != ST.ruta_db:
            try:
                from core.bitacora_engine import BitacoraEngine
                self._bitacora_eng_cache = BitacoraEngine(ST.ruta_db)
                self._bitacora_eng_db = ST.ruta_db
            except Exception as e:
                _registrar_error(f"bitácora: no se pudo abrir {ST.ruta_db}", e)
                return None
        return self._bitacora_eng_cache

    def _bitacora_abrir(self):
        """Abre (o trae al frente) la ventana flotante de bitácora."""
        if self._bitacora_win is not None:
            try:
                self._bitacora_win.lift()
                self._bitacora_win.focus_set()
                return
            except Exception:
                self._bitacora_win = None

        win, bit_content = self._mk_glass_toplevel("📓 Bitácora de investigación",
                                                     ancho=760, alto=560)
        win.attributes("-topmost", True)
        win.protocol("WM_DELETE_WINDOW", lambda: self._bitacora_cerrar(win))
        self._bitacora_win = win

        nb = ttk.Notebook(bit_content)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # ── Tab 1: Nueva nota ──────────────────────────────────────────────────
        tab_nueva = tk.Frame(nb, bg=TEMA.CONTENT_BG, padx=12, pady=10)
        nb.add(tab_nueva, text="  ➕ Nueva nota  ")
        self._bitacora_build_nueva(tab_nueva)

        # ── Tab 2: Todas las notas ─────────────────────────────────────────────
        tab_lista = tk.Frame(nb, bg=TEMA.CONTENT_BG, padx=8, pady=6)
        nb.add(tab_lista, text="  📋 Todas las notas  ")
        self._bitacora_build_lista(tab_lista)

        win._nb = nb
        self._bitacora_refrescar_lista()

    def _bitacora_cerrar(self, win):
        win.destroy()
        self._bitacora_win = None

    def _bitacora_build_nueva(self, parent):
        """Construye el formulario de nueva nota."""
        # Tipo de nota
        row_tipo = tk.Frame(parent, bg=TEMA.CONTENT_BG)
        row_tipo.pack(fill="x", pady=(0, 6))
        tk.Label(row_tipo, text="Tipo:", bg=TEMA.CONTENT_BG, fg=TEMA.TXT_PRI,
                 font=("Segoe UI", 9, "bold"), width=10, anchor="w").pack(side="left")
        self._bvar_tipo = tk.StringVar(value="libre")
        for val, etiq in [("libre", "📝 Libre"), ("hipotesis", "💡 Hipótesis"), ("cita", "📌 Cita")]:
            ttk.Radiobutton(row_tipo, text=etiq, variable=self._bvar_tipo,
                            value=val, command=self._bitacora_on_tipo).pack(side="left", padx=6)

        # Estado (solo si hipótesis)
        self._row_estado = tk.Frame(parent, bg=TEMA.CONTENT_BG)
        tk.Label(self._row_estado, text="Estado:", bg=TEMA.CONTENT_BG, fg=TEMA.TXT_PRI,
                 font=("Segoe UI", 9, "bold"), width=10, anchor="w").pack(side="left")
        self._bvar_estado = tk.StringVar(value="abierta")
        for val, etiq in [("abierta","🔵 Abierta"),("confirmada","✅ Confirmada"),
                          ("descartada","❌ Descartada"),("revisada","🔄 Revisada")]:
            ttk.Radiobutton(self._row_estado, text=etiq,
                            variable=self._bvar_estado, value=val).pack(side="left", padx=4)
        # Ocultar inicialmente
        self._bitacora_on_tipo()

        # Referencia (pre-rellena desde módulo activo)
        row_ref = tk.Frame(parent, bg=TEMA.CONTENT_BG)
        row_ref.pack(fill="x", pady=(0, 4))
        tk.Label(row_ref, text="Referencia:", bg=TEMA.CONTENT_BG, fg=TEMA.TXT_PRI,
                 font=("Segoe UI", 9, "bold"), width=10, anchor="w").pack(side="left")
        self._bvar_ref_num = tk.StringVar()
        self._bvar_ref_pag = tk.StringVar()
        tk.Entry(row_ref, textvariable=self._bvar_ref_num, width=20,
                 font=("Segoe UI", 9), bg="#171C20", fg=TEMA.TXT_PRI,
                 relief="solid", bd=1, insertbackground=TEMA.TXT_PRI).pack(side="left", padx=(0, 4))
        tk.Label(row_ref, text="pág:", bg=TEMA.CONTENT_BG,
                 fg=TEMA.TXT_DIM, font=("Segoe UI", 8)).pack(side="left")
        tk.Entry(row_ref, textvariable=self._bvar_ref_pag, width=10,
                 font=("Segoe UI", 9), bg="#171C20", fg=TEMA.TXT_PRI,
                 relief="solid", bd=1, insertbackground=TEMA.TXT_PRI).pack(side="left", padx=(2, 8))
        tk.Label(row_ref, text="módulo:", bg=TEMA.CONTENT_BG,
                 fg=TEMA.TXT_DIM, font=("Segoe UI", 8)).pack(side="left")
        self._bvar_modulo = tk.StringVar()
        tk.Entry(row_ref, textvariable=self._bvar_modulo, width=12,
                 font=("Segoe UI", 9), bg="#171C20", fg=TEMA.TXT_PRI,
                 relief="solid", bd=1, insertbackground=TEMA.TXT_PRI,
                 state="readonly").pack(side="left", padx=2)

        # Etiquetas
        row_tags = tk.Frame(parent, bg=TEMA.CONTENT_BG)
        row_tags.pack(fill="x", pady=(0, 4))
        tk.Label(row_tags, text="Etiquetas:", bg=TEMA.CONTENT_BG, fg=TEMA.TXT_PRI,
                 font=("Segoe UI", 9, "bold"), width=10, anchor="w").pack(side="left")
        self._bvar_tags = tk.StringVar()
        tk.Entry(row_tags, textvariable=self._bvar_tags, width=50,
                 font=("Segoe UI", 9), bg="#171C20", fg=TEMA.TXT_PRI,
                 relief="solid", bd=1, insertbackground=TEMA.TXT_PRI).pack(side="left")
        tk.Label(row_tags, text="(separadas por coma)", bg=TEMA.CONTENT_BG,
                 fg=TEMA.TXT_DIM, font=("Segoe UI", 8)).pack(side="left", padx=6)

        # Texto
        tk.Label(parent, text="Nota:", bg=TEMA.CONTENT_BG, fg=TEMA.TXT_PRI,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(4, 2))
        self._btxt_nota = scrolledtext.ScrolledText(
            parent, height=8, bg="#171C20", fg=TEMA.TXT_PRI,
            insertbackground=TEMA.TXT_PRI, font=("Segoe UI", 10),
            relief="solid", bd=1, wrap="word")
        self._btxt_nota.pack(fill="both", expand=True)

        # Botón guardar
        row_btn = tk.Frame(parent, bg=TEMA.CONTENT_BG)
        row_btn.pack(fill="x", pady=(8, 0))
        ttk.Button(row_btn, text="💾 Guardar nota", style="P.TButton",
                   command=self._bitacora_guardar_nota).pack(side="left")
        self._blbl_ok = tk.Label(row_btn, text="", bg=TEMA.CONTENT_BG,
                                  fg=TEMA.VERDE, font=("Segoe UI", 9, "bold"))
        self._blbl_ok.pack(side="left", padx=10)

    def _bitacora_on_tipo(self):
        """Muestra/oculta el selector de estado según tipo."""
        if self._bvar_tipo.get() == "hipotesis":
            self._row_estado.pack(fill="x", pady=(0, 4))
        else:
            self._row_estado.pack_forget()

    def _bitacora_build_lista(self, parent):
        """Construye la vista de todas las notas con filtros."""
        # Barra de filtros
        fbar = tk.Frame(parent, bg=TEMA.CONTENT_BG)
        fbar.pack(fill="x", pady=(0, 6))

        tk.Label(fbar, text="Tipo:", bg=TEMA.CONTENT_BG, fg=TEMA.TXT_DIM,
                 font=("Segoe UI", 8)).pack(side="left")
        self._bflt_tipo = tk.StringVar(value="todos")
        ttk.Combobox(fbar, textvariable=self._bflt_tipo,
                     values=["todos", "libre", "hipotesis", "cita"],
                     state="readonly", width=10,
                     font=("Segoe UI", 8)).pack(side="left", padx=(2, 8))

        tk.Label(fbar, text="Estado:", bg=TEMA.CONTENT_BG, fg=TEMA.TXT_DIM,
                 font=("Segoe UI", 8)).pack(side="left")
        self._bflt_estado = tk.StringVar(value="todos")
        ttk.Combobox(fbar, textvariable=self._bflt_estado,
                     values=["todos", "abierta", "confirmada", "descartada", "revisada"],
                     state="readonly", width=12,
                     font=("Segoe UI", 8)).pack(side="left", padx=(2, 8))

        tk.Label(fbar, text="Buscar:", bg=TEMA.CONTENT_BG, fg=TEMA.TXT_DIM,
                 font=("Segoe UI", 8)).pack(side="left")
        self._bflt_q = tk.StringVar()
        tk.Entry(fbar, textvariable=self._bflt_q, width=20,
                 font=("Segoe UI", 9), bg="#171C20", fg=TEMA.TXT_PRI,
                 relief="solid", bd=1, insertbackground=TEMA.TXT_PRI).pack(side="left", padx=(2, 6))
        ttk.Button(fbar, text="🔍", style="S.TButton",
                   command=self._bitacora_refrescar_lista).pack(side="left")
        ttk.Button(fbar, text="📄 Exportar Markdown", style="S.TButton",
                   command=self._bitacora_exportar_md).pack(side="right")

        # Treeview
        cols = ("tipo", "ref", "texto", "etiquetas", "fecha")
        self._btv = ttk.Treeview(parent, columns=cols, show="headings", height=12)
        self._btv.heading("tipo",     text="Tipo",        anchor="w")
        self._btv.heading("ref",      text="Referencia",  anchor="w")
        self._btv.heading("texto",    text="Texto",        anchor="w")
        self._btv.heading("etiquetas",text="Etiquetas",   anchor="w")
        self._btv.heading("fecha",    text="Fecha",       anchor="w")
        self._btv.column("tipo",     width=90,  stretch=False)
        self._btv.column("ref",      width=110, stretch=False)
        self._btv.column("texto",    width=300)
        self._btv.column("etiquetas",width=120, stretch=False)
        self._btv.column("fecha",    width=90,  stretch=False)

        # Colores por tipo
        self._btv.tag_configure("libre",     background="#171C20", foreground=TEMA.TXT_SEC)
        self._btv.tag_configure("hipotesis", background="#14202A", foreground="#6CA8E8")
        self._btv.tag_configure("cita",      background="#15251F", foreground="#6EC69A")

        sb = ttk.Scrollbar(parent, orient="vertical", command=self._btv.yview)
        self._btv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._btv.pack(fill="both", expand=True)
        self._btv.bind("<Double-1>", self._bitacora_editar_seleccion)

        # Botón eliminar
        btn_row = tk.Frame(parent, bg=TEMA.CONTENT_BG)
        btn_row.pack(fill="x", pady=(4, 0))
        ttk.Button(btn_row, text="🗑 Eliminar seleccionada", style="S.TButton",
                   command=self._bitacora_eliminar_seleccion).pack(side="left")
        self._btv_ids: dict[str, int] = {}  # iid → nota_id

    def _bitacora_guardar_nota(self):
        """Guarda la nota actual en la BD."""
        eng = self._bitacora_engine()
        if eng is None:
            messagebox.showwarning("Sin proyecto",
                                   "Abre o crea un proyecto antes de guardar notas.")
            return
        texto = self._btxt_nota.get("1.0", "end-1c").strip()
        if not texto:
            messagebox.showwarning("Nota vacía", "Escribe algo en el campo de nota.")
            return
        tags_raw = self._bvar_tags.get()
        etiquetas = [t.strip() for t in tags_raw.split(",") if t.strip()]
        nota = {
            "tipo":          self._bvar_tipo.get(),
            "estado":        self._bvar_estado.get() if self._bvar_tipo.get() == "hipotesis" else None,
            "texto":         texto,
            "etiquetas":     etiquetas,
            "ref_numero":    self._bvar_ref_num.get().strip(),
            "ref_pagina":    self._bvar_ref_pag.get().strip(),
            "modulo_origen": self._bvar_modulo.get().strip(),
        }
        eng.insertar(nota)
        self._btxt_nota.delete("1.0", "end")
        self._bvar_tags.set("")
        self._blbl_ok.config(text="✅ Nota guardada")
        self.after(2000, lambda: self._blbl_ok.config(text=""))
        self._bitacora_refrescar_lista()

    def _bitacora_refrescar_lista(self):
        """Recarga el treeview con las notas filtradas."""
        if not hasattr(self, "_btv"):
            return
        eng = self._bitacora_engine()
        if eng is None:
            return
        tipo   = self._bflt_tipo.get()  if hasattr(self, "_bflt_tipo")   else "todos"
        estado = self._bflt_estado.get() if hasattr(self, "_bflt_estado") else "todos"
        q      = self._bflt_q.get()     if hasattr(self, "_bflt_q")      else ""
        notas = eng.listar(
            tipo=None if tipo == "todos" else tipo,
            estado=None if estado == "todos" else estado,
            q=q or None,
        )
        self._btv.delete(*self._btv.get_children())
        self._btv_ids = {}
        iconos = {"libre": "📝", "hipotesis": "💡", "cita": "📌"}
        for n in notas:
            tipo_n = n.get("tipo", "libre")
            icono  = iconos.get(tipo_n, "")
            estado_n = n.get("estado") or ""
            ref    = " ".join(filter(None, [n.get("ref_numero"), n.get("ref_pagina")]))
            texto  = n.get("texto", "")
            preview = texto[:60].replace("\n", " ") + ("…" if len(texto) > 60 else "")
            tags_str = ", ".join(n.get("etiquetas", []))
            fecha  = (n.get("creado") or "")[:10]
            tipo_display = f"{icono} {tipo_n}" + (f" · {estado_n}" if estado_n else "")
            iid = self._btv.insert("", "end",
                values=(tipo_display, ref, preview, tags_str, fecha),
                tags=(tipo_n,))
            self._btv_ids[iid] = n["id"]

    def _bitacora_editar_seleccion(self, event=None):
        """Abre diálogo de edición para la nota seleccionada."""
        sel = self._btv.selection()
        if not sel:
            return
        nota_id = self._btv_ids.get(sel[0])
        if nota_id is None:
            return
        eng = self._bitacora_engine()
        if eng is None:
            return
        nota = eng.obtener(nota_id)
        if not nota:
            return
        # Pre-rellenar formulario de nueva nota y cambiar a ese tab
        self._bvar_tipo.set(nota.get("tipo", "libre"))
        self._bitacora_on_tipo()
        if nota.get("estado"):
            self._bvar_estado.set(nota["estado"])
        self._bvar_ref_num.set(nota.get("ref_numero", ""))
        self._bvar_ref_pag.set(nota.get("ref_pagina", ""))
        self._bvar_tags.set(", ".join(nota.get("etiquetas", [])))
        self._btxt_nota.delete("1.0", "end")
        self._btxt_nota.insert("1.0", nota.get("texto", ""))
        if self._bitacora_win:
            self._bitacora_win._nb.select(0)

    def _bitacora_eliminar_seleccion(self):
        sel = self._btv.selection()
        if not sel:
            return
        if not messagebox.askyesno("Eliminar", "¿Eliminar la nota seleccionada?"):
            return
        eng = self._bitacora_engine()
        if eng is None:
            return
        nota_id = self._btv_ids.get(sel[0])
        if nota_id:
            eng.eliminar(nota_id)
        self._bitacora_refrescar_lista()

    def _bitacora_exportar_md(self):
        from tkinter import filedialog
        dest = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("Texto", "*.txt")],
            initialfile="bitacora_investigacion.md",
            title="Exportar bitácora a Markdown")
        if not dest:
            return
        eng = self._bitacora_engine()
        if eng is None:
            messagebox.showwarning("Sin proyecto", "Abre un proyecto primero.")
            return
        ruta = eng.exportar_markdown(
            Path(dest),
            publicacion=getattr(ST, "publicacion", ""))
        self.toast(f"Bitácora exportada → {Path(dest).name}", tipo="ok")

    def _bitacora_nueva_nota(self, modulo_pid: str = ""):
        """Abre la bitácora y pre-rellena la referencia con el contexto del módulo activo."""
        self._bitacora_abrir()
        if self._bitacora_win is None:
            return
        # Pre-rellenar módulo
        if hasattr(self, "_bvar_modulo"):
            self._bvar_modulo.config(state="normal")
            self._bvar_modulo.set(modulo_pid)
            self._bvar_modulo.config(state="readonly")
        # Pre-rellenar número/página según el módulo
        numero = ""
        pagina = ""
        if modulo_pid == "norm" and hasattr(self, "_norm_var_numero"):
            numero = self._norm_var_numero.get()
            if hasattr(self, "_norm_bloques") and self._norm_idx_actual >= 0:
                try:
                    pagina = self._norm_bloques[self._norm_idx_actual].get("pagina", "")
                except Exception:
                    pass
        elif modulo_pid == "seg" and hasattr(self, "_lbl_seg_n"):
            numero = getattr(ST, "corpus_meta", {}) and ""
        if hasattr(self, "_bvar_ref_num") and numero:
            self._bvar_ref_num.set(numero)
        if hasattr(self, "_bvar_ref_pag") and pagina:
            self._bvar_ref_pag.set(pagina)
        # Traer al frente y seleccionar tab nueva nota
        try:
            self._bitacora_win.lift()
            self._bitacora_win.focus_set()
            self._bitacora_win._nb.select(0)
        except Exception:
            pass
