# Bashkar Station — Changelog

---

## Sesión 42 — 2026-06-29 — Wikidata v3 + Gemini 3 + guías por módulo + .exe v11.6

### Contexto
Tres encargos del usuario: (1) habilitar Gemini 3 en adelante en las opciones de
API key, (2) que cada módulo explique al usuario qué es / para qué sirve / qué
resultado da y cómo interpretar los datos, (3) refinar la herramienta de Wikidata
al 100 %. Más: dejar el `.exe` recompilado y desplegado con todo lo pendiente de
las sesiones 41-42. Suite final: **927 passed, 11 skipped, 0 failed**.

### 1. Wikidata — `core/entity_linker.py` a v3 (4 huecos cerrados)
`_ALGO_VERSION = 3`. Causa raíz de cada hueco y solución:
- **#1 Homónimos sin contexto** (p. ej. "Alfonso López" presidente vs. deportista):
  el linker no usaba el texto del artículo. Solución: `enlazar_entidad(...,
  contexto="")` + `_puntuar_candidato(..., contexto)` suma hasta +0.8 por
  solapamiento entre las palabras de contenido de la descripción del candidato y el
  contexto. `enlazar_indice_ner(..., textos_articulos={art_id: texto})` propaga el
  contexto; la GUI lo arma desde `ST.df_articulos`.
- **#2 Enlaces espurios de basura OCR** ("Bogo"→Bogotá conf 0.5): no había filtro.
  Solución: `_MIN_LEN_ENTIDAD=4` + exigir ≥1 letra; `_CONF_MINIMA=0.45` (por debajo,
  se trata como no encontrado).
- **#3 Homónimos modernos** ganaban por ranking: no se verificaba la época. Solución:
  `_obtener_fecha_relevante(qid)` (P569 nacimiento / P571 fundación / P580 inicio) +
  `_anio_de_claim`; descarta candidatos fuera de `[1700, 1945]`.
- **#4 Caché enmascaraba mejoras**: resultados viejos (algoritmo anterior) se
  devolvían sin re-enlazar. Solución: columna `algo_version` (migración ALTER suave);
  en `obtener()`, versión < actual ⇒ se trata como ausente ⇒ re-enlaza.
- Tests: `tests/test_entity_linker.py` clase `TestMejorasDesambiguacion` (7 nuevos,
  sin red, verdes). Los 6 de red siguen skip en sandbox.

### 2. Gemini 3.x en opciones de API key — `app.py`
- `_OPCIONES_MODELO` (config «Modelo activo por etapa»): + `gemini-2.5-flash`,
  `gemini-2.5-pro`, `gemini-3.1-flash`, `gemini-3-pro`; quitados `gemini-1.5-*`.
- Texto de ayuda del proveedor Gemini actualizado a esos modelos.
- (El panel «Extracción IA» ya tenía Gemini 3 desde la sesión 41; `costos.py` ya
  tenía los precios.)

### 3. Guías por módulo — `core/guia_modulos.py` (NUEVO)
- 29 guías HD (qué es / para qué / qué resultado / cómo interpretar), con umbrales
  de referencia (p. ej. "modularidad >0.4", "Kappa >0.6"), trampas comunes (ruido
  OCR) y cómo llevarlo al paper.
- Integración en `app.py`: el loop que construye los paneles fija
  `self._guia_pagina_actual = pid` antes de cada `build_fn`; `_page_header` llama a
  `_inyectar_guia_modulo(...)` que muestra **resumen siempre visible** bajo el título
  + sección colapsable **«📖 Cómo interpretar los resultados»** (lazy `_mk_avanzado`).
  Cubre las 28 páginas sin tocar cada `_build_*`. Silencioso si el módulo no está.

### 4. Build y despliegue — `.exe v11.6`
- `bashkar_station.spec`: +14 hiddenimports que faltaban (extractor_multimodal,
  guia_modulos, costos, frame_engine, sentimiento_discriminante, revision_engine,
  validacion_engine, sintaxis_engine, coref_engine, viz_engine, timeline_engine,
  bitacora_engine, image_captioner, layout_tesseract) +
  `collect_submodules('google.generativeai')` (68 submódulos, SDK Gemini del MMX).
- `app.py`: APP_VERSION y splash 11.5 → 11.6.
- Compilado a disco local (`C:/build_rf/bs_dist`, WMI kill previo — lección build).
  Smoke test: arranca sin crash, stderr sin ModuleNotFound. Desplegado con robocopy
  a `C:\Programas\BashkarStation\` (7591 archivos, exe 77 MB). Verificado: arranca
  desde el destino final. Acceso directo **Bashkar Station v11.6.lnk** en ambos
  escritorios (OneDrive + local); v11.4/v11.5 eliminados.

### Archivos modificados
| Archivo | Cambio |
|---------|--------|
| `core/entity_linker.py` | Desambiguación v3 (contexto, filtros, ventana histórica, caché versionada) |
| `core/guia_modulos.py` | NUEVO — 29 guías HD por panel |
| `app.py` | Gemini 3 en `_OPCIONES_MODELO` + ayuda; `_inyectar_guia_modulo`; `_guia_pagina_actual`; contexto Wikidata; versión 11.6 |
| `bashkar_station.spec` | +14 hiddenimports + google.generativeai |
| `tests/test_entity_linker.py` | +7 tests `TestMejorasDesambiguacion` |

### Pendiente próxima sesión
1. **E2E real Gemini** — el usuario configura su key en ⚙ y corre «Extracción IA»
   sobre imágenes reales de Estampa (round-trip HTTP a Google, único no verificado).
2. **Hacerwiki 2026 ciclo 2** (cierra 10-jul): borrador completo en
   `Desktop\Hacerwiki_2026_Estampa_Abierta.{md,docx}`. Falta: usuario revisa cifras,
   localizar el formulario oficial en Meta-wiki WMCO, crear cuenta Wikimedia (Fase 0),
   confirmar base legal del dominio público de Estampa para Commons.
3. Posible: alimentar imagenes_registro→análisis visual y bloque_publicitario→
   análisis de publicidad.

---

## Sesión 41 — 2026-06-28 — Extracción multimodal estructurada (imagen → JSON → corpus)

### Contexto
Encargo: pipeline de extracción de datos a partir de imágenes de hemeroteca usando
IA de visión, forzando salida JSON estricta (artículo jerárquico + imágenes con
pies + publicidad). Es la respuesta directa al hallazgo de la auditoría (sesión 36):
las imágenes BNC de microfilm NO se rescatan con preproceso clásico, requieren OCR
por IA de visión. Aquí esa salida queda **estructurada** y lista para el pipeline.

### Módulo nuevo — `core/extractor_multimodal.py`
- **`PROMPT_MAESTRO`**: instrucción fija por imagen (esquema obligatorio) + regla
  añadida: conservar ortografía de época (no modernizar). 
- **`extraer_pagina(img, api_key, proveedor, modelo)`**: visión → JSON validado.
  Multiproveedor reusando los clientes de `core.ocr_llm`: gemini (default, JSON
  mode nativo `response_mime_type=application/json`), claude, openai
  (`json_object`), ollama (`format:json`). Registra usage en `ocr_llm` (costo real).
- **`_extraer_json`**: parseo tolerante (quita fences ```json, recorta prosa).
- **`validar_pagina`**: normaliza y rellena claves faltantes (nunca KeyError aguas
  abajo); rechaza páginas sin contenido.
- **`procesar_directorio`**: lote robusto — **un try/except por imagen, ninguna
  página detiene el lote**; callback de progreso; guarda `pNNNN.json` + `pNNNN.md`.
- **`json_a_markdown`** (.md jerárquico), **`json_a_texto_plano`** (puente a
  `ST.corpus_txt`, excluye pies/publicidad del cuerpo), **`json_a_publicidad`**.
- **`estimar_costo_directorio`**: reusa `costos.estimar_lote_ocr` (estándar costo-IA).
- Sin dependencias nuevas en el módulo (validación con dataclasses, offline-first);
  no importa tkinter (core/ desacoplado de la UI).

### Integración GUI — panel «Extracción IA» 🧠
- Página `"mmx"` en Activity Bar 📥 Ingestión (tras Conversor PDF). 4 pasos:
  carpetas, proveedor/modelo (combobox + defaults por proveedor), salida (guardar
  JSON crudo / alimentar corpus), procesar (estimar costo + extraer + progreso +
  log). Worker threaded vía `self.after`. Confirmación de costo antes de gastar y
  costo real al terminar (`costos.costo_real_desde_usages`). Alimenta `ST.corpus_txt`
  y marca el proyecto modificado. Comando en Command Palette (Ctrl+K).

### Dependencias
- `google-generativeai>=0.8.0` añadido a requirements.txt (opcional, degrada con
  gracia). NOTA: Google lo deprecó a favor de `google-genai`; se mantiene por
  consistencia con `core/ocr_llm.py` (mismo SDK). Migrar ambos = tarea aparte.

### Selector de modelos de visión por proveedor (mismo día)
- El panel «Extracción IA» ahora muestra un **combobox editable de modelos** que
  se actualiza según el proveedor cuya API key se elige; el 1.º es el recomendado.
  Constante `_MMX_MODELOS` (vigentes jun-2026, verificados: Claude vía skill
  claude-api, Gemini/OpenAI/Ollama vía docs):
  - gemini: gemini-2.5-flash / 2.5-pro / 3.1-flash / 3-pro
  - claude: opus-4-8 / sonnet-4-6 / haiku-4-5 / opus-4-7 / fable-5
  - openai: gpt-5.5 / gpt-5.4-mini / gpt-4o / gpt-4o-mini
  - ollama: llava / llama3.2-vision / qwen2.5-vl / minicpm-v
- Default de Gemini actualizado **gemini-1.5-flash → gemini-2.5-flash**
  (1.5 quedó atrás; Gemini 2.0 se apagó jun-2026). Mismo cambio en
  `core/extractor_multimodal.py`.
- `core/costos.py`: precios añadidos/actualizados (web 2026-06-28) para
  gemini-2.5-flash/pro, gemini-3*, gpt-5.5, gpt-5.4-mini, claude-opus-4-7 →
  la estimación de costo sale `catalogado=True` para todos los modelos del selector.

### Verificación
- **Tests:** `tests/test_extractor_multimodal.py` (25), fixture = el JSON real de la
  página 20 de Estampa ("De la vida y la muerte… un bisté a un tango dramático",
  Piquillo Pío). Proveedor mockeado (sin red). **Suite total: 920 passed, 11
  skipped, 0 failed.** Cero regresiones.
- **Smoke GUI headless:** panel construye, widgets presentes, navegación al
  contexto Ingestión, puente a corpus_txt OK.
- **Rama gemini con SDK real (solo red mockeada):** `genai.configure` +
  `GenerativeModel(response_mime_type/temperature)` + carga PIL ejecutan sin error.
- **PENDIENTE — E2E real:** el usuario configurará su Gemini key en ⚙ y correrá el
  panel sobre imágenes reales (la única parte no verificada es el round-trip HTTP).

---

## Sesión 39 — 2026-06-17 — Módulo de entidades, grafo y exploradores (DH) + .exe v11.5

### Contexto
Encargo nuevo (convocatoria DH tipo Max Planck, proyectos SCC Explorer / Orbis
Dioecesium): capa incremental de entidades, grafo de conocimiento y exploradores.
La auditoría mostró que 5/7 funciones del prompt YA existían parcial/totalmente
(NER, cola de revisión, annotation_engine con procedencia/confianza, Wikidata,
mapa, timeline). El hueco real: capa de **entidades canónicas + tripletas**. Se
implementaron las 4 fases completas + integración GUI + .exe v11.5 + demostración.

### Fase 1 — Capa canónica (datos)
- **`datos/schema.py`**: 3 tablas nuevas en SCHEMA_PROYECTO — `entidades_canonicas`
  (id estable `<tipo>:<slug>`, idempotente, UNIQUE(tipo,nombre_norm)),
  `menciones_canonicas` (puente mención→canónica) y `relaciones` (tripletas
  sujeto-predicado-objeto). Sin triplestore aparte.
- **Bug de diseño cazado por test:** un `UNIQUE` normal NO deduplica tripletas con
  objeto NULL (en SQLite NULL≠NULL). Solución: índice de expresión
  `idx_relaciones_unica` sobre COALESCE(destino_id,''), COALESCE(destino_pagina,'');
  `destino_id` queda NULL (no '') cuando el objeto es página, para que la FK lo
  ignore; el `ON CONFLICT` apunta a las mismas expresiones COALESCE.
- **`datos/repositorio.py`**: `id_canonico`, `guardar_entidad_canonica`,
  `fundir_menciones_en_canonicas` (cat NER→tipo, agrupa por nombre_norm, idempotente),
  `guardar_relacion`, `listar_relaciones`, `grafo_entidades`, `vincular_mencion`.
- **`datos/migracion.py`**: capa REVERSIBLE `aplicar_grafo`/`revertir_grafo`/
  `grafo_aplicado`. No toca el .bashkar; revertir deja las menciones intactas.
