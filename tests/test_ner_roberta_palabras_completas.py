"""Las entidades de BERT son palabras completas del texto original.

Medido el 15-nov-2026 sobre Estampa ene–may 1939: 1.263 de 13.747 menciones
(9,19 %) no correspondían a palabras completas del texto: «# # anese»,
«ttmann», «Alfonso Fuenmayo», «D Annunzio», «Manuel. Alvarez Angulo». Con la
agregación «simple», si el modelo etiqueta distinto los subtokens de una
palabra, la corta; y el texto decodificado por el tokenizador no es el
original. Ahora el texto se toma del original por posición y se amplía a la
palabra completa.
"""

import core.ner_roberta_local as N


class _Pipe:
    tokenizer = None

    def __init__(self, ents):
        self.ents = ents

    def __call__(self, texto):
        return self.ents


def _correr(monkeypatch, texto, ents):
    monkeypatch.setattr(N, "_pipeline_ner", lambda: _Pipe(ents))
    monkeypatch.setattr(N, "_fragmentar_por_tokens", lambda t, tok: [t])
    return sorted((e["texto"], e["categoria"]) for e in N.ner_roberta(texto))


def _ent(texto, trozo, grupo="PER", score=0.9, word=None, desde=0):
    i = texto.index(trozo, desde)
    return {"word": word or trozo, "entity_group": grupo, "score": score,
            "start": i, "end": i + len(trozo)}


def test_un_trozo_de_palabra_se_amplia_a_la_palabra():
    assert N.expandir_a_palabra("visitó a Hauptmann ayer", 13, 18) == (9, 18)
    assert N.expandir_a_palabra("visitó a Hauptmann ayer", 9, 12) == (9, 18)
    assert N.expandir_a_palabra("en Bogotá, ayer", 3, 9) == (3, 9)      # ya completa
    assert N.expandir_a_palabra("D'Annunzio habló", 2, 10) == (0, 10)   # apóstrofo interno


def test_fragmentos_de_una_palabra_dan_una_sola_entidad(monkeypatch):
    t = "El escritor Hauptmann visitó Bogotá."
    ents = [_ent(t, "Haup", word="Haup"), _ent(t, "tmann", word="##tmann", score=0.7),
            _ent(t, "Bogotá", "LOC")]
    assert _correr(monkeypatch, t, ents) == [("Bogotá", "lugares"), ("Hauptmann", "personas")]


def test_el_texto_sale_del_original_no_del_tokenizador(monkeypatch):
    t = "Habló D'Annunzio con Manuel Álvarez\nAngulo en la Federación [Americana] del Trabajo."
    ents = [_ent(t, "D'Annunzio", word="D Annunzio"),
            _ent(t, "Manuel Álvarez\nAngulo", word="Manuel. Alvarez Angulo")]
    assert _correr(monkeypatch, t, ents) == [
        ("D'Annunzio", "personas"), ("Manuel Álvarez Angulo", "personas")]


def test_trozos_con_etiquetas_distintas_gana_la_de_mayor_confianza(monkeypatch):
    t = "Llegó Fuenmayor a Barranquilla."
    ents = [_ent(t, "Fuenmayo", "PER", 0.95), _ent(t, "r", "ORG", 0.61, desde=t.index("Fuenmayor") + 8)]
    assert _correr(monkeypatch, t, ents) == [("Fuenmayor", "personas")]


def test_sin_posiciones_sigue_funcionando_como_antes(monkeypatch):
    ents = [{"word": "Arciniegas", "entity_group": "PER", "score": 0.99}]
    assert _correr(monkeypatch, "texto", ents) == [("Arciniegas", "personas")]


# ── Fragmentos literales del texto original ───────────────────────────────────

class _TokFalso:
    """Un token por palabra; como un tokenizador «fast», da posiciones. Su
    decode pierde las palabras «desconocidas», como el real con [UNK]."""

    def __call__(self, texto, add_special_tokens=False, return_offsets_mapping=False):
        import re
        ms = list(re.finditer(r"\S+", texto))
        d = {"input_ids": list(range(len(ms)))}
        if return_offsets_mapping:
            d["offset_mapping"] = [(m.start(), m.end()) for m in ms]
        return d

    def decode(self, ids, skip_special_tokens=True):
        return "TEXTO RECONSTRUIDO"


def test_los_fragmentos_son_trozos_literales_del_original(monkeypatch):
    monkeypatch.setattr(N, "_VENTANA_TOKENS", 6)
    monkeypatch.setattr(N, "_SOLAPE_TOKENS", 2)
    texto = "Alfonso Jaramillo Arango y D'Annunzio hablaron\nen Bogotá con Manuel J. Álvarez Angulo ayer"
    frags = N._fragmentar_por_tokens(texto, _TokFalso())
    assert len(frags) > 1
    assert all(f in texto for f in frags)                 # literales, no reconstruidos
    assert "Alfonso Jaramillo Arango" in frags[0]
    cubierto = set()
    for f in frags:
        i = texto.index(f)
        cubierto.update(range(i, i + len(f)))
    assert all(i in cubierto for i, c in enumerate(texto) if not c.isspace())   # nada se pierde


def test_texto_corto_no_se_fragmenta():
    assert N._fragmentar_por_tokens("Bogotá, 1939", _TokFalso()) == ["Bogotá, 1939"]
