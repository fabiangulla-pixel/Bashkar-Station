"""Tests de los 4 módulos portados de ¡Quac! a Bashkar Station:
frame_engine, validacion_engine, sentimiento_discriminante, revision_engine.

Todos offline, sin red ni LLM.
"""

import sqlite3

import pytest

from core import (
    frame_engine,
    revision_engine,
    sentimiento_discriminante,
    validacion_engine,
)

# ──────────────────────────────────────────────────────────────────────────
# frame_engine
# ──────────────────────────────────────────────────────────────────────────

def test_frame_guerra_dominante():
    texto = ("El frente republicano resistió la ofensiva del ejército "
             "nacionalista en la batalla; las tropas avanzaron entre trincheras.")
    r = frame_engine.analizar_frame(texto)
    assert r["frame_dominante"] == "guerra"
    assert r["total_marcadores"] >= 3
    assert r["distribucion"][0]["frame"] == "guerra"


def test_frame_modernidad():
    texto = ("La vida moderna trae el automóvil, la aviación y la electricidad; "
             "un adelanto que transforma la metrópoli con velocidad y confort.")
    r = frame_engine.analizar_frame(texto)
    assert r["frame_dominante"] == "modernidad"


def test_frame_mujer_social():
    texto = ("La dama luce un vestido de gran elegancia en el salón; la moda "
             "femenina y la belleza marcan la recepción de sociedad.")
    r = frame_engine.analizar_frame(texto)
    assert r["frame_dominante"] == "mujer_social"


def test_frame_texto_vacio():
    r = frame_engine.analizar_frame("")
    assert r["frame_dominante"] is None
    assert r["distribucion"] == []
    assert r["total_marcadores"] == 0


def test_frame_sin_marcadores():
    r = frame_engine.analizar_frame("xyz qwerty zzz uuu")
    assert r["frame_dominante"] is None


def test_registrar_marcos_personalizados_extiende_y_crea():
    n_antes = len(frame_engine.FRAMES["guerra"]["marcadores"])
    frame_engine.registrar_marcos_personalizados({
        "guerra": ["legionario"],            # extiende existente
        "deporte": ["fútbol", "campeonato"], # crea nuevo
    })
    try:
        assert len(frame_engine.FRAMES["guerra"]["marcadores"]) == n_antes + 1
        assert "deporte" in frame_engine.FRAMES
        r = frame_engine.analizar_frame("El campeonato de fútbol reunió aficionados.")
        assert r["frame_dominante"] == "deporte"
    finally:
        # limpieza para no contaminar otros tests
        frame_engine.FRAMES["guerra"]["marcadores"].remove("legionario")
        del frame_engine.FRAMES["deporte"]


def test_analizar_corpus_frames():
    corpus = {
        "a1": "guerra frente batalla ejército tropa",
        "a2": "guerra ofensiva soldado trinchera",
        "a3": "moda mujer elegancia vestido salón",
    }
    r = frame_engine.analizar_corpus_frames(corpus)
    assert r["n_articulos"] == 3
    assert r["dominante_corpus"] == "guerra"
    assert r["distribucion_corpus"]["guerra"] == 2


def test_cruce_seccion_frame():
    por_art = {
        "a1": frame_engine.analizar_frame("guerra batalla frente ejército"),
        "a2": frame_engine.analizar_frame("moda mujer vestido elegancia salón"),
    }
    seccion = {"a1": "Internacional", "a2": "Sociales"}
    m = frame_engine.cruce_seccion_frame(por_art, seccion)
    assert m["Internacional"]["guerra"] == 1
    assert m["Sociales"]["mujer_social"] == 1


def test_cruce_seccion_frame_con_textos_crudos():
    # Pasar {art_id: texto} (strings) en vez de resultados de analizar_frame
    # no debe reventar: se analizan al vuelo (antes daba AttributeError).
    por_art = {
        "a1": "guerra batalla frente ejército",
        "a2": "moda mujer vestido elegancia salón",
    }
    seccion = {"a1": "Internacional", "a2": "Sociales"}
    m = frame_engine.cruce_seccion_frame(por_art, seccion)
    assert m["Internacional"]["guerra"] == 1
    assert m["Sociales"]["mujer_social"] == 1


# ──────────────────────────────────────────────────────────────────────────
# sentimiento_discriminante
# ──────────────────────────────────────────────────────────────────────────

def test_polaridad_positiva():
    r = sentimiento_discriminante.analizar_polaridad(
        "Un triunfo glorioso, esplendor y grandeza; homenaje al ilustre talento.")
    assert r["polaridad"] == "positivo"
    assert r["score"] > 0


def test_polaridad_negativa():
    r = sentimiento_discriminante.analizar_polaridad(
        "La tragedia, la miseria y el horror de la guerra; muerte y destrucción.")
    assert r["polaridad"] == "negativo"
    assert r["score"] < 0


def test_polaridad_negacion_invierte():
    # "sin gloria" → la negación previa invierte el término positivo
    base = sentimiento_discriminante.analizar_polaridad("gloria gloria gloria")
    neg = sentimiento_discriminante.analizar_polaridad("sin gloria sin gloria")
    assert base["polaridad"] == "positivo"
    assert neg["score"] < base["score"]