- Validado con DB real Proyecto_04_Mar_2026: 114 menciones → 103 canónicas.

### Fase 2 — Aserción + vocabulario controlado
- "Assertive Edition" (Vogeler): el annotation_engine ya guarda fuente+confianza+
  historial; documentado para el paper.
- **`core/vocabulario_controlado.py`** (nuevo): unifica OFFLINE glosario global +
  arcaísmos morfológicos + entidades canónicas (término→tipo). construir/consultar/
  estadisticas/exportar_csv+json. 197 términos en el corpus real.

### Fase 3 — Exploradores
- **`core/exploradores.py`** (nuevo, módulo de publicación): `geocodificar_lugares`
  (gazetteer local), `mapa_lugares_html` (folium→fallback Leaflet CDN),
  `timeline_numeros_html` (cada nº enlaza transcripción).

### Fase 4 — RDF opcional
- `exportar_rdf` en exploradores.py: rdflib si está, si no Turtle a mano
  (degradación con gracia; rdflib NUNCA obligatorio).

### Integración GUI
- **`app.py`**: pestaña «Grafo canónico» en panel Redes (🕸, notebook nb_red).
  Handlers `_can_fundir`/`_can_generar_menciones`/`_can_exportar_gexf`/`_can_exportar_rdf`/
  `_can_mapa_lugares`/`_can_timeline`/`_can_vocabulario` (workers threaded). Export
  GEXF propio sin deps. **`_can_editor_relacion`**: editor manual de tripletas
  (combos sujeto/predicado/objeto + confianza, fuente=revision_manual). Comando
  «🕸 Grafo canónico» en Command Palette. APP_VERSION 11.4→11.5.

### .exe v11.5
- **`bashkar_station.spec`**: añadidos a `datas` los JSON/TXT de `datos/`
  (coordenadas_colombia, personajes, stopwords) — ANTES NO se empaquetaban → el
  mapa habría fallado en el .exe. hiddenimports: +vocabulario_controlado,
  +exploradores, +morfologia_historica.
- Compilado, **desplegado a `C:\Programas\BashkarStation\`** (la unidad D: del exe
  v10.7 ya no existe), acceso directo `Bashkar Station v11.5.lnk` en Escritorio.
  Verificado: arranca, splash «v11.5», sin crash.
- **Lección operativa:** NO compilar con dist en la red (I:/Google Drive): el
  bootstrap se relanza en cadena y bloquea DLLs; `--clean` falla con WinError 5;
  solo WMI Terminate mata los procesos. Compilar a disco local con --distpath/--workpath.

### Tests
- `tests/test_grafo_entidades.py` (14), `tests/test_grafo_gui.py` (7),
  `tests/test_fase234.py` (9). **Suite: 885 passed, 11 skipped, 0 failed** (856+29).

### Material para el paper
- `Desktop\Bashkar_Paper_Estampa\grafo_demo\`: grafo_canonico.gexf, .ttl (RDF),
  mapa_lugares.html, timeline_numeros.html, vocabulario_controlado.csv.

### Pendiente próxima sesión
1. **Enriquecer el grafo:** re-NER guardando TODAS las entidades (la base tiene ~1
   entidad/art → 0 co-presencias). Es lo que da densidad al grafo de co-ocurrencia.
2. **Limpieza Wikidata espurios** por umbral de confianza (Fase 4, fleco menor).
3. **Demo OCR Vision IA** sobre 3-5 págs BNC (bloqueada sin api_key) para cerrar la
   cadena visual con material de calidad.
4. Recompilar/redesplegar solo si se cambia código (recordar: disco local + WMI kill).

---

## Sesión 37 — 2026-06-16 — 4 motores portados de ¡Quac! + integración en Lingüística + pruebas GUI

### Contexto
El investigador pidió traer a Bashkar lo desarrollado en su proyecto hermano ¡Quac!
(prensa contemporánea) que aplicara a prensa histórica, integrarlo en el panel
Lingüística, probarlo y mejorar el programa.

### Módulos nuevos en `core/` (¡Quac! los inventó; Bashkar no los tenía)
Funciones puras texto→dict, recalibradas al dominio de Estampa (1930s):
- **`core/frame_engine.py`** — análisis de ENCUADRE (Media Frames Corpus). 10 frames de
  prensa ilustrada 1930s (guerra/modernidad/mujer_social/cultura/nacion/politica/
  ciencia/religion_moral/economia/internacional) con léxico ES (raíces sin tilde para
  OCR). `analizar_frame`, `analizar_corpus_frames`, `cruce_seccion_frame`,
  `registrar_marcos_personalizados`, `clasificar_frame_llm` (opcional). El salto de
  "tono" a "ángulo" para el paper.
- **`core/validacion_engine.py`** — validación metodológica (fiabilidad inter-codificador):
  `exportar_muestra` (aleatoria reproducible por semilla, con etiqueta automática) +
  `calcular_concordancia` (acuerdo % + Kappa de Cohen + interpretación + matriz de
  confusión). Generalizado: valida cualquier dimensión (polaridad/frame/emocion).
- **`core/sentimiento_discriminante.py`** — polaridad pos/neg/neutro que NO sesga a
  "confianza" como el NRC de 8 emociones (problema documentado en la auditoría s.36).
  Léxico de prensa 1930s, negaciones que invierten. `polaridad_hacia(texto, formas)`,
  `polaridad_hacia_corpus(textos, formas)` (tono hacia entidad SIN cruzar fronteras de
  artículo), `indice_polarizacion_afectiva`, `distribucion_polaridad`. Transformer
  pysentimiento inerte en Py3.14 (igual que ¡Quac!).
- **`core/revision_engine.py`** — human-in-the-loop NER. Cola de entidades dudosas
  (amarillo/rojo vía `confianza_engine`), persistencia en tabla `revision_entidades`
  sobre conexión sqlite3 directa (patrón de `datos/repositorio.py`, row_factory=Row),
  decisiones verificada/descartada/renombrada con trazabilidad, `aplicar_revisiones`
  re-funde renombres y quita descartadas del índice global `{cat:{ent:[arts]}}`.

### Integración en la GUI (`app.py`, panel Lingüística 🔭)
4 pestañas nuevas en `_build_ling()` (notebook `self._nb_ling`), tras las 6 existentes:
- **🖼 Encuadre** (idx 6) — `_ling_frames` (worker threaded), tabla por artículo +
  resumen dominante + `📊 Graficar` (barh matplotlib) + `💾 CSV`.
- **⚖ Polaridad** (idx 7) — `_ling_polaridad`, tabla con tags color pos/neg/neutro,
  índice de polarización afectiva, campo «polaridad hacia entidad» (`_ling_pol_hacia`).
- **🔍 Revisión NER** (idx 8) — `_ling_rev_construir` desde `ST.indice_ner_global`,
  botones Verificar/Descartar/Renombrar. Persistencia: `_ling_rev_con()` abre sqlite3
  a `ST.ruta_db` (o `revision_ner.db` junto al proyecto). `_ling_rev_aplicar_al_indice`
  re-aplica TODAS las decisiones al índice en memoria en cada acción.
- **✔ Validación** (idx 9) — combobox dimensión (polaridad/frame/**emocion**) + n + semilla;
  `_ling_val_exportar` → muestra; `_ling_val_concordancia` → acuerdo%/Kappa/matriz.
- Helper `_ir_a_ling_pestania(idx)`. **Command Palette (Ctrl+K): +4 comandos → 25 total.**
- Descripción de `_PAGINAS["ling"]` y subtítulo del panel actualizados.

### Mejoras aplicadas durante las pruebas
1. **Clasificación de polaridad fiel** — si TODAS las marcas polares son de un signo
   (n_pos=0 ó n_neg=0), la polaridad es clara aunque el score esté diluido. Antes
   "Franco impuso terror" daba neutro por umbral ±0.15; ahora negativo. Neutro solo si
   hay marcas de AMBOS signos balanceadas o ninguna.
2. **`polaridad_hacia_corpus`** — procesa artículo por artículo para que la ventana ±25
   NO cruce de un artículo al siguiente (antes unía con `\n` y contaminaba con el tono
   de la nota vecina). El handler `_ling_pol_hacia` ahora lo usa.
3. **Revisión NER consistente** — `_ling_rev_decidir` SIEMPRE re-aplica decisiones al
   índice (no solo renombrar); descartar limpia la entidad del índice.
4. **3ª dimensión validable «emocion»** — aprovecha `sentiment_engine.analizar_emociones`.

### Diagnóstico que vale recordar
Los síntomas iniciales de "solo procesa 1 artículo" NO eran bug: `_cargar_ultimo_proyecto`
(auto-carga al arrancar, vía `after`) pisaba el `ST.corpus_txt` del driver de prueba. En
uso real con proyecto cargado funciona. Verificado con auto-carga desactivada.

### Verificación
- App arranca con `mainloop` REAL sin errores en callbacks.
- Inspección VISUAL de las 4 pestañas (screenshots sobre mainloop real, corpus 5 arts):
  todas correctas (encuadre dom "guerra", polaridad con colores e IPA 0.800, polaridad
  hacia Franco = negativo -1.000, revisión 6 dudosas, validación con controles).
- Guards verificados (exportar/graficar sin datos → aviso, no crashea).
- **Tests:** `tests/test_quac_portados.py` (31) + `tests/test_ling_handlers.py` (7).
  **Suite total: 855 passed, 11 skipped, 0 failed.** Cero regresiones.

### Archivos
| Archivo | Cambio |
|---------|--------|
| `core/frame_engine.py` | NUEVO — encuadre 10 frames prensa 1930s |
| `core/validacion_engine.py` | NUEVO — Kappa de Cohen + muestra reproducible |
| `core/sentimiento_discriminante.py` | NUEVO — polaridad discriminante + polaridad_hacia(_corpus) |
| `core/revision_engine.py` | NUEVO — human-in-the-loop NER |
| `app.py` | +4 pestañas en `_build_ling`, +handlers, +4 cmds Command Palette, helper `_ir_a_ling_pestania` |
| `tests/test_quac_portados.py` | NUEVO — 31 tests de los 4 motores |
| `tests/test_ling_handlers.py` | NUEVO — 7 tests de los handlers GUI (app headless) |

### Pendiente para próxima sesión
1. **Demo OCR Vision IA (BLOQUEADA sin api_key)** — configurar api_key en ⚙ Config,
   correr Ruta 2 sobre 3-5 págs BNC para tener texto de calidad y demostrar la cadena
   visual end-to-end (etiquetado→segmentación→recorte→descripción).
2. (Opcional) Probar las 4 pestañas con un corpus REAL grande de Estampa para validar
   rendimiento y la utilidad interpretativa de los encuadres/polaridad para el paper.

---

## Sesión 36 — 2026-06-13 — Auditoría de la cadena de producción + Wikidata corpus + visualizaciones

### Contexto
El investigador cuestionó (con razón) que no se había probado la cadena de PRODUCCIÓN
(etiquetado, normalización, segmentación, recorte) y que la red de autores y las
visualizaciones no convencían. Escrutinio completo sobre el corpus real.

### Hallazgo transversal
El código de la cadena está sano; el cuello de botella es la **calidad de las imágenes
BNC** (microfilm, 43% de tinta). Ninguna estrategia de preproceso (denoise NLMeans,
Otsu, adaptativo, CLAHE, upscale 3×) rescata el OCR Tesseract → **requieren OCR Vision IA**.
El texto de la base (motor='legacy') vino de OCR previo, por eso el análisis textual sí funcionó.

### Verificado OK
- **Normalización**: preserva arcaísmos, quita coordenadas BNC, limpia OCR.
- **Segmentación por tipología**: clasifica índice/publicidad/colofón/artículo con texto realista.
- **Detección visual** (sobre imagen limpia): detecta fotos + texto correctamente.

### Bugs reparados
- `core/visual_analyzer.py::analizar_elementos_visuales` — la dilatación agresiva
  (`kernel wc*0.04 × hc*0.025`, 2 iter) fusionaba toda la página en un contorno único
  que superaba el área máxima → **0 elementos**. Fix: `MORPH_CLOSE` moderado (kernel 1.2%)
  + reintento con apertura si queda 1 blob. Corregido también el `del ... dilated, eroded`.
- `core/viz_engine.py` — la nube se generaba sobre texto OCR crudo (dominada por
  "ns/M/uno/todos/ilegible"). Nueva capa `_limpiar_vocabulario_nube` (lematización spaCy
  + `_es_token_valido` + filtro de fragmentos OCR + stopwords ampliadas). Parámetros
  `limpiar=True`/`usar_ia`/`api_key` en `nube_palabras`. Ahora domina
  "ciudad/valor/guerra/intelectual/colombia/moderno".

### Rehecho con criterio
- **Red de autores → red de ENTIDADES co-ocurrentes**. La de autores no procede:
  corpus 74% anónimo, 0 firmas reales. Re-NER guardando TODAS las entidades
  (2.6/artículo vs 1.0 de la base) → red curada de **43 nodos, 8 comunidades temáticas,
  modularidad 0.57**. Comunidades coherentes (guerra de España, mundo anglosajón, Europa).

### Material para el paper (Desktop\Bashkar_Paper_Estampa\)
- `figuras/fig9_red_entidades.png` (red curada), `figuras/fig5_nube_corpus_LIMPIA.png`
- `tablas/red_entidades_v2.gexf` + métricas, `tablas/entidades_wikidata.csv/.json`
- columna `wikidata_qid` añadida a `tablas/indice_ner.csv` (161 entidades enlazadas)
- `REPORTE_INVESTIGADOR.md` con sección §0 de auditoría

### Tests: 817 passed, 11 skipped (cero regresiones)

### Pendientes
1. **Demo OCR Vision IA** (bloqueada sin api_key): configurar clave en ⚙ Config, re-OCR
   3-5 págs BNC, demostrar etiquetado→segmentación→recorte→descripción sobre material bueno.
2. Probar el etiquetador en la GUI (motor tesseract, dividir/fusionar/orden, 👁 OCR zonas).
3. Limpieza de enlaces Wikidata espurios ("Bogo"→Bogotá conf 0.5) con umbral más alto.

---

## Sesión 35 — 2026-06-13 — Wikidata entity_linker: desambiguación reparada

### Problema
`core/entity_linker.py` conectaba pero desambiguaba mal: 5/7 entidades del corpus
erróneas ("Francisco Franco"→tenista colombiano, "España"→acorazado, "Mussolini"→apellido).

### Causas y fix
- `wbsearchentities` pedía `language=es` sin `uselang=es` → descripciones en inglés.
- Ignoraba el ORDEN de Wikidata (primera acepción = más enlazada).
- El bonus "+Colombia" sesgaba al revés; el filtro P31 estaba definido pero sin usar.
- Reescrito `_puntuar_candidato`: señal dominante `2.0 − rango*0.6`, descarte de homónimos
  (`_DESC_DESCARTE`: apellido/barco/pintura), filtro `_P31_VALIDOS` por categoría vía
  `_obtener_p31` (wbgetclaims). **Resultado: 6/7 correctas.**

### Tests: 817 passed (4 nuevos de scoring + 2 de red verificados online)

---

## Sesión 34 — 2026-06-13 — Word2Vec backend PyTorch (gensim no compila en Python 3.14)

### Problema raíz
gensim 4.4.0 (única versión publicada) usa `_longobject.ob_digit` y la firma vieja de
`_PyLong_AsByteArray` — **API interna de CPython eliminada en 3.13+**. No compila en 3.14
ni con C++ Build Tools 2022 + Cython 3.2.5 (`error C2039: ob_digit`). No hay wheel cp314.

### Solución
`core/word_vectors.py` reescrito con doble backend: gensim si está (Python ≤3.12), si no
**PyTorch skip-gram + negative sampling** (`_entrenar_torch`). Clase `_KeyedVectors` con
interfaz idéntica a gensim (`in`, `[palabra]`, `__len__`, `most_similar`, guardar/cargar .npz).
El resto del módulo y la UI no cambian. Validado: 7164 palabras en 53s sobre el corpus real.

### Tests: 816 passed (10 nuevos en test_word_vectors_torch.py)

---

## Sesión 33 — 2026-06-12/13 — Corrida completa del investigador: 6 bugs en uso real

Driver end-to-end sobre el corpus real (219 artículos). 16 motores de core/ ejercitados.
**6 bugs reparados** con tests de regresión (`tests/test_bugs_investigador.py`):
1. `ocr_llm` — respuestas-rechazo del LLM se guardaban como artículos →
   `_es_respuesta_invalida`/`_filtrar_vision`.
2. `sentiment_engine.analizar_intensidad` — `set(cuant)[:3]` no subscriptable → `sorted()`.
3. `stylometry_engine.atribuir_autoria` — fila sparse TF-IDF en `np.dot` → `.toarray().ravel()`.
4. `morfologia_historica` — regex `-ares` marcaba "lugares/hogares" como futuro subjuntivo.
5. `tei_engine` — `xml:id` con espacios/dígitos → XML inválido → `_ncname()`. TEI valida 0 errores.
6. `excel_export` — `.get(k,{})` no protege None + `confianza_autor` ausente.

---

## Sesión 32 — 2026-06-12 (v11.4) — Etiquetador clon FineReader: detección local + OCR por zonas

### El problema

La detección automática de zonas fallaba en el corpus real: los escaneos BNC de
Estampa tienen 12-17° de inclinación y grano de microfilm tan severo que
Tesseract PSM 3 devuelve **0 palabras** por página. Ni el detector OpenCV
original, ni los motores neuronales (DocLayNet — documentos modernos), ni el
XY-cut clásico (falla en layouts "marco" con fotos rodeando el texto)
funcionaban. Además, las zonas solo filtraban el stream lineal de texto por
posición vertical — inútil en páginas multicolumna.

### Nuevo motor `core/layout_tesseract.py` (motor "tesseract", ahora por defecto)

Pipeline validado con páginas reales de Estampa (marzo 1939):

1. **Deskew automático** (hasta 2 pasadas) — Hough sobre líneas de texto +
   respaldo por `minAreaRect` del contenido (necesario para 12-17° donde Hough
   no ve líneas). La imagen corregida SE GUARDA sobre `02_imagenes/` para que
   zonas, canvas y OCR compartan el mismo marco. Validado: +7.4° y +12.3°
   corregidos automáticamente.
2. **Máscara de tinta limpia** — mediana 5 + umbral adaptativo (41, C=25) +
   eliminación de grano (<25px) y líneas largas (marcos/filetes).
3. **Segmentación RLSA** (run-length smoothing) — bloques aunque el layout sea
   de tipo marco. 26-50 zonas/página en <2s donde antes salía 1 bloque.
4. **Clasificación texto/foto por periodicidad del interlineado**
   (autocorrelación de la proyección de filas, umbral 0.22).
5. **Refinamiento Tesseract** cuando el escaneo lo permite: titulo (tipografía
   ≥1.6× mediana), cabecera y numero_pag por posición; pie_foto por adyacencia
   a foto. Filetes/separadores por morfología.
6. **Orden de lectura** automático (bandas por zonas de ancho completo +
   columnas por solapamiento X) — `calcular_orden_lectura` en zone_labeler.

### OCR por zonas (la pieza central de FineReader)

- `ocr_por_zonas()` — recorta cada zona procesable, la mejora (mediana +
  fastNlMeansDenoising + upscale 2x) y la reconoce por separado (PSM 6/7) en
  orden de lectura. Validado: de 0 palabras (página completa) a ~500 palabras
  por página en escaneos BNC. Preserva columnas.
- `ocr_pagina_con_zonas()` — integración pipeline: Ruta 1 y re-OCR de
  Normalizar usan OCR zonal automáticamente si la página tiene etiquetas en
  `05_etiquetas/`; metodo="ocr_zonas" en metadatos.

### Editor de zonas (app.py)

- Campo `orden` en `Zona` (persiste en JSON, retrocompatible).
- Badge circular azul con el número de orden de lectura en cada zona del canvas.
- Menú contextual nuevo: **✂ Dividir aquí** (horizontal/vertical, corta en el
  punto exacto del clic), **🔗 Fusionar con…**, **🔢 Recalcular orden de lectura**.
- Botón **👁 OCR zonas** (verde) — vista previa threaded del OCR zonal de la
  página actual en el panel TEXTO OCR, con separadores por zona y confianza.
- Motor "tesseract" agregado al combobox y como valor por defecto; rama
  threaded en detectar página/número; recarga de imagen tras deskew.
- `_etz_instalar_motor` ya no intenta instalar motores locales.

### Módulos

- `core/layout_tesseract.py` (nuevo, ~600 líneas) — todo el motor.
- `core/zone_labeler.py` — `orden` en Zona, `calcular_orden_lectura()`,
  `dividir_zona()`, `fusionar_zonas()`.
- `tests/test_layout_local.py` (nuevo) — 24 tests: clasificación, orden de
  lectura (bandas/columnas), dividir/fusionar, persistencia, fallbacks.

### Tests

**791 passed, 9 skipped, 0 failed** (antes 767 — 24 nuevos, sin regresiones).

### Limitación conocida

En las páginas más degradadas (fotograbado puro, p.ej. "La Sierra Nevada"),
la clasificación texto/foto comete errores — el flujo es: detectar → corregir
tipos con clic derecho → guardar → OCR zonal. La calidad del OCR sigue
limitada por la fuente (conf ~35 en los peores escaneos); para esas páginas
la ruta Claude Vision sigue siendo la de máxima calidad.

---

## Sesión 31 — 2026-06-05 (v11.4) — Persistencia completa + UX vanguardia

### Persistencia / autoguardado (core/project_manager.py + app.py)

**Problema raíz:** `df_articulos` se guardaba sin columna `texto` (drop explícito en línea 213), por lo que `corpus_txt` quedaba vacío al restaurar un proyecto → módulo Lingüística, colocaciones y búsqueda semántica no tenían textos al reanudar sesión.

**Solución:**
- `guardar_proyecto` — escribe `<datos_dir>/corpus_txt.json` con la lista de textos planos si `ST.corpus_txt` no está vacío.
- `cargar_proyecto` — restaura `ST.corpus_txt` desde ese JSON si existe; si no, reconstruye automáticamente leyendo el archivo TXT más reciente de cada subcarpeta en `out_dir/03_ocr/`.
- `_autoguardar_periodico()` — `self.after(180_000, ...)` en `__init__`; guarda silenciosamente cada 3 minutos solo cuando `_hay_cambios=True`; se reprograma indefinidamente.
- `_marcar_modificado()` — activa `●` en el nombre del proyecto (ámbar `#F59E0B`); inicia pulso entre dos tonos para señal visual suave. Se llama al terminar segmentación, análisis textual y guardar bloque Normalizar.
- `_limpiar_modificado()` — quita el `●` y restaura color normal. Se llama tras guardar manual y en autoguardado exitoso.

