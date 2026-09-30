"""core/perfil_corpus.py — Lo que un análisis supone sobre el corpus.

Bashkar se calibró sobre *Estampa* (Bogotá, 1938-1940), y algunas de esas
suposiciones vivían como constantes en el código: el enlazador con Wikidata
premiaba descripciones que mencionan Colombia y descartaba entidades nacidas o
fundadas después de 1945. Con *Caras y Caretas* (Buenos Aires, 1898-1939) o
*El Gráfico* (Bogotá, 1910-1929) esas constantes empujan en la dirección
equivocada, sin aviso.

``PerfilCorpus`` las hace explícitas. El perfil por defecto es exactamente el
comportamiento anterior, de modo que nada cambia para *Estampa*; otro corpus
declara el suyo en el proyecto (clave ``perfil_corpus`` del ``.bashkar``).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class PerfilCorpus:
    id: str = "estampa"
    # Términos que, si aparecen en la descripción de un candidato de Wikidata,
    # sugieren que es el del país del corpus (desempate suave, no dominante).
    terminos_pais: tuple[str, ...] = ("colombia", "colombiano", "colombiana")
    # Entidades nacidas/fundadas después de este año no pueden ser las que
    # cita el corpus: se descartan como homónimos modernos.
    anio_fin: int = 1945
    notas: str = field(default="", compare=False)

    def es_por_defecto(self) -> bool:
        return self == POR_DEFECTO

    def firma(self) -> str:
        """Identificador estable de lo que cambia resultados (no las notas)."""
        datos = {"terminos_pais": sorted(self.terminos_pais), "anio_fin": self.anio_fin}
        return hashlib.sha1(json.dumps(datos, sort_keys=True).encode()).hexdigest()[:10]

    def como_dict(self) -> dict:
        d = asdict(self)
        d["terminos_pais"] = list(self.terminos_pais)
        return d

    @classmethod
    def desde_dict(cls, datos: dict | None) -> PerfilCorpus:
        """Perfil desde el proyecto; claves ausentes toman el valor por defecto."""
        if not datos:
            return POR_DEFECTO
        base = POR_DEFECTO.como_dict()
        base.update({k: v for k, v in datos.items() if k in base})
        base["terminos_pais"] = tuple(t.lower() for t in base["terminos_pais"])
        base["anio_fin"] = int(base["anio_fin"])
        return cls(**base)


POR_DEFECTO = PerfilCorpus()
