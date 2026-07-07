"""
instalar.py — Instalador inicial de Bashkar Station v11
Ejecutar UNA SOLA VEZ antes de lanzar la app.

CAMBIOS v11:
  · Nuevos componentes: transformers, torch, sentence-transformers, faiss-cpu
  · Modelo NER: mrm8488/bert-spanish-cased-finetuned-ner (descarga automática)
  · Embeddings semánticos: paraphrase-multilingual-MiniLM-L12-v2
  · Búsqueda vectorial FAISS (faiss-cpu)
  · OCR local Kraken (opcional, requiere kraken + modelo CATMuS-Print)
  · OCR visual Ollama (opcional, requiere Ollama + qwen2.5vl instalado)
  · Exportación ALTO XML v4 (sin dependencias externas)
  · Entity linking a Wikidata (sin dependencias externas, caché local)
  · Precarga de modelos IA al terminar la instalación

Herencia v1.1:
  · Resuelve conflicto numpy / opencv-python-headless
  · Tesseract en Windows: winget → descarga directa .exe → instrucciones manuales
  · Verifica idioma español de Tesseract (spa.traineddata)
  · Verificación final con versiones detectadas
"""

import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

APP_DIR = Path(__file__).parent
PY      = sys.executable
PYV     = sys.version_info


# ── Utilidades ────────────────────────────────────────────────────────────────

def _pip(*args, ignorar_error=False):
    cmd = [PY, "-m", "pip", "install", "--quiet",
           "--no-warn-script-location", *args]
    try:
        subprocess.check_call(cmd)
        return True
    except subprocess.CalledProcessError as e:
        if not ignorar_error:
            print(f"    ⚠️  pip: {e}")
        return False

def _importable(modulo):
    try: __import__(modulo); return True
    except ImportError: return False


# ── PASO 1: Paquetes Python ───────────────────────────────────────────────────

def instalar_python():
    print("=" * 60)
    print("  PASO 1 — Paquetes Python")
    print("=" * 60)

    # ── Resolver el conflicto NumPy / OpenCV ─────────────────────────────
    # opencv-python-headless >= 4.10 requiere numpy >= 2
    # Pero numpy >= 2 puede romper gensim / spacy en Python < 3.9
    # Solución: usar numpy >= 2 si Python >= 3.9, y dejar que pip
    # resuelva qué versión de OpenCV instalar.
    print("  → Resolviendo compatibilidad NumPy / OpenCV…")
    if PYV >= (3, 9):
        numpy_spec = "numpy>=2.0,<3"
        print("    Python >= 3.9 detectado → numpy>=2 (compatible con opencv>=4.10)")
    else:
        numpy_spec = "numpy>=1.24,<2"
        print("    Python < 3.9 detectado  → numpy<2")

    if not _pip(numpy_spec):
        print("    No se pudo instalar numpy con la versión preferida; usando numpy<2")
        _pip("numpy<2", ignorar_error=True)

    # Verificar compatibilidad inmediata
    try:
        import numpy as _np
        print(f"    ✓ numpy {_np.__version__} instalado")
    except Exception:
        pass

    # ── Paquetes (sin numpy, ya instalado) ───────────────────────────────
    paquetes = [
        # Base
        ("pymupdf>=1.23",                    "fitz"),
        ("pdf2image>=1.17",                  "pdf2image"),
        ("pytesseract>=0.3.10",              "pytesseract"),
        ("Pillow>=10.0",                     "PIL"),
        ("spacy>=3.7",                       "spacy"),
        ("scikit-learn>=1.4",                "sklearn"),
        ("networkx>=3.2",                    "networkx"),
        ("matplotlib>=3.8",                  "matplotlib"),
        ("seaborn>=0.13",                    "seaborn"),
        ("pandas>=2.1",                      "pandas"),
        ("openpyxl>=3.1",                    "openpyxl"),
        ("scipy>=1.12",                      "scipy"),
        ("opencv-python-headless",           "cv2"),
        ("requests>=2.31",                   "requests"),
        # NER + embeddings semánticos (v11)
        ("torch>=2.0",                       "torch"),
        ("transformers>=4.40",               "transformers"),
        ("sentence-transformers>=3.0",       "sentence_transformers"),
        # Búsqueda vectorial (v11)
        ("faiss-cpu>=1.7",                   "faiss"),
        # Dictado por voz (v11)
        ("SpeechRecognition>=3.10",          "speech_recognition"),
        ("sounddevice>=0.4",                 "sounddevice"),
        # Validación TEI y XML avanzado (v11)
        ("lxml>=5.0",                        "lxml"),
        # Exportación Word/PPTX (v11)
        ("python-docx>=1.1",                 "docx"),
        ("python-pptx>=0.6",                 "pptx"),
        # Gráficos interactivos (v11)
        ("pyvis>=0.3",                       "pyvis"),
        # Folium (mapa interactivo)
        ("folium>=0.15",                     "folium"),
    ]

    ok_count = 0
    for spec, modulo in paquetes:
        if _importable(modulo):
            print(f"  ✓  {spec.split('>=')[0]} (ya instalado)")
            ok_count += 1
            continue
        print(f"  → {spec}")
        if _pip(spec):
            ok_count += 1

    # Verificar que numpy+opencv son compatibles
    print("\n  Verificando compatibilidad final NumPy + OpenCV…")
    try:
        import cv2 as _cv
        import numpy as _np
        print(f"  ✅ numpy {_np.__version__} + opencv {_cv.__version__} — OK")
    except Exception as e:
        print(f"  ⚠️  Problema de compatibilidad: {e}")
        print("     Intentando reinstalar con versiones fijas…")
        _pip("numpy<2", "--force-reinstall", ignorar_error=True)
        _pip("opencv-python-headless==4.9.0.80", "--force-reinstall",
             ignorar_error=True)

    print(f"\n  ✅ {ok_count}/{len(paquetes)} paquetes listos.\n")

    # ── Kraken OCR (opcional) ─────────────────────────────────────────────
    print("  → Kraken OCR (opcional — necesario para OCR de prensa histórica)…")
    if _importable("kraken"):
        print("  ✓  kraken ya instalado.")
    else:
        print("    Intentando instalar kraken…")
        if _pip("kraken", ignorar_error=True):
            print("  ✅ kraken instalado.")
        else:
            print("  ℹ️  kraken no pudo instalarse automáticamente.")
            print("     Instala manualmente:  pip install kraken")
            print("     Luego descarga el modelo CATMuS-Print con:")
            print("       python -c \"from core.ocr_kraken import descargar_modelo_catmus; descargar_modelo_catmus(print)\"")
    print()


# ── PASO 2: spaCy ─────────────────────────────────────────────────────────────

def instalar_spacy_model(modelo="es_core_news_sm"):
    print("=" * 60)
    print(f"  PASO 2 — Modelo spaCy ({modelo})")
    print("=" * 60)
    try:
        import spacy; spacy.load(modelo)
        print(f"  ✓  {modelo} ya instalado.\n"); return
    except Exception:
        pass
    print(f"  → Descargando {modelo}…")
    try:
        subprocess.check_call([PY, "-m", "spacy", "download", modelo])
        print(f"  ✅ {modelo} instalado.\n")
    except Exception as e:
        print(f"  ⚠️  Error: {e}")
        print("     Ejecuta manualmente:  python -m spacy download es_core_news_sm\n")


# ── PASO 3: Tesseract (Windows) ───────────────────────────────────────────────

_TESS_EXE_URL = (
    "https://github.com/UB-Mannheim/tesseract/releases/download/"
    "v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe"
)
_TESS_RUTAS = [
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
]

def _buscar_tesseract():
    t = shutil.which("tesseract")
    if t: return Path(t)
    for p in _TESS_RUTAS:
        if p.exists(): return p
    # Buscar en cualquier subcarpeta de Program Files
    for base in [Path(r"C:\Program Files"), Path(r"C:\Program Files (x86)")]:
        hits = list(base.glob("**/tesseract.exe"))
        if hits: return hits[0]
    return None

def instalar_tesseract_windows():
    print("=" * 60)
    print("  PASO 3 — Tesseract OCR")
    print("=" * 60)

    tess = _buscar_tesseract()
    if tess:
        (APP_DIR / "tesseract_path.txt").write_text(str(tess), encoding="utf-8")
        print(f"  ✓  Tesseract encontrado: {tess}")
        _asegurar_spa(tess)
        print()
        return

    print("  Tesseract no encontrado. Probando métodos de instalación…\n")

    # Método A: winget
    if _intentar_winget():
        tess = _buscar_tesseract()

    # Método B: descarga directa del .exe
    if not tess:
        if _descargar_tess_exe():
            tess = _buscar_tesseract()

    if tess:
        (APP_DIR / "tesseract_path.txt").write_text(str(tess), encoding="utf-8")
        print(f"  ✅ Tesseract: {tess}")
        _asegurar_spa(tess)
    else:
        _instrucciones_manuales_tesseract()
    print()