### 6 mejoras UX de vanguardia (app.py)

**Toast notifications** — `toast(msg, tipo, duracion)` no-modal esquina inferior derecha:
- Tipos: `info/ok/warn/error` con colores e íconos distintivos.
- Fade in/out animado (16ms/frame, ~30 steps).
- Apilado automático: múltiples toasts se posicionan sin solaparse.
- Botón `×` para cerrar anticipadamente.
- Reemplaza ~10 `messagebox.showinfo` de confirmaciones no críticas (OCR OK, segmentación OK, análisis OK, exportar CSV, guardar etiquetas, exportar red, exportar gráfico, configurar archivos, exportar bitácora).

**Command Palette** — `_abrir_command_palette()`:
- `Ctrl+K` global (bind_all) + botón `⌨` en topbar.
- 21 comandos indexados: 15 de navegación de páginas + 6 acciones (guardar, proyectos, nuevo, adhoc, bitácora, tema).
- Filtrado live en `Entry`, navegación `↑↓`, `Enter` ejecuta, `Esc` cierra.
- Se cierra solo al perder el foco (FocusOut con delay 150ms).
- Hint visual de atajos en pie del panel.

**Micro-animaciones**:
- `_pulso_modificado()` — pulsa el indicador `●` entre `#F59E0B` y `#E6A817` cada 800ms; se detiene automáticamente cuando `_hay_cambios=False`.
- Hook `_fade_pagina()` disponible para transiciones al cambiar de página.

**Skeleton loading** (panel Segmentación):
- `_skeleton_show(parent, n_filas)` — crea frame con barras grises sobre el Treeview mientras el worker corre.
- `_skeleton_animar()` — pulso de brillo entre `CARD_BOR` y `#3A3A3A` cada 400ms.
- `_skeleton_hide(sk)` — destruye el frame al llegar el resultado.
- Referencia `_tv_seg_outer` + `_seg_skeleton` guardada en `_build_seg`.

**Progressive disclosure** — `_mk_avanzado(parent, label, build_fn)`:
- Helper lazy: el `build_fn(frame)` solo se ejecuta la primera vez que el usuario despliega la sección.
- Flecha `▶/▼` animada.
- Aplicado en panel Segmentación: umbral de confianza de autoría (Slider 0.1–0.9) y máx. artículos por número (Spinbox).

**Glassmorphism** — `_mk_glass_toplevel(titulo, ancho, alto)`:
- Devuelve `(win, content_frame)`.
- Borde 1px color `HDR_LINE` (azul VS Code), shadow interior frame `#1A1A1A`, header con botón `✕` (hover → rojo).
- Aplicado a ventana Bitácora (`bit_content` como contenedor del Notebook).

### Archivos modificados

| Archivo | Qué cambió |
|---|---|
| `core/project_manager.py` | `guardar_proyecto`: serializa `corpus_txt.json`; `cargar_proyecto`: restaura desde JSON o reconstruye desde `03_ocr/` |
| `app.py` | `__init__`: `_hay_cambios`, `_cp_win`, `_toasts_activos`, bind `Ctrl+K`, `after(180_000, autoguardar)`; métodos toast/skeleton/palette/glass/avanzado; `_on_ok` → toasts; `_start_seg` → skeleton; `_bitacora_abrir` → glass; `_build_seg` → progressive disclosure |

