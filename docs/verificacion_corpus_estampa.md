# Verificación del corpus *Estampa*, enero–mayo de 1939

Medición del 15 de noviembre de 2026 (hito A6 de [PLAN_MVP.md](../PLAN_MVP.md)).
Todas las cifras salen de ejecutar la aplicación, no se escribieron a mano: el
script maneja la interfaz real de Bashkar Station (los mismos métodos que los
botones, dentro del bucle de eventos de Tk) y escribe un JSON con lo que mide.

## Cómo se obtuvo

1. **Proyecto:** `scripts/importar_vision_ocr_a_proyecto.py` copia las 792
   transcripciones de `vision_ocr/salida/` (Claude Vision, lote de agosto de
   2026) a un proyecto nuevo, con su procedencia (`claude_vision`).
2. **Normalización por lote:** la etapa `norm` de `cli.py`, sobre la copia
   del proyecto (los originales de `vision_ocr/salida/` no se tocan).
3. **Interfaz de escritorio:** abrir proyecto → Segmentar (segmentador v1, el
   que usan todas las interfaces) → NER de corpus → Guardar → Fundir entidades
   canónicas → Tripletas «mencionado_en» → Exportar TEI → reabrir el proyecto.

Motor de NER: BERT (mrm8488/bert-spanish-cased-finetuned-ner); spaCy es_core_news_sm de respaldo. Equipo: portátil con GPU NVIDIA (el NER tardó
38 s; el grafo canónico, 168 s).

## Cifras

| Número | Páginas | Unidades editoriales |
|---|---:|---:|
| ene 1939 | 138 | 120 |
| feb 1939 | 178 | 145 |
| mar 1939 | 89 | 67 |
| abr 1939 | 214 | 169 |
| may 1939 | 173 | 138 |
| **Total** | **792** | **639** |

Cada unidad tiene un identificador estable y único (639 distintos).

| Entidades | Panel NER | Base del proyecto | Al reabrir |
|---|---:|---:|---:|
| Únicas (categoría + texto) | 7.605 | 7.605 | 7.605 |
| Pares entidad–unidad | 13.747 | 13.747 | 13.747 |

| Categoría | Entidades únicas |
|---|---:|
| personas | 4.261 |
| lugares | 2.014 |
| organizaciones | 1.213 |
| fechas | 117 |
| obras_publicaciones | 0 |
| eventos_historicos | 0 |

`obras_publicaciones` y `eventos_historicos` quedan en 0 porque el modelo BERT
solo reconoce personas, lugares, organizaciones y misceláneos: es una
limitación conocida del modelo, no una pérdida de datos.

| Grafo de conocimiento | |
|---|---:|
| Entidades canónicas | 7.359 |
| Relaciones | 3.816 |

El grafo funde variantes de una misma entidad (mayúsculas, acentos), por eso
tiene menos entidades canónicas (7.359) que entidades únicas el panel
(7.605).

| TEI P5 | |
|---|---:|
| Tamaño | 5.9 MB |
| Entidades en el TEI | 13.479 |
| Pares exportables esperados | 13.479 |
| Errores de validación | 0 |

El TEI omite las entidades de dos caracteres o menos (ruido de OCR): por eso
lleva 13.479 de los 13.747 pares.

## Lo que esta medición corrige

- **Unidades editoriales.** Hasta el 15-nov-2026 el escritorio segmentaba por
  defecto con el «segmentador avanzado (v2)» y daba **599** unidades; la CLI,
  la API y la web, **639**. Ahora todas usan v1. Sin normalizar antes, v1 da 636.
- **Entidades.** Antes de los hitos A1–A5 la base guardaba una entidad por
  unidad, el grafo se construía sobre ellas y el TEI no traía ninguna.

## Pendiente conocido

- El normalizador no es idempotente: en 41 de las 792 páginas, normalizar dos
  veces no da lo mismo que una. No afecta a esta medición (se normalizó una
  vez), pero conviene corregirlo después del lanzamiento.

Evidencia completa (JSON, registro y script): fuera del repositorio, en la
carpeta de evidencia del diagnóstico.