def test_polaridad_vacia_neutro():
    r = sentimiento_discriminante.analizar_polaridad("")
    assert r["polaridad"] == "neutro"
    assert r["score"] == 0.0


def test_polaridad_un_solo_signo_diluido_no_neutro():
    # Texto largo con pocos términos negativos (score cercano a 0 por dilución)
    # pero TODOS del mismo signo → debe ser negativo, no neutro.
    texto = ("El acontecimiento ocurrido durante aquella jornada de la temporada "
             "resultó en una verdadera tragedia para los presentes en el lugar.")
    r = sentimiento_discriminante.analizar_polaridad(texto)
    assert r["n_neg"] >= 1 and r["n_pos"] == 0
    assert r["polaridad"] == "negativo"


def test_polaridad_balanceada_es_neutra():
    # Igual número de marcas pos y neg → ambivalente → neutro.
    r = sentimiento_discriminante.analizar_polaridad("triunfo glorioso pero tragedia y muerte")
    assert r["n_pos"] >= 1 and r["n_neg"] >= 1
    assert r["polaridad"] == "neutro"


def test_polaridad_hacia_entidad():
    texto = ("Franco impuso terror y destrucción sobre el pueblo. "
             "En otro tema, el clima fue agradable y la cosecha próspera.")
    r = sentimiento_discriminante.polaridad_hacia(texto, ["Francisco Franco", "Franco"])
    assert r["n_menciones"] >= 1
    assert r["polaridad"] == "negativo"


def test_polaridad_hacia_corpus_no_cruza_articulos():
    # La entidad aparece en un artículo negativo; el siguiente artículo es muy
    # positivo. La ventana NO debe cruzar de artículo → polaridad hacia la
    # entidad debe ser negativa (no diluida por el artículo vecino).
    arts = [
        "Franco impuso terror y destrucción sobre el pueblo.",
        "Qué triunfo glorioso, esplendor y grandeza; un homenaje admirable.",
    ]
    r = sentimiento_discriminante.polaridad_hacia_corpus(arts, ["Franco"])
    assert r["n_menciones"] == 1
    assert r["n_documentos"] == 1
    assert r["polaridad"] == "negativo"


def test_polaridad_hacia_corpus_sin_menciones():
    r = sentimiento_discriminante.polaridad_hacia_corpus(
        ["texto uno", "texto dos"], ["Mussolini"])
    assert r["n_menciones"] == 0
    assert r["polaridad"] == "neutro"


def test_polaridad_hacia_sin_menciones():
    r = sentimiento_discriminante.polaridad_hacia("texto cualquiera", ["Mussolini"])
    assert r["n_menciones"] == 0
    assert r["polaridad"] == "neutro"


def test_indice_polarizacion_afectiva():
    # cobertura dividida pos/neg → polarización alta
    alta = sentimiento_discriminante.indice_polarizacion_afectiva(
        {"positivo": 5, "negativo": 5, "neutro": 0})
    # cobertura concentrada en un signo → baja
    baja = sentimiento_discriminante.indice_polarizacion_afectiva(
        {"positivo": 10, "negativo": 0, "neutro": 0})
    nula = sentimiento_discriminante.indice_polarizacion_afectiva(
        {"positivo": 0, "negativo": 0, "neutro": 10})
    assert alta == 1.0
    assert baja == 0.0
    assert nula == 0.0


def test_distribucion_polaridad():
    textos = ["triunfo glorioso esplendor", "tragedia horror muerte", "mesa silla"]
    d = sentimiento_discriminante.distribucion_polaridad(textos)
    assert d["positivo"] == 1
    assert d["negativo"] == 1
    assert d["neutro"] == 1


def test_transformer_inerte_en_314():
    # En Python 3.14 debe reportar no disponible (no debe intentar cargar torch)
    import sys
    if sys.version_info[:2] >= (3, 14):
        assert sentimiento_discriminante.transformer_disponible() is False


# ──────────────────────────────────────────────────────────────────────────
# validacion_engine  (Kappa de Cohen)
# ──────────────────────────────────────────────────────────────────────────

def test_kappa_acuerdo_perfecto():
    pares = [("pos", "pos"), ("neg", "neg"), ("neu", "neu"), ("pos", "pos")]
    assert validacion_engine._kappa_cohen(pares) == 1.0


def test_kappa_peor_que_azar_negativo():
    pares = [("pos", "neg"), ("neg", "pos"), ("pos", "neg"), ("neg", "pos")]
    assert validacion_engine._kappa_cohen(pares) < 0


def test_interpreta_kappa():
    assert validacion_engine._interpreta_kappa(1.0) == "casi perfecto"
    assert validacion_engine._interpreta_kappa(0.65) == "sustancial"
    assert validacion_engine._interpreta_kappa(-0.1).startswith("pobre")


