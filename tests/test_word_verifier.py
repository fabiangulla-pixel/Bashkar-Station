"""tests/test_word_verifier.py — Verificador OCR palabra-por-palabra
(estilo ABBYY FineReader) + vocabulario de usuario en spell_corrector."""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import word_verifier as wv  # noqa: E402
from core.spell_corrector import (  # noqa: E402
    SpellCorrector,
    _cargar_vocab_usuario,
    _guardar_vocab_usuario,
)

TESSERACT_DISPONIBLE = shutil.which("tesseract") is not None or Path(
    "C:/Program Files/Tesseract-OCR/tesseract.exe"
).exists()


# ── aplicar_reemplazo / reemplazar_todas (puros, sin Tesseract) ─────────────

def test_aplicar_reemplazo_ocurrencia_correcta():
    texto = "el rio Bogota y el rio Cauca"
    nuevo, encontrada = wv.aplicar_reemplazo(texto, "rio", "río", idx_ocurrencia=1)
    assert encontrada is True
    assert nuevo == "el rio Bogota y el río Cauca"


def test_aplicar_reemplazo_primera_ocurrencia():
    texto = "rio Bogota, rio Cauca"
    nuevo, encontrada = wv.aplicar_reemplazo(texto, "rio", "río", idx_ocurrencia=0)
    assert encontrada is True
    assert nuevo == "río Bogota, rio Cauca"


def test_aplicar_reemplazo_no_encontrada():
    texto = "una sola mencion de rio"
    nuevo, encontrada = wv.aplicar_reemplazo(texto, "rio", "río", idx_ocurrencia=5)
    assert encontrada is False
    assert nuevo == texto  # texto intacto, no adivina posición


def test_aplicar_reemplazo_no_toca_subcadenas():
    texto = "el rioja no es rio"
    # "rio" solo debe casar como palabra completa, no dentro de "rioja"
    nuevo, encontrada = wv.aplicar_reemplazo(texto, "rio", "río", idx_ocurrencia=0)
    assert encontrada is True
    assert nuevo == "el rioja no es río"


def test_reemplazar_todas():
    texto = "rio Bogota, rio Cauca, rioja no cuenta"
    nuevo, n = wv.reemplazar_todas(texto, "rio", "río")
    assert n == 2
    assert nuevo == "río Bogota, río Cauca, rioja no cuenta"


def test_reemplazar_todas_sin_coincidencias():
    nuevo, n = wv.reemplazar_todas("texto sin la palabra", "xyz", "abc")
    assert n == 0
    assert nuevo == "texto sin la palabra"


# ── sugerencias_para (corpus + corrector, sin Tesseract) ────────────────────

def test_sugerencias_para_usa_frecuencia_del_corpus():
    dicc = {"bogota": 40, "bogotano": 3, "gobierno": 12}
    sugerencias = wv.sugerencias_para("bogotta", corrector=None, dicc_corpus=dicc)
    assert "bogota" in sugerencias


def test_sugerencias_para_sin_corpus_ni_corrector():
    assert wv.sugerencias_para("palabra", corrector=None, dicc_corpus=None) == []


def test_sugerencias_para_no_incluye_la_original():
    dicc = {"bogota": 40}
    sugerencias = wv.sugerencias_para("bogota", corrector=None, dicc_corpus=dicc)
    assert "bogota" not in sugerencias


# ── vocabulario de usuario (spell_corrector) ────────────────────────────────

def _redirigir_vocab(monkeypatch, tmp_path):
    ruta = tmp_path / ".bashkar" / "vocab_usuario.json"
    monkeypatch.setattr("core.spell_corrector._VOCAB_USUARIO_PATH", ruta)
    return ruta


def test_agregar_palabra_usuario_persiste(monkeypatch, tmp_path):
    ruta = _redirigir_vocab(monkeypatch, tmp_path)
    sc = SpellCorrector()
    sc.agregar_palabra_usuario("Piquillo")
    assert ruta.exists()
    assert "piquillo" in _cargar_vocab_usuario()


def test_palabra_usuario_pasa_a_lista_blanca(monkeypatch, tmp_path):
    _redirigir_vocab(monkeypatch, tmp_path)
    sc = SpellCorrector()
    assert sc._en_lista_blanca("piquillopio") is False
    sc.agregar_palabra_usuario("PiquilloPio")
    assert sc._en_lista_blanca("piquillopio") is True


def test_vocab_usuario_se_carga_en_nueva_instancia(monkeypatch, tmp_path):
    ruta = _redirigir_vocab(monkeypatch, tmp_path)
    _guardar_vocab_usuario({"matadero"})
    sc = SpellCorrector()
    assert sc._en_lista_blanca("matadero") is True
    assert ruta.exists()


def test_cargar_vocab_usuario_archivo_corrupto_no_lanza(monkeypatch, tmp_path):
    ruta = _redirigir_vocab(monkeypatch, tmp_path)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("no es json valido", encoding="utf-8")
    assert _cargar_vocab_usuario() == set()


# ── extraer_palabras_dudosas / recortar_palabra (requieren Tesseract real) ──

def _pagina_sintetica(path: Path):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (600, 120), "white")
    d = ImageDraw.Draw(img)
    d.text((10, 40), "Bogota es la capital", fill="black")
    img.save(path)
    return img


def test_extraer_palabras_dudosas_estructura(tmp_path):
    if not TESSERACT_DISPONIBLE:
        import pytest
        pytest.skip("Tesseract no disponible")
    from PIL import Image
    p = tmp_path / "pagina.png"
    _pagina_sintetica(p)
    img = Image.open(p)
    palabras = wv.extraer_palabras_dudosas(img, umbral_conf=101)  # todo cae bajo el umbral
    assert isinstance(palabras, list)
    if palabras:
        pd = palabras[0]
        assert pd.x1 > pd.x0 and pd.y1 > pd.y0
        assert isinstance(pd.contexto, str)


def test_recortar_palabra_devuelve_imagen_ampliada(tmp_path):
    if not TESSERACT_DISPONIBLE:
        import pytest
        pytest.skip("Tesseract no disponible")
    from PIL import Image
    p = tmp_path / "pagina.png"
    _pagina_sintetica(p)
    img = Image.open(p)
    palabras = wv.extraer_palabras_dudosas(img, umbral_conf=101)
    assert palabras, "la página sintética debería producir al menos una palabra"
    recorte = wv.recortar_palabra(img, palabras[0], margen=4, zoom=2.0)
    ancho_esperado = (palabras[0].x1 - palabras[0].x0 + 8) * 2
    assert abs(recorte.width - ancho_esperado) <= 4  # tolerancia por redondeo
