"""
core/plataforma.py — Capa única para todo lo que depende del sistema operativo.

Bashkar Station nació en Windows y arrastraba las decisiones del sistema
repartidas por el monolito: `os.startfile`, rutas de "Program Files", carpetas
de datos con letra de unidad. Cada una de esas líneas es un punto donde la app
se rompe al arrancar en macOS o Linux, y son difíciles de encontrar porque
están mezcladas con la lógica editorial.

Este módulo las concentra en un solo sitio para que el resto del código pida
"abre esto" o "dime dónde está tesseract" sin saber en qué sistema corre.

Reglas de la casa:
  · SOLO biblioteca estándar. Si este módulo necesitara una dependencia
    externa, dejaría de poder usarse en el arranque, que es justo cuando hace
    falta (antes de que se resuelvan pytesseract, pdf2image, etc.).
  · Ninguna función lanza por culpa del sistema. Un OCR sin tesseract debe
    avisar en la interfaz, no reventar el hilo.
  · La detección de sistema se resuelve en cada llamada, no en una constante
    de módulo: los tests recorren los caminos de macOS y Linux desde Windows
    simulando el sistema, y una constante congelada en el import los volvería
    imposibles de verificar hasta tener el hardware delante.

Sobre la simulación en tests: manda `platform.system()`, que es lo que ya
usaba el resto del proyecto; `sys.platform` solo se consulta como respaldo si
el primero viene vacío (ocurre en algunos entornos empaquetados). Al simular
un sistema conviene fijar los dos para que no queden incoherentes entre sí.
"""

import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

__all__ = [
    "es_windows", "es_macos", "es_linux",
    "abrir_en_sistema",
    "dir_datos_usuario", "dir_config_usuario", "dir_temp_ascii",
    "nombre_ejecutable", "buscar_binario",
    "buscar_tesseract", "buscar_poppler", "dir_poppler", "dirs_tessdata",
]


# ── Identificación del sistema ────────────────────────────────────────────────

def _sistema() -> str:
    """Devuelve "windows", "macos", "linux" u "otro"."""
    try:
        s = (platform.system() or "").lower()
    except Exception:      # platform.system() puede fallar en entornos exóticos
        s = ""
    if not s:
        # Respaldo: sys.platform siempre trae algo, incluso congelado.
        p = sys.platform.lower()
        s = {"win32": "windows", "cygwin": "windows", "darwin": "macos"}.get(p, p)
    if s.startswith("win") or s == "cygwin":
        return "windows"
    if s in ("darwin", "macos"):
        return "macos"
    if s.startswith("linux"):
        return "linux"
    return "otro"


def es_windows() -> bool:
    return _sistema() == "windows"


def es_macos() -> bool:
    return _sistema() == "macos"


def es_linux() -> bool:
    # Los BSD y demás Unix caen en "otro" y siguen el camino POSIX en el resto
    # del módulo; aquí se responde con precisión para no mentirle al llamador.
    return _sistema() == "linux"


def _es_posix() -> bool:
    """Todo lo que no es Windows comparte convenciones POSIX de rutas y `open`."""
    return not es_windows()


# ── Abrir archivos con la aplicación predeterminada ───────────────────────────

def abrir_en_sistema(ruta) -> bool:
    """
    Abre `ruta` (archivo o carpeta) con la aplicación predeterminada del sistema.

    Sustituye a `os.startfile`, que solo existe en Windows: en el resto de los
    sistemas ni siquiera es un atributo del módulo `os`, así que el código que
    lo llamaba fallaba con AttributeError antes de poder mostrar un aviso.

    Devuelve True si el visor arrancó. Nunca lanza: abrir un PDF de cortesía
    al terminar una exportación no debe poder tumbar el hilo que acaba de
    generar el archivo.
    """
    ruta = str(ruta)
    try:
        if es_windows():
            # getattr y no os.startfile directo: en macOS/Linux el atributo no
            # existe, y así el camino simulado en tests devuelve False limpio.
            startfile = getattr(os, "startfile", None)
            if startfile is None:
                return False
            startfile(ruta)
            return True

        # macOS trae `open`; el resto de los Unix usan `xdg-open` de freedesktop.
        cmd = ["open", ruta] if es_macos() else ["xdg-open", ruta]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
    except Exception:
        # FileNotFoundError si el comando no está (Linux mínimo sin xdg-utils),
        # OSError si la ruta es inválida. En ambos casos: no se pudo abrir.
        return False

    try:
        # `open` de macOS delega y sale enseguida; `xdg-open` a veces hace exec
        # del visor y se queda vivo mientras el usuario mira el archivo. Por eso
        # NO se usa subprocess.run(timeout=...): al vencer el plazo mataría al
        # visor. Aquí se espera un poco y, si sigue vivo, eso ES el éxito.
        return proc.wait(timeout=5) == 0
    except subprocess.TimeoutExpired:
        return True
    except Exception:
        return False


