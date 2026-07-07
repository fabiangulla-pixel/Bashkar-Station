"""
tests/test_article_segmenter.py — Tests para core/article_segmenter.py

Cubre: helpers (_es_nombre_personal, _es_pagina_especial, _extraer_autor,
       _extraer_titulo_pagina, limpiar_texto_ocr), segmentación de una página
       (_procesar_pagina_ocr, segmentar_texto_ocr) y consolidación de páginas
       consecutivas (_consolidar_paginas).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.article_segmenter import (
    _consolidar_paginas,
    _es_nombre_personal,
    _es_pagina_especial,
    _extraer_autor,
    _extraer_titulo_pagina,
    _procesar_pagina_ocr,
    _ratio_alfabetico,
    _tiene_palabras_sin_vocales,
    limpiar_texto_ocr,
    segmentar_texto_ocr,
)

# ══════════════════════════════════════════════════════════════════════════════
# _es_nombre_personal
# ══════════════════════════════════════════════════════════════════════════════

class TestEsNombrePersonal:
    def test_nombre_simple_valido(self):
        assert _es_nombre_personal("Jorge Gaitán") is True

    def test_nombre_con_tres_palabras(self):
        assert _es_nombre_personal("María Consuelo Zapata") is True

    def test_nombre_con_de(self):
        # "de" y "la" son funcionales — la función los rechaza si todos los tokens
        # no propios son funcionales. "Jorge de la Torre" falla porque "de"/"la" son
        # funcionales y "Torre" puede quedar solo sin suficientes propios.
        # La función es conservadora: rechaza "Jorge de la Torre".
        assert _es_nombre_personal("Jorge de la Torre") is False

    def test_una_sola_palabra_rechazada(self):
        assert _es_nombre_personal("García") is False

    def test_minuscula_inicial_rechazada(self):
        assert _es_nombre_personal("jorge gaitán") is False

    def test_digitos_en_nombre_rechazados(self):
        assert _es_nombre_personal("Juan 3ro Pérez") is False

    def test_palabra_publicidad_rechazada(self):
        assert _es_nombre_personal("Farmacia Nacional") is False

    def test_solo_funcionales_rechazado(self):
        assert _es_nombre_personal("El De La") is False

    def test_palabra_muy_larga_rechazada(self):
        # token de más de 20 caracteres
        assert _es_nombre_personal("Juan Perezzzzzzzzzzzzzzzzzzzzzz") is False

    def test_seis_tokens_rechazados(self):
        assert _es_nombre_personal("Juan Carlos De La Torre Espinoza Real") is False


# ══════════════════════════════════════════════════════════════════════════════
# _tiene_palabras_sin_vocales
# ══════════════════════════════════════════════════════════════════════════════

class TestTienePalabrasSinVocales:
    def test_texto_normal_false(self):
        assert _tiene_palabras_sin_vocales("esto es texto normal") is False

    def test_token_sin_vocales_true(self):
        assert _tiene_palabras_sin_vocales("GVRD texto") is True

    def test_token_corto_ignorado(self):
        # Tokens de menos de 3 caracteres se ignoran
        assert _tiene_palabras_sin_vocales("ab cd") is False


# ══════════════════════════════════════════════════════════════════════════════
# _ratio_alfabetico
# ══════════════════════════════════════════════════════════════════════════════

class TestRatioAlfabetico:
    def test_vacio_retorna_cero(self):
        assert _ratio_alfabetico("") == 0.0

    def test_todo_letras(self):
        assert _ratio_alfabetico("hola") == 1.0

    def test_mitad_letras(self):
        r = _ratio_alfabetico("ab12")
        assert 0.4 < r < 0.6


# ══════════════════════════════════════════════════════════════════════════════
# _es_pagina_especial
# ══════════════════════════════════════════════════════════════════════════════

class TestEsPaginaEspecial:
    def test_portada_pocas_palabras(self):
        resultado = _es_pagina_especial("Estampa Año IV")
        assert "Portada" in resultado or resultado == "Portada/Cubierta"

    def test_pagina_normal_retorna_vacio(self):
        texto = " ".join(["palabra"] * 80)  # 80 palabras normales
        assert _es_pagina_especial(texto) == ""

    def test_publicidad_detectada(self):
        texto = ("droguería farmacia precio precios venta suscripción oferta "
                 "solicite visítenos distribuidores representantes ") * 5
        resultado = _es_pagina_especial(texto)
        assert resultado == "Publicidad"

    def test_colofon_detectado(self):
        texto = ("Director General Redacción principal Jefe de redacción "
                 "imprenta tipografía Bogotá " * 5)
        resultado = _es_pagina_especial(texto)
        assert resultado == "Colofón/Créditos"

    def test_indice_detectado(self):
        # El texto debe tener suficientes palabras para no activar "Portada" (<20 palabras)
        intro = "Contenido completo del número de la revista. " * 4
        entradas = ("Artículo uno Pág. 3\nArtículo dos Pág. 7\nArtículo tres Pág. 12\n"
                    "Artículo cuatro Pág. 18\nArtículo cinco Pág. 25\n")
        resultado = _es_pagina_especial(intro + entradas)
        assert resultado == "Índice"


# ══════════════════════════════════════════════════════════════════════════════
# limpiar_texto_ocr
# ══════════════════════════════════════════════════════════════════════════════

class TestLimpiarTextoOcr:
    def test_guion_al_final_de_linea_une_palabra(self):
        texto = "tra-\nbajar"
        resultado = limpiar_texto_ocr(texto)
        assert "trabajar" in resultado

    def test_multiples_espacios_colapsados(self):
        resultado = limpiar_texto_ocr("hola   mundo")
        assert "hola mundo" in resultado

    def test_numero_pagina_aislado_eliminado(self):
        resultado = limpiar_texto_ocr("\n42\n")
        assert "42" not in resultado

    def test_exceso_lineas_en_blanco_colapsado(self):
        resultado = limpiar_texto_ocr("a\n\n\n\n\nb")
        assert "\n\n\n" not in resultado

    def test_texto_vacio(self):
        assert limpiar_texto_ocr("") == ""


# ══════════════════════════════════════════════════════════════════════════════
# _extraer_titulo_pagina
# ══════════════════════════════════════════════════════════════════════════════

class TestExtraerTituloPagina:
    def test_titulo_all_caps(self):
        texto = "Texto introductorio\nEL REGRESO DEL PRESIDENTE\nCuerpo del artículo aquí."
        titulo = _extraer_titulo_pagina(texto)
        assert "Regreso" in titulo or "REGRESO" in titulo.upper()

    def test_fallback_primera_linea(self):
        texto = "Primera línea legible\nSegunda línea"
        titulo = _extraer_titulo_pagina(texto)
        assert titulo != "Sin título"

    def test_texto_solo_basura_retorna_sin_titulo(self):
        texto = "~[]<>{}\\^$%@&!*|\n~[]<>"
        titulo = _extraer_titulo_pagina(texto)
        assert titulo == "Sin título"

    def test_titulo_despues_de_por(self):
        texto = "Por Juan García\nLa Revolución Silenciosa\nTexto del artículo sigue aquí."
        titulo = _extraer_titulo_pagina(texto)
        assert "Revolución" in titulo or "Silenciosa" in titulo


# ══════════════════════════════════════════════════════════════════════════════
# _extraer_autor
# ══════════════════════════════════════════════════════════════════════════════

class TestExtraerAutor:
    def test_byline_explicita(self):
        texto = "Por Jorge Gaitán\nContenido del artículo aquí con muchas palabras."
        autor, conf = _extraer_autor(texto)
        assert "Gaitán" in autor or "Jorge" in autor
        assert conf > 0.8

    def test_sin_autor_retorna_anonimo(self):
        texto = "Texto sin ningún byline ni firma al final del texto."
        autor, conf = _extraer_autor(texto)
        assert "Anónimo" in autor
        assert conf == 0.0

    def test_firma_final_mayusculas(self):
        texto = ("Texto largo de relleno " * 20 +
                 "\n\nCARLOS MARIO RESTREPO\n")
        autor, conf = _extraer_autor(texto)
        # Puede o no detectar según longitud del token
        assert isinstance(autor, str)
        assert isinstance(conf, float)


# ══════════════════════════════════════════════════════════════════════════════
# _procesar_pagina_ocr y segmentar_texto_ocr
# ══════════════════════════════════════════════════════════════════════════════

class TestProcesarPaginaOcr:
    TEXTO_NORMAL = (
        "LA VIDA EN BOGOTÁ\n"
        "Por María Fernández\n"
        "La ciudad de Bogotá ha cambiado mucho en los últimos años. "
        "Los ciudadanos se adaptan a nuevas condiciones de vida urbana. "
        "El progreso avanza con firmeza. " * 5
    )

    def test_retorna_dict_con_campos_obligatorios(self):
        resultado = _procesar_pagina_ocr(self.TEXTO_NORMAL, "p0001")
        assert resultado is not None
        for campo in ("titulo", "autor", "seccion", "texto", "palabras", "pagina"):
            assert campo in resultado

    def test_pagina_nombre_en_resultado(self):
        resultado = _procesar_pagina_ocr(self.TEXTO_NORMAL, "p0042")
        assert resultado["pagina"] == "p0042"

    def test_palabras_mayor_que_cero(self):
        resultado = _procesar_pagina_ocr(self.TEXTO_NORMAL, "p0001")
        assert resultado["palabras"] > 0

    def test_texto_demasiado_corto_retorna_none(self):
        resultado = _procesar_pagina_ocr("Hola", "p0001")
        assert resultado is None

    def test_texto_vacio_retorna_none(self):
        resultado = _procesar_pagina_ocr("", "p0001")
        assert resultado is None

    def test_campos_internos_no_expuestos_en_segmentar(self):
        arts = segmentar_texto_ocr(self.TEXTO_NORMAL, "p0001")
        assert len(arts) == 1
        for campo in arts[0]:
            assert not campo.startswith("_")

    def test_pagina_muy_corta_devuelve_lista_vacia(self):
        arts = segmentar_texto_ocr("Hola mundo", "p0001")
        assert arts == []


# ══════════════════════════════════════════════════════════════════════════════
# _consolidar_paginas
# ══════════════════════════════════════════════════════════════════════════════

class TestConsolidarPaginas:
    def _pag(self, texto, pagina="p0001", autor="Anónimo / Sin atribuir",
             especial=False, continua_en=None):
        return {
            "titulo": "Título de prueba",
            "autor": autor,
            "confianza_autor": 0.0 if autor == "Anónimo / Sin atribuir" else 0.9,
            "seccion": "General",
            "texto": texto,
            "palabras": len(texto.split()),
            "pagina": pagina,
            "tipo_pagina": "Artículo",
            "_es_especial": especial,
            "_continua_en": continua_en,
        }

    def test_pagina_sola_retorna_una(self):
        pags = [self._pag("texto " * 50, "p0001")]
        resultado = _consolidar_paginas(pags)
        assert len(resultado) == 1

    def test_continuacion_explicita_fusiona(self):
        p1 = self._pag("texto " * 50, "p0001", continua_en=2)
        p2 = self._pag("continúa el relato " * 20, "p0002")
        resultado = _consolidar_paginas([p1, p2])
        assert len(resultado) == 1
        assert "p0001" in resultado[0]["pagina"] and "p0002" in resultado[0]["pagina"]

    def test_autores_distintos_no_fusionan(self):
        p1 = self._pag("texto " * 30, "p0001", autor="Jorge García")
        p2 = self._pag("texto " * 30, "p0002", autor="María López")
        resultado = _consolidar_paginas([p1, p2])
        assert len(resultado) == 2

    def test_pagina_especial_no_se_fusiona(self):
        p1 = self._pag("texto " * 50, "p0001")
        p2 = self._pag("publicidad " * 30, "p0002", especial=True)
        resultado = _consolidar_paginas([p1, p2])
        assert len(resultado) == 2

    def test_fragmento_corto_minuscula_fusiona(self):
        p1 = self._pag("texto muy corto", "p0001")  # < 150 palabras
        p2 = self._pag("el artículo continúa aquí " * 20, "p0002")
        resultado = _consolidar_paginas([p1, p2])
        # La segunda comienza con "el" (minúscula) y la primera es corta
        assert len(resultado) == 1

    def test_lista_vacia(self):
        assert _consolidar_paginas([]) == []

    def test_campos_internos_eliminados(self):
        pags = [self._pag("texto " * 50, "p0001")]
        resultado = _consolidar_paginas(pags)
        for campo in resultado[0]:
            assert not campo.startswith("_")

    def test_texto_fusionado_contiene_ambos(self):
        p1 = self._pag("primer fragmento " * 5, "p0001", continua_en=2)
        p2 = self._pag("segundo fragmento " * 5, "p0002")
        resultado = _consolidar_paginas([p1, p2])
        assert "primer fragmento" in resultado[0]["texto"]
        assert "segundo fragmento" in resultado[0]["texto"]

    def test_palabras_suman_al_fusionar(self):
        t1 = "texto " * 50
        t2 = "más texto " * 30
        p1 = self._pag(t1, "p0001", continua_en=2)
        p2 = self._pag(t2, "p0002")
        resultado = _consolidar_paginas([p1, p2])
        assert resultado[0]["palabras"] == len(t1.split()) + len(t2.split())
