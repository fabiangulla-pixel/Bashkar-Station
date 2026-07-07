"""tests/test_entity_linker.py — Tests del entity linker a Wikidata."""
import pytest

# ---------------------------------------------------------------------------
# Tests de caché local
# ---------------------------------------------------------------------------

class TestCacheEntidades:
    def test_cache_vacia_retorna_none(self, tmp_path):
        from core.entity_linker import _CacheEntidades
        cache = _CacheEntidades(str(tmp_path / "test.db"))
        assert cache.obtener("German Arciniegas", "personas") is None

    def test_guardar_y_recuperar(self, tmp_path):
        from core.entity_linker import _CacheEntidades
        cache = _CacheEntidades(str(tmp_path / "test.db"))
        resultado = {"id": "Q1234567", "label": "Germán Arciniegas", "confianza": 0.9}
        cache.guardar("German Arciniegas", "personas", resultado)
        recuperado = cache.obtener("German Arciniegas", "personas")
        assert recuperado == resultado

    def test_guardar_none_retorna_dict_vacio(self, tmp_path):
        from core.entity_linker import _CacheEntidades
        cache = _CacheEntidades(str(tmp_path / "test.db"))
        cache.guardar("XyzNoExiste", "personas", None)
        # None guardado → {} al recuperar → enlazar_entidad lo convierte a None
        recuperado = cache.obtener("XyzNoExiste", "personas")
        assert recuperado == {}  # {} significa "consultado, no encontrado"

    def test_estadisticas_iniciales(self, tmp_path):
        from core.entity_linker import _CacheEntidades
        cache = _CacheEntidades(str(tmp_path / "test.db"))
        stats = cache.estadisticas()
        assert stats["total"] == 0
        assert stats["encontrados"] == 0

    def test_estadisticas_despues_de_guardar(self, tmp_path):
        from core.entity_linker import _CacheEntidades
        cache = _CacheEntidades(str(tmp_path / "test.db"))
        cache.guardar("Bogota", "lugares", {"id": "Q2841", "label": "Bogotá", "confianza": 0.95})
        cache.guardar("XyzNoExiste", "lugares", None)
        stats = cache.estadisticas()
        assert stats["total"] == 2
        assert stats["encontrados"] == 1

    def test_replace_on_conflict(self, tmp_path):
        from core.entity_linker import _CacheEntidades
        cache = _CacheEntidades(str(tmp_path / "test.db"))
        r1 = {"id": "Q100", "label": "Viejo", "confianza": 0.5}
        r2 = {"id": "Q200", "label": "Nuevo", "confianza": 0.9}
        cache.guardar("test", "personas", r1)
        cache.guardar("test", "personas", r2)
        assert cache.obtener("test", "personas") == r2


# ---------------------------------------------------------------------------
# Tests de puntuación de candidatos
# ---------------------------------------------------------------------------

class TestPuntuarCandidato:
    def test_match_exacto_puntuacion_alta(self):
        from core.entity_linker import _puntuar_candidato
        candidato = {
            "id": "Q123", "rango": 0,
            "label": "German Arciniegas",
            "description": "escritor y periodista colombiano",
        }
        score = _puntuar_candidato(candidato, "German Arciniegas", "personas")
        # rango 0 (2.0) + label exacto (1.0) + colombiano (0.4) > 3
        assert score >= 3.0

    def test_rango_domina_la_puntuacion(self):
        """La primera acepción de Wikidata debe ganarle a una posterior aunque
        la posterior mencione Colombia (el bug que enlazaba Franco al tenista)."""
        from core.entity_linker import _puntuar_candidato
        dictador = {"id": "Q29179", "rango": 0, "label": "Francisco Franco",
                    "description": "militar y dictador español"}
        tenista = {"id": "Q5865733", "rango": 2, "label": "Francisco Franco",
                   "description": "tenista colombiano"}
        s_dict = _puntuar_candidato(dictador, "Francisco Franco", "personas")
        s_ten  = _puntuar_candidato(tenista, "Francisco Franco", "personas")
        assert s_dict > s_ten

    def test_homonimo_de_otro_tipo_penalizado(self):
        """Un 'apellido' o 'acorazado' homónimo debe puntuar muy por debajo."""
        from core.entity_linker import _puntuar_candidato
        persona = {"id": "Q1", "rango": 1, "label": "Mussolini",
                   "description": "político y dictador italiano"}
        apellido = {"id": "Q2", "rango": 0, "label": "Mussolini",
                    "description": "apellido"}
        s_per = _puntuar_candidato(persona, "Mussolini", "personas")
        s_ape = _puntuar_candidato(apellido, "Mussolini", "personas")
        assert s_per > s_ape

    def test_tipo_correcto_suma(self):
        from core.entity_linker import _puntuar_candidato
        con_tipo = _puntuar_candidato(
            {"id": "Q1", "rango": 0, "label": "Bogota",
             "description": "capital de Colombia"}, "Bogota", "lugares")
        sin_tipo = _puntuar_candidato(
            {"id": "Q2", "rango": 0, "label": "Bogota",
             "description": "xyz"}, "Bogota", "lugares")
        assert con_tipo > sin_tipo


