"""
core/ocr_kraken.py — Motor OCR Kraken para prensa histórica en español.

Kraken es un motor OCR especializado en documentos históricos con soporte
para scripts históricos, ligaduras y tipografías deterioradas.

Modelo recomendado: CATMuS-Print Large (DOI 10.5281/zenodo.10592716)
  - Entrenado en prensa ibérica y latinoamericana siglos XVI-XX
  - Precisión ~90-95% en prensa colombiana 1930s
  - Descarga: python -m kraken get 10.5281/zenodo.10592716

Instalación:
  pip install kraken
"""

import os
import sys
from pathlib import Path

# Ruta por defecto de modelos (relativa al directorio de la app)
_MODELOS_DIR = Path(__file__).parent.parent / "modelos"
_MODELO_DEFAULT = "catmus-print-large.mlmodel"

# ── Venv dedicado a Kraken (Python 3.12 + kraken instalado ahí) ──────────────
# Kraken arrastra torch, cuyas rutas internas son larguísimas; en Windows eso
# choca contra MAX_PATH, y por eso el venv vive en una raíz corta de D: y no
# junto al proyecto. En macOS y Linux ese límite no existe, así que ahí el sitio
# natural es el home del usuario, donde además no hacen falta permisos de
# administrador para crearlo.

def _candidatos_venv_kraken() -> list[Path]:
    from core import plataforma
    # La variable de entorno va primero: permite mover el venv sin tocar código,
    # que es justo lo que hace falta en un equipo ajeno.
    propia = os.environ.get("BASHKAR_KRAKEN_VENV")
    rutas = [Path(propia)] if propia else []
    if plataforma.es_windows():
        rutas += [Path("D:/kraken_env"), Path("C:/kraken_env")]
    else:
        rutas += [Path.home() / "kraken_env",
                  Path.home() / ".venvs" / "kraken",
                  Path("/opt/kraken_env")]
    return rutas


def _resolver_venv_kraken() -> Path:
    """Primer venv candidato que exista; si ninguno existe, el canónico.

    Devolver siempre algo (aunque no exista) mantiene el contrato anterior:
    `_KRAKEN_PYTHON.exists()` es la señal de "no está instalado" y los mensajes
    de error pueden nombrar la ruta esperada.
    """
    candidatos = _candidatos_venv_kraken()
    for ruta in candidatos:
        try:
            if ruta.is_dir():
                return ruta
        except OSError:      # unidad D: ausente o desconectada
            continue
    return candidatos[0]


def _bin_venv(venv: Path, nombre: str) -> Path:
    """Ubicación del ejecutable dentro de un venv, que difiere por sistema:
    Windows usa Scripts\\x.exe y el resto de los sistemas bin/x."""
    from core import plataforma
    if plataforma.es_windows():
        return venv / "Scripts" / plataforma.nombre_ejecutable(nombre)
    return venv / "bin" / nombre


_KRAKEN_VENV = _resolver_venv_kraken()
_KRAKEN_PYTHON = _bin_venv(_KRAKEN_VENV, "python")
_KRAKEN_EXE   = _bin_venv(_KRAKEN_VENV, "kraken")


def _python_kraken() -> str | None:
    """Retorna el ejecutable Python que tiene kraken disponible, o None si
    no hay ninguno usable. En un .exe congelado, sys.executable es el propio
    .exe: lanzarlo como subproceso solo abre una copia duplicada de la app
    en vez de ejecutar el código pedido (ver el incidente documentado en
    app.py::_auto_instalar), así que ahí NO se usa como último recurso."""
    if _KRAKEN_PYTHON.exists():
        return str(_KRAKEN_PYTHON)
    if getattr(sys, "frozen", False):
        return None
    return sys.executable


def _buscar_modelo(modelo_path: str | None = None) -> Path | None:
    """Busca el modelo Kraken en la ruta dada o en el directorio por defecto."""
    if modelo_path:
        p = Path(modelo_path)
        if p.exists():
            return p

    # Buscar en carpeta modelos/
    if _MODELOS_DIR.exists():
        candidatos = list(_MODELOS_DIR.glob("*.mlmodel"))
        if candidatos:
            # Preferir el que tenga "catmus" en el nombre
            for c in candidatos:
                if "catmus" in c.name.lower():
                    return c
            return candidatos[0]

    return None


def kraken_disponible() -> bool:
    """True si kraken está accesible (venv dedicado o instalación directa) Y hay modelo."""
    import subprocess
    python = _python_kraken()
    if python is None:
        return False
    try:
        r = subprocess.run(
            [python, "-c", "import kraken"],
            capture_output=True, timeout=10
        )
        return r.returncode == 0 and _buscar_modelo() is not None
    except Exception:
        return False


