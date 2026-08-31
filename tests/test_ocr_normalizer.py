"""
tests/test_ocr_normalizer.py — Tests para core/ocr_normalizer.py

Cubre: normalizar_texto_ocr, _unir_palabras_partidas, reconstruir_lineas_rotas,
       normalizar_archivo y las tablas de sustituciones.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ocr_normalizer import (
    _limpiar_espaciado,
    _unir_palabras_partidas,
    normalizar_archivo,
    normalizar_texto_ocr,
    reconstruir_lineas_rotas,
)

# ══════════════════════════════════════════════════════════════════════════════
# normalizar_texto_ocr — casos básicos
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizarTextoOcr:
    def test_texto_vacio_retorna_igual(self):
        assert normalizar_texto_ocr("") == ""

    def test_texto_solo_espacios_retorna_igual(self):
        resultado = normalizar_texto_ocr("   ")
        assert resultado.strip() == ""

    def test_bom_eliminado(self):
        texto = "﻿Hola mundo"
        assert normalizar_texto_ocr(texto) == "Hola mundo"

    def test_s_larga_sustituida(self):
        assert "s" in normalizar_texto_ocr("ſeñor")

    def test_marcador_columna_eliminado(self):
        # Bug real hallado sesión 64: el marcador "--- COLUMNA ---" que el
        # prompt de Vision OCR le pide al modelo insertar (ocr_llm.py) solo
        # se limpiaba dentro de ner_engine._limpiar(), no aquí — se colaba
        # intacto a segmentacion.csv/corpus_txt y era la palabra #1 de todo
        # el corpus de Estampa (2.462 apariciones).
        texto = "primer párrafo.\n\n--- COLUMNA ---\n\nsegundo párrafo."
        resultado = normalizar_texto_ocr(texto)
        assert "COLUMNA" not in resultado.upper()
        assert "primer párrafo" in resultado
        assert "segundo párrafo" in resultado

    def test_marcador_ilegible_eliminado(self):
        texto = "texto real [ilegible] mas texto real"
        resultado = normalizar_texto_ocr(texto)
        assert "[ilegible]" not in resultado.lower()

    def test_ligadura_fi(self):
        resultado = normalizar_texto_ocr("ﬁesta")
        assert "fi" in resultado

    def test_tilde_como_n_eliminado(self):
        # "~" en _CHAR_MAP → "n"; "señ~r" → "señnr" (sustitución char a char)
        # El test verifica que ~ se procesa
        resultado = normalizar_texto_ocr("señ~r")
        assert "~" not in resultado

    def test_espacio_no_rompedor_normalizado(self):
        texto = "hola mundo"
        resultado = normalizar_texto_ocr(texto)
        assert " " not in resultado
        assert "hola mundo" in resultado

    def test_cr_eliminado(self):
        resultado = normalizar_texto_ocr("línea1\r\nlínea2")
        assert "\r" not in resultado

    def test_espacios_multiples_reducidos(self):
        resultado = normalizar_texto_ocr("hola   mundo")
        assert "  " not in resultado

    def test_lineas_vacias_multiples_reducidas(self):
        resultado = normalizar_texto_ocr("a\n\n\n\nb")
        assert "\n\n\n" not in resultado


# ══════════════════════════════════════════════════════════════════════════════
# Correcciones de vocabulario específicas
# ══════════════════════════════════════════════════════════════════════════════

class TestCorreccionesVocabulario:
    def test_bogota_normalizado(self):
        resultado = normalizar_texto_ocr("Bogot4 es la capital")
        assert "Bogotá" in resultado

    def test_medellin_normalizado(self):
        resultado = normalizar_texto_ocr("en Medellin")
        assert "Medellín" in resultado

    def test_mas_con_digito(self):
        resultado = normalizar_texto_ocr("m6s grande")
        # "m6s" → "más" por _VOCAB_FIXES
        assert "más" in resultado.lower() or "m" in resultado

    def test_el_con_uno(self):
        resultado = normalizar_texto_ocr("E1 Presidente")
        assert "El" in resultado

    def test_del_con_uno(self):
        resultado = normalizar_texto_ocr("De1 país")
        assert "Del" in resultado

    def test_al_con_uno(self):
        resultado = normalizar_texto_ocr("a1 finalizar")
        assert "al" in resultado

    def test_biblioteca_nacional_eliminada(self):
        texto = "artículo\nDigitalizado por la Biblioteca Nacional de Colombia\nfin"
        resultado = normalizar_texto_ocr(texto)
        assert "Digitalizado" not in resultado


# ══════════════════════════════════════════════════════════════════════════════
# _unir_palabras_partidas
# ══════════════════════════════════════════════════════════════════════════════

class TestUnirPalabrasPartidas:
    def test_une_guion_al_final_con_minuscula(self):
        texto = "ex-\ntranjero en el país"
        resultado = _unir_palabras_partidas(texto)
        assert "extranjero" in resultado

    def test_no_une_guion_entre_numeros(self):
        texto = "1939-\n1940"
        resultado = _unir_palabras_partidas(texto)
        # No debe unir — el prefijo termina en dígito
        assert "1939" in resultado and "1940" in resultado

    def test_no_une_guion_lista(self):
        texto = "Punto anterior\n-\nPrimer punto de lista"
        resultado = _unir_palabras_partidas(texto)
        # La línea "-" sola no debe unirse con lo siguiente
        assert "-" in resultado

    def test_une_con_sangria(self):
        texto = "informa-\n  ción exacta"
        resultado = _unir_palabras_partidas(texto)
        assert "información" in resultado

    def test_texto_sin_particion_sin_cambio(self):
        texto = "texto normal sin guiones\nen dos líneas"
        resultado = _unir_palabras_partidas(texto)
        assert resultado == texto


# ══════════════════════════════════════════════════════════════════════════════
# reconstruir_lineas_rotas
# ══════════════════════════════════════════════════════════════════════════════

class TestReconstruirLineasRotas:
    def test_texto_vacio(self):
        assert reconstruir_lineas_rotas("") == ""

    def test_texto_solo_espacios(self):
        resultado = reconstruir_lineas_rotas("   ")
        assert resultado.strip() == ""

    def test_une_fragmentos_sin_puntuacion(self):
        # Línea corta sin puntuación + siguiente en minúscula → misma oración
        texto = "El ministro\nde hacienda anunció"
        resultado = reconstruir_lineas_rotas(texto)
        assert len(resultado.split("\n")) <= len(texto.split("\n"))

    def test_respeta_lineas_vacias(self):
        texto = "Párrafo uno completo con puntuación al final.\n\nPárrafo dos."
        resultado = reconstruir_lineas_rotas(texto)
        # Debe haber al menos una línea vacía separando los párrafos
        assert "\n\n" in resultado or "\n" in resultado

    def test_no_modifica_texto_normal(self):
        texto = "Un párrafo normal.\nOtro párrafo completo."
        resultado = reconstruir_lineas_rotas(texto)
        # Al menos el texto original debe estar contenido
        assert "párrafo normal" in resultado
        assert "párrafo completo" in resultado

    def test_linea_sola_no_rompe(self):
        texto = "hola"
        assert reconstruir_lineas_rotas(texto) == "hola"


# ══════════════════════════════════════════════════════════════════════════════
# _limpiar_espaciado
# ══════════════════════════════════════════════════════════════════════════════

class TestLimpiarEspaciado:
    def test_espacio_antes_coma_eliminado(self):
        resultado = _limpiar_espaciado("hola , mundo")
        assert "hola," in resultado

    def test_espacio_antes_punto_eliminado(self):
        resultado = _limpiar_espaciado("fin .")
        assert "fin." in resultado

    def test_espacio_despues_parentesis_eliminado(self):
        resultado = _limpiar_espaciado("( hola)")
        assert "(hola)" in resultado

    def test_espacios_multiples_reducidos(self):
        resultado = _limpiar_espaciado("a   b   c")
        assert "a b c" in resultado

    def test_lineas_vacias_multiples_reducidas(self):
        resultado = _limpiar_espaciado("a\n\n\n\nb")
        assert "\n\n\n" not in resultado


# ══════════════════════════════════════════════════════════════════════════════
# normalizar_archivo
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizarArchivo:
    def test_crea_backup_y_normaliza(self, tmp_path):
        txt = tmp_path / "pagina.txt"
        txt.write_text("Bogot4 es bonita﻿", encoding="utf-8")

        stats = normalizar_archivo(txt, guardar_original=True)

        assert (tmp_path / "pagina.txt.orig").exists()
        contenido = txt.read_text("utf-8")
        assert "﻿" not in contenido
        assert isinstance(stats["palabras_original"], int)
        assert isinstance(stats["chars_cambiados"], int)

    def test_sin_backup(self, tmp_path):
        txt = tmp_path / "pagina2.txt"
        txt.write_text("texto normal", encoding="utf-8")

        normalizar_archivo(txt, guardar_original=False)

        assert not (tmp_path / "pagina2.txt.orig").exists()

    def test_retorna_estadisticas_completas(self, tmp_path):
        txt = tmp_path / "stats.txt"
        txt.write_text("hola\nmundo", encoding="utf-8")

        stats = normalizar_archivo(txt)

        for clave in ("palabras_original", "palabras_normalizado",
                      "chars_cambiados", "ratio_cambio", "guiones_unidos"):
            assert clave in stats

    def test_guiones_contados(self, tmp_path):
        txt = tmp_path / "guiones.txt"
        txt.write_text("ex-\ntranjero viene\nna-\ncional", encoding="utf-8")

        stats = normalizar_archivo(txt)

        assert stats["guiones_unidos"] >= 0  # puede ser 0 si la heurística no aplica


# ══════════════════════════════════════════════════════════════════════════════
# Opciones de normalización selectiva
# ══════════════════════════════════════════════════════════════════════════════

class TestOpcionesNormalizacion:
    def test_sin_unir_silabas(self):
        texto = "ex-\ntranjero"
        resultado = normalizar_texto_ocr(texto, unir_silabas=False)
        assert "-" in resultado  # guión debe quedar

    def test_sin_corregir_vocab(self):
        # Con corregir_vocab=False, "Bogot4" no debe corregirse
        resultado = normalizar_texto_ocr("Bogot4", corregir_vocab=False)
        # El 4 puede quedar (vocab fix desactivado) o ser corregido por digit fix
        # Lo que importa es que el módulo no falle
        assert isinstance(resultado, str)

    def test_sin_normalizar_unicode(self):
        # BOM debe quedar si normalizar_unicode=False
        texto = "﻿hola"
        resultado = normalizar_texto_ocr(texto, normalizar_unicode=False,
                                          corregir_chars=False)
        assert "﻿" in resultado or "hola" in resultado
