"""Trabajador persistente de Surya (corre en el venv de Surya, NO en el de Bashkar).

Protocolo: ver ``core/ocr/externo.py``. stdout es solo protocolo; todo lo
demás va a stderr.

Surya 0.22 es un VLM (surya-ocr-2) servido por llama.cpp en Windows (vLLM no
existe para Windows). ``LLAMA_CPP_BINARY`` debe apuntar a un ``llama-server``
con CUDA; por defecto ``C:\\dev\\tools\\llama.cpp\\llama-server.exe``.
"""

import html
import json
import os
import re
import sys

_stdout = sys.stdout
sys.stdout = sys.stderr          # cualquier print de Surya va a stderr

os.environ.setdefault("SURYA_INFERENCE_BACKEND", "llamacpp")
_LLAMA = r"C:\dev\tools\llama.cpp\llama-server.exe"
if os.path.isfile(_LLAMA):
    os.environ.setdefault("LLAMA_CPP_BINARY", _LLAMA)

# Etiquetas canónicas de Surya → tipos de bloque de Bashkar (core/ocr/interfaces.py).
_TIPOS = {
    "Text": "texto", "SectionHeader": "titulo", "PageHeader": "cabecera",
    "PageFooter": "pie_pagina", "Caption": "pie_imagen", "Footnote": "nota",
    "ListGroup": "lista", "Table": "tabla", "Picture": "figura", "Figure": "figura",
    "Equation": "formula", "TableOfContents": "lista", "Form": "tabla",
}
_ETIQUETA = re.compile(r"<[^>]+>")


def _texto_de_html(h: str) -> str:
    h = re.sub(r"(?i)<br\s*/?>", "\n", h or "")
    h = re.sub(r"(?i)</(p|div|li|tr|h\d)>", "\n", h)
    return html.unescape(_ETIQUETA.sub("", h)).strip()


def _responder(d):
    _stdout.write(json.dumps(d, ensure_ascii=False) + "\n")
    _stdout.flush()


def main():
    from importlib.metadata import version

    from PIL import Image
    from surya.inference import SuryaInferenceManager
    from surya.recognition import RecognitionPredictor

    ver = f"surya-ocr {version('surya-ocr')}"
    gestor = SuryaInferenceManager()
    gestor.start()
    reconocedor = RecognitionPredictor(gestor)
    _responder({"listo": True, "version": f"{ver} backend={gestor.method}"})

    for linea in sys.stdin:
        if not linea.strip():
            continue
        try:
            pedido = json.loads(linea)
            img = Image.open(pedido["imagen"]).convert("RGB")
            pagina = reconocedor([img], full_page=True)[0]
            bloques = []
            for b in sorted(pagina.blocks, key=lambda b: b.reading_order):
                if b.skipped:
                    texto = ""
                else:
                    texto = _texto_de_html(b.html)
                xs = [p[0] for p in b.polygon]
                ys = [p[1] for p in b.polygon]
                bloques.append({
                    "texto": texto,
                    "bbox": [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))],
                    "poligono": [[int(x), int(y)] for x, y in b.polygon],
                    "tipo": _TIPOS.get(b.label, "desconocido"),
                    "orden": b.reading_order + 1,
                    "confianza": None if b.confidence is None else round(b.confidence * 100, 1),
                    "revisar": bool(b.error),
                    "alternativas": [],
                })
            texto = "\n\n".join(b["texto"] for b in bloques if b["texto"])
            _responder({"ok": True, "texto": texto, "bloques": bloques, "confianza": None,
                        "version": ver,
                        "detalles": {"bloques_con_error": sum(b["revisar"] for b in bloques)}})
        except Exception as e:
            _responder({"ok": False, "error": f"{type(e).__name__}: {e}"})
    gestor.stop()


if __name__ == "__main__":
    main()
