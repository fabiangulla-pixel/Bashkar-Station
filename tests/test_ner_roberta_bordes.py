"""ner_roberta limpia la puntuación de los bordes de cada entidad (sesión 72).

Con páginas reales de Estampa (abril 1939) RoBERTa devolvió la persona
". Sen": la misma entidad quedaba dos veces en el índice.
"""

import core.ner_roberta_local as N


class _Pipe:
    tokenizer = None

    def __init__(self, ents):
        self.ents = ents

    def __call__(self, texto):
        return self.ents


def _correr(monkeypatch, palabras):
    ents = [{"word": w, "entity_group": "PER", "score": 0.99} for w in palabras]
    monkeypatch.setattr(N, "_pipeline_ner", lambda: _Pipe(ents))
    monkeypatch.setattr(N, "_fragmentar_por_tokens", lambda t, tok: [t])
    return sorted(e["texto"] for e in N.ner_roberta("texto cualquiera"))


def test_quita_puntuacion_de_los_bordes(monkeypatch):
    assert _correr(monkeypatch, [". Sen", "«Franco»", "(Bogotá)", "— Arciniegas,"]) == [
        "Arciniegas", "Bogotá", "Franco", "Sen"]


def test_conserva_iniciales_y_puntuacion_interna(monkeypatch):
    assert _correr(monkeypatch, ["Alicia A.", "S.A.", "O'Higgins"]) == [
        "Alicia A.", "O'Higgins", "S.A."]


def test_solo_puntuacion_se_descarta(monkeypatch):
    assert _correr(monkeypatch, [". ,", "«»"]) == []
