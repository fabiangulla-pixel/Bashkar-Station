"""core/identidad_articulo.py — Contrato A1: el id de un artículo.

Único sitio donde se acuña la identidad de un artículo. Todo productor y todo
consumidor deben pasar por aquí.

**Por qué existe.** Antes convivían nueve formas distintas de acuñar el id, y no
eran compatibles entre sí:

    str(row.get("id", row.get("titulo", f"art_{i}")))   productores de NER
    tf.stem                                             NER desde archivos .txt
    str(i)                                              paneles de revisión
    str(row.get("numero")) + "_" + str(row.get("pagina"))
    f"art_{i:04d}"                                      TODOS los exportadores
    str(row.get("id", row.name))
    a.get("id", str(i))                                 cli.py, servidor_web.py
    art.get("id", f"art_{i:04d}")                       pipeline_maestro

Los productores de NER caían a `titulo`; los exportadores usaban `art_%04d`.
Nunca podían coincidir: por eso el índice NER de Proyecto_04 tenía 184 entidades
y la exportación TEI lograba asignar **0**.

**El daño no era solo de enlace.** `articulos.id` es `TEXT PRIMARY KEY` y
`Repositorio.guardar_articulo` inserta con `ON CONFLICT(id) DO UPDATE`. Con el
título como id, dos artículos homónimos se pisan **en silencio**: uno sobrevive
y el otro desaparece sin error. Medido sobre el corpus real de Proyecto_04
(``articulos.csv``, 138 filas): 117 títulos distintos, 18 repetidos, **21
artículos perdidos (15 %)**. Los que se repiten son justo lo que se repite en
una revista — "Especial para ESTAMPA" ×3, "A cargo de COLETTE." ×3.

**Forma del id:** ``<numero>_p<pagina>_<orden>``, por ejemplo
``rev_estampa_mar_1939_p0017_02``.

**Estabilidad.** El id se deriva del contenido bibliográfico (número de la
publicación, página de inicio y posición dentro de esa página), no de un
contador global. Reprocesar el mismo PDF con la misma segmentación devuelve los
mismos ids, así que las anotaciones y el NER siguen enlazados. Lo que sí lo
mueve es un cambio en la segmentación: si un artículo se parte en dos, cambia el
orden dentro de esa página. Es inherente a identificar por posición y no se
puede evitar sin un identificador persistido; se documenta en vez de fingir que
no pasa.
"""

from __future__ import annotations

import ast
import re
import unicodedata
from collections import Counter
from typing import Iterable

__all__ = [
    "SIN_NUMERO",
    "id_articulo",
    "asignar_ids",
    "primera_pagina",
    "slug_numero",
]

SIN_NUMERO = "sin_numero"

_RE_NO_ALFANUM = re.compile(r"[^a-z0-9]+")
_RE_DIGITOS = re.compile(r"\d+")


def slug_numero(numero: str | None) -> str:
    """Normaliza el número de la publicación a un fragmento seguro de id.

    Se quitan las tildes en vez de sustituirlas por "_": el campo `numero` de un
    corpus real llega con basura de OCR ("Páginas desderev_estampa_mar_1939"), y
    convertir cada tilde en separador produce ids ilegibles y frágiles frente a
    variaciones de acentuación de la misma cadena.
    """
    texto = (numero or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = _RE_NO_ALFANUM.sub("_", texto).strip("_")
    return texto or SIN_NUMERO


def primera_pagina(paginas) -> int:
    """Primera página de un artículo, venga como venga.

    En `articulos.csv` la columna llega como el repr de una lista ("[3, 4, 5]"),
    porque el CSV lo escribe pandas desde una celda que contiene una lista. Se
    aceptan además int, lista real y cadenas sueltas; lo que no se pueda leer da
    0, que es una página imposible y por tanto detectable.
    """
    if isinstance(paginas, bool):
        return 0
    if isinstance(paginas, int):
        return max(paginas, 0)
    if isinstance(paginas, (list, tuple)):
        for p in paginas:
            try:
                return max(int(p), 0)
            except (TypeError, ValueError):
                continue
        return 0
    texto = str(paginas or "").strip()
    if not texto:
        return 0
    try:
        valor = ast.literal_eval(texto)
    except (ValueError, SyntaxError):
        valor = None
    if isinstance(valor, (list, tuple, int)) and not isinstance(valor, bool):
        return primera_pagina(valor)
    m = _RE_DIGITOS.search(texto)
    return int(m.group()) if m else 0


def id_articulo(numero: str | None, paginas, orden: int = 1) -> str:
    """Acuña el id de un artículo.

    orden: posición (desde 1) entre los artículos que empiezan en esa misma
    página. Para asignarlo automáticamente sobre un corpus, usar `asignar_ids`.
    """
    return f"{slug_numero(numero)}_p{primera_pagina(paginas):04d}_{max(int(orden), 1):02d}"


def asignar_ids(filas: Iterable[dict], campo_numero: str = "numero",
                campo_paginas: str = "paginas") -> list[str]:
    """Ids de un corpus completo, en el orden en que llegan las filas.

    El `orden` se calcula contando cuántos artículos previos empiezan en la
    misma página del mismo número, así que dos artículos distintos nunca reciben
    el mismo id aunque compartan título, autor y página.

    Verificado sobre el corpus real de Proyecto_04 (138 filas): 138 ids
    distintos, 0 colisiones — frente a los 21 artículos que hoy se pierden al
    usar el título como clave primaria.
    """
    vistos: Counter = Counter()
    ids: list[str] = []
    for fila in filas:
        numero = fila.get(campo_numero)
        paginas = fila.get(campo_paginas)
        clave = (slug_numero(numero), primera_pagina(paginas))
        vistos[clave] += 1
        ids.append(id_articulo(numero, paginas, vistos[clave]))
    return ids
