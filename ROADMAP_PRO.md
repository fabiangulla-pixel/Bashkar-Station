# Bashkar Station Pro — plan de arranque

> Decidido el 3-sep-2026 (sesión 66). Documento vivo: se actualiza a medida que
> avanza. `app.py` **no se toca** mientras Pro no cumpla el criterio de
> aceptación de la §4.

## 1. Qué es Pro y qué no es

Pro **no** es una reescritura de Bashkar Station. Es una **interfaz nueva sobre
una capa de contratos nueva**, reusando `core/` sin modificarlo.

La razón está en el reparto real del código (medido el 3-sep-2026):

| Capa | Líneas | Módulos | Estado |
|---|---|---|---|
| `core/` | 32.435 | 93 | ya modular — **se reusa tal cual** |
| `datos/` + `exportadores/` | 1.823 | 7 | ya modular — se reusa |
| `app.py` | 21.459 | **1** | el monolito — se reemplaza en Pro |
| `tests/` | 17.386 | — | válidos para ambos |

El monolito no es el proyecto: es `app.py`. El 64 % del código de producción ya
está partido, y es justo la parte que no conviene rehacer, porque codifica
calibración empírica que no se recupera leyendo el código — el umbral de espacio
de `alto_reconstructor` (0,018 × tamaño de fuente, acotado por evidencia real),
los 80+ patrones de `morfologia_historica`, las listas de `ocr_normalizer`, y los
bugs corregidos en las auditorías de las sesiones 62 a 66. Reescribir eso
significaría volver a encontrar los mismos bugs uno por uno.

### Regla dura: un solo `core/`

Pro vive en **el mismo repositorio**, como paquete `pro/`. No es una copia del
directorio ni un fork.

El precedente que lo justifica: el segfault de RoBERTa (sesión 62) apareció
primero en `cli.py` y después, por separado, en `app.py` — la misma lógica
copiada en dos sitios obligó a arreglar el mismo bug dos veces. Con dos copias
completas del proyecto eso pasaría con **cada** bug, y la suite de 1.562 tests se
bifurcaría, que es la única red de seguridad que hay.

Dirección de dependencia, en un solo sentido:

```
pro/  ──────►  core/  ◄──────  app.py
              datos/
```

## 2. Fase A — los contratos (antes de cualquier interfaz)

El diagnóstico de la sesión 66: los bugs recientes no vienen del tamaño del
archivo, sino de **contratos de datos que la GUI reinventa cada vez que los
necesita**. Tres casos medidos:

1. La DDL de `normalizaciones` vivía suelta dentro de `app.py`; `colaboracion.py`
   y `kraken_finetune.py` tenían que adivinar su forma. → Los parches salían sin
   ninguna de las 169 correcciones manuales del corpus.
2. La exportación TEI arma sus registros de artículo inline y **por duplicado**
   en `app.py`, con dos formas distintas y ambas incompletas; una llama a
   `exportar_corpus_tei(titulo=…, fecha=…)`, parámetros que la función no tiene.
   → `TypeError` capturado por un `except` genérico: el paquete de publicación
   se genera **sin el TEI** y solo anota el error en una lista.
3. El índice NER se indexa con `row.get("id", row.get("titulo", f"art_{i}"))`.
   El `articulos.csv` real no tiene columna `id` → cae a `titulo` → los títulos
   reales son fragmentos de OCR. → **0 de 184 entidades** llegan al TEI.

Mover paneles de sitio no arregla ninguno de los tres. Los deja en seis archivos
en vez de uno.

Contratos a construir, en este orden:

- **A1 · Identidad de artículo.** Un id estable y único, decidido en un solo
  sitio. Es la raíz del 0/184 y bloquea el re-run de NER (§5).
- **A2 · `core/corpus.py`.** Una única función que devuelve los artículos del
  proyecto en una forma declarada: id, título, autor, fecha, texto, entidades.
  Hoy hay al menos cinco sitios que arman esa lista a mano, cada uno distinto:
  `comparador`, `colaboracion`, TEI (×2), `pipeline_maestro`, `excel_export`.
- **A3 · Cero SQL fuera de `datos/`.** Todo `CREATE TABLE` en `datos/schema.py`.
  Ya empezado: `SCHEMA_NORMALIZACIONES` (commit `b07b906`).

Los tres se prueban contra `Proyecto_04` **sin abrir la GUI**, que es la única
forma de verificación que ha encontrado bugs reales en las últimas sesiones.

## 3. Fase B — `ST` con forma declarada

El estado global no tiene que desaparecer; tiene que tener **contrato**. Un
dataclass con campos tipados en lugar de un objeto al que cualquiera le cuelga
atributos. El bug de `ST.datos_dir` inexistente —que dejó "Exportar glosario" sin
funcionar sin que nadie se enterara— lo detecta el linter, no una auditoría.

Pro nace ya con esto. `app.py` sigue con su `ST` actual, sin tocar.

## 4. Pro v0.1 — alcance: Ingestión → OCR