### Tests
- **767 passed, 9 skipped** — sin regresiones

### Pendientes próxima sesión
1. Crear acceso directo `Bashkar Station v11.4.lnk` en Escritorio
2. Compilar nuevo `.exe` (último compilado era v10.7)
3. Probar flujo completo corpus Estampa con el módulo Lingüística
4. Integrar Kraken como opción seleccionable en `_build_ocr`
5. Aplicar `_mk_glass_toplevel` y `_mk_avanzado` en más paneles (NER, Análisis)

---

## Sesión 30 — 2026-06-04 (v11.4) — Lingüística Computacional

### Módulos nuevos

**`core/sintaxis_engine.py`** — Análisis sintáctico y extracción de relaciones:
- `analizar_dependencias(texto, nlp)` — árbol de dependencias spaCy por oración; extrae sujeto, verbo raíz, objeto directo.
- `resumir_arbol_dep(oracion_info)` — resumen legible `[sujeto: X] [verbo: Y] [objeto: Z]` para la UI.
- `concordancias_sintaticas(corpus, patron)` — concordancias KWIC sintácticas con 6 patrones: `verbo_sujeto`, `verbo_objeto`, `sustantivo_adj`, `entidad_verbo`, `negacion`, `pregunta`. Con callback de progreso y límite de resultados.
- `extraer_relaciones(corpus)` — tripletas sujeto-relación-objeto con score de confianza 0–1; filtro opcional a solo entidades nombradas.
- `agrupar_relaciones(relaciones)` — agrupa tripletas por verbo con conteo de frecuencia.
- `exportar_relaciones_csv(relaciones, ruta)` — CSV con todos los campos SVO.

**`core/coref_engine.py`** — Resolución de correferencia (100% offline):
- `resolver_correferencias(texto)` — cadenas referenciales por heurísticas spaCy NER + pronombres (distancia máx. 3 oraciones). Fallback automático a `coreferee` si está instalado.
- `cadena_referencial(texto, entidad)` — todas las menciones de una entidad específica con contexto de oración.
- `sustituir_referencias(texto)` — reemplaza pronombres por su antecedente para mejorar NER posterior.
- `estadisticas_coref(corpus)` — densidad referencial, promedio de menciones por cadena, top 20 entidades más referidas.

**`core/morfologia_historica.py`** — Español histórico 1900–1950:
- `normalizar_formas_historicas(texto)` — normaliza grafías históricas (fué→fue, setiembre→septiembre, ó entre números→o) sin cambiar el significado.
- `lematizar_historico(tokens)` — lematiza con 80+ excepciones para formas que spaCy moderno no reconoce (habia→haber, tenia→tener, decia→decir, etc.).
- `analizar_morfologia_token(token)` — análisis morfológico completo: lema, POS, rasgos morfológicos, si es arcaísmo y de qué tipo.
- `analizar_densidad_historica(texto)` — score 0–1 de cuán arcaico es el texto; detecta 6 tipos de marcadores: futuro subjuntivo, voseo, vocativo formal, superlativos en -ísimo, construcciones inversas, acusativo preposicional.
- `glosario_arcaismos()` — lista ordenada de todas las excepciones.
- `enriquecer_corpus_con_lemas(corpus)` — stats de arcaísmos por documento para análisis del corpus completo.

**`core/sentiment_engine.py`** — Extensión offline (análisis emocional sin API):
- `analizar_emociones(texto)` — 8 emociones básicas (alegría, tristeza, miedo, ira, sorpresa, confianza, disgusto, anticipación) con léxico NRC adaptado al español histórico (~150 palabras). Incluye emoción dominante, distribución porcentual, subjetividad y tipo de discurso.
- `analizar_subjetividad(texto)` — clasifica oraciones como factuales u opinativas; retorna score 0–1, tipo de discurso (subjetivo/factual/mixto), marcadores detectados y ejemplos.
- `analizar_intensidad(texto)` — detecta intensidad retórica: superlativos en -ísimo, exclamaciones, cuantificadores extremos (nunca/siempre/jamás), énfasis gráfico (!!).
- `analisis_completo_emocion(texto)` — combina las tres funciones anteriores en un dict; función de conveniencia para la UI.

### Panel nuevo en Activity Bar

Página **🔭 Lingüística** registrada como `"ling"` en grupo `analisis` con 5 pestañas:

1. **🌲 Sintaxis** — selector de 5 patrones sintácticos, tabla de concordancias, exportar CSV
2. **🔗 Relaciones SVO** — tabla sujeto→verbo→objeto con tipo de entidad y confianza; agrupar por verbo (ventana flotante); exportar CSV
3. **🔁 Correferencia** — listbox de cadenas referenciales + visor de menciones; filtro por entidad; estadísticas del corpus
4. **📜 Morfología histórica** — score por documento, top formas arcaicas, resumen del corpus, glosario en ventana flotante, exportar CSV
5. **💭 Emociones** — emoción dominante/subjetividad/intensidad por artículo, resumen estadístico, gráfico de barras matplotlib, exportar CSV

### Fixes y mejoras internas

- `Estado.reset()` — nuevo atributo `corpus_txt: list[str]` inicializado a `[]`.
- `_worker_seg` — al finalizar la segmentación, construye `ST.corpus_txt` desde `df_articulos["texto"]` para que el módulo de lingüística lo use directamente sin re-leer los TXTs.

### Tests

- `tests/test_linguistica.py` — 47 tests nuevos que cubren los 4 módulos: sintaxis, correferencia, morfología histórica, extensiones de sentiment.

### Versión
- `APP_VERSION` → `11.4`
- Suite de tests: **764 passed** (estimado tras agregar los nuevos)

---

## Sesión 29 — 2026-06-04 (v11.3) — Análisis de grafos completo

### Panel Redes — expansión completa

**`core/network_engine.py` — funciones nuevas:**
- `metricas_avanzadas(G)` — betweenness centrality, PageRank, closeness centrality. Agrega los valores como atributos de nodo para exportación en GEXF. Detecta y agrupa comunidades Louvain.
- `evolucion_temporal(indice_por_numero, ...)` — calcula métricas por cada número del corpus y retorna serie temporal: nodos, aristas, densidad, nodo más central.
- `exportar_metricas_csv(G, metricas_av, ruta)` — CSV con grado, betweenness, PageRank, closeness, comunidad y categoría por nodo.

**Panel Redes UI — 4 nuevas pestañas en Notebook:**
1. **Métricas** — tabla de métricas globales + top 10 nodos por centralidad de grado
2. **Centralidad avanzada** — selector radio betweenness/PageRank/closeness, tabla top 30
3. **Comunidades** — lista de comunidades Louvain con N miembros; clic → ver miembros con grado
4. **Evolución temporal** — tabla y gráfico matplotlib de cómo cambia la red número a número

**Botones nuevos en barra:**
- `🔬 Métricas avanzadas` — calcula betweenness, PageRank, closeness en worker thread
- `📅 Evolución temporal` — calcula la serie temporal número a número
- `💾 CSV métricas` — exporta tabla completa de métricas por nodo

### Versión
- `APP_VERSION` → `11.3`

---

## Sesión 28 — 2026-06-04 (v11.2) — Cierre de brechas

### Bugs críticos corregidos
- **Persistencia de configuración lingüística**: `stopwords_proyecto` y `lematizar` ahora se guardan en el `.bashkar` al guardar el proyecto y se restauran al cargarlo (`project_manager.py` + `_confirmar_cfg`). También `norm_version` se persiste correctamente.
- **Sincronización UI al cargar**: `_sincronizar_ui_con_st` restaura el checkbox de lematización y el textarea de stopwords con los valores del proyecto cargado.
- **`requirements.txt`** actualizado: agrega `SpeechRecognition`, `sounddevice`, `lxml`, `transformers`, `sentence-transformers`, `torch`, `faiss-cpu`.

### Panel Validar — completado
- Botón **✅✅ Marcar todas 🟢 como verificadas** — valida en lote todas las entidades de confianza verde.
- Botón **📥 Exportar CSV** — exporta la tabla de validación a CSV.
- Al guardar en KB, marca la etapa `anal` como `ready` en los semáforos.

### Búsqueda semántica — fallback léxico
- Sin índice FAISS construido, la búsqueda ahora usa `_bsem_buscar_lexico()`: búsqueda por coincidencia de términos en los TXT del corpus con score por cobertura. Nunca más muestra solo un error — siempre retorna resultados.

### Modo ad-hoc (análisis sin proyecto)
- Botón **⚡** en topbar: carga directamente una carpeta de TXT sin crear proyecto `.bashkar`. Útil para demostraciones, análisis exploratorio, y clase.

### README expandido
- Guía completa de instalación, flujos de trabajo, arquitectura, decisiones metodológicas, instrucciones de citación en BibTeX para Zenodo.

### Tests — 44 tests nuevos (integración)
- `tests/test_integration_pipeline.py` — 15 tests de integración end-to-end:
  - Carga/guardado de proyecto con stopwords y lematizar
  - Roundtrip completo de índice NER
  - Normalización preserva arcaísmos
  - Pipeline corpus → n-gramas → frecuencias
  - Bitácora persiste entre instancias

### Versión
- `APP_VERSION` → `11.2`

---

## Sesión 27 — 2026-06-04 (v11.1) — Completitud HD

### Panel Collocates — expansión completa
- **Export CSV** en concordancias KWIC, collocates y frecuencias
- **Frecuencia relativa** — checkbox "/10.000 palabras", exporta ambas columnas
- **N-gramas** — nueva subpestaña con bigramas/trigramas, filtro stopwords, export CSV
- **Dispersión léxica** — nueva subpestaña con gráfico matplotlib tipo AntConc (posición en corpus por palabra)
- **Stopwords del proyecto** — nueva subpestaña para agregar términos específicos (arcaísmos, nombres propios del corpus) a la lista base
- **Lematización configurable** — en Configuración sección 3, opción para desactivar lematización en corpus histórico (preserva formas originales del español de los años 30)

### NER — Wikidata integrado
- Tabla NER ahora muestra columna "Wikidata" con el label del enlace
- Doble click en cualquier entidad abre su página Wikidata en el navegador
- `_ner_abrir_wikidata()` resuelve URL desde `ST.wikidata_enlaces`

### Resultados — Metodología y reproducibilidad
- **`core/methods_reporter.py`** — genera METHODS.md con versiones de software, parámetros del pipeline, estadísticas del corpus; listo para sección de metodología en paper
- **📋 METHODS.md** — botón en panel Resultados
- METHODS.md incluido en ZIP del Paquete de publicación

### Colaboración — flujo completo
- `_colab_importar_worker` ahora muestra vista previa del parche (autor, fecha, notas, N secciones) y pide confirmación antes de aplicar
- Backup automático `.bashkar.bak` antes de aplicar cualquier parche

### Estado global (ST)
- `ST.stopwords_proyecto` — lista de stopwords adicionales del proyecto
- `ST.lematizar` — flag de lematización (True/False)

### instalar.py
- Agregados: `SpeechRecognition`, `sounddevice`, `lxml`, `python-docx`, `python-pptx`, `pyvis`, `folium`

### Tests
- `tests/test_v11_features.py` — **29 tests, todos pasando**
  - BitacoraEngine (10 tests), TimelineEngine (3), KrakenTrainer (3), MethodsReporter (2), NGramas (4), StopwordsPersonalizadas (2), Dispersion (2), ValidarTei (3)

### Versión
- `APP_VERSION` → `11.1`

---

## Sesión 26 — 2026-06-04 (v11.0) — Super Sayayín

### Nuevo — Bitácora de investigación
- **`core/bitacora_engine.py`** — motor completo: notas libres, hipótesis (con estado abierta/confirmada/descartada/revisada), citas de corpus. Persistencia SQLite en el proyecto.
- **`datos/schema.py`** — nueva tabla `notas_investigacion` (tipo, estado, texto, etiquetas, ref_numero, ref_pagina, ref_art_id, modulo_origen).
- **`datos/repositorio.py`** — métodos CRUD: `insertar_nota`, `actualizar_nota`, `eliminar_nota`, `listar_notas`.
- **Ventana 📓** en topbar — flotante siempre encima, no modal. Tabs: "Nueva nota" | "Todas las notas". Filtros por tipo/estado/búsqueda. Export a Markdown.
- **Botón 📓 Nota** en 6 módulos: Normalizar, Segmentar, Analizar, NER, Anotar, Collocates. Pre-rellena número/página del módulo activo.