# ── Carpetas de usuario ───────────────────────────────────────────────────────

def dir_datos_usuario(nombre_app: str) -> Path:
    """
    Carpeta donde la app guarda datos propios (cachés, índices, modelos).

    Cada sistema tiene su convención y saltársela tiene consecuencias reales:
    en macOS lo que no vive bajo ~/Library queda fuera de Time Machine y de la
    limpieza del sistema; en Linux, escribir en ~/ a pelo ensucia el home del
    usuario y contradice XDG.

    Devuelve la ruta; NO la crea. Crear directorios es un efecto secundario que
    corresponde a quien va a escribir, no a quien pregunta dónde escribir.
    """
    if es_windows():
        # LOCALAPPDATA y no APPDATA: son datos pesados que no deben viajar en
        # los perfiles móviles de dominio.
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    elif es_macos():
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / nombre_app


def dir_config_usuario(nombre_app: str) -> Path:
    """
    Carpeta de configuración del usuario (preferencias, rutas guardadas).

    Difiere de `dir_datos_usuario` donde el sistema distingue ambas cosas:
      · Windows: APPDATA (móvil) sí acompaña al usuario entre equipos del
        dominio, y eso es exactamente lo que se quiere de una preferencia.
      · Linux: XDG separa config de datos por diseño (~/.config vs ~/.local/share).
      · macOS: NO las separa. ~/Library/Preferences es territorio de los .plist
        que gestiona el propio sistema, así que la configuración de una app de
        terceros va también en Application Support; devolver lo mismo aquí es
        deliberado, no un descuido.
    """
    if es_windows():
        base = (os.environ.get("APPDATA")
                or os.environ.get("LOCALAPPDATA")
                or str(Path.home() / "AppData" / "Roaming"))
    elif es_macos():
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / nombre_app


def dir_temp_ascii() -> str | None:
    """
    Carpeta temporal garantizada sin caracteres no-ASCII, o None si no hace falta.

    FAISS y algunas extensiones nativas que usa el análisis visual abren rutas
    con APIs de bytes y fallan si el nombre del usuario de Windows lleva tildes
    o eñes — cosa habitual aquí. C:\\Windows\\Temp siempre es ASCII y evita el
    problema. En macOS y Linux la temporal por defecto ya es /tmp o /var/folders,
    ambas ASCII, así que se devuelve None para que `tempfile` use la suya.
    """
    if not es_windows():
        return None
    candidata = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Temp"
    return str(candidata) if candidata.is_dir() else None


# ── Búsqueda de binarios externos ─────────────────────────────────────────────

def nombre_ejecutable(nombre: str) -> str:
    """Añade la extensión .exe solo donde el sistema la exige."""
    if es_windows() and not nombre.lower().endswith(".exe"):
        return nombre + ".exe"
    return nombre


