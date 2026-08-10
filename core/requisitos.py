"""
core/requisitos.py — Qué necesita Bashkar Station para funcionar, y qué falta.

Este módulo SOLO diagnostica y describe. No imprime, no pregunta y no instala
por su cuenta: devuelve datos. Existe para que el instalador de consola
(`instalar.py`) y el asistente gráfico (`setup_wizard.py`) compartan un único
criterio de "esto está listo" en vez de mantener dos listas que se separan con
el tiempo.

La distinción que ordena todo el módulo es entre lo que se puede instalar solo
y lo que no:

  · Los paquetes de Python se instalan con pip, dentro del mismo intérprete.
    Salvo una excepción crítica: dentro de un .exe de PyInstaller NO se puede,
    porque `sys.executable` apunta al propio .exe y no a un Python con pip —
    intentarlo generó una bomba de fork real en este proyecto (~90 procesos en
    12 segundos, hubo que reiniciar la máquina). De ahí `puede_instalarse`.

  · Tesseract y Poppler son programas del sistema. Se instalan con el gestor de
    paquetes de cada plataforma (Homebrew en macOS, apt en Linux) o con un
    instalador descargado (Windows). Aquí nunca se lanzan esos comandos por
    cuenta propia: se devuelve la instrucción exacta para que la persona decida.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from core import plataforma

# Versión mínima de Python. Por debajo de 3.10 el proyecto usa sintaxis que ni
# siquiera compila (`X | Y` en anotaciones, match), así que no es negociable.
PYTHON_MINIMO = (3, 10)

# (especificación para pip, módulo que se importa, para qué sirve)
PAQUETES: list[tuple[str, str, str]] = [
    ("pymupdf>=1.23", "fitz", "Leer PDF y renderizar páginas"),
    ("pdf2image>=1.17", "pdf2image", "Convertir PDF a imagen (necesita Poppler)"),
    ("pytesseract>=0.3.10", "pytesseract", "Puente con Tesseract OCR"),
    ("Pillow>=10.0", "PIL", "Tratamiento de imágenes"),
    ("spacy>=3.7", "spacy", "Análisis lingüístico en español"),
    ("scikit-learn>=1.4", "sklearn", "Modelos de temas y similitud"),
    ("networkx>=3.2", "networkx", "Redes de entidades"),
    ("matplotlib>=3.8", "matplotlib", "Gráficos"),
    ("seaborn>=0.13", "seaborn", "Gráficos estadísticos"),
    ("pandas>=2.1", "pandas", "Tablas de datos"),
    ("openpyxl>=3.1", "openpyxl", "Exportar a Excel"),
    ("scipy>=1.12", "scipy", "Cálculo científico"),
    ("opencv-python-headless", "cv2", "Visión por computador (deskew, zonas)"),
    ("requests>=2.31", "requests", "Consultas a Wikidata y proveedores de IA"),
    ("torch>=2.0", "torch", "NER neuronal y Word2Vec"),
    ("transformers>=4.40", "transformers", "Modelo BERT de entidades"),
    ("sentence-transformers>=3.0", "sentence_transformers", "Búsqueda semántica"),
    ("faiss-cpu>=1.7", "faiss", "Índice vectorial"),
    ("lxml>=5.0", "lxml", "Validar TEI"),
    ("python-docx>=1.1", "docx", "Exportar a Word"),
    ("python-pptx>=0.6", "pptx", "Exportar a PowerPoint"),
    ("pyvis>=0.3", "pyvis", "Grafos interactivos"),
    ("folium>=0.15", "folium", "Mapas"),
]

# Paquetes que la app usa si están, pero cuya ausencia no impide trabajar.
PAQUETES_OPCIONALES: list[tuple[str, str, str]] = [
    ("kraken", "kraken", "OCR de manuscrito e impresión antigua"),
    ("SpeechRecognition>=3.10", "speech_recognition", "Dictado por voz"),
    ("sounddevice>=0.4", "sounddevice", "Captura de audio para el dictado"),
]

MODELO_SPACY = "es_core_news_sm"


@dataclass
class Requisito:
    """Un componente que Bashkar necesita, y en qué estado está."""

    clave: str
    nombre: str
    para_que: str
    instalado: bool
    detalle: str = ""
    # ¿Puede este proceso instalarlo por su cuenta y sin riesgo?
    puede_instalarse: bool = False
    # Qué escribir en una terminal si hay que hacerlo a mano.
    instruccion_manual: str = ""
    # Sin esto la app no arranca o pierde su función principal.
    obligatorio: bool = True

    @property
    def estado(self) -> str:
        if self.instalado:
            return "listo"
        return "falta" if self.obligatorio else "opcional"


@dataclass
class Diagnostico:
    """Resultado completo de revisar el equipo."""

    sistema: str
    requisitos: list[Requisito] = field(default_factory=list)
    congelado: bool = False

    @property
    def faltantes(self) -> list[Requisito]:
        return [r for r in self.requisitos if not r.instalado and r.obligatorio]

    @property
    def listo(self) -> bool:
        return not self.faltantes

    def por_clave(self, clave: str) -> Requisito | None:
        return next((r for r in self.requisitos if r.clave == clave), None)


# ── Ayudas ────────────────────────────────────────────────────────────────────

def esta_congelado() -> bool:
    """¿Corremos dentro de un .exe de PyInstaller?

    Determina si se puede llamar a pip. Ver la nota del encabezado: hacerlo
    congelado no es "poco elegante", es una bomba de fork.
    """
    return bool(getattr(sys, "frozen", False))


def _importable(modulo: str) -> bool:
    """¿Existe el módulo, sin llegar a importarlo?

    Se usa `find_spec` y no un `import` real porque importar torch o
    transformers tarda segundos y bloquearía la interfaz solo para responder
    "sí, está".
    """
    try:
        return importlib.util.find_spec(modulo) is not None
    except (ImportError, ValueError):
        return False


def _instruccion_binario(programa: str) -> str:
    """Cómo instalar un programa del sistema en la plataforma actual."""
    if plataforma.es_macos():
        return f"brew install {programa}"
    if plataforma.es_linux():
        paquete = "tesseract-ocr tesseract-ocr-spa" if programa == "tesseract" else programa
        return f"sudo apt install {paquete}"
    if programa == "tesseract":
        return "Descargar el instalador de https://github.com/UB-Mannheim/tesseract/wiki"
    return "Descargar el .zip de https://github.com/oschwartz10612/poppler-windows/releases"


def _tesseract_tiene_espanol(ruta_exe: str) -> bool:
    """¿Está el modelo de español? Sin él el OCR devuelve texto en inglés.

    Se mira PRIMERO el archivo `spa.traineddata` en las carpetas que conoce
    `plataforma.dirs_tessdata()`, y solo después se pregunta a Tesseract.

    El orden no es un capricho. `tesseract --list-langs` a secas solo lista lo
    que hay en su tessdata de instalación, y Bashkar usa además la carpeta
    `~/tessdata` —la que el usuario controla y donde se deja el español cuando
    no se tienen permisos de administrador—. Preguntando solo al binario, un
    equipo perfectamente configurado se reportaba como «falta el español»: una
    falsa alarma que manda a reinstalar algo que ya estaba.
    """
    for carpeta in plataforma.dirs_tessdata():
        try:
            if (carpeta / "spa.traineddata").is_file():
                return True
        except OSError:
            continue

    if not ruta_exe:
        return False
    try:
        salida = subprocess.run(
            [ruta_exe, "--list-langs"],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return "spa" in (salida.stdout or "").split()


# ── Diagnóstico ───────────────────────────────────────────────────────────────

def _requisito_python() -> Requisito:
    v = sys.version_info
    ok = v >= PYTHON_MINIMO
    return Requisito(
        clave="python",
        nombre=f"Python {PYTHON_MINIMO[0]}.{PYTHON_MINIMO[1]} o superior",
        para_que="Es el lenguaje en el que corre Bashkar",
        instalado=ok,
        detalle=f"Tienes Python {v.major}.{v.minor}.{v.micro}",
        puede_instalarse=False,
        instruccion_manual="Descargar desde https://www.python.org/downloads/",
    )


def _requisitos_paquetes(congelado: bool) -> list[Requisito]:
    salida: list[Requisito] = []
    for lista, obligatorio in ((PAQUETES, True), (PAQUETES_OPCIONALES, False)):
        for spec, modulo, para_que in lista:
            presente = _importable(modulo)
            nombre = spec.split(">=")[0].split("==")[0]
            salida.append(Requisito(
                clave=f"pip:{modulo}",
                nombre=nombre,
                para_que=para_que,
                instalado=presente,
                # Congelado NO se puede instalar nada con pip. Ver encabezado.
                puede_instalarse=not presente and not congelado,
                instruccion_manual=f"pip install {spec}",
                obligatorio=obligatorio,
            ))
    return salida


def _requisito_modelo_spacy(congelado: bool) -> Requisito:
    presente = _importable(MODELO_SPACY)
    return Requisito(
        clave="spacy_modelo",
        nombre=f"Modelo de español ({MODELO_SPACY})",
        para_que="Lematización, entidades y análisis sintáctico",
        instalado=presente,
        puede_instalarse=not presente and not congelado,
        instruccion_manual=f"python -m spacy download {MODELO_SPACY}",
    )


def _requisito_tesseract() -> Requisito:
    ruta = plataforma.buscar_tesseract()
    if not ruta:
        return Requisito(
            clave="tesseract",
            nombre="Tesseract OCR",
            para_que="Reconocer el texto de las páginas escaneadas",
            instalado=False,
            detalle="No se encontró en el sistema",
            instruccion_manual=_instruccion_binario("tesseract"),
        )
    if not _tesseract_tiene_espanol(ruta):
        instruccion = ("brew install tesseract-lang" if plataforma.es_macos()
                       else _instruccion_binario("tesseract"))
        return Requisito(
            clave="tesseract",
            nombre="Tesseract OCR — falta el español",
            para_que="Sin spa.traineddata el OCR lee el texto como si fuera inglés",
            instalado=False,
            detalle=f"Tesseract está en {ruta}, pero sin el idioma español",
            instruccion_manual=instruccion,
        )
    return Requisito(
        clave="tesseract",
        nombre="Tesseract OCR",
        para_que="Reconocer el texto de las páginas escaneadas",
        instalado=True,
        detalle=ruta,
    )


def _requisito_poppler() -> Requisito:
    ruta = plataforma.buscar_poppler()
    return Requisito(
        clave="poppler",
        nombre="Poppler (pdftoppm)",
        para_que="Convertir las páginas del PDF en imágenes para el OCR",
        instalado=bool(ruta),
        detalle=ruta or "No se encontró en el sistema",
        instruccion_manual=_instruccion_binario("poppler"),
    )


def diagnosticar() -> Diagnostico:
    """Revisa el equipo entero y devuelve qué hay y qué falta."""
    congelado = esta_congelado()
    requisitos = [_requisito_python()]
    requisitos += _requisitos_paquetes(congelado)
    requisitos.append(_requisito_modelo_spacy(congelado))
    requisitos.append(_requisito_tesseract())
    requisitos.append(_requisito_poppler())
    sistema = ("Windows" if plataforma.es_windows()
               else "macOS" if plataforma.es_macos()
               else "Linux" if plataforma.es_linux()
               else "desconocido")
    return Diagnostico(sistema=sistema, requisitos=requisitos, congelado=congelado)


# ── Instalación ───────────────────────────────────────────────────────────────

def instalar_requisito(req: Requisito, registrar=None) -> bool:
    """
    Instala lo que se pueda instalar solo. Devuelve True si quedó listo.

    `registrar` es una función que recibe líneas de texto para mostrar el
    progreso; el llamador decide si van a una consola o a una ventana.

    NUNCA llama a pip cuando el proceso está congelado, aunque el requisito
    diga que sí: es la última barrera antes de la bomba de fork.
    """
    def log(msg: str) -> None:
        if registrar:
            registrar(msg)

    if esta_congelado():
        log(f"No se puede instalar {req.nombre} desde la aplicación empaquetada.")
        log(f"Hazlo desde una terminal:  {req.instruccion_manual}")
        return False

    if not req.puede_instalarse:
        log(f"{req.nombre} hay que instalarlo a mano:  {req.instruccion_manual}")
        return False

    if req.clave == "spacy_modelo":
        cmd = [sys.executable, "-m", "spacy", "download", MODELO_SPACY]
    elif req.clave.startswith("pip:"):
        spec = req.instruccion_manual.replace("pip install ", "")
        cmd = [sys.executable, "-m", "pip", "install", "--no-warn-script-location", spec]
    else:
        log(f"{req.nombre} no se instala automáticamente:  {req.instruccion_manual}")
        return False

    log(f"Instalando {req.nombre}…")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except (OSError, subprocess.SubprocessError) as e:
        log(f"  falló: {e}")
        return False

    if proc.returncode == 0:
        log(f"  {req.nombre} quedó instalado.")
        return True

    # Solo la última línea del error: el volcado de pip es ilegible en una GUI.
    ultima = (proc.stderr or proc.stdout or "").strip().splitlines()
    log(f"  no se pudo: {ultima[-1] if ultima else 'error desconocido'}")
    return False


def comando_terminal_completo(diag: Diagnostico) -> str:
    """
    Un solo bloque con todo lo que falta, listo para pegar en la terminal.

    Cuando falta bastante, copiar un bloque y pegarlo es más rápido y menos
    frustrante que pulsar diez botones de instalación uno por uno.
    """
    lineas: list[str] = []
    pips = [r for r in diag.faltantes if r.clave.startswith("pip:")]
    if pips:
        specs = " ".join(r.instruccion_manual.replace("pip install ", "") for r in pips)
        lineas.append(f"pip install {specs}")
    for r in diag.faltantes:
        if not r.clave.startswith("pip:"):
            lineas.append(r.instruccion_manual)
    return "\n".join(lineas)


def ruta_python_del_sistema() -> str:
    """Un Python con pip utilizable, incluso si esto corre congelado.

    Congelado, `sys.executable` es el .exe. Aquí se busca un intérprete de
    verdad para poder DECIRLE al usuario con cuál ejecutar los comandos.
    """
    if not esta_congelado():
        return sys.executable
    for nombre in ("python3", "python"):
        hallado = shutil.which(nombre)
        if hallado:
            return hallado
    return "python"


def carpeta_de_la_app() -> Path:
    """Raíz del proyecto, funcione o no congelado."""
    if esta_congelado():
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent
