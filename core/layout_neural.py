"""
core/layout_neural.py — Detección de layout con redes neuronales.

Tres motores seleccionables por el usuario:

  Motor "yolo"  — YOLOv8n entrenado en DocLayNet/PubLayNet.
                   ~6 MB, corre en CPU, ~2s/pág. Recomendado para el PC actual.
                   Requiere: pip install ultralytics

  Motor "onnx"  — DocLayNet exportado a ONNX Runtime, sin torch.
                   ~45 MB, corre en CPU, ~1s/pág.
                   Requiere: pip install onnxruntime pillow

  Motor "dit"   — Microsoft DiT (Document Image Transformer) via Hugging Face.
                   ~330 MB, ideal con ≥16 GB RAM / GPU. Para el PC nuevo.
                   Requiere: pip install transformers torch

Salida unificada de los tres motores:
  list[dict]  con campos:
    tipo      : str   — "texto"|"titulo"|"figura"|"tabla"|"lista"|"cabecera"|"pie_foto"
    x0,y0,x1,y1: float  — coordenadas normalizadas [0,1]
    confianza : float

Uso:
    from core.layout_neural import detectar_layout, motor_disponible
    zonas = detectar_layout(img_path, motor="yolo")
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional

# ── Mapa de etiquetas de modelos → tipos de zona de Bashkar ──────────────────

# PubLayNet / DocLayNet labels
_LABEL_MAP_PUBLAY = {
    "text":    "articulo",
    "title":   "titulo",
    "figure":  "foto",
    "table":   "indice",
    "list":    "articulo",
}

# DocLayNet labels (11 clases)
_LABEL_MAP_DOCLAY = {
    "Caption":          "pie_foto",
    "Footnote":         "colofon",
    "Formula":          "articulo",
    "List-item":        "articulo",
    "Page-footer":      "numero_pag",
    "Page-header":      "cabecera",
    "Picture":          "foto",
    "Section-header":   "titulo",
    "Table":            "indice",
    "Text":             "articulo",
    "Title":            "titulo",
}

# DiT labels (mismos que PubLayNet)
_LABEL_MAP_DIT = _LABEL_MAP_PUBLAY


# ── Comprobación de disponibilidad ───────────────────────────────────────────

def motor_disponible(motor: str) -> tuple[bool, str]:
    """
    Devuelve (disponible, mensaje).
    mensaje describe qué falta instalar si no está disponible.
    """
    if motor == "yolo":
        try:
            import ultralytics  # noqa
            return True, "YOLOv8 disponible"
        except ImportError:
            return False, "Instala ultralytics: pip install ultralytics"

    elif motor == "onnx":
        try:
            import onnxruntime  # noqa
            return True, "ONNX Runtime disponible"
        except ImportError:
            return False, "Instala onnxruntime: pip install onnxruntime"

    elif motor == "dit":
        try:
            import transformers  # noqa
            import torch         # noqa
            return True, "DiT disponible (transformers + torch)"
        except ImportError:
            return False, "Instala transformers y torch: pip install transformers torch"

    return False, f"Motor desconocido: {motor}"


# ── Función principal ─────────────────────────────────────────────────────────

def detectar_layout(
    img_path: Path,
    motor: str = "yolo",
    modelo_path: Optional[Path] = None,
    umbral: float = 0.3,
    callback=None,
) -> list[dict]:
    """
    Detecta zonas de layout en una imagen de página.

    Args:
        img_path:    Ruta a la imagen PNG/JPG de la página.
        motor:       "yolo" | "onnx" | "dit"
        modelo_path: Ruta local al modelo descargado. Si None, descarga
                     automáticamente a la carpeta modelos/ del proyecto.
        umbral:      Confianza mínima para incluir una detección.
        callback:    callable(mensaje) para logging en UI.

    Returns:
        list[dict] con campos: tipo, x0, y0, x1, y1, confianza
    """
    def log(m):
        if callback:
            callback(m)

    img_path = Path(img_path)
    if not img_path.exists():
        log(f"⚠ Imagen no encontrada: {img_path}")
        return []

    if motor == "yolo":
        return _detectar_yolo(img_path, modelo_path, umbral, log)
    elif motor == "onnx":
        return _detectar_onnx(img_path, modelo_path, umbral, log)
    elif motor == "dit":
        return _detectar_dit(img_path, modelo_path, umbral, log)
    else:
        log(f"⚠ Motor desconocido: {motor}")
        return []


# ── Motor YOLO ────────────────────────────────────────────────────────────────

_YOLO_MODEL_URL = (
    "https://huggingface.co/Omnivore/yolov8_doclaynet/resolve/main/"
    "yolov8n-doclaynet.pt"
)
_YOLO_MODEL_NAME = "yolov8n-doclaynet.pt"


def _yolo_model_path(modelo_path: Optional[Path]) -> Path:
    if modelo_path and Path(modelo_path).exists():
        return Path(modelo_path)
    # Buscar en carpeta modelos/ del proyecto
    local = Path(__file__).parent.parent / "modelos" / _YOLO_MODEL_NAME
    return local


def _descargar_si_falta(url: str, destino: Path, log):
    if destino.exists():
        return True
    log(f"Descargando modelo → {destino.name} …")
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        import urllib.request
        urllib.request.urlretrieve(url, str(destino))
        log(f"✅ Descarga completada: {destino.name}")
        return True
    except Exception as e:
        log(f"⚠ Error al descargar: {e}")
        return False


def _detectar_yolo(img_path: Path, modelo_path: Optional[Path],
                   umbral: float, log) -> list[dict]:
    try:
        from ultralytics import YOLO
    except ImportError:
        log("⚠ YOLOv8 no disponible. Instala: pip install ultralytics")
        return []

    mp = _yolo_model_path(modelo_path)
    if not mp.exists():
        ok = _descargar_si_falta(_YOLO_MODEL_URL, mp, log)
        if not ok:
            return []

    log(f"YOLOv8 · analizando {img_path.name} …")
    try:
        model  = YOLO(str(mp))
        result = model(str(img_path), conf=umbral, verbose=False)[0]
    except Exception as e:
        log(f"⚠ Error YOLOv8: {e}")
        return []

    from PIL import Image
    img    = Image.open(img_path)
    W, H   = img.size
    zonas  = []
    names  = result.names  # {int: "Text", ...}

    for box in result.boxes:
        conf   = float(box.conf[0])
        cls_id = int(box.cls[0])
        label  = names.get(cls_id, "articulo")
        tipo   = _LABEL_MAP_DOCLAY.get(label, _LABEL_MAP_PUBLAY.get(label, "articulo"))
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        zonas.append({
            "tipo":      tipo,
            "x0":        round(x1 / W, 4),
            "y0":        round(y1 / H, 4),
            "x1":        round(x2 / W, 4),
            "y1":        round(y2 / H, 4),
            "confianza": round(conf, 3),
        })

    log(f"  YOLOv8: {len(zonas)} zonas detectadas")
    return zonas


# ── Motor ONNX ────────────────────────────────────────────────────────────────

_ONNX_MODEL_URL  = (
    "https://huggingface.co/nickmuchi/yolos-small-finetuned-DocLayNet/resolve/main/"
    "onnx/model.onnx"
)
_ONNX_MODEL_NAME = "doclaynet_yolos.onnx"

# Clases del modelo YOLOS-DocLayNet (en orden)
_ONNX_LABELS = [
    "Caption","Footnote","Formula","List-item","Page-footer",
    "Page-header","Picture","Section-header","Table","Text","Title",
]


def _detectar_onnx(img_path: Path, modelo_path: Optional[Path],
                   umbral: float, log) -> list[dict]:
    try:
        import onnxruntime as ort
        import numpy as np
        from PIL import Image
    except ImportError:
        log("⚠ ONNX Runtime no disponible. Instala: pip install onnxruntime")
        return []

    if modelo_path and Path(modelo_path).exists():
        mp = Path(modelo_path)
    else:
        mp = Path(__file__).parent.parent / "modelos" / _ONNX_MODEL_NAME

    if not mp.exists():
        ok = _descargar_si_falta(_ONNX_MODEL_URL, mp, log)
        if not ok:
            return []

    log(f"ONNX DocLayNet · analizando {img_path.name} …")
    try:
        sess = ort.InferenceSession(str(mp),
               providers=["CPUExecutionProvider"])
        img = Image.open(img_path).convert("RGB")
        W, H = img.size

        # Preprocesar: resize a 800px lado largo, normalizar
        scale = 800 / max(W, H)
        nw, nh = int(W * scale), int(H * scale)
        img_r  = img.resize((nw, nh))
        arr    = np.array(img_r, dtype=np.float32) / 255.0
        # Pad a cuadrado 800x800
        canvas = np.zeros((800, 800, 3), dtype=np.float32)
        canvas[:nh, :nw] = arr
        # NCHW
        inp = canvas.transpose(2, 0, 1)[np.newaxis]

        inp_name  = sess.get_inputs()[0].name
        out_names = [o.name for o in sess.get_outputs()]
        outputs   = sess.run(out_names, {inp_name: inp})

        # outputs[0] = boxes (N,4) en xyxy relativo a 800x800
        # outputs[1] = scores (N, n_clases) o (N,) según el modelo exportado
        boxes  = outputs[0]  # shape (N, 4)
        scores = outputs[1]  # shape (N, n_clases) o (N,)

        zonas = []
        for i, box in enumerate(boxes):
            if scores.ndim == 2:
                cls_id = int(np.argmax(scores[i]))
                conf   = float(scores[i][cls_id])
            else:
                cls_id = 0
                conf   = float(scores[i])
            if conf < umbral:
                continue
            label = _ONNX_LABELS[cls_id] if cls_id < len(_ONNX_LABELS) else "Text"
            tipo  = _LABEL_MAP_DOCLAY.get(label, "articulo")
            x0r, y0r, x1r, y1r = box
            zonas.append({
                "tipo":      tipo,
                "x0":        round(float(x0r / 800 / scale * scale), 4),
                "y0":        round(float(y0r / 800 / scale * scale), 4),
                "x1":        round(float(x1r / 800 / scale * scale), 4),
                "y1":        round(float(y1r / 800 / scale * scale), 4),
                "confianza": round(conf, 3),
            })

        log(f"  ONNX: {len(zonas)} zonas detectadas")
        return zonas

    except Exception as e:
        log(f"⚠ Error ONNX: {e}")
        return []


# ── Motor DiT (Document Image Transformer) ───────────────────────────────────

_DIT_MODEL_ID   = "microsoft/dit-base-finetuned-rvlcdip"
_DIT_MODEL_NAME = "dit-base-doclaynet"

# Para detección de objetos usamos el modelo de object detection de DiT
_DIT_OD_MODEL_ID = "Xenova/dit-base-finetuned-publaynet"


def _detectar_dit(img_path: Path, modelo_path: Optional[Path],
                  umbral: float, log) -> list[dict]:
    try:
        from transformers import AutoFeatureExtractor, AutoModelForObjectDetection
        import torch
        from PIL import Image
    except ImportError:
        log("⚠ DiT no disponible. Instala: pip install transformers torch")
        return []

    model_id = str(modelo_path) if modelo_path and Path(str(modelo_path)).exists() \
               else _DIT_OD_MODEL_ID

    log(f"DiT · cargando modelo {model_id} …")
    try:
        extractor = AutoFeatureExtractor.from_pretrained(model_id)
        model     = AutoModelForObjectDetection.from_pretrained(model_id)
        model.eval()

        img      = Image.open(img_path).convert("RGB")
        W, H     = img.size
        inputs   = extractor(images=img, return_tensors="pt")

        with torch.no_grad():
            outputs = model(**inputs)

        target_sizes = torch.tensor([[H, W]])
        results = extractor.post_process_object_detection(
            outputs, threshold=umbral, target_sizes=target_sizes)[0]

        zonas = []
        for score, label, box in zip(results["scores"],
                                      results["labels"],
                                      results["boxes"]):
            conf  = float(score)
            lname = model.config.id2label.get(int(label), "text")
            tipo  = _LABEL_MAP_DIT.get(lname.lower(), "articulo")
            x0, y0, x1, y1 = box.tolist()
            zonas.append({
                "tipo":      tipo,
                "x0":        round(x0 / W, 4),
                "y0":        round(y0 / H, 4),
                "x1":        round(x1 / W, 4),
                "y1":        round(y1 / H, 4),
                "confianza": round(conf, 3),
            })

        log(f"  DiT: {len(zonas)} zonas detectadas")
        return zonas

    except Exception as e:
        log(f"⚠ Error DiT: {e}")
        return []


# ── Instalación asistida ──────────────────────────────────────────────────────

def instalar_motor(motor: str, callback=None) -> bool:
    """
    Intenta instalar las dependencias del motor indicado vía pip.
    Retorna True si la instalación fue exitosa.
    """
    import subprocess, sys
    def log(m):
        if callback:
            callback(m)

    paquetes = {
        "yolo": ["ultralytics"],
        "onnx": ["onnxruntime"],
        "dit":  ["transformers", "torch"],
    }
    pkgs = paquetes.get(motor, [])
    if not pkgs:
        return False

    for pkg in pkgs:
        log(f"pip install {pkg} …")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg, "-q"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log(f"  ✅ {pkg} instalado")
        except Exception as e:
            log(f"  ⚠ Error instalando {pkg}: {e}")
            return False
    return True
