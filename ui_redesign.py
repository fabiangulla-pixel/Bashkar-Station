"""
Bashkar Station — Desktop UI Redesign
=====================================

Módulo visual independiente para la aplicación de escritorio (Tkinter).

Objetivo
--------
Reproducir, dentro de las limitaciones razonables de Tkinter, el lenguaje visual
del mockup aprobado para Bashkar Station:

- identidad propia, no inspirada visualmente en VS Code;
- dark mode académico con grafito + cobre/ámbar + teal;
- navegación por flujo de investigación;
- pantalla Inicio / Panel de investigación;
- KPIs de corpus;
- pipeline OCR → Normalización → Segmentación → NER → Análisis → Exportación;
- estado offline/local visible;
- acciones siguientes;
- capacidades locales;
- barra de estado inferior;
- componentes reutilizables para extender al resto de módulos.

CÓMO SE INTEGRA (estado real, sesión 56)
----------------------------------------
Este archivo NO sustituye `app.py` y NO importa `core/`: es la capa visual, sin
lógica de negocio, de modo que OCR, NER, segmentación, exportación, bitácora y
el estado existente quedan intactos.

`app.py` lo usa en dos puntos:

1. **La paleta.** `Theme` es la única fuente de verdad de la identidad visual;
   `_PALETA_DARK` / `_PALETA_LIGHT` de `app.py` se derivan de estos tokens, así
   que los 30 paneles heredan la imagen nueva sin tocarlos uno por uno.
2. **El panel Inicio.** `BashkarDesktopShell(..., chrome=False)` se monta dentro
   del área de contenido y aporta solo el tablero (KPIs, flujo, actividad,
   acciones siguientes, capacidades). El chrome real —topbar, activity bar,
   sidebar y barra de estado— lo sigue dibujando `app.py`, que es quien conoce
   los 30 paneles.

    from ui_redesign import (
        BashkarDesktopShell,
        DashboardState,
        BashkarCallbacks,
        state_from_bashkar,
    )

El shell recibe:
1. un `DashboardState` (datos presentacionales);
2. callbacks opcionales para navegación/acciones;
3. puede actualizarse con `shell.set_state(nuevo_estado)`.

`state_from_bashkar(ST)` construye ese `DashboardState` desde el `Estado` real
de `core/estado.py`. Nunca evalúa un DataFrame como booleano: `corpus_meta` y
`df_articulos` SON DataFrames y `bool(df)` lanza ValueError (bug real de la
sesión 43).

Al ejecutarse directamente:
    python ui_redesign.py

abre una PREVISUALIZACIÓN autónoma con datos simulados.

No modifica archivos, no llama APIs, no usa red y no requiere paquetes externos.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence


# ============================================================================
# DESIGN TOKENS
# ============================================================================

class Theme:
    """Sistema visual de Bashkar Station Desktop."""

    # Fondos
    BG = "#0E1114"
    TOPBAR = "#101316"
    SIDEBAR = "#12171B"
    SURFACE = "#171C20"
    SURFACE_2 = "#1C2227"
    SURFACE_HOVER = "#22292F"
    SURFACE_ACTIVE = "#30291F"
    BORDER = "#2A3238"
    BORDER_SOFT = "#22292E"

    # Texto
    TEXT = "#E8E5DF"
    TEXT_2 = "#B5B6B3"
    TEXT_3 = "#777F84"
    TEXT_MUTED = "#646D72"

    # Identidad
    COPPER = "#D58B45"
    COPPER_2 = "#B96F32"
    AMBER = "#E6A64C"
    TEAL = "#62C6B5"
    BLUE = "#6CA8E8"
    GREEN = "#6EC69A"
    PURPLE = "#B18AD6"
    RED = "#D96B6B"

    # Estados
    READY_BG = "#15251F"
    READY_FG = "#75D2A5"
    INFO_BG = "#14202A"
    INFO_FG = "#75B9EC"
    WARN_BG = "#2A2116"
    WARN_FG = "#E5AD5A"
    DISABLED_BG = "#202226"
    DISABLED_FG = "#9B9FA3"

    # Tipografía
    FONT_UI = "Segoe UI"
    FONT_DISPLAY = "Georgia"
    FONT_MONO = "Consolas"

    # Escala
    RADIUS = 12      # conceptual; Tkinter estándar no redondea frames
    PAD = 16
    GAP = 12


# Nombre del token → clave equivalente en las paletas de app.py.
_EQUIVALENCIAS_PALETA = {
    "BG": "CONTENT_BG",       "TOPBAR": "TOPBAR_BG",   "SIDEBAR": "SB_BG",
    "SURFACE": "CARD_BG",     "SURFACE_2": "AZ2",      "SURFACE_HOVER": "SB_HOV",
    "SURFACE_ACTIVE": "SB_SEL", "BORDER": "CARD_BOR",  "BORDER_SOFT": "CARD_BOR",
    "TEXT": "TXT_PRI",        "TEXT_2": "SB_TXT",      "TEXT_3": "TXT_SEC",
    "TEXT_MUTED": "TXT_DIM",  "COPPER": "AZ3",         "COPPER_2": "AZ3",
    "AMBER": "AZ4",           "TEAL": "TEAL",          "BLUE": "AZ_INFO",
    "GREEN": "VERDE",         "PURPLE": "PURPURA",     "RED": "ROJO",
    "READY_BG": "READY_BG",   "READY_FG": "VERDE",
    "INFO_BG": "INFO_BG",     "INFO_FG": "AZ_INFO",
    "WARN_BG": "WARN_BG",     "WARN_FG": "ACENT",
    "DISABLED_BG": "AZ2",     "DISABLED_FG": "TXT_DIM",
}


def aplicar_tema(paleta: Mapping[str, str]) -> None:
    """
    Reescribe los tokens con la paleta activa de `app.py` (claro u oscuro).

    `Theme` es un registro de tokens, y esto es exactamente lo que significa
    cambiar de tema: los mismos nombres, otros valores. Quien lo llame debe
    reconstruir el tablero después (`shell.set_state(...)`), porque los widgets
    ya creados conservan el color con el que se pintaron.
    """
    for token, clave in _EQUIVALENCIAS_PALETA.items():
        valor = paleta.get(clave)
        if valor:
            setattr(Theme, token, valor)


# ============================================================================
# DATA MODEL
# ============================================================================

@dataclass
class PipelineStep:
    key: str
    label: str
    status: str = "pending"  # completed | active | pending | warning


@dataclass
class Capability:
    name: str
    detail: str = ""
    enabled: bool = True
    version: str = ""


@dataclass
class RecentActivity:
    title: str
    detail: str = ""
    when: str = ""
    kind: str = "info"  # ok | info | warning | export


@dataclass
class NextAction:
    title: str
    detail: str = ""
    target: str = ""
    kind: str = "warning"


@dataclass
class DashboardState:
    project_name: str = "Sin proyecto"
    publication: str = "Bashkar Station"
    period: str = ""
    description: str = (
        "Plataforma local para el análisis computacional de publicaciones "
        "periódicas históricas."
    )

    pages_processed: int = 0
    pages_total: int = 0
    ocr_quality: float | None = None
    articles: int = 0
    entities: int = 0

    current_number: str = ""
    current_year: str = ""
    current_date: str = ""
    current_section: str = ""
    current_page: str = ""

    local_mode: bool = True
    external_ai_enabled: bool = False
    system_ready: bool = True
    free_storage_text: str = ""

    pipeline: list[PipelineStep] = field(default_factory=lambda: [
        PipelineStep("ocr", "OCR", "pending"),
        PipelineStep("norm", "Normalización", "pending"),
        PipelineStep("seg", "Segmentación", "pending"),
        PipelineStep("ner", "NER", "pending"),
        PipelineStep("anal", "Análisis", "pending"),
        PipelineStep("export", "Exportación", "pending"),
    ])

    recent_activity: list[RecentActivity] = field(default_factory=list)
    next_actions: list[NextAction] = field(default_factory=list)
    capabilities: list[Capability] = field(default_factory=list)


@dataclass
class BashkarCallbacks:
    """Puntos de integración con BashkarApp."""

    navigate: Callable[[str], None] | None = None
    save_project: Callable[[], None] | None = None
    edit_project: Callable[[], None] | None = None
    open_projects: Callable[[], None] | None = None
    open_corpus_viewer: Callable[[], None] | None = None
    toggle_external_ai: Callable[[], None] | None = None
    open_settings: Callable[[], None] | None = None
    action_selected: Callable[[str], None] | None = None


# ============================================================================
# BEST-EFFORT ADAPTER FROM CURRENT BASHKAR STATE
# ============================================================================

def _safe_len(value: Any) -> int:
    """Longitud tolerante: None → 0, DataFrame → nº de filas, nunca lanza."""
    if value is None:
        return 0
    try:
        return len(value)
    except Exception:
        return 0


def _texto(value: Any, default: str = "") -> str:
    """
    str() tolerante que NUNCA evalúa el valor como booleano.

    Existe porque `ST.corpus_meta` y `ST.df_articulos` son DataFrames y
    `bool(df)` / `df in (None, "")` lanzan ValueError (bug real de la sesión 43).
    """
    if value is None:
        return default
    try:
        s = str(value).strip()
    except Exception:
        return default
    return s or default


def _normalize_stage_status(value: Any) -> str:
    """Traduce los semáforos de `Estado.estado_etapas` al vocabulario del panel."""
    v = str(value or "").strip().lower()
    if v in {"ready", "done", "completed", "complete", "ok", "listo", "completado"}:
        return "completed"
    if v in {"running", "active", "working", "en_progreso", "en progreso"}:
        return "active"
    if v in {"stale", "warning", "warn", "attention", "revisar"}:
        # "stale" = la etapa se completó pero una anterior cambió: hay que
        # rehacerla. En el tablero es un aviso, no un logro.
        return "warning"
    return "pending"


def _calidad_ocr(st: Any) -> float | None:
    """
    Confianza media del OCR en porcentaje (0-100), o None si no hay dato.

    Dos fuentes, en orden: la columna `confianza` de `corpus_meta` (por página,
    ya en escala 0-100) y `resumen_ocr["confianza_media"]` (fracción 0-1).
    """
    meta = getattr(st, "corpus_meta", None)
    try:
        if meta is not None and hasattr(meta, "columns") and "confianza" in meta.columns:
            serie = meta["confianza"].dropna()
            if len(serie):
                return float(serie.mean())
    except Exception:
        pass
    resumen = getattr(st, "resumen_ocr", None)
    if isinstance(resumen, Mapping):
        try:
            return float(resumen.get("confianza_media", 0)) * 100.0
        except Exception:
            return None
    return None


def state_from_bashkar(st: Any) -> DashboardState:
    """
    Construye un `DashboardState` desde el `Estado` real de `core/estado.py`.

    Solo lee; no toca disco, red ni widgets, así que puede llamarse desde un
    hilo worker o desde el hilo de Tk indistintamente.
    """
    publicacion = _texto(getattr(st, "publicacion", None), "Sin proyecto")
    periodo = _texto(getattr(st, "periodo", None))

    corpus_txt = getattr(st, "corpus_txt", None) or []
    corpus_meta = getattr(st, "corpus_meta", None)

    # El total de páginas lo manda `corpus_meta` (una fila por página del
    # corpus); `corpus_txt` son las que ya tienen texto disponible.
    paginas_total = _safe_len(corpus_meta) or _safe_len(corpus_txt)
    paginas_procesadas = sum(1 for t in corpus_txt if _texto(t))
    if not paginas_procesadas and _safe_len(corpus_txt):
        paginas_procesadas = _safe_len(corpus_txt)

    articulos = _safe_len(getattr(st, "df_articulos", None))

    indice_ner = getattr(st, "indice_ner_global", None)
    entidades = 0
    if isinstance(indice_ner, Mapping):
        entidades = sum(_safe_len(v) for v in indice_ner.values())

    etapas = getattr(st, "estado_etapas", None)
    if not isinstance(etapas, Mapping):
        etapas = {}

    def _estado_de(clave: str) -> str:
        return _normalize_stage_status(etapas.get(clave))

    # NER y Exportación no viven en `estado_etapas` (que solo cubre el flujo
    # etz→ocr→norm→seg→anal): se deducen de los artefactos ya producidos.
    ner_listo = bool(getattr(st, "ner_done", False)) or entidades > 0
    exportado = any(
        _texto(getattr(st, attr, None))
        for attr in ("xlsx_path", "graph_path", "pptx_path")
    )

    pipeline = [
        PipelineStep("ocr", "OCR", _estado_de("ocr")),
        PipelineStep("norm", "Normalización", _estado_de("norm")),
        PipelineStep("seg", "Segmentación", _estado_de("seg")),
        PipelineStep("ner", "NER", "completed" if ner_listo else "pending"),
        PipelineStep("anal", "Análisis", _estado_de("anal")),
        PipelineStep("export", "Exportación", "completed" if exportado else "pending"),
    ]

    return DashboardState(
        project_name=publicacion,
        publication=publicacion,
        period=periodo,
        pages_processed=paginas_procesadas,
        pages_total=paginas_total,
        ocr_quality=_calidad_ocr(st),
        articles=articulos,
        entities=entidades,
        local_mode=not bool(getattr(st, "ia_habilitada", False)),
        external_ai_enabled=bool(getattr(st, "ia_habilitada", False)),
        system_ready=True,
        pipeline=pipeline,
        capabilities=[],
    )


# ============================================================================
# LOW-LEVEL WIDGET HELPERS
# ============================================================================

def _clear(widget: tk.Misc) -> None:
    for child in widget.winfo_children():
        child.destroy()


def _label(
    parent: tk.Misc,
    text: str,
    *,
    fg: str = Theme.TEXT,
    bg: str | None = None,
    font: tuple = (Theme.FONT_UI, 10),
    anchor: str = "w",
    **kwargs: Any,
) -> tk.Label:
    if bg is None:
        bg = parent.cget("bg") if "bg" in parent.keys() else Theme.BG
    return tk.Label(
        parent,
        text=text,
        fg=fg,
        bg=bg,
        font=font,
        anchor=anchor,
        **kwargs,
    )


def _separator(parent: tk.Misc, *, vertical: bool = False) -> tk.Frame:
    return tk.Frame(
        parent,
        bg=Theme.BORDER_SOFT,
        width=1 if vertical else 10,
        height=10 if vertical else 1,
    )


class HoverButton(tk.Label):
    """Botón visual ligero construido con Label para control total del color."""

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command: Callable[[], None] | None = None,
        *,
        bg: str | None = None,
        hover_bg: str | None = None,
        fg: str | None = None,
        active_fg: str | None = None,
        font: tuple | None = None,
        padx: int = 12,
        pady: int = 7,
        border: bool = True,
        **kwargs: Any,
    ):
        # Los colores se resuelven AQUÍ, no en la firma: un valor por defecto se
        # evalúa al definir la clase, y entonces `aplicar_tema` no lo alcanzaría
        # nunca (el botón seguiría en modo oscuro con el tema claro puesto).
        bg = bg or Theme.SURFACE_2
        hover_bg = hover_bg or Theme.SURFACE_HOVER
        fg = fg or Theme.TEXT_2
        active_fg = active_fg or Theme.TEXT
        font = font or (Theme.FONT_UI, 9)
        super().__init__(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=font,
            cursor="hand2",
            padx=padx,
            pady=pady,
            relief="solid" if border else "flat",
            bd=1 if border else 0,
            highlightthickness=0,
            **kwargs,
        )
        self._normal_bg = bg
        self._hover_bg = hover_bg
        self._normal_fg = fg
        self._active_fg = active_fg
        self._command = command
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._click)

    def _enter(self, _event: tk.Event) -> None:
        self.configure(bg=self._hover_bg, fg=self._active_fg)

    def _leave(self, _event: tk.Event) -> None:
        self.configure(bg=self._normal_bg, fg=self._normal_fg)

    def _click(self, _event: tk.Event) -> None:
        if self._command:
            self._command()


class Card(tk.Frame):
    """Superficie reutilizable."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        bg: str | None = None,
        padx: int = 16,
        pady: int = 14,
        **kwargs: Any,
    ):
        super().__init__(
            parent,
            bg=bg or Theme.SURFACE,
            padx=padx,
            pady=pady,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
            highlightcolor=Theme.BORDER_SOFT,
            **kwargs,
        )


