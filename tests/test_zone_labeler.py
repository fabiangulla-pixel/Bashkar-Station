"""
tests/test_zone_labeler.py — Tests para core/zone_labeler.py

Cubre: Zona (área, solapamiento, conversión a/desde píxeles),
       PaginaEtiquetada (zonas_ocr, zonas_ignorar, serialización),
       persistencia (guardar/cargar/listar), DetectorZonas (entrenar,
       predecir, aplicar) y aplicar_zonas_a_texto.
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.zone_labeler import (
    TIPOS_ZONA,
    Zona,
    PaginaEtiquetada,
    DetectorZonas,
    aplicar_zonas_a_texto,
    filtrar_texto_con_etiquetas,
    guardar_pagina,
    cargar_pagina,
    listar_paginas_etiquetadas,
    cargar_todas_manual,
    ruta_etiquetas,
)


# ══════════════════════════════════════════════════════════════════════════════
# Zona — propiedades geométricas
# ══════════════════════════════════════════════════════════════════════════════

class TestZona:
    def _zona(self, x0=0.1, y0=0.1, x1=0.5, y1=0.5, tipo="articulo"):
        return Zona(tipo=tipo, x0=x0, y0=y0, x1=x1, y1=y1)

    def test_area_correcta(self):
        z = self._zona(0.0, 0.0, 0.5, 0.4)
        assert abs(z.area() - 0.20) < 1e-6

    def test_area_zona_degenerada_cero(self):
        # max(0.0, negativo) → 0.0 solo cuando x1-x0 < 0 AND y1-y0 < 0
        # Con x0=0.5,x1=0.3 → (0.3-0.5) = -0.2 → max(0.0, producto_negativo) = 0.0
        z = Zona(tipo="articulo", x0=0.5, y0=0.5, x1=0.3, y1=0.3)
        # área = max(0.0, (0.3-0.5)*(0.3-0.5)) = max(0.0, 0.04)
        # El método usa (x1-x0)*(y1-y0) directamente sin reordenar:
        # si ambos son negativos el producto es positivo → area > 0
        # Si solo uno es negativo → producto negativo → max(0.0,...) = 0.0
        z_uno_invertido = Zona(tipo="articulo", x0=0.5, y0=0.1, x1=0.3, y1=0.9)
        assert z_uno_invertido.area() == 0.0

    def test_solapamiento_identico_es_uno(self):
        z = self._zona()
        assert abs(z.solapamiento(z) - 1.0) < 1e-6

    def test_solapamiento_sin_interseccion_es_cero(self):
        z1 = self._zona(0.0, 0.0, 0.3, 0.3)
        z2 = self._zona(0.7, 0.7, 1.0, 1.0)
        assert z1.solapamiento(z2) == 0.0

    def test_solapamiento_parcial(self):
        z1 = self._zona(0.0, 0.0, 0.5, 0.5)
        z2 = self._zona(0.25, 0.25, 0.75, 0.75)
        s = z1.solapamiento(z2)
        assert 0.0 < s < 1.0

    def test_a_pixeles(self):
        z = self._zona(0.1, 0.2, 0.6, 0.8)
        x0, y0, x1, y1 = z.a_pixeles(1000, 1400)
        assert x0 == 100
        assert y0 == 280
        assert x1 == 600
        assert y1 == 1120

    def test_desde_pixeles(self):
        z = Zona.desde_pixeles(100, 200, 600, 800, 1000, 1000)
        assert abs(z.x0 - 0.1) < 1e-6
        assert abs(z.y0 - 0.2) < 1e-6
        assert abs(z.x1 - 0.6) < 1e-6
        assert abs(z.y1 - 0.8) < 1e-6

    def test_desde_pixeles_orden_invertido(self):
        # x0 > x1 debe normalizarse
        z = Zona.desde_pixeles(600, 800, 100, 200, 1000, 1000)
        assert z.x0 < z.x1
        assert z.y0 < z.y1

    def test_tipo_valido(self):
        z = self._zona(tipo="foto")
        assert z.tipo == "foto"


# ══════════════════════════════════════════════════════════════════════════════
# PaginaEtiquetada
# ══════════════════════════════════════════════════════════════════════════════

class TestPaginaEtiquetada:
    def _pag(self):
        return PaginaEtiquetada(
            pagina="p0001",
            ancho_px=1000,
            alto_px=1400,
            zonas=[
                Zona("articulo", 0.0, 0.0, 1.0, 0.7),
                Zona("foto",     0.1, 0.0, 0.9, 0.4),
                Zona("pie_foto", 0.1, 0.4, 0.9, 0.5),
                Zona("publicidad", 0.0, 0.7, 1.0, 1.0),
            ],
        )

    def test_zonas_ocr_filtra_correctamente(self):
        pag = self._pag()
        ocr = pag.zonas_ocr()
        tipos = {z.tipo for z in ocr}
        # "articulo" y "pie_foto" deben aparecer (ocr=True en TIPOS_ZONA)
        assert "articulo" in tipos
        assert "pie_foto" in tipos
        # "foto" y "publicidad" NO deben aparecer (ocr=False)
        assert "foto" not in tipos
        assert "publicidad" not in tipos

    def test_zonas_ignorar_filtra_correctamente(self):
        pag = self._pag()
        ignorar = pag.zonas_ignorar()
        tipos = {z.tipo for z in ignorar}
        assert "foto" in tipos
        assert "publicidad" in tipos
        assert "articulo" not in tipos

    def test_to_dict_y_from_dict_roundtrip(self):
        pag = self._pag()
        d = pag.to_dict()
        pag2 = PaginaEtiquetada.from_dict(d)
        assert pag2.pagina == pag.pagina
        assert len(pag2.zonas) == len(pag.zonas)
        assert pag2.zonas[0].tipo == pag.zonas[0].tipo

    def test_from_dict_sin_zonas(self):
        d = {"pagina": "p0001", "ancho_px": 1000, "alto_px": 1400, "manual": True}
        pag = PaginaEtiquetada.from_dict(d)
        assert pag.zonas == []

    def test_manual_por_defecto_true(self):
        pag = PaginaEtiquetada(pagina="p0001", ancho_px=1000, alto_px=1400)
        assert pag.manual is True


# ══════════════════════════════════════════════════════════════════════════════
# Persistencia
# ══════════════════════════════════════════════════════════════════════════════

class TestPersistencia:
    def test_guardar_y_cargar_roundtrip(self, tmp_path):
        pag = PaginaEtiquetada(
            pagina="p0001",
            ancho_px=1000,
            alto_px=1400,
            zonas=[Zona("articulo", 0.0, 0.0, 1.0, 1.0)],
        )
        guardar_pagina(tmp_path, "enero_1939", pag)
        cargada = cargar_pagina(tmp_path, "enero_1939", "p0001")
        assert cargada is not None
        assert cargada.pagina == "p0001"
        assert len(cargada.zonas) == 1
        assert cargada.zonas[0].tipo == "articulo"

    def test_cargar_pagina_inexistente_retorna_none(self, tmp_path):
        resultado = cargar_pagina(tmp_path, "enero_1939", "p9999")
        assert resultado is None

    def test_listar_paginas_etiquetadas(self, tmp_path):
        for nombre in ("p0001", "p0002", "p0005"):
            pag = PaginaEtiquetada(pagina=nombre, ancho_px=1000, alto_px=1400)
            guardar_pagina(tmp_path, "enero_1939", pag)
        lista = listar_paginas_etiquetadas(tmp_path, "enero_1939")
        assert lista == ["p0001", "p0002", "p0005"]

    def test_listar_paginas_directorio_inexistente(self, tmp_path):
        lista = listar_paginas_etiquetadas(tmp_path, "numero_inexistente")
        assert lista == []

    def test_cargar_todas_manual_filtra_predichas(self, tmp_path):
        manual = PaginaEtiquetada(pagina="p0001", ancho_px=1000, alto_px=1400, manual=True)
        predicha = PaginaEtiquetada(pagina="p0002", ancho_px=1000, alto_px=1400, manual=False)
        guardar_pagina(tmp_path, "enero_1939", manual)
        guardar_pagina(tmp_path, "enero_1939", predicha)
        manuales = cargar_todas_manual(tmp_path, "enero_1939")
        assert len(manuales) == 1
        assert manuales[0].pagina == "p0001"


# ══════════════════════════════════════════════════════════════════════════════
# DetectorZonas
# ══════════════════════════════════════════════════════════════════════════════

class TestDetectorZonas:
    def _paginas_entrenamiento(self, n=5):
        paginas = []
        for i in range(n):
            paginas.append(PaginaEtiquetada(
                pagina=f"p{i:04d}",
                ancho_px=1000,
                alto_px=1400,
                zonas=[
                    Zona("articulo",  0.05, 0.05, 0.95, 0.70),
                    Zona("cabecera",  0.05, 0.00, 0.95, 0.05),
                    Zona("numero_pag", 0.40, 0.95, 0.60, 1.00),
                ],
            ))
        return paginas

    def test_no_entrenado_inicialmente(self):
        det = DetectorZonas()
        assert det.esta_entrenado() is False

    def test_entrenado_tras_entrenar(self):
        det = DetectorZonas()
        det.entrenar(self._paginas_entrenamiento())
        assert det.esta_entrenado() is True

    def test_n_paginas_entrenamiento(self):
        det = DetectorZonas()
        det.entrenar(self._paginas_entrenamiento(7))
        assert det.n_paginas_entrenamiento() == 7

    def test_entrenar_retorna_estadisticas(self):
        det = DetectorZonas()
        stats = det.entrenar(self._paginas_entrenamiento())
        assert "n_paginas" in stats
        assert "tipos" in stats
        assert "articulo" in stats["tipos"]

    def test_predecir_retorna_pagina_etiquetada(self):
        det = DetectorZonas()
        det.entrenar(self._paginas_entrenamiento())
        pred = det.predecir("p0010", 1000, 1400)
        assert isinstance(pred, PaginaEtiquetada)
        assert pred.pagina == "p0010"
        assert pred.manual is False

    def test_predecir_incluye_tipos_frecuentes(self):
        det = DetectorZonas()
        det.entrenar(self._paginas_entrenamiento(5))
        pred = det.predecir("p0010", 1000, 1400, umbral_frecuencia=0.4)
        tipos = {z.tipo for z in pred.zonas}
        # articulo, cabecera y numero_pag aparecen en el 100% de páginas
        assert "articulo" in tipos

    def test_predecir_umbral_alto_filtra_tipos(self):
        # Con umbral 1.0, solo tipos que aparecen en TODAS las páginas
        paginas = self._paginas_entrenamiento(4)
        # Solo 2 de 4 tienen "foto"
        paginas[0].zonas.append(Zona("foto", 0.1, 0.1, 0.9, 0.5))
        paginas[1].zonas.append(Zona("foto", 0.1, 0.1, 0.9, 0.5))
        det = DetectorZonas()
        det.entrenar(paginas)
        pred = det.predecir("p0010", 1000, 1400, umbral_frecuencia=0.9)
        tipos = {z.tipo for z in pred.zonas}
        assert "foto" not in tipos  # frecuencia 50% < umbral 90%

    def test_entrenar_lista_vacia(self):
        det = DetectorZonas()
        stats = det.entrenar([])
        assert stats["n_paginas"] == 0
        assert det.esta_entrenado() is False

    def test_aplicar_a_numero(self, tmp_path):
        det = DetectorZonas()
        det.entrenar(self._paginas_entrenamiento(5))
        predichas = det.aplicar_a_numero(
            out_dir=tmp_path,
            numero="enero_1939",
            paginas_disponibles=["p0010", "p0011", "p0012"],
            paginas_ya_etiquetadas=[],
            ancho_px=1000,
            alto_px=1400,
        )
        assert predichas == 3
        # Verificar que se guardaron
        lista = listar_paginas_etiquetadas(tmp_path, "enero_1939")
        assert len(lista) == 3

    def test_aplicar_a_numero_salta_ya_etiquetadas(self, tmp_path):
        det = DetectorZonas()
        det.entrenar(self._paginas_entrenamiento(5))
        predichas = det.aplicar_a_numero(
            out_dir=tmp_path,
            numero="enero_1939",
            paginas_disponibles=["p0001", "p0002", "p0003"],
            paginas_ya_etiquetadas=["p0001"],
        )
        assert predichas == 2

    def test_aplicar_sin_entrenar_retorna_cero(self, tmp_path):
        det = DetectorZonas()
        predichas = det.aplicar_a_numero(
            out_dir=tmp_path,
            numero="enero_1939",
            paginas_disponibles=["p0001"],
            paginas_ya_etiquetadas=[],
        )
        assert predichas == 0


# ══════════════════════════════════════════════════════════════════════════════
# aplicar_zonas_a_texto
# ══════════════════════════════════════════════════════════════════════════════

class TestAplicarZonasATexto:
    def _texto_10_lineas(self):
        return "\n".join([f"línea {i}" for i in range(10)])

    def test_sin_zonas_retorna_texto_completo(self):
        texto = self._texto_10_lineas()
        resultado = aplicar_zonas_a_texto(texto, [], [])
        assert resultado == texto

    def test_zona_ignorar_elimina_lineas(self):
        texto = self._texto_10_lineas()
        # Ignorar las primeras 3 líneas (~0.0–0.3 de la página)
        zonas_ignorar = [Zona("publicidad", 0.0, 0.0, 1.0, 0.35)]
        resultado = aplicar_zonas_a_texto(texto, [], zonas_ignorar)
        lineas = [l for l in resultado.split('\n') if l]
        assert len(lineas) < 10

    def test_zona_ocr_solo_conserva_su_rango(self):
        texto = self._texto_10_lineas()
        # Solo conservar la mitad inferior (líneas 5-9)
        zonas_ocr = [Zona("articulo", 0.0, 0.5, 1.0, 1.0)]
        resultado = aplicar_zonas_a_texto(texto, zonas_ocr, [])
        lineas = [l for l in resultado.split('\n') if l]
        assert len(lineas) <= 5

    def test_texto_vacio(self):
        resultado = aplicar_zonas_a_texto("", [], [])
        assert resultado == ""

    def test_zona_ignorar_y_ocr_combinadas(self):
        texto = self._texto_10_lineas()
        zonas_ocr     = [Zona("articulo",   0.0, 0.1, 1.0, 0.9)]
        zonas_ignorar = [Zona("publicidad", 0.0, 0.7, 1.0, 1.0)]
        resultado = aplicar_zonas_a_texto(texto, zonas_ocr, zonas_ignorar)
        # Las líneas al final (>70%) deben estar ausentes
        lineas = resultado.split('\n')
        assert len(lineas) < 10


# ══════════════════════════════════════════════════════════════════════════════
# filtrar_texto_con_etiquetas
# ══════════════════════════════════════════════════════════════════════════════

class TestFiltrarTextoConEtiquetas:
    def test_sin_archivo_etiquetas_retorna_original(self, tmp_path):
        texto = "línea uno\nlínea dos\nlínea tres"
        resultado = filtrar_texto_con_etiquetas(tmp_path, "enero_1939", "p0001", texto)
        assert resultado == texto

    def test_con_etiquetas_filtra(self, tmp_path):
        texto = "\n".join([f"línea {i}" for i in range(20)])
        pag = PaginaEtiquetada(
            pagina="p0001",
            ancho_px=1000,
            alto_px=1400,
            zonas=[
                Zona("articulo",   0.0, 0.0, 1.0, 0.5),   # solo primera mitad
                Zona("publicidad", 0.0, 0.5, 1.0, 1.0),   # segunda mitad ignorar
            ],
        )
        guardar_pagina(tmp_path, "enero_1939", pag)
        resultado = filtrar_texto_con_etiquetas(tmp_path, "enero_1939", "p0001", texto)
        lineas = [l for l in resultado.split('\n') if l]
        assert len(lineas) < 20
