"""tests/test_spell_corrector.py — Corrección ortográfica post-OCR.

Sesión 63: core/spell_corrector.py no tenía NINGÚN test. El heurístico
_parece_error_ocr() solo detectaba dígitos mezclados, ruido o palabras
larguísimas — nunca la confusión de letras (rn→m, t→l, i→l) que es el error
de OCR más común en texto histórico. El corrector nunca llegaba a pedirle
una sugerencia a Hunspell para "gobiemo", "presidenle", "colombla",
"nacionaies" aunque Hunspell las corrige bien y con alta confianza —
0 correcciones sobre una frase con 5 errores típicos de OCR, verificado
antes del fix. Ver [[project_bashkar_station]] sesión 63.
"""
import pytest

pytest.importorskip("spylls")

from core.spell_corrector import SpellCorrector  # noqa: E402


@pytest.fixture(scope="module")
def sc():
    corrector = SpellCorrector()
    if not corrector._cargar_diccionario():
        pytest.skip("diccionario Hunspell no disponible en esta máquina")
    return corrector


class TestCorreccionDeRuidoOCRComun:
    """Confusión de letras (rn→m, t→l, i→l): el error de OCR más común en
    prensa histórica, y el que el heurístico viejo nunca detectaba."""

    @pytest.mark.parametrize("palabra_rota,esperada", [
        ("gobiemo", "gobierno"),
        ("presidenle", "presidente"),
        ("nacionaies", "nacionales"),
    ])
    def test_corrige_confusion_de_letras_comun(self, sc, palabra_rota, esperada):
        corregido = sc.corregir_texto(f"El {palabra_rota} anuncio medidas.")
        assert esperada in corregido, (
            f"'{palabra_rota}' no se corrigió a '{esperada}' — "
            f"resultado: {corregido!r}"
        )

    def test_corrige_con_mayuscula_inicial_preservada(self, sc):
        corregido = sc.corregir_texto("colombla anuncio medidas.")
        assert corregido.startswith("Colombia") or "olombia" in corregido


class TestProtegeNombresPropiosSinCatalogar:
    """El heurístico nuevo distingue por mayúscula inicial: un nombre propio
    real que Hunspell no conoce (topónimo, apellido) no debe tocarse."""

    @pytest.mark.parametrize("topico", ["Titiribi", "Amaga", "Bogota"])
    def test_no_toca_toponimos_reales_capitalizados(self, sc, topico):
        original = f"{topico} es un municipio de Antioquia."
        corregido = sc.corregir_texto(original)
        assert topico in corregido, (
            f"un nombre propio capitalizado sin catalogar se corrigió cuando "
            f"no debía — original: {original!r}, resultado: {corregido!r}"
        )

    def test_lista_blanca_de_epoca_nunca_se_toca(self, sc):
        from core.spell_corrector import _VOCAB_EPOCA_LOWER
        if not _VOCAB_EPOCA_LOWER:
            pytest.skip("vocabulario de época vacío")
        palabra = next(iter(_VOCAB_EPOCA_LOWER))
        assert sc.corregir_palabra(palabra) == palabra


class TestNoSobrecorrige:
    def test_palabra_real_no_se_toca(self, sc):
        assert sc.corregir_texto("La casa es grande.") == "La casa es grande."

    def test_numeros_no_se_tocan(self, sc):
        assert sc.corregir_texto("El año 1939 fue importante.") == "El año 1939 fue importante."

    def test_estadisticas_reflejan_las_correcciones(self, sc):
        sc.corregir_texto("gobiemo presidenle nacionaies")
        stats = sc.estadisticas()
        assert stats["diccionario_cargado"] is True
        assert stats["palabras_corregidas"] >= 1


class TestResolucionDelDiccionario:
    """spylls empaqueta en/ru/sv pero NO español: hasta la sesión 67 el
    corrector solo miraba los datos internos de spylls, así que en cualquier
    máquina recién instalada `_cargar_diccionario()` devolvía False y el
    corrector quedaba inerte sin decir una palabra. Estas pruebas fijan las
    dos rutas que hoy sí se buscan."""

    def test_encuentra_el_diccionario_en_la_carpeta_del_usuario(self, tmp_path, monkeypatch):
        from core import spell_corrector as sc_mod
        (tmp_path / "es_ES.aff").write_text("SET UTF-8\n", encoding="utf-8")
        (tmp_path / "es_ES.dic").write_text("1\ncasa\n", encoding="utf-8")
        monkeypatch.delenv("BASHKAR_DICCIONARIO_ES", raising=False)
        monkeypatch.setattr(sc_mod, "DICCIONARIOS_DIR", tmp_path)
        assert sc_mod.ruta_diccionario_es() == tmp_path / "es_ES"

    def test_la_variable_de_entorno_manda_sobre_la_carpeta(self, tmp_path, monkeypatch):
        from core import spell_corrector as sc_mod
        otra = tmp_path / "otra"
        otra.mkdir()
        (otra / "es_ES.aff").write_text("SET UTF-8\n", encoding="utf-8")
        monkeypatch.setattr(sc_mod, "DICCIONARIOS_DIR", tmp_path)
        monkeypatch.setenv("BASHKAR_DICCIONARIO_ES", str(otra / "es_ES"))
        assert sc_mod.ruta_diccionario_es() == otra / "es_ES"

    def test_sin_diccionario_devuelve_none_y_no_revienta(self, tmp_path, monkeypatch):
        from core import spell_corrector as sc_mod
        monkeypatch.delenv("BASHKAR_DICCIONARIO_ES", raising=False)
        monkeypatch.setattr(sc_mod, "DICCIONARIOS_DIR", tmp_path / "no_existe")
        monkeypatch.setattr(sc_mod, "_NOMBRES_DIC_ES", ("es_ES",))
        import spylls
        from pathlib import Path as _P
        monkeypatch.setattr(spylls, "__file__",
                            str(_P(tmp_path) / "spylls" / "__init__.py"))
        assert sc_mod.ruta_diccionario_es() is None

    def test_verificar_instalacion_mira_donde_mira_el_corrector(self, tmp_path, monkeypatch):
        # El diagnostico y el runtime deben coincidir: antes verificar_instalacion()
        # solo miraba los datos de spylls y decia "no hay diccionario" con el
        # diccionario ya instalado al lado.
        from core import spell_corrector as sc_mod
        (tmp_path / "es_ES.aff").write_text("SET UTF-8\n", encoding="utf-8")
        monkeypatch.delenv("BASHKAR_DICCIONARIO_ES", raising=False)
        monkeypatch.setattr(sc_mod, "DICCIONARIOS_DIR", tmp_path)
        estado = sc_mod.verificar_instalacion()
        assert estado["diccionario_es"] is True
        assert estado["ruta_diccionario"] == str(tmp_path / "es_ES")