# ---------------------------------------------------------------------------
# Tests de enlazar_entidad (modo offline / sin_red=True)
# ---------------------------------------------------------------------------

class TestEnlazarEntidadOffline:
    def test_texto_vacio_retorna_none(self, tmp_path):
        from core.entity_linker import enlazar_entidad
        assert enlazar_entidad("", "personas", str(tmp_path / "c.db"), sin_red=True) is None

    def test_texto_solo_espacios_retorna_none(self, tmp_path):
        from core.entity_linker import enlazar_entidad
        assert enlazar_entidad("   ", "personas", str(tmp_path / "c.db"), sin_red=True) is None

    def test_sin_red_usa_solo_cache(self, tmp_path):
        from core.entity_linker import _CacheEntidades, enlazar_entidad
        ruta_cache = str(tmp_path / "c.db")
        # Guardar un resultado en caché manualmente
        cache = _CacheEntidades(ruta_cache)
        cache.guardar("Bogota", "lugares", {"id": "Q2841", "label": "Bogotá", "confianza": 0.9,
                                             "description": "capital de Colombia", "url": "https://www.wikidata.org/wiki/Q2841"})
        resultado = enlazar_entidad("Bogota", "lugares", ruta_cache, sin_red=True)
        assert resultado is not None
        assert resultado["id"] == "Q2841"

    def test_sin_red_sin_cache_retorna_none(self, tmp_path):
        from core.entity_linker import enlazar_entidad
        resultado = enlazar_entidad("Bogota", "lugares", str(tmp_path / "c.db"), sin_red=True)
        assert resultado is None

    def test_no_encontrado_en_cache_retorna_none(self, tmp_path):
        from core.entity_linker import _CacheEntidades, enlazar_entidad
        ruta_cache = str(tmp_path / "c.db")
        cache = _CacheEntidades(ruta_cache)
        cache.guardar("XyzNoExiste", "personas", None)
        resultado = enlazar_entidad("XyzNoExiste", "personas", ruta_cache, sin_red=True)
        assert resultado is None


# ---------------------------------------------------------------------------
# Tests de enlazar_lista_entidades (sin red)
# ---------------------------------------------------------------------------

class TestEnlazarListaEntidades:
    def test_retorna_misma_cantidad(self, tmp_path):
        from core.entity_linker import enlazar_lista_entidades
        entidades = [
            {"texto": "German Arciniegas", "categoria": "personas", "confianza": 0.9, "fuente": "roberta_bne"},
            {"texto": "Bogota", "categoria": "lugares", "confianza": 0.95, "fuente": "roberta_bne"},
        ]
        resultado = enlazar_lista_entidades(entidades, str(tmp_path / "c.db"), sin_red=True)
        assert len(resultado) == 2

    def test_campo_wikidata_presente(self, tmp_path):
        from core.entity_linker import enlazar_lista_entidades
        entidades = [{"texto": "Test", "categoria": "personas", "confianza": 0.8, "fuente": "test"}]
        resultado = enlazar_lista_entidades(entidades, str(tmp_path / "c.db"), sin_red=True)
        assert "wikidata" in resultado[0]

    def test_no_modifica_original(self, tmp_path):
        from core.entity_linker import enlazar_lista_entidades
        entidad = {"texto": "Bogota", "categoria": "lugares", "confianza": 0.9, "fuente": "test"}
        enlazar_lista_entidades([entidad], str(tmp_path / "c.db"), sin_red=True)
        assert "wikidata" not in entidad  # original no modificado

    def test_lista_vacia(self, tmp_path):
        from core.entity_linker import enlazar_lista_entidades
        assert enlazar_lista_entidades([], str(tmp_path / "c.db"), sin_red=True) == []


# ---------------------------------------------------------------------------
# Tests de enlazar_indice_ner (sin red)
# ---------------------------------------------------------------------------

