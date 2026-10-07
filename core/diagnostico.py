"""core/diagnostico.py — ¿Funciona de verdad lo que este equipo debería poder hacer?

    BashkarStation.exe --diagnostico [informe.json]
    python app.py --diagnostico [informe.json]

Escribe un informe JSON y termina sin abrir la interfaz. Existe porque el
.exe es una aplicación de ventana: sin esto no hay forma de comprobar, sin
hacer clic, que dentro del paquete congelado la GPU responde y los modelos
cargan (sesión 72). Cada comprobación ejecuta el código real, no mira si un
módulo existe: "importa" no es "funciona".
"""

from __future__ import annotations

import json
import platform
import sys
import time
import traceback
from pathlib import Path


def _probar(nombre: str, fn, resultados: list):
    t0 = time.perf_counter()
    try:
        detalle = fn()
        ok = True
    except Exception as e:
        detalle = f"{type(e).__name__}: {e}"
        ok = False
    resultados.append({"prueba": nombre, "ok": ok, "detalle": detalle,
                       "segundos": round(time.perf_counter() - t0, 2)})


def _gpu():
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError(f"torch {torch.__version__} sin CUDA")
    x = torch.randn(1024, 1024, device="cuda")
    assert float((x @ x).abs().sum()) > 0
    return {"torch": torch.__version__, "cuda": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0)}


def _ner():
    from core.ner_roberta_local import _pipeline_ner, ner_roberta
    pipe = _pipeline_ner()
    ents = ner_roberta("Germán Arciniegas llegó a Bogotá desde Buenos Aires.")
    nombres = {e["texto"] for e in ents}
    assert "Bogotá" in nombres, f"entidades: {nombres}"
    return {"dispositivo": str(pipe.device), "entidades": sorted(nombres)}


def _embeddings():
    from core.embeddings_local import _modelo_embeddings, generar_embeddings
    v = generar_embeddings(["prensa colombiana de 1939"])
    return {"dimension": int(v.shape[1]), "dispositivo": str(_modelo_embeddings().device)}


def _spacy():
    """Sintaxis y correferencia dependen de spaCy: analizar una frase de verdad."""
    from core.servicios_ner import cargar_spacy
    nlp = cargar_spacy()
    if nlp is None:
        raise RuntimeError("ningún modelo es_core_news_* carga")
    doc = nlp("Germán Arciniegas publicó una crónica en Bogotá.")
    raiz = [t.text for t in doc if t.dep_ == "ROOT"]
    assert raiz, "sin análisis de dependencias"
    return {"modelo": nlp.meta.get("name"), "raiz": raiz,
            "entidades": [e.text for e in doc.ents]}


def _motores():
    from core.ocr import crear, nombres
    salida = {}
    for n in nombres():
        try:
            salida[n] = crear(n).motivo_no_disponible() or "disponible"
        except Exception as e:
            salida[n] = f"error: {e}"
    return salida


def _plan_ocr():
    from core.ocr.enrutador import Enrutador
    plan = Enrutador().plan()
    return {k: plan[k] for k in ("primario", "segunda_opinion", "respaldo")}


def _ocr_real():
    """Una página sintética con texto conocido, por el motor primario."""
    import tempfile

    from PIL import Image, ImageDraw, ImageFont

    from core.ocr.enrutador import Enrutador
    img = Image.new("RGB", (1400, 400), "white")
    d = ImageDraw.Draw(img)
    try:
        fuente = ImageFont.truetype("arial.ttf", 64)
    except OSError:
        fuente = ImageFont.load_default()
    d.text((60, 140), "Revista Estampa Bogota 1939", fill="black", font=fuente)
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "diag.png"
        img.save(ruta)
        with Enrutador() as enr:
            r, fila = enr.procesar(ruta, Path(tmp) / "diag.txt", "diagnostico")
        texto = (Path(tmp) / "diag.txt").read_text("utf-8")
    assert "Estampa" in texto, f"leyó {texto!r}"
    return {"motor": fila["metodo"], "texto": texto.strip()[:80]}


def _importaciones():
    """Importa de verdad las librerías pesadas y devuelve el error REAL.

    Los módulos de Bashkar envuelven el ImportError en "no está instalado";
    en el .exe congelado la causa suele ser otra (un submódulo que PyInstaller
    no empaquetó) y ese mensaje la tapa.
    """
    import importlib
    salida, fallos = {}, []
    for mod in ("transformers", "sentence_transformers", "torchvision", "faiss", "spacy",
                "transformers.models.qwen2_5_vl"):
        try:
            m = importlib.import_module(mod)
            salida[mod] = getattr(m, "__version__", "ok")
        except Exception as e:
            fallos.append(mod)
            salida[mod] = "".join(traceback.format_exception_only(type(e), e)).strip()[-400:]
    if fallos:
        raise RuntimeError(json.dumps(salida, ensure_ascii=False))
    return salida


def ejecutar(destino: Path | None = None, ocr: bool = True) -> dict:
    resultados: list = []
    _probar("importaciones", _importaciones, resultados)
    _probar("gpu", _gpu, resultados)
    _probar("ner_roberta", _ner, resultados)
    _probar("embeddings", _embeddings, resultados)
    _probar("spacy", _spacy, resultados)
    _probar("motores_ocr", _motores, resultados)
    _probar("plan_enrutador", _plan_ocr, resultados)
    if ocr:
        _probar("ocr_real", _ocr_real, resultados)
    informe = {
        "congelado": bool(getattr(sys, "frozen", False)),
        "python": platform.python_version(),
        "ejecutable": sys.executable,
        "ok": all(r["ok"] for r in resultados),
        "pruebas": resultados,
    }
    if destino:
        Path(destino).write_text(json.dumps(informe, ensure_ascii=False, indent=1,
                                            default=str), "utf-8")
    return informe


def main(argv: list[str]) -> int:
    i = argv.index("--diagnostico")
    destino = Path(argv[i + 1]) if len(argv) > i + 1 else (
        Path.home() / "bashkar_diagnostico.json")
    try:
        informe = ejecutar(destino)
    except Exception:
        destino.write_text(traceback.format_exc(), "utf-8")
        return 2
    return 0 if informe["ok"] else 1
