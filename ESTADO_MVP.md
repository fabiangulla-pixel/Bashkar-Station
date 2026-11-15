# Estado hacia el MVP público — Bashkar Station

Diagnóstico del 14 de noviembre de 2026. Sesión de solo diagnóstico: no se modificó
código de la aplicación.

**Convención de evidencia.** Cada afirmación lleva una marca:

- **[EJECUTADO]**: lo comprobé corriéndolo en esta sesión.
- **[LEÍDO]**: lo deduzco leyendo código, documentación o historial, sin ejecutarlo.
- **[EXTERNO]**: viene de una fuente pública consultada hoy (fichas de modelos, GitHub).

Evidencia completa (registros, JSON del recorrido y scripts usados), fuera del
repositorio porque contiene rutas personales y texto del corpus:
`C:\build_rf\mvp_evidencia_2026-11-14\`.

---

## 0. Punto de partida: la versión no es la v11.9

| Dato del encargo | Lo que hay hoy |
|---|---|
| Versión madura v11.9 | **v13.1** en el código (`gui_comun.APP_VERSION`). [LEÍDO] |
| ~1.145 pruebas | **1.969 pasan, 27 saltadas, 0 fallan**. [EJECUTADO] |
| Corpus ene–jun 1939, 973 páginas | Lo versionado es **ene–may 1939: 5 números, 792 páginas** (`vision_ocr/salida/`). Junio no aparece en el repositorio. [LEÍDO] |
| Desarrollada con el Instituto Caro y Cuervo | Un documento del 14-oct (`docs/e-rihs-2026-evidence/TECHNICAL_EVIDENCE.md`) corrige el encuadre: Beca de Estímulo del Ministerio de las Culturas, con el ICyC como **institución mentora**, sin afiliación contractual vigente. [LEÍDO] |

Última versión publicada como *release* en GitHub (y con DOI en Zenodo): **v12.0**,
del 14-ago. El README, la cita BibTeX, la insignia de pruebas (dice «1410») y la
cabecera de `requirements.txt` siguen diciendo v12.0. [LEÍDO]

### Qué se estaba haciendo y qué quedó a medias [LEÍDO]

- **Último commit:** `7e6cdbd` (13-oct-2026), sesión 74: la referencia humana del
  benchmark de OCR pasa a JSON por zonas y el dictado se mueve al Etiquetador.
  Está en `origin/main`. Desde entonces, **un mes sin commits**.
- **Pendiente de la sesión 74:** probar el botón «🎙 Referencia humana» con voz
  real; seguir transcribiendo la referencia humana. Sin esa referencia, los
  umbrales del enrutador de OCR (`config/ocr.toml`) siguen siendo provisionales,
  como lo dice el propio archivo.
- **Sin commitear en `C:\dev\bashkar_station`:** la entrada de la sesión 74 en
  `CHANGELOG.md` y la carpeta `docs/e-rihs-2026-evidence/` (paquete E-RIHS del
  14-oct, con una página real de Estampa en PDF).
- **La copia de Drive (`G:\…\bashkar_station`) está 4 commits atrás** de
  `origin/main`, con `paneles/resultados.py` modificado y
  `vision_ocr/muestras_corpus/` sin versionar. Es la misma situación de dos copias
  que en septiembre dejó trabajo huérfano.
- **Ramas:** `agent/desktop-ui-redesign` y `claude/bashkar-station-8qhcvs` ya
  están fusionadas (0 commits por delante). Local: `respaldo-sesion69-sin-integrar`.
- **Issues y pull requests abiertos en GitHub:** ninguno. [EJECUTADO, `gh`]
- **Actividad de los últimos 4 meses:** 147 commits (jul 5, ago 69, sep 59, oct 14).

---

## 1. Inventario

### Arquitectura real [LEÍDO, cifras medidas con `wc`]

| Pieza | Tamaño | Papel |
|---|---|---|
| `app.py` + `paneles/` (9 mixins) + `gui_comun.py` | 6.581 + 15.746 + 127 líneas | Escritorio Tkinter; 31 paneles |
| `core/` (105 módulos) + `core/ocr/` (enrutador, motores, trabajadores Surya/Paddle) | ~36.000 líneas | Toda la lógica |
| `datos/` | 1.612 líneas | SQLite: artículos, OCR, normalizaciones con historial, entidades, grafo (`entidades_canonicas`, `relaciones`) |
| `cli.py` | 462 líneas | Pipeline sin interfaz; **no crea proyectos**, exige un `.bashkar` existente |
| `api/app.py` (FastAPI) | 962 líneas | API «nube»: 46 rutas, paridad 25/25 operaciones con el escritorio |
| `servidor_web.py` + `web/` (stdlib + JS vanilla) | 1.114 + 565 líneas | **Segundo** backend web, con interfaz parcial (unos 8 de 31 paneles) |
| `tests/` | 112 archivos, 20.531 líneas | |

Formato de proyecto: `.bashkar` (JSON) + `.db` (SQLite) hermano, en
`~/Documents/BashkarStation/proyectos/`. Claves de API en
`~/.bashkar/credenciales.json`, nunca en el proyecto. La IA en la nube arranca
apagada (`ia_habilitada = False`).

Ojo: hay **dos backends web distintos** (`servidor_web.py` y `api/app.py`) con
contratos diferentes. Cualquier opción web obliga a elegir uno.

### Dependencias [LEÍDO + EJECUTADO]

- Python: el *lock* y la CI usan **3.12.10**; el README pide «3.10 o superior».
  Probé con 3.14.7 (el `python` por defecto de esta máquina): instala, pero Kraken
  falla y las versiones no coinciden con el *lock* (torch 2.15 frente a 2.14,
  transformers 5.23 frente a 5.16), porque `instalar.py` no fija versiones.
- Binarios externos: Tesseract ≥ 5 con español y Poppler.
- Pila pesada: torch, transformers, sentence-transformers, faiss, spaCy.

### Modelos que se descargan [EJECUTADO: tamaños en caché]

| Modelo | Tamaño | Uso | ¿Lo instala el README? |
|---|---|---|---|
| `mrm8488/bert-spanish-cased-finetuned-ner` | 839 MB | NER | Sí |
| `paraphrase-multilingual-MiniLM-L12-v2` | 458 MB | Embeddings y búsqueda | Sí |
| `es_core_news_sm` (spaCy) | ~15 MB | NER y sintaxis | Sí |
| `stanford-oval/churro-3B` | **7,1 GB** | OCR Ruta 6 (estándar de oro) | No; se descarga al usarlo; además falta `accelerate` |
| PERO-OCR | paquete + motor aparte | OCR Ruta 7 | No. **No está instalado en ningún entorno de esta máquina ni hay motor descargado**: no se ha ejecutado aquí |
| Surya / PP-Structure (enrutador v13) | ~2 GB / ~1 GB | OCR primario en GPU | No; venvs aparte (`INSTALACION.md`) |

Instalación limpia según el README: **8 min 10 s**, entorno virtual de 1,9 GB y
1,3 GB de modelos (sin CHURRO ni motores GPU). [EJECUTADO]

### Claves de API [LEÍDO]

Opcionales: Anthropic, OpenAI y Gemini (Ollama y LM Studio son locales). Ninguna
hace falta para el flujo principal, que corrió entero sin claves. [EJECUTADO]

### Hardware

- **Medido** [EJECUTADO]: este portátil (RTX 5080 Laptop, 16 GB de VRAM). El flujo
  de 6 páginas tarda ~90 s en CPU (instalación limpia, torch solo CPU) y ~80 s con GPU.
- **Inferido** [LEÍDO]: mínimo razonable sin GPU: Windows 10/11 de 64 bits, 8 GB de
  RAM (Kraken real pide ~5,5 GB) y ~6 GB de disco. CHURRO necesita en la práctica
  una GPU NVIDIA con ≥ 8 GB de VRAM (7,8 GB medidos en la sesión 72); en CPU, la
  documentación habla de ~34 min por página. No probé un equipo modesto.

---

## 2. Qué funciona hoy (comprobado ejecutando)

1. **Suite completa:** 1.969 pasan, 27 saltadas, 0 fallan, en 4 min 47 s (venv de
   desarrollo, Python 3.12.10). Las 27 saltadas tienen motivo explícito: sin red a
   Wikidata (6), pruebas del asistente gráfico desactivadas por el límite de raíces
   de Tk (6), un *crash* nativo conocido de faiss+torch en esta máquina (5),
   TF-IDF vacío (4), Kraken (4), PERO-OCR no instalado (2).
2. **Instalación siguiendo solo el README** (`python instalar.py` en un clon nuevo
   de GitHub, con un venv limpio): termina con «Todo listo. Ejecuta: python app.py».
3. **Recorrido principal con la GUI real**, sin clics de pantalla (se invocan los
   mismos métodos que los botones, dentro de `mainloop()`, con un perfil de usuario
   aislado), sobre 6 páginas de *Estampa* de abril de 1939. Mismo resultado en el
   entorno de desarrollo y en el limpio:

   | Paso | Resultado |
   |---|---|
   | Arranque | 6–9 s; los 31 paneles se construyen sin error |
   | Crear proyecto | OK (diálogo real, botón real) |
   | Cargar PDF y confirmar configuración | OK |
   | OCR | 6 páginas, 4.175 palabras, 64–73 s |
   | Segmentar | 5 artículos |
   | NER | 161 entidades (90 personas, 46 lugares, 23 organizaciones, 2 fechas), 3–5 s |
   | Exportar TEI P5 | Archivo de 36 KB que pasa `validar_tei()` sin errores (pero vea §3) |
   | Guardar y reabrir `.bashkar` | Páginas, textos, estado y NER se recuperan iguales |
   | Grafo de conocimiento | Funciona **solo después de cerrar y reabrir** el proyecto (vea §3) |

4. **Servidores:** `servidor_web.py` responde y `/api/capacidades` lista lo
   disponible; `python -m api` levanta FastAPI con `/docs` y 46 rutas.
5. **CI en cada push:** verde (último, 14-oct). [EJECUTADO, `gh run list`]

---

## 3. Qué está roto o incompleto, con evidencia

### Fallos de datos (afectan resultados de investigación)

**F1. Al guardar, SQLite conserva una sola entidad por artículo.** [EJECUTADO + LEÍDO]
`core/project_manager.py:330-337` llama a `repo.guardar_entidades(aid, [una])` una
vez **por cada entidad**, y `guardar_entidades` (`datos/repositorio.py:193-199`)
empieza con `DELETE FROM entidades WHERE articulo_id = ?`. Cada llamada borra la
anterior. Evidencia: 161 entidades en memoria → 5 filas en la tabla `entidades`
(IDs 92, 163, 166, 167, 169, sobrevivientes de borrados sucesivos). El grafo
canónico se construyó sobre **5 de 161** entidades. El índice del `.bashkar`
(JSON) sí se conserva, por eso el panel NER se ve bien y el fallo pasa inadvertido.
Afecta a todo lo que lee `entidades` en SQLite: grafo canónico, tripletas y
exportación OKF.

**F2. El TEI exportado no contiene ninguna entidad.** [EJECUTADO + LEÍDO]
`core/servicios_exportacion.py:71-80` busca las entidades por los ID `art_0000…`,
pero el NER las indexa por el **título del artículo** («LO QUE HA PASADO»…). Nunca
coinciden: 0 `persName`, 0 `placeName`, 0 `orgName` y ningún `standOff`, aunque el
README promete «entidades en `<standOff>`». Y `validar_tei()` no lo detecta.

**F3. La cabecera del TEI trae datos fijos que pueden ser falsos.** [EJECUTADO]
Para el proyecto «E2E Estampa abr 1939», la cabecera dice título «Corpus Estampa»,
editor «Instituto Caro y Cuervo», fuente «Revista Estampa 1930-1940» y que las
entidades se identificaron «mediante NER híbrido (spaCy + Claude)» y con
«corrección asistida por IA», cuando no se usó IA. Para otro corpus, o con el
encuadre institucional corregido el 14-oct, esto es proveniencia falsa.
(`core/tei_engine.py:89, 182-184, 257, 299`)

### Fallos de flujo

**F4. El grafo canónico no se puede usar en un proyecto recién creado.**
[EJECUTADO + LEÍDO] `guardar_proyecto()` nunca asigna `ST.ruta_db`; solo lo hace
`cargar_proyecto()`. Aunque el usuario guarde, el panel responde «Abre o guarda un
proyecto con base de datos» hasta que cierra y reabre. Además, toda la
sincronización con SQLite al guardar está envuelta en `except Exception: pass`
(`core/project_manager.py:340`): si falla, no queda rastro.

**F5. La app crea proyectos vacíos sola.** [LEÍDO + EJECUTADO, lectura de disco]
`_crear_proyecto_automatico()` genera «Proyecto <fecha>» cuando no hay uno previo.
En esta máquina hay seis «Proyecto 11 Nov 2026» vacíos creados el mismo día.

### Instalación (README insuficiente para un usuario nuevo) [EJECUTADO]

**F6.** El README no dice cómo obtener el código (clonar o descargar), ni que hay
que crear un entorno virtual, ni qué versión exacta de Python usar (pide «3.10 o
superior», pero la CI y el *lock* son 3.12; con 3.14 Kraken no instala).

**F7.** `instalar.py` instala una lista propia, distinta de `requirements.txt`.
Tras seguir el README faltan: `anthropic` y `google-generativeai` (toda la IA en la
nube), `accelerate` (CHURRO), `wordcloud` (nube de palabras), `python-louvain`
(comunidades de la red), `spylls` (corrección ortográfica: queda «inactiva» con
solo un aviso ℹ️) y `fastapi`/`uvicorn`. No fija versiones.

**F8.** `instalar.py` termina con `EOFError` (código de salida 1) en el
`input("Presiona ENTER…")` final cuando no hay consola interactiva. No pasa al
abrirlo con doble clic, pero rompe la automatización.

**F9.** El asistente gráfico (`setup_wizard.py`, el «Paso 1» del README) no lo pude
probar: es una ventana que exige clics, y sus pruebas automáticas están apagadas
por defecto (6 saltadas).

### Integración continua [EJECUTADO, `gh run view`]

**F10.** Las corridas **semanales** fallan desde el 12-oct, aunque las de cada push
pasan:
- *Gitleaks* sobre el historial completo marca 2 falsos positivos en la librería
  incluida `vis-network.min.js` (`lib/` y `core/lib/`).
- Desde el 19-oct la instalación del *lock* en el runner de Windows falla por un
  conflicto con un `pipx` preinstalado en la imagen de GitHub (`filelock`). Es
  deriva del runner, no un fallo de la app.

### Menores

- `python -m api --port 8432` ignora el puerto y escucha en 8422. [EJECUTADO]
- Tres mensajes con voseo («Usá primero el Conversor…») en
  `paneles/analisis.py:491, 614, 668`. [LEÍDO]
- `CLAUDE.md` dice que `app.py` tiene 21.459 líneas (hoy 6.581);
  `docs/PROJECT_STATE.md` y `docs/NEXT_STEPS.md` son del 9-sep. [LEÍDO]
- NER con RoBERTa: `obras_publicaciones` y `eventos_historicos` siempre quedan en 0
  (el modelo solo tiene PER/LOC/ORG/MISC). Limitación ya conocida, pero la
  interfaz las muestra como si fueran categorías activas. [EJECUTADO]
- PERO-OCR (Ruta 7) nunca se ha ejecutado en esta máquina. [EJECUTADO]

### Lo que no pude verificar

- Dictado por voz (requiere micrófono y Google Speech).
- Asistente gráfico de instalación (F9).
- El `.exe` v13.1 (3,6 GB) en un equipo ajeno: no hay segundo equipo.
- OCR con CHURRO, Surya y Paddle en este recorrido: el enrutador usó Tesseract
  porque en el entorno limpio no están instalados.
- Un corpus completo: el recorrido usó 6 páginas.

---

## 4. Tres opciones de MVP público

Supuestos: una sola persona mantiene el proyecto con ayuda de IA, y «MVP» significa
que un investigador externo logra un resultado útil sin ayuda. Las estimaciones son
de días-persona de trabajo efectivo y son **inferencias**, no mediciones.

### (a) Instalable para Windows con asistente de instalación

Un `.exe` solo CPU (sin CHURRO ni motores GPU) dentro de un instalador (Inno Setup
o similar) que coloque Tesseract y Poppler y descargue los modelos en el primer
arranque.

- **Esfuerzo:** 15–25 días. Ya existen `bashkar_station.spec`, el diagnóstico
  `--diagnostico` y un historial de `.exe` compilados hasta la v13.1; falta el instalador, una versión CPU
  más liviana, la descarga de modelos con progreso, pruebas en 2–3 equipos ajenos
  y corregir F1–F5.
- **Costo:** certificado de firma de código ~USD 200–500 al año (sin él, Windows
  SmartScreen advierte que la app es peligrosa). Hospedaje gratis en GitHub
  Releases (límite de 2 GB por archivo).
- **Riesgos:** falsos positivos de antivirus con PyInstaller (en este PC ya hay
  Norton interceptando cosas); tamaño (1–1,5 GB sin CUDA); soporte equipo por
  equipo; distribuir binarios GPL (Poppler, el modelo spaCy) obliga a cumplir esa
  licencia; solo Windows.

### (b) Aplicación web

Un servidor con la API FastAPI y una interfaz web completa, con cuentas de
usuario y carga de archivos.

- **Esfuerzo:** 40–80 días. La lógica ya está en `core/` y la API declara paridad,
  pero la interfaz web cubre ~8 de 31 paneles y está montada sobre el otro backend
  (`servidor_web.py`). Faltan autenticación real, almacenamiento por usuario,
  colas para OCR largo, límites de carga, copias de seguridad y operación.
- **Costo:** con torch, el plan `starter` de Render (512 MB, el de `render.yaml`)
  no alcanza [inferencia]. Un servidor con 4–8 GB de RAM sin GPU cuesta
  ~USD 25–90 al mes; con GPU para OCR serio, cientos de dólares al mes.
- **Riesgos:** contradice el principio «el corpus no sale del equipo» del propio
  README. Los usuarios subirían material de la BNC a un servidor suyo, lo que
  plantea derechos y responsabilidad. Habría que custodiar claves de API ajenas.
  Es operación continua para una sola persona.

### (c) Demo pública de solo lectura con *Estampa* 1939 + instalable para usuarios avanzados

Un sitio estático con los resultados ya calculados del corpus (artículos,
entidades, red, línea de tiempo, mapa, descargas TEI/CSV/BibTeX) y, para quien
quiera procesar su propio corpus, instalación desde el código con instrucciones
corregidas y versiones fijas.

- **Esfuerzo:** 15–22 días: corregir F1–F4 (2–3), reprocesar el corpus (1–2),
  generar el sitio estático (6–9), arreglar el README y el instalador (2–3),
  licencias y avisos (1–2), *release* v13.x con DOI nuevo (1).
- **Costo:** ~USD 0 (GitHub Pages o Zenodo); dominio propio opcional.
- **Riesgos:** depende por completo de la decisión sobre derechos del texto y de
  las imágenes de *Estampa* (§6). Si la respuesta es «no se puede mostrar el
  texto», la demo se reduce a datos derivados (entidades, estadísticas, red) con
  enlaces al visor de la BNC, que sigue siendo útil. El instalable avanzado sigue
  exigiendo saber usar la terminal.

### Recomendación: (c)

Es la única que pone algo en manos de un investigador externo en semanas y sin
costo recurrente, y muestra el valor del proyecto (lectura distante de un corpus
real) sin pedirle instalar 3 GB. Es coherente con el principio *offline-first*:
el procesamiento sigue en la máquina de cada quien. Además prepara el terreno
para (a): el instalador se puede construir después sobre las mismas
correcciones. Antes de hacer cualquier cosa pública hay que resolver F1–F3,
porque la demo mostraría justo el grafo y el TEI que hoy salen mal.

---

## 5. Brecha hacia el MVP recomendado (c)

### Bloqueante

| # | Tarea | Esfuerzo |
|---|---|---|
| B1 | Decidir sobre los derechos del texto y las imágenes de *Estampa* (§6) y, según la respuesta, retirar la *pre-release* pública `vision-ocr-entrada-v1` | Decisión suya + 1 h |
| B2 | Corregir F1 (entidades en SQLite) con prueba de regresión que guarde varias entidades por artículo | 0,5 día |
| B3 | Corregir F2 (TEI sin entidades) y hacer que `validar_tei()` avise cuando hay NER pero el TEI no trae entidades | 1 día |
| B4 | Corregir F3: cabecera TEI desde los datos del proyecto; declarar IA solo si se usó | 0,5–1 día |
| B5 | Corregir F4 (`ruta_db` al guardar) y registrar los errores de sincronización en vez de tragarlos | 0,5 día |
| B6 | Reprocesar el corpus completo con la versión corregida. ¿Dónde está hoy el proyecto real de 792 páginas? (§7) | 1–2 días |
| B7 | Construir el sitio estático de la demo | 6–9 días |
| B8 | README de instalación avanzada: clonar, venv, Python 3.12 exacto, `pip install -r requirements.lock.txt`; alinear `instalar.py` con `requirements.txt` (F6–F8) | 2–3 días |
| B9 | Avisos de licencia de terceros (modelos y binarios) y CHURRO marcado como «solo investigación» | 1 día |
| B10 | Coherencia de versión: README, CITATION, `.zenodo.json`, *release* v13.x y DOI | 0,5–1 día |

Total bloqueante: ~14–20 días más su decisión sobre derechos.

### Importante

| Tarea | Esfuerzo |
|---|---|
| Prueba con 1–2 investigadores externos, sin ayuda, con registro de dónde se traban | 1 semana de calendario, 2 días suyos |
| Reparar la CI semanal (excepción de gitleaks para `vis-network`; instalación del *lock* en el runner) | 0,5 día |
| Dejar una sola copia de trabajo (C:\dev) y decidir sobre los cambios sin commitear (CHANGELOG s.74, paquete E-RIHS) | 0,5 día |
| F5: no crear proyectos vacíos automáticamente | 0,5 día |
| Guía rápida de una página («de un PDF a un TEI en 10 minutos») y regenerar el manual de 42 páginas | 1–2 días |
| Referencia humana del benchmark, para poder afirmar en público la calidad del OCR con CER medido | Semanas de su tiempo |
| Ocultar o rotular las categorías NER que el modelo no produce | 0,5 día |
| Elegir un solo backend web (`api/` o `servidor_web.py`) y congelar el otro | Decisión + 1 día |

### Puede esperar

- Verificar PERO-OCR de punta a punta (nunca ejecutado aquí).
- Kraken y soporte formal de Python 3.14.
- Instalador de Windows con asistente (opción a), después de la demo.
- El `--port` de la API, el voseo y el aviso de `fitz` obsoleto.
- Acciones de GitHub en Node 20 (obsoleto).
- Actualizar `CLAUDE.md` y `docs/PROJECT_STATE.md`.

---

## 6. Riesgos de lanzamiento

### Claves expuestas [EJECUTADO]

- Busqué en las 166 confirmaciones de todas las ramas patrones de claves de
  Anthropic, OpenAI, Google, GitHub, Hugging Face, AWS y claves privadas: **ninguna
  real**. Solo aparece `sk-ant-SECRETO-LEGADO`, un valor ficticio de prueba.
- Gitleaks (CI) solo marca los 2 falsos positivos de `vis-network.min.js`.
- Las claves del usuario viven en `~/.bashkar/credenciales.json`, fuera del
  proyecto y del repositorio. [LEÍDO]

### Costos de API para el usuario [LEÍDO + EJECUTADO]

- El flujo principal corre sin ninguna clave (comprobado).
- La IA en la nube está apagada por defecto; cuando se activa, la app estima el
  costo antes de ejecutar y registra el gasto real. El usuario pone su propia
  clave y paga su propio consumo: en la demo (c) nadie gasta nada.
- Riesgo residual: el OCR con Claude Vision sobre un corpus entero puede costar
  decenas de dólares. Conviene un tope configurable y visible.

### Licencias de modelos y dependencias [EXTERNO, consultado hoy]

| Componente | Licencia declarada | Implicación |
|---|---|---|
| Código de Bashkar | Apache-2.0 | Sin problema |
| **CHURRO-3B** | **`qwen-research`** (derivado de Qwen2.5-VL-3B) | Por su nombre, licencia de investigación, probablemente no comercial. **Verifique el texto completo** antes de redistribuirlo o de usarlo en un servicio; no empaquetarlo |
| PERO-OCR | Código BSD-3-Clause; **los motores entrenados no declaran licencia** | Preguntar a los autores antes de redistribuir un motor |
| `es_core_news_sm` (spaCy) | **GPL-3.0** | Si se empaqueta en un instalador, ese componente arrastra obligaciones GPL (ofrecer su fuente, avisar) |
| Poppler (binarios) | GPL [conocimiento general, no verificado hoy] | Igual que el anterior si se incluye en el instalador |
| `mrm8488/bert-spanish-cased-finetuned-ner` | **No declara licencia** | Riesgo legal difuso; buscar una alternativa con licencia o pedir permiso |
| `pysentimiento/robertuito-sentiment-analysis` | No declara licencia; entrenado con TASS 2020 | Datos TASS de uso para investigación [inferencia]; no usarlo en un servicio comercial sin revisar |
| `paraphrase-multilingual-MiniLM-L12-v2` | Apache-2.0 | Sin problema |
| Surya, PaddleOCR (motores v13) | No verificado hoy | Revisar antes de empaquetarlos |

### Derechos sobre las imágenes de *Estampa* y la BNC [EJECUTADO + LEÍDO]

Es el riesgo principal. Hoy, en el repositorio **público**:

1. **Una *pre-release* pública, `vision-ocr-entrada-v1`, con las 792 páginas de
   *Estampa* en 5 ZIP (~293 MB)**, descargables por cualquiera. Tienen 4–5
   descargas cada una, probablemente del propio flujo de Actions.
2. **792 transcripciones OCR completas** de *Estampa* versionadas en
   `vision_ocr/salida/`, además de textos en `benchmark/` y en los candidatos del
   piloto.
3. **47 imágenes de páginas** en el historial de git (añadidas el 27-ago, retiradas
   del árbol el 29-sep, pero recuperables desde los commits anteriores).
4. Contradicción: el TEI exportado declara `availability status="restricted"`
   («para uso exclusivo de investigación académica») mientras el texto fuente es
   público en GitHub.
5. El depósito de Zenodo de la v12.0 **no** contiene material del corpus.

Sobre el fondo jurídico (es hipótesis, no asesoría legal): en Colombia las obras
de personas jurídicas o colectivas tienen 70 años de protección desde la
publicación, lo que dejaría en dominio público lo editorial de 1939, pero las
colaboraciones firmadas por autores muertos después de 1945 (Germán Arciniegas
murió en 1999) y las fotografías con autor identificable podrían seguir
protegidas. Aparte del derecho de autor están las **condiciones de uso de la BNC**
sobre sus digitalizaciones, que no consulté. Necesita una respuesta de la BNC o de
alguien con criterio jurídico antes de publicar texto o imágenes.

---

## 7. Preguntas que necesito que responda

1. **Derechos.** ¿Tiene autorización escrita de la BNC (o de quien corresponda)
   para redistribuir imágenes y texto OCR de *Estampa*? Mientras no la tenga, ¿doy
   por hecho que hay que retirar la *pre-release* pública de 792 páginas y que la
   demo solo muestra datos derivados más enlaces a la BNC?
2. **Historial.** ¿Reescribimos el historial de git para quitar las 47 imágenes y
   las 792 transcripciones? Rompe los hashes y los enlaces a commits; el DOI de la
   v12.0 no se ve afectado.
3. **Corpus.** ¿El corpus del MVP es ene–may 1939 (792 páginas, lo que está en el
   repositorio) o ene–jun (973)? Si incluye junio, ¿dónde está ese número? ¿Y dónde
   está hoy el proyecto procesado completo (la memoria lo ubica en el Lenovo)?
4. **Encuadre institucional.** ¿Cómo debe figurar el Instituto Caro y Cuervo en el
   producto público (mentor de la beca, sin afiliación)? Hoy el TEI lo pone como
   editor de todo lo que se exporta.
5. **Opción.** ¿Acepta la recomendación (c), o hay un compromiso (beca, E-RIHS,
   convocatoria) que exija un instalable (a) o una web (b) con fecha?
6. **Público objetivo.** ¿El investigador externo típico tiene Windows y equipo
   sin GPU? Eso decide si CHURRO y los motores GPU quedan fuera del MVP.
7. **Licencias de modelos.** ¿Le parece bien sustituir o advertir los modelos sin
   licencia declarada (BERT NER de mrm8488, robertuito) y no distribuir CHURRO?
8. **Copias de trabajo.** ¿Puedo tratar `C:\dev\bashkar_station` como la única
   copia y archivar la de Drive? ¿Se commitean la entrada de la sesión 74 del
   CHANGELOG y el paquete E-RIHS (que trae una página real de *Estampa* en PDF)?
9. **Plazo.** ¿Hay una fecha objetivo para el lanzamiento?