def _intentar_winget():
    if not shutil.which("winget"):
        print("  ⚠️  winget no disponible.")
        return False
    print("  → Intentando instalar con winget…")
    try:
        # Actualizar fuente (puede fallar en redes corporativas)
        subprocess.run(["winget", "source", "update"],
                       capture_output=True, timeout=30)
        r = subprocess.run(
            ["winget", "install", "--id", "UB-Mannheim.TesseractOCR",
             "-e", "--silent",
             "--accept-package-agreements", "--accept-source-agreements"],
            capture_output=True, timeout=180,
        )
        if r.returncode == 0:
            print("  ✅ Tesseract instalado con winget.")
            return True
        print(f"  ⚠️  winget código {r.returncode}. Probando descarga directa…")
        return False
    except Exception as e:
        print(f"  ⚠️  winget: {e}. Probando descarga directa…")
        return False

def _descargar_tess_exe():
    tmp = Path(os.environ.get("TEMP", "C:\\Temp"))
    tmp.mkdir(parents=True, exist_ok=True)
    exe = tmp / "tesseract_setup.exe"
    print("  → Descargando instalador Tesseract (~50 MB)…")
    print(f"    {_TESS_EXE_URL}")
    try:
        def _prog(c, b, t):
            print(f"\r    {min(int(c*b*100/max(t,1)),100):3d}%…", end="", flush=True)
        urllib.request.urlretrieve(_TESS_EXE_URL, exe, reporthook=_prog)
        print()
    except Exception as e:
        print(f"\n  ⚠️  Descarga fallida: {e}")
        return False

    print("  → Ejecutando instalador (puede pedir permisos de administrador)…")
    try:
        inst_dir = Path(r"C:\Program Files\Tesseract-OCR")
        r = subprocess.run(
            [str(exe), "/S", f"/D={inst_dir}"],
            timeout=180,
        )
        exe.unlink(missing_ok=True)
        return r.returncode == 0
    except Exception as e:
        print(f"  ⚠️  Instalador falló: {e}")
        exe.unlink(missing_ok=True)
        return False

def _asegurar_spa(tess_exe: Path):
    tessdata = tess_exe.parent / "tessdata"
    if (tessdata / "spa.traineddata").exists():
        print("  ✓  Idioma español (spa) disponible.")
        return
    print("  → Descargando datos de idioma español (spa.traineddata)…")
    url  = "https://github.com/tesseract-ocr/tessdata_best/raw/main/spa.traineddata"
    dest = tessdata / "spa.traineddata"
    try:
        tessdata.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(url, dest)
        print("  ✅ spa.traineddata instalado.")
    except Exception as e:
        print(f"  ⚠️  No se pudo descargar spa.traineddata: {e}")
        print("     Descarga manualmente: https://github.com/tesseract-ocr/tessdata_best")
        print(f"     Coloca el archivo en: {tessdata}")

def _instrucciones_manuales_tesseract():
    url_directa = (
        "https://github.com/UB-Mannheim/tesseract/releases/download/"
        "v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe"
    )
    print()
    print("  ┌─────────────────────────────────────────────────────────┐")
    print("  │  INSTALACIÓN MANUAL DE TESSERACT (pasos necesarios)     │")
    print("  │                                                          │")
    print("  │  1. Descarga el instalador directamente desde:           │")
    print(f"  │     {url_directa[:56]}│")
    print(f"  │     {url_directa[56:]}  │")
    print("  │                                                          │")
    print("  │  2. Ejecuta el instalador.                               │")
    print("  │     En 'Additional language data' marca: Spanish         │")
    print("  │                                                          │")
    print("  │  3. Al terminar, la ruta será normalmente:               │")
    print("  │     C:\\Program Files\\Tesseract-OCR\\tesseract.exe         │")
    print("  │                                                          │")
    print("  │  4. Crea el archivo  tesseract_path.txt  en la carpeta  │")
    print("  │     de Bashkar Station con esa ruta como contenido.      │")
    print("  │                                                          │")
    print("  │  5. Vuelve a ejecutar:  python instalar.py               │")
    print("  └─────────────────────────────────────────────────────────┘")
    print()
    print(f"  URL de descarga: {url_directa}")


# ── PASO 4: Poppler (Windows) ─────────────────────────────────────────────────

_POPPLER_URL = (
    "https://github.com/oschwartz10612/poppler-windows/releases/"
    "download/v24.08.0-0/Release-24.08.0-0.zip"
)

