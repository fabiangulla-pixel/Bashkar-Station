"""core.ocr.enrutador y core.ocr.desacuerdo, con motores simulados (sin GPU)."""

import json

import pytest

from core.ocr import Bloque, ResultadoOCR
from core.ocr.desacuerdo import comparar, discrepancia_caracteres, palabras_en_disputa
from core.ocr.enrutador import Enrutador, cargar_politica, necesita_segunda_opinion

TEXTO_BUENO = ("La revista publicó en marzo una crónica sobre la llegada del nuevo "
               "embajador a la capital y la recepción en el palacio presidencial. ") * 8


class _Motor:
    def __init__(self, nombre, texto=TEXTO_BUENO, conf=95.0, bloques=(), disponible=True,
                 falla=False):
        self.nombre = self.etiqueta = nombre
        self.texto, self.conf, self.bloques = texto, conf, list(bloques)
        self._disp, self._falla, self.llamadas, self.liberado = disponible, falla, 0, False

    def motivo_no_disponible(self):
        return None if self._disp else "no instalado"

    def version(self):
        return f"{self.nombre} 1"

    def reconocer(self, imagen):
        self.llamadas += 1
        if self._falla:
            raise RuntimeError("caído")
        return ResultadoOCR(self.texto, self.nombre, self.version(), confianza=self.conf,
                            bloques=[Bloque(b.texto, b.bbox, b.tipo, b.orden, b.confianza)
                                     for b in self.bloques])

    def liberar(self):
        self.liberado = True


def _enrutador(motores: dict, **cambios):
    pol = cargar_politica()
    pol["enrutador"].update(primarios=["a", "b"], segundos=["c", "b"], respaldo="r")
    for seccion, valores in cambios.items():
        pol[seccion].update(valores)
    return Enrutador(politica=pol, crear=lambda n, **_: motores[n])


# ── desacuerdo ───────────────────────────────────────────────────────────────
def test_discrepancia_ignora_espacios():
    assert discrepancia_caracteres("hola  mundo\n", "hola mundo") == 0.0
    assert discrepancia_caracteres("", "") == 0.0
    assert discrepancia_caracteres("abc", "xyz") == 1.0


def test_disputas_son_pares_legibles():
    assert palabras_en_disputa("murió en Francia", "murió en Franco") == [("Francia", "Franco")]


def test_comparar_marca_bloques_en_duda_y_guarda_alternativa():
    p = ResultadoOCR("Rumania x", "pp", "1", bloques=[
        Bloque("Rumania", (0, 0, 100, 20)), Bloque("x", (0, 50, 100, 70))])
    s = ResultadoOCR("Rumonia x", "surya", "1", bloques=[
        Bloque("Rumonia", (2, 1, 101, 21)), Bloque("x", (0, 51, 99, 70))])
    c = comparar(p, s, umbral_bloque=0.1)
    assert c.bloques_en_duda == 1
    assert p.bloques[0].revisar and not p.bloques[1].revisar
    assert p.bloques[0].alternativas[0]["texto"] == "Rumonia"


def test_comparar_sin_solapamiento_no_inventa_pareja():
    p = ResultadoOCR("a", "pp", "1", bloques=[Bloque("a", (0, 0, 10, 10))])
    s = ResultadoOCR("b", "s", "1", bloques=[Bloque("b", (500, 500, 510, 510))])
    assert comparar(p, s).bloques_en_duda == 0 and not p.bloques[0].alternativas


# ── enrutador ────────────────────────────────────────────────────────────────
def test_primario_salta_motores_no_disponibles():
    e = _enrutador({"a": _Motor("a", disponible=False), "b": _Motor("b"), "c": _Motor("c"),
                    "r": _Motor("r")})
    assert e.primario() == "b" and e.segundo("b") == "c"


def test_ninguno_disponible_lanza():
    e = _enrutador({n: _Motor(n, disponible=False) for n in "abcr"})
    with pytest.raises(RuntimeError):
        e.primario()


