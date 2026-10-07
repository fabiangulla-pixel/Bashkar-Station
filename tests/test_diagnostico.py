"""core/diagnostico: informe JSON sin abrir la ventana (BashkarStation.exe --diagnostico)."""

import json

from core import diagnostico


def test_informe_tiene_todas_las_pruebas_y_se_escribe(tmp_path, monkeypatch):
    for nombre in ("_importaciones", "_gpu", "_ner", "_embeddings", "_spacy", "_motores", "_plan_ocr"):
        monkeypatch.setattr(diagnostico, nombre, lambda: {"falso": True})
    destino = tmp_path / "d.json"
    inf = diagnostico.ejecutar(destino, ocr=False)
    assert inf["ok"] and [p["prueba"] for p in inf["pruebas"]] == ["importaciones",
        "gpu", "ner_roberta", "embeddings", "spacy", "motores_ocr", "plan_enrutador"]
    assert json.loads(destino.read_text("utf-8"))["ok"]


def test_una_prueba_que_falla_no_tumba_las_demas(monkeypatch, tmp_path):
    def revienta():
        raise RuntimeError("sin CUDA")
    monkeypatch.setattr(diagnostico, "_gpu", revienta)
    for nombre in ("_importaciones", "_ner", "_embeddings", "_spacy", "_motores", "_plan_ocr"):
        monkeypatch.setattr(diagnostico, nombre, lambda: "ok")
    inf = diagnostico.ejecutar(None, ocr=False)
    assert not inf["ok"]
    assert inf["pruebas"][1]["detalle"] == "RuntimeError: sin CUDA"
    assert sum(not p["ok"] for p in inf["pruebas"]) == 1


def test_main_devuelve_codigo_de_salida(monkeypatch, tmp_path):
    monkeypatch.setattr(diagnostico, "ejecutar", lambda destino, ocr=True: {"ok": False})
    assert diagnostico.main(["app.py", "--diagnostico", str(tmp_path / "x.json")]) == 1
