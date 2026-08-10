# ⬡ Bashkar Station v11.9
### Plataforma de Análisis Editorial Computacional para Publicaciones Periódicas Históricas

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-1145%20passing-brightgreen.svg)](#tests)

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

**Corpus de referencia:** Revista *Estampa* (Colombia, 1930–1940), digitalizada por
la Biblioteca Nacional de Colombia (BNC).

**Institución mentora:** Instituto Caro y Cuervo, Bogotá, Colombia.

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

## Instalación rápida

Funciona en **Windows, macOS y Linux**. Guía completa y paso a paso, escrita
para quien no programa: **[INSTALACION.md](INSTALACION.md)**.

### Requisitos previos
- Python 3.10 o superior
- pip actualizado (`python -m pip install --upgrade pip`)

### Paso 1 — Revisar e instalar lo que falte
```bash
python setup_wizard.py
```
Abre una ventana que revisa el equipo, explica para qué sirve cada componente e
instala los paquetes de Python que falten. Para Tesseract y Poppler —que son
programas del sistema— muestra el comando exacto de tu plataforma
(`brew install …` en macOS, `sudo apt install …` en Linux, el enlace al
instalador en Windows) con un botón para copiarlo.

Gestiona: paquetes de Python · modelo spaCy español (`es_core_news_sm`) ·
Tesseract OCR con el idioma español · Poppler · Kraken y dictado (opcionales).

¿Prefieres la terminal? `python instalar.py` sigue existiendo y hace lo mismo
sin ventana.

### Paso 2 — Ejecutar la app
```bash
python app.py
```
O en Windows: doble clic en `Ejecutar.bat`.

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

```
bashkar_station/
├── app.py              # Frontend escritorio (Tkinter, ~20.000 líneas)
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
│   └── repositorio.py  # DAO único punto de acceso
└── tests/              # 1000+ tests (pytest)
```

**Decisiones de diseño:**
- **Tkinter** — incluido con Python, cero dependencias de UI, funciona 100% offline
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

---

## Citación

Si usas Bashkar Station en tu investigación, por favor cita:

```bibtex
@software{gulla_bashkar_station_2026,
  author    = {Gulla, Fabián},
  title     = {Bashkar Station: Plataforma de Análisis Editorial Computacional
               para Publicaciones Periódicas Históricas},
  year      = {2026},
  version   = {11.9},
  url       = {https://github.com/fabiangulla-pixel/Bashkar-Station}
}
```

Los metadatos de citación legibles por máquina están en
[`CITATION.cff`](CITATION.cff).

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

**Estado actual:** 1145 tests, 0 fallos (16 se saltan por requerir red o
dependencias opcionales). Verificado el 29-jul-2026 en Python 3.14.

---

## Licencia

**Apache License 2.0** — ver [LICENSE](LICENSE) y [NOTICE](NOTICE).

Software libre: puedes usarlo, estudiarlo, modificarlo y redistribuirlo,
incluso con fines comerciales, conservando el aviso de copyright y de licencia
e indicando los cambios que hagas. La licencia incluye una concesión expresa de
patentes. Se ofrece sin garantías.

El corpus de la revista *Estampa* **no** se distribuye con el software: fue
digitalizado por la Biblioteca Nacional de Colombia y tiene sus propias
condiciones de uso. La licencia de este repositorio cubre únicamente el código.

---

## Agradecimientos

- **Biblioteca Nacional de Colombia (BNC)** — acceso al corpus digital de la revista Estampa
- **Instituto Caro y Cuervo** — apoyo institucional y financiamiento de la investigación
- Metodología inspirada en: Impresso Project (EPFL), Newspaper Navigator (Library of Congress)
