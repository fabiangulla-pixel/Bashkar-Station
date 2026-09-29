# Benchmark OCR

Mide las rutas de OCR de Bashkar contra **transcripciones humanas** y detecta
regresiones antes de publicar un cambio. Código: `core/benchmark_regresion.py`;
CLI: `scripts/benchmark_ocr_regresion.py`.

## Estado actual

`estampa-1939/` tiene las 47 páginas del piloto de marzo de 1939, **sin
referencias todavía**. Los archivos `referencia/*.txt` están vacíos a propósito.

Los juicios de `ground_truth_piloto/*/juicios/` los produjo un modelo de IA
(`accuracy_estimate`). **No son verdad de referencia** y el benchmark se niega a
medir contra ellos: un CER calculado contra la opinión de un modelo parece
riguroso y no vale nada.

Rutas ya cargadas en `estampa-1939/salidas/`:

| Ruta | Origen |
|---|---|
| `tesseract` | `core.ocr_engine.ocr_pagina` (la función de la app), generada el 29-sep-2026 |
| `vision_llm` | Pase de IA de visión, `vision_ocr/salida/rev_estampa_mar_1939/` |
| `candidato_piloto` | Texto candidato del piloto (`_prueba5/03_ocr`), el mismo que vio el juez de IA |

**Limitación de las imágenes del piloto:** están reducidas a ~1063×1500 px
(se achicaron para el juez de IA). A esa resolución la ruta `zonas` (deskew +
bloques RLSA) clasifica bloques de texto como fotografía y recupera 1-96
palabras donde Tesseract de página completa saca ~600: por eso no se cargó.
Para medir `zonas` en serio hacen falta las imágenes a resolución completa
(asset del release `vision-ocr-entrada-v1`).

Las imágenes (`ground_truth_piloto/*/imagenes/`) **no están en el repositorio**
por las condiciones de uso de la BNC: quien clone el proyecto debe obtenerlas
aparte. Las referencias y las salidas son texto y sí se versionan.

## Cómo completarlo

1. En `estampa-1939/benchmark.json`, escribe tu nombre en
   `referencia.transcriptor`.
2. Transcribe cada página en `referencia/<page_id>.txt`. Sigue las reglas de
   `core/estandar_oro.py`: se copia lo que se ve, con la ortografía de la
   época, sin corregir a la revista.
3. **No prellenes** con la salida de un motor. Si lo haces, anota cuál en
   `referencia.prellenado_con`: esa ruta queda excluida de la medición,
   porque corregir su propia salida la favorece.
4. Si puedes, completa `tipografia` y `calidad_imagen` en cada caso. Así los
   resultados se desglosan por estrato.

Con 20 páginas o más la herramienta deja de advertir que la muestra es ruido.
Para comparar revistas o años se necesitan al menos 20 páginas por estrato.

## Uso

```bash
python scripts/benchmark_ocr_regresion.py generar   benchmark/estampa-1939  # Tesseract, ruta real de la app
python scripts/benchmark_ocr_regresion.py evaluar   benchmark/estampa-1939
python scripts/benchmark_ocr_regresion.py base      benchmark/estampa-1939  # congela linea_base.json
python scripts/benchmark_ocr_regresion.py verificar benchmark/estampa-1939  # sale 1 si algo empeora
```

Para otras rutas (Kraken, IA de visión, CHURRO), pon su salida en
`salidas/<nombre_ruta>/<page_id>.txt`. Cada carpeta de `salidas/` se trata
como una ruta distinta.

`linea_base.json` incluye un manifiesto de ejecución completo: commit, versión
de Python y de las librerías, componentes externos y hash de las referencias.
Una línea base sin esos datos no se puede reproducir.

## Métricas

| Métrica | Qué mide |
|---|---|
| CER / WER | Distancia de edición por carácter / palabra, micro-promediada |
| Fusión | Palabras de la referencia pegadas en la salida (`de los` → `delos`) |
| Fragmentación | Palabras partidas en la salida (`gobierno` → `gob ierno`) |
| Cobertura | Fracción de páginas con referencia para las que la ruta produjo texto |

Una página sin salida cuenta como error total, no como dato ausente.
