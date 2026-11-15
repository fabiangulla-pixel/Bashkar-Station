# Derechos sobre el corpus *Estampa*

> **Las imágenes y los textos de *Estampa* se publican con autorización de la
> Biblioteca Nacional de Colombia.**
>
> Redacción provisional. Se ajustará a los términos exactos de la autorización
> (alcance, crédito exigido y condiciones de reutilización por terceros) antes
> del lanzamiento: hito E2 de [PLAN_MVP.md](PLAN_MVP.md).

## Qué cubre este aviso

*Estampa* fue una revista semanal ilustrada publicada en Bogotá. Este proyecto
trabaja con cinco números de 1939, de enero a mayo: **792 páginas**,
digitalizadas por la **Biblioteca Nacional de Colombia (BNC)**.

| Número | Páginas | Archivo de la BNC | Digitalización (fecha del PDF) | SHA-256 del PDF | Fuente en la BNC |
|---|---:|---|---|---|---|
| Enero de 1939 | 138 | `rev_estampa_ene_1939.pdf` | 27-mar-2018 | `af90b1bb…2212146e` | enlace pendiente |
| Febrero de 1939 | 178 | `rev_estampa_feb_1939.pdf` | 27-mar-2018 | `85958247…90c75333` | enlace pendiente |
| Marzo de 1939 | 89 | `rev_estampa_mar_1939.pdf` | 3-abr-2018 | `b8429a81…476eb452` | enlace pendiente |
| Abril de 1939 | 214 | `rev_estampa_abr_1939.pdf` | 27-mar-2018 | `95d8e4d3…1f6fcacb` | enlace pendiente |
| Mayo de 1939 | 173 | `rev_estampa_may_1939.pdf` | 20-abr-2018 | `a863f268…db4560b9` | enlace pendiente |

Los enlaces al registro de cada número en la colección digital de la BNC
están pendientes: no figuran en los PDF ni se encontraron con búsquedas
públicas, y no se van a inventar.

Las sumas SHA-256 completas permiten comprobar que un archivo es exactamente
el que digitalizó la BNC:

```
af90b1bb9812b8b8c5774e7a092bba134944bba591a036bc5d4846ec2212146e  rev_estampa_ene_1939.pdf
859582473ad90bbc9d97031c64002a44f91999ee20c3924b052cd72890c75333  rev_estampa_feb_1939.pdf
b8429a8177021a77c1886348e54ac594a9916e9976a64f7e7d502245476eb452  rev_estampa_mar_1939.pdf
95d8e4d336f7de3025694cd7e4a5fda9ab9845fc596ee9a1f7969d821f6fcacb  rev_estampa_abr_1939.pdf
a863f26840efe37a31dfc10fc45e6e7ddaacbabf701112d94577f534db4560b9  rev_estampa_may_1939.pdf
```

## Dónde está ese material

| Lugar | Contenido |
|---|---|
| *Release* `vision-ocr-entrada-v1` en GitHub | Las 792 páginas como imágenes, en 5 ZIP (uno por número) |
| `vision_ocr/salida/` | Transcripción de las 792 páginas (Claude Vision, agosto de 2026) |
| `vision_ocr/muestras_corpus/` | Muestra de 25 páginas transcritas y tipificadas a mano |
| `benchmark/`, `ground_truth_piloto/`, `tests/fixtures/` | Textos y referencias de páginas sueltas |
| `docs/e-rihs-2026-evidence/` | Una página de marzo de 1939 y sus exportaciones |
| Historial de git (commits del 27-ago al 29-sep de 2026) | 47 imágenes de páginas de marzo de 1939 |
| Demo pública (cuando se publique) | Imágenes, transcripciones, entidades, grafo y TEI de los 5 números |

## Lo que no cubre

- **La licencia Apache-2.0 del repositorio cubre solo el código fuente.** No
  se aplica a las imágenes ni a los textos de *Estampa*.
- Este aviso no concede a terceros ningún derecho de reutilización. Hasta que
  se publiquen las condiciones de la autorización (hito E2), quien quiera
  reutilizar imágenes o textos de *Estampa* debe consultar a la Biblioteca
  Nacional de Colombia.

## Cómo citar la fuente

> *Estampa* (Bogotá), enero–mayo de 1939. Digitalización: Biblioteca Nacional
> de Colombia.

Para citar el software, vea [CITATION.cff](CITATION.cff).
