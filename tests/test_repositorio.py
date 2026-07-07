"""tests/test_repositorio.py — Tests del Repositorio SQLite."""


class TestArticulos:
    def test_guardar_y_obtener(self, repo, articulo_simple):
        repo.guardar_articulo(articulo_simple)
        art = repo.obtener_articulo("art_001")
        assert art is not None
        assert art["id"] == "art_001"
        assert art["titulo"] == "La educacion en Colombia"
        assert art["autor"] == "German Arciniegas"

    def test_obtener_inexistente_retorna_none(self, repo):
        assert repo.obtener_articulo("art_inexistente") is None

    def test_actualizar_upsert(self, repo, articulo_simple):
        repo.guardar_articulo(articulo_simple)
        articulo_simple["titulo"] = "Titulo actualizado"
        repo.guardar_articulo(articulo_simple)
        art = repo.obtener_articulo("art_001")
        assert art["titulo"] == "Titulo actualizado"

    def test_listar_vacio(self, repo):
        arts = repo.listar_articulos()
        assert arts == []

    def test_listar_multiples(self, repo, articulo_simple, articulo_segundo):
        repo.guardar_articulo(articulo_simple)
        repo.guardar_articulo(articulo_segundo)
        arts = repo.listar_articulos()
        assert len(arts) == 2

    def test_listar_por_numero(self, repo, articulo_simple):
        repo.guardar_articulo(articulo_simple)
        arts = repo.listar_articulos(numero="estampa_1939_01")
        assert len(arts) == 1
        arts_otro = repo.listar_articulos(numero="otro_numero")
        assert len(arts_otro) == 0

    def test_actualizar_estado(self, repo, articulo_simple):
        repo.guardar_articulo(articulo_simple)
        repo.actualizar_estado("art_001", "completo")
        art = repo.obtener_articulo("art_001")
        assert art["estado"] == "completo"

    def test_articulos_pendientes(self, repo, articulo_simple, articulo_segundo):
        repo.guardar_articulo(articulo_simple)
        repo.guardar_articulo(articulo_segundo)
        repo.actualizar_estado("art_001", "completo")
        pendientes = repo.articulos_pendientes()
        assert len(pendientes) == 1
        assert pendientes[0]["id"] == "art_002"


class TestOCR:
    def test_guardar_y_obtener_texto(self, repo, articulo_simple):
        repo.guardar_articulo(articulo_simple)
        repo.guardar_ocr("art_001", "texto crudo", "texto limpio", 0.85, "kraken", "6.0")
        assert repo.obtener_texto("art_001", limpio=True) == "texto limpio"
        assert repo.obtener_texto("art_001", limpio=False) == "texto crudo"

    def test_obtener_texto_inexistente(self, repo, articulo_simple):
        repo.guardar_articulo(articulo_simple)
        assert repo.obtener_texto("art_001") is None

    def test_confianza_ocr(self, repo, articulo_simple):
        repo.guardar_articulo(articulo_simple)
        repo.guardar_ocr("art_001", "crudo", "limpio", 0.82, "tesseract")
        assert abs(repo.obtener_confianza_ocr("art_001") - 0.82) < 0.001

    def test_estado_cambia_a_completo_tras_ocr(self, repo, articulo_simple):
        repo.guardar_articulo(articulo_simple)
        repo.guardar_ocr("art_001", "crudo", "limpio", 0.8, "kraken")
        art = repo.obtener_articulo("art_001")
        assert art["estado"] == "completo"


