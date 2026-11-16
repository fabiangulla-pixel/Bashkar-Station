# ⬡ Bashkar Station v12.0
### Plataforma de Análisis Editorial Computacional para Publicaciones Periódicas Históricas

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21939404.svg)](https://doi.org/10.5281/zenodo.21939404)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)
[![CI](https://github.com/fabiangulla-pixel/Bashkar-Station/actions/workflows/ci.yml/badge.svg)](https://github.com/fabiangulla-pixel/Bashkar-Station/actions/workflows/ci.yml)

**▶ [Ver la demo: *Estampa*, enero–mayo de 1939](https://fabiangulla-pixel.github.io/Bashkar-Station/)** —
792 páginas con su facsímil y transcripción, 639 unidades editoriales, entidades
nombradas, grafo y descargas en TEI, sin instalar nada.

Bashkar Station es una plataforma que integra varios módulos y servicios en un solo entorno, 
donde el usuario puede acceder, configurar y ejecutar cosas sin salir de ahí. 
No es un framework, no es una biblioteca, no es un IDE, en el sentido estricto porque no se programa ahí. 
Es un sistema de consumo y orquestación. Una aplicación de escritorio **100 % offline**
para el análisis computacional de publicaciones periódicas históricas en español.
Desarrollada para investigadores en historia de la prensa, estudios editoriales y
humanidades digitales.

**Offline por defecto, no como opción escondida.** El estado de la aplicación arranca con
un interruptor global `ia_habilitada = False`: mientras no lo actives, ninguna función
llama a una API externa. Todo el recorrido está cubierto sin salir de tu máquina — OCR con
Tesseract o Kraken, modelos de spaCy locales, embeddings y búsqueda semántica con FAISS, y
modelos de lenguaje locales vía Ollama o LM Studio, sin costo por token.

Las APIs en la nube (Anthropic, OpenAI, Gemini) son **opcionales** y exigen que tú
configures una clave. Cuando las usas, la aplicación **estima el costo y te lo muestra
antes de ejecutar**, y registra el gasto real después.

Esto no es un detalle técnico: trabajar con prensa histórica implica material sujeto a las
condiciones de uso de la institución que lo digitalizó. Que el corpus no salga del equipo
salvo decisión explícita del investigador es un requisito, no una comodidad.

**Corpus de referencia:** revista *Estampa* (Bogotá), enero–mayo de 1939: 5
números, 792 páginas y 639 unidades editoriales, digitalizados por la
Biblioteca Nacional de Colombia (BNC).

> **Las imágenes y los textos de *Estampa* se publican con autorización de la
> Biblioteca Nacional de Colombia.** Procedencia, fuente de cada número y
> condiciones: [DERECHOS.md](DERECHOS.md).

**Financiación y mentoría:** Beca a Nuevos Investigadores en Estudios
Editoriales del Ministerio de las Culturas, las Artes y los Saberes de
Colombia. El Instituto Caro y Cuervo fue la institución mentora de la beca;
Bashkar Station no es propiedad del Instituto y su autor no tiene afiliación
con él.

---

## Características principales

| Módulo | Función |
|--------|---------|
| **OCR multi-ruta** | Tesseract, Kraken CATMuS, Claude Vision, Ollama local |
| **Normalización** | Post-OCR conservadora: preserva arcaísmos del español histórico |
| **Segmentación** | Artículo como unidad atómica; señales de continuación explícitas |
| **NER híbrido** | spaCy + BERT (mrm8488) + Claude API; 6 categorías históricas |
| **Análisis léxico** | Collocates (PMI), KWIC, n-gramas, dispersión, frecuencia relativa |
| **Stopwords proyecto** | Lista personalizable por investigador/corpus |
| **Topic modeling** | LDA con scikit-learn; BERTopic opcional |
| **Redes** | Co-ocurrencia de entidades (networkx + pyvis) |
| **Wikidata** | Linking de entidades a base de conocimiento global (LOD) |
| **Bitácora** | Notas situadas, hipótesis con estado, citas del corpus |
| **Timeline** | HTML interactivo con vis.js, por sección/tono/autor |
| **Export TEI P5** | XML-TEI válido con entidades en `<standOff>` |
| **Export BibTeX** | Referencias bibliográficas para gestores de citas |
| **METHODS.md** | Sección de metodología automática para papers |
| **Paquete publicación** | ZIP con TEI + BibTeX + CSV + Bitácora + Métodos |
| **CLI** | Pipeline completo sin interfaz gráfica |
| **HTR dataset** | Export de ground truth para reentrenamiento Kraken |

---

## Instalación

Para usuarios con algo de práctica en la terminal. La instalación por defecto
funciona **solo con CPU**: no hace falta tarjeta gráfica. Los motores con GPU y
CHURRO-3B son complementos opcionales ([INSTALACION.md](INSTALACION.md)).
Guía para macOS y Linux: también en [INSTALACION.md](INSTALACION.md).

### Lo que necesitas (Windows)

- Windows 10 u 11 de 64 bits, 8 GB de RAM y unos 6 GB libres en disco.
- Conexión a internet durante la instalación (después funciona sin ella).
- **Python 3.12** exactamente. Las versiones de todas las dependencias están
  fijadas y probadas con 3.12; con otra versión algunas no instalan (con 3.14,
  por ejemplo, Kraken falla). Descárgalo de
  [python.org](https://www.python.org/downloads/) y marca «Add python.exe to
  PATH» al instalarlo.
- **Tesseract OCR** con el idioma español: instalador de
  [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki); en el paso
  «Additional language data» marca *Spanish*.

### Paso 1 — Descargar el código

Desde la [página del proyecto](https://github.com/fabiangulla-pixel/Bashkar-Station):
botón **Code → Download ZIP** y descomprime la carpeta; o, con git:

```bat
git clone https://github.com/fabiangulla-pixel/Bashkar-Station.git
cd Bashkar-Station
```

### Paso 2 — Crear un entorno virtual con Python 3.12

Dentro de la carpeta del proyecto, en la terminal (`cmd`):

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
```

El entorno virtual aísla las dependencias de Bashkar del resto del equipo. Hay
que activarlo (segunda línea) cada vez que abras una terminal nueva.

### Paso 3 — Instalar

```bat
python instalar.py
```

Instala las **versiones exactas** de `requirements.lock.txt` (PyTorch solo
CPU), el modelo de español de spaCy, el diccionario del corrector, descarga
Poppler y los modelos de NER y búsqueda semántica (~1,3 GB). Tarda entre 10 y
20 minutos. Al final muestra una verificación: todo lo requerido debe salir
con ✅.

¿Prefieres una ventana? `python setup_wizard.py` revisa lo mismo y te deja
instalar componente por componente.

### Paso 4 — Abrir la aplicación

```bat
python app.py
```

O doble clic en `Ejecutar.bat`. Para comprobar que todo funciona sin abrir la
interfaz: `python app.py --diagnostico informe.json`.

### Línea de comandos (sin GUI)
```bash
python cli.py --proyecto ruta/a/proyecto.bashkar --etapas ocr,norm,seg,anal,ner
python cli.py --proyecto ruta/a/proyecto.bashkar --info
```

---

## Guía de inicio rápido

### Flujo típico de análisis

```
1. Configuración ──→ Define la publicación, carpetas, parámetros OCR
2. Extracción    ──→ OCR del corpus (Tesseract recomendado, PSM 3)
3. Normalizar    ──→ Revisar y corregir texto página por página
4. Segmentar     ──→ Detectar artículos, títulos y autores
5. Analizar      ──→ NER, LDA, campos semánticos, Word2Vec
6. Resultados    ──→ Exportar TEI, BibTeX, paquete de publicación
```

### Flujo alternativo (PDFs con texto embebido BNC)
```
1. Configuración ──→ Definir parámetros
2. Conversor PDF ──→ Extrae texto sin re-OCR (7 seg por número)
3. Normalizar    ──→ Revisar texto extraído
4. Segmentar     ──→ Artículos
5. Analizar / Resultados
```

### Análisis rápido sin proyecto
Haz clic en **⚡** en la barra superior para cargar una carpeta de TXT
directamente sin crear proyecto. Útil para demostraciones o análisis exploratorio.

---

## Escritorio con GPU y API para la nube (sesión 72)

Bashkar tiene dos versiones en paridad: el **escritorio** (`python app.py`),
que usa la GPU NVIDIA si la hay, y la **API** (`python -m api`, documentación
en `http://localhost:8422/docs`). Toda la lógica vive en `core/`;
`core/operaciones.py` registra qué operación del escritorio tiene ruta en la
API y `tests/test_paridad.py` lo hace cumplir.

El OCR pasa por un **enrutador** (`config/ocr.toml`) que, página por página,
usa el texto embebido si es bueno o elige motor (PP-StructureV3, Surya,
Tesseract…), pide una segunda opinión si el resultado es dudoso y marca para
revisión las discrepancias en vez de elegir en silencio. Cada página guarda
sus bloques con coordenadas (`<pagina>.bloques.json`). Instalación de la GPU
y de los motores pesados: [INSTALACION.md](INSTALACION.md#gpu-nvidia-y-motores-pesados-opcional-recomendado-si-hay-gpu).

## Versión web (segundo frontend)

Bashkar Station también puede usarse desde el navegador. No es una reescritura:
`servidor_web.py` es un segundo frontend que consume exactamente los mismos
módulos `core/` y la misma clase `Estado` (`core/estado.py`) que la app de
escritorio — ambos comparten el 100% de la lógica de negocio.

### Modo local (un solo usuario, en tu propia máquina)
```bash
python servidor_web.py
```
Abre `http://127.0.0.1:8421`. Mismo comportamiento que la app de escritorio:
estado global, acceso a las carpetas del disco, sin login.

### Modo público (multi-sesión, para desplegar y compartir)
```bash
BASHKAR_PASSWORD=tu-clave python servidor_web.py     # Windows: set BASHKAR_PASSWORD=tu-clave
```
Cada visitante recibe su propia sesión aislada (cookie `sid`, `HttpOnly`) tras
iniciar sesión con la contraseña. Ningún visitante ve los proyectos, el estado
ni las claves de API de otro. Las claves de proveedor de IA se guardan **solo
en memoria de la sesión**, nunca en disco. Las sesiones inactivas por más de
6 h se liberan automáticamente.

### Capacidades según el host
El frontend consulta `/api/capacidades` y **oculta con un aviso explícito**
lo que no esté disponible en el servidor donde corre (Tesseract, Poppler,
spaCy español) en vez de dejar que el usuario elija algo que va a fallar. En
un despliegue remoto sin Tesseract/Poppler, el **Conversor PDF** (texto
embebido vía PyMuPDF) sigue funcionando completo — es la ruta recomendada
para corpus BNC / Paper Capture en modo web.

### Qué está portado en este tramo
Configuración/proyectos, Conversor PDF, Normalizar, Segmentar, Analizar
(léxico básico), Entidades (NER con spaCy), Resultados (TEI/BibTeX/CSV) y
Dashboard. El resto de los 29 paneles del escritorio (Etiquetador, OCR
multi-ruta, Lingüística, Redes, etc.) muestran su guía HD y quedan señalados
como pendientes de portar — la lógica ya vive en `core/`, solo falta la vista.

### Desplegar en Render
Ver [`render.yaml`](render.yaml). El puerto lo inyecta Render vía `PORT`;
la contraseña se configura como variable de entorno en el dashboard (nunca
se commitea).

---

## Arquitectura técnica

Diagramas C4 (contexto, contenedores, componentes y código) y estado medido
del monolito en [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

```
bashkar_station/
├── app.py              # Frontend escritorio: arranque, navegación, tema (~6.600 líneas)
├── paneles/            # Cada pestaña del escritorio como mixin de BashkarApp
├── gui_comun.py        # Lo compartido por app.py y los paneles (ST, TEMA, versión)
├── ui_redesign.py      # Identidad visual (tokens de color) + panel Inicio
├── servidor_web.py     # Frontend web (http.server stdlib, sin frameworks)
├── web/                # Frontend web: HTML/CSS/JS vanilla, sin build
├── cli.py              # Interfaz de línea de comandos
├── setup_wizard.py     # Asistente de instalación (ventana, multiplataforma)
├── instalar.py         # Instalador de dependencias (consola)
├── core/               # 80+ módulos de procesamiento (sin dependencia de UI)
│   ├── estado.py               # Estado del proyecto — compartido por ambos frontends
│   ├── ocr_engine.py           # Motor OCR multi-ruta
│   ├── ocr_normalizer.py       # Normalización post-OCR histórica
│   ├── article_segmenter.py    # Segmentación de artículos
│   ├── ner_engine.py           # NER híbrido spaCy+BERT+Claude
│   ├── collocation_engine.py   # Collocates, KWIC, n-gramas, dispersión
│   ├── bitacora_engine.py      # Notas de investigación situadas
│   ├── timeline_engine.py      # Timeline HTML interactiva
│   ├── tei_engine.py           # Export XML-TEI P5 + validación
│   ├── okf_export_engine.py    # Export bundle OKF (Open Knowledge Format)
│   ├── methods_reporter.py     # METHODS.md automático
│   ├── kraken_trainer.py       # Dataset HTR para reentrenamiento
│   └── voice_dictation.py      # Dictado por voz en Normalizar
├── datos/              # Capa de datos SQLite
│   ├── schema.py       # DDL: articulos, ocr, entidades, notas_investigacion…
│   ├── normalizaciones.py  # Capas OCR / IA / revisión humana + historial
│   └── repositorio.py  # DAO único punto de acceso
├── benchmark/          # Benchmark OCR formal (referencias humanas + línea base)
└── tests/              # 1000+ tests (pytest)
```

**Decisiones de diseño:**
- **Tkinter** — incluido con Python, cero dependencias de UI, funciona 100% offline
- **Un solo lugar para el color** — la identidad (grafito, cobre, teal) vive en `ui_redesign.Theme`; las paletas de `app.py` y las variables de `web/styles.css` se derivan de ahí, así que escritorio y web no pueden divergir
- **JSON + SQLite** — proyectos inspeccionables con cualquier editor o Excel
- **Offline-first** — todas las funciones analíticas funcionan sin internet; Claude/GPT son opcionales
- **Página como unidad atómica** — la sub-segmentación intra-página es imposible con el OCR de la BNC (columnas mezcladas); se documenta como decisión metodológica
- **Arcaísmos preservados** — el normalizador NO moderniza el español de los años 30

---

## Decisiones metodológicas documentadas

| Decisión | Razón |
|----------|-------|
| Página = unidad atómica | OCR BNC mezcla columnas en stream lineal sin información espacial recuperable |
| Sin lematización por defecto | Preserva variación ortográfica histórica como dato lingüístico |
| Stopwords personalizables | Corpus histórico requiere listas propias (topónimos, arcaísmos válidos) |
| Tres rutas OCR | Cada ruta tiene trade-offs documentados (tiempo, costo, calidad); el investigador elige |
| Multi-proveedor IA | Sin dependencia de un proveedor; degrada gracefully a spaCy/BERT offline |
| Elección de OCR medida, no intuida | El módulo Benchmark compara rutas con CER/WER contra un estándar de oro (ver abajo) |

---

## Manual de usuario

[`manual/salida/Manual_Bashkar_Station.pdf`](manual/salida/Manual_Bashkar_Station.pdf)
— 42 páginas: marco metodológico, puesta en marcha, seis recorridos de trabajo
completos, y la referencia de los treinta paneles.

No se escribe entero a mano: la referencia **se genera desde
`core/guia_modulos.py`**, la misma fuente que alimenta la ayuda dentro de la
aplicación, de modo que manual e interfaz no puedan contradecirse. Para
regenerarlo tras cambiar el código:

```bash
python manual/generar_manual.py --pdf     # HTML + PDF (necesita Chrome o Edge)
```

El HTML es autocontenido —estilos incrustados, sin recursos externos— y se abre
desde una memoria USB sin conexión.

---

## Benchmark de OCR — elegir motor con datos

Elegir ruta de OCR «porque se ve mejor» no es defendible en una publicación.
El panel **⚖️ Benchmark OCR** transcribe las mismas páginas con varias rutas y
las compara contra una transcripción de referencia hecha a mano:

| Métrica | Qué mide | Lectura |
|---|---|---|
| **CER** | proporción de caracteres a corregir | ≤0,05 casi limpio · ≤0,10 explotable · ≤0,25 requiere corrección · >0,25 inservible |
| **WER** | lo mismo por palabras | siempre mayor que el CER: un carácter invalida la palabra |
| **Similitud normalizada** | `1 − CER` | comparable con la literatura de HTR |
| **s/página** | costo en tiempo | decide qué ruta sirve para el corpus completo y cuál solo para la muestra |

Exporta a CSV o como tabla Markdown lista para pegar en un artículo.

### Benchmark de regresión

`benchmark/` convierte la medición en una prueba repetible: cada caso declara
su imagen, su transcripción humana y los estratos (revista, año, tipografía,
calidad de imagen). `scripts/benchmark_ocr_regresion.py verificar` compara
contra una línea base congelada y sale con error si una ruta empeora. Añade
dos tasas que el CER esconde: **fusión** de palabras y **fragmentación**. Se
niega a medir contra referencias que no sean humanas. Ver
[benchmark/README.md](benchmark/README.md).

### Rutas comparables

Además de Tesseract (página completa y por zonas), se integran dos motores
recientes, ambos **locales y sin costo por página**:

- **[CHURRO-3B](https://huggingface.co/stanford-oval/churro-3B)** (Ruta 6) —
  modelo de visión-lenguaje de pesos abiertos entrenado sobre 99.491 páginas
  históricas de 46 grupos lingüísticos ([EMNLP 2025](https://aclanthology.org/2025.emnlp-main.1763/)).
  Reporta 82,3 % de similitud en impreso, por encima de Gemini 2.5 Pro y con un
  costo 15,5× menor. Corre en CPU (varios minutos por página): pensado para
  **construir el estándar de oro**, no para procesar el corpus entero. Descarga
  ~7 GB la primera vez y después funciona sin conexión.
  **Solo disponible ejecutando desde código fuente** (`python app.py`): PyTorch
  se excluye del `.exe` a propósito, porque incluirlo llevaría el ejecutable de
  ~1 GB a más de 3 GB. La versión compilada lo indica en pantalla en vez de
  fallar.
- **[PERO-OCR](https://github.com/DCGM/pero-ocr)** (Ruta 7) — motor especializado
  en **prensa digitalizada desde microfilm**, que es exactamente el material de
  la BNC. Cadena clásica (detección de párrafos y líneas + transcripción +
  refinamiento con modelo de lenguaje), órdenes de magnitud más rápida que un
  VLM. Requiere `pip install pero-ocr` y descargar un motor entrenado.

Si a alguna le faltan dependencias, la interfaz la ofrece **deshabilitada con el
motivo a la vista** en vez de fallar a mitad de un lote.

---

## Rendimiento en equipos sin GPU

Bashkar reparte la CPU en lugar de tomarla toda: deja núcleos libres para que la
interfaz siga respondiendo durante un lote. Sin eso, en un portátil de 6 núcleos
un lote de OCR deja la ventana sin repintar y la aplicación **parece congelada**
aunque por dentro esté trabajando.

Tres variables de entorno permiten ajustarlo sin tocar código:

| Variable | Por defecto | Para qué |
|---|---|---|
| `BASHKAR_HILOS` | núcleos físicos − 1 | Hilos de cálculo numérico. Súbelo en una máquina dedicada a un lote nocturno; bájalo si quieres trabajar en otra cosa mientras corre. |
| `BASHKAR_CHURRO_MAX_PIXELS` | `1003520` | Techo de resolución que recibe CHURRO-3B, en píxeles. Manda sobre su velocidad: el modelo trocea la imagen en parches y el tiempo crece con el número de parches. Súbelo si se pierde cuerpo pequeño; bájalo para ir más rápido. |
| `BASHKAR_CHURRO_MIN_PIXELS` | `200704` | Piso de resolución, para que un pie de foto recortado no se diluya. |

Al cambiar los límites de píxeles conviene **volver a medir el CER** con el
benchmark: la velocidad se gana remuestreando hacia abajo, y eso puede costar
calidad.

---

## Exportación para publicación

El botón **📦 Paquete publicación** genera un ZIP con:

```
paquete_publicacion_YYYYMMDD.zip
├── corpus.xml      ← XML-TEI P5 (validado con validar_tei())
├── corpus.bib      ← BibTeX de todas las unidades
├── entidades.csv   ← Índice NER completo
├── bitacora.md     ← Notas del investigador en Markdown
├── METHODS.md      ← Sección de metodología lista para el paper
└── metadatos.json  ← Versiones de software, parámetros, estadísticas
```

---

## Reproducibilidad

Bashkar Station genera automáticamente un archivo **METHODS.md** con:
- Versiones exactas de todos los paquetes usados
- Parámetros del pipeline (DPI, idioma OCR, modelo NER, etc.)
- Estadísticas del corpus (páginas, palabras, artículos, entidades)
- Decisiones metodológicas aplicadas

Este documento está diseñado para incluirse directamente en la sección
de Metodología de papers en revistas de humanidades digitales.

Además:

- **Cada exportación** (TEI, BibTeX, OKF, Excel, PDF buscable, ALTO, PPTX)
  deja al lado un `<archivo>.proveniencia.json` con las fuentes, el commit del
  software (`+sucio` si había cambios sin commitear), la versión de Python y de
  las librerías relevantes, y el aviso de licencias. Lo que no se sabe figura
  como `desconocido`: nunca se rellena.
- **El OCR original nunca se sobrescribe.** El texto de cada página tiene tres
  capas (OCR, corrección automática, revisión humana) y cada cambio queda en
  un historial de solo inserción con autor, hora y commit.
- **Las rutas personales** (`C:\Users\<nombre>`) se reemplazan por `~` en
  los manifiestos.

---

## Citación

Cada versión publicada queda archivada en Zenodo con su propio DOI.

```bibtex
@software{gullavan_bashkar_station_2026,
  author    = {Gullaván Vera, Fabián Andrés},
  title     = {Bashkar Station: Plataforma de Análisis Editorial Computacional
               para Publicaciones Periódicas Históricas},
  year      = {2026},
  version   = {12.0},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.21939405},
  url       = {https://doi.org/10.5281/zenodo.21939405}
}
```

**Dos DOI, y no dan lo mismo:**

| DOI | Resuelve a | Cuándo usarlo |
|-----|-----------|---------------|
| [`10.5281/zenodo.21939404`](https://doi.org/10.5281/zenodo.21939404) | siempre a la versión más reciente | citar el software como proyecto |
| [`10.5281/zenodo.21939405`](https://doi.org/10.5281/zenodo.21939405) | fijo a la versión 12.0 | reproducibilidad: describir los resultados que produjo *esta* versión |

Si publicas resultados obtenidos con la aplicación, cita el DOI de versión: es
el único que garantiza que quien te lea pueda descargar exactamente el mismo
código que ejecutaste.

Los metadatos de citación legibles por máquina están en
[`CITATION.cff`](CITATION.cff), y los del depósito en
[`.zenodo.json`](.zenodo.json). Cuando existe `.zenodo.json`, **Zenodo ignora
`CITATION.cff`**: los dos hay que actualizarlos a la vez o el registro del DOI
y la ficha de GitHub dirán versiones distintas.

---

## Usar Bashkar con otro corpus

La herramienta se calibró sobre *Estampa* (Bogotá, enero–mayo de 1939). Las suposiciones
sobre el corpus que afectan resultados se declaran en el proyecto, en la
clave `config.perfil_corpus` del `.bashkar`:

```json
"perfil_corpus": {
  "id": "caras-y-caretas",
  "terminos_pais": ["argentina", "argentino"],
  "anio_fin": 1940
}
```

- `terminos_pais`: al enlazar entidades con Wikidata, un candidato cuya
  descripción mencione el país del corpus gana un desempate suave.
- `anio_fin`: entidades nacidas o fundadas después se descartan como
  homónimos modernos.

Sin la clave rige el perfil de *Estampa* (Colombia, 1945), el comportamiento
de siempre. Los enlaces de cada perfil se guardan aparte en la caché. Siguen
calibradas para *Estampa* —y documentadas en `docs/DECISIONS.md`— las listas
del normalizador y de la morfología histórica; la abstención por calidad de
OCR (sesión 69) sí se validó sobre nueve publicaciones de la BNC.

---

## Si algo falla sin aviso

Todo error que ocurra dentro de la interfaz o de un proceso en segundo plano
queda en el registro de errores, con las rutas personales anonimizadas, y la
app muestra un aviso en la esquina inferior derecha:

- Windows: `%LOCALAPPDATA%\BashkarStation\logs\errores.log`
- macOS: `~/Library/Application Support/BashkarStation/logs/errores.log`
- Linux: `~/.local/share/BashkarStation/logs/errores.log`

Adjunta ese archivo al reportar un problema. Antes de la sesión 70 el `.exe`
(sin consola) perdía estos errores: así pasó inadvertido que la bitácora no
guardaba notas.

---

## Tests

```bash
# Todos los tests
python -m pytest tests/ -v

# Solo tests de integración
python -m pytest tests/test_integration_pipeline.py -v

# Tests de features v11
python -m pytest tests/test_v11_features.py -v
```

**Estado actual:** ver el badge de CI y la última entrada del
[CHANGELOG](CHANGELOG.md). La CI (`.github/workflows/ci.yml`) instala desde
cero con el lock, corre la suite completa y falla si corren menos tests de los
esperados: una suite verde que se salta tests prueba menos, no más.

---

## Licencia

**Apache License 2.0** — ver [LICENSE](LICENSE) y [NOTICE](NOTICE).

Software libre: puedes usarlo, estudiarlo, modificarlo y redistribuirlo,
incluso con fines comerciales, conservando el aviso de copyright y de licencia
e indicando los cambios que hagas. La licencia incluye una concesión expresa de
patentes. Se ofrece sin garantías.

La licencia de este repositorio cubre **únicamente el código**. Hay tres
capas con licencias distintas:

| Capa | Licencia | ¿Se distribuye aquí? |
|---|---|---|
| Código | Apache 2.0 | Sí |
| Corpus (*Estampa*, enero–mayo de 1939, digitalizado por la Biblioteca Nacional de Colombia) | Publicado con autorización de la BNC; ver [DERECHOS.md](DERECHOS.md) | Sí: transcripciones en `vision_ocr/salida/` y las 792 páginas como imágenes en la *release* `vision-ocr-entrada-v1` |
| Modelos y programas de terceros | Cada uno la suya; ver [LICENCIAS_DE_TERCEROS.md](LICENCIAS_DE_TERCEROS.md) | No: se descargan aparte (CHURRO-3B no se distribuye) |

Las exportaciones repiten este aviso en su manifiesto de proveniencia.

---

## Agradecimientos

- **Biblioteca Nacional de Colombia (BNC)** — digitalización de la revista *Estampa* y autorización para publicar sus imágenes y textos
- **Ministerio de las Culturas, las Artes y los Saberes de Colombia** — Beca a Nuevos Investigadores en Estudios Editoriales, que financió la investigación
- **Instituto Caro y Cuervo** — institución mentora de la beca (sin afiliación)
- Metodología inspirada en: Impresso Project (EPFL), Newspaper Navigator (Library of Congress)