def test_exportar_muestra_y_concordancia(tmp_path):
    articulos = [
        {"art_id": f"a{i}", "texto": f"contenido {i}", "seccion": "S",
         "titulo": f"T{i}"}
        for i in range(50)
    ]
    ruta = tmp_path / "muestra.csv"
    validacion_engine.exportar_muestra(
        articulos, ruta, n=10, semilla=42,
        etiqueta_auto=lambda a: "positivo", nombre_etiqueta="polaridad")
    assert ruta.exists()

    # Reproducibilidad: misma semilla → misma muestra
    ruta2 = tmp_path / "muestra2.csv"
    validacion_engine.exportar_muestra(
        articulos, ruta2, n=10, semilla=42,
        etiqueta_auto=lambda a: "positivo", nombre_etiqueta="polaridad")
    assert ruta.read_text(encoding="utf-8-sig") == ruta2.read_text(encoding="utf-8-sig")

    # Sin codificación manual → error informativo
    r = validacion_engine.calcular_concordancia(ruta, nombre_etiqueta="polaridad")
    assert r["n"] == 0
    assert "error" in r


def test_concordancia_con_codificacion(tmp_path):
    import csv
    ruta = tmp_path / "cod.csv"
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["polaridad_auto", "polaridad_manual"])
        w.writeheader()
        # 8 de 10 coinciden
        filas = [("positivo", "positivo")] * 4 + [("negativo", "negativo")] * 4 + \
                [("positivo", "negativo"), ("neutro", "positivo")]
        for auto, man in filas:
            w.writerow({"polaridad_auto": auto, "polaridad_manual": man})
    r = validacion_engine.calcular_concordancia(ruta, nombre_etiqueta="polaridad")
    assert r["n"] == 10
    assert r["acuerdo"] == 0.8
    assert -1.0 <= r["kappa"] <= 1.0
    assert "matriz_confusion" in r


# ──────────────────────────────────────────────────────────────────────────
# revision_engine  (human-in-the-loop)
# ──────────────────────────────────────────────────────────────────────────

@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    yield c
    c.close()


def _indice_demo():
    # {categoria: {entidad: [art_ids]}}  ← formato de ner_engine
    return {
        "personas": {
            "Franco": ["a1", "a2", "a3", "a4"],   # 4 arts → verde, no entra
            "Lopez": ["a1", "a2"],                # 2 arts → amarillo
            "Ruido OCR": ["a1"],                  # 1 art → rojo
        },
        "lugares": {
            "España": ["a1", "a2", "a3"],         # 3 arts → verde
            "Bgta": ["a1"],                       # 1 art → rojo
        },
    }


def test_construir_cola_solo_dudosas():
    cola = revision_engine.construir_cola(_indice_demo())
    nombres = {c["nombre"] for c in cola}
    assert "Franco" not in nombres      # verde (4 arts)
    assert "España" not in nombres      # verde (3 arts)
    assert "Lopez" in nombres           # amarillo
    assert "Ruido OCR" in nombres       # rojo
    assert "Bgta" in nombres            # rojo
    # ordenadas peor primero (rojo antes que amarillo)
    assert cola[0]["nivel"] == revision_engine.confianza_engine.ROJO


def test_construir_cola_kb_respaldada():
    # "Ruido OCR" entra en KB → no debe aparecer en la cola
    cola = revision_engine.construir_cola(_indice_demo(), kb={"ruido ocr"})
    nombres = {c["nombre"] for c in cola}
    assert "Ruido OCR" not in nombres


def test_flujo_persistencia_y_decision(con):
    cola = revision_engine.construir_cola(_indice_demo())
    revision_engine.guardar_cola(con, cola)
    pend = revision_engine.pendientes(con)
    assert len(pend) == len(cola)

    # decidir descartar "Ruido OCR" y renombrar "Bgta" → "Bogotá"
    assert revision_engine.decidir(con, "Ruido OCR", "personas",
                                   revision_engine.DESCARTADA)
    assert revision_engine.decidir(con, "Bgta", "lugares",
                                   revision_engine.RENOMBRADA,
                                   nombre_nuevo="Bogotá")

    stats = revision_engine.estadisticas(con)
    assert stats["descartadas"] == 1
    assert stats["renombradas"] == 1

    # guardar_cola otra vez no debe pisar decisiones tomadas
    revision_engine.guardar_cola(con, cola)
    stats2 = revision_engine.estadisticas(con)
    assert stats2["descartadas"] == 1
    assert stats2["renombradas"] == 1


def test_decidir_invalida(con):
    with pytest.raises(ValueError):
        revision_engine.decidir(con, "X", "personas", "borrar_todo")


def test_aplicar_revisiones():
    indice = _indice_demo()
    decisiones = {
        ("Ruido OCR", "personas"): {"decision": revision_engine.DESCARTADA,
                                    "nombre_nuevo": ""},
        ("Bgta", "lugares"): {"decision": revision_engine.RENOMBRADA,
                              "nombre_nuevo": "Bogotá"},
    }
    out = revision_engine.aplicar_revisiones(indice, decisiones)
    assert "Ruido OCR" not in out["personas"]
    assert "Bgta" not in out["lugares"]
    assert "Bogotá" in out["lugares"]
    assert out["lugares"]["Bogotá"] == ["a1"]
