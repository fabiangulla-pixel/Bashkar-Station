"""tests/test_page_quality.py — Avisos de calidad por página (DPI, página
vacía, confianza baja) + miniaturas en caché local."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import page_quality as pq  # noqa: E402


def _png(path: Path, size=(100, 100), dpi=None):
    from PIL import Image
    img = Image.new("RGB", size, "white")
    if dpi:
        img.save(path, dpi=dpi)
    else:
        img.save(path)


# ── dpi_de_imagen ────────────────────────────────────────────────────────────

def test_dpi_de_imagen_con_metadato(tmp_path):
    p = tmp_path / "img.png"
    _png(p, dpi=(300, 300))
    assert pq.dpi_de_imagen(p) == 300


def test_dpi_de_imagen_sin_metadato(tmp_path):
    p = tmp_path / "img.png"
    _png(p)
    assert pq.dpi_de_imagen(p) is None


def test_dpi_de_imagen_archivo_inexistente_no_lanza(tmp_path):
    assert pq.dpi_de_imagen(tmp_path / "no_existe.png") is None


# ── es_pagina_vacia (umbrales exactos de FineReader: ≤2 letras, ≤20 tokens) ──

def test_pagina_vacia_sin_texto():
    assert pq.es_pagina_vacia("") is True


def test_pagina_vacia_dos_letras_exactas():
    assert pq.es_pagina_vacia("a b") is True  # 2 letras, en el límite


def test_pagina_no_vacia_tres_letras():
    assert pq.es_pagina_vacia("abc") is False  # 3 letras, supera el límite


def test_pagina_vacia_respeta_n_tokens():
    # pocas letras pero muchos tokens (ruido/números) → no se considera vacía
    assert pq.es_pagina_vacia("1 2 3", n_tokens=25) is False


def test_pagina_vacia_n_tokens_bajo_limite():
    assert pq.es_pagina_vacia("", n_tokens=20) is True


# ── evaluar_pagina ───────────────────────────────────────────────────────────

def test_evaluar_pagina_dpi_bajo(tmp_path):
    p = tmp_path / "p0001.png"
    _png(p)
    avisos = pq.evaluar_pagina(p, "texto normal de la pagina", conf=80, dpi=150)
    codigos = [a.codigo for a in avisos]
    assert "dpi_bajo" in codigos


def test_evaluar_pagina_dpi_suficiente_no_avisa(tmp_path):
    p = tmp_path / "p0001.png"
    _png(p)
    avisos = pq.evaluar_pagina(p, "texto normal de la pagina con contenido real",
                                conf=80, dpi=300, n_tokens=50)
    assert avisos == []


def test_evaluar_pagina_estima_por_tamano_sin_dpi(tmp_path):
    p = tmp_path / "p0001.png"
    _png(p, size=(1000, 1200))  # alto bajo la cota ALTO_PX_MINIMO_SIN_DPI
    avisos = pq.evaluar_pagina(p, "texto suficiente para no marcar vacia aqui",
                                conf=80, img_size=(1000, 1200), n_tokens=50)
    assert any(a.codigo == "dpi_bajo" for a in avisos)


def test_evaluar_pagina_vacia(tmp_path):
    p = tmp_path / "p0002.png"
    _png(p)
    avisos = pq.evaluar_pagina(p, "", conf=0, dpi=300)
    assert any(a.codigo == "pagina_vacia" for a in avisos)


def test_evaluar_pagina_confianza_baja(tmp_path):
    p = tmp_path / "p0003.png"
    _png(p)
    avisos = pq.evaluar_pagina(p, "texto largo suficiente para no ser pagina vacia aqui",
                                conf=15, dpi=300, n_tokens=50)
    assert any(a.codigo == "conf_baja" for a in avisos)


def test_evaluar_pagina_no_reabre_imagen_si_recibe_size_y_dpi(tmp_path, monkeypatch):
    p = tmp_path / "no_existe_de_verdad.png"  # nunca se crea

    def _falla(*a, **k):
        raise AssertionError("no debería reabrir la imagen si ya se pasó dpi/size")
    monkeypatch.setattr("PIL.Image.open", _falla)

    avisos = pq.evaluar_pagina(p, "texto suficiente para pasar sin abrir la imagen aqui",
                                conf=80, dpi=300, n_tokens=50, img_size=(100, 100))
    assert avisos == []


# ── generar_miniatura (caché local) ──────────────────────────────────────────

def test_generar_miniatura_crea_y_reusa_cache(tmp_path):
    p = tmp_path / "pagina.png"
    _png(p, size=(400, 800))
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    destino1 = pq.generar_miniatura(p, cache_dir, alto=140)
    assert destino1.exists()
    from PIL import Image
    with Image.open(destino1) as im:
        assert im.height == 140

    mtime_1 = destino1.stat().st_mtime
    destino2 = pq.generar_miniatura(p, cache_dir, alto=140)
    assert destino2 == destino1
    assert destino2.stat().st_mtime == mtime_1  # no se regeneró


def test_generar_miniatura_cambia_si_la_imagen_cambia(tmp_path):
    import time
    p = tmp_path / "pagina.png"
    _png(p, size=(400, 800))
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    destino1 = pq.generar_miniatura(p, cache_dir)
    time.sleep(0.01)
    _png(p, size=(500, 900))  # "cambia" el archivo (mtime+tamaño distintos)
    destino2 = pq.generar_miniatura(p, cache_dir)
    assert destino1 != destino2