def ocr_kraken(ruta_imagen: str,
               modelo_path: str | None = None,
               binarizar: bool = True,
               timeout: int = 600) -> tuple[str, float]:
    """
    OCR con Kraken sobre una imagen de página.
    Ejecuta Kraken en el venv dedicado (Python 3.12) vía subproceso para evitar
    incompatibilidades con Python 3.14 / torch 2.x.

    Returns: (texto, confianza) donde confianza es 0.0–1.0.
    """
    import json
    import subprocess

    python = _python_kraken()
    if python is None:
        raise ImportError(
            "Kraken no está disponible en el .exe compilado (requiere el "
            f"venv dedicado en {_KRAKEN_VENV}, que no existe en este equipo).")

    # Verificar que kraken esté accesible
    chk = subprocess.run([python, "-c", "import kraken"],
                         capture_output=True, timeout=10)
    if chk.returncode != 0:
        raise ImportError(
            "Kraken no disponible en el entorno configurado.\n"
            "Venv: " + str(_KRAKEN_VENV)
        )

    ruta_modelo = _buscar_modelo(modelo_path)
    if ruta_modelo is None:
        raise FileNotFoundError(
            f"No hay modelos Kraken en {_MODELOS_DIR}.\n"
            "Descarga primero el modelo CATMuS-Print desde la UI."
        )

    # Script inline que ejecuta Kraken y devuelve JSON con texto+confianza
    script = f"""
import json, sys
try:
    from kraken import blla, rpred
    from kraken.lib import models
    import PIL.Image

    img = PIL.Image.open({repr(ruta_imagen)}).convert("RGB")
    if {repr(binarizar)}:
        try:
            from kraken.lib.segmentation import binarize
            img_proc = binarize(img)
        except Exception:
            img_proc = img.convert("L")
    else:
        img_proc = img

    seg = blla.segment(img_proc)
    model = models.load_any({repr(str(ruta_modelo))})
    pred_it = rpred.rpred(model, img_proc, seg)
    lineas, confs = [], []
    for r in pred_it:
        if r.prediction.strip():
            lineas.append(r.prediction)
            if hasattr(r, "confidences") and r.confidences:
                confs.append(sum(r.confidences) / len(r.confidences))
    texto = "\\n".join(lineas)
    conf = round(sum(confs) / len(confs) if confs else 0.82, 4)
    print(json.dumps({{"texto": texto, "confianza": conf}}))
except Exception as e:
    print(json.dumps({{"error": str(e)}}))
"""
    resultado = subprocess.run(
        [python, "-c", script],
        capture_output=True, text=True, timeout=timeout
    )
    if resultado.returncode != 0:
        raise RuntimeError(f"Error en subproceso Kraken:\n{resultado.stderr[:400]}")

    try:
        data = json.loads(resultado.stdout.strip().split("\n")[-1])
    except Exception:
        raise RuntimeError(f"Respuesta inesperada de Kraken:\n{resultado.stdout[:200]}")

    if "error" in data:
        raise RuntimeError(f"Kraken reportó error: {data['error']}")

    return data["texto"], data["confianza"]


def ocr_kraken_lote(rutas_imagenes: list[str],
                     modelo_path: str | None = None,
                     callback=None,
                     workers: int = 3,
                     timeout: int = 600) -> list[dict]:
    """
    Procesa un lote de imágenes con Kraken en paralelo.

    Args:
        rutas_imagenes: Lista de rutas a imágenes.
        modelo_path:    Ruta al modelo .mlmodel.
        callback:       callable(i, total, ruta, ok) — progreso.
        workers:        Subprocesos Kraken en paralelo (default 3).
                        Cada worker carga el modelo en RAM (~400 MB).
                        Con 7-8 GB RAM, 3 es seguro; subir a 4 si hay >12 GB.

    Returns:
        Lista de dicts en el mismo orden que rutas_imagenes:
        {ruta, texto, confianza, ok, error}
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    total = len(rutas_imagenes)
    if total == 0:
        return []

    # Resultados indexados para preservar el orden original
    resultados = [None] * total
    completados = threading.Lock()
    n_completados = [0]

    def _procesar(idx: int, ruta: str) -> tuple[int, dict]:
        try:
            texto, confianza = ocr_kraken(ruta, modelo_path, timeout=timeout)
            return idx, {"ruta": ruta, "texto": texto, "confianza": confianza,
                         "ok": True, "error": None}
        except Exception as e:
            return idx, {"ruta": ruta, "texto": "", "confianza": 0.0,
                         "ok": False, "error": str(e)}

    with ThreadPoolExecutor(max_workers=min(workers, total)) as pool:
        futures = {pool.submit(_procesar, i, r): i
                   for i, r in enumerate(rutas_imagenes)}
        for fut in as_completed(futures):
            idx, res = fut.result()
            resultados[idx] = res
            with completados:
                n_completados[0] += 1
                n = n_completados[0]
            if callback:
                callback(n, total, res["ruta"], res["ok"])

    return resultados


def descargar_modelo_catmus(callback=None) -> str:
    """
    Descarga el modelo CATMuS-Print Large si no está presente.
    Retorna la ruta del modelo descargado.
    """
    try:
        import subprocess
        import sys
    except ImportError:
        raise ImportError("subprocess no disponible")

    _MODELOS_DIR.mkdir(parents=True, exist_ok=True)
    modelo_existente = _buscar_modelo()
    if modelo_existente:
        return str(modelo_existente)

    if callback:
        callback("Descargando modelo CATMuS-Print Large (~300 MB)...")

    kraken_exe = str(_KRAKEN_EXE) if _KRAKEN_EXE.exists() else "kraken"
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    resultado = subprocess.run(
        [kraken_exe, "get", "10.5281/zenodo.10592716"],
        capture_output=True, text=True, cwd=str(_MODELOS_DIR), env=env
    )

    if resultado.returncode != 0:
        raise RuntimeError(
            f"Error descargando modelo Kraken:\n{resultado.stderr}"
        )

    # kraken get descarga a AppData/Local/htrmopo — copiar a modelos/
    import shutil
    htrmopo_base = Path(os.environ.get("LOCALAPPDATA", "")) / "htrmopo" / "htrmopo"
    encontrados = list(htrmopo_base.glob("**/*.mlmodel")) if htrmopo_base.exists() else []
    if encontrados:
        origen = max(encontrados, key=lambda p: p.stat().st_mtime)
        destino = _MODELOS_DIR / origen.name
        shutil.copy2(str(origen), str(destino))
        if callback:
            callback(f"Modelo copiado a modelos/{origen.name}")

    modelo = _buscar_modelo()
    if modelo is None:
        raise RuntimeError("Modelo descargado pero no encontrado en modelos/")

    return str(modelo)