class TestEntidades:
    def test_guardar_y_buscar(self, repo, articulo_simple, entidades_ejemplo):
        repo.guardar_articulo(articulo_simple)
        repo.guardar_entidades("art_001", entidades_ejemplo)
        personas = repo.buscar_entidades(categoria="personas")
        assert len(personas) == 2
        textos = [p["texto"] for p in personas]
        assert "German Arciniegas" in textos
        assert "Lopez de Mesa" in textos

    def test_buscar_por_texto(self, repo, articulo_simple, entidades_ejemplo):
        repo.guardar_articulo(articulo_simple)
        repo.guardar_entidades("art_001", entidades_ejemplo)
        resultados = repo.buscar_entidades(texto="Arciniegas")
        assert len(resultados) == 1
        assert resultados[0]["texto"] == "German Arciniegas"

    def test_guardar_reemplaza(self, repo, articulo_simple):
        repo.guardar_articulo(articulo_simple)
        repo.guardar_entidades("art_001", [
            {"texto": "entidad_vieja", "categoria": "personas", "confianza": 0.9, "fuente": "test"}
        ])
        repo.guardar_entidades("art_001", [
            {"texto": "entidad_nueva", "categoria": "personas", "confianza": 0.9, "fuente": "test"}
        ])
        todas = repo.buscar_entidades(articulo_id="art_001")
        textos = [e["texto"] for e in todas]
        assert "entidad_vieja" not in textos
        assert "entidad_nueva" in textos

    def test_indice_global(self, repo, articulo_simple, articulo_segundo, entidades_ejemplo):
        repo.guardar_articulo(articulo_simple)
        repo.guardar_articulo(articulo_segundo)
        repo.guardar_entidades("art_001", entidades_ejemplo)
        # Agregar German Arciniegas también en art_002
        repo.guardar_entidades("art_002", [
            {"texto": "German Arciniegas", "categoria": "personas", "confianza": 0.9, "fuente": "roberta"}
        ])
        indice = repo.indice_global(categoria="personas")
        assert "German Arciniegas" in indice
        assert "art_001" in indice["German Arciniegas"]
        assert "art_002" in indice["German Arciniegas"]
        assert "Lopez de Mesa" in indice
        assert len(indice["Lopez de Mesa"]) == 1