### Nuevo — Funciones metodológicas HD
- **`core/timeline_engine.py`** — genera HTML interactivo con vis.js. Artículos coloreados por sección/tono/autor con tooltips. Reemplaza la versión básica anterior.
- **`core/kraken_trainer.py`** — exporta pares (imagen, transcripción_manual) para reentrenamiento HTR con `ketos train`. Formato compatible con Kraken 7+.
- **`cli.py`** — interfaz de línea de comandos: `python cli.py --proyecto X.bashkar --etapas ocr,norm,seg,anal,ner,tei,csv`. Incluye `--info` para inspeccionar proyectos.
- **`core/tei_engine.py`** — nueva función `validar_tei(ruta_xml)`: verifica XML bien formado + namespace TEI P5 + elementos obligatorios (teiHeader, text).

### Nuevo — En Normalizar
- **🔍 Ver cambios** — diff visual coloreado (rojo=eliminado, verde=añadido) entre OCR crudo y versión manual. Usa `difflib`, sin dependencias nuevas.
- **🏋 Dataset HTR** — exporta ground truth para reentrenamiento Kraken desde el número seleccionado.

### Nuevo — En Resultados
- **✓ Validar TEI** — valida el XML-TEI exportado contra esquema P5.
- **📦 Paquete publicación** — genera ZIP con corpus.xml + corpus.bib + entidades.csv + bitacora.md + metadatos.json. Un click para tener todo listo para el paper.

### Versión
- `APP_VERSION` actualizada a `11.0`.

---

## Sesión 25b — 2026-06-04 (v10.8)

### Nuevo
- **Secciones colapsables en Configuración**: las 8 secciones de la pantalla de configuración ahora tienen encabezados clickeables (▼/▶) que muestran u ocultan su contenido. Las secciones 1–4 abren por defecto (las más usadas); 5–8 cerradas por defecto para reducir el scroll inicial.
- **Nombre del proyecto en tiempo real**: al escribir el nombre de la publicación en Configuración sección 1, la etiqueta de la topbar y del sidebar se actualiza inmediatamente (sin necesidad de pulsar "Confirmar").

### Corregido
- **Ícono Segmentar desalineado** en la Activity Bar: `✂️` (con variation selector U+FE0F) renderizaba como emoji grande en Windows. Reemplazado por `✂` (sin selector) para alineación consistente.
- `APP_VERSION` actualizada a `10.8`.

---

## Sesión 25 — 2026-06-04

### Nuevo
- **Diccionario de corpus** (`📖 Diccionario de corpus` en panel Normalizar): botón que ejecuta `construir_diccionario_corpus()` en thread separado, escanea todos los `.txt` de `03_ocr/`, guarda `diccionario_corpus.json` con frecuencias (freq ≥ 3), muestra top-5 palabras en el estado y abre diálogo con resumen.

### Corregido
- **Bug barra lateral al cambiar de contexto**: `_poblar_sidebar_contexto` destruía widgets del sidebar anterior pero dejaba sus referencias en `self._sb_btns`; las iteraciones posteriores (`_aplicar_estilo_sb_btn`, `_actualizar_badges`) llamaban `.config()` sobre widgets destruidos. Fix: los pids del contexto anterior se eliminan de `_sb_btns` antes de repoblar.

### Verificado (ya implementado, no pendiente)
- **Detección negrita/cursiva**: `alto_reconstructor.py` líneas 207-224 ya detecta `bold`/`italic` desde flags PyMuPDF (bit 4 = bold, bit 1 = italic) y los expone en cada entrada de línea.
- **Detector columnas HoughLinesP**: `zone_labeler.py` líneas 174-207 ya implementa filetes horizontales/verticales y separadores de columna via morfología + contornos.
- **Kraken CATMuS large con 7 GB RAM**: evaluado con corpus real (página 3, Marzo 1939, 35 líneas). RAM total: 0.78 GB (modelo: 0.25 GB, BLLA: +0.13 GB, OCR: +0.11 GB). Factible. Reconoce texto coherente en español de los años 30. Advertencias `TopologyException` son conocidas y no impiden el procesamiento. No es necesario descargar modelo small — el large funciona bien.

---

## Sesión 24 — 2026-06-03 (v10.7)

### Nuevo
- **Conversor masivo PDF→Word/TXT** (`core/conversor_pdf_a_word.py` + panel ⚡ en Activity Bar Ingestión): extrae texto embebido de PDFs BNC sin re-OCR. 48 páginas en 7 segundos.
- **Limpieza BNC integrada** (`limpiar_coordenadas_bnc` en `ocr_normalizer.py`): elimina coordenadas XY de Adobe Paper Capture, sello BNC, normaliza Unicode y une guiones de columna.
- **Selector de versión en Normalizar**: barra con 3 opciones (Crudo / Manual / IA) que determina qué texto pasa al pipeline. Persiste en el proyecto `.bashkar`.
- **Zoom/pan en imagen de Normalizar**: botones +/−, Ctrl+rueda, arrastrar para pan, scrollbars.
- **Flujo Conversor→Normalizar→Segmentar→Análisis** sin necesitar pipeline OCR previo: `_reconstruir_corpus_meta_desde_txt()` construye el índice desde los TXT existentes en `03_ocr/`.
- **`exportar_para_normalizar`** en ConfiguracionConversor: escribe `p0001.txt...` en `03_ocr/<nombre>/` y refresca Normalizar automáticamente al terminar.

### Corregido
- `_worker_seg`, `_worker_anal`, `_worker_vis`, `_worker_comp` ya no crashean con `TypeError: NoneType` cuando `ST.corpus_meta` es None — reconstruyen desde disco.
- Separador visual cortaba la opción "Imágenes sueltas" en Configuración (row grid incorrecto).
- `_conv_modo`, `_conv_word_pag`, `_conv_txt_pag` faltaban en el panel rediseñado del Conversor → botón Convertir no hacía nada.
- Imagen en Normalizar no cargaba cuando el texto venía del Conversor (buscaba en `02_imagenes/` inexistente) — ahora renderiza directamente desde el PDF original vía PyMuPDF.
- Error 401 IA en Normalizar mostraba texto enterrado en lugar de messagebox visible.
- Persistencia de carpetas entre sesiones: `_sincronizar_ui_con_st` restaura campos del Conversor.

### Versión
- `APP_VERSION` y etiquetas de UI actualizadas a `10.7`.

---

## Sesión 23 — 2026-06-02

### Implementado

| Área | Cambio |
|---|---|
| **Modo Subcarpetas** | Nuevo radiobutton "📁 Subcarpetas" en Configuración. Cada subdirectorio = un número. `_poblar_lista` detecta PDFs internos y los muestra con conteo y tamaño |
| **`_worker_ocr_carpetas`** | Worker dedicado: itera PDFs de cada subcarpeta como páginas, extrae imagen a color con PyMuPDF (150 DPI), reconstruye texto con `alto_reconstructor`, normaliza y guarda en `03_ocr/<nombre>/` |
| **Análisis corpus Estampa** | 48 PDFs/número · 46 páginas útiles · 772 palabras/pág · 3.3% ruido · fuente `HiddenHorzOCR` (ABBYY BNC). La Ruta 3 BNC es la óptima para este corpus |
| **Módulo imgdesc en Analizar** | `_build_imgdesc`: tabla ordenable, filtros por categoría, visor de recorte, búsqueda similitud FAISS, exportación CSV/JSON. Proveedor + modelo intercambiables |
| **Etiquetar → 📊 Estadísticas** | Reemplaza botón Describir. Muestra conteo por tipo de zona, manuales vs predichas, acceso directo a Desc. imágenes |
| **Normalizar — herramientas** | 📂 Importar .txt (página o carpeta completa), ⚙ Reconstruir columnas BNC, 🖼 Regenerar imágenes desde PDF, 🔄 Re-OCR Tesseract (página o número) |
| **Prompt tipos custom** | `construir_prompt_deteccion()` incluye todos los tipos activos incluyendo los del usuario (★ crédito, etc.) |

**Tests:** 673 passed, 9 skipped, 0 failed
**Exe:** v10.6 en `D:\Programas\BashkarStation\` · acceso directo `Bashkar Station v10.6.lnk`

---

## Sesión 22 — 2026-06-02

### Arquitectura

| Área | Cambio |
|---|---|
| **Módulo Descripción de imágenes** | Movido de ribbon Etiquetar → módulo propio "🎨 Desc. imágenes" en contexto Analizar |
| **Etiquetar → 📊 Estadísticas** | Reemplaza el botón Describir: muestra conteo de zonas por tipo, manuales vs predichas, botón para ir a Desc. imágenes |
| **Ruta 3 BNC** | Ahora usa `alto_reconstructor.reconstruir_texto_pagina()` con coordenadas X/Y en vez de `get_text("text")` simple — reconstruye el orden correcto de columnas. Elimina la marca "Digitalizado Biblioteca Nacional de Colombia" automáticamente |
| **pdf_a_imagenes** | Usa PyMuPDF con `page.get_pixmap(matrix=mat, alpha=False)` que respeta la rotación embebida en los metadatos del PDF. Fallback a poppler si no está disponible |
| **ocr_pagina** | No convierte a gris antes de Tesseract; contraste reducido de 1.5→1.2; modo "L" solo si es necesario |
| **Normalizar → 📂 Importar .txt** | Importa archivo externo (de Acrobat u otro) para página o carpeta completa |
| **Normalizar → ⚙ Reconstruir columnas BNC** | Aplica `reconstruir_lineas_rotas` a página actual o número completo |
| **Normalizar → 🖼 Regenerar imágenes** | Borra las imágenes existentes y las re-extrae del PDF original con PyMuPDF |
| **Normalizar → 🔄 Re-OCR Tesseract** | Re-extrae texto de páginas con OCR corrupto (ej. Kraken sin RAM) |
| **Deskew** | Ya no sobreescribe la imagen original — guarda la versión corregida en `02_imagenes_ocr/` |
| **Prompt detección de zonas** | Generado dinámicamente con `construir_prompt_deteccion()` — incluye tipos custom del proyecto (★) |
| **Ruta 2 OCR** | Multiproveedor: Claude / GPT-4o / Gemini / Ollama. Función `_ocr_vision_multiproveedor()` con prompt de transcripción OCR específico |
| **Prompt tipos custom en IA** | `construir_prompt_deteccion()` incluye todos los tipos activos (base + custom) con descripción y marca ★ |
| **Paleta VS Code** | Dark+ (`#1E1E1E`, `#252526`, `#333333`) y Light+ (`#FFFFFF`, `#F3F3F3`, `#2C2C2C`) — activity bar siempre oscura |
| **Scroll sidebar** | `_hacer_scrollable()` propaga `<MouseWheel>` a todos los hijos dinámicamente |
| **Suprimir zona** | `<Delete>` y `<BackSpace>` en canvas y listbox del etiquetador eliminan la zona seleccionada |

**Tests:** 673 passed, 9 skipped, 0 failed

---

## Sesión 21 — 2026-06-02

### Implementado

| Área | Cambio |
|---|---|
| **Predicción de zonas** | `DetectorZonas` conectado a la UI: entrena automáticamente al guardar, botón "🔮 Predecir resto" aplica plantilla al número completo |
| **Bug fix predicción** | `cargar_todas_manual` devuelve lista, no dict — corregido en `_etz_entrenar_detector` y `_etz_predecir_numero` |
| **Bug fix Normalizar** | Panel carga automáticamente al entrar; `_norm_refrescar_numeros` recarga siempre, no solo si el combobox estaba vacío |
| **Bug fix IA Normalizar** | `mejorar_texto_ocr` no existía → corregido a `corregir_texto(texto, api_key)` |
| **Argentinismos** | 41 reemplazos: voseo directo + "Primero X" → forma neutral |
| **Toggle dark/light mode** | Botón `☀/🌙` en topbar; paletas `_PALETA_DARK` y `_PALETA_LIGHT` completas; `_toggle_theme()` repinta todos los widgets |
| **`core/layout_neural.py`** | Módulo nuevo: motores YOLO, ONNX, DiT + instalación asistida + `motor_disponible()` |
| **Motor YOLO** | YOLOv8n-DocLayNet (~6 MB), CPU ~2s/pág, auto-descarga |
| **Motor ONNX** | YOLOS-DocLayNet ONNX (~45 MB), sin torch, CPU ~1s/pág |
| **Motor DiT** | Microsoft DiT via transformers (~330 MB), para PC ≥16 GB RAM |
| **Motor `vision_ia`** | Claude, GPT-4o, Gemini, Ollama — mismo prompt, proveedor intercambiable |
| **`detectar_zonas_vision()`** | Función unificada en `zone_labeler.py` con backends: `_vision_claude`, `_vision_openai`, `_vision_gemini`, `_vision_ollama` |
| **UI etiquetador** | Combobox motor: opencv/yolo/onnx/dit/vision_ia; sub-selector proveedor+modelo (aparece solo con vision_ia); botón ✏ Prompt; botón ⬇ Instalar; botones ? con tooltips en todos los selectores |
| **Prompt editable** | Único prompt compartido por todos los proveedores; editable con `_etz_editar_prompt`; persiste con el proyecto |

**Tests:** 673 passed, 9 skipped, 0 failed

---

## Sesión 20 — 2026-06-02

### Arquitectura investigativa completada

