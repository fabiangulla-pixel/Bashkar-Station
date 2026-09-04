"""tests/test_churro_offline_orden.py — HF_HUB_OFFLINE antes de importar nada.

Regresión de un segfault reproducible (3-sep-2026). `ocr_churro._cargar()`
fijaba `HF_HUB_OFFLINE` justo antes de `import torch` / `from transformers
import ...`, lo cual PARECE bastante temprano y no lo es: la llamada anterior,
`motivo_no_disponible()`, usa `importlib.util.find_spec()`, que con estos
paquetes **ejecuta el módulo**. Medido: antes de esa llamada ni torch ni
transformers ni huggingface_hub están en `sys.modules`; después, los tres.

Con `huggingface_hub` ya importado, su constante interna queda congelada en
`False` y fijar la variable después deja al proceso con dos verdades sobre si
hay red. La carga del procesador revienta en código nativo: 0xC0000005 en
Windows, código 139 en bash, **sin stderr ni traza de Python**. Comprobado con
el mismo script cambiando solo el orden: antes del import -> salida 0; después
-> 139.

Es la MISMA causa raíz que la sesión 63 arregló en `ner_roberta_local.py`. El
test que la guardaba (`test_hf_offline_cacheado.py`) cubría ese módulo y
`embeddings_local`, y su docstring daba por bueno que `ocr_churro` ya lo tenía
—«Mismo patrón que ocr_churro.py ya tenía para CHURRO»—. No lo tenía. De ahí
que reapareciera: la lógica está copiada en tres módulos en vez de compartida.

Este test no carga el modelo (son 7,5 GB): corta la ejecución en el punto exacto
donde importa el orden y comprueba el estado en ese instante.
"""

import sys

import pytest

import core.ocr_churro as ocr_churro


class _Corte(Exception):
    """Detiene _cargar() en la comprobación, sin llegar a importar la pila."""


@pytest.fixture(autouse=True)
def _sin_modelo_en_memoria(monkeypatch):
    """_cargar() devuelve pronto si ya hay modelo cargado; forzar que no."""
    monkeypatch.setattr(ocr_churro, "_modelo", None)
    monkeypatch.setattr(ocr_churro, "_procesador", None)


def test_offline_se_fija_antes_de_la_comprobacion_de_disponibilidad(monkeypatch):
    """`motivo_no_disponible()` importa torch/transformers/huggingface_hub.

    Si la variable no está puesta ANTES de esa llamada, ya es tarde.
    """
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.setattr(ocr_churro, "esta_descargado", lambda: True)
    monkeypatch.setattr(ocr_churro, "_carpeta_modelo_local", lambda: None)

    visto = {}

    def _espia():
        visto["offline"] = ocr_churro.os.environ.get("HF_HUB_OFFLINE")
        raise _Corte

    monkeypatch.setattr(ocr_churro, "motivo_no_disponible", _espia)

    with pytest.raises(_Corte):
        ocr_churro._cargar()

    assert visto["offline"] == "1", (
        "HF_HUB_OFFLINE debe estar fijada ANTES de motivo_no_disponible(), "
        "que importa toda la pila de ML y congela la constante de "
        "huggingface_hub. Ponerla después provoca un segfault sin traza."
    )


def test_no_fuerza_offline_si_el_modelo_no_esta_descargado(monkeypatch):
    """Sin modelo en caché hay que poder ir a la red a buscarlo."""
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.setattr(ocr_churro, "esta_descargado", lambda: False)
    monkeypatch.setattr(ocr_churro, "_carpeta_modelo_local", lambda: None)
    monkeypatch.setattr(ocr_churro, "motivo_no_disponible", lambda: (_ for _ in ()).throw(_Corte()))

    with pytest.raises(_Corte):
        ocr_churro._cargar()

    assert ocr_churro.os.environ.get("HF_HUB_OFFLINE") is None


def test_respeta_un_valor_puesto_por_el_usuario(monkeypatch):
    """Se usa setdefault: si el entorno ya trae un valor, manda ese."""
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setattr(ocr_churro, "esta_descargado", lambda: True)
    monkeypatch.setattr(ocr_churro, "_carpeta_modelo_local", lambda: None)
    monkeypatch.setattr(ocr_churro, "motivo_no_disponible", lambda: (_ for _ in ()).throw(_Corte()))

    with pytest.raises(_Corte):
        ocr_churro._cargar()

    assert ocr_churro.os.environ.get("HF_HUB_OFFLINE") == "0"


def test_la_comprobacion_de_disponibilidad_importa_la_pila_de_ml():
    """Documenta el efecto secundario que hace necesario todo lo anterior.

    `motivo_no_disponible()` parece barata y no lo es. La GUI la llama al pintar
    el catálogo de rutas de OCR (`app.py`), así que abrir ese panel carga torch
    y transformers en memoria sin que nadie lo pida. Si algún día deja de tener
    este efecto, este test falla y se puede simplificar el orden de `_cargar()`.
    """
    ocr_churro.motivo_no_disponible()

    assert "huggingface_hub" in sys.modules or "transformers" in sys.modules, (
        "Si motivo_no_disponible() ya no importa la pila de ML, revisar si "
        "sigue haciendo falta fijar HF_HUB_OFFLINE tan temprano en _cargar()."
    )
