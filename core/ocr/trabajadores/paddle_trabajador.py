"""Trabajador persistente de PaddleOCR / PP-StructureV3 (venv de Paddle, NO el de Bashkar).

    python paddle_trabajador.py ocr          # PaddleOCR: líneas con caja y confianza
    python paddle_trabajador.py estructura   # PP-StructureV3: layout, tablas, orden

Protocolo: ver ``core/ocr/externo.py``. stdout es solo protocolo.

En Windows las DLL de CUDA vienen en ``site-packages/nvidia/**`` y Paddle no
las encuentra por sí mismo (error 126 al cargar cublas64_13.dll): se registran
antes de importar paddle.
"""

import glob
import json
import os
import site
import sys

_stdout = sys.stdout
sys.stdout = sys.stderr

for _d in sorted({os.path.dirname(p) for sp in site.getsitepackages()
                  for p in glob.glob(os.path.join(sp, "nvidia", "**", "*.dll"), recursive=True)}):
    os.add_dll_directory(_d)
    os.environ["PATH"] = _d + os.pathsep + os.environ["PATH"]
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

# Etiquetas de PP-StructureV3 → tipos de bloque de Bashkar.
_TIPOS = {
    "text": "texto", "paragraph_title": "subtitulo", "doc_title": "titulo",
    "figure_title": "pie_imagen", "table_title": "pie_imagen", "chart_title": "pie_imagen",
    "image": "figura", "chart": "figura", "seal": "figura", "table": "tabla",
    "formula": "formula", "display_formula": "formula", "inline_formula": "formula",
    "header": "cabecera", "footer": "pie_pagina", "number": "numero_pagina",
    "footnote": "nota", "vision_footnote": "nota", "aside_text": "nota",
    "content": "lista", "reference": "lista", "abstract": "texto", "algorithm": "texto",
}


def _responder(d):
    _stdout.write(json.dumps(d, ensure_ascii=False) + "\n")
    _stdout.flush()


def _caja(b):
    return [int(round(v)) for v in b[:4]]


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "ocr"
    from importlib.metadata import version

    import paddleocr
    comunes = dict(lang="es", use_doc_orientation_classify=False, use_doc_unwarping=False)
    if modo == "estructura":
        motor = paddleocr.PPStructureV3(**comunes)
        ver = f"PP-StructureV3 paddleocr {version('paddleocr')} paddle {version('paddlepaddle-gpu')}"
    else:
        motor = paddleocr.PaddleOCR(**comunes)
        ver = f"PaddleOCR {version('paddleocr')} paddle {version('paddlepaddle-gpu')}"
    _responder({"listo": True, "version": ver})

    for linea in sys.stdin:
        if not linea.strip():
            continue
        try:
            img = json.loads(linea)["imagen"]
            res = motor.predict(img)[0].json["res"]
            if modo == "estructura":
                bloques = []
                for i, b in enumerate(res.get("parsing_res_list", [])):
                    orden = b.get("block_order")
                    bloques.append({
                        "texto": (b.get("block_content") or "").strip(),
                        "bbox": _caja(b["block_bbox"]),
                        "tipo": _TIPOS.get(b.get("block_label"), "desconocido"),
                        "orden": int(orden) if isinstance(orden, int) else 0,
                        "confianza": None, "revisar": False, "alternativas": []})
                # PP-StructureV3 entrega parsing_res_list ya en orden de lectura;
                # block_order solo numera los bloques de texto. El orden de la
                # lista es el que vale para todos.
                for i, b in enumerate(bloques, 1):
                    b["orden"] = i
                confs = (res.get("overall_ocr_res") or {}).get("rec_scores") or []
            else:
                textos, confs = res.get("rec_texts", []), res.get("rec_scores", [])
                cajas = res.get("rec_boxes", [])
                bloques = [{"texto": t, "bbox": _caja(c), "tipo": "texto", "orden": i + 1,
                            "confianza": round(float(s) * 100, 1), "revisar": False,
                            "alternativas": []}
                           for i, (t, c, s) in enumerate(zip(textos, cajas, confs))]
            texto = ("\n\n" if modo == "estructura" else "\n").join(
                b["texto"] for b in bloques if b["texto"])
            conf = round(100 * sum(confs) / len(confs), 1) if confs else None
            _responder({"ok": True, "texto": texto, "bloques": bloques, "confianza": conf,
                        "version": ver, "detalles": {"lineas_reconocidas": len(confs)}})
        except Exception as e:
            _responder({"ok": False, "error": f"{type(e).__name__}: {e}"})


if __name__ == "__main__":
    main()