class TestZonas:
    def test_guardar_y_obtener(self, repo, articulo_simple, zonas_ejemplo):
        repo.guardar_articulo(articulo_simple)
        repo.guardar_zonas_anotacion("art_001", zonas_ejemplo)
        zonas = repo.obtener_zonas_anotacion("art_001")
        assert len(zonas) == 3

    def test_tipos_correctos(self, repo, articulo_simple, zonas_ejemplo):
        repo.guardar_articulo(articulo_simple)
        repo.guardar_zonas_anotacion("art_001", zonas_ejemplo)
        zonas = repo.obtener_zonas_anotacion("art_001")
        tipos = [z["tipo"] for z in zonas]
        assert "articulo" in tipos
        assert "titulo" in tipos
        assert "foto" in tipos

    def test_verificada_guardada(self, repo, articulo_simple, zonas_ejemplo):
        repo.guardar_articulo(articulo_simple)
        repo.guardar_zonas_anotacion("art_001", zonas_ejemplo)
        zonas = repo.obtener_zonas_anotacion("art_001")
        titulo = next(z for z in zonas if z["tipo"] == "titulo")
        assert titulo["verificada"] == 1

    def test_reemplaza_en_guardar(self, repo, articulo_simple):
        repo.guardar_articulo(articulo_simple)
        repo.guardar_zonas_anotacion("art_001", [
            {"tipo": "articulo", "x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 1.0}
        ])
        repo.guardar_zonas_anotacion("art_001", [
            {"tipo": "foto", "x1": 0.1, "y1": 0.1, "x2": 0.9, "y2": 0.9},
            {"tipo": "titulo", "x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 0.1},
        ])
        zonas = repo.obtener_zonas_anotacion("art_001")
        assert len(zonas) == 2


class TestTono:
    def test_guardar_y_obtener(self, repo, articulo_simple):
        repo.guardar_articulo(articulo_simple)
        repo.guardar_tono("art_001", {
            "tono_principal": "celebratorio",
            "tono_secundario": "neutro",
            "confianza": 0.88,
            "resumen": "Tono positivo y optimista.",
            "indicadores": ["exito", "progreso", "avance"],
        })
        tono = repo.obtener_tono("art_001")
        assert tono is not None
        assert tono["tono_principal"] == "celebratorio"
        assert isinstance(tono["indicadores"], list)
        assert "exito" in tono["indicadores"]

    def test_obtener_sin_tono(self, repo, articulo_simple):
        repo.guardar_articulo(articulo_simple)
        assert repo.obtener_tono("art_001") is None


class TestCoocurrencias:
    def test_guardar_y_listar(self, repo, articulo_simple):
        repo.guardar_articulo(articulo_simple)
        repo.guardar_coocurrencia("Arciniegas", "Lopez de Mesa", "personas", "art_001")
        coocs = repo.coocurrencias(categoria="personas", min_peso=1)
        assert len(coocs) == 1
        assert coocs[0]["peso"] == 1

    def test_incrementa_peso(self, repo, articulo_simple, articulo_segundo):
        repo.guardar_articulo(articulo_simple)
        repo.guardar_articulo(articulo_segundo)
        repo.guardar_coocurrencia("Arciniegas", "Lopez de Mesa", "personas", "art_001")
        repo.guardar_coocurrencia("Arciniegas", "Lopez de Mesa", "personas", "art_002")
        coocs = repo.coocurrencias(min_peso=1)
        assert coocs[0]["peso"] == 2

    def test_min_peso_filtra(self, repo, articulo_simple):
        repo.guardar_articulo(articulo_simple)
        repo.guardar_coocurrencia("A", "B", "personas", "art_001")
        assert len(repo.coocurrencias(min_peso=2)) == 0
        assert len(repo.coocurrencias(min_peso=1)) == 1

    def test_par_ordenado(self, repo, articulo_simple):
        """(B, A) y (A, B) deben ser el mismo par."""
        repo.guardar_articulo(articulo_simple)
        repo.guardar_coocurrencia("B_nombre", "A_nombre", "personas", "art_001")
        repo.guardar_coocurrencia("A_nombre", "B_nombre", "personas", "art_001")
        coocs = repo.coocurrencias(min_peso=1)
        assert len(coocs) == 1
        assert coocs[0]["peso"] == 2


class TestEstadisticas:
    def test_corpus_vacio(self, repo):
        stats = repo.estadisticas_corpus()
        assert stats["total_articulos"] == 0
        assert stats["con_ocr"] == 0
        assert stats["con_entidades"] == 0

    def test_corpus_con_datos(self, repo, articulo_simple, entidades_ejemplo):
        repo.guardar_articulo(articulo_simple)
        repo.guardar_ocr("art_001", "crudo", "limpio", 0.8, "kraken")
        repo.guardar_entidades("art_001", entidades_ejemplo)
        stats = repo.estadisticas_corpus()
        assert stats["total_articulos"] == 1
        assert stats["con_ocr"] == 1
        assert stats["con_entidades"] == 1
        assert stats["total_entidades"] == len(entidades_ejemplo)


class TestHistorialIA:
    def test_registrar_y_costo(self, repo, articulo_simple):
        repo.guardar_articulo(articulo_simple)
        repo.registrar_llamada_ia("ner", "anthropic", "claude-sonnet-4-6",
                                   1000, 200, 0.003, True, "art_001")
        repo.registrar_llamada_ia("tono", "anthropic", "claude-sonnet-4-6",
                                   500, 100, 0.0015, True, "art_001")
        costo = repo.costo_total_ia()
        assert abs(costo - 0.0045) < 0.0001

    def test_resumen_uso(self, repo, articulo_simple):
        repo.guardar_articulo(articulo_simple)
        repo.registrar_llamada_ia("ner", "anthropic", "claude-sonnet-4-6",
                                   1000, 200, 0.003, True)
        resumen = repo.resumen_uso_ia()
        assert len(resumen) == 1
        assert resumen[0]["etapa"] == "ner"
        assert resumen[0]["llamadas"] == 1