Flujo vertical y estrecho, elegido por el usuario porque es donde está el valor
de investigación. Toca las tres capas y valida la arquitectura de punta a punta.

Módulos de `core/` que quedan bajo esta ruta (3.868 líneas, todas reusadas):

| Módulo | Líneas | Papel |
|---|---|---|
| `ocr_normalizer` | 726 | normalización + vocabulario de época |
| `ocr_churro` | 601 | CHURRO-3B, visión local |
| `ocr_llm` | 560 | Vision OCR en la nube |
| `alto_reconstructor` | 367 | capa oculta de Paper Capture (BNC) |
| `ocr_engine` | 330 | Tesseract |
| `ocr_kraken` | 316 | HTR |
| `text_extractor` | 281 | extracción de PDF |
| `image_preprocessor` | 280 | preproceso de imagen |
| `benchmark_ocr` | 275 | CER / WER / similitud Levenshtein |
| `page_quality` | 132 | calidad de página |

### Criterio de aceptación (no una sensación)

Pro v0.1 se considera viva cuando, **sobre `Proyecto_04`**:

1. Abre el proyecto y lista los 138 artículos con id estable (contrato A1).
2. Corre la ruta de OCR y produce texto para las mismas páginas que `app.py`.
3. `benchmark_ocr` da un CER **igual o mejor** que el de la ruta actual sobre el
   estándar de oro existente.
4. Todo lo anterior corre **sin GUI**, desde una prueba automatizada.

Mientras no cumpla los cuatro, **`app.py` es la versión oficial** y el trabajo
real no se migra a Pro.

## 5. Re-run de NER sobre Proyecto_04

### Por qué hace falta

El índice actual tiene 184 entidades bajo **24 claves**, y esas claves no
corresponden ya a su propio corpus: solo 2 de las 24 son título de alguna fila de
`articulos.csv`, y emparejando por título se recuperan 10 de 184. El enlace entre
entidades y artículos está perdido; no se puede reparar por emparejamiento, hay
que volver a generarlo.

### Costo real (medido, no estimado por analogía)

Medido el 3-sep-2026 con `mrm8488/bert-spanish-cased-finetuned-ner` **ya
cacheado** en `~/.cache/huggingface/hub`, corriendo el mismo motor que usaría el
re-run sobre textos reales del corpus:

| Artículo | Tamaño | Tiempo | Entidades |
|---|---|---|---|
| corto | 205 chars | 0,16 s | 7 |
| mediana | 5.397 chars | 1,69 s | 37 |
| largo | 39.521 chars | 13,15 s | 183 |

- Ritmo: **3.008 chars/s**
- Corpus: 138 artículos, 969.192 chars
- **Re-run completo: ~5,4 min** + 15 s de carga del modelo

**Costo en dinero: cero.** El modelo es local y está cacheado; no interviene
ninguna API de pago. No aplica el estándar de estimación de costo de IA.

### Orden obligatorio

El re-run va **después** del contrato A1. Correrlo antes significa volver a
generar un índice con ids inestables y tener que repetirlo.

```
A1 (identidad de artículo)  →  re-run de NER  →  verificación
```

### Pasos

1. Respaldar el `.bashkar` y el `.db` antes de tocar nada (el índice viejo se
   conserva, no se sobrescribe a ciegas).
2. Correr NER local sobre los 138 artículos con id del contrato A1.
3. Escribir el índice en `resultados.indice_ner_global` y las entidades en la
   tabla `entidades` del SQLite.

### Verificación

Tres comprobaciones, ninguna basada en que el proceso "terminó sin error":

- **Enlace:** cada clave del índice es un id real de `articulos`; 0 huérfanas.
- **Cobertura:** el número de entidades sube muy por encima de 184. La mediana
  medida da 37 entidades por artículo; sobre 138 artículos se esperan miles, no
  cientos. Si sale del orden de 184, el re-run no hizo lo que se cree.
- **Extremo a extremo:** el `<standOff>` del TEI exportado deja de estar vacío.
  Ese es el síntoma que inició todo esto y es el que tiene que desaparecer.

### Advertencia sobre el índice viejo

Las 183 filas de `revision_entidades` están **todas** en estado `pendiente`: son
una cola de revisión, no decisiones tomadas. No hay trabajo humano de validación
NER que preservar en el re-run. (Sí lo hay en `normalizaciones`: 169 páginas
corregidas a mano — esas no las toca el re-run.)

## 6. Lo que NO se hace

- **No** se reescribe `app.py` de una vez. 21.459 líneas y una suite que puede
  estar en verde con 16 bugs vivos (sesión 65) hacen que una reescritura grande
  deje la app rota a mitad de camino sin forma de saber cuándo se rompió.
- **No** se copia el directorio del proyecto. Un solo `core/`.
- **No** se migra trabajo real a Pro antes del criterio de §4.
- **No** se toca `PAPER_METODOLOGICO_ESQUELETO.md` hasta que la app esté
  verificada: su contenido depende de cifras que estos arreglos cambian.
