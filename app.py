"""
╔══════════════════════════════════════════════════════════════════════╗
║  BASHKAR STATION v11.7 — Análisis editorial computacional           ║
║  Aplicación de escritorio · 100% offline · Publicaciones históricas ║
╚══════════════════════════════════════════════════════════════════════╝
"""
import gc
import os
import queue
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

# Única dependencia del proyecto que se importa antes de resolver paquetes:
# core.plataforma es solo biblioteca estándar, así que no puede fallar aquí, y
# hace falta ya para saber dónde busca cada sistema tesseract y poppler.
from core import plataforma, recursos

# Reparto de CPU. Va aquí arriba del todo y no en el arranque de la ventana
# porque OpenMP/MKL leen estas variables al inicializarse: si para entonces ya
# se importó torch o numpy por cualquier camino, fijarlas no sirve de nada.
# Sin esto, un lote de OCR deja la interfaz sin un solo núcleo para repintar y
# la app parece congelada.
recursos.aplicar_limites_cpu()

if TYPE_CHECKING:
    from core.bitacora_engine import BitacoraEngine

# ── Rutas de binarios externos (Tesseract/Poppler) ───────────────────────────
_APP_DIR = Path(__file__).parent
_APP_VERSION_SPLASH = "13.1"   # sincronizar con APP_VERSION abajo


def _configurar_rutas_binarios():
    """Prepara PATH, pytesseract y TESSDATA_PREFIX antes de que arranque la UI.

    Antes esto corría solo en Windows, porque se daba por hecho que en Unix los
    binarios están siempre en el PATH. En macOS no es así: una app abierta desde
    Finder hereda un PATH mínimo que no incluye Homebrew, de modo que tesseract
    "desaparece" aunque el usuario lo tenga instalado. Por eso ahora se ejecuta
    en los tres sistemas; lo que cambia son las rutas, no el procedimiento.
    """
    for cfg_file in ["tesseract_path.txt", "poppler_path.txt"]:
        cfg = _APP_DIR / cfg_file
        if not cfg.exists():
            continue
        ruta = cfg.read_text(encoding="utf-8").strip()
        if not ruta:
            continue
        p = Path(ruta)
        if not p.exists():
            continue
        # Si la ruta apunta a un ejecutable, agregar su carpeta al PATH
        carpeta = str(p.parent) if p.is_file() else str(p)
        os.environ["PATH"] = carpeta + os.pathsep + os.environ.get("PATH", "")
        if cfg_file.startswith("tesseract"):
            try:
                import pytesseract
                exe = (str(p) if p.is_file()
                       else str(p / plataforma.nombre_ejecutable("tesseract")))
                pytesseract.pytesseract.tesseract_cmd = exe
            except ImportError:
                pass

    # Si no había tesseract_path.txt, buscarlo donde lo deja cada sistema.
    if not (_APP_DIR / "tesseract_path.txt").exists():
        hallado = plataforma.buscar_tesseract()
        if hallado:
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = hallado
            except ImportError:
                pass

    # ── TESSDATA_PREFIX — buscar tessdata/spa.traineddata ────────────────────
    # Orden de prioridad: carpeta local del usuario → carpeta de instalación
    for _td in plataforma.dirs_tessdata():
        try:
            if (_td / "spa.traineddata").exists():
                os.environ["TESSDATA_PREFIX"] = str(_td)
                break
        except OSError:      # unidades de red desconectadas
            continue

_configurar_rutas_binarios()