| Módulo / área | Cambio |
|---|---|
| `_worker_ner_articulo` / `_worker_ner_corpus` | Leen `PARAMS_SCHEMA` del panel lateral: motor, umbral confianza, categorías activas, mín. palabras |
| `core/ner_engine.py — pipeline_ner` | Nuevos kwargs `umbral_confianza`, `categorias`; solo retorna categorías activas |
| `_worker_tono` | Lee params del panel: motor (ia/lexicon/transformers), workers paralelos |
| `_worker_top` / `_top_ejecutar` | Lee params: backend, n_topics, min_df, max_df, n_palabras |
| `core/topic_engine.py — modelar_topicos` | Acepta `min_df`, `max_df`, `n_palabras`; los pasa a `_modelar_nmf` |
| `core/topic_engine.py — _modelar_nmf` | Usa `min_df`, `max_df`, `n_palabras` configurables |
| `_build_coloc` | Panel lateral de parámetros collocates integrado |
| `_build_sem` | Panel lateral de parámetros sentimiento integrado |
| `_build_top` | Panel lateral de parámetros topic modeling integrado |
| `_on_ok` | Llama `_norm_refrescar_numeros` tras completar OCR; llama `_actualizar_badges` siempre |
| `bashkar_station.spec` | Actualizado a v10.3 con todos los módulos nuevos en `hiddenimports` |

**Tests:** 673 passed, 9 skipped, 0 failed

---

## Sesión 19 — 2026-06-02

### Nuevas funcionalidades

| Módulo | Cambio |
|---|---|
| `core/ocr_engine.py` | `ocr_pagina()` llama a `preprocesar_para_ocr()` (deskew + enhance + despeckle) antes de Tesseract |
| `core/alto_reconstructor.py` | Campos `bold` e `italic` en cada línea (PyMuPDF flags bit 4 / bit 1) |
| `core/ocr_normalizer.py` | `construir_diccionario_corpus()` + `detectar_palabras_sospechosas()` |
| `core/zone_labeler.py` | Detección de filetes y separadores de columna (paso 4 en `detectar_zonas_opencv`); tipos base `filete` y `separador_columna` |
| `core/text_postprocessor.py` | **Módulo nuevo** — `ordenar_zonas_lectura()`, `normalizar_bloque()`, `postprocesar_pagina()`, `postprocesar_numero()`, `bloques_desde_etiquetas()` |
| `core/ner_engine.py` | `PARAMS_SCHEMA` con 5 parámetros configurables |
| `core/sentiment_engine.py` | `PARAMS_SCHEMA` con 5 parámetros configurables |
| `core/collocation_engine.py` | `PARAMS_SCHEMA` con 6 parámetros configurables |
| `core/topic_engine.py` | `PARAMS_SCHEMA` con 6 parámetros configurables |
| `app.py — Estado` | `estado_etapas` dict + `marcar_etapa()` con propagación de `stale`; `norm_done` |
| `app.py — sidebar` | `_actualizar_badges()` muestra semáforo ✓/⚠ por etapa (verde=ready, amarillo=stale) |
| `app.py — Activity Bar` | Nuevo contexto **📝 Normalizar** entre Ingestión y Segmentar |
| `app.py — _build_norm` | Panel de 4 vistas: imagen · OCR crudo · edición usuario · sugerencia IA; persistencia SQLite `normalizaciones` |
| `app.py — _build_params_panel` | Generador dinámico de panel lateral de parámetros desde `PARAMS_SCHEMA` |
| `app.py — _build_ner` | Panel de parámetros NER integrado como primer ejemplo |

### Flujo de trabajo actualizado

```
📥 Ingestión → 📝 Normalizar → ✂️ Segmentar → 🔬 Analizar → 🎨 Visualizar → 📤 Publicar
```

Cada etapa del flujo muestra semáforo (✓ verde / ⚠ amarillo) en el sidebar.

**Tests:** 673 passed, 9 skipped, 0 failed

---

## Sesión 18 — 2026-06-02

### Problemas resueltos