def test_texto_nativo_bueno_no_ocr(tmp_path):
    ms = {n: _Motor(n) for n in "abcr"}
    r, fila = _enrutador(ms).procesar(tmp_path / "p1.png", tmp_path / "p1.txt", "N",
                                      texto_nativo=TEXTO_BUENO)
    assert fila["ruta"] == "nativo" and ms["a"].llamadas == 0
    assert (tmp_path / "p1.txt").read_text("utf-8") == TEXTO_BUENO


def test_texto_nativo_basura_va_a_ocr(tmp_path):
    ms = {n: _Motor(n) for n in "abcr"}
    basura = " ".join(["a b c d e f g h"] * 30)
    _, fila = _enrutador(ms).procesar(tmp_path / "p1.png", tmp_path / "p1.txt", "N",
                                      texto_nativo=basura)
    assert fila["ruta"] == "a" and ms["a"].llamadas == 1


def test_confianza_alta_sin_segunda_opinion(tmp_path):
    ms = {n: _Motor(n) for n in "abcr"}
    _, fila = _enrutador(ms).procesar(tmp_path / "p1.png", tmp_path / "p1.txt", "N")
    assert "segunda_opinion" not in fila and ms["c"].llamadas == 0


def test_confianza_baja_pide_segunda_y_discrepancia_marca_revision(tmp_path):
    ms = {"a": _Motor("a", conf=40.0), "b": _Motor("b"),
          "c": _Motor("c", texto=TEXTO_BUENO.replace("embajador", "embojodor")
                                            .replace("capital", "copitol")),
          "r": _Motor("r")}
    _, fila = _enrutador(ms, revision={"discrepancia_pagina": 0.001}).procesar(
        tmp_path / "p1.png", tmp_path / "p1.txt", "N")
    assert fila["segunda_opinion"] == "c" and fila["revision"]
    alt = json.loads((tmp_path / "p1.alternativas.json").read_text("utf-8"))
    assert alt["alternativas"][0]["motor"] == "c"
    # La segunda lectura NO se escribe como .txt: entraría al corpus.
    assert sorted(p.suffix for p in tmp_path.glob("*.txt")) == [".txt"]


def test_segunda_opinion_que_falla_no_tumba_la_pagina(tmp_path):
    ms = {"a": _Motor("a", conf=40.0), "b": _Motor("b"), "c": _Motor("c", falla=True),
          "r": _Motor("r")}
    r, fila = _enrutador(ms).procesar(tmp_path / "p1.png", tmp_path / "p1.txt", "N")
    assert r is not None and fila["segunda_opinion"] == "c (falló)"


def test_primario_caido_usa_respaldo(tmp_path):
    ms = {"a": _Motor("a", falla=True), "b": _Motor("b"), "c": _Motor("c"), "r": _Motor("r")}
    _, fila = _enrutador(ms).procesar(tmp_path / "p1.png", tmp_path / "p1.txt", "N")
    assert fila["metodo"] == "r_respaldo_de_a" and fila["revision"]


def test_liberar_suelta_todos_los_motores(tmp_path):
    ms = {n: _Motor(n) for n in "abcr"}
    with _enrutador(ms) as e:
        e.procesar(tmp_path / "p1.png", tmp_path / "p1.txt", "N")
    assert ms["a"].liberado


def test_politica_lee_toml(tmp_path):
    t = tmp_path / "ocr.toml"
    t.write_text('[revision]\ndiscrepancia_pagina = 0.5\n', "utf-8")
    pol = cargar_politica(t)
    assert pol["revision"]["discrepancia_pagina"] == 0.5
    assert pol["enrutador"]["respaldo"] == "tesseract"     # el resto, por defecto


def test_bloque_con_error_pide_segunda():
    r = ResultadoOCR(TEXTO_BUENO, "a", "1", confianza=99.0,
                     bloques=[Bloque("x", (0, 0, 1, 1), revisar=True)])
    assert necesita_segunda_opinion(r, cargar_politica())[0]