class TestEnlazarIndiceNER:
    def test_retorna_mismas_categorias(self, tmp_path):
        from core.entity_linker import enlazar_indice_ner
        indice = {
            "personas": {"German Arciniegas": ["art_001"]},
            "lugares":  {"Bogota": ["art_001", "art_002"]},
        }
        resultado = enlazar_indice_ner(indice, str(tmp_path / "c.db"), sin_red=True)
        assert set(resultado.keys()) == {"personas", "lugares"}

    def test_retorna_mismas_entidades(self, tmp_path):
        from core.entity_linker import enlazar_indice_ner
        indice = {"personas": {"Arciniegas": ["art_001"], "Lopez": ["art_002"]}}
        resultado = enlazar_indice_ner(indice, str(tmp_path / "c.db"), sin_red=True)
        assert set(resultado["personas"].keys()) == {"Arciniegas", "Lopez"}

    def test_callback_invocado(self, tmp_path):
        from core.entity_linker import enlazar_indice_ner
        llamadas = []
        def cb(n, total):
            llamadas.append((n, total))
        indice = {"personas": {"A": ["x"], "B": ["y"]}, "lugares": {"C": ["z"]}}
        enlazar_indice_ner(indice, str(tmp_path / "c.db"), sin_red=True, callback=cb)
        assert len(llamadas) == 3
        assert llamadas[-1] == (3, 3)


class TestMejorasDesambiguacion:
    """Mejoras sesión 42: contexto (#1), filtro basura OCR (#2),
    ventana histórica (#3) y versionado de caché (#4). Sin red."""

    def test_contexto_favorece_acepcion_correcta(self):
        """#1 — 'Alfonso López': el contexto del artículo debe inclinar el
        score hacia el presidente cuando la nota habla de política colombiana."""
        from core.entity_linker import _puntuar_candidato
        presidente = {"id": "Q1", "rango": 1,
                      "label": "Alfonso López Pumarejo",
                      "description": "presidente de Colombia"}
        deportista = {"id": "Q2", "rango": 0,
                      "label": "Alfonso López",
                      "description": "futbolista mexicano"}
        ctx = ("El presidente de Colombia inauguró la reforma; el gobierno "
               "anunció medidas en Bogotá durante su mandato político.")
        s_pres = _puntuar_candidato(presidente, "Alfonso López", "personas", ctx)
        s_dep  = _puntuar_candidato(deportista, "Alfonso López", "personas", ctx)
        assert s_pres > s_dep

    def test_contexto_no_rompe_sin_contexto(self):
        """El parámetro contexto es opcional: sin él, el score es el de antes."""
        from core.entity_linker import _puntuar_candidato
        c = {"id": "Q1", "rango": 0, "label": "X", "description": "político"}
        s_sin = _puntuar_candidato(c, "X", "personas")
        s_vac = _puntuar_candidato(c, "X", "personas", "")
        assert s_sin == s_vac

    def test_filtro_basura_ocr_corta(self, tmp_path):
        """#2 — fragmentos OCR demasiado cortos no se enlazan (offline)."""
        from core.entity_linker import enlazar_entidad
        assert enlazar_entidad("Bo", "lugares", str(tmp_path / "c.db")) is None
        assert enlazar_entidad("...", "lugares", str(tmp_path / "c.db")) is None
        assert enlazar_entidad("123", "personas", str(tmp_path / "c.db")) is None

    def test_ventana_historica_helper(self):
        """#3 — el extractor de año parsea el formato de tiempo de Wikidata."""
        from core.entity_linker import _anio_de_claim
        claims = {"P569": [{"mainsnak": {"datavalue": {"value":
                  {"time": "+1934-08-07T00:00:00Z"}}}}]}
        assert _anio_de_claim(claims, "P569") == 1934
        assert _anio_de_claim({}, "P569") is None

    def test_cache_invalida_version_vieja(self, tmp_path):
        """#4 — un resultado guardado con algo_version < actual se ignora
        (se trata como ausente para forzar re-enlace con la lógica nueva)."""
        import sqlite3

        from core.entity_linker import _ALGO_VERSION, _CacheEntidades
        ruta = str(tmp_path / "c.db")
        cache = _CacheEntidades(ruta)
        # Insertar a mano una entrada con versión vieja (0)
        con = sqlite3.connect(ruta)
        con.execute(
            "INSERT OR REPLACE INTO cache_wikidata"
            "(texto, categoria, resultado, consultado, algo_version)"
            " VALUES (?,?,?,?,?)",
            ("Viejo", "personas", '{"id":"Q1","label":"x","description":"",'
             '"url":"","confianza":0.9}', 0, _ALGO_VERSION - 1),
        )
        con.commit(); con.close()
        # Debe verse como ausente (None), no como el dict viejo
        assert cache.obtener("Viejo", "personas") is None

    def test_cache_version_actual_se_conserva(self, tmp_path):
        """Un resultado de la versión actual sí se devuelve desde caché."""
        from core.entity_linker import _CacheEntidades
        cache = _CacheEntidades(str(tmp_path / "c.db"))
        dato = {"id": "Q1", "label": "x", "description": "",
                "url": "", "confianza": 0.9}
        cache.guardar("Nuevo", "personas", dato)
        assert cache.obtener("Nuevo", "personas") == dato

    def test_contexto_propaga_por_indice(self, tmp_path):
        """enlazar_indice_ner acepta textos_articulos sin romper (offline)."""
        from core.entity_linker import enlazar_indice_ner
        indice = {"personas": {"Lopez": ["art_001"]}}
        textos = {"art_001": "El presidente de Colombia y su gobierno."}
        r = enlazar_indice_ner(indice, str(tmp_path / "c.db"), sin_red=True,
                               textos_articulos=textos)
        assert "personas" in r and "Lopez" in r["personas"]


