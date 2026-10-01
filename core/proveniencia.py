"""
core/proveniencia.py — Manifiestos de ejecución y de exportación.

Un resultado de Bashkar solo es auditable si se puede decir con qué se produjo:
qué corpus (y en qué versión), con qué commit del software, qué intérprete,
qué versiones de las librerías y qué programas externos. Este módulo junta esos
datos en un JSON que viaja junto al producto.

Dos usos:

  · ``manifiesto_ejecucion(...)``: una corrida completa del pipeline o de un
    benchmark. Se escribe con ``escribir_manifiesto``.
  · ``escribir_manifiesto_exportacion(ruta, ...)``: deja
    ``<archivo>.proveniencia.json`` al lado de cualquier exportación.

Principio: lo que no se sabe se declara como desconocido, nunca se rellena.
Un campo ``"commit": "desconocido"`` es información; un commit inventado no.
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DESCONOCIDO = "desconocido"
VERSION_MANIFIESTO = 1

_RAIZ = Path(__file__).resolve().parent.parent

# Paquetes cuya versión cambia resultados: OCR, NLP, modelos, métricas.
PAQUETES_RELEVANTES = (
    "pymupdf", "pytesseract", "Pillow", "opencv-python-headless", "spacy",
    "es_core_news_sm", "transformers", "sentence-transformers", "torch",
    "faiss-cpu", "scikit-learn", "numpy", "pandas", "spylls", "kraken",
    "anthropic", "lxml",
)


@functools.lru_cache(maxsize=1)
def commit_software() -> str:
    """Commit del código que está corriendo.

    Orden: ``BASHKAR_COMMIT`` → ``_build_info.json`` (lo escribe el build del
    .exe, donde no hay git) → ``git rev-parse`` → desconocido. Si el árbol
    tiene cambios sin commitear se marca con ``+sucio``: un commit limpio y uno
    con ediciones locales no producen lo mismo.
    """
    env = os.environ.get("BASHKAR_COMMIT", "").strip()
    if env:
        return env
    for base in (_RAIZ, Path(getattr(sys, "_MEIPASS", _RAIZ))):
        info = base / "_build_info.json"
        if info.exists():
            try:
                return json.loads(info.read_text(encoding="utf-8")).get("commit", DESCONOCIDO)
            except (OSError, ValueError):
                pass
    try:
        r = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=_RAIZ,
                           capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return DESCONOCIDO
        sha = r.stdout.strip()
        s = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                           cwd=_RAIZ, capture_output=True, text=True, timeout=10)
        return sha + ("+sucio" if s.stdout.strip() else "")
    except (OSError, subprocess.SubprocessError):
        return DESCONOCIDO


def version_app() -> str:
    """APP_VERSION sin importar la GUI (importarla abre Tk).

    Vive en gui_comun.py desde la sesión 71; app.py se mira por compatibilidad
    con árboles anteriores."""
    for archivo in ("gui_comun.py", "app.py"):
        try:
            for linea in (_RAIZ / archivo).read_text(encoding="utf-8").splitlines():
                if linea.startswith("APP_VERSION"):
                    return linea.split("=", 1)[1].strip().strip("\"'")
        except OSError:
            continue
    return DESCONOCIDO


def versiones_paquetes(nombres=PAQUETES_RELEVANTES) -> dict[str, str]:
    import importlib.metadata as md
    out = {}
    for n in nombres:
        try:
            out[n] = md.version(n)
        except md.PackageNotFoundError:
            out[n] = "no instalado"
    return out


def anonimizar_ruta(texto: str) -> str:
    """Reemplaza la carpeta personal por ``~`` para no filtrar el usuario."""
    home = str(Path.home())
    if not texto or not home:
        return texto
    for variante in {home, home.replace("\\", "/")}:
        texto = texto.replace(variante, "~")
    return texto


def componentes_externos() -> dict[str, dict]:
    """Programas y modelos fuera de pip, con las MISMAS rutas que usa el runtime.

    Reutiliza ``core.requisitos``: si el manifiesto y el diagnóstico miraran en
    sitios distintos podrían contradecirse (fallo ya visto con el diccionario).
    """
    out: dict[str, dict] = {}
    try:
        from core import requisitos
        for r in requisitos.diagnosticar().requisitos:
            if r.clave.startswith("pip:"):
                continue
            out[r.clave] = {"instalado": r.instalado,
                            "detalle": anonimizar_ruta(r.detalle)}
    except Exception as e:  # el manifiesto no debe tumbar una exportación
        out["_error"] = {"instalado": False, "detalle": f"{type(e).__name__}: {e}"}
    try:
        from core.spell_corrector import ruta_diccionario_es
        ruta = ruta_diccionario_es()
        out["diccionario_es"] = {"instalado": bool(ruta), "detalle": anonimizar_ruta(str(ruta or ""))}
    except Exception:
        out["diccionario_es"] = {"instalado": False, "detalle": DESCONOCIDO}
    return out


def entorno(incluir_externos: bool = True) -> dict:
    datos = {
        "bashkar_version": version_app(),
        "commit": commit_software(),
        "python": platform.python_version(),
        "sistema": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "congelado": bool(getattr(sys, "frozen", False)),
        "paquetes": versiones_paquetes(),
    }
    if incluir_externos:
        datos["componentes_externos"] = componentes_externos()
    return datos


def hash_archivos(rutas) -> str:
    """SHA-256 estable de un conjunto de archivos (nombre relativo + contenido).

    Sirve como "versión del corpus": si cambia una sola página, cambia el hash.
    """
    rutas = sorted(Path(r) for r in rutas)
    if not rutas:
        return DESCONOCIDO
    base = Path(os.path.commonpath([str(r.parent) for r in rutas]))
    h = hashlib.sha256()
    for r in rutas:
        h.update(r.relative_to(base).as_posix().encode("utf-8") + b"\0")
        with open(r, "rb") as f:
            for bloque in iter(lambda: f.read(1 << 20), b""):
                h.update(bloque)
        h.update(b"\0")
    return h.hexdigest()


def hash_texto(textos: dict[str, str]) -> str:
    """Igual que ``hash_archivos`` pero sobre textos en memoria (clave → texto)."""
    if not textos:
        return DESCONOCIDO
    h = hashlib.sha256()
    for k in sorted(textos):
        h.update(k.encode("utf-8") + b"\0" + (textos[k] or "").encode("utf-8") + b"\0")
    return h.hexdigest()


def manifiesto_ejecucion(*, tipo: str, corpus: dict, configuracion: dict | None = None,
                         modelos: dict | None = None, metricas: dict | None = None,
                         advertencias: list[str] | None = None,
                         etapas_omitidas: list[str] | None = None) -> dict:
    """Arma el manifiesto de una ejecución.

    ``corpus`` debe traer al menos ``id``; se recomienda ``version`` (p. ej. el
    resultado de ``hash_archivos``) y ``n_paginas``.
    """
    if "id" not in corpus:
        raise ValueError("el corpus del manifiesto necesita un 'id'")
    return {
        "manifiesto_version": VERSION_MANIFIESTO,
        "tipo": tipo,
        "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
        "corpus": {"version": DESCONOCIDO, **corpus},
        "configuracion": configuracion or {},
        "modelos": modelos or {},
        "entorno": entorno(),
        "metricas": metricas or {},
        "advertencias": advertencias or [],
        "etapas_omitidas": etapas_omitidas or [],
    }


def escribir_manifiesto(manifiesto: dict, destino) -> Path:
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    return destino


AVISO_LICENCIA_CORPUS = (
    "El código de Bashkar Station se distribuye bajo su propia licencia (ver "
    "LICENSE). El corpus procesado y los modelos tienen licencias propias y NO "
    "se redistribuyen con el software; verificar derechos antes de publicar "
    "este archivo."
)


def escribir_manifiesto_exportacion(ruta_producto, *, formato: str,
                                    corpus: dict | None = None,
                                    fuentes: list[str] | None = None,
                                    advertencias: list[str] | None = None,
                                    extra: dict | None = None) -> Path:
    """Escribe ``<producto>.proveniencia.json`` junto a una exportación.

    Nunca lanza: una exportación exitosa no debe fallar por su manifiesto.
    Devuelve la ruta escrita (o la que se intentó).
    """
    ruta_producto = Path(ruta_producto)
    if ruta_producto.is_dir():
        destino = ruta_producto / "proveniencia.json"
    else:
        destino = ruta_producto.with_name(ruta_producto.name + ".proveniencia.json")
    try:
        advert = list(advertencias or [])
        if not fuentes:
            advert.append("No se registró la lista de fuentes de esta exportación.")
        datos = {
            "manifiesto_version": VERSION_MANIFIESTO,
            "producto": ruta_producto.name,
            "formato": formato,
            "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
            "corpus": {"id": DESCONOCIDO, "version": DESCONOCIDO, **(corpus or {})},
            "fuentes": fuentes or [],
            "entorno": entorno(incluir_externos=False),
            "advertencias": advert,
            "licencias": AVISO_LICENCIA_CORPUS,
            **(extra or {}),
        }
        escribir_manifiesto(datos, destino)
    except Exception:
        pass
    return destino


def _fuentes_de(valor) -> list[str]:
    """Extrae identificadores de fuente de articulos / paginas, sin inventar."""
    fuentes = []
    if isinstance(valor, dict):
        valor = list(valor.values())
    for item in valor or []:
        if not isinstance(item, dict):
            continue
        partes = [str(item[k]) for k in ("numero", "id", "pagina", "titulo")
                  if item.get(k) not in (None, "")]
        if not partes and item.get("img_path"):
            partes = [Path(str(item["img_path"])).name]
        if partes:
            fuentes.append(" · ".join(partes))
    return fuentes


def con_proveniencia(formato: str, destino: str, fuentes: str | None = None):
    """Decorador para exportadores: escribe el manifiesto al terminar.

    ``destino`` y ``fuentes`` son NOMBRES de parámetros de la función
    decorada. Si el destino es una carpeta, el manifiesto va dentro como
    ``proveniencia.json``. Un fallo del manifiesto nunca rompe la exportación.
    """
    import inspect

    def deco(fn):
        firma = inspect.signature(fn)

        @functools.wraps(fn)
        def envoltura(*args, **kwargs):
            resultado = fn(*args, **kwargs)
            try:
                ligados = firma.bind(*args, **kwargs)
                ligados.apply_defaults()
                ruta = Path(ligados.arguments[destino])
                lista = _fuentes_de(ligados.arguments.get(fuentes)) if fuentes else []
                escribir_manifiesto_exportacion(
                    ruta, formato=formato, fuentes=lista,
                    extra={"exportador": f"{fn.__module__}.{fn.__name__}"})
            except Exception:
                pass
            return resultado
        return envoltura
    return deco
