"""Tests del extractor multimodal estructurado (imagen → JSON → .md / corpus).

Usa como fixture el JSON real de la página 20 de Estampa ("De la vida y la
muerte: lo que va de un bisté a un tango dramático", Piquillo Pío) extraído por
Gemini — el mejor caso de validación disponible. No llama a ninguna API: el
proveedor se mockea inyectando la respuesta cruda.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import extractor_multimodal as em

# ── Fixture: salida real de la IA sobre la página del matadero ───────────────

PAGINA_MATADERO = {
    "pagina_metadata": {
        "numero_pagina": 20,
        "fuente_digital": "Digitalizado Biblioteca Nacional de Colombia",
        "contexto_historico_estimado": "Circa 1938-1940",
    },
    "articulo_principal": {
        "titulo": "De la vida y la muerte: LO QUE VA DE UN BISTÉ A UN TANGO DRAMÁTICO",
        "antetitulo_subtitulo": "EL MATADERO MUNICIPAL.—350 ANIMALES MUEREN DIARIAMENTE.",
        "autor": "Piquillo Pío",
        "bloques_contenido": [
            {"tipo": "parrafo_introductorio",
             "texto": "Cuando usted, lector, llega a un restaurante..."},
            {"tipo": "parrafo_transicion",
             "texto": "Déle usted vacaciones a sus carrillos..."},
            {"tipo": "seccion", "subtitulo": "Los animalitos.",
             "parrafos": ["Luis Antonio Chivas, aquel negro trashumante...",
                          "Así, lector, es conveniente..."]},
            {"tipo": "seccion", "subtitulo": "El Matadero.",
             "parrafos": ["El actual Matadero Municipal es el resultado..."]},
        ],
    },
    "imagenes_registro": [
        {"id_imagen": 1, "posicion_relativa": "Superior Izquierda",
         "descripcion_contenido": "Grupo de obreros del matadero",
         "pie_de_pagina": "capitanes de la muerte. Matarifes, ayudantes..."},
        {"id_imagen": 2, "posicion_relativa": "Superior Centro-Izquierda",
         "descripcion_contenido": "Matarife con un mazo",
         "pie_de_pagina": "El poderoso matarife acaba de asestarle el mazazo..."},
    ],
    "bloque_publicitario": [
        {"id_anuncio": 1, "entidad": "Lotería de Manizales", "tipo": "Sorteo Especial",
         "glosa_texto": "Extraordinario de $20.000,00 el Sábado Santo"},
        {"id_anuncio": 2, "entidad": "Banco Central Hipotecario",
         "tipo": "Financiero", "glosa_texto": "CEDULAS DE CAPITALIZACION"},
    ],
}

RAW_OK = json.dumps(PAGINA_MATADERO, ensure_ascii=False)


# ── _extraer_json: parseo tolerante ──────────────────────────────────────────

def test_extraer_json_directo():
    obj = em._extraer_json(RAW_OK)
    assert obj["articulo_principal"]["autor"] == "Piquillo Pío"


def test_extraer_json_con_fences():
    raw = "```json\n" + RAW_OK + "\n```"
    obj = em._extraer_json(raw)
    assert obj["pagina_metadata"]["numero_pagina"] == 20


def test_extraer_json_con_prosa_alrededor():
    raw = "Aquí tienes el JSON solicitado:\n" + RAW_OK + "\nEspero que sea útil."
    obj = em._extraer_json(raw)
    assert len(obj["imagenes_registro"]) == 2


def test_extraer_json_vacio_falla():
    with pytest.raises(em.JSONInvalidoError):
        em._extraer_json("   ")


def test_extraer_json_malformado_falla():
    with pytest.raises(em.JSONInvalidoError):
        em._extraer_json("{ esto no es json }")


def test_extraer_json_no_objeto_falla():
    with pytest.raises(em.JSONInvalidoError):
        em._extraer_json("[1, 2, 3]")


# ── validar_pagina: normalización y guardas ──────────────────────────────────

def test_validar_pagina_completa():
    norm = em.validar_pagina(PAGINA_MATADERO)
    assert norm["articulo_principal"]["titulo"].startswith("De la vida")
    assert len(norm["bloque_publicitario"]) == 2


def test_validar_pagina_rellena_faltantes():
    norm = em.validar_pagina({"articulo_principal": {"titulo": "X"}})
    assert norm["imagenes_registro"] == []
    assert norm["bloque_publicitario"] == []
    assert norm["pagina_metadata"] == {}


def test_validar_pagina_sin_contenido_falla():
    with pytest.raises(em.JSONInvalidoError):
        em.validar_pagina({"articulo_principal": {"titulo": ""}})


def test_validar_pagina_solo_imagenes_es_valida():
    norm = em.validar_pagina({"imagenes_registro": [{"id_imagen": 1, "pie_de_pagina": "x"}]})
    assert len(norm["imagenes_registro"]) == 1


def test_validar_pagina_tipos_corruptos_se_sanean():
    # bloques_contenido como string en vez de lista → se normaliza a []
    norm = em.validar_pagina({"articulo_principal": {"titulo": "X",
                                                     "bloques_contenido": "basura"}})
    assert norm["articulo_principal"]["bloques_contenido"] == []


# ── json_a_markdown ──────────────────────────────────────────────────────────

def test_markdown_estructura():
    md = em.json_a_markdown(PAGINA_MATADERO)
    assert md.startswith("# De la vida")
    assert "**Autor:** Piquillo Pío" in md
    assert "## Los animalitos." in md
    assert "## Imágenes" in md
    assert "## Publicidad" in md
    assert "Lotería de Manizales" in md
    assert "capitanes de la muerte" in md


def test_markdown_sin_imagenes_ni_publicidad():
    datos = {"articulo_principal": {"titulo": "Solo texto",
                                    "bloques_contenido": [{"tipo": "parrafo_introductorio",
                                                           "texto": "Hola"}]}}
    md = em.json_a_markdown(datos)
    assert "## Imágenes" not in md
    assert "## Publicidad" not in md
    assert "Hola" in md


# ── Puentes al pipeline ──────────────────────────────────────────────────────

def test_texto_plano_incluye_cuerpo_no_pies():
    txt = em.json_a_texto_plano(PAGINA_MATADERO)
    assert "De la vida y la muerte" in txt
    assert "Los animalitos." in txt
    assert "El actual Matadero Municipal" in txt
    # los pies de foto NO deben contaminar el cuerpo del artículo
    assert "capitanes de la muerte" not in txt
    # ni la publicidad
    assert "Lotería de Manizales" not in txt


def test_texto_plano_apto_para_corpus_txt():
    txt = em.json_a_texto_plano(PAGINA_MATADERO)
    assert isinstance(txt, str) and len(txt) > 50


def test_publicidad_normalizada():
    pub = em.json_a_publicidad(PAGINA_MATADERO)
    assert len(pub) == 2
    assert pub[0]["entidad"] == "Lotería de Manizales"
    assert set(pub[0].keys()) == {"entidad", "tipo", "glosa_texto"}


# ── listar_imagenes ──────────────────────────────────────────────────────────

def test_listar_imagenes(tmp_path):
    (tmp_path / "p0002.png").write_bytes(b"x")
    (tmp_path / "p0001.jpg").write_bytes(b"x")
    (tmp_path / "notas.txt").write_text("ignorar")
    (tmp_path / "p0003.tif").write_bytes(b"x")
    imgs = em.listar_imagenes(tmp_path)
    assert [p.name for p in imgs] == ["p0001.jpg", "p0002.png", "p0003.tif"]


def test_listar_imagenes_no_carpeta(tmp_path):
    f = tmp_path / "x.jpg"
    f.write_bytes(b"x")
    with pytest.raises(NotADirectoryError):
        em.listar_imagenes(f)


# ── extraer_pagina (proveedor mockeado) ──────────────────────────────────────

def _mock_proveedor(monkeypatch, raw: str):
    """Hace que extraer_pagina no llame a ninguna API: parchea la rama gemini
    sustituyendo google.generativeai por un stub que devuelve `raw`."""
    import sys
    import types

    class _Resp:
        text = raw

    class _Model:
        def __init__(self, *a, **k):
            pass

        def generate_content(self, *a, **k):
            return _Resp()

    stub = types.SimpleNamespace(
        configure=lambda **k: None,
        GenerativeModel=_Model,
    )
    monkeypatch.setitem(sys.modules, "google.generativeai", stub)


def _png_real(path: Path):
    """Escribe un PNG 2x2 decodificable (la rama gemini abre la imagen con PIL)."""
    from PIL import Image
    Image.new("RGB", (2, 2), (255, 255, 255)).save(path, "PNG")


def test_extraer_pagina_gemini_mock(tmp_path, monkeypatch):
    img = tmp_path / "p0020.png"
    _png_real(img)
    _mock_proveedor(monkeypatch, RAW_OK)
    datos = em.extraer_pagina(img, api_key="fake", proveedor="gemini")
    assert datos["articulo_principal"]["autor"] == "Piquillo Pío"


def test_extraer_pagina_imagen_inexistente():
    with pytest.raises(FileNotFoundError):
        em.extraer_pagina("no_existe_xyz.png", api_key="fake", proveedor="gemini")


def test_extraer_pagina_proveedor_desconocido(tmp_path):
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    with pytest.raises(ValueError):
        em.extraer_pagina(img, api_key="fake", proveedor="inexistente")


# ── procesar_directorio: robustez (una página fallida no detiene el lote) ─────

def test_procesar_directorio_robusto(tmp_path, monkeypatch):
    carpeta = tmp_path / "imgs"
    carpeta.mkdir()
    (carpeta / "p0001.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (carpeta / "p0002.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    out = tmp_path / "out"

    # p0001 → JSON válido; p0002 → respuesta basura (debe marcar fallida, no romper)
    llamadas = {"n": 0}

    def fake_extraer(img_path, api_key, proveedor="gemini", modelo=None, prompt=em.PROMPT_MAESTRO):
        llamadas["n"] += 1
        if Path(img_path).stem == "p0002":
            raise em.JSONInvalidoError("ilegible")
        return em.validar_pagina(PAGINA_MATADERO)

    monkeypatch.setattr(em, "extraer_pagina", fake_extraer)

    progreso = []
    res = em.procesar_directorio(carpeta, "fake", out,
                                 callback=lambda i, t, r: progreso.append((i, t, r.ok)))

    assert len(res) == 2
    assert res[0].ok is True and res[1].ok is False
    assert (out / "p0001.json").exists()
    assert (out / "p0001.md").exists()
    assert not (out / "p0002.json").exists()  # la fallida no escribe archivos
    assert progreso == [(1, 2, True), (2, 2, False)]


def test_resumen_lote(tmp_path, monkeypatch):
    carpeta = tmp_path / "imgs"
    carpeta.mkdir()
    (carpeta / "p0001.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    out = tmp_path / "out"
    monkeypatch.setattr(em, "extraer_pagina",
                        lambda *a, **k: em.validar_pagina(PAGINA_MATADERO))
    res = em.procesar_directorio(carpeta, "fake", out)
    resumen = em.resumen_lote(res)
    assert resumen["ok"] == 1
    assert resumen["imagenes_detectadas"] == 2
    assert resumen["anuncios_detectados"] == 2
    assert resumen["fallidas"] == 0


# ── estimación de costo (estándar costo-IA) ──────────────────────────────────

def test_estimar_costo_directorio(tmp_path):
    carpeta = tmp_path / "imgs"
    carpeta.mkdir()
    for i in range(5):
        (carpeta / f"p{i:04d}.png").write_bytes(b"x")
    est = em.estimar_costo_directorio(carpeta, proveedor="gemini")
    assert est.n_items == 5
    assert est.n_imagenes == 5  # todas por visión


def test_estimar_costo_ollama_es_local(tmp_path):
    carpeta = tmp_path / "imgs"
    carpeta.mkdir()
    (carpeta / "p0001.png").write_bytes(b"x")
    est = em.estimar_costo_directorio(carpeta, proveedor="ollama", modelo="llava")
    assert est.costo_usd == 0.0
