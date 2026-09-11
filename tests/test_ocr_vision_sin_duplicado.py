"""tests/test_ocr_vision_sin_duplicado.py — el OCR por visión se implementa
UNA sola vez, en `core/ocr_llm.py`.

`app.py` llevaba su propia `_ocr_vision_multiproveedor`, y la Ruta 2 de la
interfaz —la que consume API de pago— llamaba a esa, no a la de `core`. La copia
había quedado atrás en cuatro cosas a la vez, todas silenciosas:

1. **El prompt.** El de `core` está calibrado contra las 46 páginas del juez de
   ground truth: pide `[ilegible]` en vez de adivinar (el error más frecuente
   medido), conservar la ortografía de época y marcar `--- COLUMNA ---`. El de
   `app.py` era genérico y no pedía nada de eso, así que el marcador de columna
   que el resto del pipeline sabe limpiar ni siquiera se generaba.
2. **El gasto.** `core` registra el `usage` de cada llamada; la copia no
   registraba nada. El OCR de visión lanzado desde la interfaz no aparecía en
   ningún cómputo de costo.
3. **Los rechazos.** `core` descarta las respuestas en que el modelo contesta
   "No puedo transcribir…" en vez de transcribir; la copia las guardaba como si
   fueran la página.
4. **`return ""` mudo** ante un proveedor desconocido: un .txt vacío y éxito
   reportado.

Este test no comprueba el OCR —eso ya tiene sus tests— sino que no exista una
segunda implementación donde volver a divergir.
"""

import ast
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
APP = RAIZ / "app.py"


def _arbol_app():
    return ast.parse(APP.read_text(encoding="utf-8"))


def test_app_no_define_su_propio_ocr_de_vision():
    nombres = {n.name for n in ast.walk(_arbol_app())
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert "_ocr_vision_multiproveedor" not in nombres, (
        "app.py volvió a definir su propio OCR de visión. La implementación "
        "única es core.ocr_llm.ocr_con_vision."
    )


def test_app_no_arma_peticiones_de_vision_a_mano():
    """Ninguna función de app.py debe construir el cuerpo de una petición de
    visión: eso es lo que hacía la copia, y es por donde diverge el prompt."""
    fuente = APP.read_text(encoding="utf-8")
    sospechosos = [
        '"type": "image"',
        '"image_url"',
        "generate_content([",
        "localhost:11434/api/generate",
    ]
    encontrados = [s for s in sospechosos if s in fuente]
    assert not encontrados, (
        f"app.py arma peticiones de visión a mano ({encontrados}). "
        "Debe delegar en core.ocr_llm."
    )


def test_app_no_lleva_su_propio_prompt_de_ocr():
    fuente = APP.read_text(encoding="utf-8")
    assert not re.search(r"Transcribe .{0,80}texto .{0,80}imagen", fuente, re.S), (
        "Hay un prompt de transcripción en app.py. El prompt de visión es uno "
        "solo y vive en core/ocr_llm.py (_PROMPT_VISION), calibrado contra el "
        "juez de ground truth."
    )


def test_la_ruta_2_llama_a_core_ocr_llm():
    fuente = APP.read_text(encoding="utf-8")
    assert "from core.ocr_llm import ocr_con_vision" in fuente
    assert "ocr_con_vision(" in fuente


def test_el_prompt_de_core_sigue_pidiendo_lo_que_se_calibro():
    """Si alguien simplifica _PROMPT_VISION, se pierde lo que costó 46 páginas
    de ground truth averiguar."""
    from core.ocr_llm import _PROMPT_VISION

    for exigencia in ("[ilegible]", "--- COLUMNA ---", "no modernices"):
        assert exigencia in _PROMPT_VISION, (
            f"El prompt de visión ya no pide «{exigencia}»."
        )


def test_core_registra_el_gasto_de_cada_transcripcion():
    """El estándar de costo de IA del proyecto exige registrar el consumo real."""
    import inspect

    from core import ocr_llm

    fuente = inspect.getsource(ocr_llm.ocr_con_vision)
    assert "_registrar_usage" in fuente, (
        "ocr_con_vision dejó de registrar el usage: el gasto de la Ruta 2 "
        "volvería a ser invisible."
    )