def _dirs_binarios_tipicos() -> list[Path]:
    """
    Sitios donde cada sistema deja los programas instalados a mano.

    No es una lista cosmética: en macOS, una app lanzada desde Finder hereda un
    PATH mínimo (/usr/bin:/bin:/usr/sbin:/sbin) que NO incluye Homebrew, así
    que `shutil.which` no ve tesseract aunque el usuario lo tenga instalado y
    funcionando en su terminal. Sin estas rutas, la app parecería no tener OCR.
    """
    dirs: list[Path] = []
    if es_windows():
        for var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "LOCALAPPDATA"):
            valor = os.environ.get(var)
            if valor:
                dirs.append(Path(valor))
        # Respaldo si las variables no están (servicios, entornos recortados).
        dirs += [Path(r"C:\Program Files"), Path(r"C:\Program Files (x86)")]
        local = os.environ.get("LOCALAPPDATA")
        if local:
            dirs.append(Path(local) / "Programs")
    else:
        if es_macos():
            # /opt/homebrew es Apple Silicon; /usr/local, los Mac Intel y las
            # compilaciones manuales; /opt/local, MacPorts.
            dirs += [Path("/opt/homebrew/bin"), Path("/usr/local/bin"),
                     Path("/opt/local/bin")]
        else:
            # Linux: los paquetes de la distro, luego snap y los flatpak de usuario.
            dirs += [Path("/usr/local/bin"), Path("/usr/bin"), Path("/bin"),
                     Path("/snap/bin"), Path("/var/lib/flatpak/exports/bin")]
        dirs += [Path("/usr/bin"), Path("/bin"), Path.home() / ".local" / "bin"]
    # Sin duplicados y conservando el orden de preferencia.
    vistos: set[str] = set()
    unicos: list[Path] = []
    for d in dirs:
        clave = str(d).lower()
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(d)
    return unicos


def _ejecutable_en(base: Path, nombre: str) -> str:
    """Busca `nombre` dentro de `base` sin recorrer el árbol entero."""
    exe = nombre_ejecutable(nombre)
    # Los tres esqueletos habituales: suelto en la carpeta, en su propio
    # directorio de producto, o bajo el bin/ de ese directorio.
    for candidato in (base / exe,
                      base / nombre / exe,
                      base / nombre / "bin" / exe):
        try:
            if candidato.is_file():
                return str(candidato)
        except OSError:
            # Unidades de red desconectadas o permisos: no es un error de la app.
            continue
    return ""


def buscar_binario(nombre: str, candidatos_extra: Iterable = ()) -> str:
    """
    Ruta completa al ejecutable `nombre`, o "" si no aparece.

    Orden: PATH primero (respeta lo que el usuario configuró), después las
    rutas que pase el llamador y por último los sitios típicos del sistema.

    `candidatos_extra` admite tanto la ruta del ejecutable como la carpeta que
    lo contiene, porque los archivos de configuración del proyecto guardan
    indistintamente una u otra según quién los haya escrito.
    """
    try:
        hallado = shutil.which(nombre)
    except Exception:
        hallado = None
    if hallado:
        return hallado

    exe = nombre_ejecutable(nombre)
    for extra in candidatos_extra:
        if not extra:
            continue
        p = Path(extra)
        try:
            if p.is_file():
                return str(p)
            if p.is_dir():
                directo = p / exe
                if directo.is_file():
                    return str(directo)
                en_bin = p / "bin" / exe
                if en_bin.is_file():
                    return str(en_bin)
        except OSError:
            continue

    for base in _dirs_binarios_tipicos():
        encontrado = _ejecutable_en(base, nombre)
        if encontrado:
            return encontrado
    return ""


# ── Tesseract ─────────────────────────────────────────────────────────────────

def _candidatos_tesseract() -> list[Path]:
    if es_windows():
        # El instalador oficial de UB-Mannheim ofrece "para todos los usuarios"
        # (Program Files) o "solo para mí" (LOCALAPPDATA\Programs); ambos casos
        # aparecen en los equipos donde ya corre Bashkar.
        rutas = [Path(r"C:\Program Files\Tesseract-OCR"),
                 Path(r"C:\Program Files (x86)\Tesseract-OCR")]
        local = os.environ.get("LOCALAPPDATA")
        if local:
            rutas += [Path(local) / "Programs" / "Tesseract-OCR",
                      Path(local) / "Tesseract-OCR"]
        return rutas
    if es_macos():
        # `brew install tesseract` deja el binario en el bin del prefijo.
        return [Path("/opt/homebrew/bin"), Path("/usr/local/bin"), Path("/opt/local/bin")]
    return [Path("/usr/bin"), Path("/usr/local/bin"), Path("/snap/bin")]


def buscar_tesseract() -> str:
    """Ruta completa al ejecutable de Tesseract, o "" si no está instalado."""
    return buscar_binario("tesseract", _candidatos_tesseract())


