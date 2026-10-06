"""api/app.py con el cliente de pruebas de FastAPI (sin red, sin GPU)."""

import io

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import servidor_web as W  # noqa: E402
from api.app import app  # noqa: E402
from core.ocr import Bloque, ResultadoOCR  # noqa: E402


@pytest.fixture
def cliente(monkeypatch, tmp_path):
    monkeypatch.setattr(W, "MODO_PUBLICO", False)
    monkeypatch.setattr(W, "ESTADO_LOCAL", W.EstadoServidor())
    return TestClient(app)


@pytest.fixture
def publico(monkeypatch):
    monkeypatch.setattr(W, "MODO_PUBLICO", True)
    monkeypatch.setattr(W, "PASSWORD", "secreta")
    monkeypatch.setattr(W, "SESIONES", {})
    return TestClient(app)


class _Motor:
    nombre = etiqueta = "falso"

    def motivo_no_disponible(self):
        return None

    def version(self):
        return "falso 1"

    def reconocer(self, imagen):
        return ResultadoOCR("texto de prueba", "falso", "falso 1", confianza=90.0,
                            bloques=[Bloque("texto de prueba", (1, 2, 30, 40), tipo="titulo")])

    def liberar(self):
        pass


def test_salud_y_sistema(cliente):
    assert cliente.get("/api/v1/salud").json()["ok"]
    s = cliente.get("/api/v1/sistema").json()
    assert "gpu" in s and s["paridad"]["con_api"] >= 1


def test_paridad_listada(cliente):
    ops = cliente.get("/api/v1/paridad").json()
    assert any(o["clave"] == "ocr" and o["api"] for o in ops)


def test_flujo_proyecto_local(cliente, tmp_path, monkeypatch):
    from core import project_manager as pm
    monkeypatch.setattr(pm, "nuevo_proyecto", lambda n, p, per: _proyecto(tmp_path, n))
    r = cliente.post("/api/v1/proyectos", json={"nombre": "prueba", "publicacion": "Estampa"})
    assert r.status_code == 200 and r.json()["publicacion"] == "Estampa"
    assert cliente.get("/api/v1/estado").json()["proyecto"] == "prueba"


def _proyecto(tmp_path, nombre):
    import json
    ruta = tmp_path / f"{nombre}.bashkar"
    ruta.write_text(json.dumps({"nombre": nombre, "config": {}}), "utf-8")
    return ruta


def test_ocr_pagina_con_motor_explicito(cliente, monkeypatch):
    import core.ocr as ocr
    monkeypatch.setattr(ocr, "crear", lambda n, **k: _Motor())
    r = cliente.post("/api/v1/ocr/pagina", data={"motor": "falso"},
                     files={"imagen": ("p0001.png", io.BytesIO(b"x"), "image/png")})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["texto"] == "texto de prueba"
    assert d["bloques"][0]["bbox"] == [1, 2, 30, 40]
    assert d["procedencia"]["metodo"] == "falso" and "txt_path" not in d["procedencia"]


def test_ocr_iniciar_sin_proyecto_es_400(cliente):
    assert cliente.post("/api/v1/ocr/iniciar", json={}).status_code == 400


def test_trabajo_inexistente_404(cliente):
    assert cliente.get("/api/v1/trabajos/nada").status_code == 404


def test_exportar_formato_desconocido_400(cliente):
    assert cliente.post("/api/v1/exportar", json={"formato": "zzz"}).status_code == 400


def test_subir_archivo(cliente):
    r = cliente.post("/api/v1/subir", files={"archivo": ("a.pdf", io.BytesIO(b"%PDF-1"), "x")})
    assert r.json() == {"nombre": "a.pdf", "bytes": 6}


def test_subir_vacio_400(cliente):
    r = cliente.post("/api/v1/subir", files={"archivo": ("a.pdf", io.BytesIO(b""), "x")})
    assert r.status_code == 400


def test_subir_no_escapa_de_la_carpeta(cliente):
    r = cliente.post("/api/v1/subir",
                     files={"archivo": ("../../fuera.pdf", io.BytesIO(b"x"), "x")})
    assert r.json()["nombre"] == "fuera.pdf"


# ── modo público ─────────────────────────────────────────────────────────────
def test_publico_exige_token(publico):
    assert publico.get("/api/v1/estado").status_code == 401
    assert publico.post("/api/v1/sesiones", json={"password": "mala"}).status_code == 401
    token = publico.post("/api/v1/sesiones", json={"password": "secreta"}).json()["token"]
    r = publico.get("/api/v1/estado", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["ruta_proyecto"] is None


def test_publico_benchmark_prohibido(publico):
    token = publico.post("/api/v1/sesiones", json={"password": "secreta"}).json()["token"]
    r = publico.post("/api/v1/benchmark", json={},
                     headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_publico_sesiones_aisladas(publico):
    t1 = publico.post("/api/v1/sesiones", json={"password": "secreta"}).json()["token"]
    t2 = publico.post("/api/v1/sesiones", json={"password": "secreta"}).json()["token"]
    publico.post("/api/v1/subir", files={"archivo": ("uno.pdf", io.BytesIO(b"x"), "x")},
                 headers={"Authorization": f"Bearer {t1}"})
    assert W.SESIONES[t1].dir_trabajo != W.SESIONES[t2].dir_trabajo
    assert not (W.SESIONES[t2].dir_trabajo / "subidas" / "uno.pdf").exists()
