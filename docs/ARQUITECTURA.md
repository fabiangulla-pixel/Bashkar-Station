# Arquitectura de Bashkar Station (modelo C4)

Estado al 29-sep-2026, medido sobre el código (no deseado). Los diagramas usan
Mermaid y se ven directamente en GitHub.

Leyenda de cada caja: **[local]** corre en el equipo sin red · **[externo]**
programa o servicio fuera de Python · **[persiste]** escribe archivos que
sobreviven a la sesión.

---

## Nivel 1 — Contexto

```mermaid
flowchart LR
    inv([Investigador/a])
    bs[Bashkar Station<br/>análisis de prensa histórica<br/>local]
    corpus[(Corpus: PDF / imágenes<br/>de revistas<br/>licencia propia)]
    ia[Proveedores de IA<br/>Anthropic · OpenAI · Gemini · Ollama<br/>externo, opcional]
    wd[Wikidata<br/>externo, opcional]
    hf[HuggingFace<br/>modelos locales tras 1.ª descarga]
    out[(Exportaciones<br/>TEI · ALTO · OKF · Excel · PDF · PPTX<br/>+ manifiesto de proveniencia)]
    inv -- revisa y corrige --> bs
    corpus --> bs
    bs -. texto/imagen con costo confirmado .-> ia
    bs -. enlace de entidades .-> wd
    hf -. pesos .-> bs
    bs --> out
```

El corpus y los modelos **no** se distribuyen con el software; cada uno tiene
su licencia (ver README, sección Licencias).

## Nivel 2 — Contenedores

```mermaid
flowchart TB
    subgraph Frontends
      gui[app.py — GUI Tkinter<br/>21.469 líneas · local]
      web[servidor_web.py — HTTP stdlib + web/<br/>local o público en Render]
      cli[cli.py — pipeline sin interfaz<br/>local]
    end
    core[core/ — ~95 módulos de lógica<br/>OCR, NER, análisis, exportación]
    datos[datos/ — Repositorio, esquema,<br/>migración, normalizaciones]
    exp[exportadores/ — ALTO, PPTX]
    proy[(Proyecto .bashkar JSON<br/>+ SQLite hermano · persiste)]
    glob[(~/.bashkar/bashkar.db<br/>entidades entre proyectos · persiste)]
    tess[[Tesseract + spa.traineddata<br/>externo]]
    pop[[Poppler<br/>externo]]
    kr[[Kraken / CHURRO / PERO<br/>opcionales]]
    gui --> core
    web --> core
    cli --> core
    gui --> datos
    core --> datos
    core --> exp
    datos --> proy
    datos --> glob
    core --> tess
    core --> pop
    core -.-> kr
```

La GUI y el servidor web comparten `core/` y `core/estado.Estado`. La GUI
todavía hace mucho trabajo propio: ver "Estado de app.py" más abajo.

## Nivel 3 — Componentes (pipeline de texto)

```mermaid
flowchart LR
    img[Imagen de página] --> pre[image_preprocessor]
    pre --> ocr[ocr_engine / ocr_kraken /<br/>ocr_llm / ocr_churro]
    ocr --> crudo[(capa ocr_crudo<br/>congelada)]
    crudo --> norm[ocr_normalizer +<br/>spell_corrector]
    norm --> ia_c[(capa norm_ia)]
    ia_c --> rev[Revisión humana<br/>panel Normalizar]
    rev --> hum[(capa norm_usuario)]
    hum --> seg[article_segmenter_v2]
    seg --> nlp[ner_engine · entity_linker ·<br/>topic · sentiment · stylometry]
    nlp --> expo[tei_engine · okf_export ·<br/>excel_export · pdf_export · exportadores/]
    expo --> man[(.proveniencia.json)]
    crudo & ia_c & hum -.-> hist[(normalizaciones_historial<br/>solo inserción)]
```

Las tres capas de texto viven en la tabla `normalizaciones`
(`datos/normalizaciones.py`). El OCR crudo no se sobrescribe nunca y cada
cambio deja una fila en `normalizaciones_historial` con autor, hora y commit.

Medición: `core/benchmark_ocr.py` (métricas) y `core/benchmark_regresion.py`
(benchmark formal con línea base, ver `benchmark/README.md`).

## Nivel 4 — Código: `datos/normalizaciones.py`

Es el único módulo con diagrama de código, porque aquí vive la regla
metodológica central (no destruir evidencia):

```mermaid
sequenceDiagram
    participant P as Panel Normalizar (app.py)
    participant N as datos.normalizaciones
    participant DB as SQLite
    P->>N: guardar(numero, pagina, ocr_crudo, norm_usuario, norm_ia)
    N->>DB: asegurar_esquema (ALTER TABLE si falta)
    N->>DB: SELECT fila previa
    Note over N: ocr_crudo = previo si existe<br/>(el .txt ya trae texto corregido)
    N->>DB: UPSERT con ts solo de capas cambiadas
    N->>DB: INSERT historial por capa cambiada
    N-->>P: capas cambiadas / excepción (nunca silencio)
```

---

## Estado de app.py

Medido con `ast` el 29-sep-2026:

| Bloque | Líneas |
|---|---:|
| Clase `BashkarApp` (única) | 20.702, 572 métodos |
| Pestaña NER (índice de entidades, canónicas, grafos, revisión) | 8.214 |
| Etiquetador de zonas | 4.254 |
| Panel de asistente IA | 1.992 |
| Resultados y exportación | 1.957 |
| Configuración | 947 |
| Resto de pestañas | < 500 cada una |

44 métodos no usan `self`: son lógica pura alojada en la clase por
comodidad, y son los primeros candidatos a salir.

### Estrategia de extracción

No se reescribe. Cada paso:

1. Elegir un bloque cuya lógica no toque widgets.
2. Escribir tests de contrato contra el comportamiento actual.
3. Moverlo a `core/` o `datos/` con una API pequeña.
4. Dejar en `app.py` un método delgado que delega (adaptador), para no tocar
   los llamadores.
5. Suite completa en verde y commit por bloque.

Hechos:

- `datos/normalizaciones.py` ← `_norm_leer_db` / `_norm_escribir_db`
  (sesión 70). La extracción destapó que el OCR original se perdía.
- `core/servicios_corpus.py` ← conteo de páginas, reconstrucción de metadatos
  del corpus y agrupación por período (sesión 70).

- `core/servicios_exportacion.py` ← configuración y estadísticas de
  METHODS.md (duplicadas en dos sitios, ambas con cifras falsas) y artículos
  TEI. Destapó que el paquete de publicación nunca incluía `corpus.xml`.
- `core/exploradores.exportar_gexf` ← `_can_escribir_gexf` (el GEXF se rompía
  con comillas en un nombre de entidad).
- `core/benchmark_ocr.catalogo_rutas` ← `_bench_catalogo_rutas`.

Tres de las cinco extracciones destaparon un fallo real. Es el argumento
práctico a favor de seguir: la lógica escondida en la GUI no tenía tests.

Siguientes, por orden:

1. Ejecución de rutas del benchmark (`_bench_correr_ruta`) → `core/benchmark_ocr`.
2. Pestaña NER: separar primero lectura/escritura en SQLite (ya existe
   `datos/repositorio.py`), después la vista.
3. Etiquetador de zonas: separar render de PDF y persistencia de zonas.

Meta: `app.py` como punto de composición (construye ventanas y conecta
señales). No hay fecha, pero sí un indicador: la tabla de arriba, regenerada
en cada sesión que extraiga algo.