def dirs_tessdata() -> list[Path]:
    """
    Carpetas donde puede vivir tessdata/ (los .traineddata de cada idioma).

    Tesseract sabe encontrarlas solo cuando lo instaló el gestor de paquetes,
    pero en Windows con instalación portable —y en cualquier sistema cuando el
    usuario descarga spa.traineddata a mano— hay que fijarle TESSDATA_PREFIX.
    La carpeta del home va primero: es la que el usuario controla y la que se
    usa para reemplazar un modelo por otro sin permisos de administrador.
    """
    rutas: list[Path] = [Path.home() / "tessdata"]
    if es_windows():
        rutas += [Path(r"C:\Program Files\Tesseract-OCR\tessdata"),
                  Path(r"C:\Program Files (x86)\Tesseract-OCR\tessdata")]
        local = os.environ.get("LOCALAPPDATA")
        if local:
            rutas.append(Path(local) / "Programs" / "Tesseract-OCR" / "tessdata")
    elif es_macos():
        # Homebrew versiona el directorio (…/tesseract/5.3.4/share/tessdata) y
        # deja un enlace estable en share/tessdata: se usa el enlace.
        rutas += [Path("/opt/homebrew/share/tessdata"),
                  Path("/usr/local/share/tessdata"),
                  Path("/opt/local/share/tessdata")]
    else:
        # Debian/Ubuntu cuelgan tessdata de la versión del paquete; el glob
        # cubre 4.00, 5, etc. sin cablear ninguna.
        rutas += [Path("/usr/share/tesseract-ocr/5/tessdata"),
                  Path("/usr/share/tesseract-ocr/4.00/tessdata"),
                  Path("/usr/share/tessdata"),
                  Path("/usr/local/share/tessdata"),
                  Path("/usr/share/tesseract-ocr/tessdata")]
    return rutas


# ── Poppler (pdftoppm, que usa pdf2image) ─────────────────────────────────────

def _candidatos_poppler() -> list[Path]:
    if es_windows():
        # Poppler para Windows no tiene instalador: se descomprime un .zip
        # donde caiga, y el binario queda enterrado varios niveles
        # (poppler-24.02\Library\bin\pdftoppm.exe). Por eso estas bases se
        # recorren en profundidad más abajo, no solo en su primer nivel.
        rutas = [Path(r"C:\poppler"),
                 Path(r"C:\Program Files\poppler"),
                 Path(r"C:\Program Files (x86)\poppler")]
        for var in ("LOCALAPPDATA", "ProgramFiles"):
            valor = os.environ.get(var)
            if valor:
                rutas.append(Path(valor) / "poppler")
        return rutas
    if es_macos():
        # `brew install poppler`: binarios sueltos en el bin del prefijo.
        return [Path("/opt/homebrew/bin"), Path("/usr/local/bin"), Path("/opt/local/bin")]
    return [Path("/usr/bin"), Path("/usr/local/bin"), Path("/snap/bin")]


def buscar_poppler() -> str:
    """
    Ruta completa al ejecutable `pdftoppm`, o "" si no aparece.

    Se busca pdftoppm y no "poppler" porque poppler no instala un ejecutable
    con su propio nombre: es una colección de utilidades, y pdftoppm es la que
    pdf2image invoca para rasterizar.
    """
    hallado = buscar_binario("pdftoppm", _candidatos_poppler())
    if hallado:
        return hallado
    if not es_windows():
        return ""
    # Último recurso solo en Windows: recorrer en profundidad las bases del zip
    # descomprimido. Es caro, así que va después de todo lo demás y se limita a
    # carpetas que ya se llaman "poppler" — nunca a Program Files entero.
    for base in _candidatos_poppler():
        try:
            if not base.is_dir():
                continue
            for hit in base.glob("**/pdftoppm.exe"):
                return str(hit)
        except OSError:
            continue
    return ""


def dir_poppler() -> str:
    """
    Carpeta que pdf2image espera en su parámetro `poppler_path`, o "".

    pdf2image no quiere el ejecutable sino el directorio que lo contiene, y
    solo hace falta pasárselo cuando poppler no está en el PATH.
    """
    exe = buscar_poppler()
    return str(Path(exe).parent) if exe else ""