| Problema | Causa raíz | Solución |
|---|---|---|
| Texto invisible (dark mode incompleto) | 100+ widgets con colores claros hardcodeados | Sustitución global + tags Treeview + ScrolledText sin `fg` |
| NER con "tesseract" como entidad | Fallback tomaba primer `.txt` incluyendo logs | Fallback exige >100 palabras reales |
| Panel Resultados vacío | `_cargar_resultados()` silencioso sin `anal_done` | Muestra "—" con mensaje de flujo correcto |
| Ribbon desbordado | Todos los controles en 1 fila de 36px | Rediseño en 2 filas |
| Scroll sidebar crash | `bind_all` causaba error al navegar contextos | Revertido a bind directo sobre canvas |
| Tesseract sin español | Solo `eng.traineddata` instalado | `spa.traineddata` en `C:\Users\Lenovo\tessdata\` |
| `No module named 'core.ocr_normalizer'` | Fallback Kraken sin `core/` en sys.path | `ocr_engine.py` agrega root al sys.path |
| Globs txt incorrectos | `glob("*/txt")` no encontraba archivos | Corregido a `03_ocr/` con `iterdir()` |
| Etiquetador desconectado del OCR | Sin mecanismo para que etiquetas influyan en OCR | Checkboxes "Usar zonas" + "Detección IA" en panel OCR |
| Imagen no carga en etiquetador | `_etz_get_img_path` devolvía None | 3 fallbacks: caché → PDF directo → canvas |

### Archivos modificados

| Archivo | Cambio principal |
|---|---|
| `app.py` | Dark mode completo; ribbon 2 filas; scroll sidebar; OCR+etiquetas conectados; NER fix; botón "📂 PDF"; `_ocr_aplicar_zonas()` |
| `core/ocr_engine.py` | `sys.path` + búsqueda tessdata |
| `core/zone_labeler.py` | Tipos extensibles con JSON global |
| `core/article_segmenter_v2.py` | Fix `_detectar_seccion(titulo, texto)` |
| `tesseract_path.txt` | Creado |
| `tests/test_gutter_deepfont.py` | 29 tests nuevos |

**Tests:** 673 passed, 9 skipped, 0 failed

---

## Sesión 14 — 2026-05-28

### Kraken venv en D:\kraken_env · Instalación exitosa

#### Problema resuelto: MAX_PATH de Windows bloqueaba instalación de torch

**Causa raíz:** Windows tiene un límite de 260 caracteres en rutas de archivo. La ruta
`I:\Mi unidad\00_Programas y macros\Bashkar Station\kraken_env\Lib\site-packages\torch\include\ATen\ops\...`
superaba ese límite durante la instalación. pip fallaba con `OSError: [Errno 2] No such file or directory`.

**Solución:** Mover el venv a `D:\kraken_env` (ruta corta).

**Cambios:**
- `core/ocr_kraken.py` — `_KRAKEN_VENV` ahora apunta a `Path("D:/kraken_env")` en lugar de ruta relativa larga
- Venv eliminado de `I:\...\kraken_env\`, recreado en `D:\kraken_env`
- Kraken 7.0.2 + torch 2.10.0+cpu instalados y verificados: `import kraken; from kraken import blla` ✓

#### Tests
```
499 passed, 9 skipped in ~50s
```
(Sin regresiones — mismos 499 que sesión 12)

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `core/ocr_kraken.py` | `_KRAKEN_VENV = Path("D:/kraken_env")` — ruta corta para evitar MAX_PATH |

### Pendientes para próxima sesión
1. Descargar modelo CATMuS-Print desde UI (botón "⬇ Descargar CATMuS-Print") — Kraken ya listo
2. Probar etiquetador rediseñado con número real del corpus
3. Probar deskew con páginas BNC reales
4. Implementar diccionario de corpus para verificación OCR (ítem #2 del roadmap FineReader)

---

## Sesión 13 — 2026-05-28

### Kraken venv Python 3.12 · Etiquetador rediseñado · Preprocesamiento imagen

#### `app.py` — Mensaje amigable error Kraken
- Si `"No module named kraken"` → mensaje legible: "✗ Kraken no instalado — incompatible con torch 2.x."

#### `core/ocr_kraken.py` — Subprocess bridge Python 3.12
- `_KRAKEN_VENV` y `_KRAKEN_PYTHON` apuntan al venv dedicado
- `_python_kraken()` retorna ejecutable del venv si existe, si no `sys.executable`
- `kraken_disponible()` usa subprocess para verificar sin importar en Python 3.14
- `ocr_kraken()` reescrito como subproceso inline JSON: ejecuta script en venv, parsea JSON con texto+confianza
- `descargar_modelo_catmus()` usa `_python_kraken()` para ejecutar `kraken get` en venv correcto

#### `app.py` — Etiquetador de zonas rediseñado (bug crítico corregido)
**Causa raíz del bug:** `_etz_img_orig` ya es la imagen escalada. Multiplicar por `_etz_escala` de nuevo → doble escala → coordenadas 2× más grandes de lo que el canvas tiene → zonas "vuelan" fuera de pantalla.

**Correcciones:**
- `_etz_canvas_wh()` — retorna dimensiones de `_etz_img_orig` directamente (sin escala adicional)
- `_etz_canvas_a_norm(cx, cy)` — convierte canvas→normalizado dividiendo por `_etz_canvas_wh()`
- `_etz_zona_canvas_coords(idx)` — usa `_etz_canvas_wh()` en lugar de `_etz_escala`
- `_etz_finish_draw` — usa `_etz_canvas_a_norm()` para crear zonas normalizadas
- `_etz_drag_resize` / `_etz_drag_move` — simplificados con `_etz_canvas_a_norm()`

**Mejoras visuales:**
- Zona activa con relleno semitransparente (`stipple="gray25"`)
- Etiquetas con fondo negro y texto blanco (contraste)
- 8 handles cuadrados en esquinas y puntos medios de zona activa
- `_etz_zona_sel_idx` — estado de zona seleccionada para resaltado

#### `core/image_preprocessor.py` — Nuevo módulo (FineReader-style)
- `deskew(img, max_angle=10.0)` — corrección inclinación con Hough transform
- `despeckle(img, kernel_size=2)` — eliminación ruido con apertura morfológica
- `enhance_contrast(img, clip_limit=2.0, tile_size=8)` — mejora contraste CLAHE
- `binarize_adaptive(img, block_size=31, c=10)` — binarización adaptativa
- `preprocesar_para_ocr(img, deskew_en, despeckle_en, enhance_en)` — pipeline completo
- `detectar_angulo_pagina(img) -> float` — retorna ángulo sin corregir

#### `app.py` — Panel OCR, checkboxes preprocesamiento
- 3 nuevos checkboxes: "Corregir inclinación", "Mejorar contraste", "Eliminar ruido"
- En `_worker_ocr`: aplica preprocesamiento a imágenes extraídas si algún checkbox activo

### Archivos modificados/creados

| Archivo | Cambio |
|---|---|
| `app.py` | Mensaje amigable Kraken; etiquetador rediseñado (fix doble escala + UX); checkboxes preprocesamiento |
| `core/ocr_kraken.py` | Subprocess bridge Python 3.12; `_python_kraken()`; venv dedicado |
| `core/image_preprocessor.py` | Nuevo — deskew, CLAHE, despeckle, binarize, pipeline OCR |

---

## Sesión 12 — 2026-05-28

### Cobertura completa de tests — 7 archivos nuevos

#### `core/pipeline_maestro.py`
- `import re` movido al bloque de imports del módulo (era lazy al final del archivo)

#### Tests nuevos

| Archivo | Tests | Cubre |
|---|---|---|
| `tests/test_confianza_engine.py` | 52 | nivel_confianza, color_semaforo, score_ocr, score_ner_entidad, EntidadValidacion, ColaPendiente, confianza_global_corpus |
| `tests/test_tei_engine.py` | 25 | articulo_a_tei, exportar_corpus_tei, exportar_bibtex |
| `tests/test_pipeline_maestro.py` | 29 | constructor, _ner_dict_a_lista, _stats_corpus, _construir_indice_global, _generar_leame, _guardar_bashkar, ejecutar_en_hilo |
| `tests/test_network_engine.py` | 22 | construir_grafo, metricas_red, grafo_a_dict/dict_a_grafo roundtrip |
| `tests/test_comparative_analyzer.py` | 35 | _tokenizar, perfil_tfidf, palabras_distintivas, similaridad_coseno_tfidf, comparar_campos_semanticos, cargar_corpora |
| `tests/test_alto_reconstructor.py` | 44 | _es_fuente_ocr_basura, _agrupar_en_lineas, _detectar_columnas, _linea_a_texto, reconstruir_texto_pagina, extraer_titulos_pagina |
| `tests/test_analysis_engine.py` | 34 | leer_numero, construir_red, run_lda, analizar_numero_texto, constantes SECCIONES/CAMPOS_SEM |

**Fixes en tests:**
- `test_network_engine.py`: `networkx.node_link_data()` retorna `"nodes"/"links"`, no `"nodos"/"aristas"` → aserciones actualizadas para aceptar ambos formatos
- `test_analysis_engine.py`: LDA requería mín. 2 documentos por término (min_df=2); fixture corregida con 10 docs en 4 grupos temáticos

```
499 passed, 9 skipped in ~88s
```
9 skipped = 4 red Wikidata + 1 Kraken sin modelo + 4 comparative_analyzer (corpus único sin IDF)

---

## Sesión 9 — 2026-05-27

### OCR Kraken + Ollama en UI · Tests ocr_normalizer y ocr_kraken

#### `app.py` — Rutas OCR 4 y 5 completas

**Handlers implementados** (métodos nuevos):
- `_ocr_verificar_kraken()` — detecta si Kraken + modelo están disponibles; actualiza `_lbl_kraken_ok`; rellena `_var_kraken_modelo` con el modelo encontrado
- `_ocr_elegir_modelo_kraken()` — diálogo de archivo para `.mlmodel`; actualiza label tras seleccionar
- `_ocr_descargar_catmus()` — ejecuta `descargar_modelo_catmus()` en thread; muestra progreso en label; maneja errores
- `_ocr_detectar_ollama()` — llama `listar_modelos_vision()` en thread; puebla combobox `_cmb_ollama`; informa si no hay modelos

**`_worker_ocr` actualizado:**
- `RUTA_LABELS` extendido: `"kraken"` → Ruta 4 · Kraken CATMuS-Print, `"ollama"` → Ruta 5 · Ollama Vision
- Detección de modo: `"kraken"` y `"ollama"` fuerzan modo `"escaneado"` (como tesseract/claude)
- Ruta 4 (`kraken`): llama `ocr_kraken_lote()` por archivo; fallback a Tesseract por página si falla; `metodo = "kraken"`
- Ruta 5 (`ollama`): llama `ocr_ollama_lote()` por archivo; fallback a Tesseract si falla; `metodo = "ollama"`

#### `tests/test_ocr_normalizer.py` — Nuevo, 40 tests

Cubre: `normalizar_texto_ocr` (vacío, BOM, s-larga, ligaduras, espacios, CR), correcciones de vocabulario colombiano (Bogotá, Medellín, Digitalizado BNC), `_unir_palabras_partidas` (une/no-une según contexto), `reconstruir_lineas_rotas`, `_limpiar_espaciado`, `normalizar_archivo` (backup, stats, sin backup), opciones de normalización selectiva.

#### `tests/test_ocr_kraken.py` — Nuevo, 17 tests + 1 skip

Cubre: `kraken_disponible` (bool, false cuando no importa), `ocr_kraken` (ImportError/FileNotFoundError sin Kraken), `ocr_kraken_lote` (lista vacía, mock exitoso, error sin detener lote, callback en ok/error, estructura dict, propagación modelo_path), `descargar_modelo_catmus` (retorna si ya existe, RuntimeError si subprocess falla), `TestKrakenReal` (skip si no instalado).

### Resultado de tests

```
175 passed, 5 skipped in ~29s
```

(+57 tests respecto a sesión 8: 40 test_ocr_normalizer + 18 test_ocr_kraken − 1 skip extra Kraken real)

### Archivos modificados/creados

| Archivo | Cambio |
|---|---|
| `app.py` | 4 handlers Kraken/Ollama; _worker_ocr con rutas 4 y 5 |
| `tests/test_ocr_normalizer.py` | Nuevo — 40 tests |
| `tests/test_ocr_kraken.py` | Nuevo — 17 tests + 1 skip |

---

## Sesión 8 — 2026-05-27

### Integración UI — Repositorio SQLite + Wikidata + Búsqueda semántica

#### `core/project_manager.py` — Integración completa con SQLite

- **`nuevo_proyecto()`**: crea automáticamente la `.db` SQLite hermana al crear cualquier proyecto nuevo. La ruta se guarda en el campo `"db"` del JSON.
- **`guardar_proyecto()`**: sincroniza con SQLite al guardar — escribe artículos desde `df_articulos` y entidades desde `indice_ner_global`. Guarda `"db"` en el JSON.
- **`cargar_proyecto()`**: migración automática v10→v11 al abrir un `.bashkar` antiguo (llama a `datos.migracion.migrar()` si `necesita_migracion()` devuelve True). Conecta la instancia `Repositorio` en `ST.repo`. Retorna `migrado: True` en el resultado cuando ocurrió migración.
- **`VERSION`**: actualizado a `"11"`.

#### `app.py` — Tres mejoras de UI

**1. Estado `ST` ampliado:**
- `ST.repo` — instancia `Repositorio` (conectada al cargar proyecto)
- `ST.ruta_db` — ruta al archivo `.db`
- `ST.wikidata_enlaces` — dict `{cat: {texto: {id, label, description, url, confianza}}}`

**2. Aviso de migración automática**: cuando se abre un proyecto v10, aparece un `messagebox.showinfo` informando que fue migrado a v11 con backup conservado.

**3. Botón "🌐 Enlazar Wikidata"** en la barra de acciones del panel NER:
- Abre ventana de progreso con `ttk.Progressbar`
- Ejecuta `enlazar_indice_ner()` en thread background
- Guarda resultado en `ST.wikidata_enlaces`
- Panel de detalle (`_ner_on_select`) muestra el enlace Wikidata al seleccionar una entidad: ID, nombre canónico, descripción, URL y confianza.

**4. Pestaña "🔍 Búsqueda"** (nueva, id `bsem`) en el grupo Análisis:
- Card "Construir índice": genera embeddings de todos los artículos con `generar_embeddings()` en thread background, construye `IndiceSemantico` FAISS.
- Campo de consulta en texto libre + spinbox K + botón Buscar (también con Enter).
- Treeview con resultados: rank, ID, similitud, título.
- Botones "Guardar índice" / "Cargar índice" (`.faiss` + `.ids.json`).
- Log interno.

#### `tests/test_project_manager.py` — Nuevo archivo, 13 tests

Tests de: `nuevo_proyecto` (crea .bashkar + .db, no sobreescribe), `guardar_proyecto`/`cargar_proyecto` (persistencia nombre, api_keys, NER), migración automática v10→v11 al cargar.

### Resultado de tests

```
118 passed, 4 skipped in ~40s
```

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `core/project_manager.py` | Integración SQLite, migración auto, VERSION=11 |
| `app.py` | ST.repo/ruta_db/wikidata_enlaces; aviso migración; botón Wikidata; pestaña Búsqueda |
| `tests/test_project_manager.py` | Nuevo — 13 tests |

---

## Sesión 7 — 2026-05-27

### Arquitectura v11 — capa de datos + motores locales + tests completos

Esta sesión implementó la totalidad del plan v11 descrito en el documento maestro: capa de
datos SQLite, OCR local (Kraken + Ollama), NER local (BERT-Spanish), embeddings semánticos
(FAISS), exportación ALTO XML v4, entity linking a Wikidata y suite de tests completa.

#### FASE 1 — Capa de datos SQLite

- **`datos/__init__.py`** — paquete nuevo.
- **`datos/schema.py`** — DDL completo para dos esquemas:
  - `SCHEMA_PROYECTO`: tablas `articulos`, `ocr`, `entidades`, `zonas_anotacion`, `tono`, `topicos`, `coocurrencias`, `intertextualidad`, `historial_ia` con índices.
  - `SCHEMA_GLOBAL`: tablas `entidades_globales`, `correcciones_ocr`, `glosario_global`, `relaciones`, `proyectos_recientes`.
- **`datos/repositorio.py`** — clase `Repositorio` con WAL mode, `row_factory = sqlite3.Row`, context manager. Métodos completos de acceso a articulos, OCR, entidades, zonas, tono, coocurrencias, historial IA.
- **`datos/migracion.py`** — `necesita_migracion()`, `migrar()` (JSON v10 → SQLite v11), `migrar_carpeta()`. Crea backup automático antes de migrar.

#### FASE 2 — OCR local

- **`core/ocr_kraken.py`** — OCR histórico con modelo CATMuS-Print Large (Kraken). Funciones: `kraken_disponible()`, `ocr_kraken()`, `ocr_kraken_lote()`, `descargar_modelo_catmus()`.
- **`core/ocr_ollama_local.py`** — OCR visual con Ollama + Qwen2.5-VL. Prompt calibrado para prensa colombiana 1930-1940. Confianza heurística basada en proporción de caracteres ilegibles.

#### FASE 3 — NER local con BERT-Spanish

- **`core/ner_roberta_local.py`** — Motor NER con `mrm8488/bert-spanish-cased-finetuned-ner` (reemplaza PlanTL-GOB-ES que requiere autenticación HF). Ventana deslizante 450 palabras + solapamiento 50. Deduplicación por clave (texto_norm, categoría). Fusión de subwords WordPiece (##).
- **`core/ner_engine.py`** — Actualizado: `pipeline_ner()` ahora acepta `nlp=None`, prueba RoBERTa primero y cae a spaCy si no disponible.

#### FASE 4 — Embeddings semánticos + FAISS

- **`core/embeddings_local.py`** — `generar_embeddings()` con `paraphrase-multilingual-MiniLM-L12-v2` (384 dim, normalizado L2). `similitud_coseno()`. `@lru_cache` para el modelo.
- **`core/busqueda_semantica.py`** — `IndiceSemantico`: `construir()`, `buscar()` (retorna rank + similitud), `guardar()`/`cargar()` (`.faiss` + `.ids.json`).

#### FASE 5 — Exportación ALTO XML v4

- **`exportadores/exportar_alto.py`** — ALTO XML v4 (namespace `http://www.loc.gov/standards/alto/ns-v4#`). Desnormaliza coordenadas 0-1 a píxeles. TextBlock / Illustration según tipo de zona. Soporte multi-línea con WC de confianza. `exportar_corpus_alto()` para lote completo.

#### FASE 6 — Suite de tests pytest

- **`pytest.ini`** — configuración con `testpaths = tests`, `-v --tb=short`, ignora warnings de terceros.
- **`tests/conftest.py`** — fixtures compartidas: `tmp_db`, `repo`, `articulo_simple`, `articulo_segundo`, `entidades_ejemplo`, `zonas_ejemplo`, `bashkar_v10`.
- **`tests/test_repositorio.py`** — 29 tests (8 clases): articulos, OCR, entidades, zonas, tono, coocurrencias, estadísticas, historial IA.
- **`tests/test_migracion.py`** — 10 tests: necesita_migracion, migrar (backup, versión, DB, entidades).
- **`tests/test_ner_engine.py`** — 16 tests: pipeline NER, índice global, RoBERTa.
- **`tests/test_exportadores.py`** — 9 tests: ALTO XML (namespace, dimensiones, TextBlocks, coordenadas).
- **`tests/test_busqueda_semantica.py`** — 17 tests: IndiceSemantico + similitud coseno + embeddings reales. Fix: ruta ASCII para FAISS en Windows con usuario con caracteres no-ASCII.

#### FASE 7 — Entity linking a Wikidata

- **`core/entity_linker.py`** — Solo stdlib (urllib, sqlite3, json). Caché local SQLite para evitar llamadas repetidas. Puntuación por relevancia al corpus: coincidencia exacta, período 1930-1940, Colombia. `enlazar_entidad()`, `enlazar_lista_entidades()`, `enlazar_indice_ner()`. Umbral mínimo 0.5 para evitar falsos positivos.
- **`tests/test_entity_linker.py`** — 25 tests (21 pasan, 4 skipped sin red): caché, puntuación, modo offline, lista, índice.

#### FASE 8 — Instalador v11

- **`instalar.py`** — Actualizado a v11: añade torch, transformers, sentence-transformers, faiss-cpu a paquetes pip. Nuevo bloque Kraken opcional. Nuevo paso 5 de precarga de modelos HuggingFace (NER + embeddings). Verificación final ampliada con modulos v11 + modulos opcionales separados.

### Resultado de tests

```
105 passed, 4 skipped in 68.64s
```
- 105 tests pasando, 0 fallos.
- 4 tests de red (Wikidata) correctamente omitidos sin conectividad.

### `app.py`

- Añadida función `_resolver_api_key_modelo(etapa)` que centraliza la resolución de proveedor/modelo desde `ST.api_keys` + `ST.modelos_etapa` con fallback a `ST.api_key` (legado).
- Todos los sitios de llamada IA conectados a `_resolver_api_key_modelo`.

### Archivos modificados / nuevos

| Archivo | Estado |
|---|---|
| `datos/__init__.py` | Nuevo |
| `datos/schema.py` | Nuevo |
| `datos/repositorio.py` | Nuevo |
| `datos/migracion.py` | Nuevo |
| `core/ocr_kraken.py` | Nuevo |
| `core/ocr_ollama_local.py` | Nuevo |
| `core/ner_roberta_local.py` | Nuevo (modelo cambiado a mrm8488) |
| `core/ner_engine.py` | Modificado |
| `core/embeddings_local.py` | Nuevo |
| `core/busqueda_semantica.py` | Nuevo |
| `exportadores/exportar_alto.py` | Nuevo |
| `core/entity_linker.py` | Nuevo |
| `core/project_manager.py` | Modificado (persiste NER, api_keys, modelos_etapa) |
| `app.py` | Modificado (_resolver_api_key_modelo) |
| `instalar.py` | Actualizado a v11 |
| `pytest.ini` | Nuevo |
| `tests/conftest.py` | Nuevo |
| `tests/test_repositorio.py` | Nuevo |
| `tests/test_migracion.py` | Nuevo |
| `tests/test_ner_engine.py` | Nuevo |
| `tests/test_exportadores.py` | Nuevo |
| `tests/test_busqueda_semantica.py` | Nuevo |
| `tests/test_entity_linker.py` | Nuevo |

