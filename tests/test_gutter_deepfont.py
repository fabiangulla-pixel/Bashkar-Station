"""tests/test_gutter_deepfont.py — Tests para gutter_completion y deepfont."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ══════════════════════════════════════════════════════════════════════════════
# gutter_completion
# ══════════════════════════════════════════════════════════════════════════════

class TestGutterDeteccion:
    def test_detectar_guion_corte(self):
        from core.gutter_completion import detectar_fragmentos
        texto = "Este es un párrafo normal.\nLa siguiente palabra es polí-\ncontinúa en la otra columna."
        frags = detectar_fragmentos(texto)
        assert len(frags) >= 1
        assert any(f.fragmento.endswith("-") for f in frags)

    def test_detectar_fragmento_corto_con_continuacion(self):
        from core.gutter_completion import detectar_fragmentos
        texto = "Texto de la primera columna co\ncolombia es el país más hermoso del mundo."
        frags = detectar_fragmentos(texto)
        # "co" al final + siguiente en minúscula → fragmento
        assert len(frags) >= 1

    def test_no_detecta_lineas_normales(self):
        from core.gutter_completion import detectar_fragmentos
        texto = "Este es un texto completamente normal.\nNo tiene palabras cortadas aquí.\nTodo está bien formado."
        frags = detectar_fragmentos(texto)
        assert len(frags) == 0

    def test_texto_vacio(self):
        from core.gutter_completion import detectar_fragmentos
        assert detectar_fragmentos("") == []

    def test_fragmento_tiene_contexto(self):
        from core.gutter_completion import detectar_fragmentos
        texto = "Línea previa.\nOtra línea.\nPalabra polí-\ntica colombiana de los años 30."
        frags = detectar_fragmentos(texto)
        if frags:
            assert frags[0].contexto_prev != ""
            assert frags[0].contexto_post != ""


class TestGutterReconstruccion:
    def _mock_claude(self, palabra: str):
        msg = MagicMock()
        msg.content = [MagicMock(text=palabra)]
        client = MagicMock()
        client.messages.create.return_value = msg
        return client

    def test_reconstruir_fragmento_llama_llm(self):
        from core.gutter_completion import detectar_fragmentos, reconstruir_fragmento
        texto = "La siguiente palabra es polí-\ntica del gobierno."
        frags = detectar_fragmentos(texto)
        if not frags:
            pytest.skip("No se detectó fragmento en este texto")
        with patch("anthropic.Anthropic", return_value=self._mock_claude("política")):
            frag = reconstruir_fragmento(frags[0], api_key="fake")
        assert frag.reconstruida == "política"
        assert frag.confianza > 0

    def test_reconstruir_sin_api_key_mantiene_original(self):
        from core.gutter_completion import FragmentoCortado, reconstruir_fragmento
        frag = FragmentoCortado(0, "derecho", "polí-", "", "tica del país")
        with patch("anthropic.Anthropic", side_effect=Exception("sin key")):
            res = reconstruir_fragmento(frag, api_key="")
        assert res.reconstruida == "polí-"  # mantiene original

    def test_reconstruir_texto_sin_fragmentos(self):
        from core.gutter_completion import reconstruir_texto
        texto = "Texto normal sin cortes en absoluto."
        texto_rec, frags = reconstruir_texto(texto, api_key="")
        assert texto_rec == texto
        assert frags == []

    def test_texto_limpio_quita_tags(self):
        from core.gutter_completion import texto_limpio
        texto = "La ⟦política⟧ colombiana de los años 30."
        assert texto_limpio(texto) == "La política colombiana de los años 30."

    def test_texto_original_quita_generadas(self):
        from core.gutter_completion import texto_original
        texto = "La ⟦política⟧ colombiana de los años 30."
        assert "política" not in texto_original(texto)

    def test_estadisticas_estructura(self):
        from core.gutter_completion import FragmentoCortado, estadisticas
        frags = [
            FragmentoCortado(0, "derecho", "polí-", "", "", "política", 0.8),
            FragmentoCortado(1, "derecho", "co", "", "", "co", 0.0),  # fallido
        ]
        stats = estadisticas(frags)
        assert stats["total_fragmentos"] == 2
        assert stats["reconstruidos"] == 1
        assert stats["fallidos"] == 1
        assert 0.0 <= stats["confianza_media"] <= 1.0

    def test_exportar_html_con_marcas(self):
        from core.gutter_completion import exportar_html_con_marcas
        texto = "La ⟦política⟧ colombiana."
        html = exportar_html_con_marcas(texto)
        assert "color:#EF4444" in html
        assert "política" in html
        assert "generado" in html

    def test_exportar_docx_con_marcas(self, tmp_path):
        from core.gutter_completion import exportar_docx_con_marcas
        texto = "La ⟦política⟧ colombiana de los años 30."
        dest = str(tmp_path / "test.docx")
        try:
            n = exportar_docx_con_marcas(texto, dest, titulo="Test")
            assert n >= 1
            assert Path(dest).exists()
        except ImportError:
            pytest.skip("python-docx no instalado")

    def test_re_generado_patron(self):
        from core.gutter_completion import RE_GENERADO
        texto = "abc ⟦política⟧ def ⟦colombia⟧ ghi"
        matches = RE_GENERADO.findall(texto)
        assert matches == ["política", "colombia"]


# ══════════════════════════════════════════════════════════════════════════════
# deepfont
# ══════════════════════════════════════════════════════════════════════════════

class TestDeepFont:
    def test_categorias_definidas(self):
        from core.deepfont import CATEGORIAS_TIPOGRAFIA
        assert len(CATEGORIAS_TIPOGRAFIA) == 8
        assert "art_deco" in CATEGORIAS_TIPOGRAFIA
        assert "serif_romana" in CATEGORIAS_TIPOGRAFIA

    def test_etiquetas_para_todas_las_categorias(self):
        from core.deepfont import CATEGORIAS_TIPOGRAFIA, ETIQUETAS_ES
        for cat in CATEGORIAS_TIPOGRAFIA:
            assert cat in ETIQUETAS_ES
            assert len(ETIQUETAS_ES[cat]) > 5

    def test_colores_para_todas_las_categorias(self):
        from core.deepfont import CATEGORIAS_TIPOGRAFIA, COLORES
        for cat in CATEGORIAS_TIPOGRAFIA:
            assert cat in COLORES
            assert COLORES[cat].startswith("#")

    def test_clip_disponible_retorna_bool(self):
        from core.deepfont import clip_disponible
        assert isinstance(clip_disponible(), bool)

    def test_clasificar_opencv_imagen_valida(self, tmp_path):
        from core.deepfont import _clasificar_opencv
        try:
            from PIL import Image
            img = Image.new("L", (200, 80), color=240)
            # Dibujar texto simulado (líneas negras)
            import random
            pixels = img.load()
            for _ in range(500):
                x = random.randint(0, 199)
                y = random.randint(0, 79)
                pixels[x, y] = 0
            ruta = str(tmp_path / "test_tipo.png")
            img.save(ruta)
            res = _clasificar_opencv(ruta)
            assert "categoria" in res
            assert "confianza" in res
            assert "metodo" in res
            assert res["categoria"] in [
                "serif_romana", "display_titular", "art_deco",
                "manuscrita", "gotica", "sans_geometrica",
                "caligráfica", "display_creative"
            ]
        except ImportError:
            pytest.skip("PIL no disponible")

    def test_clasificar_opencv_imagen_inexistente(self):
        from core.deepfont import _clasificar_opencv
        res = _clasificar_opencv("ruta_que_no_existe.png")
        assert "categoria" in res
        assert res["metodo"] == "fallback"

    def test_clasificar_tipografia_fallback_sin_clip(self, tmp_path):
        from core.deepfont import clasificar_tipografia
        try:
            from PIL import Image
            img = Image.new("L", (100, 40), color=255)
            ruta = str(tmp_path / "test.png")
            img.save(ruta)
            # Forzar fallback OpenCV
            res = clasificar_tipografia(ruta, usar_clip=False)
            assert "categoria" in res
            assert "etiqueta" in res
            assert "color" in res
        except ImportError:
            pytest.skip("PIL no disponible")

    def test_estadisticas_clasificacion(self):
        from core.deepfont import estadisticas_tipografia
        resultados = [
            {"categoria": "serif_romana",  "confianza": 0.8, "metodo": "opencv"},
            {"categoria": "art_deco",       "confianza": 0.7, "metodo": "clip"},
            {"categoria": "serif_romana",   "confianza": 0.9, "metodo": "opencv"},
        ]
        stats = estadisticas_tipografia(resultados)
        assert stats["total"] == 3
        assert "serif_romana" in stats["distribucion"]
        assert stats["distribucion"]["serif_romana"]["n"] == 2
        assert stats["distribucion"]["serif_romana"]["pct"] == pytest.approx(66.7, abs=0.1)
        assert 0.0 <= stats["confianza_media"] <= 1.0

    def test_estadisticas_vacio(self):
        from core.deepfont import estadisticas_tipografia
        stats = estadisticas_tipografia([])
        assert stats["total"] == 0


# ══════════════════════════════════════════════════════════════════════════════
# zone_labeler — tipos extensibles
# ══════════════════════════════════════════════════════════════════════════════

class TestTiposZonaExtensibles:
    def test_tipos_base_presentes(self):
        from core.zone_labeler import TIPOS_ZONA
        for tid in ("articulo", "titulo", "publicidad", "foto"):
            assert tid in TIPOS_ZONA

    def test_agregar_tipo_custom(self, tmp_path, monkeypatch):
        import core.zone_labeler as zl
        from core.zone_labeler import agregar_tipo_zona
        # Redirigir el path global a tmp
        ruta_tmp = tmp_path / "tipos_zona.json"
        monkeypatch.setattr(zl, "_TIPOS_CUSTOM_PATH", ruta_tmp)

        agregar_tipo_zona("titulo_arte", "Título Arte", "#FF6B35", ocr=True)
        assert "titulo_arte" in zl.TIPOS_ZONA
        assert zl.TIPOS_ZONA["titulo_arte"]["label"] == "Título Arte"
        assert zl.TIPOS_ZONA["titulo_arte"]["color"] == "#FF6B35"
        assert zl.TIPOS_ZONA["titulo_arte"]["ocr"] is True

    def test_persistencia_tipos_custom(self, tmp_path, monkeypatch):
        import json

        import core.zone_labeler as zl
        from core.zone_labeler import agregar_tipo_zona
        ruta_tmp = tmp_path / "tipos_zona.json"
        monkeypatch.setattr(zl, "_TIPOS_CUSTOM_PATH", ruta_tmp)

        agregar_tipo_zona("tipo_prueba", "Prueba", "#AABBCC", ocr=False)
        # Verificar que se guardó en disco
        assert ruta_tmp.exists()
        datos = json.loads(ruta_tmp.read_text())
        assert "tipo_prueba" in datos

    def test_eliminar_tipo_custom(self, tmp_path, monkeypatch):
        import core.zone_labeler as zl
        from core.zone_labeler import agregar_tipo_zona, eliminar_tipo_zona
        ruta_tmp = tmp_path / "tipos_zona.json"
        monkeypatch.setattr(zl, "_TIPOS_CUSTOM_PATH", ruta_tmp)

        agregar_tipo_zona("tipo_borrar", "Borrar", "#123456")
        assert "tipo_borrar" in zl.TIPOS_ZONA
        eliminar_tipo_zona("tipo_borrar")
        assert "tipo_borrar" not in zl.TIPOS_ZONA

    def test_no_eliminar_tipo_base(self, tmp_path, monkeypatch):
        import core.zone_labeler as zl
        from core.zone_labeler import eliminar_tipo_zona
        monkeypatch.setattr(zl, "_TIPOS_CUSTOM_PATH", tmp_path / "t.json")
        with pytest.raises(ValueError):
            eliminar_tipo_zona("articulo")

    def test_tipo_custom_tiene_flag(self, tmp_path, monkeypatch):
        import core.zone_labeler as zl
        from core.zone_labeler import agregar_tipo_zona
        monkeypatch.setattr(zl, "_TIPOS_CUSTOM_PATH", tmp_path / "t.json")
        agregar_tipo_zona("mi_tipo", "Mi tipo", "#999999")
        assert zl.TIPOS_ZONA["mi_tipo"].get("custom") is True
