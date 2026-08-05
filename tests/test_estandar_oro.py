"""Tests de core/estandar_oro.py — preparar y recolectar la transcripción de referencia."""

from __future__ import annotations

import json

import pytest

from core import estandar_oro
from core.zone_labeler import PaginaEtiquetada, Zona, guardar_pagina


@pytest.fixture
def proyecto(tmp_path):
    """Proyecto mínimo: una imagen y una página etiquetada con zonas mixtas."""
    from PIL import Image

    numero, pagina = "estampa_mar_1939", "p0001-02"
    img_dir = tmp_path / "02_imagenes" / numero
    img_dir.mkdir(parents=True)
    Image.new("RGB", (1000, 1400), "white").save(img_dir / f"{pagina}.png")

    zonas = [
        Zona(tipo="titulo", x0=0.1, y0=0.05, x1=0.9, y1=0.12, orden=1),
        Zona(tipo="foto", x0=0.1, y0=0.15, x1=0.5, y1=0.45, orden=2),
        Zona(tipo="pie_foto", x0=0.1, y0=0.46, x1=0.5, y1=0.50, orden=3),
        Zona(tipo="articulo", x0=0.55, y0=0.15, x1=0.9, y1=0.6, orden=4),
        Zona(tipo="publicidad", x0=0.1, y0=0.65, x1=0.9, y1=0.9, orden=5),
    ]
    guardar_pagina(tmp_path, numero,
                   PaginaEtiquetada(pagina=pagina, ancho_px=1000, alto_px=1400,
                                    zonas=zonas))
    return tmp_path, numero, pagina


class TestExportar:
    def test_exporta_solo_las_zonas_con_texto(self, proyecto, tmp_path):
        out, numero, pagina = proyecto
        destino = tmp_path / "oro"
        z = estandar_oro.exportar_zonas(out, numero, [pagina], destino)

        # titulo, pie_foto y articulo; NO foto ni publicidad
        assert len(z) == 3
        assert {x.tipo for x in z} == {"titulo", "pie_foto", "articulo"}

    def test_crea_recorte_y_txt_vacio_por_zona(self, proyecto, tmp_path):
        out, numero, pagina = proyecto
        destino = tmp_path / "oro"
        zonas = estandar_oro.exportar_zonas(out, numero, [pagina], destino)

        for z in zonas:
            assert (destino / z.imagen).exists()
            assert (destino / z.texto).exists()
            assert (destino / z.texto).read_text(encoding="utf-8") == ""

    def test_los_nombres_ordenan_por_lectura(self, proyecto, tmp_path):
        out, numero, pagina = proyecto
        destino = tmp_path / "oro"
        zonas = estandar_oro.exportar_zonas(out, numero, [pagina], destino)
        nombres = [z.texto for z in zonas]
        assert nombres == sorted(nombres)          # z01, z03, z04
        assert nombres[0].startswith(f"{pagina}_z01_titulo")

    def test_escribe_instrucciones_y_manifiesto(self, proyecto, tmp_path):
        out, numero, pagina = proyecto
        destino = tmp_path / "oro"
        estandar_oro.exportar_zonas(out, numero, [pagina], destino)

        assert (destino / "INSTRUCCIONES.md").exists()
        m = json.loads((destino / estandar_oro.MANIFIESTO).read_text(encoding="utf-8"))
        assert m["numero"] == numero
        assert len(m["zonas"]) == 3
        assert m["prellenado"] is False

    def test_NO_pisa_una_transcripcion_ya_hecha(self, proyecto, tmp_path):
        """Reexportar no puede destruir horas de trabajo manual."""
        out, numero, pagina = proyecto
        destino = tmp_path / "oro"
        zonas = estandar_oro.exportar_zonas(out, numero, [pagina], destino)
        (destino / zonas[0].texto).write_text("YA TRANSCRITO", encoding="utf-8")

        estandar_oro.exportar_zonas(out, numero, [pagina], destino)
        assert (destino / zonas[0].texto).read_text(encoding="utf-8") == "YA TRANSCRITO"

    def test_prellenar_queda_registrado(self, proyecto, tmp_path):
        """Prellenar sesga al transcriptor: tiene que quedar constancia."""
        out, numero, pagina = proyecto
        destino = tmp_path / "oro"
        base = f"{pagina}_z01_titulo"
        estandar_oro.exportar_zonas(out, numero, [pagina], destino,
                                    prellenar={base: "texto del OCR"})
        assert (destino / f"{base}.txt").read_text(encoding="utf-8") == "texto del OCR"
        m = json.loads((destino / estandar_oro.MANIFIESTO).read_text(encoding="utf-8"))
        assert m["prellenado"] is True

    def test_pagina_sin_etiquetar_se_omite_sin_reventar(self, proyecto, tmp_path):
        out, numero, _ = proyecto
        avisos = []
        z = estandar_oro.exportar_zonas(out, numero, ["p9999-99"], tmp_path / "oro",
                                        callback=avisos.append)
        assert z == []
        assert any("sin etiquetar" in a for a in avisos)


