"""
tests/conftest.py — Fixtures compartidas para todos los tests de Bashkar Station.
"""

import json
import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def tmp_db(tmp_path):
    """Ruta a una base de datos SQLite temporal."""
    return str(tmp_path / "test.db")


@pytest.fixture
def repo(tmp_db):
    """Instancia de Repositorio sobre una DB temporal."""
    from datos.repositorio import Repositorio
    return Repositorio(tmp_db)


@pytest.fixture
def articulo_simple():
    """Artículo mínimo para tests."""
    return {
        "id":               "art_001",
        "archivo_origen":   "estampa_test.png",
        "numero":           "estampa_1939_01",
        "tipo":             "articulo",
        "titulo":           "La educacion en Colombia",
        "autor":            "German Arciniegas",
        "fecha_publicacion":"1939-01-15",
        "seccion":          "Educacion",
        "palabras":         450,
        "estado":           "pendiente",
    }


@pytest.fixture
def articulo_segundo():
    """Segundo artículo para tests que necesitan múltiples artículos."""
    return {
        "id":    "art_002",
        "tipo":  "articulo",
        "titulo":"Fotografia moderna en Colombia",
        "palabras": 220,
        "estado": "pendiente",
    }


@pytest.fixture
def entidades_ejemplo():
    """Lista de entidades NER de ejemplo."""
    return [
        {"texto": "German Arciniegas",  "categoria": "personas",       "confianza": 0.92, "fuente": "roberta_bne"},
        {"texto": "Lopez de Mesa",       "categoria": "personas",       "confianza": 0.88, "fuente": "roberta_bne"},
        {"texto": "Bogota",              "categoria": "lugares",        "confianza": 0.95, "fuente": "roberta_bne"},
        {"texto": "Colombia",            "categoria": "lugares",        "confianza": 0.97, "fuente": "roberta_bne"},
        {"texto": "Universidad Nacional","categoria": "organizaciones", "confianza": 0.85, "fuente": "spacy"},
    ]


@pytest.fixture
def zonas_ejemplo():
    """Zonas de anotación de ejemplo."""
    return [
        {"tipo": "articulo",  "x1": 0.05, "y1": 0.10, "x2": 0.48, "y2": 0.85,
         "texto_ocr": "Texto del articulo", "confianza_ocr": 0.85, "fuente": "opencv"},
        {"tipo": "titulo",    "x1": 0.05, "y1": 0.05, "x2": 0.95, "y2": 0.09,
         "texto_manual": "La educacion en Colombia", "confianza_ocr": 0.95, "fuente": "manual",
         "verificada": True},
        {"tipo": "foto",      "x1": 0.52, "y1": 0.10, "x2": 0.95, "y2": 0.60,
         "fuente": "layoutparser"},
    ]


@pytest.fixture
def bashkar_v10(tmp_path):
    """Archivo .bashkar de versión 10 para tests de migración."""
    ruta = tmp_path / "proyecto_test.bashkar"
    data = {
        "version":     "10",
        "nombre":      "Estampa Test",
        "publicacion": "Estampa",
        "periodo":     "1939",
        "config":      {"publicacion": "Estampa", "periodo": "1939", "api_key": "sk-test-xxx"},
        "articulos": [
            {
                "id":      "art_001",
                "titulo":  "La educacion en Colombia",
                "autor":   "German Arciniegas",
                "tipo":    "articulo",
                "n_palabras": 350,
                "ocr": {
                    "texto_crudo":  "La educacion en Colombia fue...",
                    "texto_limpio": "La educacion en Colombia fue...",
                    "confianza":    0.78,
                    "motor":        "tesseract",
                },
                "ner": {
                    "personas":      ["German Arciniegas", "Lopez de Mesa"],
                    "lugares":       ["Bogota", "Colombia"],
                    "organizaciones":["Universidad Nacional"],
                }
            },
            {
                "id":   "art_002",
                "tipo": "articulo",
                "titulo": "Fotografia",
                "n_palabras": 80,
            }
        ],
        "progreso":    {"ocr": True, "seg": True, "anal": False, "vis": False, "comp": False},
        "historial_ia": [],
    }
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return ruta