class StatusPill(tk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        *,
        fg: str,
        bg: str,
        symbol: str = "●",
    ):
        super().__init__(
            parent,
            bg=bg,
            padx=9,
            pady=4,
            highlightthickness=1,
            highlightbackground=Theme.BORDER,
        )
        _label(
            self,
            f"{symbol}  {text}",
            fg=fg,
            bg=bg,
            font=(Theme.FONT_UI, 8),
        ).pack()


class MetricCard(Card):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        title: str,
        value: str,
        detail: str,
        accent: str,
        symbol: str = "◆",
        progress: float | None = None,
    ):
        super().__init__(parent, padx=14, pady=12)
        top = tk.Frame(self, bg=Theme.SURFACE)
        top.pack(fill="x")
        _label(
            top,
            symbol,
            fg=accent,
            bg=Theme.SURFACE,
            font=(Theme.FONT_UI, 15, "bold"),
        ).pack(side="left")
        _label(
            top,
            title.upper(),
            fg=Theme.TEXT_3,
            bg=Theme.SURFACE,
            font=(Theme.FONT_UI, 7, "bold"),
            justify="left",
        ).pack(side="left", padx=(8, 0))

        _label(
            self,
            value,
            fg=Theme.TEXT,
            bg=Theme.SURFACE,
            font=(Theme.FONT_DISPLAY, 20),
        ).pack(anchor="w", pady=(8, 0))
        _label(
            self,
            detail,
            fg=Theme.TEXT_3,
            bg=Theme.SURFACE,
            font=(Theme.FONT_UI, 8),
        ).pack(anchor="w", pady=(2, 0))

        if progress is not None:
            progress = max(0.0, min(1.0, float(progress)))
            bar = tk.Canvas(
                self,
                height=5,
                bg=Theme.SURFACE,
                bd=0,
                highlightthickness=0,
            )
            bar.pack(fill="x", pady=(10, 0))

            def redraw(_event: tk.Event | None = None) -> None:
                bar.delete("all")
                width = max(4, bar.winfo_width())
                bar.create_rectangle(
                    0, 1, width, 4,
                    fill=Theme.SURFACE_HOVER,
                    outline="",
                )
                bar.create_rectangle(
                    0, 1, width * progress, 4,
                    fill=accent,
                    outline="",
                )
            bar.bind("<Configure>", redraw)