class TestRecolectar:
    @pytest.fixture
    def oro(self, proyecto, tmp_path):
        out, numero, pagina = proyecto
        destino = tmp_path / "oro"
        zonas = estandar_oro.exportar_zonas(out, numero, [pagina], destino)
        return destino, zonas, pagina

    def test_devuelve_lo_transcrito_por_zona(self, oro):
        destino, zonas, _ = oro
        (destino / zonas[0].texto).write_text("Primera Gran Rifa", encoding="utf-8")
        (destino / zonas[1].texto).write_text("Pie de la foto", encoding="utf-8")

        r = estandar_oro.recolectar(destino)
        assert len(r) == 2
        assert "Primera Gran Rifa" in r.values()

    def test_descarta_las_zonas_sin_transcribir(self, oro):
        destino, zonas, _ = oro
        (destino / zonas[0].texto).write_text("solo esta", encoding="utf-8")
        r = estandar_oro.recolectar(destino)
        assert list(r.values()) == ["solo esta"]

    def test_por_pagina_concatena_en_orden_de_lectura(self, oro):
        destino, zonas, pagina = oro
        (destino / zonas[0].texto).write_text("TITULO", encoding="utf-8")
        (destino / zonas[1].texto).write_text("PIE", encoding="utf-8")
        (destino / zonas[2].texto).write_text("CUERPO", encoding="utf-8")

        r = estandar_oro.recolectar(destino, por_pagina=True)
        assert set(r) == {pagina}
        assert r[pagina] == "TITULO\n\nPIE\n\nCUERPO"

    def test_carpeta_sin_manifiesto_da_error_claro(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="estándar de oro"):
            estandar_oro.recolectar(tmp_path)

    def test_la_salida_alimenta_al_benchmark(self, oro):
        """El contrato con benchmark_ocr: {clave: texto}."""
        from core import benchmark_ocr
        destino, zonas, _ = oro
        (destino / zonas[0].texto).write_text("la guerra civil española",
                                              encoding="utf-8")
        refs = estandar_oro.recolectar(destino)
        clave = next(iter(refs))
        r = benchmark_ocr.comparar(refs, {clave: "la guerra civil espanola"},
                                   ruta="prueba")
        assert r.cer == 0.0        # las tildes no penalizan por defecto


class TestEstado:
    def test_cuenta_avance_y_desglosa_por_tipo(self, proyecto, tmp_path):
        out, numero, pagina = proyecto
        destino = tmp_path / "oro"
        zonas = estandar_oro.exportar_zonas(out, numero, [pagina], destino)

        e = estandar_oro.estado(destino)
        assert (e["total"], e["hechas"], e["porcentaje"]) == (3, 0, 0.0)

        (destino / zonas[0].texto).write_text("dos palabras", encoding="utf-8")
        e = estandar_oro.estado(destino)
        assert e["hechas"] == 1
        assert e["pendientes"] == 2
        assert e["palabras"] == 2
        assert e["por_tipo"]["titulo"] == {"total": 1, "hechas": 1}

    def test_carpeta_vacia_no_revienta(self, tmp_path):
        e = estandar_oro.estado(tmp_path)
        assert e["total"] == 0 and e["porcentaje"] == 0.0