def instalar_poppler_windows():
    print("=" * 60)
    print("  PASO 4 — Poppler (renderizado PDF → imagen)")
    print("=" * 60)

    if shutil.which("pdftoppm"):
        print("  ✓  Poppler ya en el PATH.\n"); return

    pfile = APP_DIR / "poppler_path.txt"
    if pfile.exists():
        r = pfile.read_text(encoding="utf-8").strip()
        if Path(r).exists():
            print(f"  ✓  Poppler ya configurado: {r}\n"); return

    import zipfile
    dest = Path(os.environ.get("LOCALAPPDATA","C:\\")) / "bashkar_poppler"
    dest.mkdir(parents=True, exist_ok=True)
    zpath = dest / "poppler.zip"

    print("  → Descargando Poppler (~20 MB)…")
    try:
        def _prog(c, b, t):
            print(f"\r    {min(int(c*b*100/max(t,1)),100):3d}%…", end="", flush=True)
        urllib.request.urlretrieve(_POPPLER_URL, zpath, reporthook=_prog)
        print()
    except Exception as e:
        print(f"\n  ⚠️  Descarga fallida: {e}")
        print("     Descarga manualmente: https://github.com/oschwartz10612/poppler-windows/releases")
        print("    Descomprime y escribe la ruta de 'bin\\' en poppler_path.txt")
        print()
        return

    print("  → Descomprimiendo…")
    try:
        with zipfile.ZipFile(zpath, "r") as zf:
            zf.extractall(dest)
        zpath.unlink(missing_ok=True)
        bins = list(dest.glob("**/pdftoppm.exe"))
        if bins:
            bin_dir = str(bins[0].parent)
            pfile.write_text(bin_dir, encoding="utf-8")
            print(f"  ✅ Poppler instalado en: {bin_dir}\n")
        else:
            print("  ⚠️  pdftoppm.exe no encontrado tras descomprimir.\n")
    except Exception as e:
        print(f"  ⚠️  Error al descomprimir: {e}\n")


# ── PASO 3-4 Unix ─────────────────────────────────────────────────────────────

def instalar_unix():
    sistema = platform.system()
    print("=" * 60)
    print(f"  PASOS 3-4 — Tesseract + Poppler ({sistema})")
    print("=" * 60)
    if sistema == "Darwin":
        cmds = [["brew","install","tesseract"],
                ["brew","install","tesseract-lang"],
                ["brew","install","poppler"]]
    else:
        cmds = [["sudo","apt","install","-y",
                 "tesseract-ocr","tesseract-ocr-spa","poppler-utils"]]
    for cmd in cmds:
        try:
            subprocess.run(cmd, check=True)
        except Exception as e:
            print(f"  ⚠️  {' '.join(cmd)}: {e}")
    print()


# ── PASO 5: Precarga de modelos IA ────────────────────────────────────────────

def precargar_modelos():
    print("=" * 60)
    print("  PASO 5 — Precarga de modelos IA")
    print("=" * 60)
    print("  (Esto descarga los modelos la primera vez; puede tardar varios minutos)")
    print()

    # Modelo NER BERT-Spanish
    print("  → Modelo NER: mrm8488/bert-spanish-cased-finetuned-ner…")
    try:
        from core.ner_roberta_local import precargar_modelo
        ok = precargar_modelo()
        print("  ✅ Modelo NER listo." if ok else "  ⚠️  Modelo NER no disponible (necesita conexión).")
    except Exception as e:
        print(f"  ⚠️  Error al cargar modelo NER: {e}")

    # Modelo de embeddings
    print("  → Embeddings: paraphrase-multilingual-MiniLM-L12-v2…")
    try:
        from core.embeddings_local import precargar_modelo as precargar_embs
        ok = precargar_embs()
        print("  ✅ Modelo embeddings listo." if ok else "  ⚠️  Modelo embeddings no disponible (necesita conexión).")
    except Exception as e:
        print(f"  ⚠️  Error al cargar embeddings: {e}")

    # Verificar Ollama (opcional)
    print("  → Verificando Ollama (OCR visual, opcional)…")
    try:
        from core.ocr_ollama_local import listar_modelos_vision
        modelos = listar_modelos_vision()
        if modelos:
            print(f"  ✅ Ollama disponible. Modelos visión: {', '.join(modelos)}")
        else:
            print("  ℹ️  Ollama instalado pero sin modelos de visión.")
            print("     Para OCR visual ejecuta:  ollama pull qwen2.5vl:7b")
    except Exception:
        print("  ℹ️  Ollama no disponible (opcional — instala desde https://ollama.ai)")
    print()