# ---------------------------------------------------------------------------
# Tests de red (marcados como skipif sin conectividad)
# ---------------------------------------------------------------------------

def _tiene_red() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen("https://www.wikidata.org", timeout=5)
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _tiene_red(), reason="Sin conexión a Wikidata")
class TestEnlazarConRed:
    def test_bogota_encontrada(self, tmp_path):
        from core.entity_linker import enlazar_entidad
        resultado = enlazar_entidad("Bogotá", "lugares", str(tmp_path / "c.db"))
        # Bogotá (Q2841) es la capital de Colombia — debe encontrarse
        assert resultado is not None
        assert resultado["id"] == "Q2841"
        assert resultado["confianza"] > 0

    def test_entidad_inexistente_retorna_none(self, tmp_path):
        from core.entity_linker import enlazar_entidad
        resultado = enlazar_entidad(
            "xyzentidadinexistente12345abc", "personas", str(tmp_path / "c.db")
        )
        assert resultado is None

    def test_resultado_tiene_campos_requeridos(self, tmp_path):
        from core.entity_linker import enlazar_entidad
        resultado = enlazar_entidad("Colombia", "lugares", str(tmp_path / "c.db"))
        if resultado is None:
            pytest.skip("Entidad no encontrada en Wikidata")
        for campo in ("id", "label", "description", "url", "confianza"):
            assert campo in resultado, f"Falta campo '{campo}'"

    def test_segunda_llamada_usa_cache(self, tmp_path):
        from core.entity_linker import enlazar_entidad
        ruta_cache = str(tmp_path / "c.db")
        # Primera llamada: va a la red
        r1 = enlazar_entidad("Colombia", "lugares", ruta_cache)
        # Segunda llamada: usa caché (verificar que devuelve lo mismo)
        r2 = enlazar_entidad("Colombia", "lugares", ruta_cache)
        assert r1 == r2

    def test_desambiguacion_entidades_estampa(self, tmp_path):
        """Regresión del bug de desambiguación: las entidades del corpus real
        deben enlazar a la acepción histórica correcta, no a un homónimo."""
        from core.entity_linker import enlazar_entidad
        ruta = str(tmp_path / "c.db")
        esperados = {
            ("Francisco Franco", "personas"): "Q29179",  # dictador, no tenista
            ("España", "lugares"): "Q29",                # país, no acorazado
            ("Bogotá", "lugares"): "Q2841",              # capital de Colombia
            ("Mussolini", "personas"): "Q23559",         # Benito, no "apellido"
            ("Goethe", "personas"): "Q5879",             # el escritor, no "apellido"
        }
        aciertos = 0
        for (texto, cat), qid in esperados.items():
            r = enlazar_entidad(texto, cat, ruta)
            if r and r["id"] == qid:
                aciertos += 1
        # Al menos 4 de 5 (tolerante a cambios menores de ranking en Wikidata)
        assert aciertos >= 4, f"solo {aciertos}/5 entidades bien enlazadas"

    def test_no_enlaza_homonimo_tipo_incorrecto(self, tmp_path):
        """'España' como lugar no debe enlazar a un barco llamado España."""
        from core.entity_linker import enlazar_entidad
        r = enlazar_entidad("España", "lugares", str(tmp_path / "c.db"))
        assert r is not None
        # la descripción no debe ser la de un buque
        assert "acorazado" not in r["description"].lower()
        assert "battleship" not in r["description"].lower()
