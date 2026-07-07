"""
Tests del análisis de layout local y operaciones de zona estilo FineReader:
  - clasificar_bloque (heurísticas de tipo)
  - calcular_orden_lectura (bandas + columnas)
  - dividir_zona / fusionar_zonas
  - persistencia del campo orden
  - ocr_pagina_con_zonas (fallback sin etiquetas)
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.zone_labeler import (
    Zona,
    PaginaEtiquetada,
    calcular_orden_lectura,
    dividir_zona,
    fusionar_zonas,
    guardar_pagina,
    cargar_pagina,
)
from core.layout_tesseract import clasificar_bloque, _descartar_contenidas


# ──────────────────────────────────────────────────────────────────────────────
# clasificar_bloque
# ──────────────────────────────────────────────────────────────────────────────

class TestClasificarBloque:
    def test_numero_pagina_arriba(self):
        tipo = clasificar_bloque(
            n_palabras=1, altura_palabra_med=14, altura_mediana_pagina=14,
            texto="37", y_centro_norm=0.03, ancho_norm=0.05)
        assert tipo == "numero_pag"

    def test_numero_pagina_abajo(self):
        tipo = clasificar_bloque(
            n_palabras=2, altura_palabra_med=12, altura_mediana_pagina=14,
            texto="— 124 —", y_centro_norm=0.96, ancho_norm=0.08)
        assert tipo == "numero_pag"

    def test_cabecera_banda_superior(self):
        tipo = clasificar_bloque(
            n_palabras=4, altura_palabra_med=15, altura_mediana_pagina=14,
            texto="ESTAMPA Bogotá enero 1939", y_centro_norm=0.03,
            ancho_norm=0.6)
        assert tipo == "cabecera"

    def test_titulo_tipografia_grande(self):
        tipo = clasificar_bloque(
            n_palabras=5, altura_palabra_med=40, altura_mediana_pagina=14,
            texto="LA MUJER MODERNA EN COLOMBIA", y_centro_norm=0.3,
            ancho_norm=0.7)
        assert tipo == "titulo"

    def test_articulo_cuerpo_normal(self):
        tipo = clasificar_bloque(
            n_palabras=120, altura_palabra_med=14, altura_mediana_pagina=14,
            texto="El presidente de la república visitó ayer " * 12,
            y_centro_norm=0.5, ancho_norm=0.3)
        assert tipo == "articulo"

    def test_texto_numerico_en_medio_no_es_numero_pag(self):
        tipo = clasificar_bloque(
            n_palabras=3, altura_palabra_med=14, altura_mediana_pagina=14,
            texto="1939 1940", y_centro_norm=0.5, ancho_norm=0.1)
        assert tipo == "articulo"


# ──────────────────────────────────────────────────────────────────────────────
# calcular_orden_lectura
# ──────────────────────────────────────────────────────────────────────────────

class TestOrdenLectura:
    def test_dos_columnas_simples(self):
        izq = Zona(tipo="articulo", x0=0.05, y0=0.1, x1=0.45, y1=0.9)
        der = Zona(tipo="articulo", x0=0.55, y0=0.1, x1=0.95, y1=0.9)
        zonas = [der, izq]   # desordenadas a propósito
        calcular_orden_lectura(zonas)
        assert izq.orden == 1
        assert der.orden == 2

    def test_titulo_ancho_va_primero(self):
        titulo = Zona(tipo="titulo",   x0=0.05, y0=0.05, x1=0.95, y1=0.12)
        col1   = Zona(tipo="articulo", x0=0.05, y0=0.15, x1=0.45, y1=0.9)
        col2   = Zona(tipo="articulo", x0=0.55, y0=0.15, x1=0.95, y1=0.9)
        zonas = [col2, col1, titulo]
        calcular_orden_lectura(zonas)
        assert titulo.orden == 1
        assert col1.orden == 2
        assert col2.orden == 3

    def test_titulo_intermedio_divide_bandas(self):
        # Columnas arriba, título de ancho completo en el medio, columnas abajo
        a1 = Zona(tipo="articulo", x0=0.05, y0=0.05, x1=0.45, y1=0.40)
        a2 = Zona(tipo="articulo", x0=0.55, y0=0.05, x1=0.95, y1=0.40)
        t  = Zona(tipo="titulo",   x0=0.05, y0=0.45, x1=0.95, y1=0.52)
        b1 = Zona(tipo="articulo", x0=0.05, y0=0.55, x1=0.45, y1=0.95)
        b2 = Zona(tipo="articulo", x0=0.55, y0=0.55, x1=0.95, y1=0.95)
        zonas = [b2, t, a1, b1, a2]
        calcular_orden_lectura(zonas)
        assert a1.orden == 1
        assert a2.orden == 2
        assert t.orden == 3
        assert b1.orden == 4
        assert b2.orden == 5

    def test_zonas_no_ocr_quedan_sin_orden(self):
        foto = Zona(tipo="foto",     x0=0.1, y0=0.1, x1=0.5, y1=0.5)
        art  = Zona(tipo="articulo", x0=0.55, y0=0.1, x1=0.95, y1=0.9)
        zonas = [foto, art]
        calcular_orden_lectura(zonas)
        assert foto.orden == 0
        assert art.orden == 1

    def test_misma_columna_de_arriba_a_abajo(self):
        arriba = Zona(tipo="articulo", x0=0.1, y0=0.1, x1=0.4, y1=0.4)
        abajo  = Zona(tipo="articulo", x0=0.1, y0=0.5, x1=0.4, y1=0.9)
        zonas = [abajo, arriba]
        calcular_orden_lectura(zonas)
        assert arriba.orden == 1
        assert abajo.orden == 2

    def test_lista_vacia_no_falla(self):
        calcular_orden_lectura([])


# ──────────────────────────────────────────────────────────────────────────────
# dividir / fusionar
# ──────────────────────────────────────────────────────────────────────────────

class TestDividirFusionar:
    def test_dividir_horizontal(self):
        z = Zona(tipo="articulo", x0=0.1, y0=0.2, x1=0.5, y1=0.8)
        a, b = dividir_zona(z, eje="h", frac=0.5)
        assert a.y0 == pytest.approx(0.2)
        assert a.y1 == pytest.approx(0.5)
        assert b.y0 == pytest.approx(0.5)
        assert b.y1 == pytest.approx(0.8)
        assert a.x0 == b.x0 == 0.1
        assert a.tipo == b.tipo == "articulo"

    def test_dividir_vertical(self):
        z = Zona(tipo="articulo", x0=0.0, y0=0.0, x1=1.0, y1=1.0)
        a, b = dividir_zona(z, eje="v", frac=0.25)
        assert a.x1 == pytest.approx(0.25)
        assert b.x0 == pytest.approx(0.25)

    def test_dividir_frac_se_acota(self):
        z = Zona(tipo="articulo", x0=0.0, y0=0.0, x1=1.0, y1=1.0)
        a, b = dividir_zona(z, eje="h", frac=0.001)
        assert a.y1 == pytest.approx(0.05)

    def test_fusionar_bounding_box(self):
        z1 = Zona(tipo="articulo", x0=0.1, y0=0.1, x1=0.4, y1=0.5)
        z2 = Zona(tipo="titulo",   x0=0.3, y0=0.4, x1=0.9, y1=0.9)
        f = fusionar_zonas([z1, z2])
        assert f.x0 == 0.1 and f.y0 == 0.1
        assert f.x1 == 0.9 and f.y1 == 0.9
        # El tipo lo aporta la zona de mayor área (z2)
        assert f.tipo == "titulo"

    def test_fusionar_vacia_lanza(self):
        with pytest.raises(ValueError):
            fusionar_zonas([])


# ──────────────────────────────────────────────────────────────────────────────
# _descartar_contenidas
# ──────────────────────────────────────────────────────────────────────────────

class TestDescartarContenidas:
    def test_fragmento_contenido_se_elimina(self):
        grande = Zona(tipo="articulo", x0=0.1, y0=0.1, x1=0.9, y1=0.9)
        chica  = Zona(tipo="articulo", x0=0.2, y0=0.2, x1=0.4, y1=0.4)
        res = _descartar_contenidas([grande, chica])
        assert grande in res
        assert chica not in res

    def test_foto_dentro_de_texto_se_conserva(self):
        texto = Zona(tipo="articulo", x0=0.0, y0=0.0, x1=1.0, y1=1.0)
        foto  = Zona(tipo="foto",     x0=0.2, y0=0.2, x1=0.5, y1=0.5)
        res = _descartar_contenidas([texto, foto])
        assert len(res) == 2

    def test_zonas_disjuntas_se_conservan(self):
        a = Zona(tipo="articulo", x0=0.0, y0=0.0, x1=0.4, y1=0.4)
        b = Zona(tipo="articulo", x0=0.6, y0=0.6, x1=1.0, y1=1.0)
        assert len(_descartar_contenidas([a, b])) == 2


# ──────────────────────────────────────────────────────────────────────────────
# Persistencia del campo orden
# ──────────────────────────────────────────────────────────────────────────────

class TestPersistenciaOrden:
    def test_orden_sobrevive_guardar_cargar(self, tmp_path):
        zonas = [
            Zona(tipo="titulo",   x0=0.1, y0=0.05, x1=0.9, y1=0.12),
            Zona(tipo="articulo", x0=0.1, y0=0.15, x1=0.45, y1=0.9),
        ]
        calcular_orden_lectura(zonas)
        pag = PaginaEtiquetada(pagina="p0001", ancho_px=1000, alto_px=1400,
                               zonas=zonas, manual=True)
        guardar_pagina(tmp_path, "enero_1939", pag)
        cargada = cargar_pagina(tmp_path, "enero_1939", "p0001")
        assert cargada is not None
        assert [z.orden for z in cargada.zonas] == [1, 2]

    def test_json_viejo_sin_orden_carga_con_cero(self, tmp_path):
        # Simula un JSON guardado por una versión anterior (sin campo orden)
        import json
        d = tmp_path / "05_etiquetas" / "num"
        d.mkdir(parents=True)
        (d / "p0001.json").write_text(json.dumps({
            "pagina": "p0001", "ancho_px": 1000, "alto_px": 1400,
            "manual": True,
            "zonas": [{"tipo": "articulo", "x0": 0.1, "y0": 0.1,
                       "x1": 0.9, "y1": 0.9, "confianza": 1.0, "notas": ""}],
        }), encoding="utf-8")
        pag = cargar_pagina(tmp_path, "num", "p0001")
        assert pag is not None
        assert pag.zonas[0].orden == 0


# ──────────────────────────────────────────────────────────────────────────────
# ocr_pagina_con_zonas — fallback
# ──────────────────────────────────────────────────────────────────────────────

class TestOcrPaginaConZonas:
    def test_sin_etiquetas_usa_pagina_completa(self, tmp_path, monkeypatch):
        """Si no hay zonas guardadas debe caer a ocr_pagina sin tocar Tesseract zonal."""
        import core.layout_tesseract as lt

        llamado = {}
        def fake_ocr_pagina(img_path, lang="spa"):
            llamado["full"] = True
            return "texto completo", 88.0

        import core.ocr_engine as oe
        monkeypatch.setattr(oe, "ocr_pagina", fake_ocr_pagina)

        img = tmp_path / "p0001.png"
        img.write_bytes(b"fake")
        texto, conf, con_z = lt.ocr_pagina_con_zonas(
            img, tmp_path, "num", "p0001", lang="spa")
        assert llamado.get("full")
        assert texto == "texto completo"
        assert conf == 88.0
        assert con_z is False

    def test_zonas_solo_ignorar_usa_pagina_completa(self, tmp_path, monkeypatch):
        """Página etiquetada solo con zonas no-OCR (foto/publicidad) → página completa."""
        import core.layout_tesseract as lt
        import core.ocr_engine as oe

        monkeypatch.setattr(oe, "ocr_pagina",
                            lambda img_path, lang="spa": ("full", 70.0))

        pag = PaginaEtiquetada(
            pagina="p0001", ancho_px=1000, alto_px=1400,
            zonas=[Zona(tipo="foto", x0=0.1, y0=0.1, x1=0.9, y1=0.9)],
            manual=True)
        guardar_pagina(tmp_path, "num", pag)

        img = tmp_path / "p0001.png"
        img.write_bytes(b"fake")
        texto, conf, con_z = lt.ocr_pagina_con_zonas(
            img, tmp_path, "num", "p0001")
        assert texto == "full"
        assert con_z is False