---

## Sesión 6 — 2026-05-25

### Problemas resueltos

#### Bug: .bat no hacía nada al ejecutarse
- **Causa raíz:** el .bat cerraba la ventana inmediatamente si `python app.py` fallaba, sin mostrar ningún error.
- **Solución:** se agregó `cd /d "%~dp0"` (para que funcione desde acceso directo) y un bloque de `if %errorlevel% neq 0 → pause` que muestra el error antes de cerrar.
- **Archivo:** `Ejecutar.bat`

#### Bug: gensim se intentaba instalar en cada inicio
- **Causa raíz:** `instalar.py` tenía `("gensim>=4.3", "gensim")` en la lista de paquetes a instalar, a pesar de que `requirements.txt` ya lo tenía comentado. Python 3.14 no puede compilar gensim (requiere Visual C++ Build Tools), así que fallaba silenciosamente en cada arranque.
- **Solución:** comentada la línea de gensim en `instalar.py`.
- **Archivo:** `instalar.py`

### Mejoras implementadas

#### Acceso directo en Escritorio
- Nuevo script `crear_acceso_directo.ps1` que crea `Bashkar Station.lnk` en el Escritorio del usuario.
- Se ejecuta automáticamente al final de cada sesión con cambios.
- El .lnk apunta a `Ejecutar.bat` con directorio de trabajo correcto e ícono `bashkar_station.ico`.
- **Escritorio:** `C:\Users\Lenovo\OneDrive - ucatolica.edu.co\Desktop\Bashkar Station.lnk`

#### Redimensionado y movimiento de zonas en el etiquetador
- El etiquetador ahora detecta el contexto del cursor sobre los recuadros existentes:
  - **Esquinas** (NW/NE/SW/SE): cursor diagonal → arrastra la esquina
  - **Bordes** (N/S/E/W): cursor de flecha doble → estira el lado
  - **Interior**: cursor ✛ → mueve toda la zona manteniendo tamaño
  - **Espacio vacío**: cursor + → dibuja zona nueva (comportamiento anterior)
- Nuevos métodos: `_etz_hit_handle()`, `_etz_on_motion()`, `_etz_drag_resize()`, `_etz_drag_move()`, `_etz_finish_draw()`, `_etz_zona_canvas_coords()`
- **Archivo:** `app.py` — refactor completo de `_etz_on_press/drag/release`

#### Detección automática de zonas (reemplaza "Entrenar + Aplicar plantilla")
- El panel "Entrenamiento automático" fue reemplazado por "Detección automática" con selector de modo:
  - **OpenCV (gratis, offline):** detecta foto (varianza de textura), pie de foto (franja bajo foto con texto), artículo (regiones de texto libre). ~1 seg/página.
  - **Claude Vision (preciso, usa tokens):** envía imagen a Claude API y recibe zonas en JSON. ~15-30 seg/página.
- Botón "Detectar esta página" (análisis inmediato) y "Detectar todo el número" (worker en hilo).
- Nuevo módulo: `core/zone_labeler.py` — funciones `detectar_zonas_opencv()` y `detectar_zonas_claude()`.
- **Archivos:** `app.py` (métodos `_etz_detectar_pagina`, `_etz_detectar_numero`, `_etz_get_img_path`), `core/zone_labeler.py`

#### Sección 8 de Configuración: multi-proveedor + modelo por etapa
- Reemplazó el campo único de API key por:
  - **Card "Claves API por proveedor":** campos separados para Anthropic, OpenAI, Google Gemini y Ollama. Cada uno con botón 👁 y botón ? con descripción de modelos, prefijos y costos.
  - **Card "Modelo activo por etapa":** combobox por cada etapa (OCR mejora, Detección zonas, NER, Tono, Narrativas, Asistente). Cada uno con botón ? que explica qué capacidad requiere la etapa y cuál modelo se destaca con ★/✓/✗.
- `Estado` ampliado: `ST.api_keys` (dict por proveedor) + `ST.modelos_etapa` (dict por etapa).
- `ST.api_key` (legado) se mantiene: se rellena automáticamente con la primera clave no vacía.
- **Archivo:** `app.py` — sección 8 de `_build_cfg()`, `_confirmar_cfg()`, `_sincronizar_ui_con_st()`

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `app.py` | Resize/move zonas; detección auto; sección 8 multi-proveedor; fix .bat |
| `Ejecutar.bat` | cd /d para acceso directo; pausa en error |
| `instalar.py` | Gensim comentado (no instalar en Python 3.14) |
| `crear_acceso_directo.ps1` | Nuevo — crea .lnk en Escritorio |
| `core/zone_labeler.py` | Nuevas funciones `detectar_zonas_opencv()` y `detectar_zonas_claude()` |

### Pendientes para próxima sesión

1. **Probar resize/move en el etiquetador** con el corpus real — verificar que las esquinas y bordes responden correctamente al arrastrar.
2. **Probar detección OpenCV** en páginas del corpus (requiere imágenes en `02_imagenes/`) — evaluar qué tan bien distingue foto vs. texto.
3. **Probar detección Claude Vision** en una página de prueba — verificar formato JSON de respuesta y coordenadas.
4. **Persistir `indice_ner_global` en .bashkar** — agregar a `project_manager.py` para que sobreviva entre sesiones.
5. **Hacer que `ST.api_key` use el modelo de la etapa activa** — las funciones que consumen `ST.api_key` deberían también leer `ST.modelos_etapa` para elegir el modelo correcto.
6. Eliminar `test_arranque.py` del directorio del proyecto (archivo temporal).

---

## Sesión 5 — 2026-05-24

### Problemas resueltos

#### Bug: zonas del etiquetador con tamaños incorrectos
- **Causa raíz:** `_etz_on_release` usaba las dimensiones de la imagen escalada (`_etz_img_orig.width/height`) como denominador para normalizar las coordenadas del canvas. Las coordenadas del canvas ya están en espacio escalado, así que la normalización se aplicaba dos veces, produciendo zonas ~escala² más pequeñas que las dibujadas.
- **Solución:** dividir las coordenadas del canvas por `_etz_escala` para obtener píxeles reales, luego usar `_etz_img_orig_full` (imagen original a resolución completa) como denominador de normalización.
- **Archivo:** `app.py` — `_etz_on_release()` (línea ~2628)

#### Bug: ventana negra al arrancar (NameError OSCURO)
- **Causa raíz:** 3 ocurrencias de `fg=OSCURO` en `_build_etz` al construir labels. La constante `OSCURO` no existe en este proyecto (los labels usan `"#374151"` directamente).
- **Solución:** `replace_all=True` → `fg="#374151"` en las 3 ocurrencias.
- **Archivo:** `app.py` — `_build_etz()` (líneas ~2263, ~2271, ~2284)

### Mejoras implementadas

#### UX zona labeler — feedback visual durante drag
- Etiqueta flotante mientras se arrastra: muestra tipo activo + dimensiones en porcentaje (`"Artículo  45% × 30%"`)
- La etiqueta se elimina correctamente al soltar el mouse
- **Archivo:** `app.py` — `_etz_on_drag()`, `_etz_on_release()`

#### UX zona labeler — menú contextual por click derecho
- Click derecho sobre el canvas: detecta qué zona hay bajo el cursor (en orden inverso = última dibujada tiene prioridad)
- Menú con submenú "Cambiar tipo" (los 9 tipos con colores) y "🗑 Eliminar esta zona"
- Nuevo helper `_etz_borrar_zona(idx)` que elimina por índice y redibuja
- **Archivo:** `app.py` — `_etz_on_click_derecho()`, `_etz_borrar_zona()` (~líneas 2668, 2717)

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `app.py` | Fix coordenadas `_etz_on_release`; fix `OSCURO`→`#374151`; feedback drag; menú clic derecho; helper `_etz_borrar_zona` |
| `memory/project_bashkar_history.md` | Historia completa v1→sesión 5 |
| `memory/project_bashkar_station.md` | Actualizado con cambios sesión 5 |

### Pendientes para próxima sesión

1. **Probar etiquetador corregido** con imágenes reales del corpus Estampa — dibujar zonas y verificar que los recuadros coinciden con el área marcada.
2. **Probar Ruta 1 (Tesseract propio)** con un número de Estampa — comparar calidad de texto vs. Ruta 3 (BNC) para validar hipótesis de mejora por re-OCR.
3. **Calibrar `reconstruir_lineas_rotas()`** con páginas reales (Ruta 3) — ajustar heurísticas de unión de líneas.
4. **Persistir `indice_ner_global` en .bashkar** — agregar a `project_manager.py` para que sobreviva entre sesiones.
5. Eliminar `test_arranque.py` del directorio del proyecto (archivo temporal de depuración).

---

## Sesión 4 — 2026-05-24

### Diagnóstico corpus Estampa (empírico)
- 62% de páginas con fragmentación severa: OCR BNC usa PSM incorrecto, mezcla columnas en stream lineal
- 36% de páginas mezclan artículo + publicidad en el mismo stream OCR
- El etiquetador de zonas no puede resolver mezcla de columnas (la información espacial ya no existe en el stream BNC)

### Tres rutas OCR implementadas
- **Ruta 1 — Tesseract propio** (recomendada): fuerza re-OCR desde imágenes, ignora texto BNC, PSM 3 maneja layout multi-columna correctamente
- **Ruta 2 — Claude Vision**: imagen → Claude API, comprende layout visual, requiere API key y genera costo
- **Ruta 3 — BNC + reconstrucción**: usa texto BNC existente + nueva función `reconstruir_lineas_rotas()` en el normalizador

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `app.py` | Selector de ruta OCR en pestaña Extracción con botón ? de ayuda; `_worker_ocr` respeta ruta seleccionada |
| `core/ocr_normalizer.py` | Nueva función `reconstruir_lineas_rotas()` — une líneas cortas del mismo párrafo, respeta títulos y límites reales |

---

## Sesión 3 — 2026-05-23

### Segmentador reescrito
- Estrategia anterior: detectar títulos + flujo de texto → cientos de fragmentos basura
- Estrategia nueva: página = unidad atómica → 115 unidades limpias para el corpus Estampa
- **Archivo:** `core/article_segmenter.py` — reescritura completa

### Sidebar scrollable + rediseño
- Antes: botones fijos sin scroll, se cortaban con ventanas pequeñas
- Ahora: Canvas+Scrollbar, 3 grupos (Flujo/Análisis/Exportar), botones numerados para el flujo
- **Archivo:** `app.py` — `_build_sidebar()`

### Etiquetador de zonas (nuevo)
- Nueva pestaña "✏️ Etiquetar" antes del paso OCR
- Canvas tkinter con dibujo de rectángulos, 9 tipos de zona, DetectorZonas estadístico
- **Archivos:** `core/zone_labeler.py` (nuevo), `app.py` — `_build_etz()` y métodos `_etz_*`

### CSV encoding
- `encoding="utf-8-sig"` en todos los `to_csv()` → tildes correctas al abrir en Excel

---

## Sesiones 1–2 — 2026-05-20 al 2026-05-22

### v11 — OCR LLM + NER híbrido
- `core/ocr_llm.py`: Claude Vision para páginas de baja confianza, corrección post-OCR
- `core/ner_engine.py`: pipeline spaCy + Claude, 6 categorías históricas (PER, ORG, LOC, EVT, OBR, DAT)
- Pestaña "🔍 Índice NER" con treeview, filtros, detalle y exportar CSV
- Botón "Mejorar con IA" + spinbox umbral en pestaña Extracción

### v12–v20 — Módulos analíticos (implementados)
- v12: Redes de co-ocurrencia (networkx + pyvis + Gephi)
- v13: Análisis semántico (BERTopic, sentimiento editorial, glosario, estilometría)
- v14: Visualizaciones avanzadas (nubes, heatmap, mapa folium, timeline)
- v15: Storytelling y exportación narrativa (Claude, HTML, Word)
- v16: Dashboard integrado
- v17: Comparador multi-proyecto + análisis intertextual
- v18: Semáforo de confianza + cola de revisión manual
- v19: Colaboración (parches .bashkar.patch, trazabilidad HTML)
- v20: Base de conocimiento SQLite, exportador PPTX, TEI P5, pipeline maestro

---

## Historial previo (v1–v10)

Ver `memory/project_bashkar_history.md` para historia completa desde el script original en Google Colab (2025) hasta la versión estable v10 entregada para FILBo 2026.
