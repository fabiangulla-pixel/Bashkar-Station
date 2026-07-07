"""tests/test_exportadores.py — Tests de exportadores ALTO XML."""
import os
import pytest
import xml.etree.ElementTree as ET
from pathlib import Path


ALTO_NS = {"alto": "http://www.loc.gov/standards/alto/ns-v4#"}


@pytest.fixture
def zonas_completas():
    return [
        {"tipo": "articulo", "x1": 0.05, "y1": 0.10, "x2": 0.48, "y2": 0.85,
         "texto_ocr": "Texto del articulo de prueba.", "confianza_ocr": 0.85},
        {"tipo": "titulo",   "x1": 0.05, "y1": 0.05, "x2": 0.95, "y2": 0.09,
         "texto_manual": "Titulo del articulo", "confianza_ocr": 0.95},
        {"tipo": "foto",     "x1": 0.52, "y1": 0.10, "x2": 0.95, "y2": 0.60},
        {"tipo": "publicidad","x1": 0.0,  "y1": 0.90, "x2": 1.0,  "y2": 1.0},
    ]


class TestExportarPaginaALTO:
    def test_crea_archivo(self, tmp_path, zonas_completas):
        from exportadores.exportar_alto import exportar_pagina_alto
        ruta = str(tmp_path / "test.xml")
        resultado = exportar_pagina_alto(
            "art_001", zonas_completas, 2480, 3508, "imagen.png", ruta
        )
        assert os.path.exists(resultado)
        assert os.path.getsize(resultado) > 100

    def test_xml_valido(self, tmp_path, zonas_completas):
        from exportadores.exportar_alto import exportar_pagina_alto
        ruta = str(tmp_path / "test.xml")
        exportar_pagina_alto("art_001", zonas_completas, 2480, 3508, "imagen.png", ruta)
        tree = ET.parse(ruta)
        root = tree.getroot()
        assert root is not None

    def test_namespace_correcto(self, tmp_path, zonas_completas):
        from exportadores.exportar_alto import exportar_pagina_alto
        ruta = str(tmp_path / "test.xml")
        exportar_pagina_alto("art_001", zonas_completas, 2480, 3508, "imagen.png", ruta)
        tree = ET.parse(ruta)
        root = tree.getroot()
        assert "alto" in root.tag.lower()

    def test_dimensiones_pagina(self, tmp_path, zonas_completas):
        from exportadores.exportar_alto import exportar_pagina_alto
        ruta = str(tmp_path / "test.xml")
        exportar_pagina_alto("art_001", zonas_completas, 2480, 3508, "imagen.png", ruta)
        tree = ET.parse(ruta)
        root = tree.getroot()
        page = root.find("alto:Layout/alto:Page", ALTO_NS)
        assert page is not None
        assert page.get("WIDTH") == "2480"
        assert page.get("HEIGHT") == "3508"

    def test_textblocks_e_illustrations(self, tmp_path, zonas_completas):
        from exportadores.exportar_alto import exportar_pagina_alto
        ruta = str(tmp_path / "test.xml")
        exportar_pagina_alto("art_001", zonas_completas, 2480, 3508, "imagen.png", ruta)
        tree = ET.parse(ruta)
        root = tree.getroot()
        ps = root.find("alto:Layout/alto:Page/alto:PrintSpace", ALTO_NS)
        text_blocks  = ps.findall("alto:TextBlock", ALTO_NS)
        illustrations = ps.findall("alto:Illustration", ALTO_NS)
        assert len(text_blocks) == 2   # articulo + titulo
        assert len(illustrations) == 2  # foto + publicidad

    def test_texto_incluido(self, tmp_path, zonas_completas):
        from exportadores.exportar_alto import exportar_pagina_alto
        ruta = str(tmp_path / "test.xml")
        exportar_pagina_alto("art_001", zonas_completas, 2480, 3508, "imagen.png", ruta)
        tree = ET.parse(ruta)
        root = tree.getroot()
        ps = root.find("alto:Layout/alto:Page/alto:PrintSpace", ALTO_NS)
        strings = ps.findall(".//alto:String", ALTO_NS)
        contenidos = [s.get("CONTENT", "") for s in strings]
        assert any("Titulo del articulo" in c for c in contenidos)

    def test_coordenadas_desnormalizadas(self, tmp_path):
        from exportadores.exportar_alto import exportar_pagina_alto
        zonas = [{"tipo": "articulo", "x1": 0.5, "y1": 0.5, "x2": 1.0, "y2": 1.0}]
        ruta = str(tmp_path / "test.xml")
        exportar_pagina_alto("art_001", zonas, 1000, 2000, "img.png", ruta)
        tree = ET.parse(ruta)
        root = tree.getroot()
        ps = root.find("alto:Layout/alto:Page/alto:PrintSpace", ALTO_NS)
        tb = ps.find("alto:TextBlock", ALTO_NS)
        assert tb.get("HPOS") == "500"
        assert tb.get("VPOS") == "1000"

    def test_zonas_vacias(self, tmp_path):
        from exportadores.exportar_alto import exportar_pagina_alto
        ruta = str(tmp_path / "test.xml")
        exportar_pagina_alto("art_001", [], 2480, 3508, "img.png", ruta)
        assert os.path.exists(ruta)
        # Debe generar XML válido aunque sin bloques
        tree = ET.parse(ruta)
        root = tree.getroot()
        assert root is not None

    def test_crea_carpeta_padre(self, tmp_path):
        from exportadores.exportar_alto import exportar_pagina_alto
        ruta = str(tmp_path / "subcarpeta" / "nueva" / "test.xml")
        exportar_pagina_alto("art_001", [], 2480, 3508, "img.png", ruta)
        assert os.path.exists(ruta)
