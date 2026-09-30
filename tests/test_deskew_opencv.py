"""El enderezado funciona con la forma de salida de HoughLinesP de OpenCV 4 y 5."""

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")
Image = pytest.importorskip("PIL.Image")

from core import image_preprocessor as IP  # noqa: E402


def _pagina_inclinada(grados: float):
    img = Image.new("L", (1200, 1600), 255)
    arr = np.array(img)
    for y in range(150, 1450, 40):  # renglones de "texto"
        arr[y:y + 8, 150:1050] = 0
    return Image.fromarray(arr).rotate(grados, expand=False, fillcolor=255)


@pytest.mark.parametrize("forma", [(-1, 1, 4), (-1, 4)])
def test_segmentos_acepta_ambas_formas(forma):
    lineas = np.array([[0, 0, 10, 1], [5, 5, 20, 6]]).reshape(forma)
    assert IP._segmentos(lineas) == [[0, 0, 10, 1], [5, 5, 20, 6]]


def test_detecta_la_inclinacion_real():
    ang = IP.detectar_angulo_pagina(_pagina_inclinada(4.0))
    assert 2.5 <= abs(ang) <= 5.5


def test_layout_detectar_angulo_no_revienta():
    from core.layout_tesseract import detectar_angulo
    assert abs(detectar_angulo(_pagina_inclinada(4.0))) >= 1.0