# ── Fijar NumPy < 2 ───────────────────────────────────────────────────────────
def _fijar_numpy():
    # Ver el guard idéntico y su porqué en _auto_instalar(): sys.executable
    # en un .exe congelado es el propio .exe, no un Python con pip.
    if getattr(sys, "frozen", False):
        return
    import subprocess as _sp
    try:
        import numpy as _np
        v = tuple(int(x) for x in _np.__version__.split(".")[:2])
        if v >= (2, 0):
            _sp.check_call([sys.executable,"-m","pip","install","numpy<2","-q","--force-reinstall"],
                           stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
    except Exception:
        pass
# _fijar_numpy()  # numpy 2.4 instalado — no forzar downgrade al arranque

# ── Auto-instalación de dependencias ─────────────────────────────────────────
_PAQUETES = [
    ("numpy",      "numpy<2"),
    ("fitz",       "pymupdf>=1.23"),
    ("pdf2image",  "pdf2image>=1.17"),
    ("pytesseract","pytesseract>=0.3.10"),
    ("PIL",        "Pillow>=10.0"),
    ("spacy",      "spacy>=3.7"),
    ("sklearn",    "scikit-learn>=1.4"),
    ("networkx",   "networkx>=3.2"),
    ("matplotlib", "matplotlib>=3.8"),
    ("seaborn",    "seaborn>=0.13"),
    ("pandas",     "pandas>=2.1"),
    ("openpyxl",   "openpyxl>=3.1"),
    ("scipy",      "scipy>=1.12"),
    ("cv2",        "opencv-python-headless>=4.9"),
    # gensim es OPCIONAL: Word2Vec usa backend PyTorch si gensim no está.
    # gensim 4.4 no compila en Python 3.14 (API CPython ob_digit eliminada),
    # por eso NO se auto-instala. En Python ≤3.12 puede instalarse a mano.
]

def _auto_instalar():
    # CRÍTICO: nunca ejecutar dentro de un .exe congelado (PyInstaller).
    # sys.executable ahí apunta al propio .exe, no a un Python con pip real;
    # el subprocess.check_call de más abajo relanzaría copias completas de
    # Bashkar Station en vez de instalar nada. Cada copia nueva detecta los
    # mismos "faltantes" y vuelve a relanzarse por cada uno — una bomba de
    # fork exponencial (~90 procesos en 12s, tumbó una máquina real).
    # Si un .exe compilado tiene una dependencia realmente faltante, la
    # solución es corregir el .spec y recompilar, nunca auto-instalar en
    # caliente.
    if getattr(sys, "frozen", False):
        return
    import subprocess
    # Comprobar con find_spec, NO con __import__: __import__ CARGA el paquete de
    # verdad, y "spacy" arrastra torch (~11 s en frío) más sklearn — es decir, el
    # arranque pagaba el costo completo de importar la pila de ML solo para
    # averiguar si estaba instalada. find_spec resuelve lo mismo mirando el
    # sistema de importación, sin ejecutar el módulo (~0,02 s en total).
    # Los módulos que la app necesita de verdad ya se importan más abajo, cada
    # uno en su sitio.
    import importlib.util
    faltantes = []
    for mod, pkg in _PAQUETES:
        try:
            encontrado = importlib.util.find_spec(mod) is not None
        except (ImportError, ValueError):
            encontrado = False
        if not encontrado:
            faltantes.append((mod, pkg))
    if not faltantes:
        return
    import tkinter as tk
    from tkinter import ttk
    root = tk.Tk(); root.title(f"Bashkar Station v{_APP_VERSION_SPLASH} — Instalando")
    root.geometry("520x340"); root.configure(bg="#12171B"); root.resizable(False,False)
    try:
        from PIL import Image, ImageTk
        _sp_img = Image.open(_APP_DIR / "assets" / "logo_splash.png")
        _sp_tk  = ImageTk.PhotoImage(_sp_img)
        tk.Label(root, image=_sp_tk, bg="#12171B").pack(pady=(12,0))
        root._sp_tk = _sp_tk  # evitar GC
    except Exception:
        tk.Label(root, text=f"BASHKAR STATION v{_APP_VERSION_SPLASH}", bg="#12171B", fg="white",
                 font=("Segoe UI",16,"bold")).pack(pady=(20,4))
    tk.Label(root, text=f"Instalando {len(faltantes)} paquete(s) faltantes…",
             bg="#12171B", fg="#6CA8E8", font=("Segoe UI",10)).pack(pady=(0,12))
    lbl = tk.Label(root, text="", bg="#12171B", fg="white", font=("Courier",10)); lbl.pack()
    prog = ttk.Progressbar(root, length=380, mode="determinate", maximum=len(faltantes)); prog.pack(pady=10)
    lbl_e = tk.Label(root, text="", bg="#12171B", fg="#6EC69A", font=("Segoe UI",9)); lbl_e.pack()
    errores = []
    def run():
        for i,(mod,pkg) in enumerate(faltantes):
            lbl.config(text=f"pip install {pkg}"); root.update()
            try:
                subprocess.check_call([sys.executable,"-m","pip","install",pkg,"-q"],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                errores.append(pkg)
            prog["value"] = i+1; root.update()
        lbl_e.config(text="✅ Listo — abriendo…" if not errores else f"⚠️ Error: {', '.join(errores)}")
        root.after(1500, root.destroy)
    root.after(200, run); root.mainloop()
_auto_instalar()

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Compartido con los paneles (paneles/*.py): ver gui_comun.py.
from gui_comun import (  # noqa: E402
    APP_VERSION,
    CAMPOS_DEFAULT,
    COLABS_DEFAULT,
    PALETTE,
    ST,
    TEMA,
    _autor_local,
    _MODELO_VISION_DEFECTO,
    _registrar_error,
    _resolver_api_key_modelo,
    _simbolo_estado_norm,
)









APP_NAME    = "Bashkar Station"

# ── Identidad visual — grafito, cobre y teal ──────────────────────────────────
# La interfaz ya NO imita a VS Code. Los colores viven en `ui_redesign.Theme`,
# el mismo módulo que dibuja el panel Inicio: así el tablero y los 30 paneles no
# pueden divergir. Aquí solo se traducen esos tokens a los nombres que el resto
# de app.py lleva usando desde siempre (CARD_BG, TXT_PRI, AZ3…), de modo que
# cambiar la identidad no exige tocar ni un panel.
from ui_redesign import Theme as _T  # noqa: E402  (va aquí, junto a la paleta)

_PALETA_DARK = {
    # Activity bar — la franja más oscura, ancla visual de la navegación
    "AB_BG":     _T.TOPBAR,
    "AB_SEL":    _T.AMBER,        # ícono activo: ámbar
    "AB_TXT":    _T.TEXT_3,       # ícono inactivo
    "AB_IND":    _T.COPPER,       # indicador izquierdo: cobre

    # Sidebar
    "SB_BG":     _T.SIDEBAR,
    "SB_HOV":    _T.SURFACE_HOVER,
    "SB_SEL":    _T.SURFACE_ACTIVE,   # selección cálida, no azul
    "SB_TXT":    _T.TEXT_2,
    "SB_TXT2":   _T.TEXT,

    # Contenido
    "CONTENT_BG":_T.BG,
    "CARD_BG":   _T.SURFACE,
    "CARD_BOR":  _T.BORDER,
    "HDR_LINE":  _T.COPPER,

    # Topbar
    "TOPBAR_BG": _T.TOPBAR,

    # Paleta funcional
    "AZ1":       _T.BG,
    "AZ2":       _T.SURFACE_2,
    "AZ3":       _T.COPPER,       # acción primaria
    "AZ4":       _T.AMBER,        # títulos y realces
    "AZ_INFO":   _T.BLUE,         # información (era el azul de todo)
    "ACENT":     _T.AMBER,
    "VERDE":     _T.GREEN,
    "TEAL":      _T.TEAL,
    "PURPURA":   _T.PURPLE,
    "ROJO":      _T.RED,
    "GRIS":      _T.SURFACE_2,
    "GRIS2":     _T.TEXT_3,       # se usa como texto atenuado, no como borde

    # Fondos tintados de las pastillas de estado
    "READY_BG":  _T.READY_BG,
    "INFO_BG":   _T.INFO_BG,
    "WARN_BG":   _T.WARN_BG,
    "ERR_BG":    "#2A1719",
    "TEAL_BG":   "#132622",
    "PURP_BG":   "#221C2E",

    # Texto
    "TXT_PRI":   _T.TEXT,
    "TXT_SEC":   _T.TEXT_3,
    "TXT_DIM":   _T.TEXT_MUTED,
}

# Modo claro: papel y tinta, con el mismo cobre. No es el Light+ de VS Code,
# es el reverso cálido de la identidad oscura.
_PALETA_LIGHT = {
    # Activity bar — se mantiene oscura también en claro, para anclar la
    # navegación con el mismo gesto que el modo oscuro.
    "AB_BG":     _T.TOPBAR,
    "AB_SEL":    _T.AMBER,
    "AB_TXT":    _T.TEXT_3,
    "AB_IND":    _T.COPPER,

    # Sidebar
    "SB_BG":     "#F0EBE3",
    "SB_HOV":    "#E4DDD2",
    "SB_SEL":    "#F3E0C9",
    "SB_TXT":    "#5A544C",
    "SB_TXT2":   "#2A2622",

    # Contenido
    "CONTENT_BG":"#FAF7F2",
    "CARD_BG":   "#FFFDF9",
    "CARD_BOR":  "#DED6C9",
    "HDR_LINE":  _T.COPPER_2,

    # Topbar
    "TOPBAR_BG": "#EDE7DE",

    # Paleta funcional
    "AZ1":       "#FAF7F2",
    "AZ2":       "#F0EBE3",
    "AZ3":       _T.COPPER_2,
    "AZ4":       "#8A5A22",
    "AZ_INFO":   "#2F6FB0",
    "ACENT":     "#B96F32",
    "VERDE":     "#2E7D57",
    "TEAL":      "#217F71",
    "PURPURA":   "#6E4C9B",
    "ROJO":      "#B3423F",
    "GRIS":      "#F0EBE3",
    "GRIS2":     "#6B6459",

    # Fondos tintados de las pastillas de estado
    "READY_BG":  "#E4F0E7",
    "INFO_BG":   "#E3ECF6",
    "WARN_BG":   "#F8EBD6",
    "ERR_BG":    "#F7E2E1",
    "TEAL_BG":   "#DEEFEC",
    "PURP_BG":   "#EBE5F3",

    # Texto
    "TXT_PRI":   "#2A2622",
    "TXT_SEC":   "#6B6459",
    "TXT_DIM":   "#948C80",
}

_MODO_OSCURO = True   # estado global mutable

def _aplicar_paleta(paleta: dict):
    """Inyecta la paleta elegida en las variables globales de color."""
    g = globals()
    for k, v in paleta.items():
        g[k] = v
    # Los paneles leen los colores de TEMA (gui_comun): actualizarlo hace
    # que el cambio de tema les llegue.
    TEMA.actualizar(paleta)

_aplicar_paleta(_PALETA_DARK)

# ── Variables de color activas (actualizadas por _aplicar_paleta) ─────────────
# Se declaran con los mismos valores que _PALETA_DARK para que los analizadores
# estáticos (ruff, PyInstaller) vean nombres definidos; _aplicar_paleta las
# reescribe en caliente al cambiar de tema.

# Activity Bar
AB_BG   = _T.TOPBAR
AB_HOV  = _T.SURFACE_HOVER
AB_SEL  = _T.AMBER
AB_TXT  = _T.TEXT_3
AB_IND  = _T.COPPER

# Sidebar
SB_BG   = _T.SIDEBAR
SB_HOV  = _T.SURFACE_HOVER
SB_SEL  = _T.SURFACE_ACTIVE
SB_TXT  = _T.TEXT_2
SB_TXT2 = _T.TEXT

# Contenido
CONTENT_BG = _T.BG
CARD_BG    = _T.SURFACE
CARD_BOR   = _T.BORDER
HDR_LINE   = _T.COPPER

# Topbar
TOPBAR_BG  = _T.TOPBAR
TOPBAR_H   = 56       # da aire a la marca y a las pastillas de estado

# Paleta funcional
AZ1=_T.BG; AZ2=_T.SURFACE_2; AZ3=_T.COPPER; AZ4=_T.AMBER
AZ_INFO=_T.BLUE
ACENT=_T.AMBER; VERDE=_T.GREEN; TEAL=_T.TEAL; PURPURA=_T.PURPLE; ROJO=_T.RED
GRIS=_T.SURFACE_2; GRIS2=_T.TEXT_3

# Fondos tintados de las pastillas de estado
READY_BG = _T.READY_BG
INFO_BG  = _T.INFO_BG
WARN_BG  = _T.WARN_BG
ERR_BG   = "#2A1719"
TEAL_BG  = "#132622"
PURP_BG  = "#221C2E"

# Texto
TXT_PRI = _T.TEXT
TXT_SEC = _T.TEXT_3
TXT_DIM = _T.TEXT_MUTED

# TEMA (gui_comun) debe reflejar los valores efectivos de arriba, no solo los
# de _PALETA_DARK: si alguna redeclaración difiriera, app.py y los paneles
# pintarían con colores distintos.
TEMA.actualizar({k: globals()[k] for k in _PALETA_DARK})





# ══════════════════════════════════════════════════════════════════════════════
# ESTADO GLOBAL
# ══════════════════════════════════════════════════════════════════════════════
# La clase Estado vive en core/estado.py — fuente única compartida con el
# servidor web (servidor_web.py). Aquí solo se instancia el singleton de la GUI.


class _VarCongelada:
    """Valor de una variable Tk ya leído, para usar dentro de un hilo worker.

    Tcl no es thread-safe: llamar `.get()` de una variable Tk desde un hilo
    secundario serializa la llamada contra el bucle de eventos del hilo
    principal, con riesgo de bloqueo mutuo si el principal está esperando al
    worker. La lectura se hace ANTES de lanzar el hilo y el worker recibe esto,
    que mantiene la misma interfaz `.get()` para no alterar el código existente.
    """

    __slots__ = ("_valor",)

    def __init__(self, valor):
        self._valor = valor

    def get(self):
        return self._valor


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS API / MODELOS
# ══════════════════════════════════════════════════════════════════════════════






# ══════════════════════════════════════════════════════════════════════════════
# ESTILOS ttk
# ══════════════════════════════════════════════════════════════════════════════
def _estilos():
    s = ttk.Style(); s.theme_use("clam")
    # Base dark
    s.configure(".", background=CONTENT_BG, foreground=TXT_PRI,
                font=("Segoe UI", 10))
    # Botón primario — cobre, la acción de la identidad. Tinta oscura encima:
    # el cobre es un color claro y el texto blanco se le pierde.
    s.configure("P.TButton", background=AZ3, foreground=_T.BG,
                font=("Segoe UI", 10, "bold"), padding=[18, 8],
                borderwidth=0, relief="flat")
    s.map("P.TButton",
          background=[("active", _T.AMBER), ("disabled", CARD_BOR)],
          foreground=[("disabled", TXT_DIM)])
    # Botón secundario — grafito
    s.configure("S.TButton", background=CARD_BOR, foreground=TXT_PRI,
                font=("Segoe UI", 9), padding=[12, 6],
                borderwidth=0, relief="flat")
    s.map("S.TButton", background=[("active", _T.SURFACE_HOVER),
                                    ("disabled", AZ2)])
    # Botón acento — ámbar
    s.configure("A.TButton", background=ACENT, foreground=_T.BG,
                font=("Segoe UI", 9, "bold"), padding=[12, 6],
                borderwidth=0, relief="flat")
    s.map("A.TButton", background=[("active", _T.COPPER)])
    # Botón éxito — verde
    s.configure("OK.TButton", background=VERDE, foreground=_T.BG,
                font=("Segoe UI", 9, "bold"), padding=[12, 6],
                borderwidth=0, relief="flat")
    s.map("OK.TButton", background=[("active", _T.TEAL)])
    # Etiquetas
    s.configure("H.TLabel",    background=CONTENT_BG, foreground=TXT_PRI,
                font=("Segoe UI", 13, "bold"))
    s.configure("H2.TLabel",   background=CARD_BG,    foreground=TXT_PRI,
                font=("Segoe UI", 11, "bold"))
    s.configure("Sub.TLabel",  background=CONTENT_BG, foreground=TXT_SEC,
                font=("Segoe UI", 9))
    s.configure("Card.TLabel", background=CARD_BG,    foreground=TXT_PRI,
                font=("Segoe UI", 10))
    # Progreso
    s.configure("TProgressbar", troughcolor=CARD_BOR, background=AZ3,
                thickness=6, borderwidth=0)
    # Notebook tabs
    s.configure("TNotebook", background=CARD_BG, borderwidth=0)
    s.configure("TNotebook.Tab", background=AZ2, foreground=TXT_SEC,
                font=("Segoe UI", 9), padding=[12, 5])
    s.map("TNotebook.Tab",
          background=[("selected", CARD_BG)],
          foreground=[("selected", TXT_PRI)])
    # Frames y separadores
    s.configure("TLabelframe", background=CARD_BG, foreground=TXT_PRI,
                bordercolor=CARD_BOR, borderwidth=1, relief="solid",
                font=("Segoe UI", 10, "bold"))
    s.configure("TLabelframe.Label", background=CARD_BG, foreground=AZ4,
                font=("Segoe UI", 10, "bold"))
    s.configure("TCheckbutton", background=CARD_BG, foreground=TXT_PRI)
    s.configure("TRadiobutton", background=CARD_BG, foreground=TXT_PRI)
    s.configure("TSeparator", background=CARD_BOR)
    # Combobox
    s.configure("TCombobox", background=CARD_BG, foreground=TXT_PRI,
                fieldbackground=CARD_BG, selectbackground=AZ3,
                arrowcolor=TXT_SEC, bordercolor=CARD_BOR)
    # Spinbox
    s.configure("TSpinbox", background=CARD_BG, foreground=TXT_PRI,
                fieldbackground=CARD_BG, bordercolor=CARD_BOR,
                arrowcolor=TXT_SEC)
    # Treeview
    s.configure("Treeview", background=CARD_BG, foreground=TXT_PRI,
                fieldbackground=CARD_BG, rowheight=28,
                font=("Segoe UI", 9), borderwidth=0)
    s.configure("Treeview.Heading", background=AZ2, foreground=TXT_SEC,
                font=("Segoe UI", 9, "bold"), relief="flat", borderwidth=0)
    s.map("Treeview",
          background=[("selected", AZ3)],
          foreground=[("selected", _T.BG)])


# ══════════════════════════════════════════════════════════════════════════════
# VENTANA PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
# ── Prompts de asistente IA sugeridos por pestaña ────────────────────────────
# Orientados a estudios editoriales colombianos: historia de la prensa,
# análisis del discurso, estudios culturales, sociología del campo editorial.
# Fuentes de referencia: Loaiza Cano, Osorio Tejeda, Riaño, Silva Olarte,
# Colombia 100 años de revistas (Banco de la República).

_AI_PROMPTS = {
    "ocr": [
        ("Calidad de transcripción",
         "Analiza el texto extraído e identifica los principales problemas de calidad OCR: "
         "palabras mal reconocidas, errores sistemáticos de caracteres confundidos (I/l, 0/O, rn/m), "
         "y fragmentos ilegibles. Estima qué porcentaje del texto es confiable para análisis cuantitativo."),
        ("Vocabulario de época",
         "Construye un glosario de términos propios del período a partir del texto extraído: "
         "arcaísmos, neologismos de los años 30-40, términos técnicos de la industria editorial "
         "colombiana y colombianismos. Indica frecuencia y contexto de aparición de cada término."),
        ("Patrones tipográficos y editoriales",
         "Identifica en el texto los patrones de presentación editorial: secciones fijas recurrentes, "
         "fórmulas de apertura y cierre de artículos, convenciones de citación y pie de foto. "
         "¿Qué revelan sobre las prácticas editoriales de la publicación?"),
        ("Variantes del español colombiano",
         "Compara la ortografía y gramática con la norma del español colombiano de los años 30-40. "
         "¿Hay variantes regionales, influencias del español peninsular o rasgos bogotanos cultos? "
         "Distingue entre errores OCR y usos propios de la época."),
    ],
    "seg": [
        ("Autoría anónima y prácticas de firma",
         "Analiza los artículos sin autor identificado. ¿Qué tipos de contenido se publican sin firma "
         "(editoriales, notas, traducciones)? Contrasta con los patrones de firma en la prensa "
         "colombiana de los años 30 y discute las implicaciones para la atribución de autoría."),
        ("Campo intelectual y redes de colaboradores",
         "A partir de los autores identificados, reconstruye el campo intelectual de la publicación. "
         "¿Hay colaboradores recurrentes? ¿Se pueden identificar redes de intelectuales, círculos "
         "literarios o afiliaciones ideológicas (liberalismo lopista, conservatismo, vanguardias)?"),
        ("Distribución de géneros periodísticos y literarios",
         "Clasifica los artículos segmentados por géneros (crónica, editorial, cuento, poema, ensayo, "
         "reportaje, nota social). ¿Cómo refleja esta distribución el proyecto editorial y el "
         "posicionamiento de la publicación en el mercado de revistas colombianas?"),
        ("Extensión, espacio y jerarquía editorial",
         "Analiza la distribución de longitud de los artículos. ¿Qué géneros o autores reciben más "
         "espacio? ¿Hay correlación entre extensión y posición en la página? Discute qué dice esto "
         "sobre la jerarquía de valores editoriales de la publicación."),
    ],
    "anal": [
        ("Posicionamiento ideológico y discurso político",
         "A partir de los temas LDA y entidades nombradas, analiza el posicionamiento ideológico. "
         "¿Cómo se refieren a los partidos políticos, al Estado, a la Iglesia? ¿Se detectan "
         "alineaciones con el liberalismo lopista, el conservatismo o corrientes de izquierda "
         "de los años 30 colombianos?"),
        ("Imaginarios de modernidad y progreso",
         "Identifica cómo la publicación construye el imaginario de la modernidad. ¿Qué referentes "
         "usa (técnica, industria, ciudad, Europa, EE.UU.)? ¿Cómo se articula el discurso del "
         "progreso con la identidad nacional colombiana de la República Liberal?"),
        ("Canon literario e intertextualidad",
         "A partir de las entidades y el vocabulario, identifica referencias a autores, publicaciones "
         "y obras. ¿Qué canon construye la revista? ¿Hay presencia de la vanguardia latinoamericana, "
         "el modernismo tardío o la literatura española? ¿Se cita prensa internacional?"),
        ("Género, mujer y representación social",
         "Analiza cómo aparece la figura femenina: como autora, como tema, como lectora implícita. "
         "¿Hay secciones dedicadas a la mujer? ¿Qué roles se le asignan? Contrasta con la prensa "
         "femenina colombiana de los años 30 (El Hogar, Letras y Encajes, Agitación Femenina)."),
    ],
    "vis": [
        ("Economía de la imagen y financiamiento publicitario",
         "Analiza la proporción de espacio editorial dedicado a publicidad gráfica vs. contenido "
         "editorial. ¿Qué sectores económicos anuncian? ¿Cómo evoluciona la presencia publicitaria? "
         "Discute la relación entre financiamiento publicitario y autonomía editorial en la "
         "prensa comercial colombiana."),
        ("Fotografía y construcción visual de la modernidad",
         "Describe el uso de la fotografía: ¿predominan retratos, eventos sociales, paisajes, "
         "industria? ¿Hay fotógrafos identificados? ¿Cómo se integra con el texto? Discute en "
         "relación con la introducción del fotograbado y el fotoperiodismo en Colombia."),
        ("Ilustración, caricatura y sátira política",
         "Analiza las ilustraciones y caricaturas. ¿Hay ilustradores identificados? ¿Los temas "
         "son costumbristas, políticos o sociales? Relaciona con la tradición de la caricatura "
         "colombiana (Ricardo Rendón, Chapete) y su función en el debate público."),
        ("Tipografía, diseño e identidad editorial",
         "A partir de las fuentes tipográficas identificadas, analiza la identidad gráfica de la "
         "publicación. ¿Hay coherencia tipográfica? ¿Se usan tipos modernos o tradicionales? "
         "¿Cómo se diferencia de otras revistas del período? Discute el diseño como estrategia "
         "de posicionamiento en el mercado editorial colombiano."),
    ],
    "comp": [
        ("Posicionamiento en el campo editorial colombiano",
         "Compara el perfil temático con el corpus de referencia. ¿En qué se diferencia la agenda "
         "editorial? ¿Ocupa un nicho especializado o compite directamente con otras publicaciones? "
         "Relaciona con la estructura del campo editorial colombiano de los años 30 "
         "(El Tiempo, El Espectador, Cromos, Semana)."),
        ("Inflexiones históricas en el discurso editorial",
         "Analiza cómo cambian los temas y el vocabulario entre números o períodos. ¿Hay "
         "inflexiones relacionadas con eventos históricos colombianos (República Liberal, "
         "violencia partidista, Segunda Guerra Mundial, Bogotazo)? ¿Cómo responde la "
         "publicación a la coyuntura política y cultural?"),
        ("Transferencias culturales e influencias externas",
         "A partir de los términos distintivos y entidades, identifica la presencia de referencias "
         "internacionales. ¿Qué literaturas nacionales tienen mayor presencia (francesa, española, "
         "anglosajona, latinoamericana)? ¿Cómo se articulan las influencias externas con el "
         "proyecto editorial nacional?"),
    ],
    "meta": [
        ("Contextualización histórica del registro",
         "A partir de los metadatos (título, fecha, editorial, descripción), elabora una ficha "
         "de contextualización histórica. ¿Qué eventos históricos colombianos o internacionales "
         "son contemporáneos? ¿Hay cambios en la dirección o el perfil editorial? Ubica el "
         "número en la historia de la publicación."),
        ("Análisis del paratexto y aparato editorial",
         "Analiza los elementos paratextuales: subtítulos, lemas, declaraciones de propósito, "
         "índices, sumarios. ¿Cómo se autopresenta la publicación? ¿Qué lector implícito "
         "construye? Usa conceptos de Gerard Genette y la historia del libro."),
        ("Reconstrucción de la cadena editorial",
         "A partir de los metadatos disponibles, reconstruye la cadena editorial: director, "
         "propietario, imprenta, distribución, precio, tiraje si está disponible. ¿Qué dice "
         "esto sobre el modelo de negocio y la sostenibilidad de la publicación en el "
         "mercado editorial colombiano?"),
    ],
    "res": [
        ("Síntesis interpretativa del corpus",
         "Con base en todos los resultados (OCR, segmentación, temas LDA, imágenes, red de autoría), "
         "elabora una síntesis interpretativa del perfil editorial. ¿Qué hipótesis de investigación "
         "surgen? ¿Qué preguntas quedan abiertas para trabajo cualitativo de archivo?"),
        ("Contraste con la historiografía existente",
         "Contrasta los hallazgos cuantitativos con lo que la historiografía dice sobre esta "
         "publicación o el período. ¿Los datos confirman, matizan o contradicen las interpretaciones "
         "existentes? Sugiere líneas de investigación novedosas derivadas del análisis computacional."),
        ("Sección metodológica para publicación académica",
         "Redacta una sección de metodología (500 palabras) que describa el proceso de análisis "
         "computacional realizado, los datos cuantitativos más relevantes, y las decisiones "
         "metodológicas. Calibra el tono para una revista de humanidades digitales o historia "
         "de la prensa latinoamericana."),
    ],
}


# ── Paneles extraídos del monolito (paso 7 de las recomendaciones) ───────────
# Cada pestaña vive en paneles/<pestaña>.py como mixin; aquí solo se componen.
from paneles.analisis import PanelAnalisis  # noqa: E402
from paneles.bitacora import PanelBitacora  # noqa: E402
from paneles.entidades import PanelEntidades  # noqa: E402
from paneles.etiquetador_zonas import PanelEtiquetadorZonas  # noqa: E402
from paneles.linguistica import PanelLinguistica  # noqa: E402
from paneles.normalizar import PanelNormalizar  # noqa: E402
from paneles.ocr import PanelOCR  # noqa: E402
from paneles.resultados import PanelResultados  # noqa: E402

_PANELES_MIXIN = (
    PanelAnalisis,
    PanelBitacora,
    PanelEntidades,
    PanelEtiquetadorZonas,
    PanelLinguistica,
    PanelNormalizar,
    PanelOCR,
    PanelResultados,
)


class BashkarApp(*_PANELES_MIXIN, tk.Tk):

    # ── Definición de páginas del sidebar ─────────────────────────────────────
    # Formato: (id, emoji, label, label_largo, badge_attr, grupo)
    # grupo:
    #   "flujo"     → pasos numerados del flujo principal
    #   "analisis"  → herramientas de análisis (sin número, opcionales)
    #   "salida"    → exportación y colaboración
    _PAGINAS = [
        # ── INICIO (tablero de investigación; grupo propio para no numerarse) ─
        ("inicio","⌂",   "Inicio",         "Panel de investigación",             None,        "inicio"),
        # ── FLUJO PRINCIPAL (numerado, secuencial) ────────────────────────────
        ("cfg",   "⚙",   "Configuración",  "Configuración del corpus",           None,        "flujo"),
        ("etz",   "✏️",  "Etiquetar",      "Etiquetar zonas de página (opcional)","etz_done",  "flujo"),
        ("ocr",   "📄",  "Extracción OCR", "Extracción de texto por OCR",         "ocr_done",  "flujo"),
        ("conv",  "⚡",  "Conversor PDF",  "Conversión masiva PDF→Word/TXT (texto embebido)", None, "flujo"),
        ("mmx",   "🧠",  "Extracción IA",  "Extracción multimodal estructurada de imágenes (IA de visión → JSON → .md)", None, "flujo"),
        ("norm",  "📝",  "Normalizar",     "Revisión y normalización del texto",  "norm_done", "flujo"),
        ("seg",   "📋",  "Segmentar",      "Segmentación en artículos",           "seg_done",  "flujo"),
        ("anal",  "🔬",  "Analizar",       "Análisis textual y semántico",        "anal_done", "flujo"),
        ("res",   "📈",  "Resultados",     "Resultados y exportación",            None,        "flujo"),
        # ── ANÁLISIS OPCIONALES ────────────────────────────────────────────────
        ("ner",   "🏷",  "Entidades",      "Índice de entidades nombradas",       "ner_done",  "analisis"),
        ("anot",  "✍️", "Anotar",         "Anotación semántica revisable",       None,        "analisis"),
        ("bsem",  "🔍",  "Búsqueda",       "Búsqueda semántica por similitud",    None,        "analisis"),
        ("coloc", "🔤",  "Collocates",     "Redes léxicas y concordancias",       None,        "analisis"),
        ("nov",   "🆕",  "Novedad",        "Detección de novedad y cambio discursivo", None,   "analisis"),
        ("red",   "🕸",  "Redes",          "Redes de co-ocurrencia",              None,        "analisis"),
        ("ling",  "🔭",  "Lingüística",    "Sintaxis, correferencia, morfología, encuadre, polaridad, revisión NER y validación", None, "analisis"),
        ("sem",   "🧠",  "Semántico",      "Tono, léxico y estilo",               None,        "analisis"),
        ("top",   "🧩",  "Tópicos",        "Topic modeling del corpus",           None,        "analisis"),
        ("viz",   "🎨",  "Visualizar",     "Visualizaciones avanzadas",           None,        "analisis"),
        ("comp",  "📊",  "Comparativo",    "Análisis comparativo interno",        "comp_done", "analisis"),
        ("comp2", "🔀",  "Multi-corpus",   "Comparación entre proyectos",         None,        "analisis"),
        ("intxt", "🔗",  "Intertexto",     "Análisis intertextual",               None,        "analisis"),
        ("meta",  "🌐",  "Metadatos URL",  "Metadatos desde URL externa",         None,        "analisis"),
        ("vis",   "🖼",  "Tipografía",     "Visual y tipografía",                 "vis_done",  "analisis"),
        ("imgdesc","🎨", "Desc. imágenes", "Descripción e iconografía de imágenes etiquetadas", None, "analisis"),
        # ── SALIDA Y COLABORACIÓN ──────────────────────────────────────────────
        ("bench", "⚖️", "Benchmark OCR",  "Compara rutas de OCR contra un estándar de oro (CER/WER)", None, "salida"),
        ("rep",   "📝",  "Reporte",        "Reporte narrativo (IA)",              None,        "salida"),
        ("dash",  "📊",  "Dashboard",      "Dashboard ejecutivo",                 None,        "salida"),
        ("valid", "✅",  "Validar",        "Validación humana y semáforo",        None,        "salida"),
        ("colab", "👥",  "Colaborar",      "Colaboración y trazabilidad",         None,        "salida"),
    ]

    # Lista plana de ids para compatibilidad con código que itera _PAGINAS
    @classmethod
    def _paginas_ids(cls):
        return [p[0] for p in cls._PAGINAS]

    def __init__(self):
        super().__init__()
        # Sin consola en el .exe: todo error de callback/hilo va al registro.
        from core import registro_errores
        registro_errores.instalar(self)
        self.title(f"{APP_NAME} v{APP_VERSION} — Análisis Editorial Computacional")
        self.geometry("1280x820")
        self.minsize(1024, 680)
        self.configure(bg=SB_BG)
        _estilos()
        self._q             = queue.Queue()
        # Arranca en el tablero: _activar_contexto compara contra este valor
        # para no navegar antes de que existan los frames de página.
        self._pagina_activa = tk.StringVar(value="inicio")
        self._frames_pagina = {}
        self._sb_btns       = {}
        self._proyecto_ruta = None      # Path del .bashkar activo
        self._historial_ia  = []        # [{tab,prompt,respuesta,fecha}]
        self._hay_cambios   = False     # indica cambios sin guardar
        self._cp_win        = None      # ventana Command Palette
        self._toasts_activos: list = [] # toasts visibles
        self._build_ui()
        self._poll()
        self.protocol("WM_DELETE_WINDOW", self._on_cerrar)
        # Restaurar última sesión
        self.after(200, self._cargar_ultimo_proyecto)
        # Autoguardado periódico cada 3 min
        self.after(180_000, self._autoguardar_periodico)
        # Bind global Ctrl+K → Command Palette
        self.bind_all("<Control-k>", self._abrir_command_palette)

    # ── Cola de mensajes ──────────────────────────────────────────────────────
    def _poll(self):
        try:
            while True:
                m = self._q.get_nowait()
                t = m.get("tipo")
                if   t == "log":  self._log(m["texto"], m.get("color","#B5B6B3"))
                elif t == "prog": self._set_prog(m["val"], m.get("txt",""))
                elif t == "fase": self._lbl_fase.config(text=m["txt"])
                elif t == "ok":   self._on_ok(m.get("res"))
                elif t == "err":  messagebox.showerror("Error", m["txt"])
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _put(self, **kw): self._q.put(kw)

    # ─────────────────────────────────────────────────────────────────────────
    # CONSTRUCCIÓN DE LA UI
    # ─────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Layout raíz: topbar + body ────────────────────────────────────────
        self.configure(bg=AB_BG)
        root_frame = tk.Frame(self, bg=AB_BG)
        root_frame.pack(fill="both", expand=True)

        # ── TOPBAR (barra superior fija) ──────────────────────────────────────
        self._topbar = tk.Frame(root_frame, bg=TOPBAR_BG, height=TOPBAR_H)
        self._topbar.pack(side="top", fill="x")
        self._topbar.pack_propagate(False)
        self._build_topbar()

        # ── Separador visual topbar/body ──────────────────────────────────────
        tk.Frame(root_frame, bg=CARD_BOR, height=1).pack(side="top", fill="x")

        # ── BODY: activity bar + sidebar + contenido ──────────────────────────
        body = tk.Frame(root_frame, bg=AB_BG)
        body.pack(side="top", fill="both", expand=True)

        # Activity Bar (60px, íconos)
        self._activity_bar = tk.Frame(body, bg=AB_BG, width=60)
        self._activity_bar.pack(side="left", fill="y")
        self._activity_bar.pack_propagate(False)

        # Separador activity bar / sidebar
        tk.Frame(body, bg=CARD_BOR, width=1).pack(side="left", fill="y")

        # Sidebar de sub-items (200px)
        self._sidebar = tk.Frame(body, bg=SB_BG, width=200)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        # Separador sidebar / contenido
        tk.Frame(body, bg=CARD_BOR, width=1).pack(side="left", fill="y")

        # Área de contenido
        self._content_area = tk.Frame(body, bg=CONTENT_BG)
        self._content_area.pack(side="left", fill="both", expand=True)

        # El sidebar primero: la activity bar lo puebla al activar su contexto,
        # y si se construyera después dejaría sus referencias apuntando a
        # widgets vacíos.
        self._build_sidebar()
        self._build_activity_bar()

        # Crear todos los frames de página (apilados, solo uno visible)
        builds = {
            "inicio": self._build_inicio,
            "cfg":  self._build_cfg,
            "ocr":  self._build_ocr,
            "etz":  self._build_etz,
            "conv": self._build_conv,
            "mmx":  self._build_mmx,
            "norm": self._build_norm,
            "seg":  self._build_seg,
            "anal": self._build_anal,
            "vis":     self._build_vis,
            "imgdesc": self._build_imgdesc,
            "comp": self._build_comp,
            "meta": self._build_meta,
            "res":  self._build_res,
            "ner":  self._build_ner,
            "anot": self._build_anot,
            "bsem": self._build_busqueda_semantica,
            "coloc":self._build_coloc,
            "nov":  self._build_nov,
            "red":  self._build_red,
            "ling": self._build_ling,
            "sem":  self._build_sem,
            "top":  self._build_top,
            "viz":  self._build_viz,
            "bench": self._build_bench,
            "rep":   self._build_rep,
            "dash":  self._build_dash,
            "comp2": self._build_comp2,
            "intxt": self._build_intxt,
            "valid": self._build_valid,
            "colab": self._build_colab,
        }
        # Cada página vive dentro de un Canvas con scrollbar vertical, para que
        # los módulos altos (guía + estadísticas + opciones + botones) siempre
        # sean navegables aunque no quepan en la ventana. `_frames_pagina[pid]`
        # es el frame INTERIOR desplazable (donde cada _build_* hace pack); el
        # contenedor externo (canvas+scrollbar) se guarda en `_contenedores_pagina`.
        self._contenedores_pagina = {}
        for pid, _, _, _, _, _ in self._PAGINAS:
            frm = self._crear_pagina_scrollable(pid)
            self._frames_pagina[pid] = frm
            # Compatibilidad con código legacy que usa self._tab_XXX
            setattr(self, f"_tab_{pid}", frm)
        # Alias legacy
        self._tab_cfg  = self._frames_pagina["cfg"]
        self._tab_ocr  = self._frames_pagina["ocr"]
        self._tab_norm = self._frames_pagina["norm"]
        self._tab_seg  = self._frames_pagina["seg"]
        self._tab_anal = self._frames_pagina["anal"]
        self._tab_vis  = self._frames_pagina["vis"]
        self._tab_comp = self._frames_pagina["comp"]
        self._tab_meta = self._frames_pagina["meta"]
        self._tab_res  = self._frames_pagina["res"]
        self._tab_ner  = self._frames_pagina["ner"]
        self._tab_red  = self._frames_pagina["red"]
        self._tab_sem  = self._frames_pagina["sem"]
        self._tab_top  = self._frames_pagina["top"]
        self._tab_viz  = self._frames_pagina["viz"]
        self._tab_rep  = self._frames_pagina["rep"]
        self._tab_dash = self._frames_pagina["dash"]

        # Construir contenido. Fijamos el id de página actual ANTES de cada
        # build_fn para que _page_header pueda inyectar la guía del módulo
        # (qué es / para qué / cómo interpretar) sin tocar cada _build_*.
        for pid, build_fn in builds.items():
            self._guia_pagina_actual = pid
            build_fn()
        self._guia_pagina_actual = None

        # Mostrar página inicial: el tablero de investigación
        self._mostrar_pagina("inicio")

        # ── BARRA DE ESTADO ───────────────────────────────────────────────────
        sb = tk.Frame(self, bg=TOPBAR_BG, height=26)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)
        tk.Frame(sb, bg=CARD_BOR, height=1).pack(fill="x", side="top")
        self._lbl_status = tk.Label(sb, text="  ✓ Listo",
                                     bg=TOPBAR_BG, fg=TXT_SEC,
                                     font=("Segoe UI", 8))
        self._lbl_status.pack(side="left", padx=10, pady=3)
        tk.Label(sb, text="◇  Todo se procesa en tu equipo",
                 bg=TOPBAR_BG, fg=VERDE,
                 font=("Segoe UI", 8)).pack(side="left", padx=10)
        tk.Label(sb, text=f"Bashkar Station v{APP_VERSION}",
                 bg=TOPBAR_BG, fg=TXT_DIM,
                 font=("Segoe UI", 8)).pack(side="right", padx=10)

    # ── SIDEBAR ───────────────────────────────────────────────────────────────
    # ══════════════════════════════════════════════════════════════════════════
    # TOPBAR
    # ══════════════════════════════════════════════════════════════════════════
    def _build_topbar(self):
        tb = self._topbar

        # El grupo derecho se empaqueta PRIMERO: pack reparte por orden, y con
        # un nombre de proyecto largo la marca y las pastillas se comían el
        # ancho, dejando los botones de la derecha fuera de la ventana.
        right = tk.Frame(tb, bg=TOPBAR_BG)
        right.pack(side="right", padx=12)

        # ── Marca: la B de cobre en serif, el nombre y el descriptor ──────────
        logo_grp = tk.Frame(tb, bg=TOPBAR_BG)
        logo_grp.pack(side="left", padx=(16, 0))
        tk.Label(logo_grp, text="B", bg=TOPBAR_BG, fg=AZ3,
                 font=(_T.FONT_DISPLAY, 20, "bold")).pack(side="left",
                                                          padx=(0, 8))
        marca_txt = tk.Frame(logo_grp, bg=TOPBAR_BG)
        marca_txt.pack(side="left")
        tk.Label(marca_txt, text="BASHKAR STATION", bg=TOPBAR_BG, fg=TXT_PRI,
                 font=(_T.FONT_DISPLAY, 10, "bold")).pack(anchor="w")
        tk.Label(marca_txt, text="Plataforma de análisis editorial",
                 bg=TOPBAR_BG, fg=TXT_SEC,
                 font=("Segoe UI", 7)).pack(anchor="w")

        # Separador
        tk.Frame(tb, bg=CARD_BOR, width=1).pack(side="left", fill="y",
                                                  pady=12, padx=14)

        # Nombre del proyecto activo
        self._lbl_pub_hdr = tk.Label(tb, text="Sin proyecto",
                                      bg=TOPBAR_BG, fg=SB_TXT2,
                                      font=(_T.FONT_DISPLAY, 11))
        self._lbl_pub_hdr.pack(side="left", padx=4)

        # Pastillas de estado: dónde se procesa y si la IA externa está activa.
        self._pastillas = tk.Frame(tb, bg=TOPBAR_BG)
        self._pastillas.pack(side="left", padx=14)
        self._mk_pastilla("◆", "Procesamiento local", AZ_INFO, INFO_BG)
        self._pill_ia = self._mk_pastilla("×", "IA externa desactivada",
                                          TXT_DIM, AZ2)

        # ── Lado derecho: switch IA + botones proyecto ────────────────────────
        # Botón Dark / Light mode
        self._btn_theme = tk.Label(right, text="☀ Claro", bg=TOPBAR_BG,
                                    fg=TXT_SEC, font=("Segoe UI", 8),
                                    cursor="hand2", padx=8, pady=2,
                                    relief="solid", bd=1)
        self._btn_theme.pack(side="right", padx=(0, 6))
        self._btn_theme.bind("<Button-1>", lambda e: self._toggle_theme())
        self._btn_theme.bind("<Enter>",
            lambda e: self._btn_theme.config(fg=TXT_PRI))
        self._btn_theme.bind("<Leave>",
            lambda e: self._btn_theme.config(fg=TXT_SEC))

        tk.Frame(right, bg=CARD_BOR, width=1).pack(side="right", fill="y",
                                                     pady=6, padx=4)

        # Switch IA — siempre visible
        self._var_ia_habilitada = tk.BooleanVar(
            value=getattr(ST, "ia_habilitada", False))
        ia_frame = tk.Frame(right, bg=TOPBAR_BG)
        ia_frame.pack(side="right", padx=(8, 0))

        self._lbl_ia_topbar = tk.Label(ia_frame, bg=TOPBAR_BG,
                                        font=("Segoe UI", 8, "bold"),
                                        cursor="hand2")
        self._lbl_ia_topbar.pack(side="left", padx=(0, 4))
        self._lbl_ia_topbar.bind("<Button-1>", lambda e: self._topbar_toggle_ia())

        ttk.Checkbutton(ia_frame, text="IA",
                         variable=self._var_ia_habilitada,
                         command=self._topbar_toggle_ia).pack(side="left")

        self._topbar_toggle_ia()  # inicializar etiqueta

        # Separador
        tk.Frame(right, bg=CARD_BOR, width=1).pack(side="right", fill="y",
                                                     pady=6, padx=8)

        # Botones de proyecto
        for txt, cmd in [("💾", self._guardar_proyecto),
                          ("📂", self._abrir_gestor_proyectos),
                          ("➕", self._nuevo_proyecto_dialogo)]:
            b = tk.Label(right, text=txt, bg=TOPBAR_BG, fg=TXT_SEC,
                         font=("Segoe UI", 12), cursor="hand2", padx=6)
            b.pack(side="right")
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>", lambda e, w=b: w.config(fg=TXT_PRI))
            b.bind("<Leave>", lambda e, w=b: w.config(fg=TXT_SEC))

        # Botón análisis rápido (modo sin proyecto)
        b_adhoc = tk.Label(right, text="⚡", bg=TOPBAR_BG, fg=TXT_SEC,
                           font=("Segoe UI", 12), cursor="hand2", padx=6)
        b_adhoc.pack(side="right")
        b_adhoc.bind("<Button-1>", lambda e: self._modo_adhoc())
        b_adhoc.bind("<Enter>",    lambda e: b_adhoc.config(fg="#E6A64C"))
        b_adhoc.bind("<Leave>",    lambda e: b_adhoc.config(fg=TXT_SEC))
        self._mk_ayuda_topbar(b_adhoc, "⚡ Análisis rápido sin proyecto\n"
                                        "Carga una carpeta de TXT directamente.")

        # Separador + botón Bitácora + botón Command Palette
        tk.Frame(right, bg=CARD_BOR, width=1).pack(
            side="right", fill="y", pady=6, padx=4)
        self._btn_bitacora = tk.Label(
            right, text="📓", bg=TOPBAR_BG, fg=TXT_SEC,
            font=("Segoe UI", 13), cursor="hand2", padx=6)
        self._btn_bitacora.pack(side="right")
        self._btn_bitacora.bind("<Button-1>", lambda e: self._bitacora_abrir())
        self._btn_bitacora.bind("<Enter>",
            lambda e: self._btn_bitacora.config(fg=TXT_PRI))
        self._btn_bitacora.bind("<Leave>",
            lambda e: self._btn_bitacora.config(fg=TXT_SEC))
        self._bitacora_win = None   # referencia a la ventana flotante
        # Caché del BitacoraEngine y la base a la que apunta. NO llamarlo
        # _bitacora_engine: así se llama el método, y el atributo lo tapaba
        # (la bitácora fallaba con TypeError en cada uso).
        self._bitacora_eng_cache = None
        self._bitacora_eng_db = None

        # Botón Command Palette
        self._btn_cp = tk.Label(
            right, text="⌨", bg=TOPBAR_BG, fg=TXT_SEC,
            font=("Segoe UI", 13), cursor="hand2", padx=6)
        self._btn_cp.pack(side="right")
        self._btn_cp.bind("<Button-1>", self._abrir_command_palette)
        self._btn_cp.bind("<Enter>", lambda e: self._btn_cp.config(fg=AZ4))
        self._btn_cp.bind("<Leave>", lambda e: self._btn_cp.config(fg=TXT_SEC))
        self._mk_ayuda_topbar(self._btn_cp, "⌨  Command Palette\nCtrl+K — busca y ejecuta cualquier acción")

    def _set_pub_hdr(self, texto: str):
        """Escribe el nombre del proyecto en la topbar Y en el sidebar."""
        for attr in ("_lbl_pub_hdr", "_lbl_pub_sb"):
            widget = getattr(self, attr, None)
            if widget is None:
                continue
            try:
                widget.config(text=texto)
            except Exception:
                pass

    def _mk_pastilla(self, simbolo: str, texto: str, fg: str, bg: str):
        """
        Pastilla de estado de la topbar (fondo tintado + texto del mismo tono).

        Devuelve la terna de widgets para poder repintarla sin reconstruirla.
        """
        marco = tk.Frame(self._pastillas, bg=bg, padx=8, pady=3)
        marco.pack(side="left", padx=3)
        lbl_sim = tk.Label(marco, text=simbolo, bg=bg, fg=fg,
                           font=("Segoe UI", 7))
        lbl_sim.pack(side="left", padx=(0, 4))
        lbl_txt = tk.Label(marco, text=texto, bg=bg, fg=fg,
                           font=("Segoe UI", 7, "bold"))
        lbl_txt.pack(side="left")
        return (marco, lbl_sim, lbl_txt)

    def _pintar_pastilla(self, pastilla, simbolo: str, texto: str,
                          fg: str, bg: str):
        marco, lbl_sim, lbl_txt = pastilla
        marco.config(bg=bg)
        lbl_sim.config(text=simbolo, fg=fg, bg=bg)
        lbl_txt.config(text=texto, fg=fg, bg=bg)

    def _mk_ayuda_topbar(self, widget, texto: str):
        """Tooltip simple para widgets de la topbar."""
        tip = [None]
        def _show(e):
            try:
                if tip[0]: tip[0].destroy()
                x = widget.winfo_rootx()
                y = widget.winfo_rooty() + widget.winfo_height() + 4
                w = tk.Toplevel(self); w.wm_overrideredirect(True)
                w.geometry(f"+{x}+{y}"); w.configure(bg=CARD_BOR)
                tk.Label(w, text=texto, bg=AZ2, fg=TXT_PRI,
                         font=("Segoe UI", 8), padx=8, pady=4,
                         justify="left").pack()
                tip[0] = w
            except Exception: pass
        def _hide(e):
            try:
                if tip[0]: tip[0].destroy(); tip[0] = None
            except Exception: pass
        widget.bind("<Enter>", _show); widget.bind("<Leave>", _hide)

    def _modo_adhoc(self):
        """Carga una carpeta de TXT directamente sin crear proyecto .bashkar."""
        from tkinter import filedialog
        carpeta = filedialog.askdirectory(
            title="Seleccionar carpeta con archivos .txt para análisis rápido")
        if not carpeta:
            return
        carpeta = Path(carpeta)
        txts = sorted(carpeta.rglob("*.txt"))
        if not txts:
            messagebox.showwarning("Sin archivos",
                                   f"No se encontraron archivos .txt en:\n{carpeta}")
            return

        # Cargar textos directamente en ST sin pipeline OCR
        corpus_txt = []
        corpus_meta = {}
        for i, p in enumerate(txts):
            try:
                texto = p.read_text(encoding="utf-8", errors="replace")
                corpus_txt.append(texto)
                corpus_meta[str(i)] = {
                    "titulo": p.stem,
                    "numero": p.parent.name,
                    "pagina": p.stem,
                    "art_id": str(i),
                }
            except Exception:
                continue

        ST.corpus_txt  = corpus_txt
        ST.corpus_meta = corpus_meta
        ST.out_dir     = carpeta
        ST.pdf_dir     = carpeta
        ST.publicacion = carpeta.name
        ST.archivos_sel = list(txts)
        ST.ocr_done = True
        ST.marcar_etapa("ocr", "ready")
        self._actualizar_badges()

        # Actualizar etiqueta de proyecto
        self._set_pub_hdr(
            f"⚡ {carpeta.name}  ·  {len(txts)} archivos (modo ad-hoc)")
        if hasattr(self, "_lbl_proyecto"):
            try:
                self._lbl_proyecto.config(text=f"⚡ {carpeta.name}")
            except Exception:
                pass

        messagebox.showinfo(
            "Corpus cargado ⚡",
            f"✅ {len(corpus_txt)} archivos TXT cargados.\n\n"
            f"Carpeta: {carpeta}\n\n"
            f"Puedes ir directamente a:\n"
            f"  · Segmentar — dividir en artículos\n"
            f"  · Collocates — análisis léxico\n"
            f"  · Búsqueda semántica — buscar en el corpus\n\n"
            f"(No se creó proyecto .bashkar — los resultados no se guardan automáticamente)")
        self._mostrar_pagina("coloc")

    def _toggle_theme(self):
        global _MODO_OSCURO
        _MODO_OSCURO = not _MODO_OSCURO
        paleta = _PALETA_DARK if _MODO_OSCURO else _PALETA_LIGHT
        _aplicar_paleta(paleta)
        # Los tokens de ui_redesign son la misma paleta con otros nombres: si no
        # se reescriben, el panel Inicio se queda oscuro dentro de una ventana
        # clara (se repinta más abajo, cuando ya están los colores nuevos).
        from ui_redesign import aplicar_tema
        aplicar_tema(paleta)

        icono = "☀ Claro" if _MODO_OSCURO else "🌙 Oscuro"
        self._btn_theme.config(text=icono)

        # Repintar todos los widgets conocidos recursivamente
        bg_main  = paleta["CONTENT_BG"]
        bg_card  = paleta["CARD_BG"]
        bg_sb    = paleta["SB_BG"]
        bg_ab    = paleta["AB_BG"]
        bg_top   = paleta["TOPBAR_BG"]
        fg_pri   = paleta["TXT_PRI"]
        fg_sec   = paleta["TXT_SEC"]
        fg_dim   = paleta["TXT_DIM"]
        bor      = paleta["CARD_BOR"]

        # Traducción color viejo → color nuevo, generada de las dos paletas: la
        # que se deja y la que entra. Antes era una tabla escrita a mano que
        # perseguía cinco generaciones de colores incrustados; ahora la paleta
        # está unificada y la tabla se deduce sola, clave por clave.
        anterior = _PALETA_LIGHT if _MODO_OSCURO else _PALETA_DARK
        _CLAVES_BG = ("CONTENT_BG", "AZ1", "CARD_BG", "AZ2", "GRIS", "SB_BG",
                      "TOPBAR_BG", "SB_HOV", "SB_SEL", "CARD_BOR",
                      "READY_BG", "INFO_BG", "WARN_BG", "ERR_BG",
                      "TEAL_BG", "PURP_BG")
        _CLAVES_FG = ("TXT_PRI", "SB_TXT2", "SB_TXT", "TXT_SEC", "GRIS2",
                      "TXT_DIM", "AZ3", "HDR_LINE", "AZ4", "ACENT", "AZ_INFO",
                      "VERDE", "TEAL", "PURPURA", "ROJO")
        _DARK_BG_MAP = {anterior[k]: paleta[k] for k in _CLAVES_BG
                        if k in anterior and k in paleta}
        _DARK_FG_MAP = {anterior[k]: paleta[k] for k in _CLAVES_FG
                        if k in anterior and k in paleta}
        _DARK_FG_MAP["white"] = fg_pri

        def _repintar(widget):
            try:
                cls = widget.winfo_class()

                if cls in ("Frame", "Canvas"):
                    try:
                        cur = widget.cget("bg")
                        widget.config(bg=_DARK_BG_MAP.get(cur, bg_main))
                    except Exception:
                        pass

                elif cls == "Label":
                    try:
                        cur_bg = widget.cget("bg")
                        cur_fg = widget.cget("fg")
                        widget.config(
                            bg=_DARK_BG_MAP.get(cur_bg, cur_bg),
                            fg=_DARK_FG_MAP.get(cur_fg, cur_fg))
                    except Exception:
                        pass

                elif cls in ("Text",):
                    try:
                        widget.config(bg=bg_card, fg=fg_pri,
                                      insertbackground=fg_pri)
                    except Exception:
                        pass

                elif cls == "Entry":
                    try:
                        cur_bg = widget.cget("bg")
                        widget.config(
                            bg=_DARK_BG_MAP.get(cur_bg, bg_card),
                            fg=fg_pri,
                            insertbackground=fg_pri,
                            relief="solid", bd=1)
                    except Exception:
                        pass

                elif cls == "Listbox":
                    try:
                        widget.config(bg=bg_card, fg=fg_pri,
                                      selectbackground=paleta["SB_SEL"],
                                      selectforeground="#E8E5DF")
                    except Exception:
                        pass

                elif cls == "Spinbox":
                    try:
                        widget.config(bg=bg_card, fg=fg_pri,
                                      insertbackground=fg_pri)
                    except Exception:
                        pass

            except Exception:
                pass
            for child in widget.winfo_children():
                _repintar(child)

        _repintar(self)

        # Actualizar sidebar y activity bar explícitamente
        self.configure(bg=bg_sb)
        if hasattr(self, "_activity_bar"):
            self._activity_bar.config(bg=bg_ab)
        if hasattr(self, "_sidebar"):
            self._sidebar.config(bg=bg_sb)
        if hasattr(self, "_topbar"):
            self._topbar.config(bg=bg_top)
        if hasattr(self, "_content_area"):
            self._content_area.config(bg=bg_main)

        # Actualizar estilos ttk (Combobox, Entry, Treeview, Button)
        style = ttk.Style(self)
        style.configure("TCombobox",
            fieldbackground=bg_card, background=bg_card,
            foreground=fg_pri, selectbackground=paleta["SB_SEL"],
            selectforeground=fg_pri, arrowcolor=fg_sec)
        style.configure("TEntry",
            fieldbackground=bg_card, foreground=fg_pri,
            insertcolor=fg_pri, bordercolor=bor)
        style.configure("TSpinbox",
            fieldbackground=bg_card, foreground=fg_pri,
            background=bg_card, arrowcolor=fg_sec)
        style.configure("Treeview",
            background=bg_card, foreground=fg_pri,
            fieldbackground=bg_card, rowheight=24)
        style.configure("Treeview.Heading",
            background=bg_card, foreground=fg_sec,
            relief="flat")
        style.map("Treeview",
            background=[("selected", paleta["SB_SEL"])],
            foreground=[("selected", "#E8E5DF")])
        style.configure("TScrollbar",
            background=bg_card, troughcolor=bg_main,
            arrowcolor=fg_sec)
        style.configure("TNotebook",
            background=bg_main, tabmargins=[2, 5, 2, 0])
        style.configure("TNotebook.Tab",
            background=bg_card, foreground=fg_sec,
            padding=[8, 4])
        style.map("TNotebook.Tab",
            background=[("selected", bg_main)],
            foreground=[("selected", fg_pri)])
        style.configure("TCheckbutton",
            background=bg_card, foreground=fg_pri)
        style.configure("TRadiobutton",
            background=bg_main, foreground=fg_pri)
        style.configure("TLabelframe",
            background=bg_card, foreground=fg_pri, bordercolor=bor)
        style.configure("TLabelframe.Label",
            background=bg_card, foreground=fg_pri)

        # La activity bar mantiene su franja oscura en los dos temas, así que
        # el repintado genérico no le sirve: se recolorea a mano. Primero el
        # logo, el separador, el espaciador y el botón de ayuda, que no están
        # en _ab_btns y se quedaban con el fondo del tema contrario.
        if hasattr(self, "_activity_bar"):
            for hijo in self._activity_bar.winfo_children():
                try:
                    hijo.config(bg=AB_BG)
                    if hijo.winfo_class() == "Label" and hijo.cget("text") != "⬡":
                        hijo.config(fg=AB_TXT)
                except tk.TclError:
                    pass
        for cid, widgets in getattr(self, "_ab_btns", {}).items():
            activo = (cid == self._ctx_activo.get())
            widgets["frm"].config(bg=AB_BG)
            widgets["ind"].config(bg=AB_IND if activo else AB_BG)
            widgets["lbl"].config(bg=AB_BG,
                                  fg=TXT_PRI if activo else AB_TXT)

        # Sidebar y tablero se reconstruyen enteros: es más fiable que repintar
        # widget por widget, y ambos saben rehacerse solos.
        self._poblar_sidebar_contexto(self._ctx_activo.get())
        self._inicio_refrescar()

        # Forzar redibujado de badges/semáforos
        self._actualizar_badges()

    def _topbar_toggle_ia(self):
        habilitada = self._var_ia_habilitada.get()
        ST.ia_habilitada = habilitada
        if habilitada:
            self._lbl_ia_topbar.config(text="● IA ON",  fg=VERDE)
        else:
            self._lbl_ia_topbar.config(text="○ IA OFF", fg=ROJO)
        # La pastilla dice lo mismo con palabras, para quien no interpreta el
        # punto: es la garantía de «esto no sale de tu equipo».
        if getattr(self, "_pill_ia", None):
            if habilitada:
                self._pintar_pastilla(self._pill_ia, "●",
                                      "IA externa activa", ACENT, WARN_BG)
            else:
                self._pintar_pastilla(self._pill_ia, "×",
                                      "IA externa desactivada", TXT_DIM, AZ2)
        # Sincronizar con el checkbox de Configuración si existe
        if hasattr(self, "_cfg_toggle_ia"):
            try:
                self._cfg_toggle_ia()
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════════════════════
    # ACTIVITY BAR
    # ══════════════════════════════════════════════════════════════════════════

    # Contextos del Activity Bar: (id_contexto, icono, tooltip, [pids_incluidos])
    _CONTEXTOS = [
        ("inicio",    "⌂",  "Inicio",      ["inicio"]),
        ("ingest",    "📥", "Ingestión",   ["cfg", "etz", "ocr", "conv", "mmx"]),
        ("normalize", "📝", "Normalizar",  ["norm"]),
        ("segment",   "✂", "Segmentar",   ["seg"]),
        ("analyze",   "🔬", "Analizar",    ["anal", "ner", "anot", "bsem",
                                             "coloc", "nov", "red", "ling",
                                             "sem", "top", "vis", "imgdesc"]),
        ("visualize", "🎨", "Visualizar",  ["viz", "comp", "comp2", "intxt"]),
        ("publish",   "📤", "Publicar",    ["bench", "rep", "dash", "valid", "colab"]),
        ("settings",  "⚙️", "Proyecto",    ["meta", "res"]),
    ]

    def _build_activity_bar(self):
        ab = self._activity_bar
        self._ctx_activo = tk.StringVar(value="inicio")
        self._ab_btns = {}

        # Logo pequeño en el tope
        tk.Label(ab, text="⬡", bg=AB_BG, fg=AB_SEL,
                 font=("Segoe UI", 16, "bold")).pack(pady=(10, 8))
        tk.Frame(ab, bg=CARD_BOR, height=1).pack(fill="x", padx=8, pady=(0, 8))

        # Botones de contexto
        for ctx_id, icono, tooltip, _ in self._CONTEXTOS:
            self._ab_btns[ctx_id] = self._make_ab_btn(ab, ctx_id, icono, tooltip)

        # Spacer
        tk.Frame(ab, bg=AB_BG).pack(fill="both", expand=True)

        # Botón ayuda al fondo
        help_b = tk.Label(ab, text="?", bg=AB_BG, fg=AB_TXT,
                          font=("Segoe UI", 11, "bold"), cursor="hand2",
                          width=3, pady=8)
        help_b.pack(pady=(0, 8))
        help_b.bind("<Button-1>", lambda e: self._abrir_docs())
        help_b.bind("<Enter>",    lambda e: help_b.config(fg=TXT_PRI))
        help_b.bind("<Leave>",    lambda e: help_b.config(fg=AB_TXT))

        # Activar contexto inicial
        self._activar_contexto("inicio")

    def _make_ab_btn(self, parent, ctx_id, icono, tooltip):
        frm = tk.Frame(parent, bg=AB_BG, cursor="hand2", width=60, height=56)
        frm.pack(fill="x")
        frm.pack_propagate(False)

        # Barra indicadora izquierda (3px, visible cuando activo)
        ind = tk.Frame(frm, bg=AB_BG, width=3)
        ind.pack(side="left", fill="y")

        # Ícono centrado
        lbl = tk.Label(frm, text=icono, bg=AB_BG, fg=AB_TXT,
                        font=("Segoe UI", 18), cursor="hand2")
        lbl.pack(expand=True)

        widgets = {"frm": frm, "ind": ind, "lbl": lbl}

        def _click(e, c=ctx_id):
            self._activar_contexto(c)
        def _enter(e, c=ctx_id):
            if self._ctx_activo.get() != c:
                lbl.config(fg=TXT_PRI)
                # Tooltip
                self._mostrar_tooltip(tooltip, frm)
        def _leave(e, c=ctx_id):
            if self._ctx_activo.get() != c:
                lbl.config(fg=AB_TXT)
            self._ocultar_tooltip()

        for w in (frm, lbl):
            w.bind("<Button-1>", _click)
            w.bind("<Enter>",    _enter)
            w.bind("<Leave>",    _leave)

        return widgets

    def _activar_contexto(self, ctx_id: str):
        self._ctx_activo.set(ctx_id)
        # Actualizar estilos activity bar
        for cid, widgets in self._ab_btns.items():
            if cid == ctx_id:
                widgets["frm"].config(bg=AB_BG)
                widgets["ind"].config(bg=AB_IND)
                widgets["lbl"].config(fg=TXT_PRI)
            else:
                widgets["frm"].config(bg=AB_BG)
                widgets["ind"].config(bg=AB_BG)
                widgets["lbl"].config(fg=AB_TXT)

        # Poblar el sidebar con los pids de este contexto
        self._poblar_sidebar_contexto(ctx_id)

        # Navegar al primer pid del contexto si ninguno está activo
        pids = next((c[3] for c in self._CONTEXTOS if c[0] == ctx_id), [])
        actual = self._pagina_activa.get()
        if actual not in pids and pids:
            self._mostrar_pagina(pids[0])

    def _mostrar_tooltip(self, texto: str, widget):
        """Tooltip simple junto al activity bar."""
        try:
            if hasattr(self, "_tooltip_win") and self._tooltip_win:
                self._tooltip_win.destroy()
            x = widget.winfo_rootx() + 64
            y = widget.winfo_rooty() + 16
            win = tk.Toplevel(self)
            win.wm_overrideredirect(True)
            win.geometry(f"+{x}+{y}")
            win.configure(bg=CARD_BOR)
            tk.Label(win, text=texto, bg=AZ2, fg=TXT_PRI,
                     font=("Segoe UI", 8), padx=8, pady=4).pack()
            self._tooltip_win = win
        except Exception:
            pass

    def _ocultar_tooltip(self):
        try:
            if hasattr(self, "_tooltip_win") and self._tooltip_win:
                self._tooltip_win.destroy()
                self._tooltip_win = None
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # SIDEBAR DE SUB-ITEMS
    # ══════════════════════════════════════════════════════════════════════════
    def _poblar_sidebar_contexto(self, ctx_id: str):
        """Limpia el sidebar y lo repuebla con los pids del contexto activo."""
        sb = self._sidebar
        for w in sb.winfo_children():
            w.destroy()
        # Ese bucle acaba de destruir la cabecera fija del sidebar: sin esto,
        # _set_pub_hdr escribiría sobre un widget muerto.
        self._lbl_pub_sb = None

        pids = next((c[3] for c in self._CONTEXTOS if c[0] == ctx_id), [])
        ctx_label = next((c[2] for c in self._CONTEXTOS if c[0] == ctx_id), "")

        # Eliminar de _sb_btns los pids que ya no están en el sidebar visible
        # para evitar .config() sobre widgets destruidos en iteraciones posteriores
        for old_pid in [p for p in self._sb_btns if p not in pids]:
            del self._sb_btns[old_pid]

        # Cabecera del contexto, rotulada en cobre como las secciones
        hdr = tk.Frame(sb, bg=SB_BG)
        hdr.pack(fill="x", padx=0, pady=0)
        tk.Label(hdr, text=ctx_label.upper(), bg=SB_BG, fg=AZ3,
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=16, pady=(14, 6))

        # Nombre del proyecto
        self._lbl_proyecto = tk.Label(sb, text=getattr(ST, "publicacion", "") or "Sin proyecto",
                                       bg=SB_BG, fg=TXT_SEC,
                                       font=("Segoe UI", 8),
                                       wraplength=180, justify="left")
        self._lbl_proyecto.pack(anchor="w", padx=16, pady=(0, 8))
        tk.Frame(sb, bg=CARD_BOR, height=1).pack(fill="x", padx=12, pady=(0, 4))

        # Área scrollable — canvas sin scrollbar visible
        canvas = tk.Canvas(sb, bg=SB_BG, highlightthickness=0, borderwidth=0)
        canvas.pack(fill="both", expand=True)

        inner = tk.Frame(canvas, bg=SB_BG)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        def _on_canvas(e):
            canvas.itemconfig(win_id, width=e.width)

        inner.bind("<Configure>", _on_inner)
        canvas.bind("<Configure>", _on_canvas)

        # Scroll con rueda del mouse
        def _on_wheel(e):
            delta = -1 if (e.delta > 0 or e.num == 4) else 1
            canvas.yview_scroll(delta, "units")

        canvas.bind("<MouseWheel>", _on_wheel)
        canvas.bind("<Button-4>",   _on_wheel)
        canvas.bind("<Button-5>",   _on_wheel)
        inner.bind("<MouseWheel>",  _on_wheel)
        inner.bind("<Button-4>",    _on_wheel)
        inner.bind("<Button-5>",    _on_wheel)

        # Buscar info de cada pid en _PAGINAS
        pag_info = {p[0]: p for p in self._PAGINAS}
        flujo_num = 1
        for pid in pids:
            info = pag_info.get(pid)
            if not info:
                continue
            _, emoji, label, _, badge_attr, grupo = info
            num = flujo_num if grupo == "flujo" else None
            btn = self._make_sb_btn(inner, pid, emoji, label, num,
                                    badge_attr, es_flujo=(grupo == "flujo"),
                                    scroll_fn=_on_wheel)
            self._sb_btns[pid] = btn
            if grupo == "flujo":
                flujo_num += 1

        # Actualizar estado activo
        actual = self._pagina_activa.get()
        for pid, widgets in self._sb_btns.items():
            self._aplicar_estilo_sb_btn(pid, widgets, pid == actual)

    def _build_sidebar(self):
        """
        Prepara el sidebar; el contenido lo pone `_poblar_sidebar_contexto`
        según el contexto elegido en la activity bar.

        Hasta la sesión 56 este método pintaba además la lista COMPLETA de los
        30 paneles, que el primer cambio de contexto borraba. El resultado, al
        arrancar, era un sidebar con dos listas y el nombre del proyecto
        repetido. Ahora hay un solo dueño de esa columna.
        """
        # Referencias que otros métodos consultan antes de que exista contenido.
        self._lbl_pub_sb = None
        self._lbl_proyecto = tk.Label(self._sidebar, text="Sin proyecto",
                                       bg=SB_BG, fg=TXT_SEC,
                                       font=("Segoe UI", 8),
                                       wraplength=180, justify="left")

    # ══════════════════════════════════════════════════════════════════════════
    # PANEL DE ASISTENTE IA (compartido por todas las pestañas de análisis)
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ai_panel(self, parent_frame: "tk.Frame", tab_id: str):
        """
        Construye el panel de asistente IA en la parte inferior de una pestaña.
        Debe llamarse ANTES de construir el contenido principal (pack side=bottom).
        """
        sugerencias = _AI_PROMPTS.get(tab_id, [])

        # Contenedor principal del panel — fondo oscuro tipo terminal
        panel = tk.Frame(parent_frame, bg="#101316", bd=0)
        panel.pack(fill="x", side="bottom")

        # ── Cabecera colapsable ───────────────────────────────────────────────
        hdr = tk.Frame(panel, bg="#14202A", cursor="hand2")
        hdr.pack(fill="x")
        self._ai_expanded = getattr(self, "_ai_expanded", {})
        self._ai_expanded[tab_id] = tk.BooleanVar(value=False)

        lbl_toggle = tk.Label(hdr,
            text="  🤖  Asistente IA  ▸  haz una pregunta sobre este análisis",
            bg="#14202A", fg="#6CA8E8", font=("Segoe UI", 9, "bold"),
            anchor="w", cursor="hand2")
        lbl_toggle.pack(side="left", fill="x", expand=True, pady=5, padx=8)
        lbl_chevron = tk.Label(hdr, text="▾", bg="#14202A", fg="#6CA8E8",
                                font=("Segoe UI", 11, "bold"))
        lbl_chevron.pack(side="right", padx=10)

        # ── Cuerpo (oculto por defecto) ───────────────────────────────────────
        body = tk.Frame(panel, bg="#101316")

        # Prompts sugeridos
        if sugerencias:
            sug_frame = tk.Frame(body, bg="#101316")
            sug_frame.pack(fill="x", padx=10, pady=(8, 0))
            tk.Label(sug_frame, text="Sugerencias:", bg="#101316", fg="#777F84",
                     font=("Segoe UI", 8, "bold")).pack(anchor="w")
            btn_row = tk.Frame(sug_frame, bg="#101316")
            btn_row.pack(fill="x", pady=(4, 0))
            for i, (label, prompt_txt) in enumerate(sugerencias):
                btn = tk.Label(btn_row, text=f"  {label}  ",
                               bg="#30291F", fg="#6CA8E8",
                               font=("Segoe UI", 8), relief="flat",
                               cursor="hand2", padx=6, pady=3)
                btn.grid(row=i//3, column=i%3, padx=3, pady=2, sticky="w")
                btn.bind("<Enter>", lambda e, b=btn: b.config(bg="#6CA8E8", fg="white"))
                btn.bind("<Leave>", lambda e, b=btn: b.config(bg="#30291F", fg="#6CA8E8"))
                btn.bind("<Button-1>",
                         lambda e, t=prompt_txt, tid=tab_id: self._set_ai_prompt(t, tid))

        # Área de texto del prompt
        txt_frame = tk.Frame(body, bg="#101316")
        txt_frame.pack(fill="x", padx=10, pady=(8, 0))
        tk.Label(txt_frame, text="Tu prompt:", bg="#101316", fg="#B5B6B3",
                 font=("Segoe UI", 8)).pack(anchor="w")

        prompt_txt_widget = tk.Text(txt_frame, height=3, font=("Segoe UI", 9),
                                     bg="#14202A", fg="#E8E5DF",
                                     insertbackground="#6CA8E8",
                                     relief="flat", bd=0,
                                     wrap="word", padx=8, pady=6)
        prompt_txt_widget.pack(fill="x", pady=(3, 0))
        prompt_txt_widget.insert("1.0",
            "Escribe tu pregunta o selecciona una sugerencia arriba…")
        prompt_txt_widget.config(fg="#777F84")

        def _on_focus_in(e):
            if prompt_txt_widget.get("1.0","end-1c") ==                "Escribe tu pregunta o selecciona una sugerencia arriba…":
                prompt_txt_widget.delete("1.0","end")
                prompt_txt_widget.config(fg="#E8E5DF")
        def _on_focus_out(e):
            if not prompt_txt_widget.get("1.0","end-1c").strip():
                prompt_txt_widget.insert("1.0",
                    "Escribe tu pregunta o selecciona una sugerencia arriba…")
                prompt_txt_widget.config(fg="#777F84")
        prompt_txt_widget.bind("<FocusIn>",  _on_focus_in)
        prompt_txt_widget.bind("<FocusOut>", _on_focus_out)

        # Botones de acción
        act_row = tk.Frame(body, bg="#101316")
        act_row.pack(fill="x", padx=10, pady=(6, 0))
        send_btn = tk.Label(act_row, text="  ▶  Enviar a IA  ",
                            bg="#6CA8E8", fg="white",
                            font=("Segoe UI", 9, "bold"),
                            cursor="hand2", padx=8, pady=4)
        send_btn.pack(side="left")
        send_btn.bind("<Enter>", lambda e: send_btn.config(bg="#6CA8E8"))
        send_btn.bind("<Leave>", lambda e: send_btn.config(bg="#6CA8E8"))

        clear_btn = tk.Label(act_row, text="  ✕ Limpiar  ",
                              bg="#30291F", fg="#B5B6B3",
                              font=("Segoe UI", 8), cursor="hand2",
                              padx=6, pady=4)
        clear_btn.pack(side="left", padx=(6, 0))
        clear_btn.bind("<Enter>", lambda e: clear_btn.config(bg="#30291F"))
        clear_btn.bind("<Leave>", lambda e: clear_btn.config(bg="#30291F"))

        lbl_proveedor = tk.Label(act_row, text="", bg="#101316", fg="#777F84",
                                  font=("Segoe UI", 7, "italic"))
        lbl_proveedor.pack(side="right", padx=8)

        # Área de respuesta
        resp_frame = tk.Frame(body, bg="#101316")
        resp_frame.pack(fill="x", padx=10, pady=(8, 0))
        resp_hdr = tk.Frame(resp_frame, bg="#14202A")
        resp_hdr.pack(fill="x")
        tk.Label(resp_hdr, text="  Respuesta de la IA",
                 bg="#14202A", fg="#B5B6B3",
                 font=("Segoe UI", 8, "bold")).pack(side="left", pady=3)
        self._ai_lbl_estado = getattr(self, "_ai_lbl_estado", {})
        lbl_estado = tk.Label(resp_hdr, text="", bg="#14202A", fg="#6EC69A",
                               font=("Segoe UI", 7, "italic"))
        lbl_estado.pack(side="right", padx=8)
        self._ai_lbl_estado[tab_id] = lbl_estado

        resp_txt = scrolledtext.ScrolledText(resp_frame, height=6,
                                              font=("Segoe UI", 9),
                                              bg="#12171B", fg="#E8E5DF",
                                              relief="flat",
                                              insertbackground="white",
                                              state="disabled", wrap="word")
        resp_txt.pack(fill="x", pady=(0, 0))

        # Separador inferior
        tk.Frame(body, bg="#30291F", height=1).pack(fill="x", pady=(8, 0))

        # ── Guardar referencias ───────────────────────────────────────────────
        if not hasattr(self, "_ai_widgets"):
            self._ai_widgets = {}
        self._ai_widgets[tab_id] = {
            "prompt": prompt_txt_widget,
            "resp":   resp_txt,
            "estado": lbl_estado,
            "prov":   lbl_proveedor,
        }

        # ── Toggle show/hide ──────────────────────────────────────────────────
        def _toggle(e=None):
            if body.winfo_ismapped():
                body.pack_forget()
                lbl_chevron.config(text="▾")
                lbl_toggle.config(text="  🤖  Asistente IA  ▸  haz una pregunta sobre este análisis")
            else:
                body.pack(fill="x", pady=(0, 4))
                lbl_chevron.config(text="▴")
                lbl_toggle.config(text="  🤖  Asistente IA")
                # Actualizar label de proveedor
                key = getattr(ST, "api_key", "")
                if key:
                    from core.image_describer import nombre_proveedor
                    lbl_proveedor.config(text=nombre_proveedor(key))
                else:
                    lbl_proveedor.config(text="⚠ Sin API key — configura en Sección 8")

        for w in (hdr, lbl_toggle, lbl_chevron):
            w.bind("<Button-1>", _toggle)

        # ── Botón enviar ──────────────────────────────────────────────────────
        send_btn.bind("<Button-1>",
                      lambda e, tid=tab_id: self._enviar_prompt_ia(tid))
        clear_btn.bind("<Button-1>",
                       lambda e, tid=tab_id: self._limpiar_respuesta_ia(tid))

    def _set_ai_prompt(self, texto: str, tab_id: str):
        """Rellena el área de texto del prompt con el texto sugerido."""
        widgets = getattr(self, "_ai_widgets", {}).get(tab_id)
        if not widgets: return
        w = widgets["prompt"]
        w.config(fg="#E8E5DF")
        w.delete("1.0", "end")
        w.insert("1.0", texto)
        w.focus_set()

    def _limpiar_respuesta_ia(self, tab_id: str):
        widgets = getattr(self, "_ai_widgets", {}).get(tab_id)
        if not widgets: return
        widgets["resp"].config(state="normal")
        widgets["resp"].delete("1.0", "end")
        widgets["resp"].config(state="disabled")
        widgets["estado"].config(text="")

    def _enviar_prompt_ia(self, tab_id: str):
        """Construye el contexto de la pestaña activa y llama a la IA."""
        widgets = getattr(self, "_ai_widgets", {}).get(tab_id)
        if not widgets:
            messagebox.showwarning("Panel IA", "Panel no inicializado."); return

        api_key, _modelo_ia = _resolver_api_key_modelo("asistente")
        api_key = api_key.strip()
        if not api_key:
            messagebox.showwarning(
                "Sin API key",
                "Configura una clave API en Sección 8 de Configuración.\n"
                "Compatible con Anthropic, OpenAI y Google Gemini."); return

        prompt = widgets["prompt"].get("1.0", "end-1c").strip()
        if not prompt or prompt == "Escribe tu pregunta o selecciona una sugerencia arriba…":
            messagebox.showwarning("Prompt vacío", "Escribe o selecciona un prompt."); return

        widgets["estado"].config(text="⏳ Consultando IA…", fg="#E6A64C")
        widgets["resp"].config(state="normal")
        widgets["resp"].delete("1.0", "end")
        widgets["resp"].insert("end", "⏳ Esperando respuesta…")
        widgets["resp"].config(state="disabled")

        # Construir contexto de la pestaña
        contexto = self._construir_contexto_ia(tab_id)

        prompt_snap = prompt  # capturar para historial
        def worker():
            try:
                respuesta = self._llamar_ia_texto(
                    api_key=api_key,
                    contexto=contexto,
                    prompt=prompt_snap,
                )
                self.after(0, lambda r=respuesta, tid=tab_id, p=prompt_snap:
                           self._mostrar_respuesta_ia(r, tid, ok=True, prompt_original=p))
            except Exception as e:
                self.after(0, lambda err=str(e), tid=tab_id:
                           self._mostrar_respuesta_ia(f"⚠️ Error: {err}", tid, ok=False))

        threading.Thread(target=worker, daemon=True).start()

    def _construir_contexto_ia(self, tab_id: str) -> str:
        """Genera un resumen del estado actual del análisis como contexto para la IA."""
        pub  = getattr(ST, "publicacion", "desconocida")
        per  = getattr(ST, "periodo", "")
        lineas = [
            f"Publicación analizada: {pub}" + (f" ({per})" if per else ""),
            f"Pestaña activa: {tab_id}",
        ]

        if tab_id == "ocr" and getattr(ST, "resumen_ocr", None):
            r = ST.resumen_ocr
            lineas.append(f"Archivos procesados: {r.get('n_archivos',0)}")
            lineas.append(f"Páginas totales: {r.get('n_paginas',0)}")
            lineas.append(f"Palabras extraídas: {r.get('n_palabras',0):,}")
            lineas.append(f"Confianza OCR media: {r.get('confianza_media',0):.1%}")

        elif tab_id == "seg" and getattr(ST, "df_articulos", None) is not None:
            df = ST.df_articulos
            lineas.append(f"Artículos segmentados: {len(df)}")
            if "autor" in df.columns:
                top_autores = df["autor"].value_counts().head(10)
                lineas.append("Top autores: " + ", ".join(
                    f"{a} ({n})" for a, n in top_autores.items() if a))
            if "seccion" in df.columns:
                secs = df["seccion"].value_counts().head(6)
                lineas.append("Secciones: " + ", ".join(f"{s} ({n})" for s, n in secs.items()))

        elif tab_id == "anal" and getattr(ST, "temas_lda", None):
            lineas.append("Temas LDA detectados:")
            for i, t in enumerate(ST.temas_lda[:6]):
                palabras = t.get("palabras", [])[:8]
                lineas.append(f"  Tema {i+1}: {', '.join(palabras)}")

        elif tab_id == "vis" and getattr(ST, "datos_imagenes", None):
            total_imgs = sum(
                len(pag.get("elementos", []))
                for datos in ST.datos_imagenes.values()
                for pag in datos.get("paginas", [])
            )
            lineas.append(f"Elementos visuales detectados: {total_imgs}")

        elif tab_id == "comp" and getattr(ST, "matriz_sim", None) is not None:
            lineas.append("Matriz de similitud calculada")
            if getattr(ST, "terminos_dist", None):
                dist = list(ST.terminos_dist.items())[:3]
                for nombre, terms in dist:
                    lineas.append(f"  Términos distintivos de {nombre}: "
                                   + ", ".join(terms[:8]))

        elif tab_id == "meta" and getattr(self, "_meta_actual", {}):
            meta = self._meta_actual
            for campo in ("titulo", "creador", "fecha", "editorial", "descripcion"):
                if meta.get(campo):
                    lineas.append(f"{campo.capitalize()}: {meta[campo]}")

        elif tab_id == "res" and getattr(ST, "df_articulos", None) is not None:
            df = ST.df_articulos
            lineas.append(f"Corpus completo: {len(df)} artículos analizados")
            if getattr(ST, "temas_lda", None):
                lineas.append(f"Temas LDA: {len(ST.temas_lda)}")
            if getattr(ST, "datos_imagenes", None):
                lineas.append(f"Números con análisis visual: {len(ST.datos_imagenes)}")

        if len(lineas) == 2:
            lineas.append("(Análisis aún no ejecutado — responde basándote en el contexto general de la publicación)")

        return "\n".join(lineas)

    def _llamar_ia_texto(self, api_key: str, contexto: str,
                          prompt: str, timeout: int = 60) -> str:
        """
        Llama a la IA con contexto + prompt y devuelve la respuesta como texto.
        Soporta Anthropic, OpenAI y Gemini.
        """
        import json
        import urllib.request

        from core.image_describer import detectar_proveedor

        proveedor = detectar_proveedor(api_key)

        system_msg = (
            "Eres un asistente experto en historia de la prensa colombiana, "
            "estudios editoriales latinoamericanos y humanidades digitales. "
            "Ayudas a investigadores a interpretar resultados de análisis "
            "computacional de publicaciones históricas. "
            "Responde siempre en español, de forma clara y académica, "
            "con referencias al contexto histórico colombiano cuando sea pertinente."
        )
        user_msg = (
            f"CONTEXTO DEL ANÁLISIS:\n{contexto}\n\n"
            f"PREGUNTA DEL INVESTIGADOR:\n{prompt}"
        )

        def _post(url, payload, headers):
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                          headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())

        if proveedor == "anthropic":
            data = _post(
                "https://api.anthropic.com/v1/messages",
                {"model": "claude-sonnet-4-20250514", "max_tokens": 1500,
                 "system": system_msg,
                 "messages": [{"role": "user", "content": user_msg}]},
                {"Content-Type": "application/json",
                 "x-api-key": api_key, "anthropic-version": "2023-06-01"})
            return data["content"][0]["text"].strip()

        elif proveedor == "openai":
            data = _post(
                "https://api.openai.com/v1/chat/completions",
                {"model": "gpt-4o", "max_tokens": 1500,
                 "messages": [{"role": "system", "content": system_msg},
                               {"role": "user", "content": user_msg}]},
                {"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"})
            return data["choices"][0]["message"]["content"].strip()

        elif proveedor == "gemini":
            url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                   f"gemini-1.5-flash:generateContent?key={api_key}")
            data = _post(url,
                {"contents": [{"parts": [{"text": system_msg + "\n\n" + user_msg}]}],
                 "generationConfig": {"maxOutputTokens": 1500, "temperature": 0.3}},
                {"Content-Type": "application/json"})
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()

        raise ValueError(f"Proveedor desconocido: {proveedor}")

    def _mostrar_respuesta_ia(self, texto: str, tab_id: str, ok: bool = True,
                               prompt_original: str = ""):
        widgets = getattr(self, "_ai_widgets", {}).get(tab_id)
        if not widgets: return
        widgets["resp"].config(state="normal")
        widgets["resp"].delete("1.0", "end")
        widgets["resp"].insert("end", texto)
        widgets["resp"].config(state="disabled")
        if ok:
            widgets["estado"].config(text="✓ Respuesta recibida", fg="#6EC69A")
            # Guardar en historial
            from datetime import datetime as _dt
            self._historial_ia.append({
                "tab":       tab_id,
                "prompt":    prompt_original,
                "respuesta": texto,
                "fecha":     _dt.now().strftime("%Y-%m-%dT%H:%M:%S"),
            })
        else:
            widgets["estado"].config(text="⚠ Error", fg="#D96B6B")


    # ══════════════════════════════════════════════════════════════════════════
    # GESTIÓN DE PROYECTOS
    # ══════════════════════════════════════════════════════════════════════════

    def _cargar_ultimo_proyecto(self):
        """Al arrancar: muestra la pantalla de inicio (si está habilitada)
        o restaura la última sesión directamente. Único call-site: el
        self.after(200, ...) del __init__ — los tests headless parchean
        este método entero, así que lo de adentro no les afecta."""
        import os
        from core.user_prefs import obtener_pref
        if not os.environ.get("BASHKAR_NO_WELCOME") and obtener_pref("mostrar_inicio", True):
            self._welcome_mostrar()
            return
        self._cargar_ultimo_proyecto_directo()

    def _welcome_mostrar(self):
        """Pantalla de inicio estilo FineReader: continuar/nuevo/abrir/
        recientes. Cerrarla sin elegir SIEMPRE deja un proyecto cargado
        (el resto de la app asume que ST tiene uno)."""
        from core.project_manager import cargar_proyecto, listar_proyectos
        from core.user_prefs import guardar_pref

        win, content = self._mk_glass_toplevel("Bienvenido a Bashkar Station", 560, 480)
        self._welcome_win = win
        win.protocol("WM_DELETE_WINDOW", lambda: self._welcome_elegir(win, self._crear_proyecto_automatico))

        pad = tk.Frame(content, bg=CONTENT_BG)
        pad.pack(fill="both", expand=True, padx=20, pady=16)

        proyectos = listar_proyectos()
        ultimo = proyectos[0] if proyectos else None

        if ultimo:
            c = tk.Frame(pad, bg=CARD_BG, relief="solid", bd=1, cursor="hand2")
            c.pack(fill="x", pady=(0, 10))
            tk.Label(c, text=f"▶ Continuar «{ultimo['nombre']}»", bg=CARD_BG, fg=TXT_PRI,
                     font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=14, pady=(10, 2))
            tk.Label(c, text=f"{ultimo.get('publicacion','')}  ·  modificado {ultimo.get('modificado','')}",
                     bg=CARD_BG, fg=TXT_DIM, font=("Segoe UI", 8)).pack(anchor="w", padx=14, pady=(0, 10))
            def _continuar(_e=None):
                self._welcome_elegir(win, self._cargar_ultimo_proyecto_directo)
            c.bind("<Button-1>", _continuar)
            for w in c.winfo_children():
                w.bind("<Button-1>", _continuar)

        fila = tk.Frame(pad, bg=CONTENT_BG)
        fila.pack(fill="x", pady=(0, 10))
        ttk.Button(fila, text="🆕 Nuevo proyecto", style="S.TButton",
                   command=lambda: self._welcome_elegir(win, self._nuevo_proyecto_dialogo)
                   ).pack(side="left", padx=(0, 8))
        ttk.Button(fila, text="📂 Abrir…", style="S.TButton",
                   command=lambda: self._welcome_elegir(win, self._abrir_gestor_proyectos)
                   ).pack(side="left")

        recientes = proyectos[1:8] if ultimo else proyectos[:8]
        if recientes:
            tk.Label(pad, text="Recientes:", bg=CONTENT_BG, fg=TXT_PRI,
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(6, 2))
            lb = tk.Listbox(pad, height=6, bg="#0E1114", fg="#E8E5DF", relief="solid", bd=1)
            lb.pack(fill="both", expand=True)
            for p in recientes:
                lb.insert("end", f"{p['nombre']}  ·  {p.get('modificado','')}")

            def _abrir_recientes_sel(_e=None):
                sel = lb.curselection()
                if not sel:
                    return
                ruta = Path(recientes[sel[0]]["ruta"])

                def _cargar():
                    res = cargar_proyecto(ruta, ST)
                    if res["ok"]:
                        self._proyecto_ruta = ruta
                        self._historial_ia = res.get("historial_ia", [])
                        self._sincronizar_ui_con_st()
                    else:
                        self._crear_proyecto_automatico()
                self._welcome_elegir(win, _cargar)
            lb.bind("<Double-Button-1>", _abrir_recientes_sel)

        var_no_mostrar = tk.BooleanVar(value=False)
        ttk.Checkbutton(pad, text="No mostrar esta pantalla al inicio",
                        variable=var_no_mostrar,
                        command=lambda: guardar_pref("mostrar_inicio", not var_no_mostrar.get())
                        ).pack(anchor="w", pady=(10, 0))

    def _welcome_elegir(self, win, fn):
        """Cierra la pantalla de inicio y ejecuta la acción elegida."""
        if win.winfo_exists():
            win.destroy()
        self._welcome_win = None
        fn()

    def _cargar_ultimo_proyecto_directo(self):
        """Restaura la última sesión guardada, o crea un proyecto vacío si
        no hay ninguna. Cuerpo original de _cargar_ultimo_proyecto (previo
        a la pantalla de inicio) — también es el camino de «Continuar»."""
        from core.project_manager import cargar_proyecto, cargar_ultimo
        ruta = cargar_ultimo()
        if ruta:
            res = cargar_proyecto(ruta, ST)
            if res["ok"]:
                self._proyecto_ruta = ruta
                self._historial_ia  = res.get("historial_ia", [])
                self._sincronizar_ui_con_st()
                nombre = res.get("nombre", ruta.stem)
                self._lbl_proyecto.config(text=nombre)
                self._set_pub_hdr(
                    f"{ST.publicacion}  ·  {ST.periodo}" if ST.periodo
                    else ST.publicacion)
                self._actualizar_badges()
                self.after(300, self._etz_refrescar_numeros)
                self.after(600, self._ocr_actualizar_estimacion)
                if res.get("migrado"):
                    self.after(500, lambda: messagebox.showinfo(
                        "Migración completada",
                        "El proyecto fue migrado automáticamente de v10 a v11.\n"
                        "Se creó una base de datos SQLite (.db) con todos los datos.\n"
                        "Se conservó un backup del archivo original."))
                return
        # Sin proyecto previo → crear uno vacío automáticamente
        self._crear_proyecto_automatico()

    def _crear_proyecto_automatico(self):
        """Crea un proyecto vacío con los datos por defecto de ST."""
        from datetime import datetime

        from core.project_manager import guardar_ultimo, nuevo_proyecto
        nombre = f"Proyecto {datetime.now().strftime('%d %b %Y')}"
        ruta = nuevo_proyecto(nombre, ST.publicacion, ST.periodo)
        guardar_ultimo(ruta)
        self._proyecto_ruta = ruta
        self._lbl_proyecto.config(text=nombre)

    def _guardar_proyecto(self):
        """Guarda el estado actual en el archivo .bashkar activo."""
        from core.project_manager import (
            guardar_proyecto,
            guardar_ultimo,
        )
        if not self._proyecto_ruta:
            self._nuevo_proyecto_dialogo(); return
        try:
            guardar_proyecto(self._proyecto_ruta, ST, self._historial_ia)
            guardar_ultimo(self._proyecto_ruta)
            self._limpiar_modificado()
            self._lbl_proyecto.config(fg="#6EC69A")
            self.after(1500, lambda: self._lbl_proyecto.config(fg="#B5B6B3"))
        except Exception as e:
            messagebox.showerror("Error al guardar", str(e))

    def _on_cerrar(self):
        """Autosave al cerrar la ventana."""
        # Detener dictado activo antes de cerrar
        if getattr(self, "_dictar_session", None) is not None:
            try:
                self._dictar_session.detener()
            except Exception:
                pass
        if self._proyecto_ruta:
            try:
                from core.project_manager import guardar_proyecto, guardar_ultimo
                guardar_proyecto(self._proyecto_ruta, ST, self._historial_ia)
                guardar_ultimo(self._proyecto_ruta)
            except Exception:
                pass
        self.destroy()
        sys.exit(0)

    def _marcar_modificado(self):
        """Activa indicador ● en la etiqueta del proyecto para señalar cambios pendientes."""
        era_falso = not self._hay_cambios
        self._hay_cambios = True
        try:
            txt = self._lbl_proyecto.cget("text")
            if not txt.startswith("●  "):
                self._lbl_proyecto.config(text=f"●  {txt}", fg="#E6A64C")
        except Exception:
            pass
        # Iniciar pulso solo la primera vez que se activa
        if era_falso:
            self.after(800, lambda: self._pulso_modificado(True))

    def _limpiar_modificado(self):
        """Quita el indicador ● tras guardar."""
        self._hay_cambios = False
        try:
            txt = self._lbl_proyecto.cget("text")
            if txt.startswith("●  "):
                self._lbl_proyecto.config(text=txt[3:], fg="#B5B6B3")
        except Exception:
            pass

    def _autoguardar_periodico(self):
        """Guarda silenciosamente el proyecto cada 3 minutos si hay cambios."""
        if self._proyecto_ruta and self._hay_cambios:
            try:
                from core.project_manager import guardar_proyecto, guardar_ultimo
                guardar_proyecto(self._proyecto_ruta, ST, self._historial_ia)
                guardar_ultimo(self._proyecto_ruta)
                self._limpiar_modificado()
            except Exception:
                pass
        # Reprogramar para el siguiente ciclo
        self.after(180_000, self._autoguardar_periodico)

    # ══════════════════════════════════════════════════════════════════════════
    # TOAST NOTIFICATIONS
    # ══════════════════════════════════════════════════════════════════════════

    _TOAST_Y_OFFSET = 24   # separación entre toasts apilados

    def toast(self, mensaje: str, tipo: str = "info", duracion: int = 3500):
        """
        Muestra una notificación no-modal en la esquina inferior derecha.
        tipo: "info" | "ok" | "warn" | "error"
        """
        colores = {
            "info":  ("#171C20", "#6CA8E8", "#6CA8E8"),
            "ok":    ("#15251F", "#62C6B5", "#62C6B5"),
            "warn":  ("#2A2116", "#E6A64C", "#E6A64C"),
            "error": ("#2A1719", "#D96B6B", "#D96B6B"),
        }
        iconos = {"info": "ℹ", "ok": "✓", "warn": "⚠", "error": "✕"}
        bg, fg_icon, fg_bor = colores.get(tipo, colores["info"])

        # Calcular posición — apilar toasts activos
        if not hasattr(self, "_toasts_activos"):
            self._toasts_activos = []

        win = tk.Toplevel(self)
        win.wm_overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=fg_bor)   # borde de color

        inner = tk.Frame(win, bg=bg, padx=14, pady=10)
        inner.pack(padx=1, pady=1)

        tk.Label(inner, text=iconos.get(tipo, "ℹ"), bg=bg, fg=fg_icon,
                 font=("Segoe UI", 13, "bold")).pack(side="left", padx=(0, 10))
        tk.Label(inner, text=mensaje, bg=bg, fg=TXT_PRI,
                 font=("Segoe UI", 9), wraplength=280,
                 justify="left").pack(side="left")

        # Botón cerrar
        def _cerrar():
            try:
                self._toasts_activos.remove(win)
                win.destroy()
                self._reposicionar_toasts()
            except Exception:
                pass

        tk.Label(inner, text="×", bg=bg, fg=TXT_SEC,
                 font=("Segoe UI", 11), cursor="hand2",
                 padx=6).pack(side="right", padx=(10, 0))
        inner.children[list(inner.children)[-1]].bind("<Button-1>", lambda e: _cerrar())

        win.update_idletasks()
        self._toasts_activos.append(win)
        self._reposicionar_toasts()

        # Animación entrada: fade in
        win.attributes("-alpha", 0.0)
        self._toast_fade(win, 0.0, 1.0, 30, duracion, _cerrar)

    def _reposicionar_toasts(self):
        """Recalcula posición Y de todos los toasts activos."""
        if not hasattr(self, "_toasts_activos"):
            return
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        y = sh - 72
        for w in reversed(self._toasts_activos):
            try:
                w.update_idletasks()
                ww = w.winfo_reqwidth()
                wh = w.winfo_reqheight()
                w.geometry(f"+{sw - ww - 20}+{y - wh}")
                y -= wh + 8
            except Exception:
                pass

    def _toast_fade(self, win, alpha: float, target: float,
                    steps: int, duracion: int, on_done):
        """Anima alpha de `alpha` a `target` en `steps` pasos."""
        if not win.winfo_exists():
            return
        step = (target - alpha) / max(steps, 1)
        alpha = round(alpha + step, 3)
        try:
            win.attributes("-alpha", alpha)
        except Exception:
            return
        if (step > 0 and alpha < target) or (step < 0 and alpha > target):
            self.after(16, lambda: self._toast_fade(win, alpha, target, steps - 1,
                                                     duracion, on_done))
        elif target == 1.0:
            # Fade-in terminó → esperar duracion → fade-out
            self.after(duracion, lambda: self._toast_fade(win, 1.0, 0.0, 20,
                                                           0, on_done))
        else:
            # Fade-out terminó
            on_done()

    # ══════════════════════════════════════════════════════════════════════════
    # COMMAND PALETTE  (Ctrl+K)
    # ══════════════════════════════════════════════════════════════════════════

    # Catálogo de comandos: (etiqueta, descripción, acción_callable)
    _COMANDOS_PALETTE: list = []   # se construye en _init_command_palette

    def _init_command_palette(self):
        """Construye el catálogo de comandos disponibles."""
        nav = [
            # Navegación de páginas
            ("Ir a Configuración",        "cfg",   lambda: self._mostrar_pagina("cfg")),
            ("Ir a Etiquetador de zonas",  "etz",   lambda: self._mostrar_pagina("etz")),
            ("Ir a Extracción OCR",        "ocr",   lambda: self._mostrar_pagina("ocr")),
            ("Ir a Conversor PDF",         "conv",  lambda: self._mostrar_pagina("conv")),
            ("Ir a Extracción multimodal IA", "mmx", lambda: self._mostrar_pagina("mmx")),
            ("Ir a Normalizar",            "norm",  lambda: self._mostrar_pagina("norm")),
            ("Ir a Segmentar",             "seg",   lambda: self._mostrar_pagina("seg")),
            ("Ir a Análisis textual",      "anal",  lambda: self._mostrar_pagina("anal")),
            ("Ir a NER / Entidades",       "ner",   lambda: self._mostrar_pagina("ner")),
            ("Ir a Anotaciones",           "anot",  lambda: self._mostrar_pagina("anot")),
            ("Ir a Colocaciones",          "coloc", lambda: self._mostrar_pagina("coloc")),
            ("Ir a Lingüística computacional", "ling", lambda: self._mostrar_pagina("ling")),
            ("Ir a Visualizar",            "vis",   lambda: self._mostrar_pagina("vis")),
            ("Ir a Comparativo",           "comp",  lambda: self._mostrar_pagina("comp")),
            ("Ir a Publicar / Resultados", "res",   lambda: self._mostrar_pagina("res")),
            ("Ir a Bitácora",              "bit",   lambda: self._bitacora_abrir()),
        ]
        acciones = [
            ("💾  Guardar proyecto",       "guardar",   self._guardar_proyecto),
            ("📂  Abrir gestor proyectos", "proyectos", self._abrir_gestor_proyectos),
            ("➕  Nuevo proyecto",         "nuevo",     self._nuevo_proyecto_dialogo),
            ("⚡  Modo análisis rápido",   "adhoc",     self._modo_adhoc),
            ("📓  Abrir bitácora",         "bitacora",  self._bitacora_abrir),
            ("🌙  Cambiar tema claro/oscuro", "tema",   self._toggle_theme),
            ("⚖️  Benchmark de OCR (CER/WER por ruta)", "bench",
             lambda: self._mostrar_pagina("bench")),
            ("🖼  Análisis de encuadre (framing)", "frame",
             lambda: self._ir_a_ling_pestania(6)),
            ("⚖  Polaridad discriminante", "pol",
             lambda: self._ir_a_ling_pestania(7)),
            ("🔍  Revisión NER (validar entidades)", "revner",
             lambda: self._ir_a_ling_pestania(8)),
            ("✔  Validación metodológica (Kappa)", "valida",
             lambda: self._ir_a_ling_pestania(9)),
            ("🕸  Grafo canónico (entidades + relaciones)", "grafo",
             lambda: self._mostrar_pagina("red")),
            ("✔  Verificación OCR palabra por palabra", "verificar",
             self._verif_abrir),
            ("🔁  Detectar cabeceras repetidas (Etiquetador)", "cabeceras",
             self._etz_detectar_cabeceras),
            ("💾  Guardar como… (PDF/TEI/Excel/texto)", "guardarcomo",
             self._exp_abrir_dialogo),
        ]
        self._COMANDOS_PALETTE = [
            {"label": lab, "tags": tag, "accion": fn}
            for lab, tag, fn in (nav + acciones)
        ]

    def _abrir_command_palette(self, event=None):
        """Abre (o cierra si ya está abierta) la Command Palette."""
        if getattr(self, "_cp_win", None) and self._cp_win.winfo_exists():
            self._cp_win.destroy()
            self._cp_win = None
            return

        if not self._COMANDOS_PALETTE:
            self._init_command_palette()

        sw = self.winfo_screenwidth()
        w_pal = 500
        x = self.winfo_rootx() + (self.winfo_width() - w_pal) // 2
        y = self.winfo_rooty() + 60

        win = tk.Toplevel(self)
        win.wm_overrideredirect(True)
        win.attributes("-topmost", True)
        win.geometry(f"{w_pal}+{x}+{y}")
        win.configure(bg=CARD_BOR)   # borde 1px simulado
        self._cp_win = win

        # Glass frame interior
        frame = tk.Frame(win, bg=CARD_BG, bd=0)
        frame.pack(padx=1, pady=1, fill="both", expand=True)

        # Header con título
        hdr = tk.Frame(frame, bg=CARD_BG, pady=6)
        hdr.pack(fill="x", padx=10)
        tk.Label(hdr, text="⌨  Comandos", bg=CARD_BG, fg=TXT_SEC,
                 font=("Segoe UI", 8)).pack(side="left")
        tk.Label(hdr, text="Esc para cerrar", bg=CARD_BG, fg=TXT_DIM,
                 font=("Segoe UI", 8)).pack(side="right")

        # Separador
        tk.Frame(frame, bg=CARD_BOR, height=1).pack(fill="x")

        # Campo de búsqueda
        var_q = tk.StringVar()
        entry = tk.Entry(frame, textvariable=var_q, bg="#0E1114", fg=TXT_PRI,
                         insertbackground=TXT_PRI, font=("Segoe UI", 12),
                         relief="flat", bd=0)
        entry.pack(fill="x", padx=14, pady=10, ipady=6)
        entry.focus_set()

        # Separador
        tk.Frame(frame, bg=CARD_BOR, height=1).pack(fill="x")

        # Lista de resultados
        listbox = tk.Listbox(frame, bg=CARD_BG, fg=TXT_PRI,
                             selectbackground=AZ3, selectforeground="#E8E5DF",
                             font=("Segoe UI", 10), relief="flat", bd=0,
                             activestyle="none", height=10)
        listbox.pack(fill="both", expand=True, padx=0, pady=4)

        # Hint inferior
        hint = tk.Frame(frame, bg="#0E1114", pady=5)
        hint.pack(fill="x")
        for txt in ["↑↓ navegar", "Enter ejecutar", "Ctrl+K cerrar"]:
            tk.Label(hint, text=txt, bg="#0E1114", fg=TXT_DIM,
                     font=("Segoe UI", 8)).pack(side="left", padx=10)

        def _poblar(q: str = ""):
            listbox.delete(0, "end")
            q_low = q.lower().strip()
            for cmd in self._COMANDOS_PALETTE:
                lbl = cmd["label"]
                if not q_low or q_low in lbl.lower() or q_low in cmd["tags"].lower():
                    listbox.insert("end", f"  {lbl}")
            if listbox.size():
                listbox.selection_set(0)

        def _ejecutar(idx=None):
            if idx is None:
                sel = listbox.curselection()
                if not sel:
                    return
                idx = sel[0]
            q_low = var_q.get().lower().strip()
            coincidentes = [c for c in self._COMANDOS_PALETTE
                            if not q_low or q_low in c["label"].lower()
                            or q_low in c["tags"].lower()]
            if idx < len(coincidentes):
                win.destroy()
                self._cp_win = None
                try:
                    coincidentes[idx]["accion"]()
                except Exception:
                    pass

        def _on_key(event):
            if event.keysym == "Escape":
                win.destroy(); self._cp_win = None
            elif event.keysym == "Return":
                _ejecutar()
            elif event.keysym == "Down":
                cur = listbox.curselection()
                nxt = (cur[0] + 1) if cur else 0
                if nxt < listbox.size():
                    listbox.selection_clear(0, "end")
                    listbox.selection_set(nxt)
                    listbox.see(nxt)
            elif event.keysym == "Up":
                cur = listbox.curselection()
                prv = (cur[0] - 1) if cur else 0
                if prv >= 0:
                    listbox.selection_clear(0, "end")
                    listbox.selection_set(prv)
                    listbox.see(prv)

        var_q.trace_add("write", lambda *_: _poblar(var_q.get()))
        entry.bind("<Key>", _on_key)
        listbox.bind("<Double-Button-1>",
                     lambda e: _ejecutar(listbox.nearest(e.y)))
        listbox.bind("<Return>", lambda e: _ejecutar())
        win.bind("<Escape>", lambda e: (win.destroy(), setattr(self, "_cp_win", None)))

        # Cerrar al perder foco
        win.bind("<FocusOut>", lambda e: self.after(150, _check_focus))
        def _check_focus():
            try:
                if win.winfo_exists() and win.focus_get() is None:
                    win.destroy(); self._cp_win = None
            except Exception:
                pass

        _poblar()

    # ══════════════════════════════════════════════════════════════════════════
    # MICRO-ANIMACIONES
    # ══════════════════════════════════════════════════════════════════════════

    def _fade_pagina(self, frame, steps: int = 8):
        """Fade-in suave de un frame al mostrarlo (alpha via after)."""
        # tkinter no soporta alpha por widget, pero simulamos con
        # cambios rápidos de bg que producen efecto visual perceptible.
        # En Windows con DWM el Toplevel sí soporta alpha; aquí usamos
        # una variante: revelar el frame con delay mínimo para dar sensación
        # de transición sin coste de rendimiento.
        frame.update_idletasks()

    def _pulso_modificado(self, activo: bool = True):
        """Pulsa el indicador ● alternando entre ámbar y naranja."""
        if not activo or not self._hay_cambios:
            return
        try:
            txt = self._lbl_proyecto.cget("text")
            if not txt.startswith("●"):
                return
            cur = self._lbl_proyecto.cget("fg")
            nxt = "#E6A64C" if cur == "#E6A64C" else "#E6A64C"
            self._lbl_proyecto.config(fg=nxt)
            self.after(800, lambda: self._pulso_modificado(self._hay_cambios))
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # SKELETON LOADING
    # ══════════════════════════════════════════════════════════════════════════

    def _skeleton_show(self, parent, n_filas: int = 6) -> tk.Frame:
        """
        Crea y muestra un skeleton placeholder en `parent`.
        Retorna el frame para poder destruirlo con _skeleton_hide().
        """
        sk = tk.Frame(parent, bg=CONTENT_BG)
        sk.place(relx=0, rely=0, relwidth=1, relheight=1)

        for i in range(n_filas):
            row = tk.Frame(sk, bg=CONTENT_BG)
            row.pack(fill="x", padx=24, pady=6)
            # línea corta (título simulado)
            w_pct = 0.4 if i % 3 == 0 else 0.75
            bar_bg = CARD_BOR
            tk.Frame(row, bg=bar_bg, height=10,
                     width=int(360 * w_pct)).pack(side="left", fill="y")
        self._skeleton_animar(sk, 0)
        return sk

    def _skeleton_animar(self, sk: tk.Frame, fase: int):
        """Pulsa el brillo de las barras skeleton."""
        if not sk.winfo_exists():
            return
        colores = [CARD_BOR, "#1C2227", CARD_BOR]
        c = colores[fase % len(colores)]
        try:
            for row in sk.winfo_children():
                for bar in row.winfo_children():
                    bar.config(bg=c)
        except Exception:
            pass
        self.after(400, lambda: self._skeleton_animar(sk, fase + 1))

    def _skeleton_hide(self, sk: tk.Frame | None):
        """Destruye el skeleton."""
        if sk and sk.winfo_exists():
            sk.destroy()

    # ══════════════════════════════════════════════════════════════════════════
    # PROGRESSIVE DISCLOSURE — helper de secciones avanzadas
    # ══════════════════════════════════════════════════════════════════════════

    def _mk_avanzado(self, parent, label: str = "Opciones avanzadas",
                     build_fn=None) -> tk.Frame:
        """
        Crea un bloque colapsable 'Opciones avanzadas' en `parent`.
        `build_fn(frame)` construye el contenido al expandir.
        Retorna el frame contenedor exterior.
        """
        outer = tk.Frame(parent, bg=CONTENT_BG)
        outer.pack(fill="x", padx=0, pady=(2, 0))

        var_open = tk.BooleanVar(value=False)
        _built   = [False]

        hdr = tk.Frame(outer, bg=CONTENT_BG, cursor="hand2")
        hdr.pack(fill="x")
        lbl_arrow = tk.Label(hdr, text="▶", bg=CONTENT_BG, fg=TXT_DIM,
                             font=("Segoe UI", 8))
        lbl_arrow.pack(side="left", padx=(4, 2))
        tk.Label(hdr, text=label, bg=CONTENT_BG, fg=TXT_DIM,
                 font=("Segoe UI", 8, "italic")).pack(side="left")

        body = tk.Frame(outer, bg=CONTENT_BG)

        def _toggle(e=None):
            if var_open.get():
                var_open.set(False)
                lbl_arrow.config(text="▶")
                body.pack_forget()
            else:
                var_open.set(True)
                lbl_arrow.config(text="▼")
                if not _built[0] and build_fn:
                    build_fn(body)
                    _built[0] = True
                body.pack(fill="x", pady=(4, 0))

        hdr.bind("<Button-1>", _toggle)
        lbl_arrow.bind("<Button-1>", _toggle)
        for child in hdr.winfo_children():
            child.bind("<Button-1>", _toggle)

        return outer

    # ══════════════════════════════════════════════════════════════════════════
    # GLASSMORPHISM — paneles flotantes con estilo mejorado
    # ══════════════════════════════════════════════════════════════════════════

    def _mk_glass_toplevel(self, titulo: str, ancho: int = 700,
                           alto: int = 500) -> tuple["tk.Toplevel", "tk.Frame"]:
        """
        Crea un Toplevel con estilo glass: borde de color,
        shadow simulada, header con título.
        Retorna (win, content_frame).
        """
        win = tk.Toplevel(self)
        win.title(titulo)
        win.geometry(f"{ancho}x{alto}")
        win.resizable(True, True)
        win.configure(bg=HDR_LINE)   # borde 1px azul

        # Shadow: frame exterior ligeramente más oscuro
        shadow = tk.Frame(win, bg="#0E1114")
        shadow.pack(padx=1, pady=1, fill="both", expand=True)

        # Header del panel
        hdr = tk.Frame(shadow, bg=CARD_BG, pady=8)
        hdr.pack(fill="x")
        tk.Label(hdr, text=titulo, bg=CARD_BG, fg=TXT_PRI,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=14)
        btn_close = tk.Label(hdr, text="✕", bg=CARD_BG, fg=TXT_SEC,
                             font=("Segoe UI", 11), cursor="hand2", padx=10)
        btn_close.pack(side="right")
        btn_close.bind("<Button-1>", lambda e: win.destroy())
        btn_close.bind("<Enter>",    lambda e: btn_close.config(fg=ROJO))
        btn_close.bind("<Leave>",    lambda e: btn_close.config(fg=TXT_SEC))

        tk.Frame(shadow, bg=CARD_BOR, height=1).pack(fill="x")

        content = tk.Frame(shadow, bg=CONTENT_BG)
        content.pack(fill="both", expand=True)

        return win, content

    # ══════════════════════════════════════════════════════════════════════════
    # BITÁCORA DE INVESTIGACIÓN
    # ══════════════════════════════════════════════════════════════════════════













    def _nuevo_proyecto_dialogo(self):
        """Diálogo para crear un nuevo proyecto."""
        dlg = tk.Toplevel(self)
        dlg.title("Nuevo proyecto")
        dlg.geometry("420x220")
        dlg.resizable(False, False)
        dlg.configure(bg=CONTENT_BG)
        dlg.grab_set()
        dlg.transient(self)

        tk.Label(dlg, text="Nuevo proyecto de investigación",
                 bg=CONTENT_BG, fg=TXT_PRI,
                 font=("Segoe UI", 11, "bold")).pack(pady=(18, 12))

        form = tk.Frame(dlg, bg=CONTENT_BG)
        form.pack(fill="x", padx=24)
        form.columnconfigure(1, weight=1)

        campos = [("Nombre del proyecto:", ""), ("Publicación:", ST.publicacion),
                  ("Período:", ST.periodo)]
        vars_ = []
        for i, (lbl, val) in enumerate(campos):
            tk.Label(form, text=lbl, bg=CONTENT_BG, fg="#E8E5DF",
                     font=("Segoe UI", 9)).grid(row=i, column=0, sticky="w", pady=4)
            v = tk.StringVar(value=val)
            tk.Entry(form, textvariable=v, font=("Segoe UI", 9),
                     relief="solid", bd=1).grid(row=i, column=1, sticky="ew", padx=(8, 0))
            vars_.append(v)

        def _crear():
            nombre = vars_[0].get().strip()
            if not nombre:
                messagebox.showwarning("Campo vacío", "Escribe un nombre.", parent=dlg)
                return
            from core.project_manager import (
                guardar_proyecto,
                guardar_ultimo,
                nuevo_proyecto,
            )
            # Guardar el proyecto actual antes de cambiar
            if self._proyecto_ruta:
                try:
                    guardar_proyecto(self._proyecto_ruta, ST, self._historial_ia)
                except Exception: pass
            ruta = nuevo_proyecto(nombre, vars_[1].get().strip(),
                                   vars_[2].get().strip())
            guardar_ultimo(ruta)
            self._proyecto_ruta = ruta
            self._historial_ia  = []
            self._lbl_proyecto.config(text=nombre)
            dlg.destroy()

        btn_row = tk.Frame(dlg, bg=CONTENT_BG)
        btn_row.pack(pady=14)
        ttk.Button(btn_row, text="Crear proyecto", style="P.TButton",
                   command=_crear).pack(side="left", padx=4)
        ttk.Button(btn_row, text="Cancelar", style="S.TButton",
                   command=dlg.destroy).pack(side="left", padx=4)

    def _abrir_gestor_proyectos(self):
        """Ventana con la lista de proyectos guardados."""
        from core.project_manager import (
            cargar_proyecto,
            eliminar_proyecto,
            fecha_legible,
            guardar_proyecto,
            guardar_ultimo,
            listar_proyectos,
            progreso_str,
        )

        win = tk.Toplevel(self)
        win.title("Proyectos guardados")
        win.geometry("780x480")
        win.configure(bg=CONTENT_BG)
        win.grab_set()
        win.transient(self)

        # Cabecera
        hdr = tk.Frame(win, bg=AZ1)
        hdr.pack(fill="x")
        tk.Label(hdr, text="  📂  Proyectos de investigación",
                 bg=AZ1, fg="white",
                 font=("Segoe UI", 11, "bold")).pack(side="left", pady=10, padx=12)
        ttk.Button(hdr, text="➕ Nuevo proyecto", style="S.TButton",
                   command=lambda: [win.destroy(),
                                    self._nuevo_proyecto_dialogo()]).pack(
                   side="right", padx=12, pady=8)

        # Lista
        cols = ("Nombre", "Publicación", "Período",
                "Última sesión", "Progreso")
        tv_f = tk.Frame(win, bg=CONTENT_BG)
        tv_f.pack(fill="both", expand=True, padx=12, pady=8)
        sbv = ttk.Scrollbar(tv_f, orient="vertical")
        tv = ttk.Treeview(tv_f, columns=cols, show="headings",
                           yscrollcommand=sbv.set, height=14)
        widths = [200, 140, 100, 140, 200]
        for col, w in zip(cols, widths):
            tv.heading(col, text=col, anchor="w")
            tv.column(col, width=w, minwidth=60)
        sbv.config(command=tv.yview)
        sbv.pack(side="right", fill="y")
        tv.pack(fill="both", expand=True)

        proyectos = listar_proyectos()
        ruta_map = {}
        for p in proyectos:
            iid = tv.insert("", "end", values=(
                p["nombre"], p["publicacion"], p["periodo"],
                fecha_legible(p["modificado"]),
                progreso_str(p["progreso"]),
            ))
            ruta_map[iid] = p["ruta"]
            # Marcar el activo
            if self._proyecto_ruta and str(p["ruta"]) == str(self._proyecto_ruta):
                tv.item(iid, tags=("activo",))
        tv.tag_configure("activo", background="#30291F", font=("Segoe UI", 9, "bold"))

        # Botones de acción
        act = tk.Frame(win, bg=CONTENT_BG)
        act.pack(fill="x", padx=12, pady=(0, 10))
        lbl_sel = tk.Label(act, text="Selecciona un proyecto de la lista",
                            bg=CONTENT_BG, fg="#777F84", font=("Segoe UI", 9))
        lbl_sel.pack(side="left")

        def _abrir():
            sel = tv.selection()
            if not sel: return
            ruta = ruta_map[sel[0]]
            # Guardar actual
            if self._proyecto_ruta:
                try:
                    guardar_proyecto(self._proyecto_ruta, ST, self._historial_ia)
                except Exception: pass
            ST.reset()
            res = cargar_proyecto(ruta, ST)
            if not res["ok"]:
                messagebox.showerror("Error", res["mensaje"], parent=win); return
            guardar_ultimo(ruta)
            self._proyecto_ruta = ruta
            self._historial_ia  = res.get("historial_ia", [])
            self._sincronizar_ui_con_st()
            nombre = res.get("nombre", Path(ruta).stem)
            self._lbl_proyecto.config(text=nombre)
            self._set_pub_hdr(
                f"{ST.publicacion}  ·  {ST.periodo}" if ST.periodo
                else ST.publicacion)
            self._actualizar_badges()
            self.after(600, self._ocr_actualizar_estimacion)
            win.destroy()
            if res.get("migrado"):
                messagebox.showinfo(
                    "Migración completada",
                    "El proyecto fue migrado automáticamente de v10 a v11.\n"
                    "Se creó una base de datos SQLite (.db) con todos los datos.\n"
                    "Se conservó un backup del archivo original.")

        def _eliminar():
            sel = tv.selection()
            if not sel: return
            ruta = ruta_map[sel[0]]
            nombre = tv.item(sel[0])["values"][0]
            if not messagebox.askyesno(
                    "Eliminar proyecto",
                    f"¿Eliminar '{nombre}'?\nEsta acción no se puede deshacer.",
                    parent=win): return
            eliminar_proyecto(ruta)
            tv.delete(sel[0])
            if str(ruta) == str(self._proyecto_ruta):
                self._proyecto_ruta = None
                self._lbl_proyecto.config(text="Sin proyecto")

        ttk.Button(act, text="📂 Abrir", style="P.TButton",
                   command=_abrir).pack(side="right", padx=(4, 0))
        ttk.Button(act, text="🗑 Eliminar", style="S.TButton",
                   command=_eliminar).pack(side="right")
        tv.bind("<Double-1>", lambda e: _abrir())

    def _sincronizar_ui_con_st(self):
        """Actualiza los widgets de configuración con los valores de ST."""
        try:
            self._var_pub.set(ST.publicacion)
            self._var_per.set(ST.periodo)
            # Restaurar versión de normalización
            if hasattr(self, "_norm_var_version"):
                self._norm_var_version.set(getattr(ST, "norm_version", "manual"))
                self._norm_version_cambio()
            if ST.pdf_dir:
                self._var_ent.set(str(ST.pdf_dir))
                try: self._poblar_lista(ST.pdf_dir)
                except Exception: pass
                # Restaurar en el Conversor también
                if hasattr(self, "_conv_entrada"):
                    self._conv_entrada.set(str(ST.pdf_dir))
            if ST.out_dir:
                self._var_sal.set(str(ST.out_dir))
                if hasattr(self, "_conv_salida"):
                    self._conv_salida.set(str(ST.out_dir))
            if ST.api_key:
                self._var_api_key.set(ST.api_key)
            # Restaurar claves por proveedor
            keys = getattr(ST, "api_keys", {})
            if keys.get("anthropic"): self._var_key_anthropic.set(keys["anthropic"])
            if keys.get("openai"):    self._var_key_openai.set(keys["openai"])
            if keys.get("gemini"):    self._var_key_gemini.set(keys["gemini"])
            if keys.get("ollama"):    self._var_key_ollama.set(keys["ollama"])
            # Restaurar modelos por etapa
            for etapa_id, var_e in getattr(self, "_vars_modelo_etapa", {}).items():
                modelo = ST.modelos_etapa.get(etapa_id, "")
                if modelo: var_e.set(modelo)
            self._var_max_ia.set(ST.max_ia)
            if ST.campos_semillas:
                import json as _json
                txt = _json.dumps(ST.campos_semillas, ensure_ascii=False, indent=2)
                try:
                    self._txt_sem.config(state="normal")
                    self._txt_sem.delete("1.0", "end")
                    self._txt_sem.insert("1.0", txt)
                except Exception: pass
            # Restaurar índice semántico FAISS si fue cargado con el proyecto
            indice_cargado = getattr(ST, "_bsem_indice", None)
            if indice_cargado is not None and getattr(indice_cargado, "construido", False):
                if hasattr(self, "_bsem_indice"):
                    self._bsem_indice = indice_cargado
                if hasattr(self, "_lbl_bsem_estado"):
                    self._lbl_bsem_estado.config(
                        text=f"✓ {indice_cargado.n_articulos} artículos (restaurado)", fg=VERDE)
                if hasattr(self, "_lbl_bsem_n"):
                    self._lbl_bsem_n.config(text=f"{indice_cargado.n_articulos} artículos")
            # Restaurar lematización
            if hasattr(self, "_var_lematizar"):
                self._var_lematizar.set(getattr(ST, "lematizar", True))
            # Restaurar stopwords del proyecto en el widget de Collocates
            if hasattr(self, "_txt_stopwords"):
                sw = getattr(ST, "stopwords_proyecto", [])
                if sw:
                    self._txt_stopwords.delete("1.0", "end")
                    self._txt_stopwords.insert("1.0", "\n".join(sw))
                    # Aplicar al motor de collocations en esta sesión
                    try:
                        import core.collocation_engine as _ce
                        _ce.STOPWORDS_ES = _ce.STOPWORDS_ES | frozenset(sw)
                    except Exception:
                        pass
        except Exception:
            pass  # widgets aún no inicializados en el primer arranque


    # ── Cabecera de sección en el sidebar ────────────────────────────────────
    def _sb_seccion(self, parent, texto: str, scroll_fn=None):
        """Renderiza un separador + etiqueta de sección, rotulada en cobre."""
        tk.Frame(parent, bg=CARD_BOR, height=1).pack(
            fill="x", padx=12, pady=(10, 3))
        lbl = tk.Label(parent, text=texto, bg=SB_BG, fg=AZ3,
                       font=("Segoe UI", 7, "bold"), anchor="w")
        lbl.pack(fill="x", padx=16, pady=(0, 3))
        if scroll_fn:
            lbl.bind("<MouseWheel>", scroll_fn)
            lbl.bind("<Button-4>",   scroll_fn)
            lbl.bind("<Button-5>",   scroll_fn)

    # ── Botón individual del sidebar ──────────────────────────────────────────
    def _make_sb_btn(self, parent, pid, emoji, label, num, badge_attr,
                     es_flujo: bool = True, scroll_fn=None):
        """Botón de navegación — dark mode GitHub-style."""
        h = 40 if es_flujo else 34
        row = tk.Frame(parent, bg=SB_BG, cursor="hand2", height=h)
        row.pack(fill="x", pady=0)
        row.pack_propagate(False)

        # Barra indicadora izquierda 3px
        bar = tk.Frame(row, bg=SB_BG, width=3)
        bar.pack(side="left", fill="y")

        # Número de paso (flujo principal)
        if num is not None:
            num_lbl = tk.Label(row, text=str(num), bg=SB_BG, fg=TXT_DIM,
                               font=("Segoe UI", 7, "bold"), width=2)
            num_lbl.pack(side="left", padx=(4, 0))
        else:
            num_lbl = tk.Label(row, text="", bg=SB_BG, width=0)
            num_lbl.pack(side="left", padx=(8, 0))

        # Emoji
        em_lbl = tk.Label(row, text=emoji, bg=SB_BG, fg=TXT_SEC,
                           font=("Segoe UI", 11 if es_flujo else 10))
        em_lbl.pack(side="left", padx=(6, 5))

        # Label
        txt_lbl = tk.Label(row, text=label, bg=SB_BG, fg=TXT_SEC,
                            font=("Segoe UI", 9 if es_flujo else 8), anchor="w")
        txt_lbl.pack(side="left", fill="x", expand=True)

        # Badge ✓
        badge = tk.Label(row, text="✓", bg=SB_BG, fg=VERDE,
                          font=("Segoe UI", 8, "bold"))

        widgets = {
            "row": row, "bar": bar, "em": em_lbl,
            "txt": txt_lbl, "num": num_lbl, "badge": badge,
            "badge_attr": badge_attr, "es_flujo": es_flujo,
        }

        def _click(e, p=pid):   self._mostrar_pagina(p)

        # Los <Enter>/<Leave> pueden llegar cuando el botón ya no existe: al
        # cambiar de contexto se repuebla el sidebar entero con el puntero
        # encima. Sin el guard, Tk imprime un TclError por cada uno.
        def _pintar(bg, fg):
            try:
                for w in (row, bar, em_lbl, txt_lbl, num_lbl):
                    w.config(bg=bg)
                txt_lbl.config(fg=fg)
                em_lbl.config(fg=fg)
            except tk.TclError:
                pass

        def _enter(e, p=pid):
            if self._pagina_activa.get() != p:
                _pintar(SB_HOV, SB_TXT2)

        def _leave(e, p=pid):
            if self._pagina_activa.get() != p:
                _pintar(SB_BG, TXT_SEC)

        for w in (row, bar, em_lbl, txt_lbl, num_lbl):
            w.bind("<Button-1>", _click)
            w.bind("<Enter>",    _enter)
            w.bind("<Leave>",    _leave)
            if scroll_fn:
                w.bind("<MouseWheel>", scroll_fn)
                w.bind("<Button-4>",   scroll_fn)
                w.bind("<Button-5>",   scroll_fn)

        return widgets

    def _aplicar_estilo_sb_btn(self, pid: str, widgets: dict, activo: bool):
        """Aplica estilos dark mode al botón de sidebar según estado activo/inactivo."""
        if activo:
            bg     = SB_SEL      # fondo cálido, no azul de sistema
            fg_txt = AZ4         # ámbar: el elemento activo se lee de un vistazo
            bg_bar = AB_IND      # barra de cobre a la izquierda
        else:
            bg     = SB_BG
            fg_txt = SB_TXT
            bg_bar = SB_BG
        widgets["row"].config(bg=bg)
        widgets["bar"].config(bg=bg_bar)
        for w_key in ("em", "txt", "num"):
            if w_key in widgets:
                widgets[w_key].config(bg=bg, fg=fg_txt)
        if widgets.get("badge_attr"):
            done = getattr(ST, widgets["badge_attr"], False)
            if done:
                widgets["badge"].config(bg=bg)
                widgets["badge"].pack(side="right", padx=6)

    def _crear_pagina_scrollable(self, pid: str) -> tk.Frame:
        """Devuelve un frame interior desplazable para la página `pid`.
        Envuelve el frame en un Canvas + Scrollbar vertical dentro de
        `_content_area`; el contenedor externo se guarda en
        `_contenedores_pagina[pid]` (es lo que se muestra/oculta)."""
        if pid == "inicio":
            # El tablero trae su propio canvas desplazable: anidarlo dentro de
            # otro deja dos barras de scroll y una altura que no se propaga.
            cont = tk.Frame(self._content_area, bg=CONTENT_BG)
            self._contenedores_pagina[pid] = cont
            return cont

        cont = tk.Frame(self._content_area, bg=CONTENT_BG)
        canvas = tk.Canvas(cont, bg=CONTENT_BG, highlightthickness=0, bd=0)
        vbar = ttk.Scrollbar(cont, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        vbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        interior = tk.Frame(canvas, bg=CONTENT_BG)
        win_id = canvas.create_window((0, 0), window=interior, anchor="nw")

        def _on_interior_config(_e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
        interior.bind("<Configure>", _on_interior_config)

        # El interior siempre ocupa el ancho del canvas (para que el pack fill=x
        # de los _build_* se extienda a lo ancho).
        def _on_canvas_config(e):
            canvas.itemconfig(win_id, width=e.width)
        canvas.bind("<Configure>", _on_canvas_config)

        # Rueda del ratón: desplaza solo cuando el puntero está sobre esta página
        # y solo si el contenido excede la altura visible.
        def _on_wheel(e):
            x0, y0, x1, y1 = canvas.bbox("all") or (0, 0, 0, 0)
            if (y1 - y0) <= canvas.winfo_height():
                return
            canvas.yview_scroll(int(-e.delta / 120), "units")

        def _bind_wheel(_e=None):
            canvas.bind_all("<MouseWheel>", _on_wheel)

        def _unbind_wheel(_e=None):
            canvas.unbind_all("<MouseWheel>")
        interior.bind("<Enter>", _bind_wheel)
        interior.bind("<Leave>", _unbind_wheel)

        self._contenedores_pagina[pid] = cont
        return interior

    def _mostrar_pagina(self, pid: str):
        # Ocultar todas (el contenedor externo canvas+scrollbar)
        for p, cont in self._contenedores_pagina.items():
            cont.pack_forget()

        # Mostrar la seleccionada
        self._contenedores_pagina[pid].pack(fill="both", expand=True)
        self._pagina_activa.set(pid)
        self._current_page = pid

        # Activar el contexto del activity bar que contiene este pid
        for ctx_id, _, _, pids in self._CONTEXTOS:
            if pid in pids:
                if self._ctx_activo.get() != ctx_id:
                    self._ctx_activo.set(ctx_id)
                    for cid, widgets in self._ab_btns.items():
                        widgets["ind"].config(bg=AB_IND if cid == ctx_id else AB_BG)
                        widgets["lbl"].config(fg=TXT_PRI if cid == ctx_id else AB_TXT)
                    # …y repoblar el sidebar, que si no se queda mostrando los
                    # paneles del contexto anterior (llegar aquí desde una
                    # acción del tablero dejaba «Inicio» en la columna mientras
                    # el contenido ya era otro). Diferido: repoblar destruye los
                    # botones del sidebar, y uno de ellos puede ser el que está
                    # atendiendo este mismo clic.
                    self.after(0, lambda c=ctx_id: self._poblar_sidebar_contexto(c))
                break

        # Actualizar estilos del sidebar
        for p, widgets in self._sb_btns.items():
            self._aplicar_estilo_sb_btn(p, widgets, p == pid)

        # Acciones al entrar a páginas específicas
        if pid == "norm":
            self.after(50, self._norm_refrescar_numeros)
        elif pid == "inicio":
            # El tablero resume el estado del proyecto: al volver a él siempre
            # se relee, no se deja la foto de cuando se construyó la ventana.
            self.after(30, self._inicio_refrescar)

    def _actualizar_badges(self):
        """Actualiza los semáforos del sidebar según estado de etapas y badges legacy."""
        _semaforo_etapa = {
            "etz":  "etz",
            "ocr":  "ocr",
            "norm": "norm",
            "seg":  "seg",
            "anal": "anal",
        }
        for pid, widgets in self._sb_btns.items():
            badge_lbl = widgets.get("badge")
            if badge_lbl is None:
                continue
            bg = SB_BG if self._pagina_activa.get() != pid else SB_SEL

            # Semáforo de flujo (prioridad sobre badge legacy)
            if pid in _semaforo_etapa:
                estado = ST.estado_etapas.get(pid, "pending")
                if estado == "ready":
                    badge_lbl.config(text="✓", fg=VERDE, bg=bg)
                    badge_lbl.pack(side="right", padx=6)
                elif estado == "stale":
                    badge_lbl.config(text="⚠", fg="#E6A64C", bg=bg)
                    badge_lbl.pack(side="right", padx=6)
                else:
                    badge_lbl.pack_forget()
                continue

            # Badge legacy (✓) para páginas sin semáforo de flujo
            attr = widgets.get("badge_attr")
            if attr and getattr(ST, attr, False):
                badge_lbl.config(text="✓", fg=VERDE, bg=bg)
                badge_lbl.pack(side="right", padx=6)
            else:
                badge_lbl.pack_forget()

    def _abrir_docs(self):
        doc = Path(__file__).parent / "PROMPT_SISTEMA.md"
        if not doc.exists():
            return
        if plataforma.es_windows():
            # En Windows .md no siempre tiene programa asociado; el bloc de
            # notas está siempre y garantiza que el documento se vea.
            import subprocess
            subprocess.Popen(["notepad.exe", str(doc)])
        else:
            # "open" solo existe en macOS: fuera de Windows manda la capa de
            # sistema, que en Linux usa xdg-open.
            plataforma.abrir_en_sistema(doc)

    # ── Compatibilidad con código que usa self._nb.select(n) ──────────────────
    class _FakeNb:
        """Proxy para compatibilidad con self._nb.select(índice)."""
        def __init__(self, app):
            self._app = app
        def select(self, idx):
            pids = [p for p,*_ in BashkarApp._PAGINAS]
            if isinstance(idx, int) and idx < len(pids):
                self._app._mostrar_pagina(pids[idx])

    @property
    def _nb(self): return self._FakeNb(self)

    # ── Header de sección (reutilizable) ──────────────────────────────────────
    def _page_header(self, parent, titulo: str, subtitulo: str = "",
                     emoji: str = "") -> tk.Frame:
        """Crea un encabezado estilizado para cada página."""
        hdr = tk.Frame(parent, bg=CONTENT_BG)
        hdr.pack(fill="x", padx=0, pady=0)

        # Banda de color superior
        banda = tk.Frame(hdr, bg=AZ3, height=3)
        banda.pack(fill="x")

        inner = tk.Frame(hdr, bg=CONTENT_BG)
        inner.pack(fill="x", padx=28, pady=(16, 8))

        if emoji:
            tk.Label(inner, text=emoji, bg=CONTENT_BG, fg=AZ3,
                     font=("Segoe UI", 20)).pack(side="left", padx=(0, 12))
        txt_frame = tk.Frame(inner, bg=CONTENT_BG)
        txt_frame.pack(side="left", fill="x", expand=True)
        tk.Label(txt_frame, text=titulo, bg=CONTENT_BG, fg=TXT_PRI,
                 font=("Segoe UI", 14, "bold"), anchor="w").pack(anchor="w")
        if subtitulo:
            tk.Label(txt_frame, text=subtitulo, bg=CONTENT_BG, fg=TXT_SEC,
                     font=("Segoe UI", 9), anchor="w").pack(anchor="w")

        # ── Guía del módulo (qué es / para qué / cómo interpretar) ──────────
        # Se inyecta según el id de página que el constructor fijó antes de
        # llamar a build_fn. Siempre visible el resumen; colapsable la guía
        # de interpretación profunda (orientada a investigación HD).
        self._inyectar_guia_modulo(hdr, getattr(self, "_guia_pagina_actual", None))

        # Línea separadora
        tk.Frame(hdr, bg=CARD_BOR, height=1).pack(fill="x")
        return hdr

    def _inyectar_guia_modulo(self, parent, page_id) -> None:
        """Bajo el encabezado del panel, muestra la guía del módulo en dos
        secciones colapsables (cerradas por defecto): «ℹ Qué es esta
        herramienta» (qué es / para qué) y «📖 Cómo interpretar los
        resultados». Silencioso si no hay guía para la página."""
        if not page_id:
            return
        try:
            from core import guia_modulos
        except ImportError:
            return
        resumen = guia_modulos.resumen_visible(page_id)
        if not resumen:
            return
        interpretacion = guia_modulos.guia_interpretacion(page_id)

        cont = tk.Frame(parent, bg=CONTENT_BG)
        cont.pack(fill="x", padx=28, pady=(0, 8))

        # «Qué es esta herramienta» — colapsable (lazy), cerrado por defecto
        def _build_resumen(frame):
            caja = tk.Frame(frame, bg=CARD_BG, bd=0)
            caja.pack(fill="x")
            tk.Frame(caja, bg=AZ3, width=3).pack(side="left", fill="y")
            tk.Label(caja, text=resumen, bg=CARD_BG, fg=TXT_SEC,
                     font=("Segoe UI", 9), anchor="w", justify="left",
                     wraplength=640).pack(side="left", fill="x",
                                          expand=True, padx=12, pady=8)
        self._mk_avanzado(cont, "ℹ  Qué es esta herramienta", _build_resumen)

        # Sección colapsable con la guía de interpretación (lazy)
        if interpretacion:
            def _build_interp(frame):
                ic = tk.Frame(frame, bg=CARD_BG)
                ic.pack(fill="x")
                tk.Frame(ic, bg="#6EC69A", width=3).pack(side="left", fill="y")
                tk.Label(ic, text=interpretacion, bg=CARD_BG, fg=TXT_SEC,
                         font=("Segoe UI", 9), anchor="w", justify="left",
                         wraplength=640).pack(side="left", fill="x",
                                              expand=True, padx=12, pady=8)
            self._mk_avanzado(cont, "📖  Cómo interpretar los resultados",
                              _build_interp)

    # ── Card dark mode ─────────────────────────────────────────────────────────
    def _card(self, parent, titulo: str = "", padding: int = 16) -> tk.Frame:
        """Crea una tarjeta oscura con borde sutil estilo GitHub dark."""
        outer = tk.Frame(parent, bg=CARD_BOR, bd=0)
        outer.pack(fill="x", padx=24, pady=6)
        inner = tk.Frame(outer, bg=CARD_BG, bd=0)
        inner.pack(fill="x", padx=1, pady=1)
        if titulo:
            title_bar = tk.Frame(inner, bg=CARD_BG)
            title_bar.pack(fill="x", padx=padding, pady=(padding, 4))
            tk.Frame(title_bar, bg=AZ3, width=3, height=18).pack(side="left")
            tk.Label(title_bar, text=f"  {titulo}", bg=CARD_BG, fg=TXT_PRI,
                     font=("Segoe UI", 10, "bold")).pack(side="left")
            tk.Frame(inner, bg=CARD_BOR, height=1).pack(fill="x", padx=padding)
        content = tk.Frame(inner, bg=CARD_BG)
        content.pack(fill="x", padx=padding, pady=padding)
        return content

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1: CONFIGURACIÓN
    # ══════════════════════════════════════════════════════════════════════════
    def _mk_ayuda(self, parent, texto: str):
        lbl = tk.Label(parent, text=" ❓", fg=TXT_DIM, bg=CARD_BG,
                       font=("Segoe UI", 9), cursor="question_arrow")
        lbl.pack(side="left")
        tip_win = [None]
        def show(event):
            tw = tk.Toplevel(lbl); tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{event.x_root+12}+{event.y_root+8}")
            tk.Message(tw, text=texto, bg="#30291F", fg="#E8E5DF",
                       relief="flat", font=("Segoe UI", 9),
                       width=340, padx=12, pady=10).pack()
            tip_win[0] = tw
        def hide(_event):
            if tip_win[0]: tip_win[0].destroy(); tip_win[0]=None
        lbl.bind("<Enter>", show); lbl.bind("<Leave>", hide)
        return lbl

    def _mk_ayuda_bg(self, parent, texto: str, bg: str):
        """Como _mk_ayuda pero con bg configurable (para barras de color distinto)."""
        lbl = tk.Label(parent, text=" ❓", fg=TXT_DIM, bg=bg,
                       font=("Segoe UI", 9), cursor="question_arrow")
        lbl.pack(side="left")
        tip_win = [None]
        def show(event):
            tw = tk.Toplevel(lbl); tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{event.x_root+12}+{event.y_root+8}")
            tk.Message(tw, text=texto, bg="#30291F", fg="#E8E5DF",
                       relief="flat", font=("Segoe UI", 9),
                       width=340, padx=12, pady=10).pack()
            tip_win[0] = tw
        def hide(_event):
            if tip_win[0]: tip_win[0].destroy(); tip_win[0]=None
        lbl.bind("<Enter>", show); lbl.bind("<Leave>", hide)
        return lbl

    def _build_cfg(self):
        f = self._tab_cfg
        self._page_header(f, "Configuración del corpus",
                          "Define la publicación, los archivos y los parámetros del análisis",
                          "⚙")

        # `f` (= self._tab_cfg) YA es el frame interior de un Canvas+Scrollbar
        # que arma `_crear_pagina_scrollable` para TODAS las páginas — no hay
        # que envolverlo en OTRO canvas (ese doble canvas era el que dejaba un
        # hueco enorme sin usar: el canvas interno se estiraba a toda la
        # altura de la ventana aunque el contenido real fuera corto). Un
        # frame simple con pack(fill="x") basta, igual que en el resto de
        # páginas — su alto lo define el contenido, no la ventana.
        pad = tk.Frame(f, bg=CONTENT_BG)
        pad.pack(fill="x")
        pad.columnconfigure(0, weight=1)
        r = 0

        # Registro de secciones colapsables: {id: {"open": BooleanVar, "body": Frame}}
        _secciones_cfg: dict = {}

        def _seccion(sec_id: str, num: str, titulo: str, subtitulo: str = "",
                     abierta: bool = True):
            """
            Crea un encabezado de sección colapsable numerado.
            Retorna el frame 'body' donde se coloca el contenido de la sección.
            El body se muestra/oculta al hacer click en el encabezado.
            """
            nonlocal r
            var_open = tk.BooleanVar(value=abierta)

            # ── Fila del encabezado ─────────────────────────────────────────────
            hdr = tk.Frame(pad, bg=CONTENT_BG, cursor="hand2")
            hdr.grid(row=r, column=0, sticky="ew", padx=24, pady=(20 if num == "1" else 8, 2))
            r += 1

            arrow_lbl = tk.Label(hdr, text="▼" if abierta else "▶",
                                 bg=CONTENT_BG, fg=AZ3,
                                 font=("Segoe UI", 10, "bold"))
            arrow_lbl.pack(side="left", padx=(0, 8))

            tk.Label(hdr, text=f"{num} · {titulo}", bg=CONTENT_BG,
                     fg=TXT_PRI, font=("Segoe UI", 11, "bold")).pack(side="left")

            if subtitulo:
                tk.Label(hdr, text=f"  {subtitulo}", bg=CONTENT_BG,
                         fg="#777F84", font=("Segoe UI", 8)).pack(side="left", padx=(8, 0))

            # ── Body colapsable ─────────────────────────────────────────────────
            body = tk.Frame(pad, bg=CONTENT_BG)
            body.grid(row=r, column=0, sticky="ew")
            body.columnconfigure(0, weight=1)
            if not abierta:
                body.grid_remove()
            r += 1

            def _toggle(e=None):
                if var_open.get():
                    var_open.set(False)
                    body.grid_remove()
                    arrow_lbl.config(text="▶")
                else:
                    var_open.set(True)
                    body.grid()
                    arrow_lbl.config(text="▼")

            for w in (hdr, arrow_lbl):
                w.bind("<Button-1>", _toggle)
                w.bind("<Enter>", lambda e, h=hdr: h.config(bg="#101316"))
                w.bind("<Leave>", lambda e, h=hdr: h.config(bg=CONTENT_BG))
            for child in hdr.winfo_children():
                child.bind("<Button-1>", _toggle)

            _secciones_cfg[sec_id] = {"open": var_open, "body": body}
            return body

        def card_lf(titulo, parent=None):
            """LabelFrame estilo card. Si parent es un body de sección, usa pack."""
            nonlocal r
            if parent is not None:
                # Dentro de un body colapsable — usar pack para apilar varias cards
                outer = tk.Frame(parent, bg=CARD_BOR)
                outer.pack(fill="x", padx=24, pady=4)
            else:
                outer = tk.Frame(pad, bg=CARD_BOR)
                outer.grid(row=r, column=0, sticky="ew", padx=24, pady=4)
                r += 1
            inner = tk.Frame(outer, bg=CARD_BG, padx=16, pady=14)
            inner.pack(fill="x", padx=1, pady=1)
            inner.columnconfigure(1, weight=1)
            title_row = tk.Frame(inner, bg=CARD_BG)
            title_row.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
            tk.Frame(title_row, bg=AZ3, width=3, height=16).pack(side="left")
            tk.Label(title_row, text=f"  {titulo}", bg=CARD_BG, fg=TXT_PRI,
                     font=("Segoe UI", 10, "bold")).pack(side="left")
            return inner

        def sep():
            nonlocal r
            tk.Frame(pad, bg=CARD_BOR, height=1).grid(
                row=r, column=0, sticky="ew", padx=24, pady=6); r+=1

        # ── Sección 1 ─────────────────────────────────────────────────────────
        body1 = _seccion("id", "1", "Identificación del proyecto",
                         "Estos datos aparecerán en todos los informes generados.")
        c1 = card_lf("🗞  Publicación y período", body1)
        tk.Label(c1, text="Nombre:", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI",9,"bold")).grid(row=1,column=0,sticky="w",pady=5)
        self._var_pub = tk.StringVar(value="Mi publicación")
        # Reflejo en tiempo real: actualizar etiqueta de nombre en topbar y sidebar
        def _sync_nombre(*_):
            nombre = self._var_pub.get().strip() or "Sin proyecto"
            self._set_pub_hdr(nombre)
            if hasattr(self, "_lbl_proyecto"):
                self._lbl_proyecto.config(text=nombre)
        self._var_pub.trace_add("write", _sync_nombre)
        tk.Entry(c1, textvariable=self._var_pub, width=52,
                 font=("Segoe UI",10), relief="solid", bd=1,
                 bg="#171C20").grid(row=1,column=1,sticky="ew",padx=8)
        tk.Label(c1, text="Período:", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI",9,"bold")).grid(row=2,column=0,sticky="w",pady=5)
        self._var_per = tk.StringVar()
        tk.Entry(c1, textvariable=self._var_per, width=34,
                 font=("Segoe UI",10), relief="solid", bd=1,
                 bg="#171C20").grid(row=2,column=1,sticky="w",padx=8)
        tk.Label(c1, text='Ej.: "enero–junio 1939"', bg=CARD_BG,
                 fg="#646D72", font=("Segoe UI",8)).grid(row=2,column=2,sticky="w")
        # Tipo de corpus
        tk.Label(c1, text="Tipo:", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI",9,"bold")).grid(row=3,column=0,sticky="w",pady=5)
        self._var_tipo_corpus = tk.StringVar(value="revista")
        ttk.Combobox(c1, textvariable=self._var_tipo_corpus,
                     values=["revista", "periódico", "libro", "colección"],
                     state="readonly", width=18,
                     font=("Segoe UI",9)).grid(row=3,column=1,sticky="w",padx=8)
        # Idioma
        tk.Label(c1, text="Idioma:", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI",9,"bold")).grid(row=4,column=0,sticky="w",pady=5)
        self._var_idioma = tk.StringVar(value="español histórico")
        ttk.Combobox(c1, textvariable=self._var_idioma,
                     values=["español histórico", "español moderno", "otro"],
                     state="readonly", width=18,
                     font=("Segoe UI",9)).grid(row=4,column=1,sticky="w",padx=8)
        # Investigador e institución
        tk.Label(c1, text="Investigador:", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI",9,"bold")).grid(row=5,column=0,sticky="w",pady=5)
        self._var_investigador = tk.StringVar()
        tk.Entry(c1, textvariable=self._var_investigador, width=34,
                 font=("Segoe UI",9), relief="solid", bd=1,
                 bg="#171C20").grid(row=5,column=1,sticky="w",padx=8)
        tk.Label(c1, text="Institución:", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI",9,"bold")).grid(row=6,column=0,sticky="w",pady=5)
        self._var_institucion = tk.StringVar(value="Instituto Caro y Cuervo")
        tk.Entry(c1, textvariable=self._var_institucion, width=40,
                 font=("Segoe UI",9), relief="solid", bd=1,
                 bg="#171C20").grid(row=6,column=1,sticky="ew",padx=8)

        # ── Sección 2 ─────────────────────────────────────────────────────────
        body2 = _seccion("archivos", "2", "Archivos de entrada",
                         "Bashkar detecta automáticamente PDFs con texto embebido vs. escaneados.")
        c2 = card_lf("📁  Tipo y carpeta de archivos", body2)
        self._var_tipo = tk.StringVar(value="pdf")
        ttk.Radiobutton(c2, text="📄  PDFs — un archivo por número (la app detecta texto vs. OCR)",
                        variable=self._var_tipo, value="pdf",
                        command=self._on_tipo, style="TRadiobutton").grid(
                        row=1, column=0, columnspan=3, sticky="w", pady=2)
        ttk.Radiobutton(c2,
                        text="📁  Subcarpetas — cada subcarpeta es un número (ej. corpus BNC/Hemeroteca)",
                        variable=self._var_tipo, value="carpetas",
                        command=self._on_tipo, style="TRadiobutton").grid(
                        row=2, column=0, columnspan=3, sticky="w", pady=2)
        ttk.Radiobutton(c2, text="🖼  Imágenes sueltas (JPG/PNG/TIFF — siempre OCR)",
                        variable=self._var_tipo, value="img",
                        command=self._on_tipo, style="TRadiobutton").grid(
                        row=3, column=0, columnspan=3, sticky="w", pady=(2,6))

        # Separador entre tipo y carpetas
        tk.Frame(c2, bg=CARD_BOR, height=1).grid(row=4, column=0, columnspan=3,
                                                   sticky="ew", pady=(0, 8))
        tk.Label(c2, text="Carpeta de entrada:", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI",9,"bold")).grid(row=5,column=0,sticky="w",pady=4)
        self._var_ent = tk.StringVar()
        ent_row = tk.Frame(c2, bg=CARD_BG); ent_row.grid(row=5,column=1,columnspan=2,sticky="ew",padx=8)
        self._lf_ent = ent_row   # compatibilidad
        tk.Entry(ent_row, textvariable=self._var_ent, width=52,
                 font=("Segoe UI",9), relief="solid", bd=1,
                 bg="#171C20").pack(side="left", fill="x", expand=True)
        ttk.Button(ent_row, text="Examinar…", style="S.TButton",
                   command=self._pick_ent).pack(side="left", padx=(6,0))

        # Salida
        tk.Label(c2, text="Carpeta de salida:", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI",9,"bold")).grid(row=6,column=0,sticky="w",pady=4)
        self._var_sal = tk.StringVar()
        sal_row = tk.Frame(c2, bg=CARD_BG); sal_row.grid(row=6,column=1,columnspan=2,sticky="ew",padx=8)
        tk.Entry(sal_row, textvariable=self._var_sal, width=52,
                 font=("Segoe UI",9), relief="solid", bd=1,
                 bg="#171C20").pack(side="left", fill="x", expand=True)
        ttk.Button(sal_row, text="Examinar…", style="S.TButton",
                   command=self._pick_sal).pack(side="left", padx=(6,0))

        # Lista de archivos
        tk.Label(c2, text="Archivos a analizar:", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI",9,"bold")).grid(row=7,column=0,sticky="nw",pady=(8,0))
        arch_frame = tk.Frame(c2, bg=CARD_BG)
        arch_frame.grid(row=7,column=1,columnspan=2,sticky="ew",padx=8,pady=(6,0))
        btn_arch = tk.Frame(arch_frame, bg=CARD_BG); btn_arch.pack(fill="x")
        ttk.Button(btn_arch, text="☑ Todos", style="S.TButton",
                   command=lambda: self._sel_todos(True)).pack(side="left", padx=(0,4))
        ttk.Button(btn_arch, text="☐ Ninguno", style="S.TButton",
                   command=lambda: self._sel_todos(False)).pack(side="left")
        self._lbl_arch_info = tk.Label(btn_arch, text="(primero selecciona la carpeta)",
                                        bg=CARD_BG, fg="#646D72", font=("Segoe UI",8))
        self._lbl_arch_info.pack(side="left", padx=10)
        lb_frame = tk.Frame(arch_frame, bg=CARD_BOR, bd=1, relief="solid")
        lb_frame.pack(fill="x", pady=(4,0))
        sby_lb = ttk.Scrollbar(lb_frame, orient="vertical")
        self._lb = tk.Listbox(lb_frame, selectmode="multiple", height=10,
                              font=("Courier",9), bg="#171C20", relief="flat",
                              yscrollcommand=sby_lb.set, selectbackground=AZ3,
                              selectforeground="white", activestyle="none")
        sby_lb.config(command=self._lb.yview)
        sby_lb.pack(side="right", fill="y"); self._lb.pack(fill="x", expand=True)
        self._archivos_disp = []

        # ── Sección 3 ─────────────────────────────────────────────────────────
        body3 = _seccion("ocr", "3", "Calidad de lectura OCR")
        c3 = card_lf("🔬  Resolución e idioma", body3)
        tk.Label(c3, text="Resolución (DPI):", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI",9,"bold")).grid(row=1,column=0,sticky="w",pady=5)
        dpi_row = tk.Frame(c3, bg=CARD_BG); dpi_row.grid(row=1,column=1,sticky="w",padx=8)
        self._var_dpi = tk.StringVar(value="150")
        for val, etiq in [("100","100 DPI · Rápido"),("150","150 DPI · Recomendado ✓"),
                           ("200","200 DPI · Alta calidad"),("300","300 DPI · Máxima")]:
            ttk.Radiobutton(dpi_row, text=etiq, variable=self._var_dpi,
                            value=val).pack(side="left", padx=8)
        self._mk_ayuda(dpi_row,
            "100 DPI: ~20 seg/número, puede perder letras pequeñas.\n"
            "150 DPI: equilibrio recomendado (~45 seg/número).\n"
            "200 DPI: mejor para textos con letra pequeña (~90 seg).\n"
            "300 DPI: máxima precisión, lento (~3 min/número).")

        tk.Label(c3, text="Idioma:", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI",9,"bold")).grid(row=2,column=0,sticky="w",pady=5)
        lang_row = tk.Frame(c3, bg=CARD_BG); lang_row.grid(row=2,column=1,sticky="w",padx=8)
        self._var_lang = tk.StringVar(value="spa")
        for val, etiq in [("spa","Español"),("spa+eng","Esp + Inglés"),("eng","Inglés")]:
            ttk.Radiobutton(lang_row, text=etiq, variable=self._var_lang,
                            value=val).pack(side="left", padx=8)

        # Lematización configurable (corpus histórico = mejor sin lematizar)
        tk.Label(c3, text="Análisis léxico:", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI",9,"bold")).grid(row=3,column=0,sticky="w",pady=5)
        lem_row = tk.Frame(c3, bg=CARD_BG); lem_row.grid(row=3,column=1,sticky="w",padx=8)
        self._var_lematizar = tk.BooleanVar(value=True)
        ttk.Checkbutton(lem_row, text="Lematizar (formas → lema base)",
                        variable=self._var_lematizar,
                        command=lambda: setattr(ST, "lematizar",
                                               self._var_lematizar.get())).pack(side="left")
        self._mk_ayuda(lem_row,
            "ACTIVADO (recomendado para español moderno):\n"
            "  'corrían', 'corrió', 'correr' → 'correr'\n"
            "  Mejora el recall en análisis de temas.\n\n"
            "DESACTIVADO (recomendado para corpus histórico):\n"
            "  Preserva formas originales: 'corrían', 'habia', 'fué'\n"
            "  Esencial para estudio de variación lingüística diacrónica.\n"
            "  Bashkar Station detectó que tu corpus es español histórico.")

        # ── Sección 4 ─────────────────────────────────────────────────────────
        body4 = _seccion("modulos", "4", "Módulos de análisis",
                         "Activa solo los módulos que necesitas para tu investigación.")
        c4 = card_lf("🧩  Módulos activos", body4)
        self._var_seg    = tk.BooleanVar(value=True)
        self._var_w2v    = tk.BooleanVar(value=False)
        self._var_vis    = tk.BooleanVar(value=True)
        self._var_red    = tk.BooleanVar(value=True)
        self._var_layout = tk.BooleanVar(value=True)

        modulos_def = [
            (self._var_seg,    "📝  Segmentación de artículos y atribución de autoría",
             "Divide cada número en artículos individuales y detecta quién los firmó."),
            (self._var_w2v,    "🧠  Word2Vec (expansión semántica)",
             "Entrena un modelo de vectores sobre el corpus para expandir automáticamente los campos temáticos. Requiere ≥50 páginas."),
            (self._var_vis,    "🖼  Análisis visual y tipográfico",
             "Detecta fotografías, ilustraciones y publicidades. Analiza fuentes tipográficas."),
            (self._var_red,    "🕸  Red de colaboración entre autores",
             "Construye un grafo de quiénes colaboraron en los mismos números."),
            (self._var_layout, "📐  Análisis de layout (distribución texto/imagen)",
             "Mide la proporción de espacio editorial dedicado a texto vs. imagen por número."),
        ]
        for i, (var, etiq, desc) in enumerate(modulos_def, 1):
            mod_row = tk.Frame(c4, bg=CARD_BG); mod_row.grid(
                row=i, column=0, columnspan=3, sticky="ew", pady=3)
            cb = ttk.Checkbutton(mod_row, text=etiq, variable=var)
            cb.pack(side="left")
            self._mk_ayuda(mod_row, desc)

        # ── Sección 5 ─────────────────────────────────────────────────────────
        body5 = _seccion("ajuste", "5", "Ajuste fino (opcional)", abierta=False)
        c5 = card_lf("🎛  Parámetros avanzados", body5)
        # spaCy
        tk.Label(c5, text="Precisión NLP:", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI",9,"bold")).grid(row=1,column=0,sticky="w",pady=5)
        spacy_row = tk.Frame(c5, bg=CARD_BG); spacy_row.grid(row=1,column=1,sticky="w",padx=8)
        self._var_spacy = tk.StringVar(value="es_core_news_sm")
        for val, etiq in [("es_core_news_sm","Pequeño ✓"),
                           ("es_core_news_md","Mediano"),
                           ("es_core_news_lg","Grande")]:
            ttk.Radiobutton(spacy_row, text=etiq, variable=self._var_spacy,
                            value=val).pack(side="left", padx=8)
        self._mk_ayuda(spacy_row,
            "Pequeño: rápido, suficiente para la mayoría de casos.\n"
            "Mediano: incluye vectores pre-entrenados (~43 MB).\n"
            "Grande: máxima precisión, requiere ~700 MB.")
        # LDA
        tk.Label(c5, text="Temas LDA:", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI",9,"bold")).grid(row=2,column=0,sticky="w",pady=5)
        lda_row = tk.Frame(c5, bg=CARD_BG); lda_row.grid(row=2,column=1,sticky="w",padx=8)
        self._var_lda = tk.IntVar(value=6)
        tk.Spinbox(lda_row, from_=3, to=20, textvariable=self._var_lda,
                   width=5, font=("Segoe UI",10), relief="solid", bd=1).pack(side="left")
        tk.Label(lda_row, text="  (3–20 temas latentes)", bg=CARD_BG,
                 fg="#646D72", font=("Segoe UI",8)).pack(side="left")
        self._mk_ayuda(lda_row,
            "Corpus pequeño (2-5 números): 4-6 temas.\n"
            "Corpus mediano (6-20 números): 6-10 temas.\n"
            "Si los temas son demasiado similares, reduce el número.")
        # Red — umbral
        tk.Label(c5, text="Umbral red:", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI",9,"bold")).grid(row=3,column=0,sticky="w",pady=5)
        red_row = tk.Frame(c5, bg=CARD_BG); red_row.grid(row=3,column=1,sticky="w",padx=8)
        self._var_red_min = tk.IntVar(value=2)
        tk.Spinbox(red_row, from_=1, to=10, textvariable=self._var_red_min,
                   width=5, font=("Segoe UI",10), relief="solid", bd=1).pack(side="left")
        tk.Label(red_row, text="  apariciones mínimas en el corpus", bg=CARD_BG,
                 fg="#646D72", font=("Segoe UI",8)).pack(side="left")
        self._mk_ayuda(red_row,
            "1: todos los autores.\n"
            "2: solo autores en ≥2 números (recomendado).\n"
            "3+: solo colaboradores frecuentes.")

        # ── Sección 6 ─────────────────────────────────────────────────────────
        body6 = _seccion("referencia", "6", "Corpus de referencia (comparativo)", abierta=False)
        c6 = card_lf("📚  Carpeta de referencia opcional", body6)
        tk.Label(c6, text="Carpeta:", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI",9,"bold")).grid(row=1,column=0,sticky="w",pady=5)
        self._var_ref = tk.StringVar()
        ref_row = tk.Frame(c6, bg=CARD_BG); ref_row.grid(row=1,column=1,columnspan=2,sticky="ew",padx=8)
        tk.Entry(ref_row, textvariable=self._var_ref, width=52,
                 font=("Segoe UI",9), relief="solid", bd=1, bg="#171C20").pack(
                 side="left", fill="x", expand=True)
        ttk.Button(ref_row, text="Examinar…", style="S.TButton",
                   command=self._pick_ref).pack(side="left", padx=(6,0))
        tk.Label(c6,
                 text="Estructura: referencia/ → El_Tiempo/ → p001.txt, p002.txt…",
                 bg=CARD_BG, fg="#646D72", font=("Segoe UI",8)).grid(
                 row=2, column=0, columnspan=3, sticky="w", pady=(0,4))

        # ── Sección 7 ─────────────────────────────────────────────────────────
        body7 = _seccion("vocab", "7", "Colaboradores y vocabulario", abierta=False)
        c7 = card_lf("👥  Colaboradores conocidos", body7)
        tk.Label(c7, text="Un nombre por línea, exactamente como aparece en la revista:",
                 bg=CARD_BG, fg="#E8E5DF", font=("Segoe UI",9)).grid(
                 row=1, column=0, columnspan=3, sticky="w", pady=(0,6))
        self._txt_col = scrolledtext.ScrolledText(c7, height=12, width=60, font=("Courier",9), bg="#0E1114", fg="#E8E5DF", insertbackground="#E8E5DF", relief="solid", bd=1)
        self._txt_col.grid(row=2, column=0, columnspan=3, sticky="ew")
        self._txt_col.insert("1.0", COLABS_DEFAULT)

        c8 = card_lf("🏷  Campos semánticos de interés", body7)
        import json as _json
        campos_txt = _json.dumps(
            CAMPOS_DEFAULT, ensure_ascii=False, indent=2
        ).strip("{}\n").strip()
        self._txt_sem = scrolledtext.ScrolledText(c8, height=26, width=70, font=("Courier",9), bg="#0E1114", fg="#E8E5DF", insertbackground="#E8E5DF", relief="solid", bd=1)
        self._txt_sem.grid(row=1, column=0, columnspan=3, sticky="ew")
        self._txt_sem.insert("1.0", campos_txt)
        # _mk_ayuda usa .pack() internamente — necesita frame propio (c8 usa grid)
        c8_ayuda_row = tk.Frame(c8, bg=CARD_BG)
        c8_ayuda_row.grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self._mk_ayuda(c8_ayuda_row,
                       "Formato JSON. Cada campo está definido por palabras 'semilla'.\n"
                       "Si activas Word2Vec, el modelo añade automáticamente términos relacionados.")

        # ── Sección 8 ─────────────────────────────────────────────────────────
        body8 = _seccion("ia", "8", "Proveedores de IA y modelos",
                         "Todas las funciones IA son opcionales — la app funciona sin claves.",
                         abierta=False)

        # ── Switch global IA ──────────────────────────────────────────────────
        sw_card = card_lf("🔌  Funciones de inteligencia artificial (IA)", body8)

        # Reutilizar la variable ya creada en _build_topbar (no crear nueva)
        if not hasattr(self, "_var_ia_habilitada"):
            self._var_ia_habilitada = tk.BooleanVar(value=getattr(ST, "ia_habilitada", False))

        sw_top = tk.Frame(sw_card, bg=CARD_BG)
        sw_top.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 8))

        self._lbl_ia_estado = tk.Label(
            sw_top, bg=CARD_BG, font=("Segoe UI", 10, "bold"))
        self._lbl_ia_estado.pack(side="left", padx=(0, 16))

        ttk.Checkbutton(
            sw_top, text="Habilitar IA externa (requiere API key o Ollama local)",
            variable=self._var_ia_habilitada,
            command=self._cfg_toggle_ia
        ).pack(side="left")

        info_ia = (
            "Cuando está DESACTIVADO (modo offline):\n"
            "  • OCR: Tesseract y Kraken funcionan normalmente\n"
            "  • NER: solo BERT local (mrm8488/bert-spanish-cased-finetuned-ner)\n"
            "  • Búsqueda semántica: embeddings locales (MiniLM)\n"
            "  • Tono, narrativas, asistente: no disponibles\n\n"
            "Cuando está ACTIVADO:\n"
            "  • Se habilitan todas las funciones que requieren API externa\n"
            "  • Cada llamada consume crédito del proveedor configurado\n"
            "  • Los datos del corpus se envían a servidores externos\n"
            "  • Ollama (si está configurado) funciona localmente sin enviar datos"
        )
        tk.Label(sw_card, text=info_ia,
                 bg=CARD_BG, fg="#E8E5DF", font=("Segoe UI", 8),
                 justify="left", wraplength=580).grid(
                 row=2, column=0, columnspan=3, sticky="w", pady=(0, 4))

        self._cfg_toggle_ia()  # actualizar etiqueta al cargar

        # ── Card: Claves API ──────────────────────────────────────────────────
        c9 = card_lf("🔑  Claves API por proveedor", body8)

        # Variable legado (compatibilidad con el resto del código)
        self._var_api_key = tk.StringVar()

        # Variables individuales por proveedor
        self._var_key_anthropic = tk.StringVar()
        self._var_key_openai    = tk.StringVar()
        self._var_key_gemini    = tk.StringVar()
        self._var_key_ollama    = tk.StringVar(value="http://localhost:11434")

        _proveedores_info = [
            ("anthropic", "Anthropic Claude", self._var_key_anthropic,
             "sk-ant-…",
             "Prefijo: sk-ant-…\n\n"
             "Modelos disponibles:\n"
             "  claude-fable-5      — el más capaz (máx.)\n"
             "  claude-opus-4-8     — muy potente\n"
             "  claude-sonnet-4-6   — equilibrio costo/calidad ✓\n"
             "  claude-haiku-4-5    — el más económico\n\n"
             "Costo aproximado por página OCR: ~$0.003\n"
             "Obtén tu clave en: console.anthropic.com"),
            ("openai", "OpenAI", self._var_key_openai,
             "sk-…",
             "Prefijo: sk-…\n\n"
             "Modelos disponibles:\n"
             "  gpt-5.5             — visión + texto, máxima calidad\n"
             "  gpt-5.4-mini        — más económico ✓\n"
             "  gpt-4o              — alternativa previa\n\n"
             "Costo aproximado por página OCR: ~$0.005\n"
             "Obtén tu clave en: platform.openai.com"),
            ("gemini", "Google Gemini", self._var_key_gemini,
             "AIza…",
             "Prefijo: AIza…\n\n"
             "Modelos disponibles:\n"
             "  gemini-2.5-flash    — muy económico ✓✓\n"
             "  gemini-2.5-pro      — alta calidad\n"
             "  gemini-3.1-flash    — nueva generación, rápido ✓\n"
             "  gemini-3-pro        — el más capaz\n\n"
             "Costo aproximado por página OCR: ~$0.0001 (más barato)\n"
             "Obtén tu clave en: aistudio.google.com"),
            ("ollama", "Ollama (local)", self._var_key_ollama,
             "http://localhost:11434",
             "URL del servidor Ollama local.\n"
             "Por defecto: http://localhost:11434\n\n"
             "Modelos ya instalados en este equipo (detectados con 'ollama list'):\n"
             "  qwen3.6            — visión + texto + tools/thinking, 36B\n"
             "  gemma4             — visión + texto + tools/thinking, 8B\n"
             "  gemma3:4b          — visión + texto, 4B (más liviano)\n\n"
             "Otros modelos recomendados (instalar con 'ollama pull'):\n"
             "  llava              — visión + texto\n"
             "  mistral            — texto, rápido\n"
             "  llama3.2           — texto, buena calidad\n"
             "  latamgpt           — texto, español latinoamericano ✓ (recomendado para Estampa)\n\n"
             "Ventaja: 100% offline, sin costo por token.\n"
             "Requiere: ollama instalado y corriendo localmente."),
        ]

        for fila_idx, (prov_id, prov_label, prov_var, placeholder, ayuda_txt) in enumerate(_proveedores_info, 1):
            tk.Label(c9, text=f"{prov_label}:", bg=CARD_BG, fg="#E8E5DF",
                     font=("Segoe UI",9,"bold")).grid(row=fila_idx, column=0, sticky="w", pady=4)
            prow = tk.Frame(c9, bg=CARD_BG)
            prow.grid(row=fila_idx, column=1, columnspan=2, sticky="ew", padx=8)
            ent = tk.Entry(prow, textvariable=prov_var, width=42,
                           font=("Courier", 9), relief="solid", bd=1, bg="#171C20",
                           show="*" if prov_id != "ollama" else "")
            ent.pack(side="left", fill="x", expand=True)
            if prov_id != "ollama":
                ttk.Button(prow, text="👁", style="S.TButton",
                           command=lambda e=ent: e.config(
                               show="" if e.cget("show") == "*" else "*")).pack(side="left", padx=2)
            self._mk_ayuda(prow, ayuda_txt)

        # Máximo de imágenes
        tk.Label(c9, text="Máx. imágenes/número:", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI",9,"bold")).grid(row=len(_proveedores_info)+1, column=0, sticky="w", pady=5)
        max_ia_row = tk.Frame(c9, bg=CARD_BG)
        max_ia_row.grid(row=len(_proveedores_info)+1, column=1, sticky="w", padx=8)
        self._var_max_ia = tk.IntVar(value=15)
        tk.Spinbox(max_ia_row, from_=1, to=50, textvariable=self._var_max_ia,
                   width=5, font=("Segoe UI",10), relief="solid", bd=1).pack(side="left")
        tk.Label(max_ia_row, text="  (cada imagen consume crédito de API)", bg=CARD_BG,
                 fg="#646D72", font=("Segoe UI",8)).pack(side="left")

        # ── Card: Modelo por etapa (dentro de body8 también) ────────────────
        c9b = card_lf("⚙️  Modelo activo por etapa del análisis", body8)
        tk.Label(c9b,
                 text="Elige qué proveedor y modelo usar en cada función. "
                      "Pulsa ? para ver en qué se destaca cada opción.",
                 bg=CARD_BG, fg="#777F84", font=("Segoe UI",8),
                 wraplength=560, justify="left").grid(
                 row=1, column=0, columnspan=3, sticky="w", pady=(0,8))

        # Opciones de modelo disponibles: (valor_interno, etiqueta_corta)
        _OPCIONES_MODELO = [
            ("anthropic/claude-fable-5",     "Claude Fable 5 (máx.)"),
            ("anthropic/claude-opus-4-8",    "Claude Opus 4.8"),
            ("anthropic/claude-sonnet-4-6",  "Claude Sonnet 4.6"),
            ("anthropic/claude-haiku-4-5",   "Claude Haiku 4.5"),
            ("openai/gpt-5.5",               "GPT-5.5"),
            ("openai/gpt-5.4-mini",          "GPT-5.4 mini"),
            ("openai/gpt-4o",                "GPT-4o"),
            ("gemini/gemini-3-pro",          "Gemini 3 Pro"),
            ("gemini/gemini-3.1-flash",      "Gemini 3.1 Flash"),
            ("gemini/gemini-2.5-pro",        "Gemini 2.5 Pro"),
            ("gemini/gemini-2.5-flash",      "Gemini 2.5 Flash"),
            ("ollama/qwen3.6",               "Ollama qwen3.6 (visión+texto ✓ instalado)"),
            ("ollama/gemma4",                "Ollama gemma4 (visión+texto ✓ instalado)"),
            ("ollama/gemma3:4b",             "Ollama gemma3:4b (visión, ligero ✓ instalado)"),
            ("ollama/llava",                 "Ollama llava"),
            ("ollama/mistral",               "Ollama mistral"),
        ]
        _vals_modelo = [v for v, _ in _OPCIONES_MODELO]
        _etiq_modelo = [e for _, e in _OPCIONES_MODELO]

        # Definición de etapas: (id, etiqueta UI, ayuda detallada)
        _ETAPAS = [
            ("ocr_mejora", "Mejora OCR (visión)",
             "Analiza imágenes de páginas con baja confianza Tesseract.\n"
             "Requiere modelo con capacidad de visión (imagen → texto).\n\n"
             "Comparación honesta:\n"
             "  GPT-4o        — buen desempeño en layouts multi-columna;\n"
             "                  costo medio (~$0.005/pág); envía datos a OpenAI\n"
             "  Claude Sonnet — desempeño comparable a GPT-4o en texto impreso;\n"
             "                  costo similar; envía datos a Anthropic\n"
             "  Gemini Flash  — el más económico (~$0.0001/pág); menor precisión\n"
             "                  en tipografías deterioradas; envía datos a Google\n"
             "  Ollama llava  — 100% local, sin costo, sin envío de datos;\n"
             "                  precisión notablemente inferior en documentos históricos\n\n"
             "Nota: ningún modelo fue evaluado sistemáticamente en prensa colombiana\n"
             "de los años 30. Los resultados pueden variar según el corpus."),
            ("deteccion", "Detección de zonas (visión)",
             "Identifica en la imagen qué áreas son foto, texto, publicidad, etc.\n"
             "Requiere modelo con capacidad de visión.\n\n"
             "Comparación honesta:\n"
             "  GPT-4o        — buen desempeño general en clasificación visual;\n"
             "                  envía imágenes a servidores de OpenAI\n"
             "  Claude Sonnet — desempeño similar a GPT-4o; envía a Anthropic\n"
             "  Gemini Flash  — más rápido y económico; menor detalle en zonas\n"
             "                  mixtas (texto+imagen en la misma área)\n"
             "  Ollama llava  — local y gratuito; dificultades con layouts complejos\n\n"
             "Alternativa sin API: el etiquetador manual de zonas no requiere IA."),
            ("ner", "Reconocimiento de entidades (NER)",
             "Extrae personas, lugares, organizaciones y eventos del texto OCR.\n\n"
             "Comparación honesta:\n"
             "  BERT local    — gratis, offline, sin envío de datos; entrenado en\n"
             "                  español moderno, menor recall en grafías de época\n"
             "  GPT-4o        — buen desempeño en NER español; costo por token;\n"
             "                  envía texto a OpenAI\n"
             "  Claude Sonnet — desempeño comparable a GPT-4o; envía a Anthropic\n"
             "  Gemini Pro    — resultados similares; envía a Google\n"
             "  Ollama mistral— local, sin costo; menor recall en entidades poco\n"
             "                  frecuentes o con grafía arcaica\n\n"
             "Recomendación práctica: BERT local para exploración inicial;\n"
             "API externa solo para validación o entidades críticas."),
            ("tono", "Análisis de tono editorial",
             "Clasifica artículos en categorías de tono histórico:\n"
             "celebratorio, crítico, elegíaco, polémico, informativo.\n\n"
             "Comparación honesta:\n"
             "  GPT-4o        — buen desempeño en clasificación; puede ser literal\n"
             "                  con ironía y ambigüedad retórica; envía a OpenAI\n"
             "  Claude Sonnet — desempeño similar; envía a Anthropic\n"
             "  Gemini Pro    — resultados comparables; más variable en matices\n"
             "                  culturales latinoamericanos; envía a Google\n"
             "  Ollama llama3 — local y gratuito; peor desempeño en registros\n"
             "                  formales del español de los años 30\n\n"
             "Importante: ninguno de estos modelos fue entrenado específicamente\n"
             "en prensa colombiana. Los resultados requieren validación humana."),
            ("narrativas", "Narrativas académicas automáticas",
             "Genera texto interpretativo sobre los hallazgos del análisis.\n\n"
             "Comparación honesta:\n"
             "  GPT-4o        — buena calidad de escritura académica en español;\n"
             "                  puede producir afirmaciones no respaldadas por los\n"
             "                  datos si el prompt no es preciso; envía a OpenAI\n"
             "  Claude Sonnet — calidad similar; igual riesgo de alucinación si los\n"
             "                  datos de entrada son ambiguos; envía a Anthropic\n"
             "  Gemini Pro    — aceptable; más variable en registro historiográfico\n"
             "  Ollama        — calidad inferior; mayor riesgo de texto genérico\n\n"
             "Advertencia: el texto generado debe revisarse antes de citarse\n"
             "en publicaciones académicas. No sustituye el análisis del investigador."),
            ("asistente", "Asistente IA por pestañas",
             "Responde preguntas sobre los resultados visibles en cada pestaña.\n\n"
             "Comparación honesta:\n"
             "  GPT-4o        — respuestas sólidas; ventana de contexto amplia;\n"
             "                  envía los datos mostrados en pantalla a OpenAI\n"
             "  GPT-4o mini   — más económico; calidad algo menor en razonamiento\n"
             "                  sobre datos complejos\n"
             "  Claude Sonnet — desempeño comparable a GPT-4o; envía a Anthropic\n"
             "  Claude Haiku  — respuestas más rápidas y económicas; menor\n"
             "                  profundidad en análisis historiográfico\n"
             "  Ollama mistral— local, sin costo, sin envío de datos; menor\n"
             "                  capacidad de razonamiento sobre datos estructurados\n\n"
             "Privacidad: con cualquier opción en la nube, los datos del corpus\n"
             "se envían al servidor del proveedor al hacer cada consulta."),
        ]

        self._vars_modelo_etapa = {}
        for fila_e, (etapa_id, etapa_label, etapa_ayuda) in enumerate(_ETAPAS, 2):
            tk.Label(c9b, text=f"{etapa_label}:", bg=CARD_BG, fg="#E8E5DF",
                     font=("Segoe UI",9,"bold")).grid(row=fila_e, column=0, sticky="w", pady=4)
            erow = tk.Frame(c9b, bg=CARD_BG)
            erow.grid(row=fila_e, column=1, sticky="w", padx=8)
            var_e = tk.StringVar(value=ST.modelos_etapa.get(etapa_id, "anthropic/claude-sonnet-4-6"))
            self._vars_modelo_etapa[etapa_id] = var_e
            cb_e = ttk.Combobox(erow, textvariable=var_e,
                                 values=_vals_modelo,
                                 state="readonly", width=30, font=("Segoe UI",9))
            # Mostrar etiquetas cortas en el combo (trucar con postcommand)
            cb_e._etiq = _etiq_modelo
            cb_e._vals = _vals_modelo
            cb_e.pack(side="left")
            self._mk_ayuda(erow, etapa_ayuda)

        c10 = card_lf("🔗  Extracción de metadatos desde URL", body8)
        tk.Label(c10, text="URL:", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI",9,"bold")).grid(row=1,column=0,sticky="w",pady=5)
        url_row = tk.Frame(c10, bg=CARD_BG); url_row.grid(row=1,column=1,columnspan=2,sticky="ew",padx=8)
        self._var_meta_url = tk.StringVar()
        tk.Entry(url_row, textvariable=self._var_meta_url, width=56,
                 font=("Segoe UI",9), relief="solid", bd=1, bg="#171C20").pack(
                 side="left", fill="x", expand=True)
        ttk.Button(url_row, text="Extraer →", style="S.TButton",
                   command=self._extraer_metadatos_url).pack(side="left", padx=(6,0))
        self._txt_meta_result = scrolledtext.ScrolledText(c10, height=14, width=70, font=("Courier",9), bg="#0E1114", fg="#E8E5DF", relief="solid", bd=1, state="disabled")
        self._txt_meta_result.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8,0))

        # ── Botón confirmar ────────────────────────────────────────────────────
        btn_frame = tk.Frame(pad, bg=CONTENT_BG)
        btn_frame.grid(row=r, column=0, pady=(16, 24)); r += 1
        ttk.Button(btn_frame, text="✓  Confirmar configuración y continuar →",
                   style="P.TButton", command=self._confirmar_cfg).pack(side="left")
        self._lbl_cfg_ok = tk.Label(btn_frame, text="", fg=VERDE,
                                     bg=CONTENT_BG, font=("Segoe UI",9,"bold"))
        self._lbl_cfg_ok.pack(side="left", padx=16)

    def _on_tipo(self):
        # _lf_ent is now a plain Frame; we update the label separately if needed
        self._lb.delete(0, "end"); self._archivos_disp = []
        # Si ya había una carpeta de entrada elegida, volver a escanearla con el
        # tipo nuevo. Antes la lista quedaba vacía en silencio hasta que el
        # usuario pulsaba "Examinar…" de nuevo — el campo de carpeta seguía
        # mostrando la ruta, así que parecía configurado y "Confirmar" fallaba
        # una y otra vez con "Selecciona al menos un archivo".
        ruta = self._var_ent.get().strip()
        if ruta and Path(ruta).is_dir():
            self._poblar_lista(Path(ruta))

    def _sel_todos(self, s):
        self._lb.select_set(0,"end") if s else self._lb.select_clear(0,"end")

    def _pick_ent(self):
        d = filedialog.askdirectory(title="Carpeta de entrada")
        if d:
            self._var_ent.set(d); self._poblar_lista(Path(d))

    def _pick_sal(self):
        d = filedialog.askdirectory(title="Carpeta de resultados")
        if d: self._var_sal.set(d)

    def _pick_ref(self):
        d = filedialog.askdirectory(title="Carpeta de publicaciones de referencia")
        if d: self._var_ref.set(d)

    def _extraer_metadatos_url(self):
        url = self._var_meta_url.get().strip()
        if not url:
            messagebox.showwarning("Sin URL", "Introduce una URL en el campo correspondiente.")
            return
        self._txt_meta_result.config(state="normal")
        self._txt_meta_result.delete("1.0", "end")
        self._txt_meta_result.insert("1.0", "⏳ Extrayendo metadatos… (puede tardar unos segundos)\n")
        self._txt_meta_result.config(state="disabled")
        self.update_idletasks()

        def _worker():
            try:
                from core.metadata_fetcher import extraer_metadatos_url
                datos = extraer_metadatos_url(url)
            except Exception as e:
                datos = {"exito": False, "error": str(e)}
            self.after(0, lambda d=datos: self._mostrar_metadatos(d))

        threading.Thread(target=_worker, daemon=True).start()

    def _mostrar_metadatos(self, datos: dict):
        self._txt_meta_result.config(state="normal")
        self._txt_meta_result.delete("1.0", "end")
        if not datos.get("exito"):
            self._txt_meta_result.insert("1.0",
                f"⚠️ No se pudieron extraer metadatos.\n"
                f"Error: {datos.get('error','desconocido')}\n\n"
                f"Sugerencia: verifica que la URL sea accesible desde tu navegador.")
        else:
            campos = [
                ("Título",        datos.get("titulo","")),
                ("Autor/es",      datos.get("autor","")),
                ("Fecha",         datos.get("fecha","")),
                ("Institución",   datos.get("institucion","")),
                ("Tipo",          datos.get("tipo_documento","")),
                ("ISSN",          datos.get("issn","")),
                ("Idioma",        datos.get("idioma","")),
                ("Editorial",     datos.get("editorial","")),
                ("Lugar",         datos.get("lugar","")),
                ("Derechos",      datos.get("derechos","")),
                ("Descripción",   datos.get("descripcion","")[:300]),
                ("Temas",         ", ".join(datos.get("temas",[])[:8])),
                ("Fuente",        datos.get("fuente","")),
            ]
            lineas = []
            for etiq, val in campos:
                if val: lineas.append(f"  {etiq:<16} {val}")
            self._txt_meta_result.insert("1.0",
                "✅ Metadatos extraídos:\n" + "\n".join(lineas))
            # Pre-rellenar nombre de publicación si está vacío
            if datos.get("titulo") and self._var_pub.get() == "Mi publicación":
                self._var_pub.set(datos["titulo"][:60])
        self._txt_meta_result.config(state="disabled")

    def _poblar_lista(self, carpeta):
        from core.ocr_engine import EXTS_IMAGEN, analizar_pdf
        self._lb.delete(0,"end"); self._archivos_disp = []
        tipo = self._var_tipo.get()

        if tipo == "carpetas":
            # Modo subcarpetas: cada subdirectorio es un número de la publicación.
            # Se registra la subcarpeta como "archivo" — el worker OCR la procesará
            # iterando sus PDFs internamente.
            subcarpetas = sorted(p for p in carpeta.iterdir() if p.is_dir())
            if not subcarpetas:
                self._lbl_arch_info.config(
                    text="⚠️ No se encontraron subcarpetas en esa carpeta")
                return
            self._lbl_arch_info.config(
                text=f"Analizando {len(subcarpetas)} subcarpeta(s)…")
            self.update_idletasks()
            for sc in subcarpetas:
                pdfs = sorted(sc.glob("*.pdf"))
                n_pdfs = len(pdfs)
                mb_total = sum(p.stat().st_size for p in pdfs) / 1024 / 1024
                # Analizar primer PDF para detectar si tiene texto
                if pdfs:
                    info = analizar_pdf(pdfs[0])
                    estado = ("✅ texto" if info["tiene_texto"] else "🔍 OCR")
                    estado += f" · {n_pdfs} PDF(s) · {mb_total:.1f} MB"
                else:
                    estado = f"Sin PDFs ({n_pdfs})"
                self._archivos_disp.append(sc)
                self._lb.insert("end", f"{sc.name:<42}  {estado}")
                self._lb.select_set(self._lb.size()-1)
            self._lbl_arch_info.config(
                text=f"{len(subcarpetas)} número(s) · todos seleccionados")
            ST.input_tipo = "carpetas"
            return

        if tipo == "pdf":
            archivos = sorted(carpeta.glob("*.pdf"))
        else:
            archivos = sorted(p for p in carpeta.iterdir()
                              if p.suffix.lower() in EXTS_IMAGEN)

        if not archivos:
            self._lbl_arch_info.config(text="⚠️ No se encontraron archivos")
            return
        self._lbl_arch_info.config(
            text=f"Analizando {len(archivos)} archivo(s)…")
        self.update_idletasks()
        for p in archivos:
            self._archivos_disp.append(p)
            mb = p.stat().st_size / 1024 / 1024
            if tipo == "pdf":
                info  = analizar_pdf(p)
                estado = (f"✅ texto ({info['palabras_promedio']:.0f} pal/pág)"
                          if info["tiene_texto"]
                          else f"🔍 OCR ({info['palabras_promedio']:.0f} pal/pág)")
            else:
                estado = ""
            self._lb.insert("end", f"{p.name:<42} {mb:5.1f} MB  {estado}")
            self._lb.select_set(self._lb.size()-1)
        self._lbl_arch_info.config(
            text=f"{len(archivos)} archivo(s) · todos seleccionados")

    def _cfg_toggle_ia(self):
        habilitada = self._var_ia_habilitada.get()
        ST.ia_habilitada = habilitada
        if hasattr(self, "_lbl_ia_estado"):
            if habilitada:
                self._lbl_ia_estado.config(
                    text="IA EXTERNA: ACTIVADA", fg=VERDE, bg=CARD_BG)
            else:
                self._lbl_ia_estado.config(
                    text="IA EXTERNA: DESACTIVADA  (modo offline)",
                    fg=ROJO, bg=CARD_BG)
        # Sincronizar topbar
        if hasattr(self, "_lbl_ia_topbar"):
            self._lbl_ia_topbar.config(
                text="● IA ON" if habilitada else "○ IA OFF",
                fg=VERDE if habilitada else ROJO)

    def _confirmar_cfg(self):
        ent = Path(self._var_ent.get().strip())
        sal = Path(self._var_sal.get().strip())
        if not ent.exists():
            messagebox.showerror("Error", f"Carpeta no existe: {ent}"); return
        sel = [self._archivos_disp[i] for i in self._lb.curselection()]
        if not sel:
            messagebox.showwarning("Sin selección","Selecciona al menos un archivo."); return
        if not str(sal).strip():
            messagebox.showerror("Error","Define la carpeta de resultados."); return
        if self._var_tipo.get() == "pdf" and len(sel) > 1:
            from core.ocr_engine import detectar_posibles_duplicados
            try:
                dups = detectar_posibles_duplicados(sel)
            except Exception:
                dups = []
            if dups:
                detalle = "\n".join(
                    f"  • {a.name}  ↔  {b.name}  ({ov:.0%} de solapamiento)"
                    for a, b, ov in dups)
                if not messagebox.askyesno(
                    "Posible contenido duplicado",
                    "Algunos de los PDF seleccionados comparten buena parte "
                    "del vocabulario de sus primeras páginas — podrían ser "
                    "el mismo número exportado dos veces con nombres "
                    "distintos:\n\n" + detalle +
                    "\n\n¿Continuar de todas formas y procesarlos como "
                    "números distintos?"):
                    return
        sal.mkdir(parents=True, exist_ok=True)
        ST.publicacion = self._var_pub.get().strip() or "Publicación"
        ST.periodo     = self._var_per.get().strip()
        ST.pdf_dir     = ent; ST.out_dir = sal
        ST.archivos_sel = sel; ST.input_tipo = self._var_tipo.get()
        # Guardar switch IA
        ST.ia_habilitada = self._var_ia_habilitada.get()
        # Guardar claves por proveedor
        ST.api_keys["anthropic"] = self._var_key_anthropic.get().strip()
        ST.api_keys["openai"]    = self._var_key_openai.get().strip()
        ST.api_keys["gemini"]    = self._var_key_gemini.get().strip()
        ST.api_keys["ollama"]    = self._var_key_ollama.get().strip()
        # api_key legado = primera clave no vacía (prioridad: anthropic → openai → gemini → ollama)
        ST.api_key = next(
            (v for v in (ST.api_keys["anthropic"], ST.api_keys["openai"],
                         ST.api_keys["gemini"]) if v),
            ""
        )
        self._var_api_key.set(ST.api_key)
        # Persistir las claves en la carpeta personal, no en el proyecto: así
        # sobreviven aunque no se guarde proyecto y nunca viajan en el .bashkar.
        try:
            from core.user_prefs import guardar_credenciales, separar_secretos
            secretos, _ = separar_secretos(ST.api_keys)
            guardar_credenciales({
                # Incluye los vacíos para que borrar una clave en la interfaz
                # también la borre del disco.
                p: secretos.get(p, "")
                for p in ("anthropic", "openai", "gemini")
            })
        except Exception:
            pass
        # Guardar modelos por etapa
        for etapa_id, var_e in self._vars_modelo_etapa.items():
            ST.modelos_etapa[etapa_id] = var_e.get()
        ST.max_ia       = self._var_max_ia.get()
        # Parsear campos semánticos
        import json
        try:
            raw = "{" + self._txt_sem.get("1.0","end").strip() + "}"
            ST.campos_semillas = json.loads(raw)
        except Exception:
            ST.campos_semillas = CAMPOS_DEFAULT
        # Guardar configuración lingüística
        if hasattr(self, "_var_lematizar"):
            ST.lematizar = self._var_lematizar.get()
        if hasattr(self, "_txt_stopwords"):
            texto_sw = self._txt_stopwords.get("1.0", "end-1c")
            ST.stopwords_proyecto = [p.strip().lower() for p in texto_sw.splitlines() if p.strip()]
        self._set_pub_hdr(f"{ST.publicacion}  ·  {ST.periodo}")
        self._lbl_cfg_ok.config(text=f"  ✅  {len(sel)} archivo(s) listos")
        self.toast(f"{len(sel)} archivo(s) configurados — continúa con Extracción", tipo="info")
        self._mostrar_pagina("ocr")










    # ══════════════════════════════════════════════════════════════════════════
    # TAB MMX: EXTRACCIÓN MULTIMODAL ESTRUCTURADA (IA de visión → JSON → .md)
    # ══════════════════════════════════════════════════════════════════════════

    # Modelos de visión vigentes por proveedor (jun-2026). El primero es el
    # default. Verificados: Claude vía skill claude-api; Gemini/OpenAI/Ollama vía
    # docs oficiales. El combobox es editable por si el usuario quiere otro.
    _MMX_MODELOS = {
        "gemini": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-3.1-flash",
                   "gemini-3-pro"],
        "claude": ["claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5",
                   "claude-opus-4-7", "claude-fable-5"],
        "openai": ["gpt-5.5", "gpt-5.4-mini", "gpt-4o", "gpt-4o-mini"],
        "ollama": ["qwen3.6", "gemma4", "gemma3:4b", "llava", "llama3.2-vision", "qwen2.5-vl", "minicpm-v"],
        "lmstudio": [],  # sin catálogo fijo: se consulta al servidor local
    }









    # ── Helpers internos del etiquetador ─────────────────────────────────────





















    # ── Helpers de detección de handles ──────────────────────────────────────

    _ETZ_HANDLE_R = 7   # radio de detección de esquinas/bordes (px)
    _ETZ_HANDLE_D = 7   # radio visual de los cuadraditos dibujados (px)





    _ETZ_CURSOR_MAP = {
        "nw": "size_nw_se", "se": "size_nw_se",
        "ne": "size_ne_sw", "sw": "size_ne_sw",
        "n":  "sb_v_double_arrow", "s": "sb_v_double_arrow",
        "e":  "sb_h_double_arrow", "w": "sb_h_double_arrow",
        "move": "fleur",
    }


    # ── Zoom y Pan ───────────────────────────────────────────────────────────








    # ── Interacción principal ─────────────────────────────────────────────────




































    # ── Helpers de normalización ──────────────────────────────────────────────
































    # ── Dictado por voz ───────────────────────────────────────────────────────






    # ── Zoom / pan del canvas de imagen en Normalizar ─────────────────────────










    def _sort_tv_seg(self, col: str):
        """Ordena la tabla de artículos por columna al hacer clic en el encabezado."""
        if ST.df_articulos is None or ST.df_articulos.empty: return
        rev = self._tv_seg_sort_rev.get(col, False)
        self._tv_seg_sort_rev[col] = not rev
        col_map = {"Número":"numero","Título":"titulo","Autor":"autor",
                   "Confianza":"confianza_autor","Sección":"seccion",
                   "Páginas":"pagina","Palabras":"palabras"}
        df_col = col_map.get(col)
        if df_col and df_col in ST.df_articulos.columns:
            df_sorted = ST.df_articulos.sort_values(df_col, ascending=not rev)
            self._tv_seg.delete(*self._tv_seg.get_children())
            for _, row in df_sorted.iterrows():
                self._insertar_fila_seg(row)

    def _insertar_fila_seg(self, row):
        """Inserta una fila en la tabla de artículos con color según confianza."""
        conf = float(row.get("confianza_autor", 0))
        if conf >= 0.65:   tag = "alta"
        elif conf >= 0.30: tag = "media"
        else:              tag = "anonimo"
        titulo_corto = str(row.get("titulo",""))[:80]
        vals = (
            str(row.get("numero",""))[:30],
            titulo_corto,
            str(row.get("autor",""))[:50],
            f"{conf:.2f}",
            str(row.get("seccion",""))[:20],
            str(row.get("pagina",""))[:15],
            str(row.get("palabras",""))
        )
        self._tv_seg.insert("", "end", values=vals, tags=(tag,))

    def _on_seg_select(self, _event=None):
        sel = self._tv_seg.selection()
        if not sel or ST.df_articulos is None: return
        item = self._tv_seg.item(sel[0])
        vals = item["values"]
        if not vals: return
        mask = ((ST.df_articulos["numero"] == str(vals[0])) &
                (ST.df_articulos["titulo"] == str(vals[1])))
        rows = ST.df_articulos[mask]
        texto = rows.iloc[0]["texto"] if not rows.empty else "(no disponible)"
        self._txt_seg_art.config(state="normal")
        self._txt_seg_art.delete("1.0","end")
        self._txt_seg_art.insert("1.0", texto[:3000])
        self._txt_seg_art.config(state="disabled")






    def _explorar_expansion(self):
        if ST.word_model is None:
            messagebox.showinfo("Sin modelo","Ejecuta el análisis textual con Word2Vec activado primero."); return
        campo = self._var_campo_exp.get()
        campos = getattr(ST,"campos_semillas", CAMPOS_DEFAULT)
        semillas = campos.get(campo, [])
        if not semillas:
            messagebox.showinfo("Sin semillas",f"No hay semillas para '{campo}'."); return
        from core.word_vectors import expandir_campo_semantico
        res = expandir_campo_semantico(semillas, ST.word_model, topn=20)
        exp_txt = (f"Semillas encontradas: {res['semillas_encontradas']}\n"
                   f"Expansiones top-15:\n" +
                   "\n".join(f"  {p}  ({s:.3f})" for p,s in res["expansiones"][:15]))
        if self._txt_exp_res is None:
            messagebox.showinfo("Expansión semántica",
                "Abre 'Expansión semántica' en las opciones avanzadas para ver el resultado.\n\n"
                + exp_txt); return
        self._txt_exp_res.config(state="normal")
        self._txt_exp_res.delete("1.0","end")
        self._txt_exp_res.insert("1.0", exp_txt)
        self._txt_exp_res.config(state="disabled")


    # ── Helpers del panel imgdesc ─────────────────────────────────────────────











    def _on_tip_select(self, _event):
        """Muestra detalle de fuentes cuando el usuario hace clic en una fila."""
        sel = self._tv_tip.selection()
        if not sel: return
        vals = self._tv_tip.item(sel[0])["values"]
        if not vals: return
        nombre = str(vals[0])
        tip = ST.datos_visual.get("tipografia", {}).get(nombre, {})
        fuentes = tip.get("fuentes_resumen", [])
        self._txt_tip_det.config(state="normal")
        self._txt_tip_det.delete("1.0", "end")
        if fuentes:
            self._txt_tip_det.insert("end",
                f"{'Fuente':<35} {'Clasificación':<22} {'Cuerpo(pt)':<12} {'Negrita%':<10} {'Cursiva%'}\n")
            self._txt_tip_det.insert("end", "─"*100 + "\n")
            for fd in fuentes[:10]:
                self._txt_tip_det.insert("end",
                    f"{fd['fuente']:<35} {fd.get('clasificacion',''):<22} "
                    f"{fd.get('tam_mediano',0):<12.1f} {fd.get('negrita_pct',0):<10.1f} {fd.get('cursiva_pct',0):.1f}\n")
        else:
            self._txt_tip_det.insert("end", "(sin detalle disponible)")
        self._txt_tip_det.config(state="disabled")

    def _on_diag_num_sel(self, _event):
        """Rellena la lista de páginas cuando el usuario selecciona un número."""
        nombre = self._var_diag_num.get()
        datos = ST.datos_imagenes.get(nombre, {})
        paginas = [p["pagina"] for p in datos.get("paginas", []) if p.get("elementos")]
        self._cmb_diag_pag["values"] = paginas
        if paginas:
            self._cmb_diag_pag.set(paginas[0])
            self._mostrar_diagrama()

    def _on_diag_pag_sel(self, _event):
        self._mostrar_diagrama()

    def _mostrar_diagrama(self):
        """Genera y muestra el diagrama de layout de la página seleccionada."""
        from core.image_analyzer import generar_diagrama_layout
        nombre = self._var_diag_num.get()
        pagina = self._var_diag_pag.get()
        datos  = ST.datos_imagenes.get(nombre, {})
        pag_datos = next((p for p in datos.get("paginas", []) if p["pagina"] == pagina), None)
        if not pag_datos:
            return
        png_bytes = generar_diagrama_layout(pag_datos, titulo=f"{nombre}")
        self._pegar_imagen_canvas(self._canvas_diag, png_bytes)

    def _pegar_imagen_canvas(self, canvas, png_bytes: bytes):
        """Pega bytes PNG en un canvas Tkinter."""
        import io

        from PIL import Image, ImageTk
        img = Image.open(io.BytesIO(png_bytes))
        cw  = canvas.winfo_width()  or 500
        ch  = canvas.winfo_height() or 600
        img.thumbnail((cw, ch), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(img)
        canvas.delete("all")
        canvas.create_image(cw//2, ch//2, anchor="center", image=tk_img)
        self._diag_img_ref = tk_img   # evitar GC

    def _exportar_csv_imagenes(self):
        """Exporta la tabla de imágenes detectadas a CSV."""
        import csv
        if not ST.datos_imagenes:
            messagebox.showwarning("Sin datos", "Ejecuta el análisis visual primero."); return
        dest = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV","*.csv")],
            initialfile="imagenes_detectadas.csv")
        if not dest: return
        cols = ["numero","pagina","tipo","confianza","w_cm","h_cm","area_cm2",
                "pos_x_pct","pos_y_pct","autor_imagen","pie_de_foto","descripcion_ia"]
        with open(dest, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for nombre, datos in ST.datos_imagenes.items():
                for pag in datos.get("paginas", []):
                    for el in pag.get("elementos", []):
                        if el["tipo"] == "Texto": continue
                        row = {k: el.get(k,"") for k in cols}
                        row["numero"] = nombre
                        row["pagina"] = pag["pagina"]
                        w.writerow(row)
        self.toast(f"Exportado → {Path(dest).name}", tipo="ok")

    def _exportar_imagenes_carpeta(self):
        """Recorta y guarda cada imagen detectada en una carpeta organizada."""
        if not ST.datos_imagenes:
            messagebox.showwarning("Sin datos", "Ejecuta el análisis visual primero."); return

        destino = filedialog.askdirectory(title="Carpeta de destino para las imágenes")
        if not destino: return
        destino = Path(destino) / "imagenes_extraidas"

        # Diálogo de progreso
        prog_win = tk.Toplevel(self)
        prog_win.title("Exportando imágenes…")
        prog_win.geometry("420x140")
        prog_win.resizable(False, False)
        prog_win.grab_set()
        tk.Label(prog_win, text="Exportando imágenes recortadas",
                 font=("Segoe UI", 10, "bold")).pack(pady=(16, 4))
        lbl_prog = tk.Label(prog_win, text="Preparando…", font=("Segoe UI", 9))
        lbl_prog.pack()
        bar = ttk.Progressbar(prog_win, mode="determinate", length=380)
        bar.pack(pady=8)

        def worker():
            from core.image_exporter import exportar_imagenes
            img_dir_raiz = ST.out_dir / "imgs" if hasattr(ST, "out_dir") else Path("imgs")

            def cb(n, total, desc):
                pct = int(n / max(total, 1) * 100)
                self.after(0, lambda: bar.config(value=pct))
                self.after(0, lambda d=desc: lbl_prog.config(text=d))

            try:
                stats = exportar_imagenes(
                    datos_imagenes=ST.datos_imagenes,
                    img_dir_raiz=img_dir_raiz,
                    destino=destino,
                    publicacion=getattr(ST, "publicacion", "Publicacion"),
                    callback=cb,
                )
                self.after(0, prog_win.destroy)
                msg = (f"✅ {stats['exportadas']} imágenes exportadas\n"
                       f"   Omitidas (demasiado pequeñas): {stats['omitidas']}\n"
                       f"   Errores: {stats['errores']}\n\n"
                       f"   Carpeta:\n   {destino}")
                self.after(0, lambda: messagebox.showinfo("Exportación completada", msg))
            except Exception as e:
                self.after(0, prog_win.destroy)
                self.after(0, lambda err=str(e): messagebox.showerror("Error", err))

        threading.Thread(target=worker, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 7: METADATOS URL
    # ══════════════════════════════════════════════════════════════════════════
    def _build_meta(self):
        f = self._tab_meta
        self._page_header(f, "Metadatos desde URL",
                          "Extrae título, autor, fecha y datos del archivo digital", "🔗")
        self._build_ai_panel(f, "meta")
        pad = tk.Frame(f, bg=CONTENT_BG); pad.pack(fill="both", expand=True, padx=24, pady=16)

        # Tarjeta de entrada
        url_card = tk.Frame(pad, bg=CARD_BG, relief="solid", bd=1,
                             highlightbackground=CARD_BOR)
        url_card.pack(fill="x", pady=(0,12))
        url_inner = tk.Frame(url_card, bg=CARD_BG, padx=16, pady=14)
        url_inner.pack(fill="x")
        url_inner.columnconfigure(1, weight=1)

        tk.Label(url_inner, text="URL del catálogo:", bg=CARD_BG, fg="#E8E5DF",
                 font=("Segoe UI",9,"bold")).grid(row=0,column=0,sticky="w",pady=4)
        self._var_meta_url = tk.StringVar()
        url_row = tk.Frame(url_inner, bg=CARD_BG)
        url_row.grid(row=0, column=1, columnspan=2, sticky="ew", padx=8)
        tk.Entry(url_row, textvariable=self._var_meta_url, width=60,
                 font=("Segoe UI",9), relief="solid", bd=1, bg="#171C20").pack(
                 side="left", fill="x", expand=True)
        ttk.Button(url_row, text="Extraer metadatos →", style="P.TButton",
                   command=self._extraer_meta).pack(side="left", padx=(8,0))
        ttk.Button(url_row, text="Ejemplos", style="S.TButton",
                   command=self._ejemplos_url).pack(side="left", padx=(4,0))

        tk.Label(url_inner,
                 text="Compatible con BNCO · Archive.org · Europeana · BNE · HathiTrust",
                 bg=CARD_BG, fg="#646D72", font=("Segoe UI",8)).grid(
                 row=1, column=0, columnspan=3, sticky="w", pady=(0,4))

        # Resultado
        res_f = tk.Frame(pad, bg=CARD_BG, relief="solid", bd=1)
        res_f.pack(fill="both", expand=True)
        res_hdr = tk.Frame(res_f, bg="#171C20"); res_hdr.pack(fill="x")
        tk.Label(res_hdr, text="  📋  Metadatos extraídos",
                 bg="#171C20", fg=TXT_PRI, font=("Segoe UI",8,"bold")).pack(
                 side="left", pady=4)
        self._txt_meta = scrolledtext.ScrolledText(res_f, height=22, font=("Consolas",10),
                                                    bg="#171C20", fg="#E8E5DF",
                                                    relief="flat", state="disabled")
        self._txt_meta.pack(fill="both", expand=True, padx=1, pady=(0,1))

        # Botones de acción
        act_f = tk.Frame(pad, bg=CONTENT_BG); act_f.pack(fill="x", pady=(8,0))
        ttk.Button(act_f, text="📥 Guardar JSON", style="S.TButton",
                   command=self._guardar_meta_json).pack(side="left", padx=(0,8))
        ttk.Button(act_f, text="📄 Añadir a Excel", style="S.TButton",
                   command=self._meta_a_excel).pack(side="left")
        self._lbl_meta_ok = tk.Label(act_f, text="", bg=CONTENT_BG, fg=VERDE,
                                      font=("Segoe UI",9,"bold"))
        self._lbl_meta_ok.pack(side="left", padx=12)
        self._meta_actual = {}

    def _extraer_meta(self):
        url = self._var_meta_url.get().strip()
        if not url:
            messagebox.showwarning("URL vacía", "Escribe o pega la URL primero."); return
        self._txt_meta.config(state="normal")
        self._txt_meta.delete("1.0", "end")
        self._txt_meta.insert("end", "⏳ Consultando biblioteca digital…\n")
        self._txt_meta.insert("end", "🌐 Buscando metadatos adicionales en la web…\n")
        self._txt_meta.config(state="disabled")
        self._lbl_meta_ok.config(text="")
        def worker():
            from core.metadata_extractor import (
                enriquecer_con_busqueda_web,
                extraer_metadata_url,
                formatear_metadatos,
            )
            try:
                meta = extraer_metadata_url(url)
                # Enriquecer con búsqueda web si faltan campos
                campos_vacios = [k for k in ("titulo","creador","fecha","descripcion")
                                 if not meta.get(k)]
                if campos_vacios:
                    meta = enriquecer_con_busqueda_web(meta, url)
                texto = formatear_metadatos(meta)
                self._meta_actual = meta
                self.after(0, lambda t=texto, m=meta: self._mostrar_meta(t, m))
            except Exception as e:
                self.after(0, lambda err=str(e): self._mostrar_meta(f"⚠️ Error: {err}", {}))
        threading.Thread(target=worker, daemon=True).start()

    def _mostrar_meta(self, texto: str, meta: dict):
        self._txt_meta.config(state="normal")
        self._txt_meta.delete("1.0", "end")
        self._txt_meta.insert("end", texto)
        self._txt_meta.config(state="disabled")
        fuente = meta.get("fuente_metadata", "—")
        if meta.get("titulo"):
            self._lbl_meta_ok.config(
                text=f"✅ Metadatos obtenidos · Fuente: {fuente}")
        else:
            self._lbl_meta_ok.config(text="⚠️ Sin metadatos encontrados")

    def _ejemplos_url(self):
        ejemplos = (
            "URLs de ejemplo para probar:\n\n"
            "• Biblioteca Nacional de Colombia (BNCO / SirsiDynix):\n"
            "  https://bnco.ent.sirsi.net/custom/web/content/conservacion/"
            "html/visorFicheros.html?idFichero=190988\n\n"
            "• Archive.org:\n"
            "  https://archive.org/details/estampa_colombia_1939\n\n"
            "• Europeana:\n"
            "  https://www.europeana.eu/item/9200579/BibliographicResource_3000126484305\n\n"
            "• Biblioteca Nacional de España (BNE):\n"
            "  https://hemerotecadigital.bne.es/hd/es/viewer?id=...\n\n"
            "El sistema intentará OAI-PMH, JSON-LD, meta etiquetas y scraping "
            "específico en ese orden."
        )
        messagebox.showinfo("URLs de ejemplo", ejemplos)

    def _guardar_meta_json(self):
        if not self._meta_actual:
            messagebox.showwarning("Sin datos", "Extrae metadatos primero."); return
        import json
        dest = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON","*.json")],
            initialfile="metadatos.json")
        if not dest: return
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(self._meta_actual, f, ensure_ascii=False, indent=2)
        self._lbl_meta_ok.config(text=f"✅ Guardado: {Path(dest).name}")

    def _meta_a_excel(self):
        messagebox.showinfo("Próximamente",
                            "Esta función añadirá los metadatos como hoja adicional "
                            "al Excel en la próxima ejecución de exportación.")






    # ══════════════════════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════════════════════
    def _mk_ind(self, parent, label, val, col):
        bg   = CARD_BG
        box  = tk.Frame(parent, bg=bg, width=138, height=70,
                        relief="solid", bd=1, highlightbackground=CARD_BOR)
        box.grid(row=0, column=col, padx=5)
        box.grid_propagate(False)
        # accent bar on top
        tk.Frame(box, bg=AZ3, height=3).pack(fill="x")
        lv = tk.Label(box, text=val, bg=bg, fg=TXT_PRI,
                      font=("Segoe UI",18,"bold"))
        lv.pack(expand=True)
        tk.Label(box, text=label, bg=bg, fg="#777F84",
                 font=("Segoe UI",8)).pack(pady=(0,6))
        return lv

    def _log(self, msg, color="#6CA8E8"):
        cur    = getattr(self, "_current_page", "ocr")
        target = self._log_a if cur == "anal" else self._log_w
        target.config(state="normal")
        target.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        target.see("end"); target.config(state="disabled")
        self._lbl_status.config(text=f"  {msg[:90]}")
    def _log_a_write(self, msg):
        self._log_a.config(state="normal")
        self._log_a.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self._log_a.see("end"); self._log_a.config(state="disabled")
        self._lbl_status.config(text=f"  {msg[:90]}")

    def _set_prog(self, v, txt=""):
        self._prog["value"] = v; self._lbl_pct.config(text=f"{v}%  {txt}")
    def _set_prog_a(self, v, txt=""):
        self._prog_a["value"] = v; self._lbl_pct_a.config(text=f"{v}%  {txt}")
        self._lbl_fase_a.config(text=txt)

    # ══════════════════════════════════════════════════════════════════════════
    # WORKERS — OCR
    # ══════════════════════════════════════════════════════════════════════════
    def _gutter_completar_corpus(self):
        """Detecta y reconstruye palabras cortadas por costura en todos los .txt."""
        if not getattr(ST, "out_dir", None):
            messagebox.showwarning("Sin carpeta",
                "Confirma la configuración y ejecuta la extracción primero."); return
        api_key, _ = _resolver_api_key_modelo("ocr_mejora")
        if not api_key:
            messagebox.showwarning("Sin IA",
                "Activa la IA y configura una API key para usar esta función.\n"
                "La reconstrucción de palabras requiere un modelo de lenguaje."); return

        ocr_dir = ST.out_dir / "03_ocr"
        if ocr_dir.exists():
            txt_dirs = [d for d in ocr_dir.iterdir() if d.is_dir()]
        else:
            txt_dirs = list({f.parent for f in ST.out_dir.rglob("*.txt") if f.is_file()})

        if not txt_dirs:
            messagebox.showinfo("Sin archivos",
                "No se encontraron archivos de texto OCR."); return

        total = sum(len(list(d.glob("*.txt"))) for d in txt_dirs)
        if not messagebox.askyesno("Completar costura",
            f"Se analizarán {total} páginas en busca de palabras cortadas por costura.\n\n"
            "Las palabras reconstruidas se marcarán con ⟦palabra⟧ en el texto\n"
            "y aparecerán en rojo en las exportaciones DOCX.\n\n"
            "¿Continuar?"): return

        self._put(tipo="fase", txt="Completando palabras cortadas por costura…")
        threading.Thread(target=self._worker_gutter, args=(txt_dirs, api_key),
                         daemon=True).start()

    def _worker_gutter(self, txt_dirs, api_key):
        from core.gutter_completion import estadisticas, reconstruir_texto
        modelo = "claude-haiku-4-5-20251001"
        total_fragmentos = 0
        total_reconstruidos = 0

        for txt_dir in txt_dirs:
            for txt_path in sorted(txt_dir.glob("*.txt")):
                try:
                    texto = txt_path.read_text("utf-8", errors="replace")
                    texto_rec, frags = reconstruir_texto(texto, api_key, modelo)
                    stats = estadisticas(frags)
                    if stats["reconstruidos"] > 0:
                        # Guardar backup
                        backup = txt_path.with_suffix(".txt.orig")
                        if not backup.exists():
                            backup.write_text(texto, encoding="utf-8")
                        txt_path.write_text(texto_rec, encoding="utf-8")
                        total_fragmentos   += stats["total_fragmentos"]
                        total_reconstruidos += stats["reconstruidos"]
                        self._put(tipo="log",
                                  texto=f"  {txt_path.stem}: "
                                        f"{stats['reconstruidos']}/{stats['total_fragmentos']} "
                                        f"palabras reconstruidas")
                except Exception as e:
                    self._put(tipo="log",
                              texto=f"  ⚠ Error en {txt_path.stem}: {e}")

        self._put(tipo="fase", txt="")
        self.after(0, lambda: messagebox.showinfo(
            "Costura completada",
            f"Análisis completado.\n\n"
            f"Fragmentos detectados: {total_fragmentos}\n"
            f"Palabras reconstruidas: {total_reconstruidos}\n\n"
            f"Los archivos originales se guardaron con extensión .txt.orig\n"
            f"Las palabras generadas están marcadas con ⟦⟧"))

    def _renormalizar_textos(self):
        """Re-aplica la normalización OCR a todos los .txt ya extraídos."""
        if not getattr(ST, "out_dir", None):
            messagebox.showwarning("Sin carpeta",
                "Confirma la configuración y ejecuta la extracción primero."); return

        # Buscar en 03_ocr/ (estructura estándar) o cualquier subcarpeta con .txt
        ocr_dir = ST.out_dir / "03_ocr"
        if ocr_dir.exists():
            txt_dirs = [d for d in ocr_dir.iterdir() if d.is_dir()]
        else:
            txt_dirs = [d for d in ST.out_dir.rglob("*.txt")
                        if d.is_file()]
            # Convertir a carpetas únicas
            txt_dirs = list({f.parent for f in txt_dirs})

        if not txt_dirs:
            messagebox.showinfo("Sin archivos",
                "No se encontraron archivos de texto.\n"
                "Extrae el OCR primero en la pestaña OCR."); return

        total_txt = sum(len(list(d.glob("*.txt"))) for d in txt_dirs)
        msg_norm = (f"Se normalizarán {total_txt} archivos .txt en "
                    f"{len(txt_dirs)} carpeta(s).\n\n"
                    "Se guardará copia del original como .txt.orig\n"
                    "¿Continuar?")
        if not messagebox.askyesno("Re-normalizar", msg_norm): return

        prog_win = tk.Toplevel(self)
        prog_win.title("Normalizando textos OCR…")
        prog_win.geometry("420x130")
        prog_win.resizable(False, False)
        prog_win.grab_set()
        tk.Label(prog_win, text="Normalizando textos OCR",
                 font=("Segoe UI", 10, "bold")).pack(pady=(14, 4))
        lbl_p = tk.Label(prog_win, text="Preparando…", font=("Segoe UI", 9))
        lbl_p.pack()
        bar = ttk.Progressbar(prog_win, mode="determinate", length=380)
        bar.pack(pady=8)

        def worker():
            total_archivos = 0
            total_cambios  = 0
            all_txts = []
            for d in txt_dirs:
                all_txts.extend(sorted(d.glob("*.txt")))

            for i, txt_path in enumerate(all_txts, 1):
                pct = int(i / max(len(all_txts), 1) * 100)
                self.after(0, lambda p=pct: bar.config(value=p))
                self.after(0, lambda n=txt_path.name: lbl_p.config(text=n))
                try:
                    from core.ocr_normalizer import normalizar_archivo
                    stats = normalizar_archivo(txt_path, guardar_original=True)
                    total_archivos += 1
                    total_cambios  += stats["chars_cambiados"]
                except Exception:
                    pass

            self.after(0, prog_win.destroy)
            msg_done = (f"Archivos normalizados: {total_archivos}\n"
                        f"Caracteres corregidos: ~{total_cambios:,}\n\n"
                        "Los originales se conservan como .txt.orig")
            self.after(0, lambda m=msg_done: messagebox.showinfo(
                "Normalización completada", m))

        threading.Thread(target=worker, daemon=True).start()




    # ── Ollama handlers ───────────────────────────────────────────────────────
    # Velocidad de referencia en segundos por página (1 worker).
    # Se actualiza con _ocr_calibrar_kraken().
    _KRAKEN_SEG_PAG = 60.0







    # Variables de la UI que lee el worker de OCR. Se congelan ANTES de lanzar
    # el hilo: Tcl no es thread-safe y leerlas desde el worker serializa la
    # llamada contra el bucle de eventos (con riesgo de bloqueo mutuo).
    _VARS_OCR = (
        "_var_dpi", "_var_lang", "_var_ruta_ocr", "_var_ocr_usar_etiquetas",
        "_var_ocr_det_auto", "_var_ocr_prov", "_var_ocr_modelo",
        "_var_pre_deskew", "_var_pre_enhance", "_var_pre_despeckle",
        "_var_kraken_modelo", "_var_kraken_workers", "_var_kraken_timeout",
        "_var_ollama_modelo",
        # Ruta 2 (IA de visión): no llevan prefijo _var_ pero son StringVar igual.
        "_ocr_vision_prov", "_ocr_vision_model",
    )

    def _snapshot_ocr(self) -> dict:
        """Lee en el hilo principal las variables Tk que necesita el worker OCR."""
        snap = {}
        for nombre in self._VARS_OCR:
            var = getattr(self, nombre, None)
            if var is not None and hasattr(var, "get"):
                snap[nombre] = _VarCongelada(var.get())
        return snap





    # ══════════════════════════════════════════════════════════════════════════
    # WORKERS — SEGMENTACIÓN
    # ══════════════════════════════════════════════════════════════════════════
    def _reconstruir_corpus_meta_desde_txt(self) -> bool:
        """Construye ST.corpus_meta leyendo los TXT de 03_ocr/ cuando no hay OCR previo.
        Retorna True si encontró archivos, False si no hay nada."""
        from core.servicios_corpus import reconstruir_meta_corpus
        df = reconstruir_meta_corpus(ST.out_dir)
        if df is None:
            return False
        ST.corpus_meta = df
        ST.ocr_done    = True
        ST.marcar_etapa("ocr", "ready")
        return True







    def _actualizar_combos_diag(self, numeros: list):
        self._cmb_diag["values"] = numeros
        if numeros:
            self._cmb_diag.set(numeros[0])
            self._on_diag_num_sel(None)



    # ══════════════════════════════════════════════════════════════════════════
    # RESULTADOS Y EXPORTACIÓN
    # ══════════════════════════════════════════════════════════════════════════
    def _cargar_resultados(self):
        if not ST.anal_done:
            # Mostrar estado pendiente en los indicadores
            for attr in ("_lbl_r_num","_lbl_r_pag","_lbl_r_pal",
                         "_lbl_r_art","_lbl_r_aut","_lbl_r_fir"):
                if hasattr(self, attr):
                    getattr(self, attr).config(text="—")
            return
        from core.excel_export import generar_figuras_completas

        # Un proyecto guardado antes de que corpus_meta se persistiera vuelve
        # con anal_done=True pero sin corpus_meta: esto reventaba con
        # TypeError ('NoneType' no es suscriptable) al abrir Resultados.
        meta=ST.corpus_meta
        if meta is None or not hasattr(meta, "columns"):
            for attr in ("_lbl_r_num","_lbl_r_pag","_lbl_r_pal"):
                if hasattr(self, attr):
                    getattr(self, attr).config(text="—")
        else:
            self._lbl_r_num.config(text=str(meta["numero"].nunique()))
            self._lbl_r_pag.config(text=f"{len(meta):,}")
            self._lbl_r_pal.config(text=f"{int(meta['palabras'].sum()):,}")
        n_art=len(ST.df_articulos) if ST.df_articulos is not None else 0
        n_aut=(ST.df_articulos[ST.df_articulos["autor"]!="Anónimo / Sin atribuir"]["autor"].nunique()
               if ST.df_articulos is not None and not ST.df_articulos.empty else 0)
        n_fir=ST.df_firmas["firma"].nunique() if ST.df_firmas is not None and not ST.df_firmas.empty else 0
        self._lbl_r_art.config(text=str(n_art))
        self._lbl_r_aut.config(text=str(n_aut))
        self._lbl_r_fir.config(text=str(n_fir))

        def gen():
            datos={
                "df_secciones":ST.df_secciones,"df_firmas":ST.df_firmas,"df_campos":ST.df_campos,
                "df_temas":ST.df_temas,"df_doc_temas":ST.df_doc_temas,"df_layout":ST.df_layout,
                "graph_path":ST.graph_path,"colaboradores":set(),
                "df_articulos":ST.df_articulos,
                "datos_visual":ST.datos_visual,
                "datos_comparativo":ST.datos_comparativo,
            }
            figs = generar_figuras_completas(datos)
            ST.figuras=figs; self.after(0, self._pintar_graficas)
        threading.Thread(target=gen, daemon=True).start()

    def _pintar_graficas(self):
        import io

        from PIL import Image as PILImage
        from PIL import ImageTk
        for key, tab in self._figs_tabs.items():
            if key not in ST.figuras: continue
            for w in tab.winfo_children(): w.destroy()
            buf = io.BytesIO(ST.figuras[key])
            img = PILImage.open(buf); img.thumbnail((940,500),PILImage.LANCZOS)
            tk_img=ImageTk.PhotoImage(img)
            lbl=tk.Label(tab,image=tk_img,bg=CONTENT_BG); lbl.image=tk_img; lbl.pack(expand=True)

    def _gen_excel(self):
        if not ST.anal_done:
            messagebox.showwarning("Sin datos","Completa el análisis textual primero."); return
        if not ST.figuras:
            messagebox.showwarning("Gráficas pendientes","Espera a que se generen las gráficas."); return
        pub_safe = re.sub(r"[^\w]","_",ST.publicacion)
        out_path = ST.out_dir/f"{pub_safe}_Analisis_Editorial.xlsx"
        try:
            from core.excel_export import construir_excel_completo
            datos={"corpus_meta":ST.corpus_meta,"df_firmas":ST.df_firmas,"df_secciones":ST.df_secciones,
                   "df_campos":ST.df_campos,"df_layout":ST.df_layout,"df_temas":ST.df_temas,
                   "df_doc_temas":ST.df_doc_temas,"graph_path":ST.graph_path,
                   "df_articulos":ST.df_articulos,"datos_visual":ST.datos_visual,
                   "datos_comparativo":ST.datos_comparativo}
            construir_excel_completo(datos, ST.figuras, out_path)
            ST.xlsx_path=out_path
            self._lbl_excel.config(text=f"✅ {out_path.name} ({out_path.stat().st_size/1024:.0f} KB)")
            if messagebox.askyesno("Excel generado",f"✅ Guardado:\n{out_path}\n\n¿Abrir carpeta?"):
                self._abrir_carpeta()
        except Exception as e:
            messagebox.showerror("Error",f"No se pudo generar el Excel:\n{e}"); raise

    def _guardar_graphml(self):
        if not ST.graph_path or not ST.graph_path.exists():
            messagebox.showwarning("Sin red","La red no fue generada."); return
        dest=filedialog.asksaveasfilename(defaultextension=".graphml",
             filetypes=[("GraphML","*.graphml")], initialfile="red_autoria.graphml")
        if dest:
            import shutil; shutil.copy2(str(ST.graph_path),dest)
            self.toast(f"Red guardada → {Path(dest).name}", tipo="ok")

    def _abrir_carpeta(self):
        if not ST.out_dir: return
        plataforma.abrir_en_sistema(ST.out_dir)

    # ══════════════════════════════════════════════════════════════════════════
    # DISPATCHER
    # ══════════════════════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════════════════════
    # OCR LLM — mejora páginas de baja confianza con Claude
    # ══════════════════════════════════════════════════════════════════════════
    def _start_mejorar_ocr(self):
        if not ST.ocr_done or ST.corpus_meta is None:
            messagebox.showwarning("OCR pendiente",
                "Ejecuta la extraccion OCR primero."); return
        if not ST.api_key:
            messagebox.showwarning("Sin API key",
                "Configura la API key en Configuracion."); return
        umbral_val = getattr(self, "_var_ocr_umbral", None)
        umbral_val = umbral_val.get() if umbral_val else 60
        proveedor = getattr(self, "_var_ocr_llm_prov", None)
        proveedor = proveedor.get() if proveedor else "claude"
        ollama_modelo = getattr(self, "_var_ocr_ollama_modelo", None)
        ollama_modelo = ollama_modelo.get() if ollama_modelo else "latamgpt"
        if ST.corpus_meta is None:
            self._reconstruir_corpus_meta_desde_txt()
        if ST.corpus_meta is None:
            messagebox.showwarning("Sin datos", "No hay texto extraído aún."); return
        candidatas = ST.corpus_meta[
            ST.corpus_meta["confianza"].notna() &
            (ST.corpus_meta["confianza"] < umbral_val)
        ]
        n = len(candidatas)
        if n == 0:
            messagebox.showinfo("Sin candidatas",
                f"No hay paginas con confianza < {umbral_val}."); return
        # Estándar de costo IA: estimar volumen→tokens→USD y pedir confirmación
        # antes de gastar. Las páginas con conf < 30 van por visión (más caras,
        # tokens de imagen); el resto por corrección de texto. El modelo de
        # referencia es el de visión/ texto por defecto de cada proveedor.
        try:
            from core.costos import estimar_lote_ocr

            n_vision = int((candidatas["confianza"] < 30).sum())
            modelo_ref = {
                "claude": "claude-sonnet-4-6",
                "openai": "gpt-4o",
            }.get(proveedor, ollama_modelo)
            est = estimar_lote_ocr(n, proveedor, modelo_ref, n_vision=n_vision)
            costo_txt = est.resumen() + "\n\n"
        except Exception:
            # Si la estimación falla por cualquier causa, no bloquear: avisar sin cifra.
            costo_txt = (f"{n} página(s); proveedor {proveedor}. "
                         "(No se pudo estimar el costo con precisión.)\n\n")
        if not messagebox.askyesno("Mejorar OCR con IA",
                f"{costo_txt}"
                "El LLM corregira errores de digitalizacion.\n"
                "Continuamos?"):
            return
        self._btn_ocr.config(state="disabled")
        threading.Thread(target=self._worker_mejorar_ocr,
                         args=(umbral_val, proveedor, ollama_modelo), daemon=True).start()

    def _worker_mejorar_ocr(self, umbral: float, proveedor: str = "claude",
                             ollama_modelo: str = "latamgpt"):
        from core.ocr_llm import mejorar_lote
        img_dir_raiz = ST.out_dir / "02_imagenes" if ST.out_dir else None
        modelo_txt = f" [{ollama_modelo}]" if proveedor in ("ollama", "lmstudio") else ""
        self._put(tipo="log", texto=f"Iniciando mejora OCR con {proveedor}{modelo_txt}...")
        # Para proveedores locales la api_key es la URL del servidor; para otros
        # es la clave real.
        if proveedor == "ollama":
            api_key = ST.api_keys.get("ollama", "http://localhost:11434")
        elif proveedor == "lmstudio":
            api_key = ST.api_keys.get("lmstudio", "http://localhost:1234")
        else:
            api_key = ST.api_key

        def cb(n_actual, n_total, desc):
            self._put(tipo="prog", val=int(n_actual / max(n_total, 1) * 100),
                      txt=f"{n_actual}/{n_total}")
            self._put(tipo="log", texto=f"  [{n_actual}/{n_total}] {desc}")

        try:
            stats = mejorar_lote(
                corpus_meta=ST.corpus_meta,
                api_key=api_key,
                umbral_confianza=umbral,
                img_dir_raiz=img_dir_raiz,
                modo="auto",
                proveedor=proveedor,
                modelo_ollama=ollama_modelo,
                callback=cb,
            )
            msg = (
                f"Mejora completada\n"
                f"  Mejoradas:  {stats['mejoradas']}\n"
                f"  Omitidas:   {stats['omitidas']}\n"
                f"  Errores:    {stats['errores']}\n"
                f"  Candidatas: {stats['total_candidatas']}"
            )
            if "costo_real_usd" in stats:
                msg += (
                    f"\n\n💲 Costo real: ${stats['costo_real_usd']:.4f} USD"
                    f"  ({stats.get('tokens_reales', 0):,} tokens)"
                )
            self._put(tipo="log", texto=msg)
            self.after(0, lambda m=msg: messagebox.showinfo("Mejora completada", m))
        except Exception as e:
            err = str(e)
            self._put(tipo="log", texto=f"Error: {err}")
            self.after(0, lambda e=err: messagebox.showerror("Error", e))
        finally:
            self.after(0, lambda: self._btn_ocr.config(state="normal"))

    def _on_ok(self, res):
        self._actualizar_badges()
        if res == "ocr":
            self._btn_ocr.config(state="normal")
            self.toast("OCR completado — revisa y normaliza el texto", tipo="ok")
            self._etz_refrescar_numeros()
            self.after(200, self._norm_refrescar_numeros)
        elif res == "seg":
            self._skeleton_hide(getattr(self, "_seg_skeleton", None))
            self._seg_skeleton = None
            self._btn_seg.config(state="normal")
            n=len(ST.df_articulos) if ST.df_articulos is not None else 0
            self._lbl_seg_n.config(text=f"✅ {n} artículos detectados")
            self._tv_seg.delete(*self._tv_seg.get_children())
            if ST.df_articulos is not None and not ST.df_articulos.empty:
                for _, row in ST.df_articulos.head(600).iterrows():
                    self._insertar_fila_seg(row)
            self.toast(f"Segmentación completada — {n} artículos detectados", tipo="ok")
        elif res == "anal":
            self._btn_anal.config(state="normal")
            self.toast("Análisis completado — pasando a Resultados", tipo="ok")
            self._mostrar_pagina("res"); self._cargar_resultados()

    # ══════════════════════════════════════════════════════════════════════════
    # PANEL LATERAL DE PARÁMETROS — generado dinámicamente desde PARAMS_SCHEMA
    # ══════════════════════════════════════════════════════════════════════════

    def _build_params_panel(self, parent, schema: dict, storage: dict) -> tk.Frame:
        """
        Construye un panel lateral de parámetros a partir de un PARAMS_SCHEMA.

        Args:
            parent:  Frame contenedor (normalmente el lado derecho de un split).
            schema:  dict PARAMS_SCHEMA del módulo core.
            storage: dict mutable donde se guardan las tkVar de cada parámetro.
                     Las claves son los nombres del schema; los valores son tkVar.

        Returns:
            El Frame construido (ya empaquetado en parent).
        """
        panel = tk.Frame(parent, bg=CARD_BG, relief="solid", bd=1, width=220)
        panel.pack(side="right", fill="y", padx=(8, 0))
        panel.pack_propagate(False)

        tk.Label(panel, text="⚙ Parámetros", bg=CARD_BG, fg=TXT_PRI,
                 font=("Segoe UI", 9, "bold")).pack(pady=(10, 6), padx=10, anchor="w")

        # Canvas + scrollbar para muchos parámetros
        cv = tk.Canvas(panel, bg=CARD_BG, highlightthickness=0)
        sb = ttk.Scrollbar(panel, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        cv.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(cv, bg=CARD_BG)
        win_id = cv.create_window((0, 0), window=inner, anchor="nw")

        def _on_resize(e):
            cv.itemconfig(win_id, width=e.width)
        cv.bind("<Configure>", _on_resize)
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))

        # Scroll con rueda del mouse — propagar a todos los hijos
        def _wheel(e):
            cv.yview_scroll(-1 if (e.delta > 0 or e.num == 4) else 1, "units")

        def _bind_wheel(w):
            w.bind("<MouseWheel>", _wheel)
            w.bind("<Button-4>",   _wheel)
            w.bind("<Button-5>",   _wheel)
            for child in w.winfo_children():
                _bind_wheel(child)

        cv.bind("<MouseWheel>", _wheel)
        cv.bind("<Button-4>",   _wheel)
        cv.bind("<Button-5>",   _wheel)
        inner.bind("<MouseWheel>", _wheel)
        # Diferir el bind a hijos porque aún no existen
        panel.after(300, lambda: _bind_wheel(inner))

        for key, spec in schema.items():
            tipo  = spec.get("type", "str")
            label = spec.get("label", key)
            help_ = spec.get("help", "")
            default = spec.get("default")

            grp = tk.Frame(inner, bg=CARD_BG)
            grp.pack(fill="x", padx=10, pady=(0, 10))

            lbl = tk.Label(grp, text=label, bg=CARD_BG, fg=TXT_PRI,
                           font=("Segoe UI", 8, "bold"), anchor="w")
            lbl.pack(fill="x")
            if help_:
                tk.Label(grp, text=help_, bg=CARD_BG, fg=TXT_DIM,
                         font=("Segoe UI", 7), wraplength=180, anchor="w",
                         justify="left").pack(fill="x")

            if tipo == "bool":
                var = tk.BooleanVar(value=bool(default))
                ttk.Checkbutton(grp, variable=var).pack(anchor="w")
                storage[key] = var

            elif tipo == "choice":
                var = tk.StringVar(value=str(default))
                cb = ttk.Combobox(grp, textvariable=var,
                                   values=spec.get("options", []),
                                   state="readonly", width=18)
                cb.pack(fill="x")
                storage[key] = var

            elif tipo == "multicheck":
                var = {}
                defaults_set = set(default or [])
                for opt in spec.get("options", []):
                    bv = tk.BooleanVar(value=(opt in defaults_set))
                    ttk.Checkbutton(grp, text=opt, variable=bv).pack(anchor="w")
                    var[opt] = bv
                storage[key] = var

            elif tipo in ("int", "float"):
                var = tk.DoubleVar(value=float(default or 0))
                mn  = spec.get("min", 0)
                mx  = spec.get("max", 100)
                step = spec.get("step", 1)
                sl = ttk.Scale(grp, from_=mn, to=mx, variable=var, orient="horizontal")
                sl.pack(fill="x")
                lbl_val = tk.Label(grp, bg=CARD_BG, fg=TXT_SEC,
                                   font=("Segoe UI", 8))
                lbl_val.pack(anchor="e")
                def _update_lbl(v, lv=lbl_val, tp=tipo, st=step):
                    val = float(v)
                    lv.config(text=f"{int(val)}" if tp == "int" else f"{val:.2f}")
                sl.config(command=_update_lbl)
                _update_lbl(var.get())
                storage[key] = var

            else:  # str / text
                var = tk.StringVar(value=str(default or ""))
                ttk.Entry(grp, textvariable=var, width=20).pack(fill="x")
                storage[key] = var

        return panel

    def _params_get_values(self, storage: dict) -> dict:
        """Extrae los valores actuales de un storage generado por _build_params_panel."""
        result = {}
        for key, var in storage.items():
            if isinstance(var, dict):
                result[key] = [opt for opt, bv in var.items() if bv.get()]
            elif hasattr(var, "get"):
                result[key] = var.get()
        return result




    def _snapshot_ner(self) -> dict:
        """Lee en el hilo principal todo lo que el worker NER necesita de la UI.

        `_params_get_values` recorre variables Tk, así que también tiene que
        ejecutarse aquí y no dentro del hilo.
        """
        p = self._params_get_values(self._ner_params) if self._ner_params else {}
        return {
            "params":        p,
            "usar_ia":       p.get("usar_ia", self._var_ner_llm.get()),
            "proveedor_llm": p.get("proveedor_llm", self._var_ner_prov.get()),
            "modelo_ollama": p.get("modelo_ollama_ner", self._var_ner_ollama_modelo.get()),
        }








    def _ner_enlazar_wikidata(self):
        """Enlaza todas las entidades del índice NER con Wikidata en un thread."""
        if not getattr(ST, "indice_ner_global", None) or not any(ST.indice_ner_global.values()):
            messagebox.showwarning("Sin datos", "Ejecuta el análisis NER primero."); return
        try:
            from core.entity_linker import enlazar_indice_ner
        except ImportError:
            messagebox.showerror("Módulo no disponible", "core/entity_linker.py no encontrado."); return

        # Contar total de entidades
        total = sum(len(ents) for ents in ST.indice_ner_global.values())
        if total == 0:
            messagebox.showwarning("Sin entidades", "El índice NER está vacío."); return

        # Ventana de progreso
        win = tk.Toplevel(self)
        win.title("Enlazando con Wikidata…")
        win.resizable(False, False)
        win.grab_set()
        tk.Label(win, text="Enlazando entidades con Wikidata",
                 font=("Segoe UI", 11, "bold"), pady=12).pack()
        tk.Label(win, text=f"{total} entidades · puede tardar varios minutos",
                 font=("Segoe UI", 9), fg="#777F84").pack()
        var_prog = tk.StringVar(value="0 / 0")
        lbl_prog = tk.Label(win, textvariable=var_prog, font=("Consolas", 9), pady=6)
        lbl_prog.pack()
        pb = ttk.Progressbar(win, mode="determinate", length=340, maximum=total)
        pb.pack(padx=20, pady=(0, 8))
        txt_log = scrolledtext.ScrolledText(win, height=8, width=52,
                                             font=("Consolas", 8), state="disabled")
        txt_log.pack(padx=12, pady=(0, 12))
        btn_cerrar = ttk.Button(win, text="Cerrar", state="disabled",
                                command=win.destroy)
        btn_cerrar.pack(pady=(0, 12))

        def _log(msg):
            txt_log.config(state="normal")
            txt_log.insert("end", msg + "\n")
            txt_log.see("end")
            txt_log.config(state="disabled")

        def _worker():
            encontradas = 0
            def _cb(n, tot):
                nonlocal encontradas
                self.after(0, lambda: pb.config(value=n))
                self.after(0, lambda: var_prog.set(f"{n} / {tot}"))

            # Mapa {art_id: texto} para desambiguación contextual de Wikidata.
            # Mismo criterio de id que el pipeline NER (id/titulo de df_articulos).
            textos_articulos = {}
            try:
                if ST.df_articulos is not None and not ST.df_articulos.empty:
                    for _i, _row in ST.df_articulos.iterrows():
                        _txt = str(_row.get("texto", _row.get("contenido", "")))
                        _aid = str(_row.get("id", _row.get("titulo", f"art_{_i}")))
                        if _txt.strip():
                            textos_articulos[_aid] = _txt
            except Exception:
                textos_articulos = {}

            try:
                from core.perfil_corpus import PerfilCorpus
                resultado = enlazar_indice_ner(
                    ST.indice_ner_global,
                    sin_red=False,
                    callback=_cb,
                    textos_articulos=textos_articulos or None,
                    perfil=PerfilCorpus.desde_dict(getattr(ST, "perfil_corpus", None)),
                )
                # Guardar resultado en ST y mostrar resumen
                ST.wikidata_enlaces = resultado
                for cat, ents in resultado.items():
                    for texto, enlace in ents.items():
                        if enlace:
                            encontradas += 1
                            self.after(0, lambda t=texto, e=enlace:
                                _log(f"✓ {t} → {e['label']} ({e['id']})"))
                self.after(0, lambda: _log(
                    f"\n✅ {encontradas}/{total} entidades enlazadas con Wikidata."))
                # Actualizar detalle si hay entidad seleccionada
                self.after(0, self._ner_refrescar_tv)
            except Exception as exc:
                self.after(0, lambda err=str(exc): _log(f"⚠️ Error: {err}"))
            finally:
                self.after(0, lambda: btn_cerrar.config(state="normal"))

        import threading
        threading.Thread(target=_worker, daemon=True).start()


    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA: BÚSQUEDA SEMÁNTICA FAISS
    # ══════════════════════════════════════════════════════════════════════════











    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA: COLLOCATES Y REDES LÉXICAS
    # ══════════════════════════════════════════════════════════════════════════
















    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA: ANOTACIÓN SEMÁNTICA REVISABLE
    # ══════════════════════════════════════════════════════════════════════════










    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA: DETECCIÓN DE NOVEDAD Y CAMBIO DISCURSIVO
    # ══════════════════════════════════════════════════════════════════════════








    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA: REDES DE CO-OCURRENCIA (v12)
    # ══════════════════════════════════════════════════════════════════════════



    # ── Grafo canónico (entidades + relaciones) ───────────────────────────────









    # ── Fase 4: export RDF ─────────────────────────────────────────────────────


    # ── Portabilidad: bundle OKF (Open Knowledge Format) ───────────────────────



    # ── Fase 3: exploradores ───────────────────────────────────────────────────



    # ── Fase 2: vocabulario controlado ─────────────────────────────────────────


    # ── Editor manual de relaciones ────────────────────────────────────────────
















    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA: SEMÁNTICO (v13) — tono editorial + léxico + estilometría
    # ══════════════════════════════════════════════════════════════════════════







    def _worker_tono(self, entradas):
        from core.sentiment_engine import analizar_corpus_tono, estadisticas_tono
        p = self._params_get_values(self._sem_params) if getattr(self, "_sem_params", None) else {}
        motor   = p.get("motor", "lexicon")
        workers = int(p.get("workers", 4))
        tonos_activos = p.get("tonos_activos") or None
        api_key = _resolver_api_key_modelo("tono")[0] if motor == "ia" else None
        total = len(entradas)

        def cb(n, t, art_id):
            self.after(0, lambda: self._lbl_tono_ok.config(
                text=f"Analizando {n}/{t}: {art_id}"))

        nuevos = analizar_corpus_tono(entradas, api_key, callback=cb, workers=workers)
        self._tono_resultados.update(nuevos)

        stats = estadisticas_tono(self._tono_resultados)
        self.after(0, lambda s=stats: self._sem_tono_actualizar_chips(s))
        self.after(0, self._sem_tono_refrescar)
        self.after(0, lambda: self._btn_tono_art.config(state="normal"))
        self.after(0, lambda: self._btn_tono_corpus.config(state="normal"))
        n = len(self._tono_resultados)
        self.after(0, lambda: self._lbl_tono_ok.config(
            text=f"✅ {n} artículos — dominante: {stats.get('tono_dominante','?')} · "
                 f"polarización: {stats.get('indice_polarizacion', 0)}%"))








    def _worker_lexico(self, textos):
        from core.lexicon_engine import construir_glosario
        api_key, _m = _resolver_api_key_modelo("tono")
        total = len(textos)

        def cb(i, t, aid):
            self.after(0, lambda n=i, tot=t, a=aid:
                       self._lbl_lex_ok.config(text=f"Procesando {n}/{tot}: {a}"))

        self._glosario_data = construir_glosario(textos, api_key, callback=cb)
        self.after(0, self._sem_lex_refrescar)
        self.after(0, lambda: self._btn_lex_art.config(state="normal"))
        self.after(0, lambda: self._btn_lex_corpus.config(state="normal"))
        n = sum(len(v) for v in self._glosario_data.values())
        self.after(0, lambda: self._lbl_lex_ok.config(text=f"✅ {n} entradas en glosario"))




    def _worker_estilo(self, textos, n_clusters):
        from core.stylometry_engine import cluster_tematico
        self.after(0, lambda: self._lbl_estilo_ok.config(text="Calculando clusters…"))
        try:
            result = cluster_tematico(textos, n_clusters=n_clusters)
            self._estilo_resultados = result
            self.after(0, self._sem_estilo_refrescar)
            n = len(result)
            self.after(0, lambda: self._lbl_estilo_ok.config(text=f"✅ {n} artículos agrupados"))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._lbl_estilo_ok.config(text=f"⚠ Error: {err}"))
        self.after(0, lambda: self._btn_estilo.config(state="normal"))




    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA: VISUALIZAR (v14) — nubes, heatmap, mapa, timeline
    # ══════════════════════════════════════════════════════════════════════════















    def _worker_nube(self, textos):
        from pathlib import Path as _PPath

        from core.viz_engine import nube_palabras
        self.after(0, lambda: self._lbl_nube_ok.config(text="Generando nube…"))
        try:
            ruta = _PPath.home() / "Documents" / "BashkarStation" / "viz" / "nube_palabras.png"
            nube_palabras(textos, ruta, titulo="Corpus Estampa 1930-1940")
            self._nube_path = ruta
            self.after(0, self._viz_nube_mostrar_preview)
            self.after(0, lambda: self._lbl_nube_ok.config(text=f"✅ Nube generada: {ruta}"))
        except ImportError as e:
            err = str(e)
            self.after(0, lambda: self._lbl_nube_ok.config(text=f"⚠ {err}"))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._lbl_nube_ok.config(text=f"⚠ Error: {err}"))
        self.after(0, lambda: self._btn_nube.config(state="normal"))




    def _worker_heatmap(self, terminos):
        from pathlib import Path as _PPath


        from core.viz_engine import heatmap_temporal
        self.after(0, lambda: self._lbl_heat_ok.config(text="Generando heatmap…"))
        try:
            textos = ST.corpus_txt or []
            df = pd.DataFrame({"texto": textos,
                                "fecha": [f"1935-{(i%12)+1:02d}-01" for i in range(len(textos))]})
            ruta = _PPath.home() / "Documents" / "BashkarStation" / "viz" / "heatmap_temporal.png"
            heatmap_temporal(df, terminos, ruta=ruta)
            self._heat_path = ruta
            self.after(0, lambda: self._lbl_heat_ok.config(text=f"✅ Heatmap generado: {ruta}"))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._lbl_heat_ok.config(text=f"⚠ Error: {err}"))
        self.after(0, lambda: self._btn_heat.config(state="normal"))



    def _worker_mapa(self):
        from pathlib import Path as _PPath

        from core.viz_engine import mapa_lugares
        self.after(0, lambda: self._lbl_mapa_ok.config(text="Generando mapa…"))
        try:
            ruta = _PPath.home() / "Documents" / "BashkarStation" / "viz" / "mapa_lugares.html"
            mapa_lugares(ST.indice_ner_global, ruta)
            self._mapa_path = ruta
            self.after(0, lambda: self._lbl_mapa_ok.config(text=f"✅ Mapa generado: {ruta}"))
        except ImportError as e:
            err = str(e)
            self.after(0, lambda: self._lbl_mapa_ok.config(text=f"⚠ {err}"))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._lbl_mapa_ok.config(text=f"⚠ Error: {err}"))
        self.after(0, lambda: self._btn_mapa.config(state="normal"))



    def _worker_timeline(self):
        from pathlib import Path as _PPath

        from core.timeline_engine import generar_timeline_html
        self.after(0, lambda: self._lbl_tl_ok.config(text="Generando timeline editorial…"))
        try:
            # Construir lista de artículos desde corpus_meta o df_articulos
            articulos = []
            if ST.df_articulos is not None and not ST.df_articulos.empty:
                for _, row in ST.df_articulos.iterrows():
                    articulos.append({
                        "art_id":  str(row.get("id", "")),
                        "titulo":  str(row.get("titulo", "") or ""),
                        "autor":   str(row.get("autor", "") or ""),
                        "seccion": str(row.get("seccion", "") or ""),
                        "fecha":   str(row.get("fecha_publicacion", "") or ""),
                        "numero":  str(row.get("numero", "") or ""),
                        "tono":    str(row.get("tono", "") or ""),
                    })
            elif ST.corpus_meta:
                for art_id, meta in ST.corpus_meta.items():
                    articulos.append({
                        "art_id":  art_id,
                        "titulo":  meta.get("titulo", ""),
                        "autor":   meta.get("autor", ""),
                        "seccion": meta.get("seccion", ""),
                        "fecha":   meta.get("fecha", ""),
                        "numero":  meta.get("numero", ""),
                    })

            if not articulos:
                self.after(0, lambda: self._lbl_tl_ok.config(
                    text="⚠ Sin artículos segmentados — ejecuta Segmentar primero"))
                self.after(0, lambda: self._btn_tl.config(state="normal"))
                return

            ruta = _PPath.home() / "Documents" / "BashkarStation" / "viz" / "timeline_editorial.html"
            ruta.parent.mkdir(parents=True, exist_ok=True)

            def _cb(n, total, msg):
                self.after(0, lambda: self._lbl_tl_ok.config(
                    text=f"⏳ {n}/{total} — {msg[:40]}"))

            generar_timeline_html(
                articulos, ruta,
                titulo_corpus=getattr(ST, "publicacion", "Corpus editorial"),
                callback=_cb,
            )
            self._tl_path = ruta
            n = len(articulos)
            self.after(0, lambda: self._lbl_tl_ok.config(
                text=f"✅ Timeline generada: {n} artículos — {ruta}"))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._lbl_tl_ok.config(text=f"⚠ Error: {err}"))
        self.after(0, lambda: self._btn_tl.config(state="normal"))



    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA: REPORTE (v15) — narrativas académicas + HTML + Word
    # ══════════════════════════════════════════════════════════════════════════
















    def _worker_narrativas(self):
        from core.storytelling_engine import generar_narrativa
        # Bug F821: api_key no estaba definida — NameError al generar narrativas.
        api_key = ST.api_keys.get("anthropic", "") or ST.api_key
        narrativas = {}

        # Narrativa corpus
        stats_corpus = self._rep_stats_corpus()
        narrativas["corpus"] = generar_narrativa(stats_corpus, api_key, seccion="corpus")

        # Narrativa NER si disponible
        if getattr(ST, "indice_ner_global", None):
            top_ner = {}
            for cat, ents in ST.indice_ner_global.items():
                top = sorted(ents.items(), key=lambda x: len(x[1]), reverse=True)[:5]
                top_ner[cat] = [(e, len(a)) for e, a in top]
            narrativas["ner"] = generar_narrativa({"top_entidades": top_ner}, api_key, seccion="corpus")

        self._narrativas_data = narrativas
        texto = "\n\n---\n\n".join(f"[{s.upper()}]\n{t}" for s, t in narrativas.items())

        def _mostrar():
            self._txt_rep_nar.config(state="normal")
            self._txt_rep_nar.delete("1.0", "end")
            self._txt_rep_nar.insert("1.0", texto)
            self._txt_rep_nar.config(state="disabled")
            self._lbl_rep_nar.config(text=f"✅ {len(narrativas)} narrativas generadas")
            self._btn_rep_nar.config(state="normal")

        self.after(0, _mostrar)








    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA: DASHBOARD (v16) — resumen ejecutivo + exportador ZIP
    # ══════════════════════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════════════════════
    # INICIO — panel de investigación (capa visual en ui_redesign.py)
    # ══════════════════════════════════════════════════════════════════════════

    # Las claves que usa el tablero → páginas reales de esta ventana.
    _INICIO_DESTINOS = {
        "home": "inicio",   "projects": "cfg",  "ocr": "ocr",
        "norm": "norm",     "seg": "seg",       "ner": "ner",
        "anal": "anal",     "red": "red",       "res": "res",
        "export": "res",
    }

    def _build_inicio(self):
        """Monta el tablero de `ui_redesign` como página de arranque."""
        from ui_redesign import (
            BashkarCallbacks,
            BashkarDesktopShell,
            state_from_bashkar,
        )

        callbacks = BashkarCallbacks(
            navigate=self._inicio_navegar,
            save_project=self._guardar_proyecto,
            edit_project=lambda: self._mostrar_pagina("cfg"),
            open_projects=self._abrir_gestor_proyectos,
            open_settings=lambda: self._mostrar_pagina("cfg"),
            action_selected=self._inicio_navegar,
        )
        # chrome=False: la topbar, la activity bar y el sidebar los dibuja esta
        # ventana, que es la que conoce los 30 paneles; el módulo solo aporta
        # el tablero.
        self._inicio_shell = BashkarDesktopShell(
            self._tab_inicio,
            state_from_bashkar(ST),
            callbacks,
            version=APP_VERSION,
            chrome=False,
        )
        self._inicio_shell.pack(fill="both", expand=True)
        self._inicio_refrescar()

    def _inicio_navegar(self, clave: str):
        destino = self._INICIO_DESTINOS.get(clave, clave)
        if destino in self._frames_pagina:
            self._mostrar_pagina(destino)

    def _inicio_capacidades(self):
        """
        Qué motores hay en ESTE equipo. Se pregunta si el paquete está, sin
        importarlo: importar spaCy en frío tarda del orden de diez segundos y
        esto corre en el hilo de la interfaz (misma lección que el endpoint
        /api/capacidades del servidor web, sesión 55).
        """
        if getattr(self, "_inicio_caps", None):
            return self._inicio_caps

        import importlib.util
        import shutil

        from ui_redesign import Capability

        def _instalado(modulo: str) -> bool:
            try:
                return importlib.util.find_spec(modulo) is not None
            except (ImportError, ValueError):
                return False

        hay_tesseract = bool(shutil.which("tesseract")) or \
            (_APP_DIR / "tesseract_path.txt").exists()
        hay_poppler = bool(shutil.which("pdftoppm")) or \
            (_APP_DIR / "poppler_path.txt").exists()

        self._inicio_caps = [
            Capability("Tesseract OCR", "Reconocimiento óptico local",
                       hay_tesseract),
            Capability("Poppler", "Convierte el PDF en imágenes", hay_poppler),
            Capability("PyMuPDF", "Lectura y render de documentos",
                       _instalado("fitz")),
            Capability("spaCy", "NER y análisis lingüístico local",
                       _instalado("es_core_news_md") or _instalado("es_core_news_sm")),
            Capability("Kraken / CATMuS", "HTR para prensa histórica",
                       _instalado("kraken")),
            Capability("LLM local", "Ollama o LM Studio en tu equipo",
                       _instalado("requests")),
        ]
        return self._inicio_caps

    def _inicio_refrescar(self):
        """Vuelve a leer ST y repinta el tablero. Barato: no toca disco."""
        shell = getattr(self, "_inicio_shell", None)
        if shell is None:
            return
        from ui_redesign import state_from_bashkar

        estado = state_from_bashkar(ST)
        estado.capabilities = self._inicio_capacidades()
        estado.current_year = getattr(ST, "periodo", "") or ""

        # Último número cargado, si el corpus ya trae metadatos.
        meta = getattr(ST, "corpus_meta", None)
        try:
            if meta is not None and hasattr(meta, "columns") and "numero" in meta.columns:
                numeros = sorted(str(n) for n in meta["numero"].dropna().unique())
                if numeros:
                    estado.current_number = numeros[-1]
        except Exception:
            pass

        try:
            shell.set_state(estado)
        except tk.TclError:
            pass          # la ventana se está cerrando






    def _worker_zip(self, dest):
        import zipfile
        from pathlib import Path as _PPath
        base = _PPath.home() / "Documents" / "BashkarStation"
        try:
            archivos = list(base.rglob("*")) if base.exists() else []
            archivos = [f for f in archivos if f.is_file()]
            with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in archivos:
                    zf.write(f, f.relative_to(base.parent))
            n = len(archivos)
            self.after(0, lambda: self._lbl_dash_ok.config(
                text=f"✅ ZIP exportado: {n} archivos → {dest}"))
            self.after(0, lambda: messagebox.showinfo("Exportado",
                f"Paquete ZIP creado con {n} archivos:\n{dest}"))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._lbl_dash_ok.config(text=f"⚠ Error: {err}"))
        self.after(0, lambda: self._btn_dash_zip.config(state="normal"))


    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA: TÓPICOS (visión definitiva)
    # ══════════════════════════════════════════════════════════════════════════






    # ══════════════════════════════════════════════════════════════════════════
    # PIPELINE MAESTRO — botón "Generar paquete completo" en Dashboard
    # ══════════════════════════════════════════════════════════════════════════


    def _pipeline_maestro_articulos(self) -> list:
        """Artículos desde el estado actual. Ver core.servicios_corpus."""
        from core.servicios_corpus import articulos_para_pipeline
        return articulos_para_pipeline(getattr(ST, "corpus_txt", []) or [],
                                       getattr(ST, "corpus_meta", None))

    # ══════════════════════════════════════════════════════════════════════════
    # «GUARDAR COMO…» — presets de exportación estilo ABBYY FineReader
    # ══════════════════════════════════════════════════════════════════════════








    # ══════════════════════════════════════════════════════════════════════════
    # EXPORTACIONES ESPECIALIZADAS — agrega botones a panel Resultados
    # ══════════════════════════════════════════════════════════════════════════






    # ── Validar TEI ───────────────────────────────────────────────────────────



    # ── Paquete para publicación ───────────────────────────────────────────────



    # ── Diff visual Normalizar ────────────────────────────────────────────────


    # ── Dataset HTR Normalizar ────────────────────────────────────────────────



# ══════════════════════════════════════════════════════════════════════════════
# COMPARAR (v17) — comparación multi-proyecto
# ══════════════════════════════════════════════════════════════════════════════

    def _build_comp2(self):
        import tkinter as tk
        from tkinter import ttk
        self._tab_comp2.columnconfigure(0, weight=1)
        self._tab_comp2.rowconfigure(2, weight=1)
        ttk.Label(self._tab_comp2, text="Comparación multi-proyecto", style="H.TLabel").grid(
            row=0, column=0, sticky="w", padx=20, pady=(18, 4))
        ttk.Label(self._tab_comp2, text="Compara entidades, vocabulario y tópicos entre distintos proyectos .bashkar",
                  style="Sub.TLabel").grid(row=1, column=0, sticky="w", padx=20, pady=(0, 8))

        cuerpo = ttk.Frame(self._tab_comp2)
        cuerpo.grid(row=2, column=0, sticky="nsew", padx=20, pady=4)
        cuerpo.columnconfigure(0, weight=1)
        cuerpo.rowconfigure(3, weight=1)

        # Lista de proyectos
        ttk.Label(cuerpo, text="Proyectos a comparar:").grid(row=0, column=0, sticky="w")
        self._comp2_lista_var = tk.Variable(value=[])
        self._comp2_listbox = tk.Listbox(cuerpo, listvariable=self._comp2_lista_var,
                                          height=6, bg="#1C2227", fg="#E8E5DF",
                                          selectmode=tk.MULTIPLE, font=("Consolas", 10))
        self._comp2_listbox.grid(row=1, column=0, sticky="ew", pady=4)

        bframe = ttk.Frame(cuerpo)
        bframe.grid(row=2, column=0, sticky="w", pady=4)
        ttk.Button(bframe, text="+ Agregar proyecto",
                   command=self._comp2_agregar).pack(side="left", padx=2)
        ttk.Button(bframe, text="✕ Quitar selección",
                   command=self._comp2_quitar).pack(side="left", padx=2)
        ttk.Button(bframe, text="▶ Comparar",
                   command=self._comp2_ejecutar).pack(side="left", padx=10)
        ttk.Button(bframe, text="🌐 Ver HTML",
                   command=self._comp2_ver_html).pack(side="left", padx=2)

        self._comp2_log = tk.Text(cuerpo, height=14, state="disabled",
                                   bg="#0E1114", fg="#B5B6B3",
                                   font=("Consolas", 9), wrap="word")
        self._comp2_log.grid(row=3, column=0, sticky="nsew", pady=8)

    def _comp2_agregar(self):
        from tkinter import filedialog
        ruta = filedialog.askopenfilename(
            title="Seleccionar proyecto .bashkar",
            filetypes=[("Bashkar", "*.bashkar"), ("Todos", "*.*")]
        )
        if ruta and ruta not in ST.comparar_rutas:
            ST.comparar_rutas.append(ruta)
            self._comp2_lista_var.set(ST.comparar_rutas)

    def _comp2_quitar(self):
        sel = self._comp2_listbox.curselection()
        for i in reversed(sel):
            ST.comparar_rutas.pop(i)
        self._comp2_lista_var.set(ST.comparar_rutas)

    def _comp2_ejecutar(self):
        if len(ST.comparar_rutas) < 2:
            from tkinter import messagebox
            messagebox.showwarning("Comparar", "Agrega al menos 2 proyectos.")
            return
        import threading
        self._comp2_log.config(state="normal")
        self._comp2_log.delete("1.0", "end")
        self._comp2_log.config(state="disabled")
        threading.Thread(target=self._comp2_worker, daemon=True).start()

    def _comp2_worker(self):
        def _log(msg):
            self.after(0, lambda m=msg: self._comp2_log_insert(m))
        try:
            from pathlib import Path

            from core.comparador import (
                exportar_reporte_html,
                generar_reporte_comparativo,
            )
            nombres = [Path(r).stem for r in ST.comparar_rutas]
            _log("Generando reporte comparativo...")
            rep = generar_reporte_comparativo(ST.comparar_rutas, nombres, callback=_log)
            ST.reporte_comparativo = rep
            out = Path.home() / "Documents" / "BashkarStation" / "comparativa.html"
            exportar_reporte_html(rep, out)
            _log(f"\n✅ Reporte guardado: {out}")
            self.after(0, lambda: setattr(self, "_comp2_html_path", str(out)))
        except Exception as e:
            _log(f"\n❌ Error: {e}")

    def _comp2_log_insert(self, msg):
        self._comp2_log.config(state="normal")
        self._comp2_log.insert("end", msg + "\n")
        self._comp2_log.see("end")
        self._comp2_log.config(state="disabled")

    def _comp2_ver_html(self):
        import os
        import webbrowser
        ruta = getattr(self, "_comp2_html_path", None)
        if ruta and os.path.exists(ruta):
            webbrowser.open(f"file:///{ruta.replace(chr(92), '/')}")
        else:
            from tkinter import messagebox
            messagebox.showinfo("Comparar", "Ejecuta la comparación primero.")


# ══════════════════════════════════════════════════════════════════════════════
# INTERTEXTUALIDAD (v17)
# ══════════════════════════════════════════════════════════════════════════════

    def _build_intxt(self):
        import tkinter as tk
        from tkinter import ttk
        self._tab_intxt.columnconfigure(0, weight=1)
        self._tab_intxt.rowconfigure(2, weight=1)
        ttk.Label(self._tab_intxt, text="Análisis intertextual", style="H.TLabel").grid(
            row=0, column=0, sticky="w", padx=20, pady=(18, 4))
        ttk.Label(self._tab_intxt, text="Detecta citas compartidas, similitud textual y conexiones entre artículos",
                  style="Sub.TLabel").grid(row=1, column=0, sticky="w", padx=20, pady=(0, 8))

        cuerpo = ttk.Frame(self._tab_intxt)
        cuerpo.grid(row=2, column=0, sticky="nsew", padx=20, pady=4)
        cuerpo.columnconfigure(1, weight=1)
        cuerpo.rowconfigure(3, weight=1)

        # Parámetros
        ttk.Label(cuerpo, text="Umbral similitud (0–1):").grid(row=0, column=0, sticky="w", pady=4)
        self._intxt_umbral = ttk.Spinbox(cuerpo, from_=0.1, to=0.9, increment=0.05,
                                          width=8, format="%.2f")
        self._intxt_umbral.set("0.30")
        self._intxt_umbral.grid(row=0, column=1, sticky="w", padx=8)

        self._intxt_usar_llm = tk.BooleanVar(value=True)
        ttk.Checkbutton(cuerpo, text="Analizar pares con LLM (Claude)",
                        variable=self._intxt_usar_llm).grid(row=1, column=0, columnspan=2,
                                                              sticky="w", pady=2)

        bframe = ttk.Frame(cuerpo)
        bframe.grid(row=2, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Button(bframe, text="▶ Analizar intertextualidad",
                   command=self._intxt_ejecutar).pack(side="left", padx=2)
        ttk.Button(bframe, text="🕸 Ver grafo HTML",
                   command=self._intxt_ver_grafo).pack(side="left", padx=4)

        self._intxt_log = tk.Text(cuerpo, height=16, state="disabled",
                                   bg="#0E1114", fg="#B5B6B3",
                                   font=("Consolas", 9), wrap="word")
        self._intxt_log.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=4)

    def _intxt_ejecutar(self):
        if not ST.seg_done:
            from tkinter import messagebox
            messagebox.showwarning("Intertextualidad", "Segmenta los artículos primero.")
            return
        import threading
        self._intxt_log.config(state="normal")
        self._intxt_log.delete("1.0", "end")
        self._intxt_log.config(state="disabled")
        threading.Thread(target=self._intxt_worker, daemon=True).start()

    def _intxt_worker(self):
        def _log(msg):
            self.after(0, lambda m=msg: self._intxt_log_insert(m))
        try:
            from pathlib import Path

            from core.intertextual_engine import (
                analizar_intertextualidad,
                exportar_grafo_intertextual,
            )
            articulos = {}
            if ST.df_articulos is not None:
                for _, row in ST.df_articulos.iterrows():
                    aid = str(row.get("id", row.name))
                    articulos[aid] = {
                        "texto_limpio": str(row.get("texto", "")),
                        "titulo": str(row.get("titulo", aid)),
                    }
            umbral = float(self._intxt_umbral.get())
            usar_llm = self._intxt_usar_llm.get()
            resultado = analizar_intertextualidad(
                articulos,
                api_key=ST.api_key,
                umbral_similitud=umbral,
                usar_llm=usar_llm,
                callback=_log,
            )
            ST.intertex_resultado = resultado
            citas = len(resultado.get("citas_compartidas", {}))
            pares = len(resultado.get("pares_similares", []))
            conn  = len(resultado.get("conexiones_llm", []))
            _log(f"\n✅ {citas} citas compartidas · {pares} pares similares · {conn} conexiones LLM")
            # Exportar grafo
            out = Path.home() / "Documents" / "BashkarStation" / "intertextual.html"
            exportar_grafo_intertextual(resultado, out)
            _log(f"Grafo: {out}")
            self.after(0, lambda: setattr(self, "_intxt_grafo_path", str(out)))
        except Exception as e:
            _log(f"\n❌ Error: {e}")

    def _intxt_log_insert(self, msg):
        self._intxt_log.config(state="normal")
        self._intxt_log.insert("end", msg + "\n")
        self._intxt_log.see("end")
        self._intxt_log.config(state="disabled")

    def _intxt_ver_grafo(self):
        import os
        import webbrowser
        ruta = getattr(self, "_intxt_grafo_path", None)
        if ruta and os.path.exists(ruta):
            webbrowser.open(f"file:///{ruta.replace(chr(92), '/')}")
        else:
            from tkinter import messagebox
            messagebox.showinfo("Intertextualidad", "Ejecuta el análisis primero.")


# ══════════════════════════════════════════════════════════════════════════════
# VALIDACIÓN HUMANA + CONFIANZA (v18)
# ══════════════════════════════════════════════════════════════════════════════








# ══════════════════════════════════════════════════════════════════════════════
# COLABORACIÓN (v19)
# ══════════════════════════════════════════════════════════════════════════════











    # ══════════════════════════════════════════════════════════════════════════
    # LINGÜÍSTICA COMPUTACIONAL — sintaxis, correferencia, morfología, emociones
    # ══════════════════════════════════════════════════════════════════════════


    # ── Helpers internos de lingüística ──────────────────────────────────────

    def _ir_a_ling_pestania(self, indice: int):
        """Navega a Lingüística y selecciona la pestaña por índice (0-based)."""
        self._mostrar_pagina("ling")
        nb = getattr(self, "_nb_ling", None)
        if nb is not None:
            try:
                nb.select(indice)
            except Exception:
                pass



    # ── Concordancias sintácticas ─────────────────────────────────────────────



    def _poblar_tv_sint(self, res):
        for row in self._tv_ling_sint.get_children():
            self._tv_ling_sint.delete(row)
        for r in res:
            frag = r.get("texto_completo", "")[:80]
            self._tv_ling_sint.insert("", "end", values=(
                r.get("patron", ""),
                r.get("match_principal", ""),
                r.get("match_secundario", ""),
                r.get("descripcion", ""),
                frag,
            ))
        self._lbl_ling_sint.config(
            text=f"✓ {len(res)} concordancias sintácticas encontradas.")


    # ── Relaciones SVO ────────────────────────────────────────────────────────



    def _poblar_tv_svo(self, res):
        for row in self._tv_ling_svo.get_children():
            self._tv_ling_svo.delete(row)
        for r in res:
            self._tv_ling_svo.insert("", "end", values=(
                r.get("sujeto", ""),
                r.get("sujeto_tipo", ""),
                r.get("relacion", ""),
                r.get("objeto", ""),
                r.get("objeto_tipo", ""),
                r.get("confianza", 0),
                r.get("oracion", "")[:80],
            ))
        # Cambiar a pestaña SVO
        self._nb_ling.select(1)
        self._lbl_ling_svo.config(
            text=f"✓ {len(res)} relaciones sujeto-verbo-objeto extraídas.")



    # ── Correferencia ─────────────────────────────────────────────────────────



    def _poblar_coref(self, cadenas):
        self._lb_coref.delete(0, "end")
        for c in cadenas:
            self._lb_coref.insert("end",
                f"{c['entidad_principal']} ({c['n_menciones']} menciones)")
        self._lbl_ling_coref.config(
            text=f"✓ {len(cadenas)} cadenas referenciales.")



    def _worker_coref_stats(self, corpus):
        try:
            from core.coref_engine import estadisticas_coref
            def cb(i, t): self.after(0, lambda: self._ling_log(
                f"Stats coref {i}/{t}…"))
            stats = estadisticas_coref(corpus[:30], callback=cb)
            msg = (
                f"Cadenas referenciales totales: {stats['total_cadenas']}\n"
                f"Menciones promedio por cadena: {stats['promedio_menciones']}\n"
                f"Densidad referencial: {stats['densidad_referencial']} "
                f"({stats['total_pronombres']} pronombres / {stats['total_tokens']} tokens)\n\n"
                "Top entidades referidas:\n"
            )
            for e in stats["entidades_mas_referidas"][:10]:
                msg += f"  {e['entidad']}: {e['n_menciones']} menciones\n"
            self.after(0, lambda: messagebox.showinfo("Estadísticas de correferencia", msg))
        except Exception as ex:
            self.after(0, lambda err=str(ex): messagebox.showerror("Error", err))
        finally:
            self.after(0, lambda: self._btn_ling_coref.config(state="normal"))

    # ── Morfología histórica ──────────────────────────────────────────────────



    def _poblar_tv_morf(self, datos):
        for row in self._tv_ling_morf.get_children():
            self._tv_ling_morf.delete(row)
        total_arc = sum(d["n_arcaismos"] for d in datos)
        total_tok = sum(d["n_tokens"] for d in datos)
        score_med = round(sum(d["score"] for d in datos) / len(datos), 4) if datos else 0
        self._lbl_morf_resumen.config(
            text=(f"Corpus: {len(datos)} docs | "
                  f"Arcaísmos: {total_arc} / {total_tok} tokens | "
                  f"Score histórico medio: {score_med:.4f}")
        )
        for d in datos:
            top = ", ".join(f"{x['forma']}×{x['n']}"
                            for x in d.get("top_arcaismos", [])[:4])
            marc = d.get("marcadores", {})
            marc_str = "  ".join(f"{k}({v})" for k, v in marc.items()) if marc else "—"
            score = d["score"]
            tag = "alta" if score >= 0.05 else ("media" if score >= 0.01 else "baja")
            self._tv_ling_morf.insert("", "end", tags=(tag,), values=(
                d["doc_idx"] + 1,
                d["n_tokens"],
                d["n_arcaismos"],
                f"{score:.4f}",
                marc_str,
                top,
            ))
        self._lbl_ling_morf.config(
            text=f"✓ {total_arc} formas históricas en {len(datos)} docs. Score medio: {score_med:.4f}")




    # ── Árbol de dependencias ─────────────────────────────────────────────────



    def _poblar_dep(self, datos: list):
        from core.sintaxis_engine import resumir_arbol_dep
        self._lb_dep.delete(0, "end")
        for i, d in enumerate(datos):
            resumen = resumir_arbol_dep(d)
            preview = d["oracion"][:60].replace("\n", " ")
            self._lb_dep.insert("end", f"{i+1}. {preview}")
        self._lbl_ling_dep.config(
            text=f"✓ {len(datos)} oraciones analizadas")
        if datos:
            self._lb_dep.selection_set(0)
            self._ling_dep_mostrar_tokens(None)



    # ── Emociones y subjetividad ──────────────────────────────────────────────



    def _poblar_tv_emo(self, resultados):
        from collections import Counter
        for row in self._tv_ling_emo.get_children():
            self._tv_ling_emo.delete(row)

        cnt_emo: Counter = Counter()
        cnt_disc: Counter = Counter()
        for r in resultados:
            emo_data = r.get("emociones", {}).get("emociones", {})
            subj_data = r.get("subjetividad", {})
            intens    = r.get("intensidad", {})

            emo_dom = r.get("emociones", {}).get("emocion_dominante") or "—"
            cnt_emo[emo_dom] += 1
            tipo_disc = subj_data.get("tipo_discurso", "—")
            cnt_disc[tipo_disc] += 1

            palabras = [p["palabra"] for p in
                        r.get("emociones", {}).get("palabras_detectadas", [])[:6]]
            score_i = intens.get("score_intensidad", 0)

            self._tv_ling_emo.insert("", "end", values=(
                r.get("art_id", ""),
                emo_dom,
                f"{subj_data.get('score_subjetividad', 0):.2f}",
                tipo_disc,
                f"{score_i:.2f}",
                ", ".join(palabras),
            ))

        # Resumen
        resumen = (
            f"Emoción dominante más frecuente: "
            f"{cnt_emo.most_common(1)[0][0] if cnt_emo else '—'} | "
            f"Discurso subjetivo: {cnt_disc.get('subjetivo', 0)} docs | "
            f"Factual: {cnt_disc.get('factual', 0)} docs | "
            f"Mixto: {cnt_disc.get('mixto', 0)} docs"
        )
        self._lbl_emo_resumen.config(text=resumen)
        self._lbl_ling_emo.config(
            text=f"✓ {len(resultados)} artículos analizados.")



    # ── Encuadre (framing) ────────────────────────────────────────────────────



    def _poblar_tv_frame(self, resumen, datos):
        for row in self._tv_ling_frame.get_children():
            self._tv_ling_frame.delete(row)
        for d in datos:
            dist = d.get("distribucion", [])
            pct = f"{dist[0]['porcentaje']:.0f}%" if dist else "—"
            sec = dist[1]["frame"] if len(dist) > 1 else "—"
            self._tv_ling_frame.insert("", "end", values=(
                d.get("art_id", ""),
                d.get("frame_dominante") or "—",
                d.get("etiqueta") or "—",
                pct, sec, d.get("total_marcadores", 0),
            ))
        dist_corpus = resumen.get("distribucion_corpus", {})
        top = " · ".join(f"{k} ({v})" for k, v in list(dist_corpus.items())[:5])
        self._lbl_frame_resumen.config(
            text=f"Encuadre dominante del corpus: "
                 f"{resumen.get('etiqueta_dominante') or '—'}   |   Top: {top}")
        self._lbl_ling_frame.config(
            text=f"✓ {resumen.get('n_articulos', 0)} artículos analizados.")



    # ── Polaridad discriminante ───────────────────────────────────────────────



    def _poblar_tv_pol(self, datos):
        from collections import Counter
        for row in self._tv_ling_pol.get_children():
            self._tv_ling_pol.delete(row)
        cnt: Counter = Counter()
        for r in datos:
            pol = r.get("polaridad", "neutro")
            cnt[pol] += 1
            self._tv_ling_pol.insert("", "end", tags=(pol,), values=(
                r.get("art_id", ""), pol, f"{r.get('score', 0):+.3f}",
                r.get("n_pos", 0), r.get("n_neg", 0),
                f"{r.get('intensidad', 0):.2f}",
            ))
        try:
            from core import sentimiento_discriminante as sd
            ipa = sd.indice_polarizacion_afectiva(dict(cnt))
        except Exception:
            ipa = 0.0
        self._lbl_pol_resumen.config(
            text=f"Positivo: {cnt.get('positivo', 0)}  ·  "
                 f"Negativo: {cnt.get('negativo', 0)}  ·  "
                 f"Neutro: {cnt.get('neutro', 0)}   |   "
                 f"Índice de polarización afectiva: {ipa:.3f}")
        self._lbl_ling_pol.config(text=f"✓ {len(datos)} artículos analizados.")



    # ── Revisión NER (human-in-the-loop) ──────────────────────────────────────



    def _poblar_tv_rev(self, pendientes):
        for row in self._tv_ling_rev.get_children():
            self._tv_ling_rev.delete(row)
        for d in pendientes:
            nivel = d.get("nivel", "")
            self._tv_ling_rev.insert("", "end", iid=f"{d['categoria']}|{d['nombre']}",
                                     tags=(nivel,), values=(
                d.get("nombre", ""), d.get("categoria", ""),
                d.get("n_articulos", 0), nivel,
                d.get("etiqueta", "") or
                ("○ VALIDAR" if nivel == "red" else "◐ REVISAR"),
            ))





    # ── Validación (Kappa de Cohen) ───────────────────────────────────────────





    def _val_log(self, msg):
        self._txt_val_res.config(state="normal")
        self._txt_val_res.delete("1.0", "end")
        self._txt_val_res.insert("end", msg + "\n")
        self._txt_val_res.config(state="disabled")


import re as re

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if "--diagnostico" in sys.argv:
        # Sin ventana: informe JSON de GPU, modelos y motores (core/diagnostico.py).
        from core.diagnostico import main as _diagnostico
        sys.exit(_diagnostico(sys.argv))
    app = BashkarApp()
    app.mainloop()