# ── Verificación final ────────────────────────────────────────────────────────

def verificar():
    print("=" * 60)
    print("  VERIFICACIÓN FINAL")
    print("=" * 60)

    # Paquetes requeridos
    checks_req = [
        ("fitz",         "PyMuPDF"),
        ("PIL",          "Pillow"),
        ("numpy",        "NumPy"),
        ("cv2",          "OpenCV"),
        ("spacy",        "spaCy"),
        ("sklearn",      "scikit-learn"),
        ("matplotlib",   "Matplotlib"),
        ("pandas",       "Pandas"),
        ("openpyxl",     "OpenPyXL"),
        ("networkx",     "NetworkX"),
        ("scipy",        "SciPy"),
        ("requests",     "Requests"),
        ("pytesseract",  "pytesseract"),
        ("torch",        "PyTorch"),
        ("transformers", "Transformers (HF)"),
        ("sentence_transformers", "Sentence-Transformers"),
        ("faiss",        "FAISS"),
    ]
    # Paquetes opcionales (no marcan error global)
    checks_opt = [
        ("kraken",       "Kraken OCR"),
        ("pdf2image",    "pdf2image"),
        ("seaborn",      "Seaborn"),
    ]

    todo_ok = True
    print("\n  Requeridos:")
    for mod, nombre in checks_req:
        try:
            m   = __import__(mod)
            ver = getattr(m, "__version__", "?")
            print(f"  ✅ {nombre:<28} {ver}")
        except ImportError:
            print(f"  ❌ {nombre:<28} NO INSTALADO")
            todo_ok = False

    print("\n  Opcionales:")
    for mod, nombre in checks_opt:
        try:
            m   = __import__(mod)
            ver = getattr(m, "__version__", "?")
            print(f"  ✅ {nombre:<28} {ver}")
        except ImportError:
            print(f"  ℹ️  {nombre:<28} no instalado (funcionalidad reducida)")

    # Tesseract
    print()
    tess = _buscar_tesseract()
    if tess:
        try:
            r = subprocess.run([str(tess), "--version"],
                               capture_output=True, text=True, timeout=5)
            ver = (r.stderr or r.stdout).split("\n")[0]
        except Exception:
            ver = str(tess)
        print(f"  ✅ {'Tesseract':<28} {ver}")
    else:
        print(f"  ❌ {'Tesseract':<28} NO ENCONTRADO — instala manualmente")
        todo_ok = False

    # Modelos IA (verificación rápida, sin descargar)
    print()
    try:
        from core.ner_roberta_local import roberta_disponible
        if roberta_disponible():
            print(f"  ✅ {'Motor NER (transformers)':<28} disponible")
        else:
            print(f"  ❌ {'Motor NER (transformers)':<28} no disponible")
            todo_ok = False
    except Exception:
        pass

    try:
        from core.embeddings_local import sentence_transformers_disponible
        if sentence_transformers_disponible():
            print(f"  ✅ {'Embeddings semánticos':<28} disponible")
        else:
            print(f"  ❌ {'Embeddings semánticos':<28} no disponible")
            todo_ok = False
    except Exception:
        pass

    try:
        from core.busqueda_semantica import faiss_disponible
        if faiss_disponible():
            print(f"  ✅ {'Búsqueda FAISS':<28} disponible")
        else:
            print(f"  ❌ {'Búsqueda FAISS':<28} no disponible")
    except Exception:
        pass

    print()
    if todo_ok:
        print("  Todo listo. Ejecuta:  python app.py")
    else:
        print("  Algunos componentes requieren atención (ver arriba).")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║   BASHKAR STATION v11 — Instalacion inicial                  ║")
    print(f"║   Python {PYV.major}.{PYV.minor}.{PYV.micro} — {platform.system()} {platform.machine():<31}║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    instalar_python()          # Paso 1: paquetes pip (incluye torch, transformers, faiss)
    instalar_spacy_model()     # Paso 2: modelo spaCy es_core_news_sm

    if platform.system() == "Windows":
        instalar_tesseract_windows()   # Paso 3
        instalar_poppler_windows()     # Paso 4
    else:
        instalar_unix()                # Pasos 3-4

    precargar_modelos()        # Paso 5: descarga modelos HuggingFace

    verificar()
    input("Presiona ENTER para cerrar…")

if __name__ == "__main__":
    main()
