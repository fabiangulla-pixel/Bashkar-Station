"""core/user_prefs.py — Preferencias de usuario persistentes entre sesiones.

Sigue la misma convención de core/zone_labeler.py (tipos_zona.json):
JSON simple en ~/.bashkar/, sin dependencias, tolerante a archivo ausente
o corrupto (nunca lanza, siempre degrada a valores por defecto).

Usado por: verificador OCR (umbral de confianza), diálogo de exportación
("abrir al terminar"), pantalla de inicio ("no mostrar al inicio").

CREDENCIALES
------------
Las API keys viven en un archivo APARTE (`credenciales.json`), NUNCA dentro del
archivo `.bashkar` del proyecto. La razón es concreta: los proyectos se guardan
en carpetas que se sincronizan a la nube y se comparten (jurados, coautores,
respaldos), así que una clave escrita ahí se filtra sin que nadie lo note. El
directorio del usuario no se comparte junto con un proyecto.

Esto NO es cifrado: es aislamiento. La clave sigue en claro en el disco del
usuario, igual que hacen `~/.aws/credentials` o `~/.netrc`. Lo que evita es que
viaje dentro de un entregable.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

PREFS_PATH = Path.home() / ".bashkar" / "prefs.json"
CREDENCIALES_PATH = Path.home() / ".bashkar" / "credenciales.json"

# Proveedores cuya "clave" es en realidad una URL local (Ollama, LM Studio):
# no son secretos y pueden viajar dentro del proyecto sin riesgo.
_PREFIJOS_NO_SECRETOS = ("http://", "https://")


def cargar_prefs() -> dict:
    """Carga todas las preferencias. Nunca lanza: archivo ausente o
    corrupto devuelve dict vacío."""
    if not PREFS_PATH.exists():
        return {}
    try:
        return json.loads(PREFS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def guardar_pref(clave: str, valor) -> None:
    """Persiste una preferencia individual (mezcla con las existentes)."""
    prefs = cargar_prefs()
    prefs[clave] = valor
    PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREFS_PATH.write_text(
        json.dumps(prefs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def obtener_pref(clave: str, default=None):
    """Lee una preferencia individual, o `default` si no existe."""
    return cargar_prefs().get(clave, default)


# ── Credenciales ─────────────────────────────────────────────────────────────

def es_secreto(valor) -> bool:
    """¿Este valor es una credencial de verdad, o una URL local inofensiva?

    Ollama y LM Studio se configuran con una URL (`http://localhost:11434`),
    no con una clave. Distinguirlos evita tratar una URL como secreto y, sobre
    todo, evita perderla al limpiar un proyecto.
    """
    v = str(valor or "").strip()
    if not v:
        return False
    return not v.lower().startswith(_PREFIJOS_NO_SECRETOS)


def cargar_credenciales() -> dict:
    """Claves por proveedor guardadas en el directorio del usuario.

    Nunca lanza: archivo ausente o corrupto devuelve dict vacío.
    """
    if not CREDENCIALES_PATH.exists():
        return {}
    try:
        datos = json.loads(CREDENCIALES_PATH.read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else {}
    except Exception:
        return {}


def guardar_credenciales(claves: dict) -> None:
    """Persiste las claves por proveedor, mezclando con las ya guardadas.

    Un valor vacío BORRA la entrada: así el usuario puede quitar una clave
    desde la interfaz sin editar el JSON a mano.
    """
    actuales = cargar_credenciales()
    for proveedor, valor in (claves or {}).items():
        v = str(valor or "").strip()
        if v:
            actuales[proveedor] = v
        else:
            actuales.pop(proveedor, None)

    CREDENCIALES_PATH.parent.mkdir(parents=True, exist_ok=True)
    CREDENCIALES_PATH.write_text(
        json.dumps(actuales, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # Restringir a solo-el-dueño donde el sistema lo respete (POSIX). En Windows
    # chmod apenas controla el atributo de solo-lectura, así que esto es un
    # refuerzo, no la defensa principal: la defensa es no escribirlas nunca en
    # el archivo del proyecto.
    try:
        os.chmod(CREDENCIALES_PATH, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass


def separar_secretos(api_keys: dict) -> tuple[dict, dict]:
    """Parte un dict de claves en (secretos, no_secretos).

    Los no-secretos (URLs de Ollama/LM Studio) sí pueden guardarse dentro del
    proyecto; los secretos van al directorio del usuario.
    """
    secretos: dict = {}
    publicos: dict = {}
    for proveedor, valor in (api_keys or {}).items():
        if es_secreto(valor):
            secretos[proveedor] = valor
        elif str(valor or "").strip():
            publicos[proveedor] = valor
    return secretos, publicos