# ============================================================================
# MAIN SHELL
# ============================================================================

class BashkarDesktopShell(tk.Frame):
    """
    Nueva capa visual para Bashkar Station.

    NO crea una nueva ventana raíz: se monta dentro de una ventana ya existente.
    Esto facilita que Claude Code la integre dentro de BashkarApp(tk.Tk).
    """

    NAV_SECTIONS = [
        ("", [
            ("home", "⌂", "Inicio"),
            ("projects", "□", "Proyectos"),
        ]),
        ("PREPARACIÓN", [
            ("ocr", "▣", "OCR"),
            ("norm", "A", "Normalizar"),
            ("seg", "▦", "Segmentar"),
        ]),
        ("ANÁLISIS", [
            ("ner", "♙", "Entidades"),
            ("anal", "◫", "Léxico"),
            ("red", "⌘", "Redes"),
        ]),
        ("PUBLICACIÓN", [
            ("res", "▥", "Resultados"),
            ("export", "⇧", "Exportar"),
        ]),
    ]

    def __init__(
        self,
        parent: tk.Misc,
        state: DashboardState | None = None,
        callbacks: BashkarCallbacks | None = None,
        *,
        version: str = "",
        chrome: bool = True,
    ):
        """
        `chrome=True`  → shell completo (topbar + sidebar + tablero + estado);
                         es lo que abre la previsualización autónoma.
        `chrome=False` → solo el tablero, para montarlo como panel «Inicio»
                         dentro de la ventana de `app.py`, que ya dibuja su
                         propio chrome con los 30 paneles reales.
        """
        super().__init__(parent, bg=Theme.BG)
        self.state = state or DashboardState()
        self.callbacks = callbacks or BashkarCallbacks()
        self.version = version
        self.chrome = chrome
        self.active_nav = "home"
        self._nav_rows: dict[str, dict[str, tk.Widget]] = {}

        self.pack_propagate(False)
        self._build_shell()
        self.set_state(self.state)

    # ----------------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------------

    def set_state(self, state: DashboardState) -> None:
        self.state = state
        self._refresh_topbar()
        self._refresh_dashboard()
        self._refresh_statusbar()

    def select_navigation(self, key: str, *, invoke: bool = False) -> None:
        self.active_nav = key
        self._paint_nav()
        if invoke and self.callbacks.navigate:
            self.callbacks.navigate(key)

    # ----------------------------------------------------------------------
    # Layout
    # ----------------------------------------------------------------------

    def _build_shell(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        if not self.chrome:
            # Montado dentro de app.py: el tablero ocupa todo el frame.
            # La fila 1 (el cuerpo cuando hay chrome) se queda sin peso; con
            # peso se llevaba media ventana vacía y recortaba las tarjetas de
            # abajo.
            self.grid_rowconfigure(0, weight=1)
            self.grid_rowconfigure(1, weight=0)
            self.grid_columnconfigure(0, weight=1)
            self.topbar = None
            self.sidebar = None
            self.statusbar = None
            self.content = tk.Frame(self, bg=Theme.BG)
            self.content.grid(row=0, column=0, columnspan=2, sticky="nsew")
            self.content.grid_rowconfigure(0, weight=1)
            self.content.grid_columnconfigure(0, weight=1)
            self._build_dashboard_area()
            return

        self.topbar = tk.Frame(
            self,
            bg=Theme.TOPBAR,
            height=70,
            highlightthickness=0,
        )
        self.topbar.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.topbar.grid_propagate(False)

        self.sidebar = tk.Frame(
            self,
            bg=Theme.SIDEBAR,
            width=220,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        )
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        self.content = tk.Frame(self, bg=Theme.BG)
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.statusbar = tk.Frame(
            self,
            bg=Theme.TOPBAR,
            height=34,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        )
        self.statusbar.grid(row=2, column=0, columnspan=2, sticky="nsew")
        self.statusbar.grid_propagate(False)

        self._build_topbar()
        self._build_sidebar()
        self._build_dashboard_area()

    def _build_dashboard_area(self) -> None:
        """Canvas desplazable donde se pinta el tablero."""
        self.dashboard_outer = tk.Frame(self.content, bg=Theme.BG)
        self.dashboard_outer.grid(row=0, column=0, sticky="nsew")
        self.dashboard_outer.grid_rowconfigure(0, weight=1)
        self.dashboard_outer.grid_columnconfigure(0, weight=1)

        self.dashboard_canvas = tk.Canvas(
            self.dashboard_outer,
            bg=Theme.BG,
            highlightthickness=0,
            bd=0,
        )
        self.dashboard_canvas.grid(row=0, column=0, sticky="nsew")

        self.dashboard_scroll = tk.Scrollbar(
            self.dashboard_outer,
            orient="vertical",
            command=self.dashboard_canvas.yview,
        )
        self.dashboard_scroll.grid(row=0, column=1, sticky="ns")
        self.dashboard_canvas.configure(yscrollcommand=self.dashboard_scroll.set)

        self.dashboard = tk.Frame(self.dashboard_canvas, bg=Theme.BG)
        self._dashboard_window = self.dashboard_canvas.create_window(
            (0, 0), window=self.dashboard, anchor="nw"
        )
        self.dashboard.bind("<Configure>", self._dashboard_configure)
        self.dashboard_canvas.bind("<Configure>", self._canvas_configure)
        # Rueda del ratón widget a widget, NUNCA con bind_all: dentro de app.py
        # un bind global se robaría el scroll de los otros 30 paneles (misma
        # razón por la que `_hacer_scrollable` de app.py lo evita).
        self._bind_wheel(self.dashboard_canvas)

    def _bind_wheel(self, widget: tk.Misc) -> None:
        """Propaga la rueda del ratón al canvas en el widget y sus hijos."""
        try:
            widget.bind("<MouseWheel>", self._mousewheel)
            widget.bind("<Button-4>", self._mousewheel)
            widget.bind("<Button-5>", self._mousewheel)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._bind_wheel(child)

    def _dashboard_configure(self, _event: tk.Event) -> None:
        self.dashboard_canvas.configure(
            scrollregion=self.dashboard_canvas.bbox("all")
        )

    def _canvas_configure(self, event: tk.Event) -> None:
        self.dashboard_canvas.itemconfigure(
            self._dashboard_window,
            width=event.width,
        )

    def _mousewheel(self, event: tk.Event) -> None:
        if not self.winfo_exists():
            return
        delta = getattr(event, "delta", 0)
        if delta:
            pasos = int(-delta / 120) or (-1 if delta > 0 else 1)
        else:  # X11: Button-4 (arriba) / Button-5 (abajo)
            pasos = -1 if getattr(event, "num", 5) == 4 else 1
        self.dashboard_canvas.yview_scroll(pasos, "units")

    # ----------------------------------------------------------------------
    # Topbar
    # ----------------------------------------------------------------------

    def _build_topbar(self) -> None:
        left = tk.Frame(self.topbar, bg=Theme.TOPBAR)
        left.pack(side="left", fill="y", padx=(18, 8))

        brand = tk.Frame(left, bg=Theme.TOPBAR)
        brand.pack(side="left", pady=11)

        _label(
            brand,
            "B",
            fg=Theme.COPPER,
            bg=Theme.TOPBAR,
            font=(Theme.FONT_DISPLAY, 25, "bold"),
        ).pack(side="left", padx=(0, 8))
        brand_txt = tk.Frame(brand, bg=Theme.TOPBAR)
        brand_txt.pack(side="left")
        _label(
            brand_txt,
            "BASHKAR STATION",
            fg=Theme.TEXT,
            bg=Theme.TOPBAR,
            font=(Theme.FONT_DISPLAY, 12, "bold"),
        ).pack(anchor="w")
        _label(
            brand_txt,
            "Plataforma de análisis editorial",
            fg=Theme.TEXT_3,
            bg=Theme.TOPBAR,
            font=(Theme.FONT_UI, 7),
        ).pack(anchor="w")

        _separator(left, vertical=True).pack(
            side="left", fill="y", padx=18, pady=15
        )

        self.project_header = tk.Frame(left, bg=Theme.TOPBAR)
        self.project_header.pack(side="left", pady=14)
        self.lbl_project = _label(
            self.project_header,
            "",
            fg=Theme.TEXT,
            bg=Theme.TOPBAR,
            font=(Theme.FONT_DISPLAY, 12),
        )
        self.lbl_project.pack(anchor="w")

        right = tk.Frame(self.topbar, bg=Theme.TOPBAR)
        right.pack(side="right", fill="y", padx=16)

        self.top_statuses = tk.Frame(right, bg=Theme.TOPBAR)
        self.top_statuses.pack(side="left", pady=17, padx=(0, 10))

        self.btn_save = HoverButton(
            right,
            "Guardar proyecto",
            self.callbacks.save_project,
            bg=Theme.TOPBAR,
            hover_bg=Theme.SURFACE_HOVER,
            fg=Theme.AMBER,
            border=True,
        )
        self.btn_save.pack(side="right", pady=16)

    def _refresh_topbar(self) -> None:
        if not self.chrome:
            return
        title = self.state.publication or self.state.project_name
        if self.state.period:
            title = f"{title} · {self.state.period}"
        self.lbl_project.configure(text=title or "Sin proyecto")

        _clear(self.top_statuses)

        if self.state.local_mode:
            StatusPill(
                self.top_statuses,
                "Modo local",
                fg=Theme.GREEN,
                bg=Theme.READY_BG,
                symbol="●",
            ).pack(side="left", padx=4)

        StatusPill(
            self.top_statuses,
            "Offline-first",
            fg=Theme.BLUE,
            bg=Theme.INFO_BG,
            symbol="◆",
        ).pack(side="left", padx=4)

        if self.state.external_ai_enabled:
            StatusPill(
                self.top_statuses,
                "IA externa activa",
                fg=Theme.WARN_FG,
                bg=Theme.WARN_BG,
                symbol="●",
            ).pack(side="left", padx=4)
        else:
            StatusPill(
                self.top_statuses,
                "IA externa desactivada",
                fg=Theme.DISABLED_FG,
                bg=Theme.DISABLED_BG,
                symbol="×",
            ).pack(side="left", padx=4)

    # ----------------------------------------------------------------------
    # Sidebar
    # ----------------------------------------------------------------------

    def _build_sidebar(self) -> None:
        nav = tk.Frame(self.sidebar, bg=Theme.SIDEBAR)
        nav.pack(fill="both", expand=True, padx=10, pady=(12, 0))

        for section, items in self.NAV_SECTIONS:
            if section:
                _label(
                    nav,
                    section,
                    fg=Theme.COPPER,
                    bg=Theme.SIDEBAR,
                    font=(Theme.FONT_UI, 7, "bold"),
                ).pack(fill="x", padx=10, pady=(14, 6))

            for key, icon, text in items:
                row = tk.Frame(
                    nav,
                    bg=Theme.SIDEBAR,
                    height=38,
                    cursor="hand2",
                )
                row.pack(fill="x", pady=1)
                row.pack_propagate(False)

                ind = tk.Frame(row, width=3, bg=Theme.SIDEBAR)
                ind.pack(side="left", fill="y")

                ico = _label(
                    row,
                    icon,
                    fg=Theme.TEXT_3,
                    bg=Theme.SIDEBAR,
                    font=(Theme.FONT_UI, 13),
                    width=3,
                    anchor="center",
                )
                ico.pack(side="left")

                txt = _label(
                    row,
                    text,
                    fg=Theme.TEXT_2,
                    bg=Theme.SIDEBAR,
                    font=(Theme.FONT_UI, 9),
                )
                txt.pack(side="left", padx=(5, 0))

                self._nav_rows[key] = {
                    "row": row,
                    "ind": ind,
                    "ico": ico,
                    "txt": txt,
                }
                for w in (row, ind, ico, txt):
                    w.bind("<Button-1>", lambda _e, k=key: self._nav_click(k))
                    w.bind("<Enter>", lambda _e, k=key: self._nav_hover(k, True))
                    w.bind("<Leave>", lambda _e, k=key: self._nav_hover(k, False))

        footer = tk.Frame(self.sidebar, bg=Theme.SIDEBAR)
        footer.pack(fill="x", side="bottom", padx=14, pady=14)
        _separator(footer).pack(fill="x", pady=(0, 10))

        row = tk.Frame(footer, bg=Theme.SIDEBAR)
        row.pack(fill="x")
        _label(
            row,
            "B",
            fg=Theme.COPPER,
            bg=Theme.SIDEBAR,
            font=(Theme.FONT_DISPLAY, 14, "bold"),
        ).pack(side="left")
        ftxt = tk.Frame(row, bg=Theme.SIDEBAR)
        ftxt.pack(side="left", padx=(8, 0))
        _label(
            ftxt,
            "Bashkar Station",
            fg=Theme.TEXT_2,
            bg=Theme.SIDEBAR,
            font=(Theme.FONT_UI, 8),
        ).pack(anchor="w")
        version = f"v{self.version} · Local" if self.version else "Local"
        _label(
            ftxt,
            version,
            fg=Theme.TEXT_3,
            bg=Theme.SIDEBAR,
            font=(Theme.FONT_UI, 7),
        ).pack(anchor="w")
        self.footer_ready = _label(
            row,
            "●",
            fg=Theme.GREEN,
            bg=Theme.SIDEBAR,
            font=(Theme.FONT_UI, 9),
        )
        self.footer_ready.pack(side="right")

        self._paint_nav()

    def _nav_click(self, key: str) -> None:
        self.select_navigation(key)
        if self.callbacks.navigate:
            self.callbacks.navigate(key)
        else:
            # En modo preview, Inicio es la única vista implementada.
            if key != "home":
                self._show_preview_notice(key)

    def _nav_hover(self, key: str, on: bool) -> None:
        if key == self.active_nav:
            return
        widgets = self._nav_rows.get(key)
        if not widgets:
            return
        bg = Theme.SURFACE_HOVER if on else Theme.SIDEBAR
        for name in ("row", "ind", "ico", "txt"):
            widgets[name].configure(bg=bg)
        widgets["txt"].configure(fg=Theme.TEXT if on else Theme.TEXT_2)
        widgets["ico"].configure(fg=Theme.TEXT_2 if on else Theme.TEXT_3)

    def _paint_nav(self) -> None:
        for key, widgets in self._nav_rows.items():
            active = key == self.active_nav
            bg = Theme.SURFACE_ACTIVE if active else Theme.SIDEBAR
            for name in ("row", "ico", "txt"):
                widgets[name].configure(bg=bg)
            widgets["ind"].configure(
                bg=Theme.COPPER if active else Theme.SIDEBAR
            )
            widgets["txt"].configure(
                fg=Theme.AMBER if active else Theme.TEXT_2
            )
            widgets["ico"].configure(
                fg=Theme.AMBER if active else Theme.TEXT_3
            )

    # ----------------------------------------------------------------------
    # Dashboard
    # ----------------------------------------------------------------------

    def _refresh_dashboard(self) -> None:
        _clear(self.dashboard)
        self.active_nav = "home"
        self._paint_nav()

        self.dashboard.grid_columnconfigure(0, weight=1)

        wrapper = tk.Frame(self.dashboard, bg=Theme.BG)
        wrapper.pack(fill="both", expand=True, padx=24, pady=20)

        # Header
        header = tk.Frame(wrapper, bg=Theme.BG)
        header.pack(fill="x", pady=(0, 12))
        left = tk.Frame(header, bg=Theme.BG)
        left.pack(side="left")

        _label(
            left,
            "Panel de investigación",
            fg=Theme.TEXT,
            bg=Theme.BG,
            font=(Theme.FONT_DISPLAY, 22),
        ).pack(anchor="w")
        _label(
            left,
            "Tu estación local para el análisis computacional de publicaciones periódicas históricas.",
            fg=Theme.TEXT_3,
            bg=Theme.BG,
            font=(Theme.FONT_UI, 9),
        ).pack(anchor="w", pady=(3, 0))

        HoverButton(
            header,
            "Editar proyecto",
            self.callbacks.edit_project,
            bg=Theme.BG,
            hover_bg=Theme.SURFACE_HOVER,
            fg=Theme.TEXT_2,
        ).pack(side="right", pady=4)

        # Hero + indicadores. Los cuatro indicadores van en una rejilla 2×2 a la
        # derecha del hero, no en una sola fila: en fila única, con una ventana
        # de 1280 px —el mínimo que admite la app— el cuarto quedaba cortado.
        upper = tk.Frame(wrapper, bg=Theme.BG)
        upper.pack(fill="x", pady=(0, Theme.GAP))
        # minsize: los pesos solo reparten el espacio SOBRANTE, y los cuatro
        # indicadores piden bastante ancho; sin un mínimo, el hero se quedaba
        # en una columna de 160 px con el texto cortado.
        upper.grid_columnconfigure(0, weight=2, minsize=310)
        upper.grid_columnconfigure(1, weight=3)

        hero = Card(upper, padx=16, pady=14)
        hero.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        _label(
            hero,
            self._project_display_name(),
            fg=Theme.TEXT,
            bg=Theme.SURFACE,
            font=(Theme.FONT_DISPLAY, 15),
        ).pack(anchor="w")
        descripcion = _label(
            hero,
            self.state.description,
            fg=Theme.TEXT_2,
            bg=Theme.SURFACE,
            font=(Theme.FONT_UI, 8),
            justify="left",
            wraplength=300,
        )
        descripcion.pack(anchor="w", pady=(7, 10))
        privacy = tk.Frame(hero, bg=Theme.SURFACE)
        privacy.pack(fill="x")
        _label(
            privacy,
            "◇",
            fg=Theme.TEAL,
            bg=Theme.SURFACE,
            font=(Theme.FONT_UI, 14, "bold"),
        ).pack(side="left")
        privacidad = _label(
            privacy,
            "Todo el procesamiento se realiza en tu equipo. "
            "Tus datos permanecen privados y bajo tu control.",
            fg=Theme.TEAL,
            bg=Theme.SURFACE,
            font=(Theme.FONT_UI, 8),
            justify="left",
            wraplength=280,
        )
        privacidad.pack(side="left", padx=(7, 0))

        # El texto se reajusta al ancho real de la tarjeta: con un wraplength
        # fijo, una ventana estrecha cortaba las frases a media palabra.
        def _reajustar(evento: tk.Event) -> None:
            # evento.width incluye el padding de la tarjeta (16 a cada lado) y
            # el borde; la línea de privacidad además va detrás del rombo.
            ancho = max(150, evento.width - 40)
            descripcion.configure(wraplength=ancho)
            privacidad.configure(wraplength=max(120, ancho - 34))

        hero.bind("<Configure>", _reajustar)

        pages_pct = (
            self.state.pages_processed / self.state.pages_total
            if self.state.pages_total
            else 0
        )
        metrics = [
            (
                "Páginas\nprocesadas",
                f"{self.state.pages_processed:,}".replace(",", "."),
                f"de {self.state.pages_total:,}".replace(",", ".")
                if self.state.pages_total
                else "sin total definido",
                Theme.AMBER,
                "▤",
                pages_pct,
            ),
            (
                "Calidad OCR",
                f"{self.state.ocr_quality:.1f}%".replace(".", ",")
                if self.state.ocr_quality is not None
                else "—",
                "Confianza media",
                Theme.TEAL,
                "A",
                None,
            ),
            (
                "Artículos\ndetectados",
                f"{self.state.articles:,}".replace(",", "."),
                "Segmentación actual",
                Theme.BLUE,
                "▣",
                None,
            ),
            (
                "Entidades\nreconocidas",
                f"{self.state.entities:,}".replace(",", "."),
                "Personas, org. y lugares",
                Theme.COPPER,
                "♙",
                None,
            ),
        ]
        rejilla = tk.Frame(upper, bg=Theme.BG)
        rejilla.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        rejilla.grid_columnconfigure(0, weight=1, uniform="metricas")
        rejilla.grid_columnconfigure(1, weight=1, uniform="metricas")

        for idx, (title, value, detail, accent, symbol, progress) in enumerate(metrics):
            card = MetricCard(
                rejilla,
                title=title,
                value=value,
                detail=detail,
                accent=accent,
                symbol=symbol,
                progress=progress,
            )
            fila, col = divmod(idx, 2)
            card.grid(
                row=fila,
                column=col,
                sticky="nsew",
                padx=(0 if col == 0 else 5, 0),
                pady=(0 if fila == 0 else 6, 0),
            )

        # Middle
        middle = tk.Frame(wrapper, bg=Theme.BG)
        middle.pack(fill="x", pady=(0, Theme.GAP))
        middle.grid_columnconfigure(0, weight=3)
        middle.grid_columnconfigure(1, weight=2)

        pipeline = self._build_pipeline_card(middle)
        pipeline.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        activity = self._build_activity_card(middle)
        activity.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        # Bottom
        lower = tk.Frame(wrapper, bg=Theme.BG)
        lower.pack(fill="x")
        lower.grid_columnconfigure(0, weight=2)
        lower.grid_columnconfigure(1, weight=2)
        lower.grid_columnconfigure(2, weight=2)

        corpus = self._build_corpus_card(lower)
        corpus.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        actions = self._build_actions_card(lower)
        actions.grid(row=0, column=1, sticky="nsew", padx=6)

        caps = self._build_capabilities_card(lower)
        caps.grid(row=0, column=2, sticky="nsew", padx=(6, 0))

        # El tablero se reconstruye entero en cada refresco: hay que volver a
        # enganchar la rueda del ratón a los widgets recién creados.
        self._bind_wheel(self.dashboard)

    def _project_display_name(self) -> str:
        name = self.state.publication or self.state.project_name or "Sin proyecto"
        if self.state.period:
            name += f" · {self.state.period}"
        return name

    def _build_pipeline_card(self, parent: tk.Misc) -> Card:
        card = Card(parent, padx=16, pady=14)
        _label(
            card,
            "Flujo de trabajo",
            fg=Theme.TEXT,
            bg=Theme.SURFACE,
            font=(Theme.FONT_DISPLAY, 13),
        ).pack(anchor="w")
        _label(
            card,
            "Estado del pipeline de análisis",
            fg=Theme.TEXT_3,
            bg=Theme.SURFACE,
            font=(Theme.FONT_UI, 8),
        ).pack(anchor="w", pady=(2, 12))

        flow = tk.Frame(card, bg=Theme.SURFACE)
        flow.pack(fill="x")
        steps = self.state.pipeline or []

        for i, step in enumerate(steps):
            block = tk.Frame(flow, bg=Theme.SURFACE)
            block.pack(side="left", expand=True, fill="x")

            if step.status == "completed":
                accent = Theme.GREEN
                symbol = "✓"
                status_txt = "Completado"
            elif step.status == "active":
                accent = Theme.AMBER
                symbol = "●"
                status_txt = "En progreso"
            elif step.status == "warning":
                accent = Theme.RED
                symbol = "!"
                status_txt = "Revisar"
            else:
                accent = Theme.TEXT_MUTED
                symbol = "○"
                status_txt = "Pendiente"

            badge = tk.Label(
                block,
                text=symbol,
                width=3,
                height=1,
                bg=Theme.SURFACE_2,
                fg=accent,
                font=(Theme.FONT_UI, 14, "bold"),
                relief="solid",
                bd=1,
            )
            badge.pack(pady=(0, 5))
            _label(
                block,
                step.label,
                fg=Theme.TEXT_2,
                bg=Theme.SURFACE,
                font=(Theme.FONT_UI, 8),
                anchor="center",
            ).pack(fill="x")
            _label(
                block,
                status_txt,
                fg=accent,
                bg=Theme.SURFACE,
                font=(Theme.FONT_UI, 7),
                anchor="center",
            ).pack(fill="x", pady=(2, 0))

            if i < len(steps) - 1:
                # Línea conceptual entre nodos; colocada al borde visual.
                line = tk.Frame(flow, bg=Theme.BORDER, height=2, width=18)
                line.pack(side="left", pady=(19, 0))
        return card

    def _build_activity_card(self, parent: tk.Misc) -> Card:
        card = Card(parent, padx=14, pady=13)
        top = tk.Frame(card, bg=Theme.SURFACE)
        top.pack(fill="x")
        _label(
            top,
            "Actividad reciente",
            fg=Theme.TEXT,
            bg=Theme.SURFACE,
            font=(Theme.FONT_DISPLAY, 12),
        ).pack(side="left")

        items = self.state.recent_activity[:5]
        if not items:
            items = [
                RecentActivity(
                    "Proyecto preparado",
                    "La actividad aparecerá aquí a medida que avance el análisis.",
                    "Ahora",
                    "ok",
                )
            ]

        for item in items:
            _separator(card).pack(fill="x", pady=(8, 7))
            row = tk.Frame(card, bg=Theme.SURFACE)
            row.pack(fill="x")
            accent = {
                "ok": Theme.GREEN,
                "info": Theme.BLUE,
                "warning": Theme.AMBER,
                "export": Theme.PURPLE,
            }.get(item.kind, Theme.BLUE)
            _label(
                row,
                "●",
                fg=accent,
                bg=Theme.SURFACE,
                font=(Theme.FONT_UI, 8),
            ).pack(side="left", padx=(0, 7))
            txt = tk.Frame(row, bg=Theme.SURFACE)
            txt.pack(side="left", fill="x", expand=True)
            _label(
                txt,
                item.title,
                fg=Theme.TEXT_2,
                bg=Theme.SURFACE,
                font=(Theme.FONT_UI, 8, "bold"),
            ).pack(anchor="w")
            if item.detail:
                _label(
                    txt,
                    item.detail,
                    fg=Theme.TEXT_3,
                    bg=Theme.SURFACE,
                    font=(Theme.FONT_UI, 7),
                ).pack(anchor="w", pady=(1, 0))
            if item.when:
                _label(
                    row,
                    item.when,
                    fg=Theme.TEXT_3,
                    bg=Theme.SURFACE,
                    font=(Theme.FONT_UI, 7),
                ).pack(side="right", padx=(8, 0))
        return card

    def _build_corpus_card(self, parent: tk.Misc) -> Card:
        card = Card(parent, padx=14, pady=13)
        _label(
            card,
            "Vista del corpus",
            fg=Theme.TEXT,
            bg=Theme.SURFACE,
            font=(Theme.FONT_DISPLAY, 12),
        ).pack(anchor="w", pady=(0, 9))

        preview = tk.Frame(
            card,
            bg="#C9B690",
            height=145,
            highlightthickness=1,
            highlightbackground="#88795B",
        )
        preview.pack(fill="x")
        preview.pack_propagate(False)
        _label(
            preview,
            self.state.publication.upper() if self.state.publication else "CORPUS",
            fg="#312719",
            bg="#C9B690",
            font=(Theme.FONT_DISPLAY, 15, "bold"),
            anchor="center",
        ).pack(fill="x", pady=(17, 5))
        _separator(preview).pack(fill="x", padx=16, pady=4)
        for width in (44, 56, 38, 61, 49):
            tk.Frame(
                preview,
                bg="#756649",
                height=2,
                width=width * 3,
            ).pack(pady=3)

        meta = tk.Frame(card, bg=Theme.SURFACE)
        meta.pack(fill="x", pady=(10, 6))
        rows = [
            ("Publicación", self.state.publication),
            ("Año", self.state.current_year),
            ("Número", self.state.current_number),
            ("Fecha", self.state.current_date),
            ("Sección", self.state.current_section),
            ("Página", self.state.current_page),
        ]
        shown = False
        for label, value in rows:
            if not value:
                continue
            shown = True
            r = tk.Frame(meta, bg=Theme.SURFACE)
            r.pack(fill="x", pady=1)
            _label(
                r,
                label,
                fg=Theme.TEXT_3,
                bg=Theme.SURFACE,
                font=(Theme.FONT_UI, 7),
                width=12,
            ).pack(side="left")
            _label(
                r,
                str(value),
                fg=Theme.TEXT_2,
                bg=Theme.SURFACE,
                font=(Theme.FONT_UI, 7),
            ).pack(side="left")
        if not shown:
            _label(
                meta,
                "La vista mostrará metadatos del número o página activa.",
                fg=Theme.TEXT_3,
                bg=Theme.SURFACE,
                font=(Theme.FONT_UI, 7),
                wraplength=260,
            ).pack(anchor="w")

        HoverButton(
            card,
            "Abrir en visor",
            self.callbacks.open_corpus_viewer,
            bg=Theme.SURFACE_2,
            hover_bg=Theme.SURFACE_HOVER,
            fg=Theme.TEXT_2,
            font=(Theme.FONT_UI, 8),
        ).pack(anchor="w", pady=(4, 0))
        return card

    def _build_actions_card(self, parent: tk.Misc) -> Card:
        card = Card(parent, padx=14, pady=13)
        _label(
            card,
            "Siguientes acciones",
            fg=Theme.TEXT,
            bg=Theme.SURFACE,
            font=(Theme.FONT_DISPLAY, 12),
        ).pack(anchor="w")

        actions = self.state.next_actions[:5]
        if not actions:
            actions = self._infer_actions()

        for action in actions:
            _separator(card).pack(fill="x", pady=(8, 7))
            row = tk.Frame(card, bg=Theme.SURFACE, cursor="hand2")
            row.pack(fill="x")
            accent = {
                "warning": Theme.AMBER,
                "info": Theme.BLUE,
                "ok": Theme.GREEN,
                "export": Theme.PURPLE,
            }.get(action.kind, Theme.AMBER)
            _label(
                row,
                "◇",
                fg=accent,
                bg=Theme.SURFACE,
                font=(Theme.FONT_UI, 12, "bold"),
            ).pack(side="left", padx=(0, 7))
            txt = tk.Frame(row, bg=Theme.SURFACE)
            txt.pack(side="left", fill="x", expand=True)
            _label(
                txt,
                action.title,
                fg=Theme.TEXT_2,
                bg=Theme.SURFACE,
                font=(Theme.FONT_UI, 8, "bold"),
            ).pack(anchor="w")
            if action.detail:
                _label(
                    txt,
                    action.detail,
                    fg=Theme.TEXT_3,
                    bg=Theme.SURFACE,
                    font=(Theme.FONT_UI, 7),
                    wraplength=250,
                ).pack(anchor="w", pady=(1, 0))
            _label(
                row,
                "›",
                fg=Theme.TEXT_3,
                bg=Theme.SURFACE,
                font=(Theme.FONT_UI, 15),
            ).pack(side="right")
            for w in (row, txt, *txt.winfo_children()):
                w.bind(
                    "<Button-1>",
                    lambda _e, a=action: self._action_click(a),
                )
        return card

    def _infer_actions(self) -> list[NextAction]:
        active = next(
            (p for p in self.state.pipeline if p.status in {"active", "warning"}),
            None,
        )
        if active:
            return [
                NextAction(
                    f"Continuar {active.label}",
                    "Retomar el punto de trabajo actual del pipeline.",
                    active.key,
                    "warning",
                ),
                NextAction(
                    "Revisar resultados intermedios",
                    "Comprobar calidad antes de avanzar a la siguiente etapa.",
                    "res",
                    "info",
                ),
            ]
        pending = next(
            (p for p in self.state.pipeline if p.status == "pending"),
            None,
        )
        if pending:
            return [
                NextAction(
                    f"Iniciar {pending.label}",
                    "Siguiente etapa disponible del flujo de investigación.",
                    pending.key,
                    "info",
                )
            ]
        return [
            NextAction(
                "Preparar exportación final",
                "El flujo principal no tiene etapas pendientes.",
                "export",
                "export",
            )
        ]

    def _action_click(self, action: NextAction) -> None:
        if self.callbacks.action_selected:
            self.callbacks.action_selected(action.target or action.title)
        elif action.target and self.callbacks.navigate:
            self.callbacks.navigate(action.target)

    def _build_capabilities_card(self, parent: tk.Misc) -> Card:
        card = Card(parent, padx=14, pady=13)
        _label(
            card,
            "Capacidades disponibles",
            fg=Theme.TEXT,
            bg=Theme.SURFACE,
            font=(Theme.FONT_DISPLAY, 12),
        ).pack(anchor="w")

        caps = self.state.capabilities[:6] or [
            Capability("Tesseract OCR", enabled=True),
            Capability("spaCy", enabled=True),
            Capability("PyMuPDF", enabled=True),
            Capability("LLM local", enabled=True),
        ]
        for cap in caps:
            _separator(card).pack(fill="x", pady=(8, 7))
            row = tk.Frame(card, bg=Theme.SURFACE)
            row.pack(fill="x")
            _label(
                row,
                "◉",
                fg=Theme.GREEN if cap.enabled else Theme.TEXT_MUTED,
                bg=Theme.SURFACE,
                font=(Theme.FONT_UI, 9),
            ).pack(side="left", padx=(0, 7))
            txt = tk.Frame(row, bg=Theme.SURFACE)
            txt.pack(side="left", fill="x", expand=True)
            _label(
                txt,
                cap.name,
                fg=Theme.TEXT_2,
                bg=Theme.SURFACE,
                font=(Theme.FONT_UI, 8, "bold"),
            ).pack(anchor="w")
            if cap.detail:
                _label(
                    txt,
                    cap.detail,
                    fg=Theme.TEXT_3,
                    bg=Theme.SURFACE,
                    font=(Theme.FONT_UI, 7),
                    wraplength=230,
                ).pack(anchor="w")
            state_fg = Theme.GREEN if cap.enabled else Theme.TEXT_MUTED
            _label(
                row,
                "Habilitado" if cap.enabled else "No disponible",
                fg=state_fg,
                bg=Theme.SURFACE,
                font=(Theme.FONT_UI, 7),
            ).pack(side="right", padx=(6, 0))
            if cap.version:
                _label(
                    row,
                    cap.version,
                    fg=Theme.TEXT_3,
                    bg=Theme.SURFACE,
                    font=(Theme.FONT_UI, 7),
                ).pack(side="right", padx=(6, 0))
        return card

    def _show_preview_notice(self, key: str) -> None:
        _clear(self.dashboard)
        wrap = tk.Frame(self.dashboard, bg=Theme.BG)
        wrap.pack(fill="both", expand=True, padx=28, pady=26)
        _label(
            wrap,
            "Vista reservada para integración",
            fg=Theme.TEXT,
            bg=Theme.BG,
            font=(Theme.FONT_DISPLAY, 22),
        ).pack(anchor="w")
        _label(
            wrap,
            (
                f"El módulo «{key}» seguirá usando el panel funcional existente "
                "de Bashkar Station. Claude Code debe montar aquí el frame actual "
                "de app.py y aplicar progresivamente estos mismos componentes visuales."
            ),
            fg=Theme.TEXT_2,
            bg=Theme.BG,
            font=(Theme.FONT_UI, 10),
            wraplength=720,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

    # ----------------------------------------------------------------------
    # Bottom statusbar
    # ----------------------------------------------------------------------

    def _refresh_statusbar(self) -> None:
        if not self.chrome:
            return
        _clear(self.statusbar)
        left = tk.Frame(self.statusbar, bg=Theme.TOPBAR)
        left.pack(side="left", fill="y", padx=16)

        _label(
            left,
            "◇  Todo se procesa localmente en tu equipo.",
            fg=Theme.GREEN,
            bg=Theme.TOPBAR,
            font=(Theme.FONT_UI, 7),
        ).pack(side="left", pady=8)

        _separator(left, vertical=True).pack(
            side="left", fill="y", padx=14, pady=8
        )

        _label(
            left,
            "Sincronización desactivada",
            fg=Theme.TEXT_3,
            bg=Theme.TOPBAR,
            font=(Theme.FONT_UI, 7),
        ).pack(side="left", pady=8)

        _separator(left, vertical=True).pack(
            side="left", fill="y", padx=14, pady=8
        )

        ready_text = "Sistema listo" if self.state.system_ready else "Sistema ocupado"
        ready_fg = Theme.GREEN if self.state.system_ready else Theme.AMBER
        _label(
            left,
            f"●  {ready_text}",
            fg=ready_fg,
            bg=Theme.TOPBAR,
            font=(Theme.FONT_UI, 7),
        ).pack(side="left", pady=8)

        right = tk.Frame(self.statusbar, bg=Theme.TOPBAR)
        right.pack(side="right", fill="y", padx=16)
        if self.state.free_storage_text:
            _label(
                right,
                f"Almacenamiento local: {self.state.free_storage_text}",
                fg=Theme.TEXT_3,
                bg=Theme.TOPBAR,
                font=(Theme.FONT_UI, 7),
            ).pack(side="left", pady=8)
        HoverButton(
            right,
            "⚙",
            self.callbacks.open_settings,
            bg=Theme.TOPBAR,
            hover_bg=Theme.SURFACE_HOVER,
            fg=Theme.TEXT_3,
            font=(Theme.FONT_UI, 10),
            padx=5,
            pady=3,
            border=False,
        ).pack(side="left", padx=(8, 0), pady=3)


# ============================================================================
# STANDALONE PREVIEW
# ============================================================================

def demo_state() -> DashboardState:
    return DashboardState(
        project_name="Revista Estampa",
        publication="Revista Estampa",
        period="1938–1940",
        description=(
            "Revista ilustrada de información general. Corpus histórico para "
            "investigación cultural, editorial, política y social."
        ),
        pages_processed=1248,
        pages_total=1320,
        ocr_quality=96.3,
        articles=386,
        entities=4782,
        current_number="98",
        current_year="1939",
        current_date="23 de julio de 1939",
        current_section="Internacionales",
        current_page="32",
        local_mode=True,
        external_ai_enabled=False,
        system_ready=True,
        free_storage_text="128 GB libres",
        pipeline=[
            PipelineStep("ocr", "OCR", "completed"),
            PipelineStep("norm", "Normalización", "completed"),
            PipelineStep("seg", "Segmentación", "completed"),
            PipelineStep("ner", "NER", "active"),
            PipelineStep("anal", "Análisis", "pending"),
            PipelineStep("export", "Exportación", "pending"),
        ],
        recent_activity=[
            RecentActivity(
                "Normalización de páginas 1.201–1.248",
                "42 páginas procesadas",
                "Hoy, 09:47",
                "ok",
            ),
            RecentActivity(
                "Artículos detectados en 15 páginas",
                "Se detectaron 18 nuevos artículos",
                "Hoy, 09:21",
                "info",
            ),
            RecentActivity(
                "Revisión de entidades",
                "312 entidades revisadas",
                "Ayer, 18:36",
                "warning",
            ),
            RecentActivity(
                "Exportación TEI completada",
                "estampa_1938_1939_tei.xml",
                "Ayer, 16:12",
                "export",
            ),
        ],
        next_actions=[
            NextAction(
                "Revisar entidades sugeridas",
                "Hay 120 entidades con baja confianza.",
                "ner",
                "warning",
            ),
            NextAction(
                "Verificar segmentación",
                "Revisar páginas con advertencias.",
                "seg",
                "info",
            ),
            NextAction(
                "Explorar redes de coocurrencia",
                "Analizar términos y entidades clave.",
                "red",
                "ok",
            ),
            NextAction(
                "Preparar exportación final",
                "Configurar metadatos y formato TEI.",
                "export",
                "export",
            ),
        ],
        capabilities=[
            Capability(
                "Tesseract OCR",
                "Reconocimiento óptico de caracteres",
                True,
                "v5.3.3",
            ),
            Capability(
                "spaCy",
                "Modelo local para NER y análisis",
                True,
                "v3.7",
            ),
            Capability(
                "PyMuPDF",
                "Extracción y manejo de documentos",
                True,
                "v1.23",
            ),
            Capability(
                "LLM local (Ollama)",
                "Modelos de lenguaje ejecutados en el equipo",
                True,
                "local",
            ),
        ],
    )


def run_preview() -> None:
    root = tk.Tk()
    root.title("Bashkar Station — Desktop UI Redesign Preview")
    root.geometry("1480x900")
    root.minsize(1160, 720)
    root.configure(bg=Theme.BG)

    def nav(key: str) -> None:
        print("navigate:", key)

    callbacks = BashkarCallbacks(navigate=nav)
    shell = BashkarDesktopShell(
        root,
        demo_state(),
        callbacks,
        version="11.10",
    )
    shell.pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    run_preview()
